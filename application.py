from flask import Flask, render_template, make_response, request, redirect, url_for, session
from flask_restful import Resource, Api
from flask_cors import CORS
from boto3.dynamodb.conditions import Key, Attr
import boto3
from PIL import Image
from pathlib import Path
import os
from wsgiref.handlers import format_date_time
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
import datetime
import shutil
# Upload folder constant, used to store photos temporarily
UPLOAD_FOLDER = '/tmp/photos/'
# Allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# Initialize the application
application = Flask(__name__)
# Setup hidden variables for the application
application.config['UPLOAD_FOLDER'] = '/tmp/photos/'
application.config['MYSQL_HOST'] = os.environ['MYSQL_HOST']
application.config['MYSQL_USER'] = os.environ['MYSQL_USER']
application.config['MYSQL_PASSWORD'] = os.environ['MYSQL_PASSWORD']
application.config['MYSQL_DB'] = os.environ['MYSQL_DB']
# Set up cors support for all routes
CORS(application, resources={r"/*": {"origins": "*"}}, supports_credentials=True)
# Set up API
api = Api(application)
# Set up MySQL
mysql = MySQL(application)
# Set up S3
s3 = boto3.Session( aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'], aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'], region_name=os.environ['AWS_REGION']).resource('s3')
# Get the S3 bucket
bucket = s3.Bucket(os.environ['AWS_BUCKET'])

def json_dirent(dirent):
    if(dirent[3] == 0):
        return {
            'id': dirent[0],
            'name': dirent[1],
            'parent': dirent[2],
            'isDir': dirent[3],
            'created_at': dirent[4],
            'path': dirent[5],
            'src': dirent[6],
            'priority': dirent[7],
            'width': dirent[8],
            'height': dirent[9],
        }
    else:
        return {
            'id': dirent[0],
            'name': dirent[1],
            'parent': dirent[2],
            'isDir': dirent[3],
            'created_at': dirent[4],
            'path': dirent[5],
            'src': dirent[6],
            'priority': dirent[7],
            'photos': [],
            'dirs': [],
        }
# Determine if a file extension is allowed
def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# Update the priority of dirents in the database
def set_priority(priority_array):
    # Given a list of photo ids, set the priority of each photo to its index in the list
    cursor = mysql.connection.cursor()
    for index in range(len(priority_array)):
        cursor.execute("UPDATE Dirents SET priority = %s WHERE id = %s", (index, priority_array[index]))
    mysql.connection.commit()
    cursor.close()
#Get photos for a directory
def getPhotos(parent_id=None):
    cursor = mysql.connection.cursor()
    query = "SELECT * FROM Dirents WHERE parent = "+str(parent_id)+" AND isDir = 0 ORDER BY priority ASC" if parent_id else "SELECT * FROM Dirents WHERE parent IS NULL AND isDir = 0 ORDER BY priority ASC"
    photos = []
    cursor.execute(query)
    for dirent in cursor.fetchall(): photos.append(json_dirent(dirent))
    cursor.close()
    return photos
def getAllDirs():
    cursor = mysql.connection.cursor()
    query = "SELECT * FROM Dirents WHERE isDir = 1 ORDER BY priority ASC"
    dirs = [json_dirent((-1, 'root', None, 1, None, '/', 'https://uploads.jaydnserrano.com/', None, None, None))]
    cursor.execute(query)
    for dirent in cursor.fetchall(): dirs.append(json_dirent(dirent))
    cursor.close()
    return dirs
def getDirs(parent_id=None):
    cursor = mysql.connection.cursor()
    query = "SELECT * FROM Dirents WHERE parent = "+str(parent_id)+" AND isDir = 1 ORDER BY priority ASC" if parent_id else "SELECT * FROM Dirents WHERE parent IS NULL AND isDir = 1 ORDER BY priority ASC"
    dirs = []
    cursor.execute(query)
    for dirent in cursor.fetchall(): dirs.append(json_dirent(dirent))
    cursor.close()
    return dirs
