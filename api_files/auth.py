
from flask import Blueprint, request, jsonify, send_file
from api_files.utils import token_required, generate_otp, send_otp_via_whatsapp,db,fs
from config import JWT_SECRET_KEY, OTP_LENGTH,OTP_EXPIRY_SECONDS
from bson.objectid import ObjectId
from io import BytesIO
import jwt
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

otp_collection = db['otp_verifications']
users_collection = db['users']


def otp(phone):
    if not phone:
        return jsonify({"error": "Phone number required"}), 400

    otp = generate_otp(OTP_LENGTH)
    print(otp)
    sent = send_otp_via_whatsapp(phone, otp)

    if sent:
        store_otp(phone, otp)
        return jsonify({'success':True,"msg": f"OTP sent to {phone}"}), 200
    else:
        return jsonify({"error": "Failed to send OTP"}), 500

# 1. Register - Send OTP
@auth_bp.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    phone = data.get("phone")
    return otp(phone)

@auth_bp.route('/register-otp', methods=['POST'])
def register_otp():
    data = request.get_json()
    phone = data.get("phone")
    if find_user_by_phone(phone):
        return jsonify({"error": "User already exists"}), 400
    return otp(phone)
    


# 2. Verify OTP and Create/Return JWT
# Updated /verify-otp route
@auth_bp.route('/verify-otp', methods=['POST'])
def verify():
    data = request.get_json()
    phone = data.get("phone")
    otp = data.get("otp")

    if not phone or not otp:
        return jsonify({"error": "Phone and OTP required"}), 400

    if verify_otp(phone, otp):
        delete_otp(phone)
        user = find_user_by_phone(phone)
        if not user:
            # User doesn't exist yet — create minimal entry and return user_id
            # res = create_user(phone)
            # user_id = str(res.inserted_id)
            return jsonify({
                "success": "OTP verified, please complete your profile",
                "details_required": True
            }), 200
        else:
            # User already exists — generate JWT directly
            token = jwt.encode({
                "user_id": str(user["_id"]),
                "phone": phone,
                "exp": datetime.utcnow() + timedelta(days=1)
            }, JWT_SECRET_KEY, algorithm="HS256")

            return jsonify({"success":True,"token": token}), 200
    else:
        return jsonify({"error": "Invalid or expired OTP"}), 400



# 3. Login -
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    password = data.get("password")
    email = data.get("email")
    user = verify_password(email,password)
    print(user)
    if user: 
        otp_response, status = otp(user.get('phone'))
        if status==200:
            return jsonify({
                'success':True,
                "msg": "OTP Sent",
                "user":user.get("phone")
            }), 200
        else:
            return otp_response
    else:
        return jsonify({"error": "Invalid credentials"}), 401
    
# 3. User Login -
@auth_bp.route('/user-login', methods=['POST'])
def User_login():
    data = request.get_json()
    password = data.get("password")
    phone = data.get("phone")
    user = verify_user_password(phone,password)
    print(user)
    if user: 
        token = jwt.encode({
                "user_id": str(user["_id"]),
                "phone": phone,
                "exp": datetime.utcnow() + timedelta(days=1)
            }, JWT_SECRET_KEY, algorithm="HS256")

        return jsonify({"success":True,"token": token}), 200
    else:
        return jsonify({"error": "Invalid credentials"}), 401
    


# 4. Protected route
@auth_bp.route('/profile', methods=['GET'])
@token_required
def profile(current_user):
    user_data = current_user.copy()
    user_data["_id"] = str(user_data["_id"])
    return jsonify(user_data), 200




@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    phone = data.get("phone")
    name = data.get("name")

    if not all([phone, name]):
        return jsonify({"error": "All fields are required"}), 400

    
    res = create_user(phone, name,data)
    user_id = str(res.inserted_id)
    if user_id:
        token = jwt.encode({
            "user_id": user_id,
            "phone": phone,
            "exp": datetime.utcnow() + timedelta(days=1)
        }, JWT_SECRET_KEY, algorithm="HS256")
        return jsonify({'success':True,"token": token,"msg": "Profile Created Successfully"}), 200
    else:
        return jsonify({"error": "Profile Createion failed"}), 400

