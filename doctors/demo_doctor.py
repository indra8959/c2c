from flask import Blueprint, request, jsonify, redirect, render_template
from api_files.utils import duniyape_db as db
import re
from datetime import datetime, timedelta
import time
import hmac
import hashlib
import json
import requests
from PIL import Image, ImageDraw, ImageFont
from bson.objectid import ObjectId
from pymongo import MongoClient
from collections import Counter
from zoneinfo import ZoneInfo
from fpdf import FPDF
from threading import Thread
import secrets

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Spacer

demo_doctor = Blueprint("demo_doctor", __name__)

duniyapedb = db


# https://whatsappflow.duniyape.in/doctor_demo_flow_api/

MONGO_URI = "mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.get_database("caredb")
doctors = db["doctors"] 
appointment = db["appointment"] 
templog = db["logs"] 
disableslot = db["disableslot"] 
vouchers = db["vouchers"] 
admin = db["admin"] 
templog2 = db["tempdata"]


def is_recent(timestamp):
                timestamp = int(timestamp)  # Ensure it's an integer
                current_time = int(time.time())  # Get current timestamp
                return (current_time - timestamp) > 300

def checktext(text):
    match = re.match(r"(appoint_id)([a-f0-9]+)", text)
    if match.group(1)=="appoint_id":
        value = match.group(1)  # "67de8d2b81b4914ab512863d"
        # value = match.group(2)  # "67de8d2b81b4914ab512863d"
        return value
    else:
        return 0

@demo_doctor.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        VERIFY_TOKEN = "demo123"
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode and token == VERIFY_TOKEN:
            return challenge, 200
        return "Verification failed", 403
    elif request.method == 'POST':
        data = request.json
        

        try:
            entry = data.get('entry', [])[0]  # Extract first entry
            changes = entry.get('changes', [])[0]  # Extract first change
            value = changes.get('value', {})

            # print("Received data:", value)

            try:
                status_obj = data["entry"][0]["changes"][0]["value"]["statuses"][0]
                print(status_obj)
                if status_obj.get("status") == "captured":
                    return payment_deduct(status_obj)
            except Exception:
                pass

            try:
                status_obj = value.get('messages', [])[0] 
                print(status_obj)
                if status_obj.get("type") == "location":
                    return attendence(status_obj)
                else :
                    pass

            except Exception:
                pass

            message_info = value.get('messages', [])[0]  # Extract first message
            contact_info = value.get('contacts', [])[0]  # Extract first contact

            from_number = message_info.get('from')
            body = message_info.get('text', {}).get('body')
            msg_type = message_info.get('type')
            msg_type = message_info.get('type')
            timestamp = message_info.get('timestamp')
            name = contact_info.get('profile', {}).get('name')

            
    
            if is_recent(timestamp)==False:

                if msg_type == 'interactive' and "button_reply" in message_info.get('interactive', {}):
                    button_id = message_info["interactive"]["button_reply"]["id"]
                    print(button_id)
                    if button_id == "book_appointment":
                        return appointment_flow(from_number)
                    # if button_id == "Re-Appointment":
                    #     return send_selection(from_number)
                    if button_id == "enrole-patient":
                        return send_selection_enroll(from_number)
                    elif button_id.startswith("o_"):
                        prefix, unique_id = button_id.split("_", 1)
                        return sendattandence(from_number,timestamp,'Official Duty',unique_id,'RO')
                    elif button_id.startswith("l_"):
                        prefix, unique_id = button_id.split("_", 1)
                        return sendattandence(from_number,timestamp,'Leave',unique_id,'RL')
                    elif button_id == "Receipt":
                        return receiptme(from_number)
                    elif button_id == "no":
                        return sendthankyou(from_number)
                    elif button_id == "Same_person":
                        return same_name(from_number,'same')
                    elif button_id == "Different_person":
                        return same_name(from_number,'deff')
                    elif checktext(button_id) == "appoint_id":
                        match = re.match(r"(appoint_id)([a-f0-9]+)", button_id)
                        value = match.group(2)
                        tempdata = {"number":from_number,"id_value":value,"role":"custom_appointment","_id":from_number}
                        try:
                            templog.insert_one(tempdata)
                        except:
                            templog.update_one({'_id': from_number}, {'$set': tempdata})
                        return custom_appointment_flow(from_number)
                    else:
                        return "Invalid message type", 400
                elif msg_type == 'button' and message_info.get('button', {})['text']=='Download':
                    try:
                        today_date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
                        return pdfdownload(from_number,today_date)
                    except Exception as e:
                        return "Invalid message type", 400
                elif msg_type == 'interactive' and "nfm_reply" in message_info.get('interactive', {}):

                    
                    # utc_expire_time = document["expiretime"].replace(tzinfo=ZoneInfo("UTC"))
                    # current_time = datetime.now(ZoneInfo("UTC"))

                
                    response_json_data2 = data["entry"][0]["changes"][0]["value"]["messages"][0]["interactive"]["nfm_reply"]["response_json"]
                    json_data2 = json.loads(response_json_data2)
                    role = json_data2.get("role")
                    print(role)

                    if role=='ex':
                        document = templog.find_one({'_id':from_number})
                        data1 = document['store_data']

                        response_json_data1 = data1["entry"][0]["changes"][0]["value"]["messages"][0]["interactive"]["nfm_reply"]["response_json"]
                        response_json_data2 = data["entry"][0]["changes"][0]["value"]["messages"][0]["interactive"]["nfm_reply"]["response_json"]
                        json1 = json.loads(response_json_data1)
                        json2 = json.loads(response_json_data2)
                        for key in ["Date_of_appointment_0", "Time_Slot_1"]:
                            if key in json2:
                                json1[key] = json2[key]
                        data1["entry"][0]["changes"][0]["value"]["messages"][0]["interactive"]["nfm_reply"]["response_json"] = json.dumps(json1)
                        data = data1


                    if role=='currentOPD':
                        return book_current_appointment(data)

                    try:

                        mydatetime = dateandtime('date', '694e602ca1b88871ddbe2d23')

                        date_to_check = json_data2.get("Date_of_appointment_0")
                        exists = any(item['id'] == date_to_check and item.get("enabled", True) for item in mydatetime)
                        if exists:
                            return book_appointment(data)
                        elif role=='ex':
                            return appointment_flow_expire(from_number)
                        else:
                            tempdata = {"number":from_number,"_id":from_number,'store_data':data}
                            try:
                                templog.insert_one(tempdata)
                            except:
                                templog.update_one({'_id': from_number}, {'$set': tempdata})
                            return appointment_flow_expire(from_number)

                    
                    except Exception as e:
                        return "Invalid message type", 400
                elif msg_type == 'interactive' and "list_reply" in message_info.get('interactive', {}):
                    try:
                        stt = message_info.get('interactive', {})
                        value = stt['list_reply']['id']

                        tempdata = {"number":from_number,"id_value":value,"role":"custom_appointment","_id":from_number}
                        try:
                            templog.insert_one(tempdata)
                        except:
                            templog.update_one({'_id': from_number}, {'$set': tempdata})
                        if value[:2]=="cb":
                            value = value[2:]
                            appoint_data = appointment.find_one({"_id": ObjectId(value)})
                            name = appoint_data.get('patient_name')
                            pname = appoint_data.get('guardian_name')
                            return book_current_appointment_by_selectedlist(from_number,name,pname,timestamp)
                        else:
                            return custom_appointment_flow(from_number)
                    except Exception as e:
                        return "Invalid message type", 400

                elif msg_type == 'text' and body.lower() == "hi":
                    appointment_flow(from_number)
                    send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())
                    return "ok",200

                elif msg_type == 'text' and body.lower() == "hlo":
                    appointment_flow(from_number)
                    send_selection_enroll(from_number)

                    print(body.lower())
                    return "ok",200

                elif msg_type == 'text' and body.lower() == "hello":
                    appointment_flow(from_number)
                    send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    return "ok",200

                elif msg_type == 'text' and body.lower() == "hii":
                    appointment_flow(from_number)
                    send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    return "ok",200

                elif msg_type == 'text' and body.lower() == "hallo":
                    appointment_flow(from_number)
                    send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    return "ok",200

                elif msg_type == 'text' and body.lower() == "hy":
                    appointment_flow(from_number)
                    send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    return "ok",200
                elif msg_type == 'text' and body.lower() == "cb":
                    current_flow(from_number)
                    # send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    return "ok",200
                elif msg_type == 'text' and body.lower() == "cb2":
                    xxs = current_flow2(from_number)
                    dsds = send_selection_enroll_current(from_number)
                    # send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    return "ok",200
                elif msg_type == 'text' and body.lower() == "pdf":
                    print(body.lower())
                    today_date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
                    if from_number=="916265578975" or from_number=="918128265003" or from_number=="918968804953" or from_number=="917087778151" or from_number=="916283450048" or from_number=="918959690512":
                        return pdfdownload(from_number,today_date)
                    else:
                        return "ok",200
                elif msg_type == 'text' and body.lower() == "receipt":
                    print(body.lower())
                    return receiptme(from_number)
                # elif msg_type == 'text' and body.lower() == "tax":
                #     if from_number=="916265578975" or from_number=="918128265003" or from_number=="918968804953" or from_number=="917087778151" or from_number=="916283450048" or from_number=="918959690512":
                #         today_date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
                #         return taxpdfdownload1(from_number,today_date)
                #     else:
                #         return "ok",200
                    
                # elif msg_type == 'text' and body.lower().split()[0] == "tax":
                #     print(body.lower())

                #     match = re.search(r"\d{2}-\d{2}-\d{4}", body.lower())
                #     if match:
                #         extracted_date = match.group()  # "20-03-2024"
    
                #         formatted_date = datetime.strptime(extracted_date, "%d-%m-%Y").strftime("%Y-%m-%d")
    
                #         print(formatted_date)
                #     if from_number=="916265578975" or from_number=="918128265003" or from_number=="918968804953" or from_number=="917087778151" or from_number=="916283450048" or from_number=="918959690512":
                #         return taxpdfdownload1(from_number,formatted_date)
                #     else:
                #         return "ok",200
                    
                elif msg_type == 'text' and body.lower().split()[0] == "pdf":
                    print(body.lower())

                    match = re.search(r"\d{2}-\d{2}-\d{4}", body.lower())
                    if match:
                        extracted_date = match.group()  # "20-03-2024"
    
    # Convert to "YYYY-MM-DD" format
                        formatted_date = datetime.strptime(extracted_date, "%d-%m-%Y").strftime("%Y-%m-%d")
    
                        print(formatted_date)
                    if from_number=="916265578975" or from_number=="918128265003" or from_number=="918968804953" or from_number=="917087778151" or from_number=="916283450048" or from_number=="918959690512":
                        return pdfdownload(from_number,formatted_date)
                    else:
                        return "ok",200
                else:
                    print(body.lower())
                    return "Invalid message type", 400
            else: 
                return "Invalid message type", 400

        except Exception as e:
            print("Error:", str(e))
            return jsonify({"error": "Invalid request"}), 400


