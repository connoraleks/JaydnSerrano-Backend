from flask import Flask, render_template, make_response, request, redirect, url_for, session
from flask_restful import Resource, Api
from flask_cors import CORS
from boto3.dynamodb.conditions import Key, Attr
import boto3
from PIL import Image
import os
from pathlib import Path
import datetime
# Initialize the application
application = Flask(__name__)

# Set up cors support for all routes
CORS(application, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Set up API
api = Api(application)

UPLOAD_FOLDER = '/tmp/photos/'
session = boto3.Session(
    region_name='us-east-1',
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY']
)
dynamodb = session.resource('dynamodb')
table = dynamodb.Table('jaydnserrano-photos')
s3 = session.resource('s3')
class Database(Resource):
    def make_photo (self, photo, root):
        parent_name = 'root'
        relative_path = '/' + root.replace(UPLOAD_FOLDER, '') if root != UPLOAD_FOLDER else ''
        format_date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Root folders should have parent set to 0
        if(root != UPLOAD_FOLDER):
            # Get the parent id from the database by querying the parent folder name
            parent_name = root.split('/')[-1]
        img = Image.open(root + '/' + photo)
        (width, height) = img.size
        return {
            'name': photo,
            'parent': parent_name,
            'type': 'photo',
            'date': format_date_time,
            'width': width,
            'height': height,
            'url': "https://jaydnserrano.s3.amazonaws.com/photos" + relative_path + '/' + photo,
            'path': relative_path + '/' + photo,
            'priority': 0
        }
    def make_directory(self, dir, root):
        parent_name = 'root'
        relative_path = '/' + root.replace(UPLOAD_FOLDER, '') if root != UPLOAD_FOLDER else ''
        format_date_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Root folders should have parent set to 0
        if(root != UPLOAD_FOLDER):
            parent_name = root.split('/')[-1]
        return {
                'name': dir,
                'parent': parent_name,
                'type': 'folder',
                'date': format_date_time,
                'width': None,
                'height': None,
                'url': None,
                'path': relative_path + '/' + dir,
                'priority': 0
            }
    def retrieve_bucket_data(self):
        bucket = s3.Bucket('jaydnserrano')
        objs = list(bucket.objects.filter(Prefix='photos/'))
        for obj in objs:
            # remove the file name from the object key
            obj_path = "/tmp/" + os.path.dirname(obj.key)
            # create nested directory structure if it doesn't exist
            if(not os.path.exists(obj_path)): Path(obj_path).mkdir(parents=True, exist_ok=True)
            # save file with full path locally if not already saved
            if(not os.path.exists("/tmp/" + obj.key)): bucket.download_file(obj.key, "/tmp/"+obj.key)
        stack = {'photos': [], 'folders': []}
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for file in files:
                stack['photos'].append(self.make_photo(file, root))
            for dir in dirs:
                stack['folders'].append(self.make_directory(dir, root))
        return stack
    def populate_db(self, stack):
        for item in stack['folders']:
            table.put_item(Item=item)
        for item in stack['photos']:
            table.put_item(Item=item)
    def get(self):
        stack = self.retrieve_bucket_data()
        self.populate_db(stack)
        response = make_response(stack, 200)
        return response
api.add_resource(Database, '/database')

class Dirent(Resource):
    # Helper function to make a folder object
    def make_folder(self, folder):
        return {
            'name': folder['name'],
            'path': folder['path'],
            'date': folder['date'],
            'photos': self.get_photos_by_folder(folder['name']),
            'folders': self.get_folders_by_folder(folder['name'])
            
        }
    # Helper function to make a photo object
    def make_photo(self, photo):
        return {
            'name': photo['name'],
            'path': photo['path'],
            'date': photo['date'],
            'width': photo['width'],
            'height': photo['height'],
            'src': photo['url']
        }
    # Helper function to get photos in a particular folder
    def get_photos_by_folder(self, folder_name):
        response = table.scan(
            FilterExpression=Attr('parent').eq(folder_name) & Attr('type').eq('photo')
        )
        items = response['Items']
        return [self.make_photo(item) for item in items] if len(items) > 0 else []
    # Helper function to get folders in a particular folder
    def get_folders_by_folder(self, folder_name):
        response = table.scan(
            FilterExpression=Attr('parent').eq(folder_name) & Attr('type').eq('folder')
        )
        items = response['Items']
        return [self.make_folder(item) for item in items] if len(items) > 0 else []
    def get_root(self):
        return self.make_folder({'name': 'root', 'path': '/', 'date': '2020-01-01 00:00:00'})
    
    # Get all dirents or a specific dirent
    def get(self, folder=None):
        if not folder:
            return make_response({
                'folders': self.get_root(),
                'photos': []
                }, 200)
        return make_response({
            'folders': self.get_folders_by_folder(folder),
            'photos': self.get_photos_by_folder(folder)
            }, 200)
api.add_resource(Dirent, '/dirents', '/dirents/<string:folder>')
class Landing(Resource):
    def get(self):
        return make_response(render_template('index.html', root=Dirent().get_root()))
api.add_resource(Landing, '/')

class Login(Resource):
    def post(self):
        username = request.form['username']
        password = request.form['password']
        print(username, password)
        print(os.environ['JS_LOGIN'], os.environ['JS_PASSWORD'])
        # compare with environment variables JS_LOGIN and JS_PASSWORD
        if(username == os.environ['JS_LOGIN'] and password == os.environ['JS_PASSWORD']):
            return make_response({'success': True}, 200)
        else:
            return make_response({'success': False}, 401)
api.add_resource(Login, '/login')
if __name__ == '__main__':
    application.run(debug=True , threaded=True, port=8000)