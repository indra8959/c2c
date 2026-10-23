from pydoc import doc

from flask import Flask, app, request, jsonify, Blueprint,send_file,render_template
from pymongo.errors import DuplicateKeyError, PyMongoError
import requests
import random
from pymongo import MongoClient

from datetime import datetime, timedelta, timezone , date
from bson import ObjectId
from api_files.c2c_mobile_app.firebase_service import send_push_notification,send_bulk_notifications
from pymongo import ReturnDocument
import os
import time
from zoneinfo import ZoneInfo
import re


c2c_app = Blueprint("c2c_app", __name__)


# MongoDB connection
client = MongoClient("mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["caredb"]
# db = client["app_db"]
otp_collection = db["otp_store"]
users_collection = db["users"]
appointment = db["appointment"]
doctors = db["doctors"]
medicine_orders_collection= db["medicine_orders"]
doctor_counters = db["counters"]

# Create TTL index (auto delete after 2 minutes)
otp_collection.create_index("created_at", expireAfterSeconds=120)
db.activity_logs.create_index("createdAt",expireAfterSeconds=180)



FAST2SMS_API_KEY = "ngqdw3X9hrZx5WHaVPs2CKDUucGzAElSyMvNjFRb6ko8QtJ7p0YQiGgqLolhC8KPWuUbxnmsrVwZc5HS"

# Generate OTP
def generate_otp():
    return str(random.randint(100000, 999999))


# 📩 Send OTP API
@c2c_app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.json
    number = data.get("number")

    if not number:
        return jsonify({"status": False, "message": "Mobile number required"}), 400

    otp = generate_otp()

    # Remove old OTP (optional)
    otp_collection.delete_many({"number": number})

    # Save OTP in MongoDB
    otp_collection.insert_one({
        "number": number,
        "otp": otp,
        "created_at": datetime.utcnow()
    })

    # Fast2SMS API
    url = "https://www.fast2sms.com/dev/bulkV2"
    querystring = {
        "authorization": FAST2SMS_API_KEY,
        "route": "dlt",
        "sender_id": "LCLPRI",
        "message": "185893",
        "variables_values": otp,
        "flash": "0",
        "numbers": number
    }

    try:
        response = requests.get(url, params=querystring)
        res_data = response.json()

        return jsonify({
            "status": True,
            "message": "OTP sent successfully",
            "otp_debug": otp,  # ❌ remove in production
            "response": res_data
        })

    except Exception as e:
        return jsonify({"status": False, "error": str(e)}), 500


# 🔐 Verify OTP API
@c2c_app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.json
    number = data.get("number")
    otp = data.get("otp")

    if not number or not otp:
        return jsonify({"status": False, "message": "Number and OTP required"}), 400

    record = otp_collection.find_one({"number": number})

    if not record:
        return jsonify({"status": False, "message": "OTP expired or not found"}), 400

    if record["otp"] == otp:
        otp_collection.delete_one({"_id": record["_id"]})
        #  # Normalize number (India)
        # number = "91" + number[-10:]
        user = users_collection.find_one({"number": number})
        # print(user)

        if user:
            return jsonify({
                "status": True,
                "message": "OTP verified - Existing User",
                "user":{
                    "user_id": str(user['_id']),
                    "mobile": number,
                },
                "screen": 1
            }),200
        else:
            return jsonify({
                "status": True,
                "message": "OTP verified - New User",
                "screen": 2
            }),200
    else:
        return jsonify({"status": False, "message": "Invalid OTP"}), 400


# 👤 Signup API
@c2c_app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.json

        number = data.get("number")
        name = data.get("name")
        gender = data.get("gender")

        # ✅ Validation
        if not number or not name or not gender:
            return jsonify({
                "status": False,
                "message": "Number, Name and Gender are required"
            }), 400

        # Normalize number (India)
        # number = "+91" + number[-10:]

        # 💾 Insert user
        user_data = {
            **data,
            "number": number,
            "name": name,
            "gender": gender,
            "created_at": datetime.utcnow()
        }

        result = users_collection.insert_one(user_data)

        return jsonify({
            "status": True,
            "message": "Signup successful",
            "user":{
                "user_id": str(result.inserted_id),
                "mobile": number,
            }
        }),200
    except Exception as e:
        return jsonify({'status':False,"message": str(e)}), 500
    


@c2c_app.route('/user', methods=['GET'])
def get_user():
    number = request.args.get("number")
    user_id = request.args.get("user_id")

    if not number and not user_id:
        return jsonify({
            "status": False,
            "message": "Provide number or user_id"
        }), 400

    query = {}

    # 🔍 Search by number
    if number:
        # number = "+91" + number[-10:]
        query["number"] = number

    # 🔍 Search by user_id
    if user_id:
        try:
            query["_id"] = ObjectId(user_id)
        except:
            return jsonify({
                "status": False,
                "message": "Invalid user_id"
            }), 400

    user = users_collection.find_one(query)

    if not user:
        return jsonify({
            "status": False,
            "message": "User not found"
        }), 404
    user["_id"] = str(user["_id"])

    return jsonify({
        "status": True,
        "data": user
    })
@c2c_app.route('/all_users', methods=['GET'])
def get_all_user():
    users = list(users_collection.find())

    for u in users:
        u["_id"] = str(u["_id"])

    return jsonify({
        "status": True,
        "data": users
    })


def appointment_fee(amount):
    if amount <= 100:
        platform_fee = 16.95
        gst = 3.05
        doctor_fee = 200
    else:
        platform_fee = float(amount)/10 - ((float(amount)/10) * 18 / 118)
        gst = ((float(amount)/10) * 18 / 118)
        doctor_fee = float(amount) - float(amount)/10

    return platform_fee, gst, doctor_fee
# make api if new patient then newamount , if old patient then old amount, if booking krne ke baad 3 din se phle fir aata h to uske liye 0 amount, if 3 din ke andar fir aata h to uske liye old amount



@c2c_app.route("/create-order", methods=["POST"])
def create_order():
    data = request.json

    order_id = f"order_{int(time.time())}"

    payload = {
        "order_id": order_id,
        "order_amount": data.get("amount"),
        "order_currency": "INR",
        "customer_details": {
            "customer_id": data.get("customer_id"),
            "customer_phone": data.get("phone")
        }
    }

    headers = {
        "x-client-id": 'TEST10546880b734d6e02f248e953aff08864501',
        "x-client-secret": 'cfsk_ma_test_6e68e1ae3c71cba3bb783d33bf0ee8dc_db4e0c8e',
        "Content-Type": "application/json",
        "x-api-version": "2025-01-01",
    }

    try:
        response = requests.post('https://sandbox.cashfree.com/pg/orders', json=payload, headers=headers)
        # return jsonify(response.json())
        cf_data = response.json()
        return jsonify({
        "order_id": cf_data["order_id"],
        "payment_session_id": cf_data["payment_session_id"]
    })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import requests
import uuid
import time


# =====================================================
# FUZZY NAME MATCH
# =====================================================

def similar(a, b):
    return SequenceMatcher(
        None,
        a.lower(),
        b.lower()
    ).ratio()


# =====================================================
# CHECK PATIENT HISTORY
# =====================================================

# def check_patient_history(
#     whatsapp_number,
#     patient_name,
#     date_of_birth,
#     doctor_id,
#     guardian,
# ):

#     patients = list(
#         appointment.find(
#             {
#                 "whatsapp_number": whatsapp_number,
#                 # "date_of_birth": date_of_birth,
#                 "doctor_phone_id": doctor_id
#             }
#         ).sort("createdAt", -1)
#     )

#     best_match = None
#     best_score = 0

#     for patient in patients:

#         score = similar(
#             patient_name,
#             patient.get("patient_name", "")
#         )

#         if score > best_score:
#             best_score = score
#             best_match = patient

#     if best_match and best_score >= 0.7:

#         return {
#             "exists": True,
#             "patient": best_match
#         }

#     return {
#         "exists": False,
#         "patient": None
#     }

def check_patient_history(
    whatsapp_number,
    patient_name,
    date_of_birth,
    doctor_id,
    guardian,
):

    patients = list(
        appointment.find(
            {
                "whatsapp_number": whatsapp_number,
                "doctor_phone_id": doctor_id
            }
        ).sort("createdAt", -1)
    )

    best_match = None
    best_score = 0

    for patient in patients:

        # patient name similarity
        name_score = similar(
            patient_name.lower().strip(),
            patient.get("patient_name", "").lower().strip()
        )

        # father/guardian name similarity
        guardian_score = similar(
            guardian.lower().strip(),
            patient.get("guardian_name", "").lower().strip()
        )

        # combined average score
        final_score = (name_score + guardian_score) / 2

        if final_score > best_score:
            best_score = final_score
            best_match = patient

    # 70% matching required
    if best_match and best_score >= 0.7:
        return {
            "exists": True,
            "patient": best_match,
            "match_score": round(best_score, 2)
        }

    return {
        "exists": False,
        "patient": None,
        "match_score": round(best_score, 2)
    }


# =====================================================
# GET LATEST PAID APPOINTMENT
# =====================================================

def get_latest_paid_appointment(
    whatsapp_number,
    patient_name,
    date_of_birth,
    doctor_id,
    guardian,
):

    history = check_patient_history(
        whatsapp_number,
        patient_name,
        date_of_birth,
        doctor_id,
        guardian,
    )
    # print("history",history)

    if not history["exists"]:
        return None

    latest_paid = appointment.find_one(
        {
            "whatsapp_number": whatsapp_number,
            "date_of_birth": date_of_birth,
            "doctor_phone_id": doctor_id,
            # "payment_status": "pending"
            "payment_status": "paid"
        },
        sort=[("createdAt", -1)]
    )

    return latest_paid


# =====================================================
# CALCULATE APPOINTMENT amount
# =====================================================

def calculate_appointment_fee(
    whatsapp_number,
    patient_name,
    date_of_birth,
    doctor_id,
    doctor,
    guardian,
    appointment_date
):
    FULL_FEE=int(doctor.get("appointmentfee",'100'))
    FOLLOWUP_FEE=int(doctor.get("secondappointmentfee","100"))
    FREE_FOLLOWUP_DAYS=doctor.get("revisit",'3')

    latest_paid = get_latest_paid_appointment(
        whatsapp_number,
        patient_name,
        date_of_birth,
        doctor_id,
        guardian
    )
    # print('latest paid',latest_paid)

    # NEW PATIENT
    if not latest_paid:

        return {
            "appointment_type": "NEW",
            "amount": FULL_FEE,
            "payment_required": True,
            "last_appointment": None,
            "days_difference": None,
            "last_payment_id":None
        }

    last_date = datetime.strptime(
            latest_paid["date_of_appointment"],
            "%Y-%m-%d"
        ).date()
    today = datetime.strptime( appointment_date,"%Y-%m-%d").date()
    days_difference = (today - last_date).days


    # FREE FOLLOWUP
    if days_difference <= int(FREE_FOLLOWUP_DAYS):

        return {
            "appointment_type": "FREE_FOLLOWUP",
            "amount": 0,
            "payment_required": False,
            "last_appointment":
                latest_paid["date_of_appointment"],
            "days_difference": days_difference,
            "last_payment_id":latest_paid['pay_id']
        }

    # PAID FOLLOWUP
    return {
        "appointment_type": "PAID_FOLLOWUP",
        "amount": FOLLOWUP_FEE,
        "payment_required": True,
        "last_appointment":
            latest_paid["createdAt"].strftime("%Y-%m-%d"),
        "days_difference": days_difference
    }


    
def razorpay_create_order(amount):

    try:

        # =========================================
        # CONVERT TO PAISA
        # =========================================
        amount_in_paisa = float(amount) * 100

        # =========================================
        # CREATE ORDER
        # =========================================
        order = razorpay_client.order.create({
            "amount": amount_in_paisa,
            "currency": "INR",
            "receipt": f"receipt_{time.time()}",
            "payment_capture": 1
        })

        print("Razorpay Order:", order)

        # =========================================
        # RETURN RESPONSE
        # =========================================
        return {
            "success": True,
            "order_id": order.get("id"),
            "amount": order.get("amount"),
            "currency": order.get("currency"),
            "status": order.get("status"),
            "full_response": order
        }

    except Exception as e:

        print("Razorpay Order Error:", str(e))

        return {
            "success": False,
            "message": str(e)
        }
# =====================================================
# GENERATE CASHFREE PAYMENT LINK
# =====================================================

def generate_payment_link(data, amount):

    try:

        url = "https://sandbox.cashfree.com/pg/links"

        # headers = {
        #     "x-client-id": "945362dcfe647952a997dd8c2b263549",
        #     "x-client-secret": "cfsk_ma_prod_b1fca991dbc82055f07729016607aeed_5c08c766",
        #     "Content-Type": "application/json",
        #     "x-api-version": "2025-01-01",
        # }
        headers = {
            "x-client-id": "TEST10546880b734d6e02f248e953aff08864501",
            "x-client-secret": "cfsk_ma_test_6e68e1ae3c71cba3bb783d33bf0ee8dc_db4e0c8e",
            "Content-Type": "application/json",
            "x-api-version": "2025-01-01",
        }

        IST = timezone(timedelta(hours=5, minutes=30))

        expiry_time = (
            datetime.now(IST) + timedelta(minutes=30)
        ).strftime("%Y-%m-%dT%H:%M:%S%z")

        expiry_time = (
            expiry_time[:-2] + ":" + expiry_time[-2:]
        )

        payload = {
            "link_id": f"link_{int(time.time())}",

            "link_amount": amount,

            "link_currency": "INR",

            "link_purpose": "appointment_payment",

            "customer_details": {
                "customer_name":
                    data.get("patient_name", "Patient"),

                "customer_phone":
                    data["whatsapp_number"],

                "customer_email":
                    data.get("email", "test@gmail.com")
            },

            "link_notify": {
                "send_sms": True,
                "send_email": False
            },

            "link_auto_reminders": True,

            "link_meta": {
                "return_url":
                    "https://api.care2connect.in/c2c_app/payment-success",

                "notify_url":
                    "https://yourdomain.com/cashfree/webhook"
            },

            "link_expiry_time": expiry_time,
            "link_notes": {
                    "source": "mobile_app"
                }
        }

        response = requests.post(
            url,
            json=payload,
            headers=headers
        )

        # return response.json()
        response_data = response.json()

        return {
            "success": response.ok,
            **response_data
        }
    except Exception as e:
        print(str(e))
        return {
            "success": False,
            "message": str(e)
        }

from datetime import datetime
from dateutil.relativedelta import relativedelta


def calculate_age(dob):

    try:
    
        if isinstance(dob, str):

            dob = dob.strip()

            # Supported formats
            formats = [
                "%Y-%m-%d",   # 2000-05-10
                "%d-%m-%Y",   # 10-05-2000
                "%d/%m/%Y",   # 10/05/2000
                "%Y/%m/%d"    # 2000/05/10
            ]

            parsed = None

            for fmt in formats:
                try:
                    parsed = datetime.strptime(dob, fmt)
                    break
                except:
                    pass

            if not parsed:
                return {
                    "success": False,
                    "message": "Invalid date format"
                }

            dob = parsed

        # =========================================
        # TODAY DATE
        # =========================================
        today = datetime.today()

        # =========================================
        # CALCULATE DIFFERENCE
        # =========================================
        diff = relativedelta(today, dob)

        # =========================================
        # RETURN DATA
        # =========================================
        return f"{diff.years} Year {diff.months} Month {diff.days} Day"

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }



# =====================================================
# CREATE APPOINTMENT
# =====================================================