headers={'Authorization': 'Bearer EAAQNrOr6av0BPojE1zKKzKEDJWVmZBBvtBefl8aS24XBz4QcLzXPeF6wTlCBsIPFeOcwHi5AZBuXwkN6IfpI4uDjyLZAYRvMNF9jdVdeJ2WiNlnY1N1NpmFZBrJCSZAZCALx23ZArZA0jWnn0kEic6gY1Li4TFw8pZAnKZAmJtM0o6ZBfQZC8zi3v2EtcsoEnu9FutphkQZDZD','Content-Type': 'application/json'}

def appointment_flow(from_number):

    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

    incoming_data = { 
    "messaging_product": "whatsapp", 
    "to": from_number, 
    "type": "template", 
    "template": { 
        "name": "dr_firstflow", 
        "language": { "code": "en" },
        "components": [
            {
                "type": "header"
            },
            {
                "type": "body",
                "parameters": []
            },
            {
                "type": "button",
                "sub_type": "flow",  
                "index": "0"  
            }
        ]
    } 
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    print(jsonify(response.json()))
    return "OK", 200


def payment_deduct(status_obj):
    result = {
    "type": status_obj["type"],
    "recipient_id": status_obj["recipient_id"],
    "timestamp": status_obj["timestamp"],
    "status": status_obj["status"],
    "reference_id": status_obj["payment"]["reference_id"],
    "pg_transaction_id": status_obj["payment"]["transaction"]["pg_transaction_id"],
    "payment_status": status_obj["payment"]["transaction"]["status"],
    "value": status_obj["payment"]["amount"]["value"]
}
    retrieved_data = appointment.find_one({"razorpay_url": status_obj["payment"]["reference_id"], "payment_status":"link generated"})

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

    print('1')

            

    dxxocument = doctors.find_one({'_id':ObjectId('694e602ca1b88871ddbe2d23')})
    fee = float(dxxocument.get('appointmentfee'))

    print('1')


    index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)

    print('1')
    payment_id = str(status_obj["payment"]["transaction"]["pg_transaction_id"])

    doc_id = ObjectId(retrieved_data['_id'])
    appointment.update_one({'_id': doc_id},{'$set':{'payment_status':'paid','status':'success','pay_id':payment_id,'appoint_number':appoint_number,'amount':fee,'appointment_index':index_number}})

    print('1')
    name = str(retrieved_data['patient_name'])
    fname = str(retrieved_data['guardian_name'])
    payment_id = str(status_obj["payment"]["transaction"]["pg_transaction_id"])
    doa = str(retrieved_data['date_of_appointment'])
    tm = str(retrieved_data['time_slot'])
    phone = str(retrieved_data['whatsapp_number'])



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
    
            count_txn = vouchers.count_documents({})
            count = vouchers.count_documents({
                        "voucher_type": "Receipt",
                        "voucher_mode": "Bank",
                        "date": {"$gte": start, "$lt": end}   # between start and end of day
                    })
    
            voucher_number = "BRV-"+ str(date_str) +'-'+ str(count + 1)
            voucher = {
                        "amount":float(fee),
                        "voucher_number": voucher_number,
                        "voucher_type": 'Receipt',
                        "voucher_mode": "Bank",
                        "txn": count_txn + 1,
                        "doctor_id": retrieved_data['doctor_phone_id'],
                        "from_id": phone,
                        "to_id": payment_id,
                        "date": datetime.now(ZoneInfo("Asia/Kolkata")),
                        "Payment_id": payment_id,
                        "narration": 'Appointment Fee',
                        "entries": [
                    {
                    "narration": "Appointment Fee",
                    "ledger_id": "A1",
                    "ledger_name": "Razorpay",
                    "debit": float(fee),
                    "credit": 0
                    },
                    {
                    "narration": "Appointment Fee",
                    "ledger_id": "A2",
                    "ledger_name": "Doctor Fee Payble",
                    "debit": 0,
                    "credit": float(fee)-20
                    },
                    {
                    "narration": "Appointment Fee",
                    "ledger_id": "A3",
                    "ledger_name": "Platform Fee",
                    "debit": 0,
                    "credit": 16.95
                    },
                     {
                    "narration": "Appointment Fee",
                    "ledger_id": "A6",
                    "ledger_name": "GST Payable",
                    "debit": 0,
                    "credit": 3.05
                    }       
                    ],
                        "created_by": "system",
                        "created_at": ist_now
                    }
            vouchers.insert_one(voucher)
    except:
        print(2)

    if tm=="current":
        print('currenet',name,phone)

        whatsapp_url = current_success_appointment(name,phone,payment_id)
        whatsapp_url = dr_current_success_appointment(name,fname,phone,payment_id,fee, '916265578975')
        whatsapp_url = dr_current_success_appointment(name,fname,phone,payment_id,fee, '918128265003')
    else :
        print('non-current',name,phone)
        whatsapp_url = success_appointment(doa,index_number,name,doa,tm,phone)

    return "ok",200

