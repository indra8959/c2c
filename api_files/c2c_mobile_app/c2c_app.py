from pydoc import doc

from flask import Flask, app, request, jsonify, Blueprint,send_file,render_template
import requests
import random
from pymongo import MongoClient
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from api_files.c2c_mobile_app.firebase_service import send_push_notification,send_bulk_notifications

import os
import time

c2c_app = Blueprint("c2c_app", __name__)


# MongoDB connection
client = MongoClient("mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["app_db"]
otp_collection = db["otp_store"]
users_collection = db["users"]
appointment = db["appointment"]
doctors = db["doctors"]
medicine_orders_collection= db["medicine_orders"]

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
                'createdAt':item.get('createdAt')
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

RAZORPAY_KEY_ID = "rzp_test_T2ahUWS4UB3qoh"
RAZORPAY_KEY_SECRET = "swPZlBJaDZDjwouAxFSLVoGO"

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
            retrieved_data = appointment.find_one({"payment_link": order_id})

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
                {
                    "payment_link": order_id
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
            return jsonify({"status": "success"}),200

        else:
            return jsonify({"status": "failure"}), 400
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

    

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

            doctors.insert_one(doctor_request)

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