# Build the directory tree from the database
def buildTree(parent_id=None):
    cursor = mysql.connection.cursor()
    # Make a json_dirent for this directory to be returned, if parent_id is None, this is the root directory
    root = None
    if(parent_id == None):
        root = json_dirent((-1, 'root', None, 1, None, '/', 'https://uploads.jaydnserrano.com/', None, None, None))
    else:
        cursor.execute("SELECT * FROM Dirents WHERE id = %s", (parent_id,))
        root = json_dirent(cursor.fetchone())
    # Get all the directories in this directory
    if(parent_id == None): cursor.execute("SELECT * FROM Dirents WHERE parent IS NULL AND isDir = 1 ORDER BY priority ASC")
    else: cursor.execute("SELECT * FROM Dirents WHERE parent = %s AND isDir = 1 ORDER BY priority ASC", (parent_id,))
    for dirent in cursor.fetchall():
        # Add the directory to the root directory
        root['dirs'].append(buildTree(dirent[0]))
    # Get all the photos in this directory
    if(parent_id == None): cursor.execute("SELECT * FROM Dirents WHERE parent IS NULL AND isDir = 0 ORDER BY priority ASC")
    else: cursor.execute("SELECT * FROM Dirents WHERE parent = %s AND isDir = 0 ORDER BY priority ASC", (parent_id,))
    for dirent in cursor.fetchall():
        # Add the photo to the root directory
        root['photos'].append(json_dirent(dirent))
    return root
def buildTreeOneLevel(parent_id=None):
    cursor = mysql.connection.cursor()
    # Make a json_dirent for this directory to be returned, if parent_id is None, this is the root directory
    root = None
    if(parent_id == None):
        root = json_dirent((-1, 'root', None, 1, None, '/', 'https://uploads.jaydnserrano.com/', None, None, None))
    else:
        cursor.execute("SELECT * FROM Dirents WHERE id = %s", (parent_id,))
        if(cursor.rowcount == 0): return []
        root = json_dirent(cursor.fetchone())
    # Get all the directories in this directory, but only add their names, ids, and photos to the dirs array
    if(parent_id == None): cursor.execute("SELECT * FROM Dirents WHERE parent IS NULL AND isDir = 1 ORDER BY priority ASC")
    else: cursor.execute("SELECT * FROM Dirents WHERE parent = %s AND isDir = 1 ORDER BY priority ASC", (parent_id,))
    for dirent in cursor.fetchall():
        # Add the name to the root directory
        tempdir = json_dirent(dirent)
        tempdir['photos'] = getPhotos(dirent[0])
        tempdir['dirs'] = getDirs(dirent[0])
        root['dirs'].append(tempdir)
    # Get all the photos in this directory
    root['photos'] = getPhotos(parent_id)
    return root
# Update the database to reflect the S3 bucket
def verifyDB():
    objs = bucket.objects.all()
    for obj in objs:
        parent, name = os.path.split(obj.key)
        # If the parent has not been added to database yet, add it
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id FROM Dirents WHERE name = %s", (parent, ))
        if(cursor.rowcount == 0):
            cursor.execute("INSERT IGNORE INTO Dirents (name, isDir, src, path) VALUES (%s, 1, %s, %s)", (parent, 'https://uploads.jaydnserrano.com/' + parent, '/' + parent))
            mysql.connection.commit()
            cursor.execute("SELECT id FROM Dirents WHERE name = %s", (parent, ))
        else:
            # Update the path and src of the parent
            path = '/' + parent
            src = 'https://uploads.jaydnserrano.com/' + parent
            cursor.execute("UPDATE Dirents SET path = %s, src = %s WHERE name = %s", (path, src, parent))
            mysql.connection.commit()
            cursor.execute("SELECT id FROM Dirents WHERE name = %s", (parent, ))
            
        parent_id = cursor.fetchone()[0]
        if(name != ''):
            cursor.execute("SELECT id FROM Dirents WHERE name = %s AND parent = %s", (name, parent_id))
            if(cursor.rowcount == 0):
                cursor.execute("INSERT INTO Dirents (name, isDir, src, parent) VALUES (%s, 0, %s, %s)", (name, 'https://uploads.jaydnserrano.com/' + obj.key, parent_id))
            else:
                path = '/' + parent + '/' + name
                src = 'https://uploads.jaydnserrano.com/' + parent + '/' + name
                cursor.execute("UPDATE Dirents SET path = %s, src = %s WHERE name = %s AND parent = %s", (path, src, name, parent_id))
        mysql.connection.commit()
        cursor.close()
