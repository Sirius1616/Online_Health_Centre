from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import pymysql
import re
import secrets
from Modules.configuration import DATABASE_CONFIG
from Modules.private import SECRET_KEY
import datetime

from Modules.physician import RecommendationModel

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
    """Render the home page."""
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handle user login.

    If the user submits the login form, check the credentials against the database.
    If valid, create a session for the user and redirect to the dashboard.
    If invalid, display an error message.

    Returns:
        render_template: Renders the login page.
    """
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username_input = request.form['username']
        password_input = request.form['password']
        
        with pymysql.connect(**DATABASE_CONFIG) as db_connection:
            with db_connection.cursor(pymysql.cursors.DictCursor) as db_cursor:
                # Fetch user account from database
                db_cursor.execute('SELECT * FROM users WHERE username = %s', (username_input,))
                user_account = db_cursor.fetchone()

                # Check if user credentials are correct
                if user_account and user_account['password'] == password_input:
                    session['loggedin'] = True
                    session['id'] = user_account['id']
                    session['username'] = user_account['username']
                    return redirect(url_for('dashboard'))
                else:
                    flash('danger', 'Incorrect username or password!')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Log out the user and redirect to the login page."""
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handle user registration.

    If the user submits the registration form, validate the input and create a new user account in the database.
    If the account already exists or if the input is invalid, display an error message.

    Returns:
        render_template: Renders the registration page.
    """
    if request.method == 'POST':
        username_input = request.form['username']
        password_input = request.form['password']
        email_input = request.form['email']
        name_input = request.form['name']
        phone_input = request.form['phone']
        
        with pymysql.connect(**DATABASE_CONFIG) as db_connection:
            with db_connection.cursor(pymysql.cursors.DictCursor) as db_cursor:
                # Check if the username already exists
                db_cursor.execute('SELECT * FROM users WHERE username = %s', (username_input,))
                user_account = db_cursor.fetchone()
                
                if user_account:
                    flash('danger', 'Account already exists!')
                elif not re.match(r'[^@]+@[^@]+\.[^@]+', email_input):
                    flash('danger', 'Invalid email address!')
                elif not re.match(r'[A-Za-z0-9]+', username_input):
                    flash('danger', 'Username must contain only characters and numbers!')
                else:
                    # Create a new user account
                    db_cursor.execute(
                        'INSERT INTO users (username, password, email, name, phone) VALUES (%s, %s, %s, %s, %s)',
                        (username_input, password_input, email_input, name_input, phone_input)
                    )
                    db_connection.commit()
                    flash('success', 'You have successfully registered!')

    return render_template('register.html')


@app.route('/booking')
def booking():
    """Render the booking page."""
    return render_template('booking.html')


@app.route('/dashboard')
def dashboard():
    """Render the dashboard for logged-in users."""
    return render_template('patient.html')


def generate_token():
    """Generate a unique token for appointment bookings."""
    return secrets.token_hex(8)


@app.route('/book_appointment', methods=['POST'])
def book_appointment():
    """
    Book an appointment.

    Validate input data and store the appointment details in the database.
    Generate a unique token for the appointment and recommend a specialist based on the patient's condition.

    Returns:
        render_template: Renders the recommendation page with the booked appointment details.
    """
    if request.method == 'POST':
        name_input = request.form['name']
        age_input = request.form['age']
        dob_str = request.form['dob']
        phone_input = request.form['phone']
        email_input = request.form['email']
        specialist_input = request.form['specialist']
        patient_condition_input = request.form['patient_condition']
        medical_history_input = request.form['medical-history']

        # Validate required fields
        if not name_input or not age_input or not dob_str or not phone_input or not email_input:
            flash('danger', 'All fields are required')
            return redirect(url_for('booking'))
        
        # Recommend a specialist for the patient's condition
        recommended_specialist = recommendation_model.recommend_doctor(patient_condition_input)
        print(f'Recommended Specialist: {specialist_input}')

        # Validate the date of birth format
        formats = ["%d/%m/%Y", "%d-%m-%Y"]
        dob = None
        for fmt in formats:
            try:
                dob = datetime.datetime.strptime(dob_str, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

        if dob is None:
            flash('danger', 'Invalid date format')
            return redirect(url_for('booking'))

        with pymysql.connect(**DATABASE_CONFIG) as db_connection:
            with db_connection.cursor(pymysql.cursors.DictCursor) as db_cursor:
                # Generate a unique appointment token
                db_cursor.execute('SELECT MAX(token) AS max_token FROM appointments')
                max_token = db_cursor.fetchone()
                if max_token and max_token['max_token']:
                    last_token_number = int(max_token['max_token'][2:])
                    new_token_number = last_token_number + 1
                    token = f'HC{new_token_number:04d}'
                else:
                    token = 'HC0001'

                # Insert the appointment details into the database
                db_cursor.execute('INSERT INTO appointments (token, name, age, dob, phone, email, specialist, patient_condition, medical_history) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                               (token, name_input, age_input, dob, phone_input, email_input, specialist_input, patient_condition_input, medical_history_input))
                db_connection.commit()

                # Fetch the newly created appointment for display
                db_cursor.execute('SELECT * FROM appointments WHERE token = %s', (token,))
                new_appointment = db_cursor.fetchone()

        flash('success', f'Appointment booked successfully! Your appointment token is: {token}')
        return render_template('recommend.html', recommended_doctor=recommended_specialist, form_data=request.form, token=token)

    return render_template('booking.html')


@app.route('/display_tokens')
def display_tokens():
    """Display all appointment tokens."""
    with pymysql.connect(**DATABASE_CONFIG) as db_connection:
        with db_connection.cursor(pymysql.cursors.DictCursor) as db_cursor:
            db_cursor.execute('SELECT token FROM appointments')
            tokens = db_cursor.fetchall()

    token_list = [token['token'] for token in tokens]
    return render_template('token.html', token_list=token_list)


@app.route('/recommend_appointment')
def recommend_appointment_route():
    """
    Provide appointment recommendations based on the specified index.

    This function fetches and displays a list of recommended appointments.

    Returns:
        render_template: Renders the recommendation page with appointment details.
    """
    appointment_index = 5
    num_recommendations = 3
    recommendations = recommendation_model.recommend(appointment_index, num_recommendations)

    return render_template('recommendation.html', recommendations=recommendations)


if __name__ == '__main__':
    app.run(debug=True)
