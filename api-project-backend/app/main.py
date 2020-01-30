from flask import Flask, request, jsonify, make_response, redirect, session
import praw
from praw.models import MoreComments
from google.cloud import firestore, tasks_v2, bigquery

import hashlib
import secrets
import time
import json

from google.cloud import language
from google.cloud.language import enums
from google.cloud.language import types

db = firestore.Client()
clientBQ = bigquery.Client()


project = 'arc-pjatk'
queue = 'mail-queue'
location = 'europe-west3'
payload = 'hello'

table_ref = clientBQ.get_table("arc-pjatk.Project.statistics")

app = Flask(__name__)

app.secret_key = "super secret key"


reddit = praw.Reddit(user_agent='Comment Extraction (by /u/damol28)',
                     client_id='xxxxxxxxxxxxxxxxxxxxxx',
                    client_secret='xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                   )

# Instantiates a client
client = language.LanguageServiceClient()




activationKey = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

def sendEmail(email, activationKey):
    user_email = request.args.get('email')
    user_activationKey = request.args.get('activationKey')

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(
        "arc-pjatk", "europe-west3", "mail-queue")
    payload = json.dumps(
        {"email": email, "key": activationKey   }, ensure_ascii=False).encode()
    task = {
        "app_engine_http_request": {
            "http_method": "POST",
            "app_engine_routing": {
                "service": "tasks-worker"
            },
            "relative_uri": "/tasks/mail",
            "headers": {
                "Content-Type": "application/json"
            },
            "body": payload
        }
    }
    client.create_task(parent, task)
    
    return 'mail send', 200


@app.route("/project/v1/score/activate/<email>", methods=["GET"])
def activate(email):
    
    users = db.collection(u'UsersProject')

    for uR in users.stream():
        if(uR.to_dict()['email']==email):
            users.document(uR.id).update({
                'activated' : True
            })
  
    return 'Hi! {} Your account has been activated'.format(email), 200
    


@app.route('/project/v1/score/users', methods=['GET'])
def getUsers():

    users = db.collection('UsersProject')
    userId = request.args.get('user_id')

    docs = users.stream()
    allUsers = []
    links =  users.document(userId).get().to_dict()['links']

    for doc in docs:
        d = doc.to_dict()['links']
        allUsers.append({
            'links': doc.to_dict()['links'],
            'password': doc.to_dict()['password'],
            'email': doc.to_dict()['email'],
            'id': doc.id,
        })
   
    return jsonify(links), 200

@app.route('/project/v1/score/user/urls', methods=['GET'])
def getUserEveryUrl():

    userId = request.args.get('user_id')
    users = db.collection('UsersProject')
    users_urls = []

    links = users.document(userId).collection('links')

    for o in links.stream():
        print(o.to_dict()['url'])
        users_urls.append(o.to_dict()['url'])


    return jsonify(users_urls), 200


@app.route('/project/v1/score/user/url/numberOfComments', methods=['GET'])
def getUserCommentsNumber():
    users = db.collection('UsersProject')
    userId = request.args.get('user_id')
    links = users.document(userId).collection('links')

    numberOfComments=0

    for o in links.stream():
        numberOfComments+=len(o.to_dict()['comments'])
        
    return jsonify(numberOfComments)

@app.route('/project/v1/score/user/url/numberOfUrls', methods=['GET'])
def getUserUrlsNumbe():
    users = db.collection('UsersProject')
    userId = request.args.get('user_id')
    links = users.document(userId).collection('links')

    numberOfUrls=0
    for o in links.stream():
            numberOfUrls+=1
        
    return jsonify(numberOfUrls)
       

@app.route('/project/v1/score/user/url/numberOfCommentsOfUrl', methods=['GET'])
def getNumberOfCommentsOfUrl():
    users = db.collection('UsersProject')
    userId = request.args.get('user_id')
    url = request.args.get('url')
    links = users.document(userId).collection('links')

    numberOfComments=0

    for o in links.stream():
        if url == o.to_dict()['url']:
            print(o.to_dict()['url'])
            numberOfComments=len(o.to_dict()['comments'])
    return jsonify(numberOfComments)


@app.route('/project/v1/score/user/url/comments', methods=['GET'])
def getUserLinksComments():

 

    users = db.collection('UsersProject')
    
    userId = request.args.get('user_id')
    userUrl = request.args.get('url')   
    
    
    links = users.document(userId).collection('links')


    for o in links.stream():
        if o.to_dict()['url'] == userUrl:
            return jsonify(o.to_dict()['comments'])

    return 'Wrong user id, or url, check every character at the end of url', 400


@app.route('/project/v1/score/users/deleteLink', methods=['POST'])
def deleteLink():
    users = db.collection('UsersProject')
    redditUrl = request.args.get('url')
    user_id = request.args.get('user_id')

    user_Links = users.document(user_id).collection('links').stream()
    
    for uL in user_Links:
            
            if  uL.to_dict()['url'] == redditUrl:
                
                users.document(user_id).collection('links').document(uL.id).delete()
                return "Url deleted from Your Account", 200


    return "Ups, something went wrong with deleting", 400            


@app.route('/project/v1/score/users/addLink', methods=['POST'])
def sentence():

    
    users = db.collection('UsersProject')

    redditUrl = request.args.get('url')
   
    user_id = request.args.get('user_id')

    submission = reddit.submission(url=redditUrl)
    allComments = []
    comments = submission.comments

    user_Links = users.document(user_id).collection('links').stream()

   
    for uL in user_Links:
            if  uL.to_dict()['url'] == redditUrl:
                users.document(user_id).collection('links').document(uL.id).delete()
                

    for comment in comments:
        if isinstance(comment, MoreComments):
            continue
        document = types.Document(
        content=comment.body,
        type=enums.Document.Type.PLAIN_TEXT)
        sentiment = client.analyze_sentiment(document=document).document_sentiment
        
        allComments.append({
            'comment': comment.body,
            'score': sentiment.score,
            'id': comment.id,
        })

 

    users.document(user_id).collection('links').add({
        'comments': allComments,
        'url': redditUrl
    })


    return 'success'
    

    

@app.route('/project/v1/score/login', methods=['POST'])
def login():
    activationKey = "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"

    data = request.json

    users = db.collection('UsersProject')

    loggedUsers = db.collection('loggedUsersProject')

    data = request.json


    user_email = data['email']
    user_password = data['password']
    
    if(user_email == '' or user_password == ''):
        return {
            'Alert': 'email or password cannot be empty',
        }, 400

    password = hashlib.sha256(user_password.encode("UTF-8"))
    
    query_ref = db.collection(u'UsersProject').where("email", "==", user_email)
    login_query_ref = db.collection(
        u'loggedUsersProject').where("email", "==", user_email)

    docs2 = query_ref.stream()
    docs3 = login_query_ref.stream()

    for doc3 in docs3:
        if user_email == doc3.to_dict()['email']:
            print(doc3.to_dict()['email'])
            return 'You have already logged in', 403

    if session.get('token'):
        print('juz jestes')
        print(session.get('token'))

    for doc2 in docs2:
        if doc2.to_dict()['activated']==False:
            return 'You need to activate your account first', 401

        if user_email == doc2.to_dict()['email'] and doc2.to_dict()['password'] == password.hexdigest():

            body = {
                'id': doc2.id,
                'email': doc2.to_dict()['email']
            }
            authToken = secrets.token_urlsafe(20)
            session['token'] = authToken
            loggedUsers.add({
                'token': authToken,
                'email': doc2.to_dict()['email']
            })
            data = {'authToken':authToken,
            'user_id':doc2.id}

            return jsonify(data), 200
    return 'Wrong email or password', 400


@app.route('/project/v1/score/register', methods=['POST'])
def register():
    activationKey = "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"

    data = request.json
    users = db.collection('UsersProject')
    loggedUsers = db.collection('loggedUsersProject')    

    docs = users.stream()
    data = request.json

    user_email = data['email']
    user_password = data['password']
    password = hashlib.sha256(user_password.encode("UTF-8"))

    query_ref = db.collection(u'UsersProject').where("email", "==", user_email)
    
    timestamp = time.time()

    docs2 = query_ref.stream()
    communicat = 'Email in firebase'

    if (user_email == '' or user_password == ''):
        return {
            'Alert': 'Email or password cannot be empty',
        }, 400

    for doc2 in docs2:
        if user_email == doc2.to_dict()['email']:
            return 'Email in firebase', 401

    data = {
        'email': user_email,
        'password': password.hexdigest(),
        'activated' : False,
        'registrationTimeStamp' : timestamp,
        "activationKey": secrets.token_urlsafe(),

    }
    
    users.add(data)

    sendEmail(user_email, activationKey)
    return 'Success', 200



@app.route('/project/v1/score/logout', methods=['POST'])
def logout():
    
    if 'token' in session:
        print(session.get('token'))
        loggedRef = db.collection(u'loggedUsersProject')
        
        docs = loggedRef.stream()

        for doc in docs:
            if doc.to_dict()['token']==session['token']:
                print('id: ',doc.id, 'token: ', doc.to_dict()['token'] )
                loggedRef.document(doc.id).delete()
                session.pop('token', None)
                return 'Logged out', 200
        
    else:
        return 'You are NOT logged in', 400


@app.route("/project/v1/score/statistics", methods=["POST"])
def addEvent():    
    data = request.json

    user_id = data["user_id"]
    number_of_comments_added = data["number_of_comments_added"]

    data = {
        "time_stamp": time.time(),
        "user_id": user_id,
        "number_of_comments_added": number_of_comments_added
        }


    errors = clientBQ.insert_rows_json(table_ref, [data])
    
    return 'Success', 200





if __name__ == "__main__":
     app.run(host='127.0.0.1', port=8080, debug=True)