class Greeting(Resource):
    def get(self):
        return make_response(render_template('index.html'))
api.add_resource(Greeting, '/')
class Login(Resource):
    def post(self):
        if(request.form['username'] == os.environ['JS_LOGIN'] and request.form['password'] == os.environ['JS_PASSWORD']):
            return make_response({'success': True}, 200)
        return make_response({'success': False}, 401)
api.add_resource(Login, '/login')
class Dirents(Resource):
    def post(self, id=None):
        if(request.form['action'] == 'add'):
            if(id != None):
                return make_response({'success': False, 'name': request.form['name'], 'id': id}, 200)
            isDir = request.form['isDir']
            name = request.form['name'] if 'name' in request.form else None
            parent = request.form['parent'] if 'parent' in request.form and request.form['parent'] != '-1' else None
            cursor = mysql.connection.cursor()
            # If the new dirent is a directory
            if(isDir == '1'):
                if(name == None):
                    return make_response({'success': False, 'error': 'No name given for new directory.'}, 400)
                cursor.execute("Select id FROM Dirents WHERE name = %s AND parent = %s", (name, parent))
                if(cursor.rowcount != 0):
                    return make_response({'success': False, 'error': 'Directory already exists.'}, 400)
                parent_path = ''
                if(parent != None):
                    cursor.execute("SELECT path FROM Dirents WHERE id = %s", (parent,))
                    parent_path = cursor.fetchone()[0]
                path = parent_path + '/' + name
                src = 'https://uploads.jaydnserrano.com' + path
                created_at = datetime.datetime.now()
                cursor.execute("INSERT INTO Dirents (name, isDir, src, parent, path, created_at) VALUES (%s, %s, %s, %s, %s, %s)", (name, isDir, src, parent, path, created_at))
                mysql.connection.commit()
                cursor.close()
                bucket.put_object(Key=name + '/', Body='', ACL='public-read')
                return make_response({'success': True, 'data': {'id': cursor.lastrowid, 'name': name, 'isDir': isDir, 'parent': parent, 'path': path, 'src': src}}, 200)
            # If the new dirent is a photo
            elif(isDir == '0'):
                # Form data contains name, parent, isDir, and file, with respective labels
                file = request.files['file'] if 'file' in request.files else None
                # If the parent is not given
                if(parent == None):
                    return make_response({'success': False, 'error': 'No parent given.'}, 400)
                # If the file is not given
                if(file == None):
                    return make_response({'success': False, 'error': 'No file given.'}, 400)
                # If the file is not an image
                if(file.content_type not in ['image/jpeg', 'image/png', 'image/gif']):
                    return make_response({'success': False, 'error': 'File is not an image.'}, 400)
                # Valid file
                name = file.filename
                # If the file already exists
                cursor.execute("SELECT id FROM Dirents WHERE name = %s", (name,))
                if(cursor.rowcount != 0):
                    return make_response({'success': False, 'error': 'File already exists.'}, 400)
                # Get the parent path
                cursor.execute("SELECT path FROM Dirents WHERE id = %s", (parent,))
                if(cursor.rowcount == 0):
                    return make_response({'success': False, 'error': 'Parent does not exist.'}, 400)
                parent_path = cursor.fetchone()[0]
                path = parent_path + '/' + name
                src = 'https://uploads.jaydnserrano.com' + path
                img = Image.open(file)
                width, height = img.size
                created_at = datetime.datetime.now()
                #Save the image with proper read permissions and proper content type to its proper directory in S3
                bucket.put_object(Key=path[1:], Body=file, ACL='public-read', ContentType=file.content_type)
                # Add the file to the database
                cursor.execute("INSERT INTO Dirents (name, isDir, src, parent, path, width, height, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (name, isDir, src, parent, path, width, height, created_at))
                # Commit the changes to the database
                mysql.connection.commit()
                # Verify that the file was added to the database
                cursor.execute("SELECT id FROM Dirents WHERE name = %s", (name,))
                if(cursor.rowcount == 0):
                    return make_response({'success': False, 'error': 'File was not added to the database.'}, 400)
                return make_response({'success': True, 'data': {'id': cursor.lastrowid, 'name': name, 'isDir': isDir, 'parent': parent, 'path': path, 'src': src, 'width': width, 'height': height}}, 200)
                
            # If the new dirent is neither a directory or a photo
            else:
                return make_response({'success': False, 'error': 'isDir must be 0 or 1.'}, 400)
        elif(request.form['action'] == 'edit'):
            # If ID was not passed
            if(id == None):
                return make_response({'success': False, 'error': 'Cannot edit NULL directory'}, 400)
            
            # Variable inits
            name = request.form['name']
            parent_id = request.form['parent'] if int(request.form['parent']) != -1 else None
            cursor = mysql.connection.cursor()
            
            # Check if the dirent already exists 
            cursor.execute("SELECT id FROM Dirents WHERE name = %s AND parent = %s", (name, parent_id))
            if(cursor.rowcount != 0):
                return make_response({'success': False, 'error': 'Directory already exists'}, 409)
                        
            # Move the object in S3 if it is an image
            cursor.execute("SELECT name,path,isDir,parent FROM Dirents WHERE id = %s", (id,))
            currname,path, isDir,currparent = cursor.fetchone()
            if(currname == name):
                if(currparent == parent_id):
                    return make_response({'success': False, 'error': 'No changes made'}, 400)
                else:
                    cursor.execute("UPDATE Dirents SET parent = %s WHERE id = %s", (parent_id, id))
                    mysql.connection.commit()
                    cursor.close()
                    return make_response({'success': True, 'response': 'Parent changed from ' + str(currparent) + ' to ' + str(parent_id)}, 200)
            parent_path = ''
            if(parent_id != None):
                cursor.execute("SELECT path FROM Dirents WHERE id = %s", (parent_id,))
                parent_path = cursor.fetchone()[0]
            temp = []
            if(isDir == 0):
                temp.append({
                    'bucket': bucket.name,
                    'old_key': path[1:],
                    'new_key': (parent_path[1:] + '/' if len(parent_path) > 0 else '') + name
                })
                bucket.Object((parent_path[1:] + '/' if len(parent_path) > 0 else '') + name).copy_from(CopySource={'Bucket': bucket.name, 'Key': path[1:]}, ACL='public-read')
                bucket.Object(path[1:]).delete()
                # Update the path and src of the dirent
                cursor.execute("UPDATE Dirents SET name = %s,parent = %s, path = %s, src = %s WHERE id = %s", (name, parent_id, parent_path + '/' + name, 'https://uploads.jaydnserrano.com' + parent_path + '/' + name, id))
                mysql.connection.commit()
            else:
                # Create empty folder in S3 titled name
                bucket.put_object(Key= name + '/', ACL='public-read')
                # Move all the objects in the directory if the
                cursor.execute("SELECT path FROM Dirents WHERE parent = %s", (id,))
                for dirent in cursor.fetchall():
                    temp.append({
                        'bucket': bucket.name,
                        'old_key': dirent[0][1:],
                        'new_key': name + '/' + dirent[0].split('/')[-1],
                    })
                    bucket.Object( name + '/' + dirent[0].split('/')[-1]).copy_from(CopySource={'Bucket': bucket.name, 'Key': dirent[0][1:]}, ACL='public-read')
                    bucket.Object(dirent[0][1:]).delete()
                # Delete the old folder
                bucket.Object(path[1:] + '/').delete()
                # Update the database
                cursor.execute("UPDATE Dirents SET name = %s ,parent = %s, path = %s, src = %s WHERE id = %s", (name,parent_id, parent_path + '/' + name, 'https://uploads.jaydnserrano.com' + parent_path + '/' + name, id))
                mysql.connection.commit()
            
            #Update the child photos to reflect the new src and path of the parent
            cursor.execute("SELECT * FROM Dirents WHERE parent = %s AND isDir = 0", (id,))
            for dirent in cursor.fetchall():
                cursor.execute("UPDATE Dirents SET path = %s, src = %s WHERE id = %s", ((parent_path[1:] + '/' if len(parent_path) > 0 else '') + name + '/' + dirent[1], 'https://uploads.jaydnserrano.com/' + (parent_path[1:] + '/' if len(parent_path) > 0 else '') + name + '/' + dirent[1], dirent[0]))
                mysql.connection.commit()
            cursor.close()
            return make_response({'success': True, 'attemptedList': temp}, 200)

    def get(self, id=None):
        verifyDB()
        if(id == None):
            return make_response(buildTree(), 200)
        elif(id == 'dirs'):
            return make_response(getAllDirs(), 200)
        elif(id == 'root'):
            return make_response(buildTreeOneLevel(), 200)
        else:
            return make_response(buildTreeOneLevel(id), 200)
    
    def delete(self, id=None):
        # If ID was not passed
        if(id == None):
            return make_response({'success': False, 'error': 'Cannot delete root'}, 400)
        # Mysql retrieval 
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT isDir FROM Dirents WHERE id = %s", (id,))
        # If the dirent does not exist
        if(cursor.rowcount == 0):
            return make_response({'success': False, 'error': 'Dirent does not exist'}, 404)
        isDir = cursor.fetchone()[0]
        # If the dirent is a directory
        if(isDir == 1):
            
            # Return failure if there are children 
            cursor.execute("SELECT id FROM Dirents WHERE parent = %s", (id,))
            if(cursor.rowcount != 0):
                return make_response({'success': False, 'error': 'Directory is not empty'}, 409)
            
            # Delete the directory in S3
            cursor.execute("SELECT path FROM Dirents WHERE id = %s", (id,))
            path = cursor.fetchone()[0]
            bucket.Object(path[1:] + '/').delete()
            
            # Delete the directory in the database
            cursor.execute("DELETE FROM Dirents WHERE id = %s", (id,))
            mysql.connection.commit()
            cursor.close()
            
            # Return success
            return make_response({'success': True, 'response': 'Deleted directory ' + path}, 200)
        
        #Else if the dirent is a photo
        elif(isDir == 0):
            
            # Delete the photo in S3
            cursor.execute("SELECT path FROM Dirents WHERE id = %s", (id,))
            path = cursor.fetchone()[0]
            bucket.Object(path[1:]).delete()
            
            # Delete the photo in the database
            cursor.execute("DELETE FROM Dirents WHERE id = %s", (id,))
            mysql.connection.commit()
            cursor.close()
            
            # Return success
            return make_response({'success': True, 'response': 'Deleted photo ' + path}, 200)
        
        # Else if the dirent is neither
        else:
            return make_response({'success': False, 'error': 'isDir set incorrectly.'}, 400)
        
api.add_resource(Dirents, '/dirents', '/dirents/<id>')

if __name__ == '__main__':
    application.run(debug=True , threaded=True)