import os
from wsgiref.handlers import format_date_time
from flask import Flask, request, redirect
from flask_mysqldb import MySQL
from flask_restful import Resource, Api
from werkzeug.utils import secure_filename
from flask_cors import CORS
from PIL import Image
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
    child = None
    if(len(root['dirs']) == 0):
        return None
    for dir in root['dirs']:
        if dir['id'] == parent_id:
            return dir
    for dir in root['dirs']:
        val = find_parent(dir, parent_id)
        child = val if val is not None else child
    return child
def set_priority(priority_array):
    # Given a list of photo ids, set the priority of each photo to its index in the list
    cursor = mysql.connection.cursor()
    for (photo_id, index) in priority_array:
        cursor.execute("UPDATE Dirents SET priority = %s WHERE id = %s", (index, photo_id))
    mysql.connection.commit()
    cursor.close()
class Greeting(Resource):
    def get(self):
        # Return a table of contents for the API links below
        return {
            'api': [
                {
                    'url': '/database',
                    'method': 'GET',
                    'description': 'Verifies the integrity of the database contents with the filesystem'
                },
                {
                    'url': '/login',
                    'method': 'POST',
                    'description': 'Logs in a use to the admin panel'
                },
                {
                    'url': '/dirents',
                    'method': 'POST',
                    'description': 'Inserts a new directory entry into the database'
                },
                {
                    'url': '/dirents',
                    'method': 'GET',
                    'description': 'Returns a list of directory entries'
                },
                {
                    'url': '/dirents',
                    'method': 'DELETE',
                    'description': 'Deletes a directory entry from the database'
                }]}   
api.add_resource(Greeting, '/')
class Database(Resource):
    def post(self):
        # Receive an array of dirent id's and set the priority of each dirent to its index
        data = request.get_json()
        set_priority(data)
    def get(self):
        # Recursively sets all dirent names from upload folder
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
                # Attempt to Insert the directory into the database
                query = "INSERT IGNORE INTO Dirents (name, parent_dirent, isDir, created_at, path, url) VALUES (%s, %s, %s, %s, %s, %s)"
                path = root.split('uploads')[1] + '/'+ dir
                cursor.execute(query, (dir, parent_val, '1', format_date_time, path, 'https://uploads.jaydnserrano.com'+path))
                mysql.connection.commit()
                # Update the path and url of the directory
                cursor.execute("UPDATE Dirents SET path = %s, url = %s WHERE name = %s", (path, 'https://uploads.jaydnserrano.com'+path, dir))
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
                cursor.execute("UPDATE Dirents SET path = %s, url = %s WHERE name = %s", (path, 'https://uploads.jaydnserrano.com'+path, photo))
                mysql.connection.commit()
                cursor.close()
                stack.append(root + '/' + photo)
        return {'success': True, 'data': stack}
api.add_resource(Database, '/database')
class Login(Resource):
    def post(self):
        username = request.json['username']
        password = request.json['password']
        return {'response': 'Login successful', 'success': True} if username == os.environ['JSADMIN_USERNAME'] and password == os.environ['JSADMIN_PASSWORD'] else {'response': 'Login failed', 'success': False}
api.add_resource(Login, '/login')

