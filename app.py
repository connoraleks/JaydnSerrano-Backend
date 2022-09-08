import json
import os
from wsgiref.handlers import format_date_time
from flask import Flask, request, redirect
from flask_mysqldb import MySQL
from flask_restful import Resource, Api
from werkzeug.utils import secure_filename
from flask_cors import CORS
from PIL import Image
import math
import datetime

UPLOAD_FOLDER = '/usr/local/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# Initialize the app
app = Flask(__name__)

# Setup hidden variables for the app
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = os.environ['MYSQL_DB_USERNAME']
app.config['MYSQL_PASSWORD'] = os.environ['MYSQL_DB_PASSWORD']
app.config['MYSQL_DB'] = os.environ['MYSQL_DB_DATABASE']

# Set up cors support for all routes
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Set up API
api = Api(app)

# Set up MySQL
mysql = MySQL(app)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
def find_parent(root, parent_id):
    # root = { dirs: [], photos: [] }
    # recursively find the parent dict
    for dir in root['dirs']:
        if dir['id'] == parent_id:
            return dir
    for dir in root['dirs']:
        return find_parent(dir, parent_id)

class Greeting(Resource):
    def get(self):
        return {'greeting': 'Hello, World!'}
api.add_resource(Greeting, '/')
class Database(Resource):
    def get(self):
        # Recursively sets all section names from upload folder
        stack = []
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            parent_val = None
            # Root folders should have parent set to 0
            if(root != UPLOAD_FOLDER):
                # Get the parent id from the database by querying the parent folder name
                parent_name = root.split('/')[-1]
                cursor = mysql.connection.cursor()
                cursor.execute("SELECT id FROM Dirents WHERE name = %s", (parent_name, ))
                parent_val = cursor.fetchone()[0]
            for dir in dirs:
                cursor = mysql.connection.cursor()
                now = datetime.datetime.now()
                # Format date to YYYY-MM-DD hh:mm:ss EST format
                format_date_time = now.strftime("%Y-%m-%d %H:%M:%S")
                # Insert the directory into the database
                query = "INSERT IGNORE INTO Dirents (name, parent_dirent, isDir, created_at, path, url) VALUES (%s, %s, %s, %s, %s, %s)"
                path = root.split('uploads')[1] + '/'+ dir
                cursor.execute(query, (dir, parent_val, '1', format_date_time, path, 'https://uploads.jaydnserrano.com'+path))
                mysql.connection.commit()
                cursor.close()
                # Add the directory to the stack
                stack.append(root + '/' + dir)
            for photo in files: 
                cursor = mysql.connection.cursor()
                now = datetime.datetime.now()
                format_date_time = now.strftime("%Y-%m-%d %H:%M:%S")
                query = "INSERT IGNORE INTO Dirents (name, parent_dirent, isDir, created_at, path, url) VALUES (%s, %s, %s, %s, %s, %s)"
                path = root.split('uploads')[1] + '/' + photo
                cursor.execute(query, (photo, parent_val, '0', format_date_time, path, 'https://uploads.jaydnserrano.com'+path))
                mysql.connection.commit()
                cursor.close()
                stack.append(root + '/' + photo)
        return {'status': 'success', 'data': stack}
api.add_resource(Database, '/database')
class Login(Resource):
    def post(self):
        username = request.json['username']
        password = request.json['password']
        return self.validate(username, password)
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
        #Get all photos by walking the upload folder
        photos = {}
        for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
            root = root.split('/')[-1]
            photos[root] = []
            for file in files:
                im = Image.open(UPLOAD_FOLDER + '/' + root + '/' + file)
                width, height = im.size
                photos[root].append({'name': file, 'src': 'https://uploads.jaydnserrano.com/' + root + '/' + file, 'width': width, 'height': height})
        return {'response': 'Successfully retrieved all photos', 'success': True, 'photos': photos}
         
            
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
        section = request.json['section']
        parent = request.json['parent'] if 'parent' in request.json else None
        # If the section exists and the parent is the same, return success
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM Sections WHERE name = %s", (section,))
        if cur.rowcount > 0 and cur.fetchone()[2] == parent:
            return {'response': 'Section already exists', 'success': True}
        # If the section doesn't exist, create it
        cur.execute("INSERT IGNORE INTO Sections (name, parent) VALUES (%s, %s)", (section, parent))
        mysql.connection.commit()
        cur.close()
        # if parent is not None, add it to section name 
        if parent is not None:
            section = parent + '/' + section
        print(section)
        # If the directory doesn't exist, create it
        if not os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], section)):
            os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], section))
        return {'response': 'Sections successfully created', 'success': True}
    def get(self):
        # Dirent Structure: id, name, parent_dirent, isDir, created_at, path
        root = {'dirs': [], 'photos': [] }
        # Get all the root directories
        cursor = mysql.connection.cursor()
        query = "SELECT * FROM Dirents WHERE parent_dirent IS NULL"
        cursor.execute(query)
        for (id, name, parent_dirent, isDir, created_at, path, url) in cursor.fetchall():
            if(isDir == 1):
                root['dirs'].append({'id': id, 'name': name, 'url': url, 'path': path, 'dirs': [], 'photos': [], 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S")})
            else:
                im = Image.open(UPLOAD_FOLDER + path)
                width, height = im.size
                root['photos'].append({'id': id, 'name': name, 'src': url, 'width': width, 'height': height, 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S")})
        # Get all the subdirectories
        query = "SELECT * FROM Dirents WHERE parent_dirent IS NOT NULL"
        cursor.execute(query)
        for (id, name, parent_dirent, isDir, created_at, path, url) in cursor.fetchall():
            parent = find_parent(root, parent_dirent)
            if(isDir == 1):
                parent['dirs'].append({'id': id, 'name': name, 'url': url, 'path': path, 'dirs': [], 'photos': [], 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S")})
            else:
                im = Image.open(UPLOAD_FOLDER + path)
                width, height = im.size
                parent['photos'].append({'id': id, 'name': name, 'src': url, 'width': width, 'height': height, 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S")})
        return {'response': 'Successfully retrieved all sections', 'success': True, 'sections': root}
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