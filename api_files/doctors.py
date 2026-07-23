from flask import Blueprint, request, jsonify
from bson.objectid import ObjectId
from datetime import datetime
from bson import ObjectId
from api_files.utils import token_required
from api_files.utils import db


doctor_bp = Blueprint('doctor_bp', __name__)

@doctor_bp.route('/doctors', methods=['POST'])
def add_doctor():
    data = request.get_json()
    try:
        doctor_id = create_doctor(data)
        return jsonify({"message": "Doctor created", "doctor_id": doctor_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@doctor_bp.route('/doctors/<doctor_id>', methods=['GET'])
def fetch_doctor(doctor_id):
    doctor = get_doctor_by_id(doctor_id,"user")
    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404
    return jsonify(doctor), 200

@doctor_bp.route('/admin/doctors/<doctor_id>', methods=['GET'])
def fetch_doctor_admin(doctor_id):
    doctor = get_doctor_by_id(doctor_id,"admin")
    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404
    return jsonify(doctor), 200


@doctor_bp.route("/doctors/<doctor_id>", methods=["POST"])
def update(doctor_id):
    try:
        updated_data = request.get_json()
        success = update_doctor(doctor_id, updated_data)
        if success:
            return jsonify({"message": "Doctor updated successfully"}),200
        else:
            return jsonify({"error": "Doctor not found or no changes made"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@doctor_bp.route('/doctors', methods=['GET'])
def fetch_doctors():
    doctors = list_doctors()
    return jsonify(doctors), 200

@doctor_bp.route('/onboard', methods=['POST'])
def onboard_doctor():
    data = request.get_json()
    try:
        id = create_doctor_onboard(data)
        return jsonify({"message": "Doctor Onboarded", "id":id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@doctor_bp.route('/doctor/onboard/<onboard_id>', methods=['GET'])
def fetch_onboard_application(onboard_id):
    app = get_onboarding_by_id(onboard_id)
    if not app:
        return jsonify({"error": "Applcation not found"}), 404
    return jsonify(app), 200

@doctor_bp.route("/doctor/onboard/<onboard_id>", methods=["POST"])
def update_doctor_onboard( onboard_id):
    try:
        updated_data = request.get_json()
        success = update_doctor_application(onboard_id, updated_data)
        if success:
            return jsonify({"message": "Application updated successfully"}),200
        else:
            return jsonify({"error": "Application not found or no changes made"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
@doctor_bp.route('/onboard_list', methods=['GET'])
def onboard_doctor_list():
    applications = application_list()
    return jsonify(applications), 200

@doctor_bp.route('/find_doctor', methods=['GET'])
@token_required
def find_doctor(current_user):
    doctor = get_doctor_by_user_id(current_user['_id'])
    if not doctor:
        application = get_onboarding_by_user_id(current_user['_id'])
        if not application:
            return jsonify({"error": "Doctor not found"}), 404
        else:
            return jsonify({"status":application.get('status','pending')}), 200
    else:
        return jsonify(doctor['_id']), 200
    

doctors_collection = db["doctors"]
onboarding_collection = db["onboarding"]

def create_doctor(data):
    data = dict(data)  # Make a mutable copy
    # Ensure hospital_id is stored as ObjectId
    if "hospital_id" in data:
        data["hospital_id"] = ObjectId(data["hospital_id"])
    if "user_id" in data:
        data["user_id"] = ObjectId(data["user_id"])
    data.pop("_id", None)

    data["created_at"] = datetime.utcnow()
    result = doctors_collection.insert_one(data)
    return str(result.inserted_id)

def get_doctor_by_id(doctor_id,type="user"):
    try:
        doctor = doctors_collection.find_one({"_id": ObjectId(doctor_id)})
        if doctor:
            doctor["_id"] = str(doctor["_id"])
            if 'user_id' in doctor:
                doctor['user_id']=str(doctor["user_id"])
            # doctor["hospital_id"] = str(doctor["hospital_id"])
            # Remove sensitive/unwanted fields
            if type == "user":
                doctor.pop("whatsAppBusinessAccountID", None)
                doctor.pop("accessToken", None)
                doctor.pop("password", None)
                doctor.pop("confirmPassword", None)
        return doctor
    except:
        return None
def get_doctor_by_user_id(phone):
    try:
        doctor = doctors_collection.find_one({"phone": phone})
        if doctor:
            doctor["_id"] = str(doctor["_id"])
            # doctor["user_id"] = str(doctor["user_id"])
            # doctor["hospital_id"] = str(doctor["hospital_id"])
            # Remove sensitive/unwanted fields
            doctor.pop("whatsAppBusinessAccountID", None)
            doctor.pop("accessToken", None)
            doctor.pop("password", None)
            doctor.pop("confirmPassword", None)
        return doctor
    except:
        return None
    
def get_onboarding_by_id(onboard_id):
    try:
        app = onboarding_collection.find_one({"_id": ObjectId(onboard_id)})
        if app:
            app["_id"] = str(app["_id"])
            # app["user_id"] = str(app["user_id"])
        return app
    except:
        return None
def get_onboarding_by_user_id(phone):
    try:
        app = onboarding_collection.find_one({"phone": phone})
        if app:
            app["_id"] = str(app["_id"])
            # app["user_id"] = str(app["user_id"])
        return app
    except:
        return None
    
def update_doctor(doctor_id, updated_data):
    if "hospital_id" in updated_data:
        updated_data["hospital_id"] = ObjectId(updated_data["hospital_id"])
    if "user_id" in updated_data:
        updated_data["user_id"] = ObjectId(updated_data["user_id"])
    print(updated_data)
    updated_data.pop("_id", None)
    result = doctors_collection.update_one(
        {"_id": ObjectId(doctor_id)},
        {"$set": updated_data}
    )
    return result.modified_count > 0

def update_doctor_application(onboard_id, updated_data):
    print(updated_data)
    updated_data.pop("_id", None)
    result = onboarding_collection.update_one(
        {"_id": ObjectId(onboard_id)},
        {"$set": updated_data}
    )
    return result.modified_count > 0

def list_doctors():
    doctors = doctors_collection.find().sort("created_at", -1)
    doctor_list = []

    for doc in doctors:
        doc["_id"] = str(doc["_id"])
        if 'user_id' in doc:
            doc['user_id']=str(doc["user_id"])

        # Remove sensitive/unwanted fields
        doc.pop("whatsAppBusinessAccountID", None)
        doc.pop("accessToken", None)
        doc.pop("passsword", None)
        doc.pop("confirmPassword", None)

        doctor_list.append(doc)

    return doctor_list

def create_doctor_onboard(data):
    data = dict(data) 
    # data["user_id"] = ObjectId(current_user["_id"])
    data["created_at"] = datetime.utcnow()
    result = onboarding_collection.insert_one(data)
    return str(result.inserted_id)


def application_list():
    appications = onboarding_collection.find().sort("created_at", -1)
    app_list = []

    for doc in appications:
        doc["_id"] = str(doc["_id"])
        if 'user_id' in doc:
            doc["user_id"] = str(doc["user_id"])
        app_list.append(doc)
    return app_list



