import jwt
from flask import request, jsonify
from functools import wraps
from config import JWT_SECRET_KEY,MONGO_URI,WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID
from bson.objectid import ObjectId
from pymongo import MongoClient
import gridfs
import random
import requests
client = MongoClient(MONGO_URI)
db = client["care2connect"] # If URI has a DB, it picks it
fs = gridfs.GridFS(db) 


users_collection = db['users']
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if request.method == "OPTIONS":
            return '', 200  # Let preflight pass without token check
        token = None

        # Get token from header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            decoded = jwt.decode(token, JWT_SECRET_KEY, algorithms=["HS256"])
            user_id = decoded.get('user_id')
            current_user = users_collection.find_one({"_id": ObjectId(user_id)})

            if not current_user:
                return jsonify({'error': 'User not found'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        # Inject current_user into the route
        return f(current_user, *args, **kwargs)

    return decorated

def generate_otp(length=6):
    """Generate a random numeric OTP"""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])


def send_otp_via_whatsapp(phone, otp_code):
    """
    Sends OTP to the given phone number using WhatsApp Cloud API.
    Assumes you have a message template with 1 variable (for OTP).
    """

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = { 
        "messaging_product": "whatsapp", 
        "to": phone,
        "type": "template", 
        "template": { 
            "name": "otp_care2connect", 
            "language": { 
                "code": "en" 
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        { "type": "text", "text": otp_code }
                    ]
                },
                {
                "type": "button",
                "index": "0",
                "sub_type": "url",
                "parameters": [
                    {
                        "type": "text",
                        "text": otp_code
                    }
                ]}
            ]} 
        }

    response = requests.post(url, headers=headers, json=payload)
    print(response.status_code)
    return response.status_code == 200

