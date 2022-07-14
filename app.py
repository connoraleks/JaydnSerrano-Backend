from mysql.connector import connect, Error
import os
from flask import Flask, request, redirect
from flask_restful import Resource, Api
from werkzeug.utils import secure_filename
from flask_cors import CORS

connection = None
NCERROR = {'response': 'No connection', 'success': False }
UPLOAD_FOLDER = '/usr/local/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
CORS(app, supports_credentials=True)
api = Api(app)
def get_connection():
    global connection
    if connection is None:
        try:
            connection = connect(
                host="localhost",
                user=os.environ['MYSQL_DB_USERNAME'],
                password=os.environ['MYSQL_DB_PASSWORD'],
                database=os.environ['MYSQL_DB_DATABASE']
            )
        except Error as e:
            print(e)
            return None
    return connection
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Login(Resource):
    def post(self):
        username = request.json['username']
        password = request.json['password']
        return self.validate(username, password)
        return login()
    def validate(self, username, password):
        if username == os.environ['JSADMIN_USERNAME'] and request.json['password'] == os.environ['JSADMIN_PASSWORD']:
            return {'response': 'Login successful', 'success': True}
        return {'response': 'Invalid username or password', 'success': False}
api.add_resource(Login, '/login')

class Photos(Resource):
    def post(self):
        if 'file' not in request.files:
            return {'response': 'No file part', 'success': False}
        file = request.files['file']
        if file.filename == '':
            return {'response': 'No file selected for uploading', 'success': False}
        if file and allowed_file(file.filename):
            filename = request.form['section'] + '/' + request.form['name']
            # Save file, make parent directory if it doesn't exist
            if not os.path.exists(os.path.dirname(os.path.join(app.config['UPLOAD_FOLDER'], filename))):
                os.makedirs(os.path.dirname(os.path.join(app.config['UPLOAD_FOLDER'], filename)))
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return {'response': 'File successfully uploaded', 'success': True}
        return {'response': 'Allowed file types are txt, pdf, png, jpg, jpeg, gif', 'success': False}
api.add_resource(Photos, '/photos')

class Sections(Resource):
    def post(self):
        # Retrieve the section name from the request
        sections = request.json['sections']
        # Create section folders
        for section in sections:
            if not os.path.exists(app.config['UPLOAD_FOLDER'] + '/' + section):
                os.makedirs(app.config['UPLOAD_FOLDER'] + '/' + section)
        return {'response': 'Sections successfully created', 'success': True}
    def get(self):
        # Send the list of sections as json
        return {'response': os.listdir(app.config['UPLOAD_FOLDER']), 'success': True}
    def delete(self):
        # Retrieve the section name from the request
        sections = request.json['sections']
        # Move all files to the 'other' section
        for section in sections:
            for filename in os.listdir(app.config['UPLOAD_FOLDER'] + '/' + section):
                os.rename(app.config['UPLOAD_FOLDER'] + '/' + section + '/' + filename, app.config['UPLOAD_FOLDER'] + '/other/' + filename)
        # Delete section folders
        for section in sections:
            if os.path.exists(app.config['UPLOAD_FOLDER'] + '/' + section):
                os.rmdir(app.config['UPLOAD_FOLDER'] + '/' + section)
        return {'response': 'Sections successfully deleted', 'success': True}
api.add_resource(Sections, '/sections')




if __name__ == '__main__':
    app.run(debug=True)