class Dirents(Resource):
    def post(self):
        # Retrieve the name name from the request
        name = request.form['name']
        # Retrieve the parent name id from the request
        parent = request.form['parent'] if request.form['parent'] != '-1' else None
        # Retrieve the type of name from the request (0 = photo, 1 = directory)
        direntType = request.form['type']
        # Make cursor
        cursor = mysql.connection.cursor()
        # Check if name already exists
        cursor.execute("SELECT * FROM Dirents WHERE name = %s", (name,))
        if cursor.rowcount > 0:
            print(cursor.rowcount, cursor.fetchAll())
            return {'response': 'Dirent already exists', 'success': True}
        parent_path = ''
        # Query for the parent name path
        if parent != None: 
            cursor.execute("SELECT path FROM Dirents WHERE id = %s", (parent, ))
            parent_path = cursor.fetchone()[0]
        print(name + ' ' + str(parent) + ' ' + str(direntType) + ' ' + parent_path)
        format_date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        path = parent_path + '/' + name
        # Insert the directory into the database
        if direntType == '1':
            query = "INSERT INTO Dirents (name, parent_dirent, isDir, created_at, path, url) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(query, (name, parent, '1', format_date_time, path, 'https://uploads.jaydnserrano.com'+path))
            # Commit the changes to the database
            mysql.connection.commit()
            cursor.close()
                        
        elif direntType == '0':
            query = "INSERT INTO Dirents (name, parent_dirent, isDir, created_at, path, url) VALUES (%s, %s, %s, %s, %s, %s)"
            cursor.execute(query, (name, parent, '0', format_date_time, path, 'https://uploads.jaydnserrano.com'+path))
            # Commit the changes to the database
            mysql.connection.commit()
            cursor.close()
        
        # Make the directory or copy the image to the location specified by the variable path
        if direntType == '1':
            print('This is upload path: ' + UPLOAD_FOLDER[1:] + path)
            os.makedirs(UPLOAD_FOLDER[1:] + path)
        elif direntType == '0':
            file = request.files['file']
            file.save(UPLOAD_FOLDER[1:] + path)
        return {'response': 'Dirent created at: ' + os.path.join(app.config['UPLOAD_FOLDER'], path), 'success': True}
         
    def get(self):
        # Dirent Structure: id, name, parent_dirent, isDir, created_at, path
        root = {'dirs': [], 'photos': [] }
        # Get all the root directories
        cursor = mysql.connection.cursor()
        query = "SELECT * FROM Dirents WHERE parent_dirent IS NULL"
        cursor.execute(query)
        for (id, name, parent_dirent, isDir, created_at, path, url, priority) in cursor.fetchall():
            if(isDir == 1):
                root['dirs'].append({'id': id, 'name': name, 'url': url, 'path': path, 'dirs': [], 'photos': [], 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S"), 'priority': priority})
            else:
                im = Image.open(UPLOAD_FOLDER + path)
                width, height = im.size
                root['photos'].append({'id': id, 'name': name, 'src': url, 'width': width, 'height': height, 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S"), 'priority': priority})
        # Get all the subdirectories
        query = "SELECT * FROM Dirents WHERE parent_dirent IS NOT NULL AND isDir = 1"
        cursor.execute(query)
        for (id, name, parent_dirent, isDir, created_at, path, url, priority) in cursor.fetchall():
            parent = find_parent(root, parent_dirent)
            if(parent == None):
                print('Parent not found for: ' + name)
                continue
            parent['dirs'].append({'id': id, 'name': name, 'url': url, 'path': path, 'dirs': [], 'photos': [], 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S"), 'priority': priority})
        # Get all the photos
        query = "SELECT * FROM Dirents WHERE parent_dirent IS NOT NULL AND isDir = 0"
        cursor.execute(query)
        for (id, name, parent_dirent, isDir, created_at, path, url, priority) in cursor.fetchall():
            parent = find_parent(root, parent_dirent)
            if(parent == None):
                print('Parent not found for: ' + name)
                continue
            im = Image.open(UPLOAD_FOLDER + path)
            width, height = im.size
            parent['photos'].append({'id': id, 'name': name, 'src': url, 'width': width, 'height': height, 'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S"), 'priority': priority})
        cursor.close()
        return {'response': 'Successfully retrieved all dirents', 'success': True, 'dirents': root}
    
    def delete(self, id):
        # Retrieve the name id from the url (format: /dirents/<id>)
        print('id: ' + id)
        # Make cursor
        cursor = mysql.connection.cursor()
        # Query for the name path
        cursor.execute("SELECT isDir,path FROM Dirents WHERE id = %s", (id, ))
        isDir, path = cursor.fetchone()
        if(path and isDir == 1):
            # See if the directory is empty
            cursor.execute("SELECT * FROM Dirents WHERE parent_dirent = %s", (id, ))
            if cursor.rowcount > 0:
                return {'response': 'Directory is not empty', 'success': False}
        if(path):
            # Delete the row from the database
            cursor.execute("DELETE FROM Dirents WHERE id = %s", (id, ))
            # Commit the changes to the database
            cursor.connection.commit()
            # Delete the directory or image from the location specified by the variable path
            if os.path.isdir(UPLOAD_FOLDER + path):
                os.rmdir(UPLOAD_FOLDER[1:] + path)
            else:
                os.remove(UPLOAD_FOLDER[1:] + path)
            return {'response': 'Dirent deleted at: ' + os.path.join(app.config['UPLOAD_FOLDER'], path), 'success': True}
        else:
            return {'response': 'Dirent does not exist', 'success': False}
    def put(self, id):
        name = request.form['name']
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT path FROM Dirents WHERE id = %s", (id, ))
        path = cursor.fetchone()[0]
        # Rename the directory or image from the location specified by the variable path
        try:
            os.rename(UPLOAD_FOLDER[1:] + path, UPLOAD_FOLDER[1:] + path[:path.rfind('/')+1] + name)
            cursor.execute("UPDATE Dirents SET name = %s, path = %s, url = %s WHERE id = %s", (name, path[:path.rfind('/')+1] + name, 'https://uploads.jaydnserrano.com' + path[:path.rfind('/')+1] + name, id))
            cursor.connection.commit()
            return {'response': 'Dirent renamed at: ' + os.path.join(app.config['UPLOAD_FOLDER'], path), 'success': True}
        except Exception as e:
            print(e)
            return {'response': 'Dirent could not be renamed', 'success': False, 'error': str(e)}
        
api.add_resource(Dirents, '/dirents', '/dirents/<id>')




if __name__ == '__main__':
    app.run(debug=True , threaded=True)