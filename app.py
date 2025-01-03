from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
import re
import secrets
from Modules.config import DATABASE_CONFIG
from Modules.secret import SECRET_KEY
import datetime
from Modules.doctor import RecommendationModel

app = Flask(__name__)
app.secret_key = SECRET_KEY

# Set up the initial database and tables
db_connection = pymysql.connect(**DATABASE_CONFIG)
with db_connection.cursor() as cursor:
    # Create the database if it doesn't exist
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE_CONFIG['database']}")
    cursor.execute(f"USE {DATABASE_CONFIG['database']}")

    # Create the users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
            password VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            name VARCHAR(255) NOT NULL,
            phone VARCHAR(15) NOT NULL
        )
    """)

    # Create the appointments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            token VARCHAR(10) NOT NULL,
            name VARCHAR(255) NOT NULL,
            age INT NOT NULL,
            dob DATE NOT NULL,
            phone VARCHAR(15) NOT NULL,
            email VARCHAR(255) NOT NULL,
            specialist VARCHAR(255) NOT NULL,
            patient_condition VARCHAR(255) NOT NULL,
            medical_history TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

# Commit changes and close the connection
db_connection.commit()
db_connection.close()

# Load the recommendation model
data_path = "Model/data/input/appointments.csv"
model_filename = 'Model/data/output/model.pkl'
specialist_dataset_filename = 'Model/data/input/specialist.csv'
general_physician_dataset_filename = 'Model/data/input/general.csv'
recommendation_model = RecommendationModel(data_path, model_filename, specialist_dataset_filename, general_physician_dataset_filename)


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        
        with pymysql.connect(**DATABASE_CONFIG) as connection:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                account = cursor.fetchone()

                if account and account['password'] == password:
                    session['loggedin'] = True
                    session['id'] = account['id']
                    session['username'] = account['username']
                    return redirect(url_for('dashboard'))
                else:
                    flash('danger', 'Incorrect username or password!')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        name = request.form['name']
        phone = request.form['phone']
        
        with pymysql.connect(**DATABASE_CONFIG) as connection:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                account = cursor.fetchone()
                
                if account:
                    flash('danger', 'Account already exists!')
                elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
                    flash('danger', 'Invalid email address!')
                elif not re.match(r'[A-Za-z0-9]+', username):
                    flash('danger', 'Username must contain only characters and numbers!')
                else:
                    cursor.execute(
                        'INSERT INTO users (username, password, email, name, phone) VALUES (%s, %s, %s, %s, %s)',
                        (username, password, email, name, phone)
                    )
                    connection.commit()
                    flash('success', 'You have successfully registered!')

    return render_template('register.html')

@app.route('/booking')
def booking():
    return render_template('booking.html')

@app.route('/dashboard')
def dashboard():
    return render_template('patient.html')

def generate_token():
    return secrets.token_hex(8)

@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        dob_str = request.form['dob']
        phone = request.form['phone']
        email = request.form['email']
        specialist = request.form['specialist']
        patient_condition = request.form['patient_condition']
        medical_history = request.form['medical-history']

        if not name or not age or not dob_str or not phone or not email:
            flash('danger', 'All fields are required')
            return redirect(url_for('booking'))
        
        recommended_doctor = recommendation_model.recommend_doctor(patient_condition)
        print(f'Recommended Specialist: {specialist}')

        formats = ["%d/%m/%Y", "%d-%m-%Y"]
        dob = None
        for format in formats:
            try:
                dob = datetime.datetime.strptime(dob_str, format).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

        if dob is None:
            flash('danger', 'Invalid date format')
            return redirect(url_for('booking'))

        with pymysql.connect(**DATABASE_CONFIG) as connection:
            with connection.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute('SELECT MAX(token) AS max_token FROM appointments')
                max_token = cursor.fetchone()
                if max_token and max_token['max_token']:
                    last_token_number = int(max_token['max_token'][2:])
                    new_token_number = last_token_number + 1
                    token = f'HC{new_token_number:04d}'
                else:
                    token = 'HC0001'

                cursor.execute('INSERT INTO appointments (token, name, age, dob, phone, email, specialist, patient_condition, medical_history) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                               (token, name, age, dob, phone, email, specialist, patient_condition, medical_history))
                connection.commit()

                cursor.execute('SELECT * FROM appointments WHERE token = %s', (token,))
                new_appointment = cursor.fetchone()

        flash('success', f'Appointment booked successfully! Your appointment token is: {token}')
        return render_template('recommend.html', recommended_doctor=recommended_doctor, form_data=request.form, token=token)

    return render_template('booking.html')

@app.route('/display_tokens')
def display_tokens():
    with pymysql.connect(**DATABASE_CONFIG) as connection:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute('SELECT token FROM appointments')
            tokens = cursor.fetchall()

    token_list = [token['token'] for token in tokens]
    return render_template('token.html', token_list=token_list)

@app.route('/recommend_appointment')
def recommend_appointment_route():
    appointment_index = 5
    num_recommendations = 5
    recommendations = recommendation_model.get_recommendations(appointment_index, num_recommendations)
    return render_template('recommend.html', recommendations=recommendations)

def get_appointment_details(appointment_index):
    with pymysql.connect(**DATABASE_CONFIG) as connection:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute('SELECT * FROM appointments WHERE id = %s', (appointment_index,))
            appointment_details = cursor.fetchone()
    return appointment_details

@app.context_processor
def utility_processor():
    def get_appointment_details_wrapper(appointment_index):
        return get_appointment_details(appointment_index)
    return dict(get_appointment_details=get_appointment_details_wrapper)

@app.route('/recommendations/<int:appointment_index>')
def show_recommendations(appointment_index):
    num_recommendations = 5
    recommendations = recommendation_model.get_recommendations(appointment_index, num_recommendations)
    recommendation_details = [get_appointment_details(index) for index in recommendations]
    return render_template('recommends.html', recommendations=recommendation_details)

@app.route('/suggest_specialist', methods=['POST'])
def suggest_specialist():
    patient_condition = request.json['patient_condition']
    suggested_specialist = RecommendationModel(patient_condition)
    return jsonify(suggested_specialist)

if __name__ == '__main__':
    app.run(debug=True)
