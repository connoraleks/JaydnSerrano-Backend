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
# Set up cors support for all routes
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
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
class Greeting(Resource):
    def get(self):
        return {'greeting': 'Hello, World!'}
api.add_resource(Greeting, '/')
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
    def get(self):
        # Get all photos organized by their parent directory
        photos = {}
        for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
            for file in files:
                #if file is an image regardless of capitalization
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                    section = root.split('/')[-1]
                    if section not in photos:
                        photos[section] = []
                    photo = {'name': file, 'url': 'https://uploads.jaydnserrano.com/' + section + '/' + file}
                    photos[section].append(photo)
        return {'response': photos, 'success': True}
    def delete(self):
        # Delete particular photo
        filename = request.json['section'] + '/' + request.json['name']
        if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return {'response': 'File successfully deleted', 'success': True}
        return {'response': 'File does not exist', 'success': False}
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
        # Send the list of sections as json excluding the 'other' section
        sections = []
        for section in os.listdir(app.config['UPLOAD_FOLDER']):
            if section != 'other':
                sections.append(section)
        # Count the number of photos in each section
        count = {}
        for section in sections:
            count[section] = len(os.listdir(app.config['UPLOAD_FOLDER'] + '/' + section))
        return {'sections': sections, 'count': count, 'success': True}
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
    app.run(debug=True , threaded=True)