def current_flow(from_number):

    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

    incoming_data = { 
    "messaging_product": "whatsapp", 
    "to": from_number, 
    "type": "template", 
    "template": { 
        "name": "current_booking_msg", 
        "language": { "code": "en" },
        "components": [
            {
                "type": "header"
            },
            {
                "type": "body",
                "parameters": [{
                    "type": "text",
                    "text": f"https://booking.doctor-connect.live/"+from_number
                }]
            }
            # ,
            # {
            #     "type": "button",
            #     "sub_type": "flow",  
            #     "index": "0"  
            # }
        ]
    } 
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    # print(jsonify(response.json()))
    return "OK", 200


def current_flow2(from_number):

    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

    incoming_data = { 
    "messaging_product": "whatsapp", 
    "to": from_number, 
    "type": "template", 
    "template": { 
        "name": "current_booking", 
        "language": { "code": "en" },
        "components": [
            {
                "type": "header"
            },
            {
                "type": "body",
                "parameters": []
            }
            ,
            {
                "type": "button",
                "sub_type": "flow",  
                "index": "0"  
            }
        ]
    } 
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    # print(jsonify(response.json()))
    return "OK", 200

def custom_appointment_flow(from_number):

    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

    incoming_data = { 
    "messaging_product": "whatsapp", 
    "to": from_number, 
    "type": "template", 
    "template": { 
        "name": "clone_appointment_flow_4", 
        "language": { "code": "en" },
        "components": [
            {
                "type": "header"
            },
            {
                "type": "body",
                "parameters": []
            },
            {
                "type": "button",
                "sub_type": "flow",  
                "index": "0"  
            }
        ]
    } 
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    print(response)
    return "OK", 200




def send_selection_enroll(from_number):

    result = list(appointment.find({"whatsapp_number": from_number}))
# Store only the latest appointment per patient
    unique_patients = {}
    latest_appointments = []

    # if len(result)<1:
    #     return appointment_flow(from_number)

    for record in result:
        patient_name = record.get("patient_name")
        display_name = (patient_name[:15] + "...") if len(patient_name) > 10 else patient_name
        if patient_name and patient_name not in unique_patients:
            unique_patients[patient_name] = True
            

            latest_appointments.append({
            "id": str(record["_id"]) if "_id" in record else "",  # Handle missing _id
            "title": display_name,
            "father":str(record["guardian_name"])
                })

    # all_buttons = latest_appointments + [{"id": "book_appointment", "title": "New Patient"},{"id": "enrole-patient", "title": "Enrole Patient"},{"id": "Re-Appointment", "title": "Re-Appointment"}]


    rows = [
    {
        "id": str(app["id"]),
        "title": app["title"],
        "description": 'Father`s Name : '+app["father"],
    }
    for app in latest_appointments[-10:]
]

    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

    incoming_data = {
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": from_number,
  "type": "interactive",
  "interactive": {
    "type": "list",
    "header": {
      "type": "text",
      "text": ""
    },
    "body": {
      "text": "Book Appointment – Existing Patients"
    },
    # "footer": {
    #   "text": "Powered by WhatsApp Cloud API"
    # },
    "action": {
      "button": "Choose Patient",
      "sections": [
        {
          "title": "Options",
          "rows": rows
        }
      ]
    }
  }
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    return "OK", 200


def send_selection_enroll_current(from_number):

    result = list(appointment.find({"whatsapp_number": from_number}))
# Store only the latest appointment per patient
    unique_patients = {}
    latest_appointments = []

    # if len(result)<1:
    #     return appointment_flow(from_number)

    for record in result:
        patient_name = record.get("patient_name")
        display_name = (patient_name[:15] + "...") if len(patient_name) > 10 else patient_name
        if patient_name and patient_name not in unique_patients:
            unique_patients[patient_name] = True
            

            latest_appointments.append({
            "id": "cb"+str(record["_id"]) if "_id" in record else "",  # Handle missing _id
            "title": display_name,
            "father":str(record["guardian_name"])
                })

    # all_buttons = latest_appointments + [{"id": "book_appointment", "title": "New Patient"},{"id": "enrole-patient", "title": "Enrole Patient"},{"id": "Re-Appointment", "title": "Re-Appointment"}]


    rows = [
    {
        "id": str(app["id"]),
        "title": app["title"],
        "description": 'Father`s Name :- '+app["father"],
    }
    for app in latest_appointments[-10:]
]

    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

    incoming_data = {
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": from_number,
  "type": "interactive",
  "interactive": {
    "type": "list",
    "header": {
      "type": "text",
      "text": ""
    },
    "body": {
      "text": "Book Appointment – Existing Patients"
    },
    # "footer": {
    #   "text": "Powered by WhatsApp Cloud API"
    # },
    "action": {
      "button": "Choose Patient",
      "sections": [
        {
          "title": "Options",
          "rows": rows
        }
      ]
    }
  }
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    return "OK", 200




def same_name(from_number,ap_type):

    data = templog2.find_one({'_id':from_number})

    entry = data.get('entry', [])[0]  # Extract first entry
    changes = entry.get('changes', [])[0]  # Extract first change
    value = changes.get('value', {})

    message_info = value.get('messages', [])[0] 
    response_json_str = data['entry'][0]['changes'][0]['value']['messages'][0]['interactive']['nfm_reply']['response_json']
    response_data = json.loads(response_json_str)
    print(response_data)

    if response_data.get('role')=='personal_flow':
        return custom_book_appointment(data)

    name = response_data.get('Patient_Name_2')
    pname = 'none'
    date = response_data.get('Date_of_appointment_0')
    slot = response_data.get('Time_Slot_1')
    vaccine = response_data.get('vaccine')

    email = 'none'
    symptoms = 'none'
    age = 'none'
    dob = 'none'
    city = 'none'
    address = 'none'

    if response_data.get('Guardian_Name'):
        pname = response_data.get('Guardian_Name')
    else:
        pname = 'none'


    if response_data.get('Email_4'):
        email = response_data.get('Email_4')
    else:
        email = 'none'

    if response_data.get('Other_Symptoms_5'):
        symptoms = response_data.get('Other_Symptoms_5')
    else:
        symptoms = 'none'

    if response_data.get('Age_3'):
        age = response_data.get('Age_3')
    else:
        age = 'none'

    if response_data.get('Date_Of_Birth'):
        dob = response_data.get('Date_Of_Birth')
    else:
        dob = 'none'

    if response_data.get('City'):
        city = response_data.get('City')
    else:
        city = 'none'

    if response_data.get('Address'):
        address = response_data.get('Address')
    else:
        address = 'none'

    from_number = message_info.get('from')
    timestamp = message_info.get('timestamp')

    doctor_id = '694e602ca1b88871ddbe2d23'

    # result = list(doctors.find({"doctor_phone_id": doctor_id}, {"_id": 0}))  # Convert cursor to list
    # data_length = len(result)

    dataset = {
        'patient_name': name,
        'guardian_name': pname,
        'date_of_appointment': date,
        'time_slot': slot,
        'doctor_phone_id':doctor_id,
        'email' : email,
        'symptoms' : symptoms,
        'age' : age,
        'timestamp' : timestamp,
        'whatsapp_number' : from_number,
        'date_of_birth' : dob,
        'city' : city,
        'address' : address,
        'role':'appointment',
        'status':'created',
        "createdAt": 'x',
        "vaccine":vaccine
            }
    
    date_str = date
    xdate = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = xdate - timedelta(days=2)

    
    from_date = datetime.strptime(new_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
    todate = datetime.strptime(date_str, "%Y-%m-%d")
    todate = todate.replace(hour=23, minute=59, second=59)  # Ensure full-day inclusion

# Query with date filtering (Convert date_of_appointment to datetime in query)
    result = list(appointment.find({
    "whatsapp_number": from_number,
    "patient_name": name,
    "doctor_phone_id": doctor_id,
    "amount":{"$gt": 0},
    "$expr": {
        "$and": [
            {"$gte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, from_date]},
            {"$lte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, todate]}
        ]
    }
    }).sort("date_of_appointment", -1).limit(1)) 

    if len(result)>0 and ap_type=='same':

        retrieved_data = result[0]
        result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":date,"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
        data_length = 1
        if result:
            data_length = len(result)+1

        xdate = date
        date_obj = datetime.strptime(xdate, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y%m%d")

        pay_id = str(retrieved_data['pay_id'])
        pay_id = "old_"+pay_id

        img_date = str(retrieved_data['date_of_appointment'])

        appoint_number = str(formatted_date)+'-'+str(data_length)

        dxxocument = doctors.find_one({'_id':ObjectId('694e602ca1b88871ddbe2d23')})
        fee = float(dxxocument.get('appointmentfee'))




        index_number = getindex(retrieved_data['doctor_phone_id'],slot,xdate)


        xid = appointment.insert_one({**dataset,'status':'success','pay_id':pay_id,'appoint_number':appoint_number,'amount':0,'appointment_index':index_number}).inserted_id


        tempdata = {"number":from_number,"current_id":xid,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        

        name = str(retrieved_data['patient_name'])
        phone = str(retrieved_data['whatsapp_number'])

        return success_appointment(img_date,index_number,name,date,slot,phone)
    else:
        id = str(appointment.insert_one(dataset).inserted_id)
        print(id)

        dxxocument = doctors.find_one({'_id':ObjectId('694e602ca1b88871ddbe2d23')})
        fee = float(dxxocument.get('appointmentfee'))
        # paymentlink = dxxocument.get('paymentlink')

        tempdata = {"number":from_number,"current_id":id,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
        razorpayid = dxocument.get('razorpayid')
        razorpaykey = dxocument.get('razorpaykey')

        razorpayid = 'rzp_test_RqfTdh1uuEAroY'
        razorpaykey = 'N4jInbrfyCmpYmA1tib3TBgm'


        # link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)
        link = f"order_{secrets.token_hex(8)}"
        doc_id = ObjectId(id)
        appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':link,'payment_status':'link generated'}})


        # link = paymentlink
        print(link)
        amount = fee
        return send_payment_flow(from_number,name,date,slot,amount,link)
    



def book_appointment(data):

    entry = data.get('entry', [])[0]  # Extract first entry
    changes = entry.get('changes', [])[0]  # Extract first change
    value = changes.get('value', {})

    message_info = value.get('messages', [])[0] 
    response_json_str = data['entry'][0]['changes'][0]['value']['messages'][0]['interactive']['nfm_reply']['response_json']
    response_data = json.loads(response_json_str)
    print(response_data)

    if response_data.get('role')=='personal_flow':
        return custom_book_appointment(data)

    name = response_data.get('Patient_Name_2')
    pname = 'none'
    date = response_data.get('Date_of_appointment_0')
    slot = response_data.get('Time_Slot_1')
    vaccine = response_data.get('vaccine')

    email = 'none'
    symptoms = 'none'
    age = 'none'
    dob = 'none'
    city = 'none'
    address = 'none'

    if response_data.get('Guardian_Name'):
        pname = response_data.get('Guardian_Name')
    else:
        pname = 'none'


    if response_data.get('Email_4'):
        email = response_data.get('Email_4')
    else:
        email = 'none'

    if response_data.get('Other_Symptoms_5'):
        symptoms = response_data.get('Other_Symptoms_5')
    else:
        symptoms = 'none'

    if response_data.get('Age_3'):
        age = response_data.get('Age_3')
    else:
        age = 'none'

    if response_data.get('Date_Of_Birth'):
        dob = response_data.get('Date_Of_Birth')
    else:
        dob = 'none'

    if response_data.get('City'):
        city = response_data.get('City')
    else:
        city = 'none'

    if response_data.get('Address'):
        address = response_data.get('Address')
    else:
        address = 'none'

    from_number = message_info.get('from')
    timestamp = message_info.get('timestamp')

    doctor_id = '694e602ca1b88871ddbe2d23'


    dataset = {
        'patient_name': name,
        'guardian_name': pname,
        'date_of_appointment': date,
        'time_slot': slot,
        'doctor_phone_id':doctor_id,
        'email' : email,
        'symptoms' : symptoms,
        'age' : age,
        'timestamp' : timestamp,
        'whatsapp_number' : from_number,
        'date_of_birth' : dob,
        'city' : city,
        'address' : address,
        'role':'appointment',
        'status':'created',
        "createdAt": 'x',
        "vaccine":vaccine
            }
    
    date_str = date
    xdate = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = xdate - timedelta(days=2)

    
    from_date = datetime.strptime(new_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
    todate = datetime.strptime(date_str, "%Y-%m-%d")
    todate = todate.replace(hour=23, minute=59, second=59)  # Ensure full-day inclusion

# Query with date filtering (Convert date_of_appointment to datetime in query)
    result = list(appointment.find({
    "whatsapp_number": from_number,
    "patient_name": name,
    "doctor_phone_id": doctor_id,
    "amount":{"$gt": 0},
    "$expr": {
        "$and": [
            {"$gte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, from_date]},
            {"$lte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, todate]}
        ]
    }
    }).sort("date_of_appointment", -1).limit(1)) 

    if len(result)>0:

        try:
            templog2.insert_one({**data,'_id': from_number})
        except:
            templog2.update_one({'_id': from_number}, {'$set': data})

        return sameordef(from_number,name)

    else:
        id = str(appointment.insert_one(dataset).inserted_id)
        print(id)

        dxxocument = doctors.find_one({'_id':ObjectId('694e602ca1b88871ddbe2d23')})
        fee = float(dxxocument.get('appointmentfee'))
        # paymentlink = dxxocument.get('paymentlink')

        tempdata = {"number":from_number,"current_id":id,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
        razorpayid = dxocument.get('razorpayid')
        razorpaykey = dxocument.get('razorpaykey')

        razorpayid = 'rzp_test_RqfTdh1uuEAroY'
        razorpaykey = 'N4jInbrfyCmpYmA1tib3TBgm'


        # link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)
        link = f"order_{secrets.token_hex(8)}"
        doc_id = ObjectId(id)
        appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':link,'payment_status':'link generated'}})


        # link = paymentlink
        print(link)
        amount = fee
        return send_payment_flow(from_number,name,date,slot,amount,link)
    
@demo_doctor.route('/current_appointment', methods=['POST'])
def book_current_appointment_web():
    data = request.get_json()
    name = data.get('Patient_Name')
    pname = data.get('Fathers_name')
    sex = data.get('sex')

    date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    slot = "current"
    vaccine = "No"

    email = 'none'
    symptoms = 'none'
    age = 'none'
    dob = 'none'
    city = 'none'
    address = 'none'

    from_number = data.get('mobile')
    # timestamp = message_info.get('timestamp')

    doctor_id = '694e602ca1b88871ddbe2d23'


    dataset = {
        'patient_name': name,
        'guardian_name': pname,
        'date_of_appointment': date,
        'time_slot': slot,
        'doctor_phone_id':doctor_id,
        'email' : email,
        'symptoms' : symptoms,
        'age' : age,
        'timestamp' : int(time.time()),
        'whatsapp_number' : from_number,
        'date_of_birth' : dob,
        'city' : city,
        'address' : address,
        'role':'appointment',
        'status':'created',
        "createdAt": 'x',
        "vaccine":vaccine,
        "sex":sex
            }
    
    date_str = date
    xdate = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = xdate - timedelta(days=2)

    
    from_date = datetime.strptime(new_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
    todate = datetime.strptime(date_str, "%Y-%m-%d")
    todate = todate.replace(hour=23, minute=59, second=59)  # Ensure full-day inclusion

# Query with date filtering (Convert date_of_appointment to datetime in query)
    result = list(appointment.find({
    "whatsapp_number": from_number,
    "patient_name": name,
    "doctor_phone_id": doctor_id,
    "amount":{"$gt": 0},
    "$expr": {
        "$and": [
            {"$gte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, from_date]},
            {"$lte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, todate]}
        ]
    }
    }).sort("date_of_appointment", -1).limit(1)) 

    if len(result)>0:

        try:
            templog2.insert_one({**data,'_id': from_number})
        except:
            templog2.update_one({'_id': from_number}, {'$set': data})

        return sameordef(from_number,name)

    else:
        id = str(appointment.insert_one(dataset).inserted_id)
        print(id)

        dxxocument = doctors.find_one({'_id':ObjectId('694e602ca1b88871ddbe2d23')})
        fee = float(dxxocument.get('appointmentfee'))
        # paymentlink = dxxocument.get('paymentlink')

        tempdata = {"number":from_number,"current_id":id,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
        razorpayid = dxocument.get('razorpayid')
        razorpaykey = dxocument.get('razorpaykey')
        razorpayid = 'rzp_test_RqfTdh1uuEAroY'
        razorpaykey = 'N4jInbrfyCmpYmA1tib3TBgm'
        link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)

        # link = f"order_{secrets.token_hex(8)}"
        # doc_id = ObjectId(id)
        # appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':link,'payment_status':'link generated'}})


        # link = paymentlink
        print(link)
        amount = fee
        return jsonify({'payment_url':f'https://rzp.io/rzp/{link}'}),200
    
def book_current_appointment(data):
    entry = data.get('entry', [])[0]  # Extract first entry
    changes = entry.get('changes', [])[0]  # Extract first change
    value = changes.get('value', {})

    message_info = value.get('messages', [])[0] 
    response_json_str = data['entry'][0]['changes'][0]['value']['messages'][0]['interactive']['nfm_reply']['response_json']
    response_data = json.loads(response_json_str)
    print(response_data)

    sex = response_data.get('sex')
    name = response_data.get('Patient_Name')
    pname = response_data.get('Fathers_name')
    date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    slot = "current"
    vaccine = "No"

    email = 'none'
    symptoms = 'none'
    age = 'none'
    dob = 'none'
    city = 'none'
    address = 'none'

    from_number = message_info.get('from')
    timestamp = message_info.get('timestamp')

    doctor_id = '694e602ca1b88871ddbe2d23'


    dataset = {
        'patient_name': name,
        'guardian_name': pname,
        'date_of_appointment': date,
        'time_slot': slot,
        'doctor_phone_id':doctor_id,
        'email' : email,
        'symptoms' : symptoms,
        'age' : age,
        'timestamp' : timestamp,
        'whatsapp_number' : from_number,
        'date_of_birth' : dob,
        'city' : city,
        'address' : address,
        'role':'appointment',
        'status':'created',
        "createdAt": 'x',
        "sex":sex,
        "vaccine":vaccine
            }
    
    date_str = date
    xdate = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = xdate - timedelta(days=2)

    
    from_date = datetime.strptime(new_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
    todate = datetime.strptime(date_str, "%Y-%m-%d")
    todate = todate.replace(hour=23, minute=59, second=59)  # Ensure full-day inclusion

# Query with date filtering (Convert date_of_appointment to datetime in query)
    result = list(appointment.find({
    "whatsapp_number": from_number,
    "patient_name": name,
    "doctor_phone_id": doctor_id,
    "amount":{"$gt": 0},
    "$expr": {
        "$and": [
            {"$gte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, from_date]},
            {"$lte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, todate]}
        ]
    }
    }).sort("date_of_appointment", -1).limit(1)) 

    if len(result)>0:

        try:
            templog2.insert_one({**data,'_id': from_number})
        except:
            templog2.update_one({'_id': from_number}, {'$set': data})

        return sameordef(from_number,name)

    else:
        id = str(appointment.insert_one(dataset).inserted_id)
        print(id)

        dxxocument = doctors.find_one({'_id':ObjectId('694e602ca1b88871ddbe2d23')})
        fee = float(dxxocument.get('appointmentfee'))
        # paymentlink = dxxocument.get('paymentlink')

        tempdata = {"number":from_number,"current_id":id,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
        razorpayid = dxocument.get('razorpayid')
        razorpaykey = dxocument.get('razorpaykey')

        razorpayid = 'rzp_test_RqfTdh1uuEAroY'
        razorpaykey = 'N4jInbrfyCmpYmA1tib3TBgm'


        # link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)

        link = f"order_{secrets.token_hex(8)}"
        doc_id = ObjectId(id)
        appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':link,'payment_status':'link generated'}})


        # link = paymentlink
        print(link)
        amount = fee
        return send_payment_flow(from_number,name,date,slot,amount,link)
    
def book_current_appointment_by_selectedlist(from_number,cutname,father,timestamp):
    

    name = cutname
    pname = father
    date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    slot = "current"
    vaccine = "No"

    email = 'none'
    symptoms = 'none'
    age = 'none'
    dob = 'none'
    city = 'none'
    address = 'none'

    from_number = from_number
    timestamp = timestamp

    doctor_id = '694e602ca1b88871ddbe2d23'


    dataset = {
        'patient_name': name,
        'guardian_name': pname,
        'date_of_appointment': date,
        'time_slot': slot,
        'doctor_phone_id':doctor_id,
        'email' : email,
        'symptoms' : symptoms,
        'age' : age,
        'timestamp' : timestamp,
        'whatsapp_number' : from_number,
        'date_of_birth' : dob,
        'city' : city,
        'address' : address,
        'role':'appointment',
        'status':'created',
        "createdAt": 'x',
        "vaccine":vaccine
            }
    
    date_str = date
    xdate = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = xdate - timedelta(days=2)

    


        # try:
        #     templog2.insert_one({**data,'_id': from_number})
        # except:
        #     templog2.update_one({'_id': from_number}, {'$set': data})

        # return sameordef(from_number,name)

    id = str(appointment.insert_one(dataset).inserted_id)
    print(id)

    dxxocument = doctors.find_one({'_id':ObjectId('694e602ca1b88871ddbe2d23')})
    fee = float(dxxocument.get('appointmentfee'))
        # paymentlink = dxxocument.get('paymentlink')

    tempdata = {"number":from_number,"current_id":id,"_id":from_number}
    try:
            templog.insert_one(tempdata)
    except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

    dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
    razorpayid = dxocument.get('razorpayid')
    razorpaykey = dxocument.get('razorpaykey')

    razorpayid = 'rzp_test_RqfTdh1uuEAroY'
    razorpaykey = 'N4jInbrfyCmpYmA1tib3TBgm'


    # link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)

    link = f"order_{secrets.token_hex(8)}"
    doc_id = ObjectId(id)
    appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':link,'payment_status':'link generated'}})


        # link = paymentlink
    # print(link)
    amount = fee
    return send_payment_flow(from_number,name,date,slot,amount,link)
    


def custom_book_appointment(data):

    entry = data.get('entry', [])[0]  # Extract first entry
    changes = entry.get('changes', [])[0]  # Extract first change
    value = changes.get('value', {})

    message_info = value.get('messages', [])[0] 
    from_number = message_info.get('from')

    document = templog.find_one({'_id':from_number})
    appoint_data = appointment.find_one({"_id": ObjectId(document["id_value"])})

    print(appoint_data)

    response_json_str = data['entry'][0]['changes'][0]['value']['messages'][0]['interactive']['nfm_reply']['response_json']
    response_data = json.loads(response_json_str)
    print(response_data)

    

    name = appoint_data.get('patient_name')
    pname = appoint_data.get('guardian_name')
    date = response_data.get('Date_of_appointment_0')
    slot = response_data.get('Time_Slot_1')
    vaccine = response_data.get('vaccine')
    email = 'none'
    symptoms = 'none'
    age = 'none'
    dob = 'none'
    city = 'none'
    address = 'none'

    if response_data.get('Guardian_Name'):
        pname = response_data.get('Guardian_Name')
    else:
        pname = pname

    if appoint_data.get('email'):
        email = appoint_data.get('email')
    else:
        email = 'none'

    if response_data.get('Other_Symptoms_5'):
        symptoms = response_data.get('Other_Symptoms_5')
    else:
        symptoms = 'none'

    if appoint_data.get('age'):
        age = appoint_data.get('age')
    else:
        age = 'none'

    if appoint_data.get('date_of_birth'):
        dob = appoint_data.get('date_of_birth')
    else:
        dob = 'none'

    if appoint_data.get('city'):
        city = appoint_data.get('city')
    else:
        city = 'none'

    if appoint_data.get('address'):
        address = appoint_data.get('address')
    else:
        address = 'none'

    from_number = message_info.get('from')
    timestamp = message_info.get('timestamp')

    doctor_id = '694e602ca1b88871ddbe2d23'

    # result = list(doctors.find({"doctor_phone_id": doctor_id}, {"_id": 0}))  # Convert cursor to list
    # data_length = len(result)

    dataset = {
        'patient_name': name,
        'guardian_name': pname,
        'date_of_appointment': date,
        'time_slot': slot,
        'doctor_phone_id':doctor_id,
        'email' : email,
        'symptoms' : symptoms,
        'age' : age,
        'timestamp' : timestamp,
        'whatsapp_number' : from_number,
        'date_of_birth' : dob,
        'city' : city,
        'address' : address,
        'role':'appointment',
        'status':'created',
        "createdAt": 'x',
        "vaccine":vaccine
            }
    
    date_str = date
    xdate = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = xdate - timedelta(days=2)

    
    from_date = datetime.strptime(new_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
    todate = datetime.strptime(date_str, "%Y-%m-%d")
    todate = todate.replace(hour=23, minute=59, second=59)  # Ensure full-day inclusion

# Query with date filtering (Convert date_of_appointment to datetime in query)
    result = list(appointment.find({
    "whatsapp_number": from_number,
    "patient_name": name,
    "doctor_phone_id": doctor_id,
    "amount":{"$gt": 0},
    "$expr": {
        "$and": [
            {"$gte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, from_date]},
            {"$lte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, todate]}
        ]
    }
    }).sort("date_of_appointment", -1).limit(1)) 

    if len(result)>0:
        retrieved_data = result[0]
        result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":date,"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
        data_length = 1
        if result:
            data_length = len(result)+1

        xdate = date
        date_obj = datetime.strptime(xdate, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y%m%d")

        pay_id = str(retrieved_data['pay_id'])
        pay_id = "old_"+pay_id

        img_date = str(retrieved_data['date_of_appointment'])

        appoint_number = str(formatted_date)+'-'+str(data_length)




        dxxocument = doctors.find_one({'_id':ObjectId('694e602ca1b88871ddbe2d23')})
        fee = float(dxxocument.get('appointmentfee'))




        index_number = getindex(retrieved_data['doctor_phone_id'],slot,xdate)

        



        xid = appointment.insert_one({**dataset,'status':'success','pay_id':pay_id,'appoint_number':appoint_number,'amount':0,'appointment_index':index_number}).inserted_id


        tempdata = {"number":from_number,"current_id":xid,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        name = str(retrieved_data['patient_name'])
        payment_id = str(pay_id)
        doa = str(retrieved_data['date_of_appointment'])
        tm = str(retrieved_data['time_slot'])
        phone = str(retrieved_data['whatsapp_number'])


        return success_appointment(img_date,index_number,name,date,slot,phone)
    
    else:
        id = str(appointment.insert_one(dataset).inserted_id)
        print(id)

        dxxocument = doctors.find_one({'_id':ObjectId('694e602ca1b88871ddbe2d23')})
        fee = float(dxxocument.get('appointmentfee'))
        # paymentlink = dxxocument.get('paymentlink')

        tempdata = {"number":from_number,"current_id":id,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})


        dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
        razorpayid = dxocument.get('razorpayid')
        razorpaykey = dxocument.get('razorpaykey')

        razorpayid = 'rzp_test_RqfTdh1uuEAroY'
        razorpaykey = 'N4jInbrfyCmpYmA1tib3TBgm'


        # link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)
        # link = paymentlink
        # print(link)

        link = f"order_{secrets.token_hex(8)}"
        doc_id = ObjectId(id)
        appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':link,'payment_status':'link generated'}})
        amount = fee
        return send_payment_flow(from_number,name,date,slot,amount,link)


def sameordef(from_number, name):
    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

    all_buttons = [
    {"id": "Same_person", "title": "Same patient"},
    {"id": "Different_person", "title": "Different patient"}
    ]

# Function to send buttons in batches of 3
    def send_whatsapp_buttons(to_number, buttons_list):
        for i in range(0, len(buttons_list), 3):  # Send in groups of 3
            buttons = buttons_list[i:i+3]  # Get 3 buttons at a time

            payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": f"We noticed that someone with the same name *{name}* has already booked an appointment.\n Are you the same patient who already booked, or someone different?"},
                "action": {
                    "buttons": [{"type": "reply", "reply": btn} for btn in buttons]
                }
            }
        }

            response = requests.post(external_url, headers=headers, json=payload)
       
         

# Send multiple messages with 3 buttons per message
    send_whatsapp_buttons(from_number, all_buttons)

    # response = requests.post(external_url, json=payloadx, headers={'Authorization': 'Bearer EAAJdr829Xj4BOxyhp8MzkQqZCr92HwzYQMyDjZBhWZBqUej9YnYqTBefwyGeIZAUOhSk3y9AspLT69frxyYsWb6ea7jAGP4xm3BCxkAF5SXMqLeY3SpYt5AUUi0CkUIhk8AC6S1H6TIr0RLQHf3Tfo6ZBblcMZCBoc81nqVTidywfSK4FoWZAZCXenHHqRr5wAtE5D2tIGf87f8B7wuXUcWyK77Wca1ZBR3tqxQMOkK6L6BUZD','Content-Type': 'application/json'})
    # print(jsonify(response.json()))
    return "OK", 200




def payment_link_canceled(link, from_number):
    """Expires a Razorpay payment link by sending a POST to /cancel."""
    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"

    incoming_data ={
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": from_number,
  "type": "interactive",
  "interactive": {
    "type": "order_status",
    "body": {
      "text": "This payment link has expired."
    },
    "action": {
      "name": "review_order",
      "parameters": {
        "reference_id": link,
        "order": {
          "status": "canceled",
          "description": "Payment window closed"
        }
      }
    }
  }
}
    
    # Wait for 5 minutes (300 seconds)
    time.sleep(300)

    retrieved_data = appointment.find_one({"razorpay_url": link, "payment_status":"link generated"})

    if retrieved_data:

        response = requests.post(external_url, json=incoming_data, headers=headers)

        if response.status_code == 200:
            print("Payment link expired successfully.")
        else:
            print("Failed to expire payment link:", response.text)


 
def send_payment_flow(from_number,name,date,slot,amount,link):


    # formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")

    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

    # incoming_data = { 
    #     "messaging_product": "whatsapp", 
    #     "to": from_number, "type": "template", 
    #     "template": { 
    #         "name": "dr_payment_link", 
    #         "language": { 
    #             "code": "en" 
    #         },
    #         "components": [
    #             {
    #                 "type": "header",
    #                 "parameters":  []

    #             },
    #              {
    #     "type": "body",
    #     "parameters": [ {
    #                 "type": "text",
    #                 "text": amount
    #             }
         
    #     ]
    #   }, {
    #             "type": "button",
    #             "index": "0",
    #             "sub_type": "url",
    #             "parameters": [
    #                 {
    #                     "type": "text",
    #                     "text": link
    #                 }
    #             ]}

    #         ]} 
    #     }


    amount = int(int(amount)*100)


    incoming_data ={
  "messaging_product": "whatsapp",
  "to": from_number,
  "type": "interactive",
  "interactive": {
    "type": "order_details",
    "header": {
      "type": "image",
      "image": {
        "link": "https://dnb.care2connect.in/c2c_banner.png" 
    }},
    "body": {
      "text": "*Please pay ₹3.00 to confirm this appointment. **This Payment link will be valid for next five minutes only"
    },
    "action": {
      "name": "review_and_pay",
      "parameters": {
        "reference_id": link,
        "type": "digital-goods",
        "currency": "INR",
        "total_amount": {
          "value": amount,
          "offset": 100
        },
        "payment_settings": [
          {
            "type": "payment_gateway",
            "payment_gateway": {
              "type": "razorpay",
              "configuration_name": "razorpay"
            }
          }
        ],
        "order": {
          "status": "pending",
          "items": [
            {
              "retailer_id": "Appointment_fee",
              "name": "Appointment Fee",
              "amount": {
                "value": amount,
                "offset": 100
              },
              "quantity": 1
            }
          ],
          "subtotal": {
            "value": amount,
            "offset": 100
          }
        }
      }
    }
  }
}



    response = requests.post(external_url, json=incoming_data, headers=headers)

    expiry_thread = Thread(target=payment_link_canceled, args=(link, from_number))
    expiry_thread.start()

    print(response)
    return 'ok', 200


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




def current_success_appointment(name,whatsapp_no,doc_id):
    url = f"https://graph.facebook.com/v22.0/794530863749639/messages"
    payload = { 
        "messaging_product": "whatsapp", 
        "to": whatsapp_no, "type": "template", 
        "template": { 
            "name": "payment_complated_current", 
            "language": { 
                "code": "en" 
            },
            "components": [
                {
                    "type": "header",
                    "parameters":  []

                },
                 {
        "type": "body",
        "parameters": [ {
                    "type": "text",
                    "text": name
                }
                
                
        ]
      },{
                "type": "button",
                "index": "0",
                "sub_type": "url",
                "parameters": [
                    {
                        "type": "text",
                        "text": doc_id
                    }
                ]}

            ]} 
        }
    

    response = requests.post(url, json=payload, headers=headers)
    return "ok", 200



def dr_current_success_appointment(name,fname,phone,payment_id,fee,number):
    url = f"https://graph.facebook.com/v22.0/794530863749639/messages"
    payload = { 
        "messaging_product": "whatsapp", 
        "to": number, "type": "template", 
        "template": { 
            "name": "dr_payment_alert", 
            "language": { 
                "code": "en" 
            },
            "components": [
                {
                    "type": "header",
                    "parameters":  []

                },
                 {
        "type": "body",
        "parameters": [ {
                    "type": "text",
                    "text": fee
                },
                {
                    "type": "text",
                    "text": name
                },
                {
                    "type": "text",
                    "text": fname
                },
                {
                    "type": "text",
                    "text": phone
                }
                
                
        ]
      },{
                "type": "button",
                "index": "0",
                "sub_type": "url",
                "parameters": [
                    {
                        "type": "text",
                        "text": payment_id
                    }
                ]}

            ]} 
        }
    

    response = requests.post(url, json=payload, headers=headers)
    return "ok", 200




# def send_payment_flow(from_number,name,date,slot,amount,link):


#     formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")

#     external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

#     incoming_data = { 
#         "messaging_product": "whatsapp", 
#         "to": from_number, "type": "template", 
#         "template": { 
#             "name": "dr_payment_link", 
#             "language": { 
#                 "code": "en" 
#             },
#             "components": [
#                 {
#                     "type": "header",
#                     "parameters":  []

#                 },
#                  {
#         "type": "body",
#         "parameters": [ {
#                     "type": "text",
#                     "text": amount
#                 }
         
#         ]
#       }, {
#                 "type": "button",
#                 "index": "0",
#                 "sub_type": "url",
#                 "parameters": [
#                     {
#                         "type": "text",
#                         "text": link
#                     }
#                 ]}

#             ]} 
#         }


#     response = requests.post(external_url, json=incoming_data, headers=headers)
#     return 'ok', 200




def success_appointment(payment_id,appoint_no,name,doa,time,whatsapp_no):

    formatted_date = datetime.strptime(doa, "%Y-%m-%d").strftime("%d-%m-%Y")


    appoint_no = str(appoint_no)

    
    img = generate_appointment_image(appoint_no,formatted_date,time,name,payment_id)
    # ok = compress_to_10kb(img, output_path="img.jpg")
    
    kk = imagesend(whatsapp_no)

    start_automation(whatsapp_no)

    # response = requests.post(url, json=payload, headers=headers)
    return f"whatsapp://send?phone=+918196961357"





def start_automation(from_number):
    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

    all_buttons = [
    {"id": "Receipt", "title": "Yes"},
    {"id": "no", "title": "No"}
    ]

# Function to send buttons in batches of 3
    def send_whatsapp_buttons(to_number, buttons_list):
        for i in range(0, len(buttons_list), 3):  # Send in groups of 3
            buttons = buttons_list[i:i+3]  # Get 3 buttons at a time

            payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Download Transaction Receipt?"},
                "action": {
                    "buttons": [{"type": "reply", "reply": btn} for btn in buttons]
                }
            }
        }

            response = requests.post(external_url, headers=headers, json=payload)
       
         

# Send multiple messages with 3 buttons per message
    send_whatsapp_buttons(from_number, all_buttons)

    # response = requests.post(external_url, json=payloadx, headers={'Authorization': 'Bearer EAAJdr829Xj4BOxyhp8MzkQqZCr92HwzYQMyDjZBhWZBqUej9YnYqTBefwyGeIZAUOhSk3y9AspLT69frxyYsWb6ea7jAGP4xm3BCxkAF5SXMqLeY3SpYt5AUUi0CkUIhk8AC6S1H6TIr0RLQHf3Tfo6ZBblcMZCBoc81nqVTidywfSK4FoWZAZCXenHHqRr5wAtE5D2tIGf87f8B7wuXUcWyK77Wca1ZBR3tqxQMOkK6L6BUZD','Content-Type': 'application/json'})
    # print(jsonify(response.json()))
    return "OK", 200



def imagesend(whatsapp_no):

    WHATSAPP_ACCESS_TOKEN = "EAAQNrOr6av0BPojE1zKKzKEDJWVmZBBvtBefl8aS24XBz4QcLzXPeF6wTlCBsIPFeOcwHi5AZBuXwkN6IfpI4uDjyLZAYRvMNF9jdVdeJ2WiNlnY1N1NpmFZBrJCSZAZCALx23ZArZA0jWnn0kEic6gY1Li4TFw8pZAnKZAmJtM0o6ZBfQZC8zi3v2EtcsoEnu9FutphkQZDZD"
    PDF_FILE_PATH = 'dimg.jpg'

    PHONE_NUMBER_ID = "794530863749639"


# API endpoint for media upload
    upload_url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/media"

# Headers
    headers = {
    "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"
    }

# File upload
    files = {
        "file": (PDF_FILE_PATH, open(PDF_FILE_PATH, "rb"), "image/jpeg"),
        "type": (None, "image/jpeg"),
        "messaging_product": (None, "whatsapp")
        }

    response = requests.post(upload_url, headers=headers, files=files)

    print(response)

# Print response
    print(response.json()['id'])


    PDF_FILE_ID = response.json()['id']  # Extracted from your provided data


        
    url = f"https://graph.facebook.com/v22.0/794530863749639/messages"

    payload = {
  "messaging_product": "whatsapp",
  "to": whatsapp_no,
  "type": "template",
  "template": {
    "name": "success_image",
    "language": {
      "code": "en"
    },
    "components": [
      {
        "type": "header",
        "parameters": [
          {
            "type": "image",
            "image": {
            #   "link": "https://78b9-2409-40c4-21c8-f1ea-8026-7db7-c465-cdae.ngrok-free.app/static/img.jpg"
            "id": PDF_FILE_ID
         
            }
          }
        ]
      },
      {
        "type": "body",
        "parameters": [
        ]
      }
    ]
  }
}


    

    response = requests.post(url, json=payload, headers=headers)

    print(response)

    return "OK", 200

def draw_justified_text(draw, text_lines, font, start_x, start_y, line_width, line_height, fill="black"):
    for line in text_lines:
        words = line.strip().split()
        if not words:
            start_y += line_height
            continue

        # Measure total width of words without spaces
        total_words_width = sum(draw.textlength(word, font=font) for word in words)
        total_spaces = len(words) - 1
        if total_spaces > 0:
            space_width = (line_width - total_words_width) / total_spaces
        else:
            space_width = 0

        x = start_x
        for i, word in enumerate(words):
            draw.text((x, start_y), word, font=font, fill=fill)
            x += draw.textlength(word, font=font) + (space_width if i < total_spaces else 0)
        start_y += line_height


def generate_appointment_image(number, date, time, name,c_date):



    date_str =c_date

# Convert string to datetime object
    given_date = datetime.strptime(date_str, "%Y-%m-%d")

# Add 3 days
    new_date = given_date + timedelta(days=2)

# Format the result back to string
    result = new_date.strftime("%d-%m-%Y")

    # Load background image
    background_path = "bgdr.jpg"  # Replace with actual path to your image
    background = Image.open(background_path).convert("RGB")
    background = background.resize((800, 800))

    draw = ImageDraw.Draw(background)
    scale = 800 / 800

    texts = [
        {"text": "Hello Dear " + name, "font_size": int(32 * scale), "y_offset": int(50 * scale)},
        {"text": "Your appointment has been confirmed", "font_size": int(32 * scale), "y_offset": int(90 * scale)},
        {"text": "Appointment No.", "font_size": int(28 * scale), "y_offset": int(200 * scale)},
        {"text": number, "font_size": int(150 * scale), "y_offset": int(240 * scale), "color": "green"},
        {"text": "Date - " + date, "font_size": int(36 * scale), "y_offset": int(460 * scale)},
        {"text": "Time - " + time, "font_size": int(36 * scale), "y_offset": int(520 * scale)},
    ]

    # Font path (Ensure the font file exists or change to a system font path)
    bold_font_path = "pt.ttf"

    # Draw main text items
    for item in texts:
        text = item["text"]
        font_size = item["font_size"]
        y_offset = item["y_offset"]
        color = item.get("color", "black")

        try:
            font = ImageFont.truetype(bold_font_path, font_size)
        except OSError:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (background.width - text_width) / 2
        draw.text((x, y_offset), text, font=font, fill=color)

    # Disclaimer text (justified)
    disclaimer_points = [
        "*Disclaimer:",
        f"1. Your appointment is valid till {result} during regular",
        "OPD hours. No consultation fee will be charged during this period.",
        "2. While we strive to honor all appointment times, please note that",
        "there may be delays due to unforeseen emergencies or circumstances",
        "beyond our control. We appreciate your patience and understanding."
    ]

    try:
        disclaimer_font = ImageFont.truetype(bold_font_path, 24)
    except OSError:
        disclaimer_font = ImageFont.load_default()

    # Calculate bottom margin positioning
    line_height = 30
    total_lines = len(disclaimer_points)
    total_disclaimer_height = total_lines * line_height
    start_y = 800 - 20 - total_disclaimer_height  # Ensure 20px bottom margin

    draw_justified_text(
        draw=draw,
        text_lines=disclaimer_points,
        font=disclaimer_font,
        start_x=40,
        start_y=start_y,
        line_width=720,  # 800 width minus 2*40 padding
        line_height=line_height,
        fill="black"
    )

    # Save the image
    background.save("dimg.jpg")
    return background










def dateandtime(id,did):
        if id == 'date':
            doc_id = ObjectId(did)
            document = doctors.find_one({"_id": doc_id})
            datas = document

            def get_next_7_days():
                today = datetime.now(ZoneInfo("Asia/Kolkata"))
                dates = [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(8)]
                return dates

            disabled_dates = get_next_7_days()

            data = datas['date']['disabledate']
            data_names = {item["name"] for item in data}
            formatted_output = [
                {"id": date, "title": date, "enabled": False} if date in data_names else {"id": date, "title": date}
                for date in disabled_dates
                ]
    
            current_time = datetime.now(ZoneInfo("Asia/Kolkata")).time()

            cutoff_time = datetime.strptime("08:30AM", "%I:%M%p").time()

            print(cutoff_time)

            is_before_8am = current_time < cutoff_time

            if not is_before_8am and data:
                formatted_output.pop(0)
            

            return formatted_output

        else:


            doc_id = ObjectId(did)
            document = doctors.find_one({"_id": doc_id})
            datas = document


            appoint = list(appointment.find({"doctor_phone_id": did, "date_of_appointment":id,"amount":{"$gt": -1}}, {"_id": 0}))
            
            if appoint:

                time_slots = [entry['time_slot'] for entry in appoint]

                time_counts = Counter(time_slots)

# Convert to required format
                result = [{"time": time, "number": count} for time, count in time_counts.items()]

                xslot = datas['slots']['slotsvalue']

                formatted_output = [
                {
                    "id": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+ datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                    "title": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                    "maxno": item["maxno"]
                }
                for index, item in enumerate(xslot)
                ]

                arry1 = result
                arry2 = formatted_output

# Convert arry1 into a dictionary for quick lookup
                time_counts = {item['time']: item['number'] for item in arry1}

# Process and apply conditions
                result = [
                {
                "id": item['id'],
                "title": item['title'],
                "enabled": False if time_counts.get(item['title'], 0) >= int(item['maxno']) else True
                }
                for item in arry2
                ]

# Remove "enabled": True for cleaner output
                for obj in result:
                    if obj["enabled"]:
                        del obj["enabled"]

                disabled_slots = []

                documentsst = list(disableslot.find({'date':id}))
                if documentsst:


                    disabled_slots = documentsst

# Create a set of disabled slot times for easy lookup
                disabled_set = {item["slot"] for item in disabled_slots if not item["enable"]}

                print(disabled_set)

# Add 'enabled' field to slots accordingly
                updated_slots = []
                for slot in result:
                    if slot["id"] in disabled_set:
                        updated_slots.append({**slot, "enabled": False})
                    else:
                        updated_slots.append(slot)
                        
                return updated_slots
            else:
                xslot = datas['slots']['slotsvalue']

                formatted_output = [
                {
                     "id": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+ datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                    "title": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                }
                for index, item in enumerate(xslot)
                ]

                disabled_slots = []

                documentsst = list(disableslot.find({'date':id}))
                if documentsst:
                    disabled_slots = documentsst

                # disabled_slots = [
                #     {"date": "2025-04-09", "slot": "09:00 AM - 10:00 AM", "enable": False},
                #     {"date": "2025-04-09", "slot": "02:00 PM - 03:00 PM", "enable": False},
                # ]

# Create a set of disabled slot times for easy lookup
                disabled_set = {item["slot"] for item in disabled_slots if not item["enable"]}

                print(disabled_set)

# Add 'enabled' field to slots accordingly
                updated_slots = []
                for slot in formatted_output:
                    if slot["id"] in disabled_set:
                        updated_slots.append({**slot, "enabled": False})
                    else:
                        updated_slots.append(slot)

                return updated_slots



def currentdateverify(did):
            doc_id = ObjectId(did)
            document = doctors.find_one({"_id": doc_id})
            datas = document

            def get_next_7_days():
                today = datetime.now(ZoneInfo("Asia/Kolkata"))
                dates = [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1)]
                return dates

            disabled_dates = get_next_7_days()

            data = datas['date']['disabledate']
            data_names = {item["name"] for item in data}
            formatted_output = [
                {"id": date, "title": date, "enabled": False} if date in data_names else {"id": date, "title": date}
                for date in disabled_dates
                ]
            
            return formatted_output[0]






@demo_doctor.route("/fatch_date_and_time/<string:id>/<string:did>", methods=["GET"])
def get_datetime(id,did):
    users = dateandtime(id, did) # Exclude MongoDB's default _id field
    return jsonify(users)


@demo_doctor.route("/fatch_current_date/<string:did>", methods=["GET"])
def get_datetimekk(did):
    users = currentdateverify(did) # Exclude MongoDB's default _id field
    return jsonify(users)






def expire_payment_link(payment_link_id, rzid, rzk):
    """Expires a Razorpay payment link by sending a POST to /cancel."""
    url = f"https://api.razorpay.com/v1/payment_links/{payment_link_id}/cancel"
    auth = (rzid, rzk)
    
    # Wait for 5 minutes (300 seconds)
    time.sleep(300)

    response = requests.post(url, auth=auth)

    # appointment_flow(from_number)
    # send_selection_enroll(from_number)
    # utc_now = datetime.now(ZoneInfo("UTC"))
    # future_time = utc_now + timedelta(minutes=5)
    # tempdata = {"number":from_number,"_id":from_number,"expiretime":future_time}
    # templog.update_one({'_id': from_number}, {'$set': tempdata})

    if response.status_code == 200:
        print("Payment link expired successfully.")
    else:
        print("Failed to expire payment link:", response.text)


def pay_link(name, number, email, id, rs, rzid, rzk):
    """
    Creates a Razorpay payment link and schedules it to expire after 5 minutes.
    Returns the payment ID or 'x' if failed.
    """
    # Razorpay API URL
    url = "https://api.razorpay.com/v1/payment_links"

    # Payment Data
    data = {
        "amount": int(rs * 100),  # Convert to paise
        "currency": "INR",
        "description": "Payment for service",
        "customer": {
            "name": name,
            # "email": email,
            "contact": number
        },
        "notify": {
            "sms": False,
            "email": False
        },
        "callback_url": f"https://api.care2connect.in/demo_doctor/payment_callback2/{id}/",
        "callback_method": "get"
    }

    # Send Request
    response = requests.post(url, auth=(rzid, rzk), json=data)

    if response.status_code == 200:
        payment_data = response.json()
        short_url = payment_data.get("short_url")
        payment_link_id = payment_data.get("id")

        print("Payment Link Created:", short_url)

        doc_id = ObjectId(id)
        appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':short_url,'payment_status':'link generated'}})

        # Start a background thread to auto-expire the link after 5 minutes
        expiry_thread = Thread(target=expire_payment_link, args=(payment_link_id, rzid, rzk))
        expiry_thread.start()

        # Extract and return payment ID from short_url
        match = re.search(r"/rzp/([\w\d]+)", short_url)
        if match:
            return match.group(1)
    else:
        print("Error creating payment link:", response.text)

    return 'x'


WEBHOOK_SECRET = "doctor"

@demo_doctor.route('/quick_razorpay_webhook', methods=['GET', 'POST'])
def razorpay_webhookupdated():
    try:
        payload = request.data
        received_signature = request.headers.get('X-Razorpay-Signature')

        # Create HMAC SHA256 signature
        generated_signature = hmac.new(
            WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        # Compare signatures
        if not hmac.compare_digest(generated_signature, received_signature):
            print("❌ Invalid signature")
            return jsonify({'status': 'unauthorized'}), 400

        # Signature verified
        data = json.loads(payload)
        print("✅ Webhook verified:", json.dumps(data, indent=2)) 

        event = data.get("event")

        if event == "payment_link.paid":
            payment = data["payload"]["payment"]["entity"]
            short_url = data["payload"]["payment_link"]["entity"]["short_url"]
            print("💰 Payment Received:", payment["id"], payment["amount"],short_url)

            retrieved_data = appointment.find_one({"razorpay_url": short_url})

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

            print('1')

            

            dxxocument = doctors.find_one({'_id':ObjectId('694e602ca1b88871ddbe2d23')})
            fee = float(dxxocument.get('appointmentfee'))

            print('1')


            index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)

            print('1')

            doc_id = ObjectId(retrieved_data['_id'])
            appointment.update_one({'_id': doc_id},{'$set':{'payment_status':'paid','status':'success','pay_id':payment["id"],'appoint_number':appoint_number,'amount':fee,'appointment_index':index_number}})

            print('1')
            name = str(retrieved_data['patient_name'])
            fname = str(retrieved_data['guardian_name'])
            payment_id = str(payment["id"])
            doa = str(retrieved_data['date_of_appointment'])
            tm = str(retrieved_data['time_slot'])
            phone = str(retrieved_data['whatsapp_number'])



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
    
                    count_txn = vouchers.count_documents({})
                    count = vouchers.count_documents({
                        "voucher_type": "Receipt",
                        "voucher_mode": "Bank",
                        "date": {"$gte": start, "$lt": end}   # between start and end of day
                    })
    
                    voucher_number = "BRV-"+ str(date_str) +'-'+ str(count + 1)
                    voucher = {
                        "amount":float(fee),
                        "voucher_number": voucher_number,
                        "voucher_type": 'Receipt',
                        "voucher_mode": "Bank",
                        "txn": count_txn + 1,
                        "doctor_id": retrieved_data['doctor_phone_id'],
                        "from_id": phone,
                        "to_id": payment_id,
                        "date": datetime.now(ZoneInfo("Asia/Kolkata")),
                        "Payment_id": payment_id,
                        "narration": 'Appointment Fee',
                        "entries": [
                    {
                    "narration": "Appointment Fee",
                    "ledger_id": "A1",
                    "ledger_name": "Razorpay",
                    "debit": float(fee),
                    "credit": 0
                    },
                    {
                    "narration": "Appointment Fee",
                    "ledger_id": "A2",
                    "ledger_name": "Doctor Fee Payble",
                    "debit": 0,
                    "credit": float(fee)-20
                    },
                    {
                    "narration": "Appointment Fee",
                    "ledger_id": "A3",
                    "ledger_name": "Platform Fee",
                    "debit": 0,
                    "credit": 16.95
                    },
                     {
                    "narration": "Appointment Fee",
                    "ledger_id": "A6",
                    "ledger_name": "GST Payable",
                    "debit": 0,
                    "credit": 3.05
                    }       
                    ],
                        "created_by": "system",
                        "created_at": ist_now
                    }
                    vouchers.insert_one(voucher)
            except:
                print(2)

            if tm=="current":
                print('currenet',name,phone)

                whatsapp_url = current_success_appointment(name,phone,payment_id)
                whatsapp_url = dr_current_success_appointment(name,fname,phone,payment_id,fee,'918128265003')
                whatsapp_url = dr_current_success_appointment(name,fname,phone,payment_id,fee,'916265578975')
            else :
                print('non-current',name,phone)
                whatsapp_url = success_appointment(doa,index_number,name,doa,tm,phone)


            return jsonify({'status': 'success'}), 200
           
        return jsonify({'status': 'success'}), 200

    except Exception as e:
        print("⚠️ Exception:", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500
    


@demo_doctor.route('/payment_callback2/<string:id>/', methods=['GET', 'POST'])
def payment_callback2(id):
    if request.method == 'GET':
        # Handle GET callback
        callback_data = request.args.to_dict()
    else:  # POST
        # Handle POST callback
        callback_data = request.json

    # Process the Razorpay response
    print("Callback Data:", callback_data)

    # Verify the payment status and act accordingly
    if callback_data.get('razorpay_payment_link_status') == 'paid':
        return redirect("whatsapp://send?phone=+918196961357")
    else:
        # Payment failed or was not captured
        print("Payment failed or not captured!")
        return jsonify({'status': 'failed', 'message': 'Payment failed or not captured'}), 400




def receiptme(from_number):

    document = templog.find_one({'_id':from_number})
    appoint_data = appointment.find_one({"_id": ObjectId(document["current_id"])})

    R_number = appointment.count_documents({"doctor_phone_id":'694e602ca1b88871ddbe2d23',"amount":{"$gt": -1}})


    name = appoint_data.get('patient_name')
    doa = appoint_data.get('date_of_appointment')
    date_str = doa
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    dformatted_date = str(date_obj.strftime("%d-%m-%Y"))


    time = appoint_data.get('time_slot')
    
    pay_id = str(appoint_data.get('pay_id'))
    amount = str(appoint_data.get('amount'))



    timestamp = int(appoint_data.get('timestamp'))
    date = datetime.fromtimestamp(timestamp)
    formatted_date = date.strftime('%d-%m-%Y')




    class PDF(FPDF):
        def header(self):
            self.set_fill_color(25, 42, 86)  # RGB for dark blue
            self.rect(0, 0, 210, 55, 'F')    # Full-width rectangle for header

            # Add logo on the top left corner
            self.image("icon.png", 10, 10, 25)  # (file, x, y, width)

            # Move to the right of the logo for text
            self.set_xy(40, 15)  # X=40 to move right of logo, Y=15 for vertical centering
            self.set_font("Arial", "B", 16)
            self.set_text_color(255, 255, 255)  # White text
            self.cell(0, 10, "", ln=True, align="L")
            self.ln(5)

        def add_appointment_details(self):
            # RED BACKGROUND SECTION ABOVE APPOINTMENT DETAILS
            self.set_fill_color(25, 42, 86) 
            self.set_text_color(255, 255, 255)  # White text
            # self.rect(0, 0, 210, 125, 'F') 
            self.set_font("Arial", "B", 18)
            self.cell(0, 10, "Dr. Neeraj Bansal Child Care Centre", ln=True, fill=True , align='C')

            self.set_font("Arial", "", 12)
            self.cell(0, 10, "Kalra Multispeciality Hospital, Opposite Street no 4, Ajit Road, Bathinda - 151001, Punjab", ln=True, fill=True, align='C')
            self.ln(10)

            self.set_text_color(0, 0, 0)
            self.set_font("Arial", "", 12)
            self.cell(0, 10, "Your appointment is confirmed", ln=True)
            self.ln(5)

            # Appointment intro
            self.set_text_color(0, 0, 0)
            self.set_font("Arial", "", 12)
            self.cell(0, 10, "Hello "+name+" ,", ln=True)
            self.ln(5)
            self.multi_cell(0, 10, "Thanks for booking an appointment on Care2Connect. Here are the details of your transaction:")
            self.ln(5)

            # Appointment details table
            self.set_font("Arial", "B", 12)
            self.cell(50, 10, "Doctor's name:", 1)
            self.set_font("Arial", "", 12)
            self.cell(0, 10, "Dr. Neeraj Bansal", 1, ln=True)

            self.set_font("Arial", "B", 12)
            self.cell(50, 10, "Date of Appointment:", 1)
            self.set_font("Arial", "", 12)
            self.cell(0, 10, dformatted_date, 1, ln=True)



            self.set_font("Arial", "B", 12)
            self.cell(50, 10, "Time Slot:", 1)
            self.set_font("Arial", "", 12)
            self.cell(0, 10, time, 1, ln=True)

            self.set_font("Arial", "B", 12)
            self.cell(50, 10, "Date of Transaction:", 1)
            self.set_font("Arial", "", 12)
            self.cell(0, 10,formatted_date, 1, ln=True)




            self.set_font("Arial", "B", 12)
            self.cell(50, 10, "Consultation fee:", 1)
            self.set_font("Arial", "", 12)
            self.cell(0, 10,amount+"/-", 1, ln=True)



            self.set_font("Arial", "B", 12)
            self.cell(50, 10, "Transaction ID:", 1)
            self.set_font("Arial", "", 12)
            self.cell(0, 10, pay_id, 1, ln=True)

            self.set_font("Arial", "B", 12)
            self.cell(50, 10, "Receipt No:", 1)
            self.set_font("Arial", "", 12)
            self.cell(0, 10, "A"+str(R_number+1), 1, ln=True)

            self.ln(10)
            self.set_font("Arial", "", 12)
            self.multi_cell(0, 10, "This is a computer generated document and doesn`t require signature.")
            self.ln(5)

            # self.set_text_color(0, 150, 255)
            # self.cell(0, 10, "Manage your appointments better by visiting My Appointments", ln=True)

    # Generate and save the PDF
    pdf = PDF()
    pdf.add_page()
    pdf.add_appointment_details()
    pdf.output("receipt.pdf")

    try:
        WHATSAPP_ACCESS_TOKEN = "EAAQNrOr6av0BPojE1zKKzKEDJWVmZBBvtBefl8aS24XBz4QcLzXPeF6wTlCBsIPFeOcwHi5AZBuXwkN6IfpI4uDjyLZAYRvMNF9jdVdeJ2WiNlnY1N1NpmFZBrJCSZAZCALx23ZArZA0jWnn0kEic6gY1Li4TFw8pZAnKZAmJtM0o6ZBfQZC8zi3v2EtcsoEnu9FutphkQZDZD"
        PDF_FILE_PATH = 'receipt.pdf'

        PHONE_NUMBER_ID = "794530863749639"


# API endpoint for media upload
        upload_url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/media"

# Headers
        headers = {
    "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"
    }

# File upload
        files = {
        "file": (PDF_FILE_PATH, open(PDF_FILE_PATH, "rb"), "application/pdf"),
        "type": (None, "application/pdf"),
        "messaging_product": (None, "whatsapp")
        }

        response = requests.post(upload_url, headers=headers, files=files)

        print(response)

# Print response
        print(response.json()['id'])


        RECIPIENT_NUMBER = from_number  # Format: "91xxxxxxxxxx"
        PDF_FILE_ID = response.json()['id']  # Extracted from your provided data

# API endpoint
        url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

# Headers
        headers = {
    "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
    "Content-Type": "application/json"
    }

# Message payload
        data = {
    "messaging_product": "whatsapp",
    "to": RECIPIENT_NUMBER,
    "type": "document",
    "document": {
        "id": PDF_FILE_ID,  # Reference to the uploaded PDF file
        "caption": "Here is your Receipt"
    }
    }

# Sending request
        response = requests.post(url, headers=headers, json=data)
# Print response
        print(response.status_code, response.json())

        return "ok",200
    except Exception as e:
        return e,400



def sendthankyou(recipientNumber):
    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"
    payload = {
  'messaging_product': 'whatsapp',
  'receipient_type':"individual",
  'to': recipientNumber,
  'text':{'body':'Thank You & Have a Good Day'},
  'type': 'text'
    }
    response = requests.post(external_url, json=payload, headers=headers)

    print(response)

    return "OK", 200


def sendattandence(recipientNumber,timestamp,btntype,id,r):
    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"
    ist_time = datetime.fromtimestamp(int(timestamp), ZoneInfo("Asia/Kolkata"))
    ist_time = ist_time.strftime("%d %B %Y at %I:%M %p")
    payload = {
  'messaging_product': 'whatsapp',
  'receipient_type':"individual",
  'to': recipientNumber,
  'text':{'body':f"✅ Your request for {btntype} on {ist_time} has been successfully submitted."},
  'type': 'text'
    }

    result = duniyapedb.attendance.update_one(
            {"_id": ObjectId(id)},
            {"$set": {'status':r}}
        )
    response = requests.post(external_url, json=payload, headers=headers)

    print(response)

    return "OK", 200


import math
def attendence(data):

    fromNum = data.get("from")
    timestamp = int(data.get("timestamp"))
    lat = float(data['location']['latitude'])
    long = float(data['location']['longitude'])

    ist_time = datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Kolkata"))
    ist_time = ist_time.strftime("%d %B %Y at %I:%M %p")

    print(lat,long,ist_time)

    def calculate_distance(lat1, lon1, lat2, lon2):
        R = 6371000  # Earth radius in meters

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * \
            math.sin(delta_lambda / 2) ** 2

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c
        return distance
    

    distance = calculate_distance(30.2093572, 74.9552614, lat, long)

    print("Distance:", distance, "meters")
    payload = {}
    if distance <= 50:
        
        

        employee = duniyapedb.staff.find_one({
            'designation': ObjectId('699adeffef0f329d90a0f35e'),
            'phone': fromNum
        })

        if employee:
            emp_name = employee.get('name')

            xist_time = datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Kolkata"))

            data = {
                'name': emp_name,
                'phone': fromNum,
                'status': 'P',
                'role': 'attendance',
                'date':  xist_time,
                'lat': lat,
                'long': long
            }
            payload = {
  'messaging_product': 'whatsapp',
  'receipient_type':"individual",
  'to': fromNum,
  'text':{'body':f"✅ Your attendance for {ist_time} has been successfully recorded."},
  'type': 'text'
    }

            result = duniyapedb.attendance.insert_one(data)
            print('Attendance updated successfully')
        else:
            print('User not found')


    else:

        
        

        employee = duniyapedb.staff.find_one({
            'designation': ObjectId('699adeffef0f329d90a0f35e'),
            'phone': fromNum
        })

        if employee:
            emp_name = employee.get('name')

            xist_time = datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Kolkata"))

            data = {
                'name': emp_name,
                'phone': fromNum,
                'status': 'U',
                'role': 'attendance',
                'date':  xist_time,
                'lat': lat,
                'long': long
            }

            result = duniyapedb.attendance.insert_one(data)
            inserted_id = result.inserted_id 
            payload = {
  "messaging_product": "whatsapp",
  "to": fromNum,
  "type": "interactive",
  "interactive": {
    "type": "button",
    "body": {
      "text": "Location is outside 50 meters"
    },
    "footer": {
      "text": "Please choose one option:"
    },
    "action": {
      "buttons": [
        {
          "type": "reply",
          "reply": {
            "id": f"o_{inserted_id}",
            "title": "Apply Official Duty"
          }
        },
        {
          "type": "reply",
          "reply": {
            "id": f"l_{inserted_id}",
            "title": "Apply for Leave"
          }
        }
        # ,
        # {
        #   "type": "reply",
        #   "reply": {
        #     "id": "btn_later",
        #     "title": "Later"
        #   }
        # }
      ]
    }
  }
}
            
            print('Attendance updated successfully')
        else:
            print('User not found')
        

    
    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"
    response = requests.post(external_url, json=payload, headers=headers)

    print(response)

    return "OK", 200





def pdfdownload(from_number,zxdate):
    
    date_obj = datetime.strptime(zxdate, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%d-%m-%Y")
    
    doc_id = ObjectId("694e602ca1b88871ddbe2d23")
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

    # print(formatted_output)
    # current_time = datetime.now(ZoneInfo("Asia/Kolkata")).time()
    # cutoff_time = datetime.strptime("03:07PM", "%I:%M%p").time()

    # is_before_8am = current_time < cutoff_time
    # if is_before_8am==False:
    #     formatted_output = formatted_output[6:]
    # else:
    #     formatted_output = formatted_output[:-2]




    json_data = list(appointment.find({"amount":{"$gt": -1},"date_of_appointment":zxdate, "doctor_phone_id": '694e602ca1b88871ddbe2d23'}))

#     print(json_data)

    custom_array = []

    for slot in formatted_output:
        slot_data = [appt for appt in json_data if appt["time_slot"] == slot["slot"]]

        while len(slot_data) < int(slot["length"]):
                slot_data.append({
                     'patient_name': ' ',
                     'appoint_number':' ',
                     'time_slot':slot["slot"],
                     'date_of_birth':' ',
                     'whatsapp_number':' ',
                     'pay_id':' ',
                     'city':' ',
                     'vaccine':' '
                     })
        # slot_data.reverse()
    
        custom_array.extend(slot_data)

    # print(custom_array)
    json_data = custom_array
    if json_data:

# Convert JSON data to table format
        table_data = [["S.No",
                        # "Appointment No.",
                        #   "Time Slot",
                            "Name",
                        # "Guardian Name",
                          "Date of Birth", "WhatsApp No.",
                        #   "Payment ID",
                          "City","vaccine",
                          "Type",
                          "Remark"]]  # Table header

        for i, item in enumerate(json_data, start=1):

            aptype = "Reappointment" if item["pay_id"].startswith("old") else ""
                
            table_data.append([
        str(i),  # Serial number
        # item["appoint_number"],
        # item["time_slot"],
        item["patient_name"], 
        # item["guardian_name"],
        item["date_of_birth"], 
        item["whatsapp_number"], 
        # item["pay_id"], 
        item["city"],
        item["vaccine"],
        aptype,
        "        ",
        ])
# Create a PDF file
        pdf_filename = "output_table.pdf"
        pdf = SimpleDocTemplate(pdf_filename, pagesize=letter)


# Create table
        table = Table(table_data)

# Add style to the table
        style = TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, -1), 8),  # Set font size to 12px
    ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        print_date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
        table.setStyle(style)

        print_date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y %H:%M:%S")
        styles = getSampleStyleSheet()
        header_left = Paragraph(f"<b>List of Appointments Dated : {formatted_date}</b>", ParagraphStyle(name="LeftHeader", fontSize=10))
        header_right = Paragraph(f"<i>Printed on: {print_date}</i>", ParagraphStyle(name="RightHeader", fontSize=10, alignment=2))
        header_table = Table([[header_left, header_right]], colWidths=[300, 240])  # Adjust if needed

        pdf.build([header_table, Spacer(1, 10), table])

  
    


        WHATSAPP_ACCESS_TOKEN = "EAAQNrOr6av0BPojE1zKKzKEDJWVmZBBvtBefl8aS24XBz4QcLzXPeF6wTlCBsIPFeOcwHi5AZBuXwkN6IfpI4uDjyLZAYRvMNF9jdVdeJ2WiNlnY1N1NpmFZBrJCSZAZCALx23ZArZA0jWnn0kEic6gY1Li4TFw8pZAnKZAmJtM0o6ZBfQZC8zi3v2EtcsoEnu9FutphkQZDZD"
        PDF_FILE_PATH = pdf_filename

        PHONE_NUMBER_ID = "794530863749639"


# API endpoint for media upload
        upload_url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/media"

# Headers
        headers = {
    "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"
    }

# File upload
        files = {
        "file": (PDF_FILE_PATH, open(PDF_FILE_PATH, "rb"), "application/pdf"),
        "type": (None, "application/pdf"),
        "messaging_product": (None, "whatsapp")
        }

        response = requests.post(upload_url, headers=headers, files=files)

        # print(response)

# Print response
        print(response.json()['id'])


        RECIPIENT_NUMBER = from_number  # Format: "91xxxxxxxxxx"
        PDF_FILE_ID = response.json()['id']  # Extracted from your provided data

# API endpoint
        url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

# Headers
        headers = {
    "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
    "Content-Type": "application/json"
    }

# Message payload
        data = {
    "messaging_product": "whatsapp",
    "to": RECIPIENT_NUMBER,
    "type": "document",
    "document": {
        "id": PDF_FILE_ID,  # Reference to the uploaded PDF file
        "caption": "Here is your PDF file."
    }
    }

# Sending request
        response = requests.post(url, headers=headers, json=data)
# Print response
        print(response.status_code, response.json())

        return "ok",200
    else:
        return "ok",200


@demo_doctor.route("/payment_done/<string:id>", methods=["GET"])
def redirect_razorpay_payment(id):
    try:
        retrieved_data = appointment.find_one({"pay_id": id})
        dates = retrieved_data['date_of_appointment']
        name = retrieved_data['patient_name']
        father = retrieved_data['guardian_name']
        number = retrieved_data['whatsapp_number']
        pay_id = retrieved_data['pay_id']
        amount = retrieved_data['amount']
        whatsid = '918196961357'
        atype = "Current Booking"
        try:
            if retrieved_data['appointmenttype']=="current":
                atype = "Current Booking"
            else:
                atype = "Advance Booking"
        except:
            atype = "Advance Booking"
        if retrieved_data['doctor_phone_id']=='67ee5e1bde4cb48c515073ee':
            whatsid = '919646465003'
        return render_template('sccesspage.html', dates=dates,name=name,father=father,number=number,pay_id=pay_id,amount=amount,whatsnum=whatsid, atype=atype)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def appointment_flow_expire(from_number):

    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL

    incoming_data = { 
    "messaging_product": "whatsapp", 
    "to": from_number, 
    "type": "template", 
    "template": { 
        "name": "expire_after_send", 
        "language": { "code": "en" },
        "components": [
            {
                "type": "header"
            },
            {
                "type": "body",
                "parameters": []
            },
            {
                "type": "button",
                "sub_type": "flow",  
                "index": "0"  
            }
        ]
    } 
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    # print(jsonify(response.json()))
    return "OK", 200