@auth_bp.route('/update_profile', methods=['POST',"OPTIONS"])
@token_required
def update_user(current_user):
    try:
        data = request.get_json()
        user_id= str(current_user["_id"])
        res = complete_user_profile(user_id,data)
        print(res)
        if res:
            return jsonify({"message": "Profile updated successfully"})
        else:
            return jsonify({"error": "Profile not found or no changes made"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    

# ✅ Upload Image to GridFS
@auth_bp.route("/upload", methods=["POST"])
def upload_image():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    file_id = fs.put(file, filename=file.filename, content_type=file.content_type)
    return jsonify({"message": "File uploaded", "file_id": str(file_id)}), 200

# ✅ Download Image by ID
@auth_bp.route("/image/<file_id>", methods=["GET"])
def get_image(file_id):
    try:
        file = fs.get(ObjectId(file_id))
        return send_file(BytesIO(file.read()), mimetype=file.content_type)
    except Exception as e:
        return jsonify({"error": str(e)}), 404
    


import razorpay
import hmac
import hashlib


RAZORPAY_KEY_ID = "rzp_live_R9tGl7bLSIBV6f"
RAZORPAY_KEY_SECRET = "dTvrApHzGc2VGCw8olP3xVOL"
# RAZORPAY_KEY_ID = "rzp_test_N6qQ6xBkec7ER4"
# RAZORPAY_KEY_SECRET = "fbKeii72zk6xbaUoJITOPqP8"

client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

@auth_bp.route('/create_order', methods=['POST'])
def create_order():
    data = request.get_json()
    amount = data.get('amount') * 100  # in paise
    payment = client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })
    return jsonify(payment)

@auth_bp.route('/verify', methods=['POST'])
def verify_payment():
    data = request.get_json()
    order_id = data.get('razorpay_order_id')
    payment_id = data.get('razorpay_payment_id')
    signature = data.get('razorpay_signature')

    generated_signature = hmac.new(
        bytes(RAZORPAY_KEY_SECRET, 'utf-8'),
        bytes(order_id + "|" + payment_id, 'utf-8'),
        hashlib.sha256
    ).hexdigest()

    if generated_signature == signature:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "failure"}), 400


def store_otp(phone, otp_code):
    otp_entry = {
        "phone": phone,
        "otp": otp_code,
        "expires_at": datetime.utcnow() + timedelta(seconds=OTP_EXPIRY_SECONDS),
        "created_at": datetime.utcnow()
    }
    otp_collection.insert_one(otp_entry)

def verify_otp(phone, otp_code):
    record = otp_collection.find_one({"phone": phone, "otp": otp_code})
    if record and record["expires_at"] > datetime.utcnow():
        return True
    return False

def delete_otp(phone):
    otp_collection.delete_many({"phone": phone})

def find_user_by_phone(phone):
    return users_collection.find_one({"phone": phone})

def verify_password(email,password):
    user=users_collection.find_one({"email": email})
    if user and user.get('password')==password:
        return user
    else:
        return None
    
def verify_user_password(phone,password):
    user=users_collection.find_one({"phone": phone})
    if user and user.get('password')==password:
        return user
    else:
        return None

def create_user(phone,name,data):
    user = {
        **data,
        "phone": phone,
        "name": name,
        "is_verified": True,
        "created_at": datetime.utcnow()
    }
    return users_collection.insert_one(user)

def complete_user_profile(user_id, data):
    print(data)
    result = users_collection.update_one({"_id": ObjectId(user_id)}, {"$set": data})
    print(result.modified_count)
    return result.modified_count > 0


def get_user_by_id(user_id):
    return users_collection.find_one({"_id": ObjectId(user_id)})