@c2c_app.route("/create-appointment", methods=["POST"])
def create_appointment():

    try:

        data = request.json
        type = request.args.get("from")

        whatsapp_number = data["whatsapp_number"]
        patient_name = data["patient_name"]
        date_of_birth = data["date_of_birth"]
        doctor_id = data["doctor_id"]
        guardian = data["guardian_name"]

        # =============================================
        # GET DOCTOR DETAILS
        # =============================================

        doctor = doctors.find_one({
            "_id": ObjectId(doctor_id)
        })

        if not doctor:

            return jsonify({
                "status": False,
                "message": "Doctor not found"
            }), 404

        # =============================================
        # CALCULATE amount
        # =============================================

        fee_info = calculate_appointment_fee(
            whatsapp_number,
            patient_name,
            date_of_birth,
            doctor_id,
            doctor,
            guardian,
            data['date'],
        )
        # print(fee_info)

        appointment_id = str(uuid.uuid4())

        # =============================================
        # APPOINTMENT DATASET
        # =============================================

        dataset = {

            "appointment_id": appointment_id,

            "patient_name": patient_name,

            "guardian_name":
                data.get("guardian_name"),

            "date_of_birth": date_of_birth,

            "sex": data.get("sex"),

            "whatsapp_number": whatsapp_number,
            'date_of_appointment': data.get("date", ""),
            'time_slot': data.get("time", ""),

            "doctor_phone_id": doctor_id,

            "doctor_name":
                doctor.get("doctor_name"),

            "department":
                doctor.get("department",''),

            "appointment_type":
                fee_info["appointment_type"],

            # "amount":
            #     fee_info["amount"],

            "payment_required":
                fee_info["payment_required"],

            "payment_status": (
                "not_required"
                if fee_info["amount"] == 0
                else "pending"
            ),

            "status": (
                "success"
                if fee_info["amount"] == 0
                else "pending_payment"
            ),

            "last_appointment":
                fee_info["last_appointment"],

            "days_difference":
                fee_info["days_difference"],
            

            "createdAt": datetime.utcnow(),

            "role": "appointment"
        }

        # =============================================
        # FREE FOLLOWUP
        # =============================================

        if fee_info["amount"] == 0:
            dataset["amount"] = 0
            result = list(appointment.find({"doctor_phone_id": doctor_id, "date_of_appointment":data.get("date", ""),"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
            data_length = 1
            if result:
                data_length = len(result)+1
            xdate = data.get("date", "")
            date_obj = datetime.strptime(xdate, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%Y%m%d")

            appoint_number = str(formatted_date)+'-'+str(data_length)

            index_number = getindex(doctor_id,data.get("time", ""),xdate)
            dataset["appoint_number"]=appoint_number
            dataset["appointment_index"]=index_number
            dataset["pay_id"]= f"old_{fee_info["last_payment_id"]}"

            insert_id = appointment.insert_one(
                dataset
            ).inserted_id

            return jsonify({
                "status": True,
                "message":
                    "Free follow-up appointment created",

                "appointment_type":
                    fee_info["appointment_type"],

                "amount": 0,
                'appoint_number':appoint_number,
                'appointment_index':index_number,

                "appointment_id":
                    str(insert_id),

                "payment_required": False,
                
            })

        # =============================================
        # GENERATE PAYMENT LINK
        # =============================================

        if type == 'web':
            payment_response = razorpay_create_order(
                                fee_info["amount"]
                            )

        else:
             payment_response = generate_payment_link(
                                data,
                                fee_info["amount"]
                            )
             
        if not payment_response.get("success"):
                return jsonify({
                    "success": False,
                    "message": payment_response.get("message", "Unable to create payment order")
                }), 500
        
        link_url = (
            payment_response.get("order_id") or
            payment_response.get("link_url")
        )

        # =============================================
        # SAVE RESPONSE
        # =============================================

        # dataset["payment_response"] = payment_response
        dataset["payment_link"] = link_url
        # dataset["payment_link_id"] = payment_response.get('payment_link_id',''),

        insert_id = appointment.insert_one(
            dataset
        ).inserted_id

        return jsonify({
            "success": True,

            "appointment_type":
                fee_info["appointment_type"],

            "amount":
                fee_info["amount"],

            "payment_required": True,

            "payment_link": link_url,

            "appointment_id":
                str(insert_id)
        })

    except Exception as e:
        print(str(e))
        return jsonify({
            "status": False,
            "message": str(e)
        }), 500


def getindex(docter_id,tslot,date):

    doc_id = ObjectId(docter_id)
    document = doctors.find_one({"_id": doc_id})
    xslot = document['slots']['slotsvalue']

    formatted_output = [
                {
                     "id": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+ datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                    "slot": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                    "length": item["maxno"]
                }
                for index, item in enumerate(xslot)
                ]

    target_id = tslot
    total_length = 0

    for slot in formatted_output:
        if slot['id'] == target_id:
            break
        total_length += int(slot['length'])


    result = list(appointment.find({"doctor_phone_id": docter_id,'time_slot':tslot ,"date_of_appointment":date,"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
    data_length = 1
    if result:
        data_length = len(result)+1

    appointment_number = data_length+total_length
    print(appointment_number)
    return appointment_number

# =====================================================
# CASHFREE WEBHOOK
# =====================================================

@c2c_app.route("/cashfree/webhook", methods=["POST"])
def cashfree_webhook():

    try:

        data = request.json

        link_data = data.get("data", {})

        link_url = link_data.get("link_url")

        link_status = link_data.get("link_status")

        paid_amount = link_data.get("link_amount_paid")

        order_data = link_data.get("order", {})

        transaction_status = (
            order_data.get("transaction_status")
        )

        transaction_id = (
            order_data.get("transaction_id")
        )

        retrieved_data = appointment.find_one({"payment_link": link_url})

        if not retrieved_data:
                return 'ok',200

        result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":retrieved_data['date_of_appointment'],"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
        data_length = 1
        if result:
            data_length = len(result)+1

        xdate = retrieved_data['date_of_appointment']
        date_obj = datetime.strptime(xdate, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y%m%d")

        appoint_number = str(formatted_date)+'-'+str(data_length)

        index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)

        # PAYMENT SUCCESS
        if (
            link_status == "PAID"
            and
            transaction_status == "SUCCESS"
        ):

            appointment.update_one(
                {
                    "payment_link": link_url
                },
                {
                    "$set": {

                        "payment_status": "paid",
                        'appoint_number':appoint_number,
                        'appointment_index':index_number,

                        "status": "success",

                        "amount":float(paid_amount),

                        "pay_id":
                            str(transaction_id),

                        "paid_at":
                            datetime.utcnow()
                    }
                }
            )

            print("PAYMENT SUCCESS")

        else:

            print("PAYMENT FAILED")

    except Exception as e:

        print(str(e))

    return jsonify({
        "status": "ok"
    }), 200


def get_status(date_str, time_range):
    """
    date_str: '2026-04-10'
    time_range: '11:00 AM - 12:00 PM'
    """

    # Split time range
    start_time_str, end_time_str = time_range.split(" - ")

    # Combine date + end time
    end_datetime_str = f"{date_str} {end_time_str}"

    # Convert to datetime object
    appointment_end = datetime.strptime(end_datetime_str, "%Y-%m-%d %I:%M %p")

    # Current time
    now = datetime.now()

    # Compare
    if appointment_end > now:
        return "Upcoming"
    else:
        return "Completed"

import re;

@c2c_app.route("/appointments/<string:m>", methods=["GET"])
def get_appointments(m):
    try:
        appointments = []
        status = request.args.get("status")
        m = str(m).strip()

        # keep only digits
        digits = re.sub(r"\D", "", m)

        # create possible formats
        possible_numbers = list(set([
            digits,                # 919876543210
            digits[-10:],          # 9876543210
            f"+{digits}",          # +919876543210
            f"91{digits[-10:]}",   # 919876543210
            f"+91{digits[-10:]}"   # +919876543210
        ]))


        # data = appointment.find({'amount': {'$gt': -1}, 'whatsapp_number': m}).sort("_id", -1)  # latest first
        # data = appointment.find({'whatsapp_number': m}) # latest first
        # data = appointment.find() # latest first

        # latest first
        data = appointment.find(
            {
                'amount': {'$gt': -1},
                "whatsapp_number": {
                    "$in": possible_numbers
                }
            }
        ).sort("_id", -1)

        doctor_list = list(doctors.find({"role": "doctor"}))

        # 🔥 Create mapping: {doctor_phone_id: doctor_name}
        doctor_map = {
            str(doc.get("_id")): {
                "name": doc.get("name"),
                "imageUrl": doc.get("imageUrl"),   # 👈 yeh field apne DB ke hisaab se change karo
                "specialty": doc.get("specialty")
            }
        for doc in doctor_list
        }

        for item in data:
            doctor_id = str(item.get("doctor_phone_id"))
            doc = doctor_map.get(doctor_id, {})
            appointments.append({
                "id": str(item.get("_id")),
                "doctorName": doc.get("name", "Unknown Doctor"),
                "specialty": 'Orthopaedics',
                "doctorPic": doc.get("imageUrl", "https://randomuser.me/api/portraits/men/15.jpg"),
                "patientName": item.get("patient_name"),
                "date": item.get("date_of_appointment"),
                "phone":item.get("whatsapp_number","9179562549"),
                "time": item.get("time_slot"),
                "amount": item.get("amount"),
                "gender": item.get("sex"),
                "fatherName": item.get("guardian_name"),
                "dob": item.get("date_of_birth"),
                'age':calculate_age(item.get("date_of_birth")),
                "status": get_status(item.get("date_of_appointment"), item.get("time_slot")),
                "pay_id": item.get("pay_id"),
                "appointmentNo": item.get("appointment_index"),
                'createdAt':item.get('createdAt'),
                'state':item.get('state',"NA"),
                'city':item.get('city',"NA"),
                'address':item.get('address',"NA"),
                'pincode':item.get('pincode',"NA"),
                'email':item.get('email',"NA"),
            })
        if status:
            appointments = [a for a in appointments if a.get('status') == status]

        appointments =sorted(appointments, key=lambda x: x["date"])

        return jsonify({
            "success": True,
            "data": appointments
        }), 200

    except Exception as e:
        print(str(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
@c2c_app.route("/payment-status/<string:order_id>", methods=["GET"])
def payment_status(order_id):
    try:
        # latest first
        data = appointment.find_one({"_id":ObjectId(order_id)})

        if not data:
            return jsonify({
            "success": False,
            "error": "Appointment Not Found"
        }), 500

        dataset={
            
            }

        return jsonify({
            "success": True,
            "id": str(data.get("_id")),
            "payment_status":data.get('status','')
        }), 200

    except Exception as e:
        print(str(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    
@c2c_app.route("/appointment_details/<string:m>", methods=["GET"])
def get_appointment_details(m):
    try:
        # latest first
        data = appointment.find_one({"_id":ObjectId(m)})

        if not data:
            return jsonify({
            "success": False,
            "error": "Appointment Not Found"
        }), 500
        doctor = doctors.find_one({"_id": ObjectId(data.get("doctor_phone_id"))})

        dataset={
            "id": str(data.get("_id")),
            "doctorName": doctor.get("name", "Unknown Doctor"),
            "specialty": 'Orthopaedics',
            "doctorPic": doctor.get("imageUrl", "https://randomuser.me/api/portraits/men/15.jpg"),
            "patientName": data.get("patient_name"),
            "date": data.get("date_of_appointment"),
            "phone":data.get("whatsapp_number","9179562549"),
            "time": data.get("time_slot"),
            "amount": data.get("amount"),
            "gender": data.get("sex"),
            "fatherName": data.get("guardian_name"),
            "dob": data.get("date_of_birth"),
            'age':calculate_age(data.get("date_of_birth")),
            "status": get_status(data.get("date_of_appointment"), data.get("time_slot")),
            "pay_id": data.get("pay_id"),
            "appointmentNo": data.get("appointment_index"),
            'createdAt':data.get('createdAt')
            }

        return jsonify({
            "success": True,
            "data": dataset
        }), 200

    except Exception as e:
        print(str(e))
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500



import razorpay
import hmac
import hashlib

# RAZORPAY_KEY_ID = "rzp_live_R9tGl7bLSIBV6f"
# RAZORPAY_KEY_SECRET = "dTvrApHzGc2VGCw8olP3xVOL"

RAZORPAY_KEY_ID = "rzp_test_TlMQdAmmaO6PuE"
RAZORPAY_KEY_SECRET = "XwNvd7hpUY5UK06F81X64RCR"

# ---------- Razorpay Client ----------
razorpay_client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

# ---------- Create Order API ----------
@c2c_app.route("/web-create-order", methods=["POST"])
def web_create_order():
    try:
        data = request.get_json() or {}

        mobile = data.get("mobile", "")
        doctor_id = data.get("doctor_id", "")
        from_number = "91" + mobile if len(mobile) == 10 else mobile

        print("Received data:", 7)

        doctor = doctors.find_one({'_id': ObjectId(doctor_id)})
        fee = float(doctor.get('appointmentfee', 0))

        print("Received data:", 7)


        amount_in_paisa = int(fee * 100)

            # 🔹 Create Razorpay Order
        order_data = {
                "amount": amount_in_paisa,
                "currency": "INR",
                "receipt": "receipt_001",
            }
        print("Creating Razorpay order with data:", data)

        order = razorpay_client.order.create(order_data)
        link_url = order['id']
        dataset = {
                'kalra_id': 'xx',
                'appointmenttype': 'current',

                'agent_id': data.get("agent_id", "User"),

                'patient_name': data.get("patient_name", "User"),
                'guardian_name': data.get("father_name", "User"),
                'date_of_appointment': data.get("date", "User"),
                'time_slot': data.get("time", "User"),

                'doctor_phone_id': data.get("doctor_id", "User"),
                'email': data.get("email", "User"),
                'symptoms': data.get("symptoms", "User"),
                'age': data.get("age", "User"),
                'timestamp': data.get("timestamp", "User"),

                'whatsapp_number': from_number,
                'date_of_birth': data.get("dob", "User"),
                'city': data.get("city", "none"),
                'state': data.get("state", "none"),
                'pincode': data.get("pincode", "none"),
                'address': data.get("address", "none"), 

                'role': 'appointment',
                'status': 'created',
                "createdAt": datetime.utcnow(),

                "sex": data.get("sex", "User"),
                "vaccine": "No",

                'razorpay_url': link_url,
                'payment_status': 'link generated',
                'itype':'test'
            }

        inserted_id = str(appointment.insert_one(dataset).inserted_id)
        # print(inserted_id)

        return jsonify(order)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


@c2c_app.route('/verify', methods=['POST'])
def verify_payment():
    try:
        data = request.get_json()
        order_id = data.get('razorpay_order_id')
        payment_id = data.get('razorpay_payment_id')
        signature = data.get('razorpay_signature')
        amount = data.get("amount")

        print(data)

        generated_signature = hmac.new(
            bytes(RAZORPAY_KEY_SECRET, 'utf-8'),
            bytes(order_id + "|" + payment_id, 'utf-8'),
            hashlib.sha256
        ).hexdigest()

        if generated_signature == signature:
            # appointment.update_one({'payment_link': order_id},{'$set':{'payment_status':'paid','status':'success','pay_id':payment_id,'appoint_number':'001','amount':float(100),'appointment_index':1}})

            # return jsonify({"status": "success"})
            # retrieved_data = appointment.find_one({"payment_link": order_id})
            retrieved_data = appointment.find_one({"razorpay_url": order_id})

            if not retrieved_data:
                return jsonify({"status": "failure"}), 400

            result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":retrieved_data['date_of_appointment'],"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
            data_length = 1
            if result:
                data_length = len(result)+1

            xdate = retrieved_data['date_of_appointment']
            date_obj = datetime.strptime(xdate, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%Y%m%d")

            appoint_number = str(formatted_date)+'-'+str(data_length)

            index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)

            # PAYMENT SUCCESS
            # if (
            #     link_status == "PAID"
            #     and
            #     transaction_status == "SUCCESS"
            # ):

            appointment.update_one(
                # {
                #     "payment_link": order_id
                # },
                {
                                    "razorpay_url": order_id
                                },
                {
                    "$set": {

                        "payment_status": "paid",
                        'appoint_number':appoint_number,
                        'appointment_index':index_number,

                        "status": "success",

                        "amount":float(amount),

                        "pay_id":
                            str(payment_id),

                        "paid_at":
                            datetime.utcnow()
                    }
                }
            )

            print("PAYMENT SUCCESS")
            return jsonify({"status": "success","appointment_index": index_number,"payment_id": str(payment_id), "amount": float(amount)}),200

        else:
            return jsonify({"status": "failure"}), 400
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


#agent appointments

import secrets
import string

def generate_identity_id():
    characters = string.ascii_letters + string.digits
    unique_part = ''.join(secrets.choice(characters) for _ in range(13))
    return f"wlt_{unique_part}"

# Example

def make_c2c_voucher(payment_id, fee,pfee,doctorfee, phone, doctor_id):
    vouchers = db["vouchers"]
    try:
    
            duplicatepayment = vouchers.find_one({'Payment_id': payment_id})
            if not duplicatepayment:
    
                    # Current time in UTC (GMT)
                utc_now = datetime.now(ZoneInfo("UTC"))
                ist_now = utc_now.astimezone(ZoneInfo("Asia/Kolkata"))
    
                    
                voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))
                date_str = voucher_date.strftime("%Y-%m-%d")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                start = datetime(date_obj.year, date_obj.month, date_obj.day)
                end = start + timedelta(days=1)
        
                voucher_number_index = "JRV-"+ str(date_str)
                count_txn = vouchers.count_documents({})
                count = vouchers.count_documents({
                    "voucher_type": "Journal",
                    "voucher_mode": "Journal",
                    "voucher_number_index": voucher_number_index   # between start and end of day
                })
        
                voucher_number = "JRV-"+ str(date_str) +'-'+ str(count + 1)
                voucher = {
                            "voucher_number_index" : voucher_number_index,
                            "amount":float(fee),
                            "voucher_number": voucher_number,
                            "voucher_type": 'Journal',
                            "voucher_mode": "Journal",
                            "txn": count_txn + 1,
                            "doctor_id": doctor_id,
                            "from_id": phone,
                            "to_id": payment_id,
                            "date": datetime.now(ZoneInfo("Asia/Kolkata")),
                            "Payment_id": payment_id,
                            "narration": 'Appointment Fee',
                            "entries": [
    
                                    {
                        "narration": "Appointment Fee",
                        "ledger_id": "A15",
                        "ledger_name": "Receivable from Channel Partners",
                        "debit": float(fee),
                        "credit": 0,
                        "employee_id": "LocalPrime",
                        "employee_name": "Local Prime"
                        },
                        {
                        "narration": "Appointment Fee",
                        "ledger_id": "A2",
                        "ledger_name": "Doctor Fee Payble",
                        "debit": 0,
                        "credit": float(doctorfee)
                        },
                        {
                        "narration": "Appointment Fee",
                        "ledger_id": "A3",
                        "ledger_name": "Platform Fee",
                        "debit": 0,
                        "credit": float(pfee)-(float(pfee) * 18 / 118)
                        },
                        {
                        "narration": "Appointment Fee",
                        "ledger_id": "A12",
                        "ledger_name": "CGST",
                        "debit": 0,
                        "credit":(float(pfee) * 18 / 118)/2
                        },
                         {
                        "narration": "Appointment Fee",
                        "ledger_id": "A13",
                        "ledger_name": "SGST",
                        "debit": 0,
                        "credit": (float(pfee) * 18 / 118)/2
                        }     
                        ],
                            "created_by": "system",
                            "created_at": ist_now
                        }
                vouchers.insert_one(voucher)
    except:
            print(2)


@c2c_app.route("/agent-create-order", methods=["POST"])
def agent_create_order():
    try:
        from api_files.badri_computers.trade import db as trade_db
        from api_files.badri_computers.localprime import get_next_sequence, create_wallet_voucher,create_appointment_wallet_voucher

        data = request.get_json() or {}

        mobile = data.get("mobile", "")
        doctor_id = data.get("doctor_id", "")
        agent_id = data.get("agent_id")
        wallet_id = data.get("wallet_id")


        if not agent_id and not wallet_id:
            return jsonify({
                "success": False,
                "error": "agent_id or wallet_id is required"
            }), 400

        if not doctor_id:
            return jsonify({
                "success": False,
                "error": "doctor_id is required"
            }), 400

        try:
            doctor = doctors.find_one({'_id': ObjectId(doctor_id)})
        except Exception:
            return jsonify({
                "success": False,
                "error": "Invalid doctor_id"
            }), 400

        if not doctor:
            return jsonify({
                "success": False,
                "error": "Doctor not found"
            }), 404

        # Calculate fee
        if data.get("amount") is not None:
            try:
                fee = float(data.get("amount"))
            except (ValueError, TypeError):
                fee = float(doctor.get('appointmentfee', 0) or 0)
        else:
            raw_fee = doctor.get('appointmentfee', 0)
            fee = float(raw_fee) if raw_fee else 0.0

        # Find agent's wallet
        wallet_type = data.get("wallet_type", "").lower()
        wallet = None
        is_saving_wallet = False

        if wallet_type == "saving":
            if wallet_id:
                try:
                    wallet = trade_db.saving_wallets.find_one({"_id": ObjectId(wallet_id)})
                except Exception:
                    wallet = None
            if not wallet and agent_id and agent_id != "User":
                try:
                    wallet = trade_db.saving_wallets.find_one({"agent_id": ObjectId(agent_id)})
                except Exception:
                    wallet = None
                if not wallet:
                    wallet = trade_db.saving_wallets.find_one({"agent_id": str(agent_id)})
            if wallet:
                is_saving_wallet = True
        else:
            if wallet_id:
                try:
                    wallet = trade_db.wallets.find_one({"_id": ObjectId(wallet_id)})
                except Exception:
                    wallet = None
                if not wallet:
                    try:
                        wallet = trade_db.saving_wallets.find_one({"_id": ObjectId(wallet_id)})
                        if wallet:
                            is_saving_wallet = True
                    except Exception:
                        wallet = None

            if not wallet and agent_id and agent_id != "User":
                try:
                    wallet = trade_db.wallets.find_one({"agent_id": ObjectId(agent_id)})
                except Exception:
                    wallet = None
                if not wallet:
                    wallet = trade_db.wallets.find_one({"agent_id": str(agent_id)})
                if not wallet:
                    try:
                        wallet = trade_db.saving_wallets.find_one({"agent_id": ObjectId(agent_id)})
                    except Exception:
                        wallet = None
                    if not wallet:
                        wallet = trade_db.saving_wallets.find_one({"agent_id": str(agent_id)})
                    if wallet:
                        is_saving_wallet = True

        if not wallet:
            return jsonify({
                "success": False,
                "error": "Wallet not found for this agent"
            }), 404

        if wallet.get("status") != "active":
            return jsonify({
                "success": False,
                "error": "Wallet is not active"
            }), 400

        if is_saving_wallet:
            available_balance = float(wallet.get("balance", 0.0))
            if fee > available_balance:
                return jsonify({
                    "success": False,
                    "error": "Insufficient saving wallet balance",
                    "balance": available_balance,
                    "requestedAmount": fee
                }), 400
        else:
            available_credit = float(wallet.get("availableCredit", 0))
            if fee > available_credit:
                return jsonify({
                    "success": False,
                    "error": "Credit limit exceeded / Insufficient wallet balance",
                    "creditLimit": wallet.get("creditLimit", 0),
                    "usedCredit": wallet.get("usedCredit", 0),
                    "availableCredit": available_credit,
                    "requestedAmount": fee
                }), 400

        from_number = "91" + mobile if len(mobile) == 10 else mobile

        # Date and appointment numbering
        xdate = data.get("date", "User")
        try:
            date_obj = datetime.strptime(xdate, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%Y%m%d")
        except Exception:
            formatted_date = datetime.utcnow().strftime("%Y%m%d")

        result = list(appointment.find({
            "doctor_phone_id": str(doctor_id),
            "date_of_appointment": xdate,
            "amount": {"$gt": -1}
        }, {"_id": 0}))

        data_length = 1
        if result:
            data_length = len(result) + 1

        appoint_number = str(formatted_date) + '-' + str(data_length)

        try:
            index_number = getindex(str(doctor_id), data.get("time", "User"), xdate)
        except Exception:
            index_number = data_length

        now = datetime.utcnow()
        razorpay_url = generate_identity_id()

        dataset = {
            'kalra_id': 'xx',
            'appointmenttype': 'current',
            'agent_id': str(data.get("agentCode", "NA")),
            'markup_amount': str(data.get("markup_amount", "0")),
            'patient_name': data.get("patient_name", "User"),
            'guardian_name': data.get("father_name", "User"),
            'date_of_appointment': xdate,
            'time_slot': data.get("time", "User"),
            'doctor_phone_id': str(doctor_id),
            'email': data.get("email", "User"),
            'symptoms': data.get("symptoms", "User"),
            'age': data.get("age", "User"),
            'timestamp': data.get("timestamp", "User"),
            'whatsapp_number': from_number,
            'date_of_birth': data.get("dob", "User"),
            'city': data.get("city", "none"),
            'state': data.get("state", "none"),
            'pincode': data.get("pincode", "none"),
            'address': data.get("address", "none"),
            'role': 'appointment',
            'status': 'success',
            "createdAt": now,
            "sex": data.get("sex", "User"),
            "vaccine": "No",
            'razorpay_url': razorpay_url,
            'pay_id': razorpay_url,
            'paid_at': now,
            'payment_status': 'paid',
            'itype': 'test',
            'amount': float(fee),
            'appoint_number': appoint_number,
            'appointment_index': index_number,
            'wallet_id': str(wallet["_id"]),
            'wallet_number': wallet.get("walletNumber"),
            'wallet_type': "saving" if is_saving_wallet else "credit"
        }

        # Wallet deduction, voucher, and transaction
        voucher = None
        transaction = None

        new_available_credit = None
        new_balance = None

        if fee > 0:
            patient_name = dataset.get("patient_name", "User")
            narration = data.get("remarks") or f"Appointment booking - {appoint_number} for {patient_name}"
            created_by = data.get("created_by") or str(wallet.get("agent_id", "admin"))

            markup_amount = float(data.get("markup_amount", 0.0))

            voucher = create_appointment_wallet_voucher(
                wallet=wallet,
                amount=fee,
                markup_amount=markup_amount,
                voucher_type="Journal",
                voucher_mode="Journal",
                narration=narration,
                credit_ledger_id="A43",
                credit_ledger_name="Payable to Service Providers",
                credit_ledger_id2="A45",
                credit_ledger_name2="Service Fees",
                debit_ledger_id="A44",
                debit_ledger_name="Advance from Channel Partners",
                created_by=created_by
            )

            pfee = float(doctor.get('platformfee', 0) or 0)
            doctorfee = float(doctor.get('doctorfee', 0) or 0)
            make_c2c_voucher(payment_id=razorpay_url, fee=fee, pfee=pfee , doctorfee=doctorfee, phone=from_number, doctor_id=str(doctor_id))
            fee = float(fee) + float(markup_amount)

            if is_saving_wallet:
                curr_balance = float(wallet.get("balance", 0.0))
                new_balance = round(curr_balance - fee, 2)
                new_available_credit = None
                new_total_withdraw = round(float(wallet.get("totalWithdraw", 0.0)) + fee, 2)

                trade_db.saving_wallets.update_one(
                    {"_id": wallet["_id"]},
                    {
                        "$set": {
                            "balance": new_balance,
                            "totalWithdraw": new_total_withdraw,
                            "updated_at": now
                        }
                    }
                )

                transaction_seq = get_next_sequence("savingWalletTransaction")
                transaction = {
                    "transactionNumber": f"SWT{transaction_seq:08d}",
                    "wallet_id": wallet["_id"],
                    "walletNumber": wallet.get("walletNumber"),
                    "agent_id": wallet.get("agent_id"),
                    "agentCode": wallet.get("agentCode"),
                    "agentName": wallet.get("agentName"),
                    "type": "withdraw",
                    "amount": fee,
                    "balanceBefore": curr_balance,
                    "balanceAfter": new_balance,
                    "voucher_id": voucher["_id"],
                    "voucher_number": voucher["voucher_number"],
                    "remarks": narration,
                    "status": "success",
                    "created_at": now
                }
                trade_db.saving_wallet_transactions.insert_one(transaction)

            else:
                old_used_credit = float(wallet.get("usedCredit", 0))
                new_used_credit = round(old_used_credit + fee, 2)
                new_available_credit = round(float(wallet.get("creditLimit", 0)) - new_used_credit, 2)
                new_total_withdraw = round(float(wallet.get("totalWithdraw", 0)) + fee, 2)

                # 1. Update wallet balance
                trade_db.wallets.update_one(
                    {"_id": wallet["_id"]},
                    {
                        "$set": {
                            "usedCredit": new_used_credit,
                            "availableCredit": new_available_credit,
                            "totalWithdraw": new_total_withdraw,
                            "updated_at": now
                        }
                    }
                )

                # 3. Create wallet transaction
                transaction_seq = get_next_sequence("walletTransaction")
                transaction = {
                    "transactionNumber": f"WT{transaction_seq:08d}",
                    "wallet_id": wallet["_id"],
                    "walletNumber": wallet.get("walletNumber"),
                    "agent_id": wallet.get("agent_id"),
                    "agentCode": wallet.get("agentCode"),
                    "agentName": wallet.get("agentName"),
                    "type": "withdraw",
                    "amount": fee,
                    "balanceBefore": old_used_credit,
                    "balanceAfter": new_used_credit,
                    "availableCreditBefore": available_credit,
                    "availableCreditAfter": new_available_credit,
                    "voucher_id": voucher["_id"],
                    "voucher_number": voucher["voucher_number"],
                    "remarks": narration,
                    "status": "success",
                    "created_at": now
                }
                trade_db.wallet_transactions.insert_one(transaction)

            dataset["voucher_id"] = voucher["_id"]
            dataset["voucher_number"] = voucher["voucher_number"]
            dataset["transaction_number"] = transaction["transactionNumber"]

        # Insert appointment record
        inserted_id = str(appointment.insert_one(dataset).inserted_id)

        # Link appointment_id to transaction
        if transaction and "_id" in transaction:
            target_tx_coll = trade_db.saving_wallet_transactions if is_saving_wallet else trade_db.wallet_transactions
            target_tx_coll.update_one(
                {"_id": transaction["_id"]},
                {"$set": {"appointment_id": inserted_id, "appoint_number": appoint_number}}
            )

        
        

        return jsonify({
    "success": True,
    "inserted_id": inserted_id,
    "appoint_number": appoint_number,
    "wallet_number": wallet.get("walletNumber"),
    "wallet_type": "saving" if is_saving_wallet else "credit",
    "voucher_number": voucher.get("voucher_number") if voucher else None,
    "transaction_number": transaction.get("transactionNumber") if transaction else None,
    "available_credit": new_available_credit,
    "balance": new_balance if is_saving_wallet else None
}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


@c2c_app.route("/appointments/agent/<string:agent_id>", methods=["GET"])
def get_agent_appointments(agent_id):
    try:
        agent_id = agent_id.strip()

        if not agent_id:
            return jsonify({
                "success": False,
                "message": "agent_id is required"
            }), 400

        # Payment status filter
        payment_status = request.args.get("payment_status", "").strip().lower()

        allowed_statuses = ["paid", "link generated"]

        query = {
            "agent_id": agent_id,
            "payment_status": {
                "$in": [payment_status]
                if payment_status
                else allowed_statuses
            }
        }

        if payment_status and payment_status not in allowed_statuses:
            return jsonify({
                "success": False,
                "message": "Invalid payment_status. Use 'paid' or 'link generated'."
            }), 400

        # Created date filters
        created_from = request.args.get("created_from")
        created_to = request.args.get("created_to")

        if created_from or created_to:
            created_filter = {}

            if created_from:
                start_date = datetime.strptime(
                    created_from, "%Y-%m-%d"
                )
                created_filter["$gte"] = start_date

            if created_to:
                end_date = datetime.strptime(
                    created_to, "%Y-%m-%d"
                ) + timedelta(days=1)
                created_filter["$lt"] = end_date

            query["createdAt"] = created_filter

        # Fetch appointments, latest first
        data = list(
            appointment.find(query).sort("createdAt", -1)
        )

        appointments = []

        doctor_list = list(doctors.find({"role": "doctor"}))

        doctor_map = {
            str(doc["_id"]): doc.get("doctor_name")
            or doc.get("name", "Unknown Doctor")
            for doc in doctor_list
        }

        for item in data:
            doctor_id = str(item.get("doctor_phone_id", ""))
            item["_id"] = str(item["_id"])
            item["doctor_name"] = doctor_map.get(
                doctor_id, "Unknown Doctor"
            )

            for field in ("createdAt", "paid_at"):
                if isinstance(item.get(field), datetime):
                    item[field] = item[field].isoformat()

            appointments.append(item)

        return jsonify({
            "success": True,
            "agent_id": agent_id,
            "total": len(appointments),
            "filters": {
                "payment_status": payment_status or "all",
                "created_from": created_from,
                "created_to": created_to
            },
            "data": appointments
        }), 200

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Invalid date format. Use YYYY-MM-DD."
        }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    

ACCESS_TOKEN = "EAAQNrOr6av0BPojE1zKKzKEDJWVmZBBvtBefl8aS24XBz4QcLzXPeF6wTlCBsIPFeOcwHi5AZBuXwkN6IfpI4uDjyLZAYRvMNF9jdVdeJ2WiNlnY1N1NpmFZBrJCSZAZCALx23ZArZA0jWnn0kEic6gY1Li4TFw8pZAnKZAmJtM0o6ZBfQZC8zi3v2EtcsoEnu9FutphkQZDZD"
PHONE_NUMBER_ID = "794530863749639"  # your phone number id

def send_prescription_whatsapp(to_number, order_id):
    try:
        url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

        # Ensure proper mobile format
        to_number = str(to_number)

        if not to_number.startswith("91"):
            to_number = f"91{to_number}"

        # Order URL
        order_url = f"https://api.care2connect.in/c2c_app/medicine_order?order_id={order_id}"

        headers = {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {
                "preview_url": True,
                "body": (
                    "New Medicine Order Received\n\n"
                    f"View Order:\n{order_url}"
                )
            }
        }

        response = requests.post(
            url,
            headers=headers,
            json=payload
        )

        print("WhatsApp Response:", response.status_code)
        print(response.text)

        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json()
            }

        return {
            "success": False,
            "error": response.text
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@c2c_app.route('/medicine/create', methods=['POST'])
def create_medicine_order():
    try:
        data = request.json
        current_time = datetime.utcnow()

        # Extract data
        store_number = data.get('medical_numbe','9131037870')
        user_mobile = data.get('user_mobile')
        prescription_url = data.get('url')

        # Basic validation
        if not store_number or not user_mobile or not prescription_url:
            return jsonify({
                "success": False,
                "message": "Missing required fields"
            }), 400

        # Create order object
        order = {
            "order_id": f"MED-{int(current_time.timestamp())}",
            "user_id": data.get('user_id'),
            "user_mobile": user_mobile,
            "url": prescription_url,
            "store_id": data.get("store_id"),
            "store_name": data.get("store_name"),
            "patient":data.get("patient",{}),

            "status": "pending",

            "tracking": {
                "order_placed_at": current_time,
                "confirmed_at": None,
                "assigned_at": None,
                "picked_up_at": None,
                "out_for_delivery_at": None,
                "delivered_at": None,
                "cancelled_at": None
            },

            "status_history": [
                {
                    "status": "pending",
                    "updated_at": current_time,
                    "note": "Order created"
                }
            ],

            "created_at": current_time,
            "updated_at": current_time
        }

        # Save to DB
        result = medicine_orders_collection.insert_one(order)

        # Send WhatsApp (non-blocking logic style)
        wa_response = send_prescription_whatsapp(
            store_number,
            str(result.inserted_id),
        )

        if not wa_response.get("success"):
            print("WhatsApp Failed:", wa_response.get("error"))

        return jsonify({
            "success": True,
            "data": {
                "_id": str(result.inserted_id),
                "order_id": order["order_id"],
                "timeline": order["tracking"]
            },
            "message": "Order created successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@c2c_app.route('/medicine/user/<user_id>', methods=['GET'])
def get_user_orders(user_id):
    try:
        orders = list(medicine_orders_collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1))

        for o in orders:
            o["_id"] = str(o["_id"])

        return jsonify({
            "success": True,
            "data": orders,
            "message": "User orders fetched"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": str(e)
        }), 500

@c2c_app.route('/medicine/order/<order_id>', methods=['GET'])
def get_single_order(order_id):
    try:
        order = medicine_orders_collection.find_one({"_id": ObjectId(order_id)})

        if not order:
            return jsonify({
                "success": False,
                "data": {},
                "message": "Order not found"
            }), 404

        user=users_collection.find_one({"_id": ObjectId(order["user_id"])})
        order["_id"] = str(order["_id"])
        order["user_name"] = user["name"]

        return jsonify({
            "success": True,
            "data": order,
            "message": "Order fetched"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": {},
            "message": str(e)
        }), 500

@c2c_app.route('/medicine/admin/orders', methods=['GET'])
def get_all_orders():
    try:
        status = request.args.get("status")

        query = {}
        if status:
            query["status"] = status

        orders = list(medicine_orders_collection.find(query).sort("created_at", -1))

        for o in orders:
            o["_id"] = str(o["_id"])

        return jsonify({
            "success": True,
            "data": orders,
            "message": "All orders fetched"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": str(e)
        }), 500


@c2c_app.route('/medicine/update/<order_id>', methods=['POST'])
def update_medicine_order(order_id):
    try:
        data = request.json
        current_time = datetime.utcnow()

        order = medicine_orders_collection.find_one({
            "_id": ObjectId(order_id)
        })

        if not order:
            return jsonify({
                "success": False,
                "data": {},
                "message": "Order not found"
            }), 404

        update_data = {
            "updated_at": current_time
        }

        # optional fields
        allowed_fields = [
            "url",
            "store_id",
            "remark"
        ]

        for field in allowed_fields:
            if field in data:
                update_data[field] = data[field]

        # status update handling
        new_status = data.get("status")

        tracking_map = {
            "confirmed": "tracking.confirmed_at",
            "assigned": "tracking.assigned_at",
            "picked_up": "tracking.picked_up_at",
            "out_for_delivery": "tracking.out_for_delivery_at",
            "delivered": "tracking.delivered_at",
            "cancelled": "tracking.cancelled_at"
        }

        update_query = {
            "$set": update_data
        }

        # if status passed
        if new_status:

            valid_statuses = [
                "pending",
                "confirmed",
                "assigned",
                "picked_up",
                "out_for_delivery",
                "delivered",
                "cancelled"
            ]

            if new_status not in valid_statuses:
                return jsonify({
                    "success": False,
                    "message": "Invalid status"
                }), 400

            update_query["$set"]["status"] = new_status

            # tracking timestamp
            if new_status in tracking_map:
                update_query["$set"][tracking_map[new_status]] = current_time

            # push history
            update_query["$push"] = {
                "status_history": {
                    "status": new_status,
                    "updated_at": current_time,
                    "note": data.get("note", "")
                }
            }

        medicine_orders_collection.update_one(
            {"_id": ObjectId(order_id)},
            update_query
        )

        return jsonify({
            "success": True,
            "data": {},
            "message": "Medicine order updated successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": {},
            "message": str(e)
        }), 500
    
doctor_requests_collection=db["doctor_requests"]

@c2c_app.route('/doctor/request', methods=['POST'])
def create_doctor_request():
    try:
        data = request.json
        current_time = datetime.utcnow()

        doctor = {
            **data,
            "status": "pending",
            "role":"doctor",
            "review": {
                "approved_by": None,
                "approved_at": None,
                "rejected_reason": None
            },

            "created_at": current_time,
            "updated_at": current_time
        }

        result = doctor_requests_collection.insert_one(doctor)

        return jsonify({
            "success": True,
            "data": {
                "_id": str(result.inserted_id)
            },
            "message": "Doctor request submitted successfully"
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "data": {},
            "message": str(e)
        }), 500


def generate_doctor_secondary_id(doctor_name):
    # First letter of doctor's name
    name = (doctor_name or "").strip()

    if not name:
        raise ValueError("Doctor name is required")

    first_letter = name[0].upper()

    # Atomic counter: safe for simultaneous approval requests
    counter = doctor_counters.find_one_and_update(
        {"_id": "doctor_secondary_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER
    )

    # First generated number = 1001
    number = 1000 + counter["seq"]

    return f"{first_letter}{number}"


@c2c_app.route('/doctor/review/<doctor_id>', methods=['POST'])
def review_doctor(doctor_id):
    try:
        data = request.json
        status = data.get("status")  # approved / rejected
        admin_id = data.get("admin_id", '')
        reason = data.get("reason", "")

        if status not in ["approved", "rejected"]:
            return jsonify({
                "success": False,
                "message": "Invalid status"
            }), 400

        current_time = datetime.utcnow()

        # ✅ Get doctor request data first
        doctor_request = doctor_requests_collection.find_one({"_id": ObjectId(doctor_id)})

        if not doctor_request:
            return jsonify({
                "success": False,
                "message": "Doctor request not found"
            }), 404

        update_data = {
            "status": status,
            "updated_at": current_time,
            "review.approved_by": admin_id,
            "review.approved_at": current_time
        }

        if status == "rejected":
            update_data["review.rejected_reason"] = reason

        # ✅ Update request status
        doctor_requests_collection.update_one(
            {"_id": ObjectId(doctor_id)},
            {"$set": update_data}
        )

        # ✅ If approved → insert into doctors collection
        if status == "approved":
            # Remove Mongo _id to avoid duplication
            doctor_request.pop("_id", None)

            # Optional: clean / map fields if needed
            doctor_request["created_at"] = current_time
            doctor_request["status"] = "active"

            # doctors.insert_one(doctor_request)


            doctor_name = (
                doctor_request.get("name")
                or doctor_request.get("doctor_name")
                or ""
            ).strip()

            secondary_id = generate_doctor_secondary_id(doctor_name)

            doctor_request["secondaryId"] = secondary_id
            doctor_request["role"] = "doctor"
            doctor_request["status"] = "active"

            # Insert approved doctor into MongoDB
            result = doctors.insert_one(doctor_request)

            print("Doctor approved successfully")
            print("Secondary ID:", secondary_id)
            print("MongoDB ID:", str(result.inserted_id))


        return jsonify({
            "success": True,
            "message": f"Doctor {status} successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
@c2c_app.route('/doctor/requests', methods=['GET'])
def get_doctor_requests():
    try:
        status = request.args.get("status")

        query = {}
        if status:
            query["status"] = status

        doctors = list(doctor_requests_collection.find(query).sort("created_at", -1))

        for d in doctors:
            d["_id"] = str(d["_id"])

        return jsonify({
            "success": True,
            "data": doctors,
            "message": "Doctor requests fetched"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": str(e)
        }), 500




@c2c_app.route("/doctors/by-pincode", methods=["GET"])
def get_doctors_by_pincode():
    """
    GET /c2c_app/doctors/by-pincode?pincode=462016

    Returns active doctors matching the district/city of the PIN code.
    """

    try:
        # 1. Get and validate pincode
        pincode = request.args.get("pincode", "").strip()

        if not pincode:
            return jsonify({
                "success": False,
                "message": "Pincode is required"
            }), 400

        if not pincode.isdigit() or len(pincode) != 6:
            return jsonify({
                "success": False,
                "message": "Pincode must be a valid 6-digit number"
            }), 400

        # 2. Fetch PIN-code details with retries
        postal_url = f"https://api.postalpincode.in/pincode/{pincode}"

        postal_data = None
        last_error = None

        for attempt in range(3):
            try:
                response = requests.get(
                    postal_url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Accept": "application/json"
                    },
                    timeout=(5, 15)
                )

                response.raise_for_status()
                postal_data = response.json()
                break

            except (requests.RequestException, ValueError) as exc:
                last_error = str(exc)
                print(
                    f"Postal API attempt {attempt + 1}/3 failed: "
                    f"{last_error}"
                )

                if attempt < 2:
                    time.sleep(1)

        if postal_data is None:
            return jsonify({
                "success": False,
                "message": "Postal API is temporarily unavailable. Please try again.",
                "error": last_error
            }), 502

        # 3. Validate postal API response
        if (
            not isinstance(postal_data, list)
            or not postal_data
            or postal_data[0].get("Status") != "Success"
            or not postal_data[0].get("PostOffice")
        ):
            return jsonify({
                "success": False,
                "message": "Invalid pincode or location not found"
            }), 404

        # 4. Get district and state
        post_office = postal_data[0]["PostOffice"][0]

        district = (post_office.get("Block") or "").strip()
        state = (post_office.get("State") or "").strip()

        if not district:
            return jsonify({
                "success": False,
                "message": "District not found for this pincode"
            }), 404

        # 5. Search active doctors in MongoDB
        # Supports doctor names stored as either "name" or "doctor_name".
        doctor_query = {
            "clinicAddress.Block": {
                "$regex": "^" + re.escape(district) + "$",
                "$options": "i"
            },
            "role": "doctor",
            "status": "active"
        }

        doctor_cursor = doctors.find(
            doctor_query,
            {
                "_id": 1,
                "name": 1,
                "doctor_name": 1,
                "secondaryId": 1,
                "appointmentdatelimit": 1,
                "appointmentfee": 1,
                "specialization": 1
            }
        )

        # 6. Prepare response
        doctor_list = []

        for doctor in doctor_cursor:
            doctor_name = (
                doctor.get("doctor_name")
                or doctor.get("name")
                or "Unknown Doctor"
            )

            doctor_list.append({
                "mongoid": str(doctor["_id"]),
                "doctor_name": doctor_name,
                "secondaryId": doctor.get("secondaryId"),
                "appointmentdatelimit": doctor.get("appointmentdatelimit"),
                "appointmentfee": doctor.get("appointmentfee"),
                "specialization": doctor.get("specialization"),
            })

        return jsonify({
            "success": True,
            "message": "Doctors fetched successfully",
            "pincode": pincode,
            "city": district,
            "district": district,
            "state": state,
            "total": len(doctor_list),
            "data": doctor_list
        }), 200

    except Exception as exc:
        print(f"Error in get_doctors_by_pincode: {exc}")

        return jsonify({
            "success": False,
            "message": "Failed to fetch doctors",
            "error": str(exc)
        }), 500


@c2c_app.route("/doctors/by-secondary-id", methods=["GET"])
def get_doctor_by_secondary_id():
    try:
        secondary_id = request.args.get("secondaryId", "").strip().upper()

        if not secondary_id:
            return jsonify({
                "success": False,
                "message": "secondaryId is required"
            }), 400

        doctor = doctors.find_one(
            {"secondaryId": secondary_id},
            {"_id": 1, "secondaryId": 1, "name": 1, "doctor_name": 1,"appointmentdatelimit": 1, "appointmentfee": 1, "specialization": 1}
        )

        if not doctor:
            return jsonify({
                "success": False,
                "message": "Doctor not found"
            }), 404

        return jsonify({
            "success": True,
            "message": "Doctor fetched successfully",
            "data": {
                "mongoid": str(doctor["_id"]),
                "secondaryId": doctor.get("secondaryId"),
                "appointmentdatelimit": doctor.get("appointmentdatelimit"),
                "appointmentfee": doctor.get("appointmentfee"),
                "specialization": doctor.get("specialization"),
                "doctor_name": (
                    doctor.get("doctor_name")
                    or doctor.get("name")
                    or "Unknown Doctor"
                )
            }
        }), 200

    except Exception as e:
        print("Get doctor by secondaryId error:", str(e))
        return jsonify({
            "success": False,
            "message": "Failed to fetch doctor",
            "error": str(e)
        }), 500

    
@c2c_app.route('/doctors', methods=['GET'])
def get_doctors_list():
    try:
        status = request.args.get("status")

        query = {}
        if status:
            query["status"] = status

        doctor_list = list(doctors.find(query).sort("created_at", -1))

        for d in doctor_list:
            d["_id"] = str(d["_id"])

        return jsonify({
            "success": True,
            "data": doctor_list,
            "message": "Doctor requests fetched"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": str(e)
        }), 500

medical_requests_collection=db["medical_requests"]
hospital_requests_collection=db["hospital_requests"]
labs_requests_collection=db["labs_requests"]

@c2c_app.route('/labs/request', methods=['POST'])
def create_labs_request():
    try:
        data = request.json
        current_time = datetime.utcnow()

        labs = {
            **data,
            "status": "pending",

            "review": {
                "approved_by": None,
                "approved_at": None,
                "rejected_reason": None
            },

            "created_at": current_time,
            "updated_at": current_time
        }

        result = labs_requests_collection.insert_one(labs)

        return jsonify({
            "success": True,
            "data": {
                "_id": str(result.inserted_id)
            },
            "message": "labs request submitted successfully"
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "data": {},
            "message": str(e)
        }), 500


@c2c_app.route('/labs/review/<labs_id>', methods=['POST'])
def review_labs(labs_id):
    try:
        data = request.json
        status = data.get("status")  # approved / rejected
        admin_id = data.get("admin_id",'')
        reason = data.get("reason", "")

        if status not in ["approved", "rejected"]:
            return jsonify({
                "success": False,
                "message": "Invalid status"
            }), 400

        current_time = datetime.utcnow()

        update_data = {
            "status": status,
            "updated_at": current_time,
            "review.approved_by": admin_id,
            "review.approved_at": current_time
        }

        if status == "rejected":
            update_data["review.rejected_reason"] = reason

        labs_requests_collection.update_one(
            {"_id": ObjectId(labs_id)},
            {"$set": update_data}
        )

        return jsonify({
            "success": True,
            "message": f"labs {status} successfully"
        }), 200

    except Exception as e:
        print(str(e))
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@c2c_app.route('/labs/requests', methods=['GET'])
def get_labs_requests():
    try:
        status = request.args.get("status")
        query = {}
        if status:
            query["status"] = status

        labs = list(labs_requests_collection.find(query).sort("created_at", -1))

        for d in labs:
            d["_id"] = str(d["_id"])

        return jsonify({
            "success": True,
            "data": labs,
            "message": "labs requests fetched"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": str(e)
        }), 500
        
@c2c_app.route('/medical/request', methods=['POST'])
def create_medical_request():
    try:
        data = request.json
        current_time = datetime.utcnow()

        medical = {
            **data,
            "status": "pending",

            "review": {
                "approved_by": None,
                "approved_at": None,
                "rejected_reason": None
            },

            "created_at": current_time,
            "updated_at": current_time
        }

        result = medical_requests_collection.insert_one(medical)

        return jsonify({
            "success": True,
            "data": {
                "_id": str(result.inserted_id)
            },
            "message": "medical request submitted successfully"
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "data": {},
            "message": str(e)
        }), 500


@c2c_app.route('/medical/review/<medical_id>', methods=['POST'])
def review_medical(medical_id):
    try:
        data = request.json
        status = data.get("status")  # approved / rejected
        admin_id = data.get("admin_id",'')
        reason = data.get("reason", "")

        if status not in ["approved", "rejected"]:
            return jsonify({
                "success": False,
                "message": "Invalid status"
            }), 400

        current_time = datetime.utcnow()

        update_data = {
            "status": status,
            "updated_at": current_time,
            "review.approved_by": admin_id,
            "review.approved_at": current_time
        }

        if status == "rejected":
            update_data["review.rejected_reason"] = reason

        medical_requests_collection.update_one(
            {"_id": ObjectId(medical_id)},
            {"$set": update_data}
        )

        return jsonify({
            "success": True,
            "message": f"medical {status} successfully"
        }), 200

    except Exception as e:
        print(str(e))
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@c2c_app.route('/medical/requests', methods=['GET'])
def get_medical_requests():
    try:
        status = request.args.get("status")
        query = {}
        if status:
            query["status"] = status

        medicals = list(medical_requests_collection.find(query).sort("created_at", -1))

        for d in medicals:
            d["_id"] = str(d["_id"])

        return jsonify({
            "success": True,
            "data": medicals,
            "message": "medical requests fetched"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": str(e)
        }), 500

@c2c_app.route('/hospital/request', methods=['POST'])
def create_hospital_request():
    try:
        data = request.json
        current_time = datetime.utcnow()

        hospital = {
            **data,
            "status": "pending",
            "role":"hospital",

            "review": {
                "approved_by": None,
                "approved_at": None,
                "rejected_reason": None
            },

            "created_at": current_time,
            "updated_at": current_time
        }

        result = hospital_requests_collection.insert_one(hospital)

        return jsonify({
            "success": True,
            "data": {
                "_id": str(result.inserted_id)
            },
            "message": "hospital request submitted successfully"
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "data": {},
            "message": str(e)
        }), 500


@c2c_app.route('/hospital/review/<hospital_id>', methods=['POST'])
def review_hospital(hospital_id):
    try:
        data = request.json
        status = data.get("status")  # approved / rejected
        admin_id = data.get("admin_id", '')
        reason = data.get("reason", "")

        if status not in ["approved", "rejected"]:
            return jsonify({
                "success": False,
                "message": "Invalid status"
            }), 400

        current_time = datetime.utcnow()

        # ✅ Get hospital request data first
        hospital_request = hospital_requests_collection.find_one({"_id": ObjectId(hospital_id)})

        if not hospital_request:
            return jsonify({
                "success": False,
                "message": "hospital request not found"
            }), 404

        update_data = {
            "status": status,
            "updated_at": current_time,
            "review.approved_by": admin_id,
            "review.approved_at": current_time
        }

        if status == "rejected":
            update_data["review.rejected_reason"] = reason

        # ✅ Update request status
        hospital_requests_collection.update_one(
            {"_id": ObjectId(hospital_id)},
            {"$set": update_data}
        )

        # ✅ If approved → insert into hospitals collection
        if status == "approved":
            # Remove Mongo _id to avoid duplication
            hospital_request.pop("_id", None)

            # Optional: clean / map fields if needed
            hospital_request["created_at"] = current_time
            hospital_request["status"] = "active"

            doctors.insert_one(hospital_request)

        return jsonify({
            "success": True,
            "message": f"hospital {status} successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@c2c_app.route('/hospital/requests', methods=['GET'])
def get_hospital_requests():
    try:
        status = request.args.get("status")
        query = {}
        if status:
            query["status"] = status

        hospitals = list(hospital_requests_collection.find(query).sort("created_at", -1))

        for d in hospitals:
            d["_id"] = str(d["_id"])

        return jsonify({
            "success": True,
            "data": hospitals,
            "message": "hospital requests fetched"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": str(e)
        }), 500

from fpdf import FPDF

@c2c_app.route('/generate-receipt/<order_id>', methods=['GET'])
def generate_receipt(order_id):
    try:
        appoint_data = appointment.find_one({'_id': ObjectId(order_id)})

        if not appoint_data:
            return jsonify({"error": "Order not found"}), 404
        doctor_id = appoint_data.get('doctor_phone_id')
        print(doctor_id)
        doctor = doctors.find_one({"_id": ObjectId(doctor_id)})
       
        name = appoint_data.get('patient_name','xys')
        doctor_name = doctor.get('name','Kalra')
        doa = appoint_data.get('date_of_appointment', '2026-05-05')  # YYYY-MM-DD
        time = appoint_data.get('time_slot','11:00 AM')
        pay_id = str(appoint_data.get('pay_id',""))
        amount = str(appoint_data.get('amount','250'))
        trans_date = appoint_data.get('timestamp') or appoint_data.get('createdAt')
        formatted_date = trans_date.strftime('%d-%m-%Y')
        R_number = int(trans_date.timestamp())
        date_obj = datetime.strptime(doa, "%Y-%m-%d")
        dformatted_date = str(date_obj.strftime("%d-%m-%Y"))
        print(pay_id)

        # ---------------- PDF CLASS ---------------- #
        class PDF(FPDF):
            def header(self):
                self.set_fill_color(25, 42, 86)
                self.rect(0, 0, 210, 55, 'F')
                self.image("icon.png", 10, 10, 25)

                self.set_xy(40, 15)
                self.set_font("Arial", "B", 16)
                self.set_text_color(255, 255, 255)
                self.cell(0, 10, "", ln=True)

            def add_appointment_details(self):
                self.set_fill_color(25, 42, 86)
                self.set_text_color(255, 255, 255)
                self.set_font("Arial", "B", 18)
                self.cell(0, 10, "Care2Connect", ln=True, fill=True, align='C')

                self.set_font("Arial", "", 12)
                self.cell(0, 10, "Appointment Receipt", ln=True, fill=True, align='C')
                self.ln(10)

                self.set_text_color(0, 0, 0)

                self.cell(0, 10, f"Hello {name},", ln=True)
                self.ln(5)

                self.set_font("Arial", "B", 12)
                self.cell(50, 10, "Doctor:", 1)
                self.set_font("Arial", "", 12)
                self.cell(0, 10, doctor_name, 1, ln=True)

                self.cell(50, 10, "Date:", 1)
                self.cell(0, 10, dformatted_date, 1, ln=True)

                self.cell(50, 10, "Time:", 1)
                self.cell(0, 10, time, 1, ln=True)

                self.cell(50, 10, "Transaction Date:", 1)
                self.cell(0, 10, formatted_date, 1, ln=True)

                self.cell(50, 10, "Amount:", 1)
                self.cell(0, 10, amount + "/-", 1, ln=True)

                self.cell(50, 10, "Transaction ID:", 1)
                self.cell(0, 10, pay_id, 1, ln=True)

                self.cell(50, 10, "Receipt No:", 1)
                self.cell(0, 10, "A" + str(R_number), 1, ln=True)

                self.ln(10)
                self.multi_cell(0, 10, "This is a computer generated receipt.")

        # ---------------- GENERATE PDF ---------------- #
        pdf = PDF()
        pdf.add_page()
        pdf.add_appointment_details()

        file_path = f"receipt.pdf"
        pdf.output(file_path)

        # ---------------- RETURN FILE ---------------- #
        return send_file(
            file_path,
            as_attachment=True,
            download_name="receipt.pdf",
            mimetype='application/pdf'
        )

    except Exception as e:
        print(str(e))
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@c2c_app.route('/recent_activity/<user_id>/<number>', methods=['GET'])
def Recent_activity(user_id,number):
    try:
        resp, _ = get_appointments(number)
        appointment = resp.get_json().get("data", [])

        resp2, _ = get_user_orders(user_id)
        medicine = resp2.get_json().get("data", [])

        activities = []

        # Appointments
        for a in appointment:
            activities.append({
                "id": a.get('id'),
                "type": "appointment",
                "sub": f"{a.get("status")} • {a.get("date")}",
                "slot":a.get("time"),
                "title": a.get('doctorName', ''),
                "createdAt": a.get("createdAt"),
                "image":a.get('doctorPic')
            })

        # Orders
        for m in medicine:
            activities.append({
                "id": m.get('_id'),
                "type": "order",
                "sub": f"Status:{m.get("status")}",
                "title": f"Order #{m.get('order_id', '')}",
                "createdAt": m.get("updated_at"),
            })

        # Sort latest first
        activities = sorted(activities, key=lambda x: x["createdAt"], reverse=True)

        # Limit
        activities = activities[:int(5)]

        return jsonify({
            "success": True,
            "data": activities,
            "message": "Recent activity fetched"
        }), 200

    except Exception as e:
        print(str(e))
        return jsonify({
            "success": False,
            "data": [],
            "message": str(e)
        }), 500

@c2c_app.route("/api/patients", methods=["GET"])
def get_patients_search():
    try:
        search = request.args.get("search", "")

        results = list(
            appointment.aggregate([
                # Search using whatsapp number
                {
                    "$match": {
                        "whatsapp_number": {
                            "$regex": search,
                            "$options": "i"
                        }
                    }
                },

                # Latest records first
                {
                    "$sort": {
                        "appointment_date": -1,
                        "_id": -1
                    }
                },

                # Unique patient by patient_name
                {
                    "$group": {
                        "_id": {
                            "patient_name": {
                                "$toLower": "$patient_name"
                            }
                        },

                        "patient_name": {
                            "$first": "$patient_name"
                        },
                        "guardian_name": {
                            "$first": "$guardian_name"
                        },
                        "date_of_birth": {
                            "$first": "$date_of_birth"
                        },
                        "sex": {
                            "$first": "$sex"
                        },
                        "whatsapp_number": {
                            "$first": "$whatsapp_number"
                        },

                        # Count appointments of same patient
                        "appointment_count": {
                            "$sum": 1
                        },

                        "last_appointment_date": {
                            "$first": "$date_of_appointment"
                        }
                    }
                },

                # Final fields
                {
                    "$project": {
                        "_id": 0,
                        "patient_name": 1,
                        "guardian_name": 1,
                        "date_of_birth": 1,
                        "sex": 1,
                        "whatsapp_number": 1,
                        "appointment_count": 1,
                        "last_appointment_date": 1
                    }
                },

                # {
                #     "$limit": 10
                # }
            ])
        )

        return jsonify({
            "success": True,
            "data": results,
            "message": "Patients fetched successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "data": [],
            "message": str(e)
        }), 500
    
@c2c_app.route('/medicine_order')
def order_page():
    return render_template('medical.html')

@c2c_app.route('/payment-success')
def pyament_success():
    return render_template('cashfree_redirect.html')

def serialize_banner(banner):
    return {
        "_id": str(banner["_id"]),
        "title": banner.get("title"),
        "image_url": banner.get("image_url"),
        "createdAt": banner.get("createdAt")
    }

# =========================
# CREATE BANNER
# =========================
@c2c_app.route("/create-banner", methods=["POST"])
def create_banner():

    try:

        data = request.json

        title = data.get("title")
        image_url = data.get("image_url")

        if not image_url:
            return jsonify({
                "success": False,
                "message": "Image URL is required"
            }), 400

        banner_data = {
            "title": title,
            "image_url": image_url,
            "createdAt": datetime.utcnow()
        }

        result = db.banners.insert_one(banner_data)

        banner_data["_id"] = str(result.inserted_id)

        return jsonify({
            "success": True,
            "message": "Banner created successfully",
            "data": banner_data
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================
# GET ALL BANNERS
# =========================
@c2c_app.route("/get-banners", methods=["GET"])
def get_banners():

    try:

        banner_list = list(
            db.banners.find().sort("createdAt", -1)
        )

        return jsonify({
            "success": True,
            "data": [serialize_banner(b) for b in banner_list]
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================
# DELETE BANNER
# =========================
@c2c_app.route("/delete-banner/<banner_id>", methods=["POST"])
def delete_banner(banner_id):

    try:

        banner = db.banners.find_one({
            "_id": ObjectId(banner_id)
        })

        if not banner:
            return jsonify({
                "success": False,
                "message": "Banner not found"
            }), 404

        db.banners.delete_one({
            "_id": ObjectId(banner_id)
        })

        return jsonify({
            "success": True,
            "message": "Banner deleted successfully"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500



# =========================================================
# SERIALIZERS
# =========================================================

def serialize_lab_test(test):

    return {
        "_id": str(test["_id"]),
        "test_name": test.get("test_name"),
        "description": test.get("description"),
        "price": test.get("price"),
        "discounted_price": test.get("discounted_price"),
        "report_time": test.get("report_time"),
        "preparation": test.get("preparation"),
        "category": test.get("category"),
        "image_url": test.get("image_url"),
        "available": test.get("available"),
        "home_collection": test.get("home_collection"),
        "parameters": test.get("parameters", []),
        "createdAt": test.get("createdAt")
    }


def serialize_booking(booking):

    return {
        "_id": str(booking["_id"]),
        "patient_id": booking.get("patient_id"),
        "tests": booking.get("tests"),
        "total_amount": booking.get("total_amount"),
        "address": booking.get("address"),
        "slot": booking.get("slot"),
        "payment_status": booking.get("payment_status"),
        "booking_status": booking.get("booking_status"),
        "sample_collection_type": booking.get("sample_collection_type"),
        "createdAt": booking.get("createdAt")
    }


# =========================================================
# CREATE LAB TEST
# =========================================================

@c2c_app.route("/create-lab-test", methods=["POST"])
def create_lab_test():

    try:

        data = request.json

        lab_test_data = {
            "test_name": data.get("test_name"),
            "description": data.get("description"),
            "price": data.get("price"),
            "discounted_price": data.get("discounted_price"),
            "report_time": data.get("report_time"),
            "preparation": data.get("preparation"),
            "category": data.get("category"),
            "image_url": data.get("image_url"),
            "available": data.get("available", True),
            "home_collection": data.get("home_collection", True),
            "parameters": data.get("parameters", []),
            "createdAt": datetime.utcnow()
        }

        result = db.lab_tests.insert_one(lab_test_data)

        lab_test_data["_id"] = str(result.inserted_id)

        return jsonify({
            "success": True,
            "message": "Lab test created successfully",
            "data": lab_test_data
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# GET ALL LAB TESTS
# =========================================================

@c2c_app.route("/get-lab-tests", methods=["GET"])
def get_lab_tests():

    try:

        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
        search = request.args.get("search", "")
        category = request.args.get("category")

        skip = (page - 1) * limit

        query = {}

        if search:
            query["test_name"] = {
                "$regex": search,
                "$options": "i"
            }

        if category:
            query["category"] = category

        tests = list(
            db.lab_tests.find(query)
            .sort("createdAt", -1)
            .skip(skip)
            .limit(limit)
        )

        total = db.lab_tests.count_documents(query)

        return jsonify({
            "success": True,
            "total": total,
            "page": page,
            "limit": limit,
            "data": [serialize_lab_test(test) for test in tests]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# GET SINGLE LAB TEST
# =========================================================

@c2c_app.route("/get-lab-test/<test_id>", methods=["GET"])
def get_lab_test(test_id):

    try:

        test = db.lab_tests.find_one({
            "_id": ObjectId(test_id)
        })

        if not test:

            return jsonify({
                "success": False,
                "message": "Lab test not found"
            }), 404

        return jsonify({
            "success": True,
            "data": serialize_lab_test(test)
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# UPDATE LAB TEST
# =========================================================

@c2c_app.route("/update-lab-test/<test_id>", methods=["POST"])
def update_lab_test(test_id):

    try:

        data = request.json

        update_data = {
            "test_name": data.get("test_name"),
            "description": data.get("description"),
            "price": data.get("price"),
            "discounted_price": data.get("discounted_price"),
            "report_time": data.get("report_time"),
            "preparation": data.get("preparation"),
            "category": data.get("category"),
            "image_url": data.get("image_url"),
            "available": data.get("available"),
            "home_collection": data.get("home_collection"),
            "parameters": data.get("parameters")
        }

        update_data = {
            k: v for k, v in update_data.items()
            if v is not None
        }

        result = db.lab_tests.update_one(
            {"_id": ObjectId(test_id)},
            {"$set": update_data}
        )

        if result.matched_count == 0:

            return jsonify({
                "success": False,
                "message": "Lab test not found"
            }), 404

        updated_test = db.lab_tests.find_one({
            "_id": ObjectId(test_id)
        })

        return jsonify({
            "success": True,
            "message": "Lab test updated successfully",
            "data": serialize_lab_test(updated_test)
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# DELETE LAB TEST
# =========================================================

@c2c_app.route("/delete-lab-test/<test_id>", methods=["POST"])
def delete_lab_test(test_id):

    try:

        result = db.lab_tests.delete_one({
            "_id": ObjectId(test_id)
        })

        if result.deleted_count == 0:

            return jsonify({
                "success": False,
                "message": "Lab test not found"
            }), 404

        return jsonify({
            "success": True,
            "message": "Lab test deleted successfully"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# TOGGLE LAB TEST AVAILABILITY
# =========================================================

@c2c_app.route("/toggle-lab-test/<test_id>", methods=["POST"])
def toggle_lab_test(test_id):

    try:

        data = request.json

        available = data.get("available")

        result = db.lab_tests.update_one(
            {"_id": ObjectId(test_id)},
            {
                "$set": {
                    "available": available
                }
            }
        )

        if result.matched_count == 0:

            return jsonify({
                "success": False,
                "message": "Lab test not found"
            }), 404

        return jsonify({
            "success": True,
            "message": "Availability updated successfully"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# GET LAB TEST CATEGORIES
# =========================================================

@c2c_app.route("/get-lab-test-categories", methods=["GET"])
def get_lab_test_categories():

    try:

        categories = db.lab_tests.distinct("category")

        return jsonify({
            "success": True,
            "data": categories
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# BOOK LAB TEST
# =========================================================

@c2c_app.route("/book-lab-test", methods=["POST"])
def book_lab_test():

    try:

        data = request.json

        booking_data = {
            "patient_id": data.get("patient_id"),
            "tests": data.get("tests", []),
            "total_amount": data.get("total_amount"),
            "address": data.get("address"),
            "slot": data.get("slot"),
            "payment_status": data.get("payment_status", "PENDING"),
            "booking_status": data.get("booking_status", "Pending"),
            "sample_collection_type": data.get(
                "sample_collection_type",
                "HOME"
            ),
            "createdAt": datetime.utcnow()
        }

        result = db.lab_test_bookings.insert_one(booking_data)

        booking_data["_id"] = str(result.inserted_id)

        return jsonify({
            "success": True,
            "message": "Lab test booked successfully",
            "data": booking_data
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# GET PATIENT BOOKINGS
# =========================================================

@c2c_app.route(
    "/get-patient-lab-bookings/<patient_id>",
    methods=["GET"]
)
def get_patient_lab_bookings(patient_id):

    try:

        bookings = list(
            db.lab_test_bookings.find({
                "patient_id": patient_id
            }).sort("createdAt", -1)
        )

        return jsonify({
            "success": True,
            "data": [
                serialize_booking(booking)
                for booking in bookings
            ]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# =========================================================
# UPDATE BOOKING STATUS
# =========================================================

@c2c_app.route(
    "/update-lab-booking-status/<booking_id>",
    methods=["POST"]
)
def update_lab_booking_status(booking_id):

    try:

        data = request.json

        booking_status = data.get("booking_status")

        payment_status = data.get("payment_status")

        update_data = {}

        if booking_status:
            update_data["booking_status"] = booking_status

        if payment_status:
            update_data["payment_status"] = payment_status

        result = db.lab_test_bookings.update_one(
            {"_id": ObjectId(booking_id)},
            {"$set": update_data}
        )

        if result.matched_count == 0:

            return jsonify({
                "success": False,
                "message": "Booking not found"
            }), 404

        return jsonify({
            "success": True,
            "message": "Booking status updated successfully"
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
@c2c_app.route("/track-event", methods=["POST"])
def track_event():

    try:

        data = request.json

        db.activity_logs.insert_one(data)

        return {
            "success": True
        }

    except Exception as e:

        return {
            "success": False
        }
        

@c2c_app.route("/track-batch", methods=["POST"])
def track_batch():

    try:

        data = request.json

        events = data.get("events", [])

        if len(events) > 0:

            db.activity_logs.insert_many(events)

        return {
            "success": True
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }



@c2c_app.route("/activities", methods=["GET"])
def get_activities():

    try:

        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 50))

        skip = (page - 1) * limit

        data = list(
            db.activity_logs.find()
            .sort("createdAt", -1)
            .skip(skip)
            .limit(limit)
        )

        for item in data:
            item["_id"] = str(item["_id"])

        return {
            "success": True,
            "data": data
        }

    except Exception as e:

        return {
            "success": False,
            "message": str(e)
        }

@c2c_app.route("/save-fcm-token", methods=["POST"])
def save_fcm_token():

    try:
        data = request.get_json()

        fcm_token = data.get("fcm_token")

        device = data.get("device", "android")

        if not fcm_token:

            return jsonify({
                "success": False,
                "message": "FCM token is required"
            }), 400

        user_id = data.get("user_id")
        user = users_collection.find_one({
            "_id": ObjectId(user_id)
        })
        if not user:

            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404

        existing_tokens = user.get("fcm_tokens", [])

        token_exists = False

        updated_tokens = []

        for item in existing_tokens:

            if item.get("token") == fcm_token:

                token_exists = True

                item["updated_at"] = datetime.utcnow()

            updated_tokens.append(item)

        if not token_exists:

            updated_tokens.append({
                "token": fcm_token,
                "device": device,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })

        users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "fcm_tokens": updated_tokens
                }
            }
        )

        return jsonify({
            "success": True,
            "message": "FCM token saved successfully"
        }), 200

    except Exception as e:

        print("SAVE FCM TOKEN ERROR:", str(e))

        return jsonify({
            "success": False,
            "message": "Internal server error",
            "error": str(e)
        }), 500
    
@c2c_app.route(
    "/send-notification",
    methods=["POST"]
)
def send_notification():

    try:

        data = request.get_json()

        user_id = data.get("user_id")

        title = data.get("title")

        body = data.get("body")

        extra_data = data.get("data", {})

        if not all([user_id, title, body]):

            return jsonify({
                "success": False,
                "message":
                "user_id, title and body required"
            }), 400

        user = users_collection.find_one({
            "_id": ObjectId(user_id)
        })

        if not user:

            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404

        tokens = user.get("fcm_tokens", [])

        if not tokens:

            return jsonify({
                "success": False,
                "message":
                "No FCM tokens found"
            }), 404

        results = []

        for item in tokens:

            token = item.get("token")

            result = send_push_notification(
                token=token,
                title=title,
                body=body,
                data=extra_data
            )

            results.append(result)

        return jsonify({
            "success": True,
            "message":
            "Notification sent successfully",
            "results": results
        }), 200

    except Exception as e:

        print("SEND NOTIFICATION ERROR:",
              str(e))

        return jsonify({
            "success": False,
            "message": "Internal server error",
            "error": str(e)
        }), 500
    
@c2c_app.route(
    "/send-bulk-notification",
    methods=["POST"]
)
def send_bulk_notification():

    try:

        data = request.get_json()

        user_ids = data.get("user_ids", [])

        title = data.get("title")

        body = data.get("body")

        extra_data = data.get("data", {})

        if not user_ids:

            return jsonify({
                "success": False,
                "message":
                "user_ids required"
            }), 400

        tokens = []

        for user_id in user_ids:

            user = users_collection.find_one({
                "_id": ObjectId(user_id)
            })

            if user:

                for item in user.get(
                    "fcm_tokens",
                    []
                ):

                    token = item.get("token")

                    if token:

                        tokens.append(token)

        tokens = list(set(tokens))

        if not tokens:

            return jsonify({
                "success": False,
                "message":
                "No valid tokens found"
            }), 404

        result = send_bulk_notifications(
            tokens=tokens,
            title=title,
            body=body,
            data=extra_data
        )

        return jsonify({
            "success": True,
            "result": result
        }), 200

    except Exception as e:

        print(
            "BULK NOTIFICATION ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message":
            "Internal server error",
            "error": str(e)
        }), 500




# from decimal import Decimal, InvalidOperation
# @c2c_app.route("/api/create-payment-link", methods=["POST"])
# def create_payment_link():
#     try:
#         data = request.get_json(silent=True) or {}

#         amount = data.get("amount")
#         name = data.get("name")
#         mobile = data.get("mobile")
#         email = data.get("email")
#         description = data.get("description", "Online Payment")
#         reference_id = data.get("reference_id")

#         # Required fields validation
#         if amount is None or not name or not mobile:
#             return jsonify({
#                 "success": False,
#                 "message": "amount, name and mobile are required"
#             }), 400

#         # Convert rupees into paise safely
#         try:
#             amount_rupees = Decimal(str(amount))
#             if not amount_rupees.is_finite() or amount_rupees <= 0:
#                 raise ValueError("Invalid amount")

#             amount_paise = amount_rupees * 100

#             if amount_paise != amount_paise.to_integral_value():
#                 raise ValueError("Amount must have at most 2 decimals")

#             amount_paise = int(amount_paise)

#         except (InvalidOperation, ValueError):
#             return jsonify({
#                 "success": False,
#                 "message": "Enter a valid amount in rupees"
#             }), 400

#         payload = {
#             "amount": amount_paise,
#             "currency": "INR",
#             "accept_partial": False,
#             "description": str(description)[:2048],
#             "customer": {
#                 "name": str(name),
#                 "contact": str(mobile)
#             },
#             "notify": {
#                 "sms": False,
#                 "email": False
#             },
#             "reminder_enable": False
#         }

#         if email:
#             payload["customer"]["email"] = str(email)

#         if reference_id:
#             reference_id = str(reference_id)
#             if len(reference_id) > 40:
#                 return jsonify({
#                     "success": False,
#                     "message": "reference_id must be at most 40 characters"
#                 }), 400
#             payload["reference_id"] = reference_id

#         payment_link = client.payment_link.create(payload)


#         # appointment generate 


#         dataset = {
#                         'kalra_id': 'xx',
#                         'appointmenttype': 'current',
        
#                         'agent_id': data.get("agent_id", "User"),
        
#                         'patient_name': data.get("patient_name", "User"),
#                         'guardian_name': data.get("father_name", "User"),
#                         'date_of_appointment': data.get("date", "User"),
#                         'time_slot': data.get("time", "User"),
        
#                         'doctor_phone_id': data.get("doctor_id", "User"),
#                         'email': data.get("email", "User"),
#                         'symptoms': data.get("symptoms", "User"),
#                         'age': data.get("age", "User"),
#                         'timestamp': data.get("timestamp", "User"),
        
#                         'whatsapp_number': from_number,
#                         'date_of_birth': data.get("dob", "User"),
#                         'city': data.get("city", "none"),
#                         'state': data.get("state", "none"),
#                         'pincode': data.get("pincode", "none"),
#                         'address': data.get("address", "none"), 
        
#                         'role': 'appointment',
#                         'status': 'created',
#                         "createdAt": datetime.utcnow(),
        
#                         "sex": data.get("sex", "User"),
#                         "vaccine": "No",
        
#                         'razorpay_url': link_url,
#                         'payment_status': 'link generated',
#                         'itype':'test'
#                     }
        
#         inserted_id = str(appointment.insert_one(dataset).inserted_id)

#         return jsonify({
#             "success": True,
#             "message": "Payment link created successfully",
#             "payment_link_id": payment_link["id"],
#             "payment_url": payment_link["short_url"],
#             "amount": float(amount_rupees),
#             "currency": payment_link["currency"],
#             "status": payment_link["status"]
#         }), 201

#     except Exception:
#         app.logger.exception("Razorpay payment link creation failed")
#         return jsonify({
#             "success": False,
#             "message": "Unable to create payment link"
#         }), 502





from decimal import Decimal, InvalidOperation
@c2c_app.route("/api/create-payment-link", methods=["POST"])
def create_payment_link():
    try:
        data = request.get_json(silent=True) or {}

        amount = data.get("amount")
        name = data.get("name") or data.get("patient_name")
        mobile = str(data.get("mobile") or data.get("whatsapp_number") or "").strip()
        email = data.get("email")
        description = data.get("description") or "Appointment Payment"
        reference_id = data.get("reference_id")

        # 1. Validate required fields
        if amount is None or not name or not mobile:
            return jsonify({
                "success": False,
                "message": "amount, name/patient_name and mobile/whatsapp_number are required"
            }), 400

        # 2. Validate amount and convert INR to paise
        try:
            amount_rupees = Decimal(str(amount))

            if not amount_rupees.is_finite() or amount_rupees <= 0:
                raise ValueError()

            amount_paise = amount_rupees * 100

            if amount_paise != amount_paise.to_integral_value():
                return jsonify({
                    "success": False,
                    "message": "Amount must have at most 2 decimal places"
                }), 400

            amount_paise = int(amount_paise)

        except (InvalidOperation, ValueError, TypeError):
            return jsonify({
                "success": False,
                "message": "Enter a valid amount in rupees"
            }), 400

        # 3. Normalize mobile number
        if not mobile.isdigit() or len(mobile) not in (10, 12):
            return jsonify({
                "success": False,
                "message": "Enter a valid 10-digit mobile number or 12-digit number with country code"
            }), 400

        if len(mobile) == 10:
            from_number = "91" + mobile
        elif mobile.startswith("91"):
            from_number = mobile
        else:
            return jsonify({
                "success": False,
                "message": "Only Indian mobile numbers are supported"
            }), 400

        # 4. Validate reference ID
        if reference_id is not None:
            reference_id = str(reference_id).strip()

            if not reference_id or len(reference_id) > 40:
                return jsonify({
                    "success": False,
                    "message": "reference_id must contain 1-40 characters"
                }), 400

        # 5. Create Razorpay payment link
        payload = {
            "amount": amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "description": str(description)[:2048],
            "customer": {
                "name": str(name).strip(),
                "contact": from_number
            },
            "notify": {
                "sms": False,
                "email": False
            },
            "reminder_enable": False
        }

        if email:
            payload["customer"]["email"] = str(email).strip()

        if reference_id:
            payload["reference_id"] = reference_id

        # IMPORTANT: use the Razorpay client, not the MongoDB client.
        payment_link = razorpay_client.payment_link.create(payload)

        link_url = payment_link.get("short_url")
        payment_link_id = payment_link.get("id")

        if not link_url or not payment_link_id:
            app.logger.error("Razorpay response missing payment link ID or URL")
            return jsonify({
                "success": False,
                "message": "Payment link was not returned by Razorpay"
            }), 502

        # 6. Create appointment record
        now = datetime.utcnow()

        dataset = {
            "appointment_id": str(uuid.uuid4()),
            "kalra_id": "xx",
            "appointmenttype": "current",

            "agent_id": str(data.get("agent_id") or "User"),

            "patient_name": str(
                data.get("patient_name") or name
            ).strip(),
            "guardian_name": data.get("father_name")
                or data.get("guardian_name", ""),
            "date_of_appointment": data.get("date", ""),
            "time_slot": data.get("time", ""),

            "doctor_phone_id": str(data.get("doctor_id") or ""),
            "email": email or "",
            "symptoms": data.get("symptoms", ""),
            "age": data.get("age", ""),
            "timestamp": data.get("timestamp"),

            "whatsapp_number": from_number,
            "date_of_birth": data.get("dob")
                or data.get("date_of_birth", ""),
            "city": data.get("city", ""),
            "state": data.get("state", ""),
            "pincode": data.get("pincode", ""),
            "address": data.get("address", ""),

            "sex": data.get("sex", ""),
            "vaccine": "No",

            "role": "appointment",
            "status": "created",
            "payment_status": "link generated",
            "payment_required": True,

            # "amount": float(amount_rupees),
            "currency": "INR",

            "razorpay_url": payment_link_id,
            "payment_link": link_url,
            "payment_link_id": payment_link_id,

            "reference_id": reference_id,
            "createdAt": now,
            "itype": "test"
        }

        result = appointment.insert_one(dataset)

        # 7. Return response
        return jsonify({
            "success": True,
            "message": "Payment link and appointment created successfully",
            "appointment_id": str(result.inserted_id),
            "appointment_reference": dataset["appointment_id"],
            "agent_id": dataset["agent_id"],
            "payment_link_id": payment_link_id,
            "payment_url": link_url,
            "amount": float(amount_rupees),
            "amount_paise": amount_paise,
            "currency": payment_link.get("currency", "INR"),
            "payment_status": "link generated",
            "status": "created"
        }), 201

    except Exception:
        return jsonify({
            "success": False,
            "message": "Unable to create payment link or save appointment"
        }), 500




shifts = db["shifts"]

@c2c_app.route("/create_shift", methods=["POST"])
def create_shift():
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return jsonify({
                "success": False,
                "error": "Valid JSON body is required"
            }), 400

        required_fields = [
            "doctor_id",
            "shift_name",
            "start_time",
            "end_time"
        ]

        missing_fields = [
            field for field in required_fields
            if not data.get(field)
        ]

        if missing_fields:
            return jsonify({
                "success": False,
                "error": "Required fields missing",
                "fields": missing_fields
            }), 400

        shift = {
            "doctor_id": str(data["doctor_id"]).strip(),
            "shift_name": data["shift_name"].strip(),
            "start_time": data["start_time"],
            "end_time": data["end_time"],
            "description": data.get("description", ""),
            "status": data.get("status", "active"),
            "created_at": datetime.utcnow()
        }

        result = shifts.insert_one(shift)

        return jsonify({
            "success": True,
            "message": "Shift created successfully",
            "shift_id": str(result.inserted_id)
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@c2c_app.route("/get_shifts/<string:doctor_id>", methods=["GET"])
def get_shifts_by_doctor(doctor_id):
    try:
        data = list(
            shifts.find({"doctor_id": doctor_id}).sort("created_at", -1)
        )

        for shift in data:
            shift["_id"] = str(shift["_id"])

        return jsonify({
            "success": True,
            "doctor_id": doctor_id,
            "count": len(data),
            "shifts": data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@c2c_app.route("/delete_shift/<string:id>", methods=["DELETE"])
def delete_shift(id):
    try:
        if not ObjectId.is_valid(id):
            return jsonify({
                "success": False,
                "error": "Invalid Shift ID"
            }), 400

        result = shifts.delete_one({
            "_id": ObjectId(id)
        })

        if result.deleted_count == 0:
            return jsonify({
                "success": False,
                "error": "Shift not found"
            }), 404

        return jsonify({
            "success": True,
            "message": "Shift deleted successfully"
        }), 200

    except PyMongoError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@c2c_app.route("/update_shift/<string:id>", methods=["PUT"])
def update_shift(id):
    try:
        if not ObjectId.is_valid(id):
            return jsonify({
                "success": False,
                "error": "Invalid Shift ID"
            }), 400

        data = request.get_json(silent=True)

        if not isinstance(data, dict) or not data:
            return jsonify({
                "success": False,
                "error": "Valid JSON body is required"
            }), 400

        allowed_fields = [
            "shift_name",
            "start_time",
            "end_time",
            "description",
            "status"
        ]

        update_data = {
            key: value
            for key, value in data.items()
            if key in allowed_fields
        }

        if not update_data:
            return jsonify({
                "success": False,
                "error": "No valid fields provided for update"
            }), 400

        if "shift_name" in update_data:
            if not isinstance(update_data["shift_name"], str) or not update_data["shift_name"].strip():
                return jsonify({
                    "success": False,
                    "error": "shift_name must be a non-empty string"
                }), 400
            update_data["shift_name"] = update_data["shift_name"].strip()

        result = shifts.update_one(
            {"_id": ObjectId(id)},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            return jsonify({
                "success": False,
                "error": "Shift not found"
            }), 404

        return jsonify({
            "success": True,
            "message": (
                "Shift updated successfully"
                if result.modified_count
                else "No changes made"
            )
        }), 200

    except PyMongoError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500



# attendance_routes.py



# attendance_routes.py

from pymongo import ASCENDING, DESCENDING


IST = ZoneInfo("Asia/Kolkata")

attendance = db["attendance"]
leave_requests = db["leave_requests"]


# --------------------------------------------------
# DATABASE INDEXES
# --------------------------------------------------

# One attendance record per staff per doctor per day.
# Remove any existing duplicate records before creating
# this unique index on a database with existing data.
attendance.create_index(
    [
        ("doctor_id", ASCENDING),
        ("staff_id", ASCENDING),
        ("date", ASCENDING)
    ],
    unique=True
)

attendance.create_index(
    [("doctor_id", ASCENDING), ("date", DESCENDING)]
)

leave_requests.create_index(
    [
        ("doctor_id", ASCENDING),
        ("staff_id", ASCENDING),
        ("start_date", ASCENDING)
    ]
)


# --------------------------------------------------
# COMMON HELPERS
# --------------------------------------------------

def now_ist():
    return datetime.now(IST)


def serialize(record):
    if record:
        record["_id"] = str(record["_id"])
    return record


def validate_date(value):
    return date.fromisoformat(value).isoformat()


def get_staff(doctor_id, staff_id):
    """Find staff in the existing doctors collection."""
    if not ObjectId.is_valid(staff_id):
        return None

    return doctors.find_one({
        "_id": ObjectId(staff_id),
        "role": "staff",
        "doctorId": doctor_id
    })


def get_staff_name(staff):
    return (
        staff.get("name")
        or staff.get("doctor_name")
        or staff.get("staff_name")
        or staff.get("FirstName")
        or ""
    )


def calculate_working_hours(check_in, check_out):
    if not check_in or not check_out:
        return None

    start = datetime.fromisoformat(check_in)
    end = datetime.fromisoformat(check_out)

    seconds = max(0, (end - start).total_seconds())
    return round(seconds / 3600, 2)


def attendance_response(record):
    record = serialize(record)

    record["working_hours"] = calculate_working_hours(
        record.get("check_in"),
        record.get("check_out")
    )

    return record


# --------------------------------------------------
# 1. STAFF CHECK-IN
# POST /attendance/check-in
# --------------------------------------------------

@c2c_app.route("/attendance/check-in", methods=["POST"])
def check_in():
    try:
        data = request.get_json(silent=True) or {}

        doctor_id = str(data.get("doctor_id", "")).strip()
        staff_id = str(data.get("staff_id", "")).strip()

        if not doctor_id or not staff_id:
            return jsonify({
                "success": False,
                "message": "doctor_id and staff_id are required"
            }), 400

        staff = get_staff(doctor_id, staff_id)

        if not staff:
            return jsonify({
                "success": False,
                "message": "Staff not found for this doctor"
            }), 404

        current = now_ist()
        today = current.date().isoformat()

        # Prevent another check-in for the same day.
        existing = attendance.find_one({
            "doctor_id": doctor_id,
            "staff_id": staff_id,
            "date": today
        })

        if existing:
            return jsonify({
                "success": False,
                "message": (
                    "Attendance already exists for today"
                    if existing.get("check_out")
                    else "You have already checked in today"
                ),
                "data": attendance_response(existing)
            }), 409

        record = {
            "doctor_id": doctor_id,
            "staff_id": staff_id,
            "staff_name": get_staff_name(staff),
            "date": today,
            "check_in": current.isoformat(),
            "check_out": None,
            "status": "present",
            "remarks": str(data.get("remarks", "")).strip(),
            "created_at": current.isoformat(),
            "updated_at": current.isoformat()
        }

        result = attendance.insert_one(record)
        record["_id"] = result.inserted_id

        return jsonify({
            "success": True,
            "message": "Check-in successful",
            "data": attendance_response(record)
        }), 201

    except DuplicateKeyError:
        return jsonify({
            "success": False,
            "message": "Attendance already exists for today"
        }), 409

    except PyMongoError as e:
        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# --------------------------------------------------
# 2. STAFF CHECK-OUT
# PUT /attendance/check-out/<attendance_id>
# --------------------------------------------------

@c2c_app.route(
    "/attendance/check-out/<string:attendance_id>",
    methods=["PUT"]
)
def check_out(attendance_id):
    try:
        if not ObjectId.is_valid(attendance_id):
            return jsonify({
                "success": False,
                "message": "Invalid attendance_id"
            }), 400

        current = now_ist()

        result = attendance.update_one(
            {
                "_id": ObjectId(attendance_id),
                "check_out": None
            },
            {
                "$set": {
                    "check_out": current.isoformat(),
                    "updated_at": current.isoformat()
                }
            }
        )

        if result.matched_count == 0:
            existing = attendance.find_one({
                "_id": ObjectId(attendance_id)
            })

            if not existing:
                return jsonify({
                    "success": False,
                    "message": "Attendance record not found"
                }), 404

            return jsonify({
                "success": False,
                "message": "Check-out already completed"
            }), 409

        record = attendance.find_one({
            "_id": ObjectId(attendance_id)
        })

        return jsonify({
            "success": True,
            "message": "Check-out successful",
            "data": attendance_response(record)
        }), 200

    except PyMongoError as e:
        return jsonify({
            "success": False,
            "message": "Database error",
            "error": str(e)
        }), 500

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# --------------------------------------------------
# 3. GET ALL STAFF WITH TODAY'S ATTENDANCE STATUS
# GET /attendance/staff-list/<doctor_id>
# --------------------------------------------------

@c2c_app.route(
    "/attendance/staff-list/<string:doctor_id>",
    methods=["GET"]
)
def attendance_staff_list(doctor_id):
    try:
        today = now_ist().date().isoformat()

        staff_members = list(doctors.find({
            "role": "staff",
            "doctorId": doctor_id
        }))

        records = list(attendance.find({
            "doctor_id": doctor_id,
            "date": today
        }))

        attendance_map = {
            record["staff_id"]: record
            for record in records
        }

        result = []

        for staff in staff_members:
            staff_id = str(staff["_id"])
            record = attendance_map.get(staff_id)

            result.append({
                "staff_id": staff_id,
                "staff_name": get_staff_name(staff),
                "doctor_id": doctor_id,
                "date": today,
                "attendance_status": (
                    record.get("status", "present")
                    if record else "not_marked"
                ),
                "check_in": record.get("check_in") if record else None,
                "check_out": record.get("check_out") if record else None,
                "attendance_id": (
                    str(record["_id"]) if record else None
                ),
                "working_hours": (
                    calculate_working_hours(
                        record.get("check_in"),
                        record.get("check_out")
                    ) if record else None
                )
            })

        return jsonify({
            "success": True,
            "date": today,
            "count": len(result),
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# --------------------------------------------------
# 4. GET DAILY ATTENDANCE
# GET /attendance/daily/<doctor_id>?date=YYYY-MM-DD
# --------------------------------------------------

@c2c_app.route(
    "/attendance/daily/<string:doctor_id>",
    methods=["GET"]
)
def get_daily_attendance(doctor_id):
    try:
        date_value = request.args.get(
            "date",
            now_ist().date().isoformat()
        )
        date_value = validate_date(date_value)

        records = list(attendance.find({
            "doctor_id": doctor_id,
            "date": date_value
        }).sort("check_in", DESCENDING))

        for record in records:
            attendance_response(record)

        return jsonify({
            "success": True,
            "date": date_value,
            "count": len(records),
            "data": records
        }), 200

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Date must use YYYY-MM-DD"
        }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# --------------------------------------------------
# 5. GET STAFF ATTENDANCE HISTORY
# GET /attendance/history/<staff_id>?doctor_id=...
# Optional: start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
# --------------------------------------------------

@c2c_app.route(
    "/attendance/history/<string:staff_id>",
    methods=["GET"]
)
def get_staff_attendance_history(staff_id):
    try:
        doctor_id = request.args.get("doctor_id", "").strip()

        if not doctor_id or not ObjectId.is_valid(staff_id):
            return jsonify({
                "success": False,
                "message": "Valid doctor_id and staff_id are required"
            }), 400

        query = {
            "doctor_id": doctor_id,
            "staff_id": staff_id
        }

        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        if start_date or end_date:
            date_filter = {}

            if start_date:
                date_filter["$gte"] = validate_date(start_date)

            if end_date:
                date_filter["$lte"] = validate_date(end_date)

            if (
                start_date and end_date
                and date_filter["$gte"] > date_filter["$lte"]
            ):
                return jsonify({
                    "success": False,
                    "message": "start_date cannot be after end_date"
                }), 400

            query["date"] = date_filter

        records = list(
            attendance.find(query)
            .sort("date", DESCENDING)
            .limit(500)
        )

        for record in records:
            attendance_response(record)

        return jsonify({
            "success": True,
            "count": len(records),
            "data": records
        }), 200

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Dates must use YYYY-MM-DD"
        }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# --------------------------------------------------
# 6. GET SINGLE ATTENDANCE RECORD
# GET /attendance/record/<attendance_id>
# --------------------------------------------------

@c2c_app.route(
    "/attendance/record/<string:attendance_id>",
    methods=["GET"]
)
def get_attendance_record(attendance_id):
    try:
        if not ObjectId.is_valid(attendance_id):
            return jsonify({
                "success": False,
                "message": "Invalid attendance_id"
            }), 400

        record = attendance.find_one({
            "_id": ObjectId(attendance_id)
        })

        if not record:
            return jsonify({
                "success": False,
                "message": "Attendance record not found"
            }), 404

        return jsonify({
            "success": True,
            "data": attendance_response(record)
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# --------------------------------------------------
# 7. MONTHLY ATTENDANCE SUMMARY
# GET /attendance/summary/<staff_id>
# Query: doctor_id=...&month=YYYY-MM
# --------------------------------------------------

@c2c_app.route(
    "/attendance/summary/<string:staff_id>",
    methods=["GET"]
)
def attendance_summary(staff_id):
    try:
        doctor_id = request.args.get("doctor_id", "").strip()
        month = request.args.get(
            "month", now_ist().strftime("%Y-%m")
        )

        if not doctor_id or not ObjectId.is_valid(staff_id):
            return jsonify({
                "success": False,
                "message": "Valid doctor_id and staff_id are required"
            }), 400

        start = date.fromisoformat(month + "-01")

        if start.strftime("%Y-%m") != month:
            raise ValueError("Invalid month")

        if start.month == 12:
            next_month = date(start.year + 1, 1, 1)
        else:
            next_month = date(start.year, start.month + 1, 1)

        records = list(attendance.find({
            "doctor_id": doctor_id,
            "staff_id": staff_id,
            "date": {
                "$gte": start.isoformat(),
                "$lt": next_month.isoformat()
            }
        }))

        summary = {
            "month": month,
            "total_days": len(records),
            "present": 0,
            "incomplete_checkouts": 0,
            "total_hours": 0.0
        }

        for record in records:
            if record.get("status") == "present":
                summary["present"] += 1

            if not record.get("check_out"):
                summary["incomplete_checkouts"] += 1
            else:
                hours = calculate_working_hours(
                    record.get("check_in"),
                    record.get("check_out")
                )
                summary["total_hours"] += hours or 0

        summary["total_hours"] = round(
            summary["total_hours"], 2
        )

        return jsonify({
            "success": True,
            "data": summary
        }), 200

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Month must use YYYY-MM format"
        }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# --------------------------------------------------
# 8. APPLY FOR LEAVE
# POST /attendance/leave
# --------------------------------------------------

@c2c_app.route("/attendance/leave", methods=["POST"])
def apply_leave():
    try:
        data = request.get_json(silent=True) or {}

        doctor_id = str(data.get("doctor_id", "")).strip()
        staff_id = str(data.get("staff_id", "")).strip()
        reason = str(data.get("reason", "")).strip()

        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if not all([
            doctor_id, staff_id, start_date, end_date, reason
        ]):
            return jsonify({
                "success": False,
                "message": (
                    "doctor_id, staff_id, start_date, "
                    "end_date and reason are required"
                )
            }), 400

        start_date = validate_date(start_date)
        end_date = validate_date(end_date)

        if end_date < start_date:
            return jsonify({
                "success": False,
                "message": "end_date cannot be before start_date"
            }), 400

        staff = get_staff(doctor_id, staff_id)

        if not staff:
            return jsonify({
                "success": False,
                "message": "Staff not found for this doctor"
            }), 404

        current = now_ist()

        leave = {
            "doctor_id": doctor_id,
            "staff_id": staff_id,
            "staff_name": get_staff_name(staff),
            "start_date": start_date,
            "end_date": end_date,
            "reason": reason,
            "request_type": "leave",
            "status": "pending",
            "reviewed_by": None,
            "review_remarks": "",
            "created_at": current.isoformat(),
            "updated_at": current.isoformat()
        }

        result = leave_requests.insert_one(leave)

        try:
            from doctors.functions.attedance import send_approval_request_to_doctor
            send_approval_request_to_doctor(doctor_id, str(result.inserted_id), leave)
        except Exception as e:
            print("[c2c_app] Failed to send WhatsApp approval to doctor:", str(e))

        return jsonify({
            "success": True,
            "message": "Leave application submitted",
            "leave_id": str(result.inserted_id),
            "status": "pending"
        }), 201

    except ValueError:
        return jsonify({
            "success": False,
            "message": "Dates must use YYYY-MM-DD"
        }), 400

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# --------------------------------------------------
# 9. GET STAFF LEAVE REQUESTS
# GET /attendance/leave/<staff_id>?doctor_id=...
# --------------------------------------------------

@c2c_app.route(
    "/attendance/leave/<string:staff_id>",
    methods=["GET"]
)
def get_staff_leaves(staff_id):
    try:
        doctor_id = request.args.get("doctor_id", "").strip()

        if not doctor_id or not ObjectId.is_valid(staff_id):
            return jsonify({
                "success": False,
                "message": "Valid doctor_id and staff_id are required"
            }), 400

        records = list(
            leave_requests.find({
                "doctor_id": doctor_id,
                "staff_id": staff_id
            }).sort("created_at", DESCENDING).limit(500)
        )

        for record in records:
            serialize(record)

        return jsonify({
            "success": True,
            "count": len(records),
            "data": records
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# --------------------------------------------------
# 10. APPROVE OR REJECT LEAVE
# PUT /attendance/leave/<leave_id>/review
# --------------------------------------------------

@c2c_app.route(
    "/attendance/leave/<string:leave_id>/review",
    methods=["PUT"]
)
def review_leave(leave_id):
    try:
        if not ObjectId.is_valid(leave_id):
            return jsonify({
                "success": False,
                "message": "Invalid leave_id"
            }), 400

        data = request.get_json(silent=True) or {}

        status = data.get("status")
        reviewed_by = str(data.get("reviewed_by", "")).strip()
        remarks = str(data.get("remarks", "")).strip()

        if status not in ("approved", "rejected"):
            return jsonify({
                "success": False,
                "message": "status must be approved or rejected"
            }), 400

        if not reviewed_by:
            return jsonify({
                "success": False,
                "message": "reviewed_by is required"
            }), 400

        result = leave_requests.update_one(
            {
                "_id": ObjectId(leave_id),
                "status": "pending"
            },
            {
                "$set": {
                    "status": status,
                    "reviewed_by": reviewed_by,
                    "review_remarks": remarks,
                    "updated_at": now_ist().isoformat()
                }
            }
        )

        if result.matched_count == 0:
            existing = leave_requests.find_one({
                "_id": ObjectId(leave_id)
            })

            if not existing:
                return jsonify({
                    "success": False,
                    "message": "Leave request not found"
                }), 404

            return jsonify({
                "success": False,
                "message": "Leave request already reviewed"
            }), 409

        # When official duty is approved, automatically mark attendance (check-in or check-out)
        leave_doc = leave_requests.find_one({"_id": ObjectId(leave_id)})
        attendance_info = None
        duty_action_applied = None

        if status == "approved" and leave_doc:
            is_official_duty = (
                leave_doc.get("request_type") == "official_duty"
                or "official duty" in str(leave_doc.get("reason", "")).lower()
            )

            if is_official_duty:
                target_date = leave_doc.get("start_date") or now_ist().date().isoformat()
                doc_id = str(leave_doc.get("doctor_id", "")).strip()
                stf_id = str(leave_doc.get("staff_id", "")).strip()
                stf_name = leave_doc.get("staff_name") or ""
                shft_id = leave_doc.get("shift_id")
                shft_name = leave_doc.get("shift_name", "Official Duty")

                existing_att = attendance.find_one({
                    "doctor_id": doc_id,
                    "staff_id": stf_id,
                    "date": target_date
                })

                # Determine action: payload override OR document duty_action OR auto-detect
                duty_action = (
                    data.get("action")
                    or data.get("duty_action")
                    or leave_doc.get("duty_action")
                )

                if not duty_action or duty_action == "auto":
                    if existing_att and not existing_att.get("check_out"):
                        duty_action = "check_out"
                    else:
                        duty_action = "check_in"

                duty_action_applied = duty_action
                current_timestamp = leave_doc.get("created_at") or now_ist().isoformat()

                if duty_action == "check_out":
                    check_out_time = data.get("check_out") or current_timestamp
                    if existing_att:
                        attendance.update_one(
                            {"_id": existing_att["_id"]},
                            {
                                "$set": {
                                    "check_out": check_out_time,
                                    "updated_at": now_ist().isoformat(),
                                    "remarks": (
                                        str(existing_att.get("remarks", ""))
                                        + f" | Official Duty Check-Out Approved ({shft_name})"
                                    ).strip(" |")
                                }
                            }
                        )
                        att_updated = attendance.find_one({"_id": existing_att["_id"]})
                        attendance_info = attendance_response(att_updated)
                    else:
                        att_new = {
                            "doctor_id": doc_id,
                            "staff_id": stf_id,
                            "staff_name": stf_name,
                            "date": target_date,
                            "check_in": check_out_time,
                            "check_out": check_out_time,
                            "status": "present",
                            "attendance_type": "official_duty",
                            "shift_id": shft_id,
                            "shift_name": shft_name,
                            "remarks": f"Official Duty Check-Out Approved ({shft_name})",
                            "official_duty_id": str(leave_id),
                            "created_at": now_ist().isoformat(),
                            "updated_at": now_ist().isoformat()
                        }
                        insert_res = attendance.insert_one(att_new)
                        att_new["_id"] = insert_res.inserted_id
                        attendance_info = attendance_response(att_new)

                else:
                    # check_in
                    check_in_time = data.get("check_in") or current_timestamp
                    if existing_att:
                        attendance.update_one(
                            {"_id": existing_att["_id"]},
                            {
                                "$set": {
                                    "status": "present",
                                    "attendance_type": "official_duty",
                                    "shift_id": shft_id or existing_att.get("shift_id"),
                                    "shift_name": shft_name or existing_att.get("shift_name"),
                                    "updated_at": now_ist().isoformat(),
                                    "remarks": (
                                        str(existing_att.get("remarks", ""))
                                        + f" | Official Duty Check-In Approved ({shft_name})"
                                    ).strip(" |")
                                }
                            }
                        )
                        att_updated = attendance.find_one({"_id": existing_att["_id"]})
                        attendance_info = attendance_response(att_updated)
                    else:
                        att_new = {
                            "doctor_id": doc_id,
                            "staff_id": stf_id,
                            "staff_name": stf_name,
                            "date": target_date,
                            "check_in": check_in_time,
                            "check_out": None,
                            "status": "present",
                            "attendance_type": "official_duty",
                            "shift_id": shft_id,
                            "shift_name": shft_name,
                            "remarks": f"Official Duty Check-In Approved ({shft_name})",
                            "official_duty_id": str(leave_id),
                            "created_at": now_ist().isoformat(),
                            "updated_at": now_ist().isoformat()
                        }
                        try:
                            insert_res = attendance.insert_one(att_new)
                            att_new["_id"] = insert_res.inserted_id
                            attendance_info = attendance_response(att_new)
                        except DuplicateKeyError:
                            attendance.update_one(
                                {"doctor_id": doc_id, "staff_id": stf_id, "date": target_date},
                                {
                                    "$set": {
                                        "status": "present",
                                        "attendance_type": "official_duty",
                                        "updated_at": now_ist().isoformat()
                                    }
                                }
                            )
                            att_updated = attendance.find_one({
                                "doctor_id": doc_id,
                                "staff_id": stf_id,
                                "date": target_date
                            })
                            attendance_info = attendance_response(att_updated)

                # Send WhatsApp notification to staff if phone number is available
                try:
                    staff_phone = leave_doc.get("mobile_number")
                    if not staff_phone:
                        staff_obj = get_staff(doc_id, stf_id)
                        staff_phone = staff_obj.get("phone") if staff_obj else None
                    if staff_phone:
                        from doctors.functions.attedance import send_whatsapp_text
                        action_title = "Check-Out" if duty_action == "check_out" else "Check-In"
                        send_whatsapp_text(
                            staff_phone,
                            f"✅ Aapki Official Duty ({action_title}) request approve kar di gayi hai.\nAttendance mark ho gayi hai."
                        )
                except Exception as notify_err:
                    print("WhatsApp notification error upon approval:", notify_err)

        resp = {
            "success": True,
            "message": f"Leave {status} successfully",
            "status": status
        }
        if attendance_info:
            resp["message"] = f"Official duty approved and attendance marked ({duty_action_applied})"
            resp["attendance"] = attendance_info

        return jsonify(resp), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# --------------------------------------------------
# 11. GET ALL LEAVE & DUTY REQUESTS FOR A DOCTOR
# GET /attendance/leave-list/<doctor_id>?status=...
# --------------------------------------------------

@c2c_app.route(
    "/attendance/leave-list/<string:doctor_id>",
    methods=["GET"]
)
def get_all_doctor_leaves(doctor_id):
    try:
        doctor_id = str(doctor_id).strip()
        if not doctor_id:
            return jsonify({
                "success": False,
                "message": "doctor_id is required"
            }), 400

        query = {"doctor_id": doctor_id}

        status = request.args.get("status")
        if status:
            query["status"] = status.strip()

        request_type = request.args.get("request_type")
        if request_type:
            req_type = request_type.strip().lower()
            if req_type == "leave":
                query["$or"] = [
                    {"request_type": "leave"},
                    {"request_type": {"$exists": False}},
                    {"request_type": None}
                ]
            else:
                query["request_type"] = req_type

        # Pagination parameters
        page = request.args.get("page")
        limit = request.args.get("limit")

        try:
            page = max(1, int(page)) if page else 1
        except (ValueError, TypeError):
            page = 1

        try:
            limit = min(500, max(1, int(limit))) if limit else 10
        except (ValueError, TypeError):
            limit = 10

        skip = (page - 1) * limit

        total = leave_requests.count_documents(query)
        total_pages = (total + limit - 1) // limit if limit > 0 else 1

        records = list(
            leave_requests.find(query)
            .sort("created_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )

        for record in records:
            serialize(record)

        return jsonify({
            "success": True,
            "count": len(records),
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
            "data": records
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

