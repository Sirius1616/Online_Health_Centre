import pandas as pd
from sklearn.neural_network import MLPClassifier
import joblib


file_path1 = 'Model/data/input/general.csv'  # Replace with the actual file path
dataset1 = pd.read_csv(file_path1)
file_path2 = 'recommend/data/input/specialist.csv'  # Replace with the actual file path
dataset2 = pd.read_csv(file_path2)
merged_dataset = pd.concat([dataset1, dataset2], ignore_index=True)
merged_dataset.columns = merged_dataset.columns.str.strip()

conditions = merged_dataset['Condition']
doctors = merged_dataset['Doctor']
unique_conditions = conditions.unique()
unique_doctors = doctors.unique()
condition_to_index = {condition: index for index, condition in enumerate(unique_conditions)}
doctor_to_index = {doctor: index for index, doctor in enumerate(unique_doctors)}
conditions = conditions.map(condition_to_index)
doctors = doctors.map(doctor_to_index)

clf = MLPClassifier(hidden_layer_sizes=(20,), max_iter=10000, activation="relu", solver="adam")
X_train = conditions.values.reshape(-1, 1)  # Reshape to 2D array
y_train = doctors
clf.fit(X_train, y_train)

model_filename = 'Model/data/output/model.pkl'  # Choose a filename
joblib.dump(clf, model_filename)
print("Model has been trained & successfully and saved as", model_filename)
