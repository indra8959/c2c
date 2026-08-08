from flask import Flask, request, jsonify,redirect,Response,render_template
from pymongo import MongoClient
import re
from datetime import datetime, timedelta
import time
import json
# import datetime
from receipt import receiptme
from appoint_flow import book_appointment, sendthankyou, appointment_flow, success_appointment,old_user_send,custom_appointment_flow,same_name,send_selection,send_selection_enroll, send_pdf_utility, appointment_flow_expire,send_payment_flow, appointment_flow_advance, dr_advance_success_appointment
from bson.objectid import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
from pdf import pdfdownload,pdfdownloadcdate,pdfdownloadinapi,taxpdfdownload1, pdfdownloadsplit
from date_and_slots import dateandtime, currentdateverify, dateandtime2, nextdateverify
from zoneinfo import ZoneInfo
import hmac
import hashlib
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
# import requests
# from requests.auth import HTTPBasicAuth
from api_files.create_ledger import accounting_bp
from api_files.doctors import doctor_bp
from api_files.auth import auth_bp
from api_files.appointments import appointment_bp
from api_files.slots import slot_bp
from api_files.duniyape.routes import duniyape_bp
from api_files.duniya_enterprises.routes import duniya_enterprises
from api_files.new_hqz_transport.routes import new_hqz_transport
from doctors.demo_doctor import demo_doctor
from api_files.vivekanand.app_server import vivekanand
from doctors.kalramindcare import kalra_mindcare
from api_files.c2c_mobile_app.c2c_app import c2c_app

from doctors.functions.route_split import create_transfers
from doctors.functions.receipt import download_receipt_selection, receiptselection

from doctors.functions.Refund import function_refund
from doctors.functions.settlement import function_settlement

from doctors.functions.doctor_payble import send_doctor_vouchers_excel,report_reply

app = Flask(__name__)
CORS(app)

app.register_blueprint(accounting_bp, url_prefix="/accounting")
app.register_blueprint(doctor_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(appointment_bp, url_prefix="/appointments")
app.register_blueprint(slot_bp)
app.register_blueprint(duniyape_bp, url_prefix="/duniyape")
app.register_blueprint(duniya_enterprises, url_prefix="/duniya_enterprises")
app.register_blueprint(new_hqz_transport, url_prefix="/new_hqz_transport")
app.register_blueprint(demo_doctor, url_prefix="/demo_doctor")
app.register_blueprint(vivekanand, url_prefix="/vivekanand")
app.register_blueprint(kalra_mindcare, url_prefix="/kalra_mindcare")
app.register_blueprint(c2c_app, url_prefix="/c2c_app")

app.register_blueprint(function_refund, url_prefix="/function_refund")
app.register_blueprint(function_settlement, url_prefix="/function_settlement")
# razorpay


# rzp_test_N6qQ6xBkec7ER4
# fbKeii72zk6xbaUoJITOPqP8

# rzp_live_wM3q1LR9LLJA1F
# XFAR0gGwtjqTKuwt777kAKvx

MONGO_URI = "mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.get_database("caredb")
doctors = db["doctors"] 
appointment = db["appointment"] 
templog = db["logs"] 
disableslot = db["disableslot"] 
vouchers = db["vouchers"] 
patient = db["patient"] 
requestdb = db["requests"]
opd_requests = db["opd_requests"]
templog2 = db["tempdata"]
API_KEY = "1234"


mogngo='mongodb+srv://pankajji442:N7EYdibmOQ4vPk0x@cluster1.rapvnpk.mongodb.net/'
Logdb = MongoClient(mogngo).get_database("Logscreen")
logs= Logdb['logs']

# Create unique index
logs.create_index("unique_id", unique=True)
logs.create_index("createdAt",expireAfterSeconds=300)
# logs.create_index("createdAt",expireAfterSeconds=172800)

# Home Route
# 8128265003 doctor number
def scheduled_task():
    # today_date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    # pdfdownload('916265578975',today_date)
    # pdfdownload('918128265003',today_date)
    # pdfdownload('918959690512',today_date)
    # print(f"Task running at {datetime.now()}")
    # send_pdf_utility('916265578975')
    # send_pdf_utility('918959690512')
    send_pdf_utility('918128265003')
    send_pdf_utility('918968804953')
    send_pdf_utility('917087778151')
    send_pdf_utility('918968965882')
    # send_pdf_utility('918959690512')


# Setup scheduler
scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Kolkata"))
scheduler.add_job(
    func=scheduled_task,
    trigger=CronTrigger(hour=8, minute=45, timezone=ZoneInfo("Asia/Kolkata"))
)
# scheduler.add_job(
#     func=scheduled_task,
#     trigger=CronTrigger(hour=15, minute=10, timezone=ZoneInfo("Asia/Kolkata"))
# )
scheduler.start()

# Clean shutdown
import atexit
atexit.register(lambda: scheduler.shutdown())


@app.route("/")
def home():
    return "updated 6.7"

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


@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        VERIFY_TOKEN = "desitestt1"
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode and token == VERIFY_TOKEN:
            return challenge, 200
        return "Verification failed", 403
    elif request.method == 'POST':
        data = request.json
        # print("Received data:", data)

        try:


            entry = data.get('entry', [])[0]  # Extract first entry
            changes = entry.get('changes', [])[0]  # Extract first change
            value = changes.get('value', {})
            messages = value.get("messages", [])

            for msg in messages:

                try:

                    logs.insert_one({
                        "unique_id": msg.get("id"),
                        "event_type": "incoming_message",
                        "message": msg,
                        "createdAt": datetime.utcnow()
                    })

                except DuplicateKeyError:
                    pass

            # =========================
            # MESSAGE STATUS EVENTS
            # =========================
            statuses = value.get("statuses", [])

            for status in statuses:

                try:

                    status_id = status.get("id")
                    status_value = status.get("status")

                    unique_status_id = f"{status_id}_{status_value}"

                    logs.insert_one({
                        "unique_id": unique_status_id,
                        "event_type": "message_status",
                        "status": status,
                        "createdAt": datetime.utcnow()
                    })

                except DuplicateKeyError:
                    pass

            
            entry = data.get('entry', [])[0]  # Extract first entry
            changes = entry.get('changes', [])[0]  # Extract first change
            value = changes.get('value', {})

            try:
                status_obj = data["entry"][0]["changes"][0]["value"]["statuses"][0]
                print(status_obj)
                if status_obj.get("status") == "captured":
                    return payment_deduct(status_obj)
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
                    if button_id == "Re-Appointment":
                        return send_selection(from_number)
                    if button_id == "enrole-patient":
                        return send_selection_enroll(from_number)
                    elif button_id == "Receipt":
                        return receiptme(from_number)
                    elif button_id == "no":
                        return sendthankyou(from_number)
                    elif button_id == "Same_person":
                        return same_name(from_number,'same')
                    elif button_id == "Different_person":
                        return same_name(from_number,'deff')
                    elif button_id == "today":
                        return new_flow(from_number,"today")
                    elif button_id == "tomorrow":
                        return new_flow(from_number,"tomorrow")


                    elif button_id == "REPORT_DOWNLOAD_PDF_2025":
                        return send_doctor_vouchers_excel("67ee5e1bde4cb48c515073ee", from_number,"2025-04-01","2026-04-01","pdf")
                    elif button_id == "REPORT_DOWNLOAD_EXCEL_2025":
                        return send_doctor_vouchers_excel("67ee5e1bde4cb48c515073ee", from_number,"2025-04-01","2026-04-01","excel")
                    elif button_id == "REPORT_DOWNLOAD_PDF_2026":
                        return send_doctor_vouchers_excel("67ee5e1bde4cb48c515073ee", from_number,"2026-04-01","x","pdf")
                    elif button_id == "REPORT_DOWNLOAD_EXCEL_2026":
                        return send_doctor_vouchers_excel("67ee5e1bde4cb48c515073ee", from_number,"2026-04-01","x","excel")


                    elif button_id == "YES_STOP":
                        return update_status_copd('67ee5e1bde4cb48c515073ee',from_number)
                    elif button_id == "NO_CONTINUE":
                        return delete_copd_time('67ee5e1bde4cb48c515073ee',from_number)

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
                        return pdfdownloadsplit(from_number,today_date)
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

                        mydatetime = dateandtime2('date')

                        date_to_check = json_data2.get("Date_of_appointment_0")
                        exists = any(item['id'] == date_to_check and item.get("enabled", True) for item in mydatetime)
                        if exists:
                            return book_appointment(data)
                        elif role=='ex':
                            return 'ok', 200
                            # return appointment_flow_expire(from_number)
                        else:
                            tempdata = {"number":from_number,"_id":from_number,'store_data':data}
                            try:
                                templog.insert_one(tempdata)
                            except:
                                templog.update_one({'_id': from_number}, {'$set': tempdata})
                            return 'ok', 200
                            # return appointment_flow_expire(from_number)

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
                        if value.startswith("rcp_"):
                            appointment_id = value.replace("rcp_", "")
                            return receiptselection(from_number, appointment_id)
                        
                        elif value[:2]=="cb":
                            value = value[2:]
                            appoint_data = appointment.find_one({"_id": ObjectId(value)})
                            name = appoint_data.get('patient_name')
                            pname = appoint_data.get('guardian_name')
                            dob = appoint_data.get('date_of_birth')
                            sex = 'Male'
                            if appoint_data.get('sex'):
                                sex = appoint_data.get('sex')

                            return book_current_appointment_by_selectedlist(from_number,name,pname,timestamp,dob,sex)
                        else:
                            return custom_appointment_flow(from_number)
                        # return custom_appointment_flow(from_number)
                    except Exception as e:
                        return "Invalid message type", 400
                # elif msg_type == 'text' and body.lower() == "hii":
                #     print(body.lower())
                #     return old_user_send(from_number)
                # elif msg_type == 'text' and body.lower() == "st":
                #     print(body.lower())
                #     return send_selection_enroll(from_number)
                elif msg_type == 'text' and body.lower() == "hi":
                    # appointment_flow(from_number)
                    # send_selection_enroll(from_number)

                    hi_reply(from_number)
        
                    print(body.lower())

                    # utc_now = datetime.now(ZoneInfo("UTC"))
                    # future_time = utc_now + timedelta(minutes=5)
                    # tempdata = {"number":from_number,"_id":from_number,"expiretime":future_time}
                    # try:
                    #     templog.insert_one(tempdata)
                    # except:
                    #     templog.update_one({'_id': from_number}, {'$set': tempdata})

                    # return old_user_send(from_number)
                    return "ok",200

                elif msg_type == 'text' and body.lower() == "hlo":
                    hi_reply(from_number)
                    # appointment_flow(from_number)
                    # send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    # utc_now = datetime.now(ZoneInfo("UTC"))
                    # future_time = utc_now + timedelta(minutes=5)
                    # tempdata = {"number":from_number,"_id":from_number,"expiretime":future_time}
                    # try:
                    #     templog.insert_one(tempdata)
                    # except:
                    #     templog.update_one({'_id': from_number}, {'$set': tempdata})

                    # return old_user_send(from_number)
                    return "ok",200

                elif msg_type == 'text' and body.lower() == "hello":
                    hi_reply(from_number)
                    # appointment_flow(from_number)
                    # send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    # utc_now = datetime.now(ZoneInfo("UTC"))
                    # future_time = utc_now + timedelta(minutes=5)
                    # tempdata = {"number":from_number,"_id":from_number,"expiretime":future_time}
                    # try:
                    #     templog.insert_one(tempdata)
                    # except:
                    #     templog.update_one({'_id': from_number}, {'$set': tempdata})

                    # return old_user_send(from_number)
                    return "ok",200
                
                elif msg_type == 'text' and body.lower() == "test":
                    # appointment_flow(from_number)
                    # send_selection_enroll(from_number)
                    hi_reply(from_number)
                    print(body.lower())
                    return "ok",200
                
                elif msg_type == 'text' and body.lower() == "2026":
                    report_reply(from_number,"2026")
                    return "ok",200
                elif msg_type == 'text' and body.lower() == "2025":
                    report_reply(from_number,"2025")
                    return "ok",200
                elif msg_type == 'text' and body.lower() == "report":
                    report_reply(from_number,"2026")
                    return "ok",200

                

                elif msg_type == 'text' and body.lower() == "hii":
                    hi_reply(from_number)
                    # appointment_flow(from_number)
                    # send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    # utc_now = datetime.now(ZoneInfo("UTC"))
                    # future_time = utc_now + timedelta(minutes=5)
                    # tempdata = {"number":from_number,"_id":from_number,"expiretime":future_time}
                    # try:
                    #     templog.insert_one(tempdata)
                    # except:
                    #     templog.update_one({'_id': from_number}, {'$set': tempdata})

                    # return old_user_send(from_number)
                    return "ok",200

                elif msg_type == 'text' and body.lower() == "hallo":
                    hi_reply(from_number)
                    # appointment_flow(from_number)
                    # send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    # utc_now = datetime.now(ZoneInfo("UTC"))
                    # future_time = utc_now + timedelta(minutes=5)
                    # tempdata = {"number":from_number,"_id":from_number,"expiretime":future_time}
                    # try:
                    #     templog.insert_one(tempdata)
                    # except:
                    #     templog.update_one({'_id': from_number}, {'$set': tempdata})

                    # return old_user_send(from_number)
                    return "ok",200

                elif msg_type == 'text' and body.lower() == "rcp":
                    download_receipt_selection(from_number)
                    return "ok",200

                
                
                elif msg_type == 'text' and body.lower() == "list":
                    if from_number=="916265578975" or from_number=="918128265003" or from_number=="918968804953" or from_number=="917087778151" or from_number=="916283450048" or from_number=="918959690512" or from_number=="918968965882":
                        cd_url(from_number)
                    return "ok",200

                elif msg_type == 'text' and body.lower() == "refund":
                    if from_number=="918128265003" or from_number=="916265578975" or from_number=="918959690512":
                        refund_url(from_number)
                    return "ok",200

                elif msg_type == 'text' and body.lower() == "hy":
                    hi_reply(from_number)
                    # appointment_flow(from_number)
                    # send_selection_enroll(from_number)
                    # send_selection(from_number)
                    print(body.lower())

                    # utc_now = datetime.now(ZoneInfo("UTC"))
                    # future_time = utc_now + timedelta(minutes=5)
                    # tempdata = {"number":from_number,"_id":from_number,"expiretime":future_time}
                    # try:
                    #     templog.insert_one(tempdata)
                    # except:
                    #     templog.update_one({'_id': from_number}, {'$set': tempdata})

                    # return old_user_send(from_number)
                    return "ok",200
                
                elif msg_type == 'text' and body.lower() == "pay":
                    xxs = current_flow2(from_number)
                    dsds = send_selection_enroll_current(from_number)
                    # send_selection_enroll(from_number)
                    # send_selection(from_number)
                    # print(body.lower())

                    return "ok",200
                
                elif msg_type == 'text' and body.lower() == "pdf":
                    print(body.lower())
                    today_date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
                    if from_number=="916265578975" or from_number=="918128265003" or from_number=="918968804953" or from_number=="917087778151" or from_number=="916283450048" or from_number=="918959690512" or from_number=="918968965882":
                        return pdfdownload(from_number,today_date)
                    else:
                        return "ok",200
                elif msg_type == 'text' and body.lower() == "receipt":
                    print(body.lower())
                    return receiptme(from_number)
                elif msg_type == 'text' and body.lower() == "tax":
                    if from_number=="916265578975" or from_number=="918128265003" or from_number=="918968804953" or from_number=="917087778151" or from_number=="916283450048" or from_number=="918959690512":
                        today_date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
                        return taxpdfdownload1(from_number,today_date)
                    else:
                        return "ok",200
                    
                elif msg_type == 'text' and body.lower().split()[0] == "tax":
                    print(body.lower())

                    match = re.search(r"\d{2}-\d{2}-\d{4}", body.lower())
                    if match:
                        extracted_date = match.group()  # "20-03-2024"
    
    # Convert to "YYYY-MM-DD" format
                        formatted_date = datetime.strptime(extracted_date, "%d-%m-%Y").strftime("%Y-%m-%d")
    
                        print(formatted_date)
                    if from_number=="916265578975" or from_number=="918128265003" or from_number=="918968804953" or from_number=="917087778151" or from_number=="916283450048" or from_number=="918959690512":
                        return taxpdfdownload1(from_number,formatted_date)
                    else:
                        return "ok",200
                    
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






def new_flow(from_number,btn_type):

    from datetime import datetime, time

    now = datetime.now(ZoneInfo("Asia/Kolkata")).time()

    if btn_type == 'tomorrow':
        x = appointment_flow_advance(from_number)
        x = send_selection_enroll(from_number)
        return "8:30 AM se pahle",200

    elif now < time(8, 30):

        date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d-%m-%Y")


        headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
        external_url = "https://graph.facebook.com/v22.0/563776386825270/messages" 

        incoming_data = {
            "messaging_product": "whatsapp",
            "to": from_number,
            "type": "text",
            "text": {
                "body": f"Current Bookings will resume after 8:30 AM {date}. The booking window for Current Booking is open from 8:31 AM to 6:00 PM daily, Kindly schedule accordingly. Thank You"
            }
            }
        response = requests.post(external_url, json=incoming_data, headers=headers)
        return "8:30 AM se pahle",200



    elif time(8,30) <= now < time(15,0):
        xxs = current_flow2(from_number)
        dsds = send_selection_enroll_current(from_number)
        return "8:30 AM ke baad aur 3 PM se pahle",200

    elif time(15,0) <= now < time(18,0):
        xxs = current_flow2(from_number)
        dsds = send_selection_enroll_current(from_number)
        return "3 PM ke baad aur 6:00 PM se pahle",200

    else:



        headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
        external_url = "https://graph.facebook.com/v22.0/563776386825270/messages" 

        now = datetime.now(ZoneInfo("Asia/Kolkata"))

        cutoff = time(8, 30)  # 8:30 AM

        # decide booking date
        if now.time() >= cutoff:
            booking_date = now + timedelta(days=1)
        else:
            booking_date = now

        formatted_date = booking_date.strftime("%-d %B %Y")

        incoming_data = {
            "messaging_product": "whatsapp",
            "to": from_number,
            "type": "text",
            "text": {
                "body": f"Current Bookings will resume after 8:30 AM {formatted_date}. The booking window for Current Booking is open from 8:31 AM to 6:00 PM daily, Kindly schedule accordingly. Thank You"
            }
            }
        response = requests.post(external_url, json=incoming_data, headers=headers)
        return "6 PM ke baad",200



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
    
    payment_id = str(status_obj["payment"]["transaction"]["pg_transaction_id"])
    
    result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":retrieved_data['date_of_appointment'],"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
    data_length = 1
    if result:
        data_length = len(result)+1

    xdate = retrieved_data['date_of_appointment']
    date_obj = datetime.strptime(xdate, "%Y-%m-%d")
    formatted_date = date_obj.strftime("%Y%m%d")

    appoint_number = str(formatted_date)+'-'+str(data_length)

    print('1')

            

    dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
    fee = float(dxxocument.get('appointmentfee'))

    print('1')


    index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)

    print('1')

    doc_id = ObjectId(retrieved_data['_id'])
    doctor_amount = float(fee)-20
    transfer_id = create_transfers(payment_id,"acc_T8BUURNqf32EnL",doctor_amount)
    appointment.update_one({'_id': doc_id},{'$set':{'transfer_id':transfer_id,'payment_status':'paid','status':'success','pay_id':payment_id,'appoint_number':appoint_number,'amount':fee,'appointment_index':index_number}})

    print('1')
    fname = str(retrieved_data['guardian_name'])
    payment_id = str(status_obj["payment"]["transaction"]["pg_transaction_id"])
    name = str(retrieved_data['patient_name'])
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
    
            voucher_number_index = "BRV-"+ str(date_str)
            count_txn = vouchers.count_documents({})
            count = vouchers.count_documents({
                "voucher_type": "Receipt",
                "voucher_mode": "Bank",
                "voucher_number_index": voucher_number_index   # between start and end of day
            })
    
            voucher_number = "BRV-"+ str(date_str) +'-'+ str(count + 1)
            voucher = {
                        "voucher_number_index" : voucher_number_index,
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
                    "ledger_id": "A12",
                    "ledger_name": "CGST",
                    "debit": 0,
                    "credit": 3.05/2
                    },
                     {
                    "narration": "Appointment Fee",
                    "ledger_id": "A13",
                    "ledger_name": "SGST",
                    "debit": 0,
                    "credit": 3.05/2
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

        whatsapp_url = current_success_appointment(name,phone,payment_id, fee,fname)
       
        whatsapp_url = dr_current_success_appointment(name,fname,phone,payment_id,fee, '918128265003')
        whatsapp_url = dr_current_success_appointment(name,fname,phone,payment_id,fee, '918968804953')
        whatsapp_url = dr_current_success_appointment(name,fname,phone,payment_id,fee, '917087778151')
        whatsapp_url = dr_current_success_appointment(name,fname,phone,payment_id,fee, '918968965882')
        whatsapp_url = dr_current_success_appointment(name,fname,phone,payment_id,fee, '918959690512')

    else :
        print('non-current',name,phone)
        ss = dr_advance_success_appointment(name,phone,payment_id,"918959690512")
        ss = dr_advance_success_appointment(name,phone,payment_id,"918128265003")
        whatsapp_url = success_appointment(doa,index_number,name,doa,tm,phone)


    # whatsapp_url = success_appointment(doa,index_number,name,doa,tm,phone)

    print('1')

    return jsonify({'status': 'success'}), 200


def find_user():
    try:
        result = list(doctors.find({"phone": "8767"}, {"_id": 0}))  # Convert cursor to list, exclude '_id'
        if result:
            return result[0]
        else:
            return 404
    except Exception as e:
        return 404

@app.route('/logs', methods=['GET'])
def meta_logs():
    try:

        data = list(logs.find())

        # Convert ObjectId to string
        for item in data:
            item["_id"] = str(item["_id"])

        return jsonify({
            "success": True,
            "data": data
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route("/add_user", methods=["POST"])
def add_user_query():
    try:
        # api_key = request.headers.get("x-api-key")
        # if api_key != API_KEY:
        #     return jsonify({"error": "Unauthorized"}), 401
        data = request.json
        # password = data.get("password")
        # hashed_password = generate_password_hash(password)
        # data["password"] = hashed_password 
        result = doctors.insert_one(data).inserted_id
        return jsonify({"inserted_id": str(result)}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
# @app.route("/slot_disable", methods=["POST"])
# def slot_disable():
#     try:
#         # api_key = request.headers.get("x-api-key")
#         # if api_key != API_KEY:
#         #     return jsonify({"error": "Unauthorized"}), 401
#         data = request.json

#         input_str = data.get("date")+data.get("slot")

# # Extract the date and starting time
#         date_part = input_str[:10]              # "2025-04-17"
#         time_part = input_str[10:19].strip()    # "09:00 AM"

# # Combine and parse
#         dt = datetime.strptime(date_part + time_part, "%Y-%m-%d%I:%M %p")

# # Format to "YYYYMMDDHH"
#         formatted = dt.strftime("%Y%m%d%H")

#         print(formatted)

#         mdata = {
#             "date" : data.get("date"),
#             "slot" : data.get("slot"),
#             "enable" : data.get("enable"),
#             "doctor_id" : '67ee5e1bde4cb48c515073ee',
#             "_id": formatted
#         }

#         try:
#             disableslot.insert_one(mdata)
#         except:
#             disableslot.update_one({'_id': formatted}, {'$set': mdata})
#         return jsonify({"inserted_id": str(formatted)}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 400


@app.route("/slot_disable_k", methods=["POST"])
def slot_disablek():
    try:
        data = request.json

        date = data.get("date")           # "2025-04-17"
        slot = data.get("slot")           # "09:00 AM - 06:00 PM"

        # Extract only first time before '-'
        start_time = slot.split("-")[0].strip()   # "09:00 AM"

        # Combine date + time
        input_str = f"{date} {start_time}"        # "2025-04-17 09:00 AM"

        # Convert to datetime
        dt = datetime.strptime(input_str, "%Y-%m-%d %I:%M %p")

        # Create ID
        formatted_id = dt.strftime("%Y%m%d%H")

        mdata = {
            "_id": formatted_id,
            "date": date,
            "slot": slot,
            "enable": data.get("enable"),
            "doctor_id": "67ee5e1bde4cb48c515073ee",
        }

        try:
            disableslot.insert_one(mdata)
        except Exception:
            disableslot.update_one({"_id": formatted_id}, {"$set": mdata})

        return jsonify({"inserted_id": formatted_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
@app.route("/get_slot", methods=["POST"])
def get_slot():
    try:
        # api_key = request.headers.get("x-api-key")
        # if not api_key or api_key != API_KEY:
        #     return jsonify({"error": "Unauthorized"}), 401
        # Fetch all appointments and convert ObjectId to string
        documents = list(disableslot.find({}))
        if not documents:
            return jsonify({"error": "No appointments found"}), 404
        # Convert ObjectId to string for JSON response
        for doc in documents:
            doc["_id"] = str(doc["_id"])
        return jsonify(documents), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/slot_disable_k/<string:id>", methods=["POST"])
def slot_disablek_id(id):
    try:
        data = request.json

        date = data.get("date")           # "2025-04-17"
        slot = data.get("slot")           # "09:00 AM - 06:00 PM"

        # Extract only first time before '-'
        start_time = slot.split("-")[0].strip()   # "09:00 AM"

        # Combine date + time
        input_str = f"{date} {start_time}"        # "2025-04-17 09:00 AM"

        # Convert to datetime
        dt = datetime.strptime(input_str, "%Y-%m-%d %I:%M %p")

        # Create ID
        formatted_id = dt.strftime("%Y%m%d%H")

        mdata = {
            "_id": formatted_id,
            "date": date,
            "slot": slot,
            "enable": data.get("enable"),
            "doctor_id": id,
        }

        try:
            disableslot.insert_one(mdata)
        except Exception:
            disableslot.update_one({"_id": formatted_id}, {"$set": mdata})

        return jsonify({"inserted_id": formatted_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
@app.route("/get_slot/<string:id>", methods=["POST"])
def get_slot_id(id):
    try:
        # api_key = request.headers.get("x-api-key")
        # if not api_key or api_key != API_KEY:
        #     return jsonify({"error": "Unauthorized"}), 401
        # Fetch all appointments and convert ObjectId to string
        documents = list(disableslot.find({'doctor_id':id}))
        if not documents:
            return jsonify({"error": "No appointments found"}), 404
        # Convert ObjectId to string for JSON response
        for doc in documents:
            doc["_id"] = str(doc["_id"])
        return jsonify(documents), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    
@app.route("/get_refund_report", methods=["POST"])
def refund_report():
    try:
        # api_key = request.headers.get("x-api-key")
        # if not api_key or api_key != API_KEY:
        #     return jsonify({"error": "Unauthorized"}), 401

        data = request.json
        doctor_id = '67ee5e1bde4cb48c515073ee'

        # Fetch appointment and disabled slot data
        appointmentdata = list(appointment.find(
            {"doctor_phone_id": doctor_id, "date_of_appointment": data.get("date"),"amount":{"$gt": 0}},
            {"_id": 0}
        ))

        disableslotdata = list(disableslot.find(
            {"doctor_id": doctor_id, "date": data.get("date"), "enable": False},
            {"_id": 0}
        ))



        # Step 1: Create set of disabled time slots for fast lookup
        disabled_slots = {slot["slot"] for slot in disableslotdata}

        # Step 2: Filter appointments whose time_slot is in disabled_slots
        refunded_appointments = [
            appt for appt in appointmentdata if appt["time_slot"] in disabled_slots
        ]

        if not refunded_appointments:
            return jsonify({"error": "No matching appointments found"}), 404

        return jsonify(refunded_appointments), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_refund_user/<string:pdate>", methods=["GET"])
def refund_appointment_user(pdate):
    try:
        # api_key = request.headers.get("x-api-key")
        # if not api_key or api_key != API_KEY:
        #     return jsonify({"error": "Unauthorized"}), 401

        # data = request.json
        doctor_id = '67ee5e1bde4cb48c515073ee'


        doc_id = ObjectId("67ee5e1bde4cb48c515073ee")
        document = doctors.find_one({"_id": doc_id})
        datas = document
        datap = datas['date']['disabledate']
        data_names = {item["name"] for item in datap}
        result = pdate in data_names

        if result:
            appointmentdata = list(appointment.find(
            {"doctor_phone_id": doctor_id, "date_of_appointment": pdate,"amount":{"$gt": 0}},
            {"_id": 0}
            ))
            return jsonify(appointmentdata), 200


        # Fetch appointment and disabled slot data
        appointmentdata = list(appointment.find(
            {"doctor_phone_id": doctor_id, "date_of_appointment": pdate,"amount":{"$gt": 0}},
            {"_id": 0}
        ))

        disableslotdata = list(disableslot.find(
            {"doctor_id": doctor_id, "date": pdate, "enable": False},
            {"_id": 0}
        ))




        # Step 1: Create set of disabled time slots for fast lookup
        disabled_slots = {slot["slot"] for slot in disableslotdata}

        # Step 2: Filter appointments whose time_slot is in disabled_slots
        refunded_appointments = [
            appt for appt in appointmentdata if appt["time_slot"] in disabled_slots
        ]

        if not refunded_appointments:
            return jsonify({"error": "No matching appointments found"}), 404

        return jsonify(refunded_appointments), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# RAZORPAY_KEY_ID = 'rzp_test_YourKeyID'
# RAZORPAY_KEY_SECRET = 'YourSecretKey'

# @app.route("/refund_payment", methods=["POST"])
# def refund_payment():
#     try:
#         data = request.get_json()

#         payment_id = data.get("payment_id")
#         amount = data.get("amount")  # in paise (optional)

#         if not payment_id:
#             return jsonify({"error": "Missing payment_id"}), 400

#         refund_url = f"https://api.razorpay.com/v1/payments/{payment_id}/refund"

#         payload = {}
#         if amount:
#             payload["amount"] = amount  # e.g., 10000 for ₹100

#         # Optional: refund speed and notes
#         payload["speed"] = "optimum"
#         payload["notes"] = {"reason": "Customer requested refund"}

#         # Make the refund request
#         response = requests.post(
#             refund_url,
#             auth=HTTPBasicAuth(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
#             json=payload
#         )

#         if response.status_code == 200:
#             return jsonify(response.json()), 200
#         else:
#             return jsonify({
#                 "error": "Refund failed",
#                 "status_code": response.status_code,
#                 "response": response.text
#             }), response.status_code

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

    

@app.route("/update_user/<string:id>/", methods=["POST"])
def update_user_query(id):
    try:
        # api_key = request.headers.get("x-api-key")
        # if api_key != API_KEY:
        #     return jsonify({"error": "Unauthorized"}), 401
        data = request.json
        try:
            doc_id = ObjectId(id)
        except:
            return jsonify({"error": "Invalid ObjectId"}), 400
        result = doctors.update_one({'_id': doc_id}, {'$set': data})
        if result.matched_count == 0:
            return jsonify({"error": "User not found"}), 404
        elif result.modified_count == 0:
            return jsonify({"message": "No changes made"}), 200
        return jsonify({'success': True, "message": "User updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/update_appointment/<string:id>/", methods=["POST"])
def update_appointment_query(id):
    try:
        api_key = request.headers.get("x-api-key")
        if api_key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        data = request.json
        try:
            doc_id = ObjectId(id)
        except:
            return jsonify({"error": "Invalid ObjectId"}), 400
        result = appointment.update_one({'_id': doc_id}, {'$set': data})
        if result.matched_count == 0:
            return jsonify({"error": "User not found"}), 404
        elif result.modified_count == 0:
            return jsonify({"message": "No changes made"}), 200
        return jsonify({'success': True, "message": "User updated"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/change-password", methods=["POST"])
def change_password():
    try:
        data = request.json or {}

        user_id = data.get("user_id")
        old_password = data.get("old_password")
        new_password = data.get("new_password")

        if not user_id or not old_password or not new_password:
            return jsonify({"error": "user_id, old_password and new_password are required"}), 400

        # Find user by _id
        user = doctors.find_one({"_id": ObjectId(user_id)})

        if not user:
            return jsonify({"error": "User not found"}), 404

        # Verify old password
        if user.get("password") != old_password:
            return jsonify({"error": "Old password is incorrect"}), 401

        # Update password
        doctors.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password": new_password}}
        )

        return jsonify({
            "message": "Password changed successfully"
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/get_profile/<string:id>/", methods=["POST"])
def get_profile(id):
    try:
        api_key = request.headers.get("x-api-key")
        if api_key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        try:
            doc_id = ObjectId(id)
        except:
            return jsonify({"error": "Invalid ObjectId"}), 400
        document = doctors.find_one({"_id": doc_id})
        if not document:
            return jsonify({"error": "User not found"}), 404
        document["_id"] = str(document["_id"])
        return jsonify(document), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/get_appointment", methods=["POST"])
def get_appointment_list():
    try:
        api_key = request.headers.get("x-api-key")
        if not api_key or api_key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        # Fetch all appointments and convert ObjectId to string
        documents = list(appointment.find({}))
        if not documents:
            return jsonify({"error": "No appointments found"}), 404
        # Convert ObjectId to string for JSON response
        for doc in documents:
            doc["_id"] = str(doc["_id"])
        return jsonify(documents), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
        
@app.route("/get_appointments/<string:date>", methods=["GET"])
def get_appointment_list_by_date(date):
    try:
        documents = list(appointment.find({"date_of_appointment": date}))
        if not documents:
            return jsonify({"error": "No appointments found"}), 404

        # Convert ObjectId to string for JSON response
        for doc in documents:
            doc["_id"] = str(doc["_id"])

        return jsonify(documents), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get_appointments/<string:date>/<string:id>", methods=["GET"])
def get_appointment_list_by_date_id(date,id):
    try:
        documents = list(appointment.find({"date_of_appointment": date, "doctor_phone_id":id}))
        if not documents:
            return jsonify({"error": "No appointments found"}), 404

        # Convert ObjectId to string for JSON response
        for doc in documents:
            doc["_id"] = str(doc["_id"])

        return jsonify(documents), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/login", methods=["POST"])
def login():
    try:
        api_key = request.headers.get("x-api-key")
        
        if api_key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401

        # Get request data
        data = request.json
        username = data.get("username")
        password = data.get("password")

        # Find user in database
        # user = doctors.find_one({"email": username})

        user = doctors.find_one({"$or": [{"email": username}, {"phone": username}]})

         
        if not user:
            return jsonify({"error": "Invalid username or password"}), 401

        # Verify password
        if user["password"]!= password:
            return jsonify({"error": "Invalid username or password"}), 401

        try:
            if user["role"]== 'staff':
                return jsonify({"message": "Login successful","role":"staff","staffId":str(user['EmpID']),"doctorId":str(user['doctorId']) ,"user": str(user['_id']), "accessToken":str(user['accessToken']), "phonenumberID":str(user['phonenumberID'])}), 200
        except:

        # ✅ Generate JWT Token
            return jsonify({"message": "Login successful","role":"doctor", "user": str(user['_id']), "accessToken":str(user['accessToken']), "phonenumberID":str(user['phonenumberID'])}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/pdf/<string:id>/<string:date>/", methods=["GET"])
def get_pdf_admin(id,date):
    return pdfdownload(id,date)  # Exclude MongoDB's default _id field

@app.route("/pdf/<string:date>/", methods=["GET"])
def get_pdf(date):
    data = pdfdownloadinapi(date)
    return data
    

# Get Users (GET)
@app.route("/users", methods=["GET"])
def get_users():
    users = list(doctors.find({}, {"_id": 0}))  # Exclude MongoDB's default _id field
    return jsonify(users)

@app.route("/fatch_date_and_time/<string:id>/", methods=["GET"])
def get_datetime(id):
    users = dateandtime(id) # Exclude MongoDB's default _id field
    return jsonify(users)

@app.route("/fatch_date_and_time2/<string:id>/", methods=["GET"])
def get_datetime2(id):
    users = dateandtime2(id) # Exclude MongoDB's default _id field
    return jsonify(users)

@app.route("/fatch_current_date", methods=["GET"])
def get_datetimekk():
    users = currentdateverify() # Exclude MongoDB's default _id field
    return jsonify(users)

@app.route("/staff/<string:id>/", methods=["POST"])
def get_staff_list(id):
    try:
        api_key = request.headers.get("x-api-key")
        if not api_key or api_key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        # Fetch all appointments and convert ObjectId to string
        documents = list(doctors.find({"role":"staff","doctorId":id}))
        if not documents:
            return jsonify({"error": "No appointments found"}), 404
        # Convert ObjectId to string for JSON response
        for doc in documents:
            doc["_id"] = str(doc["_id"])
        return jsonify(documents), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Delete User (DELETE)
@app.route("/delete_user", methods=["DELETE"])
def delete_user():
    data = request.json
    if not data or "email" not in data:
        return jsonify({"error": "Email required"}), 400

    result = doctors.delete_one({"email": data["email"]})
    if result.deleted_count:
        return jsonify({"message": "User deleted"}), 200
    else:
        return jsonify({"error": "User not found"}), 404
    
@app.route('/payment_callback/<string:id>/', methods=['GET', 'POST'])
def payment_callback(id):
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

        doc_id = ObjectId(id)
        retrieved_data = appointment.find_one({"_id": doc_id})

        print(retrieved_data['doctor_phone_id'])

        result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":retrieved_data['date_of_appointment'],"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
        data_length = 1
        if result:
            data_length = len(result)+1

        xdate = retrieved_data['date_of_appointment']
        date_obj = datetime.strptime(xdate, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y%m%d")

        appoint_number = str(formatted_date)+'-'+str(data_length)

        dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        fee = float(dxxocument.get('appointmentfee'))

        appointment.update_one({'_id': doc_id},{'$set':{'status':'success','pay_id':callback_data.get('razorpay_payment_id'),'appoint_number':appoint_number,'amount':fee}})

        name = str(retrieved_data['patient_name'])
        payment_id = str(callback_data.get('razorpay_payment_id'))
        doa = str(retrieved_data['date_of_appointment'])
        tm = str(retrieved_data['time_slot'])
        phone = str(retrieved_data['whatsapp_number'])

        whatsapp_url = success_appointment(doa,appoint_number,name,doa,tm,phone)
        return redirect(whatsapp_url)
    else:
        # Payment failed or was not captured
        print("Payment failed or not captured!")
        return jsonify({'status': 'failed', 'message': 'Payment failed or not captured'}), 400
    
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
    # if tslot=='04:00 PM - 05:00 PM':
    #     return "E"+str(int(appointment_number-80))
    # if tslot=='05:00 PM - 06:00 PM':
    #     return "E"+str(int(appointment_number-80))

    # return "M"+str(appointment_number)
    return str(appointment_number)



    
# def getindex(docter_id,tslot,date):

#     doc_id = ObjectId(docter_id)
#     document = doctors.find_one({"_id": doc_id})
#     xslot = document['slots']['slotsvalue']

#     formatted_output = [
#                 {
#                      "id": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+ datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
#                     "slot": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
#                     "length": item["maxno"]
#                 }
#                 for index, item in enumerate(xslot)
#                 ]

#     target_id = tslot
#     total_length = 1

#     for slot in formatted_output:
#         if slot['id'] == target_id:
#             total_length += int(slot['length'])
#             break
#         total_length += int(slot['length'])


#     result = list(appointment.find({"doctor_phone_id": docter_id,'time_slot':tslot ,"date_of_appointment":date,"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
#     data_length = 0
#     if result:
#         data_length = len(result)

#     appointment_number = total_length-data_length-1
#     print(appointment_number)
#     return appointment_number





WEBHOOK_SECRET = "doctor"

@app.route('/razorpay/webhook', methods=['POST'])
def razorpay_webhook():
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
        # print("✅ Webhook verified:", json.dumps(data, indent=2))

        event = data.get("event")

        # if event == "payment_link.paid":
        #     payment = data["payload"]["payment"]["entity"]
        #     print("💰 Payment Received:", payment["id"], payment["amount"])

        if event == "order.paid":
            payment_entity = data["payload"]["payment"]["entity"]
            payment_id = payment_entity["id"]
            contact = str(payment_entity["contact"])
            contact = contact.lstrip('+')

            print(f"✅ Payment ID: {payment_id}")
            print(f"📞 Contact: {contact}")

            document = templog.find_one({'_id':contact})

            doc_id = ObjectId(document["current_id"])
            retrieved_data = appointment.find_one({"_id": doc_id})

            print(retrieved_data['doctor_phone_id'])

            result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":retrieved_data['date_of_appointment'],"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
            data_length = 1
            if result:
                data_length = len(result)+1

            xdate = retrieved_data['date_of_appointment']
            date_obj = datetime.strptime(xdate, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%Y%m%d")

            appoint_number = str(formatted_date)+'-'+str(data_length)


            dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
            fee = float(dxxocument.get('appointmentfee'))

            index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)

            appointment.update_one({'_id': doc_id},{'$set':{'status':'success','pay_id':payment_id,'appoint_number':appoint_number,'amount':fee,'appointment_index':index_number}})

            name = str(retrieved_data['patient_name'])
            payment_id = str(payment_id)
            doa = str(retrieved_data['date_of_appointment'])
            tm = str(retrieved_data['time_slot'])
            phone = str(retrieved_data['whatsapp_number'])

            whatsapp_url = success_appointment(doa,index_number,name,doa,tm,phone)
            return redirect(whatsapp_url)

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        print("⚠️ Exception:", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500



@app.route("/login-kk", methods=["POST"])
def loginss():
    try:
        data = request.json or {}
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400

        # Find user by email or phone
        user = doctors.find_one({"$or": [{"email": username}, {"phone": username}]})

        if not user:
            return jsonify({"error": "Invalid username or password"}), 401

        # Verify password (⚠️ using plain-text is risky, better use bcrypt)
        if user.get("password") != password:
            return jsonify({"error": "Invalid username or password"}), 401

        # Prepare base response
        response = {
            "message": "Login successful",
            "role": user.get("role", "doctor"),
            "user": str(user["_id"]),
            "accessToken": user.get("accessToken", ""),
            "phonenumberID": user.get("phonenumberID", ""),
            "name": user.get("name", ""),
            
        }

        # Extra fields for staff
        if user.get("role") == "staff":
            response.update({
                "staffId": str(user.get("EmpID", "")),
                "doctorId": str(user.get("doctorId", ""))
            })

        if user.get("role") == "hospital":
            response.update({
                "user": str(user.get("firstdoctor", "")),
                "hospital": str(user.get("_id", ""))
            })

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route('/payment_callback2/<string:id>/', methods=['GET', 'POST'])
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

        # doc_id = ObjectId(id)
        # retrieved_data = appointment.find_one({"_id": doc_id})

        # print(retrieved_data['doctor_phone_id'])

        # result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":retrieved_data['date_of_appointment'],"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
        # data_length = 1
        # if result:
        #     data_length = len(result)+1

        # xdate = retrieved_data['date_of_appointment']
        # date_obj = datetime.strptime(xdate, "%Y-%m-%d")
        # formatted_date = date_obj.strftime("%Y%m%d")

        # appoint_number = str(formatted_date)+'-'+str(data_length)

        # print('1')


        # dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        # fee = float(dxxocument.get('appointmentfee'))

        # print('1')


        # index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)

        # print('1')


        # appointment.update_one({'_id': doc_id},{'$set':{'status':'success','pay_id':callback_data.get('razorpay_payment_id'),'appoint_number':appoint_number,'amount':fee,'appointment_index':index_number}})

        # print('1')
        # name = str(retrieved_data['patient_name'])
        # payment_id = str(callback_data.get('razorpay_payment_id'))
        # doa = str(retrieved_data['date_of_appointment'])
        # tm = str(retrieved_data['time_slot'])
        # phone = str(retrieved_data['whatsapp_number'])

        # print('1')


        # whatsapp_url = success_appointment(doa,index_number,name,doa,tm,phone)

        # print('1')

        return redirect("whatsapp://send?phone=+919646465003")
    else:
        # Payment failed or was not captured
        print("Payment failed or not captured!")
        return jsonify({'status': 'failed', 'message': 'Payment failed or not captured'}), 400



@app.route('/quick_razorpay_webhook', methods=['GET', 'POST'])
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
        # print("✅ Webhook verified:", json.dumps(data, indent=2)) 

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

            

            dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
            fee = float(dxxocument.get('appointmentfee'))

            print('1')


            index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)

            print('1')

            doc_id = ObjectId(retrieved_data['_id'])
            appointment.update_one({'_id': doc_id},{'$set':{'payment_status':'paid','status':'success','pay_id':payment["id"],'appoint_number':appoint_number,'amount':fee,'appointment_index':index_number}})

            print('1')
            name = str(retrieved_data['patient_name'])
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
                    "ledger_id": "A12",
                    "ledger_name": "CGST GST",
                    "debit": 0,
                    "credit": 3.05/2
                    },
                     {
                    "narration": "Appointment Fee",
                    "ledger_id": "A13",
                    "ledger_name": "SGST GST",
                    "debit": 0,
                    "credit": 3.05/2
                    }     
                    ],
                        "created_by": "system",
                        "created_at": ist_now
                    }
                    vouchers.insert_one(voucher)
            except:
                print(2)

            whatsapp_url = success_appointment(doa,index_number,name,doa,tm,phone)

            print('1')

            return jsonify({'status': 'success'}), 200
           
        return jsonify({'status': 'success'}), 200

    except Exception as e:
        print("⚠️ Exception:", str(e))
        return jsonify({'status': 'error', 'message': str(e)}), 500
    

@app.route("/doctor-payment", methods=["POST"])
def v1_doctor_payment():
    try:
        data = request.json
        doctorId = data.get("doctorId")
        fee = data.get("amount")
        payment_id = data.get("paymentId")
        ledgerCode = data.get("ledgerCode")
        ledgerName = data.get("ledgerName")

        voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))
        date_str = voucher_date.strftime("%Y-%m-%d")
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        start = datetime(date_obj.year, date_obj.month, date_obj.day)
        end = start + timedelta(days=1)

        count_txn = vouchers.count_documents({})
        count = vouchers.count_documents({
                    "voucher_type": "Payment",
                    "voucher_mode": "Bank",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
        })

        voucher_number = "BPV-"+ str(date_str) +'-'+ str(count + 1)
        voucher = {
                    "voucher_number": voucher_number,
                    "voucher_type": 'Payment',
                    "voucher_mode": "Bank",
                    "txn": count_txn + 1,
                    "doctor_id": doctorId,
                    "from_id": "admin",
                    "to_id": doctorId,
                    "date": datetime.now(ZoneInfo("Asia/Kolkata")),
                    "Payment_id": payment_id,
                    "narration": 'Doctor Payment',
                    "amount":float(fee),
                    "entries": [
                {
                "narration": "Doctor Payment",
                "ledger_id": "A2",
                "ledger_name": "Doctor Fee Payble",
                "debit": float(fee),
                "credit": 0
                },
                {
                "narration": "Doctor Payment",
                "ledger_id": ledgerCode,
                "ledger_name": ledgerName,
                "debit": 0,
                "credit": float(fee)
                }
                ],
                    "created_by": "system",
                    "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }
        vouchers.insert_one(voucher)
        return jsonify({"status": "ok","voucherCode":voucher_number,"txn":count_txn + 1}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/v1/vouchers", methods=["GET"])
def get_vouchers_filtered():
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    voucher_type = request.args.get("voucher_type")
    voucher_mode = request.args.get("voucher_mode")
    
    query = {}

    if from_date and to_date:
        start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        end = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        end = end.replace(hour=23, minute=59, second=59)

        # MongoDB UTC me hota hai → convert IST → UTC
        start = start.astimezone(ZoneInfo("UTC"))
        end = end.astimezone(ZoneInfo("UTC"))

        query["date"] = {"$gte": start, "$lte": end}
    
    if voucher_type:
        query["voucher_type"] = voucher_type

    if voucher_mode:
        query["voucher_mode"] = voucher_mode
    
    vouchers_list = list(vouchers.find(query))
    
    for v in vouchers_list:
        v["_id"] = str(v["_id"])
        
        # 🔥 UTC → IST convert
        if "date" in v:
            v["date"] = v["date"].astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
        
        if "created_at" in v:
            v["created_at"] = v["created_at"].astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify(vouchers_list)


@app.route('/v1/ledger/<ledger_id>', methods=['GET'])
def get_ledger_entries(ledger_id):

    from_date_str = request.args.get("from")
    to_date_str = request.args.get("to")

    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d") if from_date_str else None
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d") if to_date_str else None
    except Exception:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    # ✅ IST → UTC conversion (IMPORTANT)
    if from_date:
        from_date = from_date.replace(tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(ZoneInfo("UTC"))

    if to_date:
        to_date = to_date.replace(hour=23, minute=59, second=59)
        to_date = to_date.replace(tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(ZoneInfo("UTC"))

    # ✅ Opening balance
    opening_balance = 0
    if from_date:
        before_cursor = vouchers.find({
            "entries.ledger_id": ledger_id,
            "date": {"$lt": from_date}
        })

        for doc in before_cursor:
            for entry in doc.get("entries", []):
                if entry.get("ledger_id") == ledger_id:
                    opening_balance += (entry.get("debit", 0) - entry.get("credit", 0))

    # ✅ Query
    query = {"entries.ledger_id": ledger_id}

    if from_date and to_date:
        query["date"] = {"$gte": from_date, "$lte": to_date}
    elif from_date:
        query["date"] = {"$gte": from_date}
    elif to_date:
        query["date"] = {"$lte": to_date}

    results = vouchers.find(query)

    ledger_entries = []

    for doc in results:
        for entry in doc.get("entries", []):
            if entry.get("ledger_id") == ledger_id:

                # 🔥 UTC → IST convert (response)
                ist_date = None
                if doc.get("date"):
                    ist_date = doc["date"].astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")

                ledger_entries.append({
                    "voucher_number": doc.get("voucher_number"),
                    "voucher_type": doc.get("voucher_type"),
                    "voucher_mode": doc.get("voucher_mode"),
                    "txn": doc.get("txn"),
                    "ledger_id": entry.get("ledger_id"),
                    "ledger_name": entry.get("ledger_name"),
                    "credit": entry.get("credit"),
                    "debit": entry.get("debit"),
                    "narration": entry.get("narration"),
                    "date": ist_date,   # ✅ fixed
                })

    # ⚠️ sort UTC pe karo ya IST string pe?
    ledger_entries.sort(key=lambda x: x["date"])

    return jsonify({
        "ledger_id": ledger_id,
        "opening_balance": opening_balance,
        "transaction_count": len(ledger_entries),
        "transactions": ledger_entries
    })

@app.route('/v1/doctor/<doctor_id>', methods=['GET'])
def get_doctor_vouchers(doctor_id):
    # query params: ?from=2025-08-01&to=2025-08-30
    from_date_str = request.args.get("from")
    to_date_str = request.args.get("to")

    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d") if from_date_str else None
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d") if to_date_str else None
    except Exception:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    # ===== Opening Balance Calculation =====
    opening_debit, opening_credit = 0, 0
    if from_date:
        opening_query = {
            "doctor_id": doctor_id,
            "date": {"$lt": from_date}
        }
        prev_vouchers = vouchers.find(opening_query)
        for doc in prev_vouchers:
            for entry in doc.get("entries", []):
                if entry.get("ledger_id") == "A2":
                    opening_debit += entry.get("debit", 0)
                    opening_credit += entry.get("credit", 0)

    opening_balance = opening_debit - opening_credit

    # ===== Current Period Transactions =====
    query = {"doctor_id": doctor_id}
    if from_date and to_date:
        query["date"] = {"$gte": from_date, "$lte": to_date}
    elif from_date:
        query["date"] = {"$gte": from_date}
    elif to_date:
        query["date"] = {"$lte": to_date}

    results = vouchers.find(query)

    transactions = []
    total_debit, total_credit = 0, 0

    for doc in results:
        for entry in doc.get("entries", []):
            if entry.get("ledger_id") == "A2":   # ✅ only A2 ledger
                transactions.append({
                    "voucher_number": doc.get("voucher_number"),
                    "voucher_type": doc.get("voucher_type"),
                    "voucher_mode": doc.get("voucher_mode"),
                    "doctor_id": doc.get("doctor_id"),
                    "ledger_id": entry.get("ledger_id"),
                    "ledger_name": entry.get("ledger_name"),
                    "debit": entry.get("debit", 0),
                    "credit": entry.get("credit", 0),
                    "narration": entry.get("narration"),
                    "date": doc.get("date"),
                    "Payment_id": doc.get("Payment_id"),
                })
                total_debit += entry.get("debit", 0)
                total_credit += entry.get("credit", 0)

    closing_balance = opening_balance + (total_debit - total_credit)

    return jsonify({
        "doctor_id": doctor_id,
        "ledger_id": "A2",
        "opening_balance": opening_balance,
        "period_debit": total_debit,
        "period_credit": total_credit,
        "closing_balance": closing_balance,
        "transaction_count": len(transactions),
        "transactions": transactions
    })


@app.route("/add_description/<string:doctorId>", methods=["GET", "POST"])
def add_description(doctorId):
    try:
        if request.method == "POST":
            data = request.get_json()

            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            # Case 1: Single product (dict)
            if isinstance(data, dict):
                doctors.update_one(
                    {"_id": ObjectId(doctorId)},
                    {"$set": {"products": [data]}}  # wrap into list
                )

            # Case 2: Multiple products (list)
            elif isinstance(data, list):
                doctors.update_one(
                    {"_id": ObjectId(doctorId)},
                    {"$set": {"products": data}}
                )

            else:
                return jsonify({"status": "error", "message": "Invalid data format"}), 400

            return jsonify({
                "status": "success",
                "message": "Product(s) updated successfully"
            }), 200

        # -------- GET: Fetch products --------
        doctor = doctors.find_one({"_id": ObjectId(doctorId)})

        if not doctor:
            return jsonify({"status": "error", "message": "Doctor not found"}), 404

        products = doctor.get("products", [])
        return jsonify(products), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



@app.route("/patient", methods=["GET", "POST"])
def patient_api():
    try:
        if request.method == "POST":
            # -------- Add patient --------
            data = request.get_json()

            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            insert_id = appointment.insert_one(data).inserted_id

            return jsonify({
                "status": "success",
                "message": "Patient added successfully",
                "patient_id": str(insert_id)
            }), 201

        else:
            # -------- Get patients --------
            patients = list(patient.find())
            for p in patients:
                p["_id"] = str(p["_id"])  # convert ObjectId to string

            return jsonify({
                "status": "success",
                "count": len(patients),
                "patients": patients
            }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



@app.route("/patient_bill", methods=["GET", "POST"])
def patient_bill_api():
    try:
        if request.method == "POST":
            # -------- Add patient --------
            data = request.get_json()

            if not data:
                return jsonify({"status": "error", "message": "No data provided"}), 400

            last_patient = patient.find_one(sort=[("id", -1)])
            new_id = (last_patient["id"] + 1) if last_patient else 4101
            data.update({"id": new_id})
            
            insert_id = patient.insert_one(data).inserted_id

            return jsonify({
                "status": "success",
                "message": "Patient added successfully",
                "patient_id": str(insert_id)
            }), 201

        else:
            from_date = request.args.get("from_date")
            to_date = request.args.get("to_date")

            query = {}
            if from_date and to_date:
                try:
                    # Dates ko proper format me convert karo
                    # start = datetime.strptime(from_date, "%Y-%m-%d")
                    # end = datetime.strptime(to_date, "%Y-%m-%d")

                    # MongoDB query banani
                    query["date"] = {"$gte": from_date, "$lte": to_date}

                except ValueError:
                    return jsonify({"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}), 400

            patients = list(patient.find(query))
            for p in patients:
                p["_id"] = str(p["_id"])

            return jsonify({
                "status": "success",
                "count": len(patients),
                "patients": patients
            }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/patient_bill_update/<string:patient_id>", methods=["POST"])
def update_patient_bill(patient_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No update data provided"}), 400

        # MongoDB ObjectId में convert
        from bson import ObjectId
        query = {"_id": ObjectId(patient_id)}

        # Update patient details
        result = patient.update_one(query, {"$set": {'brackup':data}})

        if result.matched_count == 0:
            return jsonify({"status": "error", "message": "Patient not found"}), 404

        return jsonify({
            "status": "success",
            "message": "Patient updated successfully",
            "patient_id": patient_id
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/patient_amount_update/<string:patient_id>", methods=["POST"])
def update_patient_bill_amount(patient_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No update data provided"}), 400

        # MongoDB ObjectId में convert
        from bson import ObjectId
        query = {"_id": ObjectId(patient_id)}

        # Update patient details
        result = patient.update_one(query, {"$set": {'amount':data.get("amount"),'name':data.get("name"),'fatherName':data.get("fatherName")}})

        if result.matched_count == 0:
            return jsonify({"status": "error", "message": "Patient not found"}), 404

        return jsonify({
            "status": "success",
            "message": "Patient updated successfully",
            "patient_id": patient_id
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500




@app.route("/api/patients", methods=["GET"])
def get_patients_search():
    search = request.args.get("search", "")
    results = list(appointment.find(
        {"whatsapp_number": {"$regex": search, "$options": "i"}}
    ).limit(10))

    # Convert ObjectId to string
    for r in results:
        r["_id"] = str(r["_id"])

    return jsonify(results)


@app.route("/get_patient_bill_reciept_number", methods=["GET"])
def get_patient_bill_reciept_number():
    try:
        last_patient = patient.find_one(sort=[("id", -1)])
        new_id = (last_patient["id"] + 1) if last_patient else 4101
        return jsonify({
                "status": "success",
                "patient_id": str(new_id)
        }), 201

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500






@app.route("/multiple_payment_doctor", methods=["GET"])
def get_multiple_doctor():
    # Use doctor_collection for DB
    doctor_collection = doctors  

    # Fetch all doctors
    doctor_list = list(doctor_collection.find({"role": "doctor"}))  

    doctorpaymentlist = []

    from_date_str = request.args.get("from")
    to_date_str = request.args.get("to")

    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d") if from_date_str else None
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d") if to_date_str else None
    except Exception:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    for doctor in doctor_list:
        doctor_id = str(doctor["_id"])  # keep Mongo _id safe for JSON

        # ===== Opening Balance Calculation =====
        opening_debit, opening_credit = 0, 0
        if from_date:
            opening_query = {"doctor_id": doctor_id, "date": {"$lt": from_date}}
            prev_vouchers = vouchers.find(opening_query)
            for doc in prev_vouchers:
                for entry in doc.get("entries", []):
                    if entry.get("ledger_id") == "A2":
                        opening_debit += entry.get("debit", 0)
                        opening_credit += entry.get("credit", 0)

        opening_balance = opening_debit - opening_credit

        # ===== Current Period Transactions =====
        query = {"doctor_id": doctor_id}
        if from_date and to_date:
            query["date"] = {"$gte": from_date, "$lte": to_date}
        elif from_date:
            query["date"] = {"$gte": from_date}
        elif to_date:
            query["date"] = {"$lte": to_date}

        results = vouchers.find(query)

        transactions, total_debit, total_credit = [], 0, 0

        for doc in results:
            for entry in doc.get("entries", []):
                if entry.get("ledger_id") == "A2":
                    transactions.append({
                        "voucher_number": doc.get("voucher_number"),
                        "voucher_type": doc.get("voucher_type"),
                        "voucher_mode": doc.get("voucher_mode"),
                        "doctor_id": doc.get("doctor_id"),
                        "ledger_id": entry.get("ledger_id"),
                        "ledger_name": entry.get("ledger_name"),
                        "debit": entry.get("debit", 0),
                        "credit": entry.get("credit", 0),
                        "narration": entry.get("narration"),
                        "date": doc.get("date"),
                        "Payment_id": doc.get("Payment_id"),
                    })
                    total_debit += entry.get("debit", 0)
                    total_credit += entry.get("credit", 0)

        closing_balance = opening_balance + (total_debit - total_credit)

        doctorpaymentlist.append({
            "id":doctor['secondaryId'],
            "doctor_id": doctor_id,
            "doctor_name": doctor['name'],
            "phone_number": doctor['phone'],
            "ledger_id": "A2",
            "opening_balance": opening_balance,
            "period_debit": total_debit,
            "period_credit": total_credit,
            "closing_balance": closing_balance,
            "transaction_count": len(transactions),
            "transactions": transactions
        })

    return jsonify(doctorpaymentlist)




@app.route("/multiple_doctor-payment", methods=["POST"])
def v1_m_doctor_payment():
    try:
        datas = request.json

        for data in datas:
            doctorId = data.get("doctorId")
            fee = data.get("amount")
            payment_id = data.get("paymentId")
            ledgerCode = data.get("ledgerCode")
            ledgerName = data.get("ledgerName")
            

            id = data.get("id")
            phone = data.get("phone")
            _id = data.get("_id")
            status = data.get("status")
            nareshan = data.get("nareshan")
            

            if status=='approve':

                transactionId = data.get("transactionId")

                requestdb.update_one({'_id':ObjectId(_id)},{"$set": {'status':'approve'}})


                voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))
                date_str = voucher_date.strftime("%Y-%m-%d")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                start = datetime(date_obj.year, date_obj.month, date_obj.day)
                end = start + timedelta(days=1)

                count_txn = vouchers.count_documents({})
                count = vouchers.count_documents({
                            "voucher_type": "Payment",
                            "voucher_mode": "Bank",
                            "date": {"$gte": start, "$lt": end}   # between start and end of day
                })

                voucher_number = "BPV-"+ str(date_str) +'-'+ str(count + 1)
                voucher = {
                            "voucher_number": voucher_number,
                            "voucher_type": 'Payment',
                            "voucher_mode": "Bank",
                            "txn": count_txn + 1,
                            "doctor_id": doctorId,
                            "from_id": "admin",
                            "to_id": doctorId,
                            "date": datetime.now(ZoneInfo("Asia/Kolkata")),
                            "Payment_id": payment_id,
                            "narration": nareshan,
                            "amount":float(fee),
                            "transaction_id":transactionId,
                            "entries": [
                        {
                        "narration": nareshan,
                        "ledger_id": "A2",
                        "ledger_name": "Doctor Fee Payble",
                        "debit": float(fee),
                        "credit": 0
                        },
                        {
                        "narration": nareshan,
                        "ledger_id": ledgerCode,
                        "ledger_name": ledgerName,
                        "debit": 0,
                        "credit": float(fee)
                        }
                        ],
                            "created_by": "system",
                            "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                        }
                vouchers.insert_one(voucher)
            else:
                requestdb.update_one({'_id':ObjectId(_id)},{"$set": {'status':status}})
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

import requests
def paymentrequest_msg(from_number,MID,amount,name,c,tilldate):
    headers={'Authorization': 'Bearer EAAQNrOr6av0BPojE1zKKzKEDJWVmZBBvtBefl8aS24XBz4QcLzXPeF6wTlCBsIPFeOcwHi5AZBuXwkN6IfpI4uDjyLZAYRvMNF9jdVdeJ2WiNlnY1N1NpmFZBrJCSZAZCALx23ZArZA0jWnn0kEic6gY1Li4TFw8pZAnKZAmJtM0o6ZBfQZC8zi3v2EtcsoEnu9FutphkQZDZD','Content-Type': 'application/json'}
    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL
    current_date = tilldate
    incoming_data = { 
  "messaging_product": "whatsapp", 
  "to": from_number, 
  "type": "template", 
  "template": { 
    "name": "payment_request_msg", 
    "language": { "code": "en" },
    "components": [
      {
        "type": "body",
        "parameters": [
          {
            "type": "text",
            "text": name 
          },
          {
            "type": "text",
            "text": MID
          },
          {
            "type": "text",
            "text": current_date
          },
          {
            "type": "text",
            "text": amount
          }
        ]
      }
    ]
  } 
}
    response = requests.post(external_url, json=incoming_data, headers=headers)
    # print(jsonify(response.json()))
    return "OK", 200

import secrets
import string
def generate_payment_id():
    today_str = datetime.now().strftime("%Y%m%d")  # YYYYMMDD
    prefix = "PAY"

    # Random 6 character string (letters+digits)
    random_str = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(6))

    return f"{prefix}-{today_str}-{random_str}"

@app.route("/multiple_doctor-payment-request", methods=["GET", "POST"])
def multiple_doctor_payment_request():
    try:
        # ✅ POST Request (insert data)
        if request.method == "POST":
            datas = request.json

            if not datas or not isinstance(datas, list):
                return jsonify({"error": "Invalid data format, expected list"}), 400

            for data in datas:
                doctorId = data.get("doctorId")
                if not doctorId:
                    continue  

                from_number = data.get("phone")
                MID = data.get("id")
                name = data.get("name")
                amount = data.get("amount")
                currentbalance = data.get("currentbalance")
                tilldate = data.get("tilldate")

                res = paymentrequest_msg(from_number, MID,amount,name,currentbalance,tilldate)

                # Save with createdAt field
                data["paymentId"] = generate_payment_id()
                data["role"] = 'payment_req'
                data["createdAt"] = datetime.now(ZoneInfo("Asia/Kolkata"))
                requestdb.insert_one(data)

            return jsonify({"status": "ok"}), 200

        elif request.method == "GET":
            from_date_str = request.args.get("from")
            to_date_str = request.args.get("to")
            status = request.args.get("status")  # query param: ?status=pending

            query = {}

            # Date range filter
            if from_date_str and to_date_str:
                try:
                    from_date = datetime.strptime(from_date_str, "%Y-%m-%d")
                    to_date = datetime.strptime(to_date_str, "%Y-%m-%d")
                    to_date = to_date.replace(hour=23, minute=59, second=59)
                    query["createdAt"] = {"$gte": from_date, "$lte": to_date}
                except ValueError:
                    return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

            # Status filter
            if status:
                query["status"] = status

            documents = list(requestdb.find(query))

            if not documents:
                return jsonify({"error": "No records found"}), 404

            records = []
            for doc in documents:
                doc["_id"] = str(doc["_id"])
                if "createdAt" in doc:
                    doc["createdAt"] = doc["createdAt"].strftime("%Y-%m-%d %H:%M:%S")
                records.append(doc)

            return jsonify(records), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/get_appointments", methods=["GET"])
def get_appointments_by_range():
    try:
        # Query parameters: /get_appointments?from=2025-09-01&to=2025-09-10
        from_date = request.args.get("from")
        to_date = request.args.get("to")

        if not from_date or not to_date:
            return jsonify({"error": "Please provide both 'from' and 'to' date"}), 400

        # MongoDB query for range
        documents = list(
            appointment.find({
                "date_of_appointment": {"$gte": from_date, "$lte": to_date},"status":"success"
            })
        )

        if not documents:
            return jsonify({"error": "No appointments found"}), 404

        # Convert ObjectId to string
        for doc in documents:
            doc["_id"] = str(doc["_id"])

        return jsonify(documents), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/doctor_dropdown", methods=["GET"])
def doctor_dropdown():
    try:
        # ✅ Only fetch _id and name fields
        documents = list(doctors.find(
            {"role": "doctor"},
            {"_id": 1, "name": 1, "secondaryId":1}   # projection
        ))

        if not documents:
            return jsonify({"error": "No doctors found"}), 404

        # Convert ObjectId to string
        for doc in documents:
            doc["_id"] = str(doc["_id"])

        return jsonify(documents), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/doctor_list", methods=["GET"])
def doctor_list():
    try:
        # ✅ Only fetch _id and name fields
        documents = list(doctors.find(
            {"role": "doctor"}  # projection
        ))

        if not documents:
            return jsonify({"error": "No doctors found"}), 404

        # Convert ObjectId to string
        for doc in documents:
            doc["_id"] = str(doc["_id"])

        return jsonify(documents), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get_doctor/<string:id>/", methods=["GET"])
def get_doctor(id):
    try:
        try:
            doc_id = ObjectId(id)
        except:
            return jsonify({"error": "Invalid ObjectId"}), 400
        document = doctors.find_one({"_id": doc_id})
        if not document:
            return jsonify({"error": "User not found"}), 404
        document["_id"] = str(document["_id"])
        return jsonify(document), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    



def transform_entry(entry):
                if not entry.get("razorpay") or entry["razorpay"] == 0:
                    return []
                pid = entry["Payment_id"]
                if not entry.get("tax") or entry["tax"] == 0:
                    return [
                        {
                        "Payment_id": pid,
                        "narration": "Payment ID - "+pid,
                        "ledger_id": "A7",
                        "ledger_name": "Gateway Expenses",
                        "debit": entry["gataway_charges"],
                        "credit": 0
                    }
                    ]
                return [
                    # {
                    #     "Payment_id": pid,
                    #     "narration": "Settlement for "+pid,
                    #     "ledger_id": "A1",
                    #     "ledger_name": "Razorpay",
                    #     "debit": 0,
                    #     "credit": entry["razorpay"]
                    # },
                    {
                        "Payment_id": pid,
                        "narration": "Payment ID - "+pid,
                        "ledger_id": "A8",
                        "ledger_name": "Input Tax Credit",
                        "debit": entry["tax"],
                        "credit": 0
                    },
                    {
                        "Payment_id": pid,
                        "narration": "Payment ID - "+pid,
                        "ledger_id": "A7",
                        "ledger_name": "Gateway Expenses",
                        "debit": entry["gataway_charges"],
                        "credit": 0
                    }
                    # ,{
                    #     "Payment_id": pid,
                    #     "narration": "Settlement for "+pid,
                    #     "ledger_id": "A4",
                    #     "ledger_name": "IDFC bank",
                    #     "debit": entry["settlemant"],
                    #     "credit": 0
                    # }
                ]


def grouping_entry(entry):
                if not entry.get("settlemant") or entry["settlemant"] == 0:
                    return []
                pid = entry["Payment_id"]
                return [
                    {
                        "Payment_id": pid,
                        "narration": "Payment ID - "+pid,
                        "ledger_id": "A4",
                        "ledger_name": "IDFC bank",
                        "debit": entry["settlemant"],
                        "credit": 0
                    }
                ]
def grouping_entry2(entry):
                if not entry.get("razorpay") or entry["razorpay"] == 0:
                    return []
                pid = entry["Payment_id"]
                return [
                    {
                        "Payment_id": pid,
                        "narration": "Payment ID - "+pid,
                        "ledger_id": "A4",
                        "ledger_name": "IDFC bank",
                        "debit": entry["razorpay"],
                        "credit": 0
                    }
                ]

@app.route("/excel_razorpay_tax", methods=["POST"])
def v1_excel_razorpay_tax():
    try:
        datas = request.json

        for data in datas:

            doctorId = 'system'
            payment_id = 'system'

            # voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))
            # date_str = voucher_date.strftime("%Y-%m-%d")

            date_str = datetime.strptime(data["date"], "%Y-%m-%d")
            date_str = date_str.strftime("%Y-%m-%d")

            date_obj = datetime.strptime(data["date"], "%Y-%m-%d")
            start = datetime(date_obj.year, date_obj.month, date_obj.day)
            end = start + timedelta(days=1)

            count_txn = vouchers.count_documents({})
            count = vouchers.count_documents({
                        "voucher_type": "Journal",
                        "voucher_mode": "Journal",
                        "date": {"$gte": start, "$lt": end}   
            })

            voucher_number = "JRV-"+ str(date_str) +'-'+ str(count + 1)

            # print(voucher_number)

            dt = datetime.strptime(data["date"], "%Y-%m-%d")
            dt = dt.replace(hour=2, minute=0, second=13, microsecond=645000, tzinfo=ZoneInfo("Asia/Kolkata"))

# ✅ keep as datetime object
            data["date"] = dt

            entries = [e for entry in data["entries"] for e in transform_entry(entry)]

            entries.append({
                        "Payment_id": 'system',
                        "narration": "Bank Settlement",
                        "ledger_id": "A4",
                        "ledger_name": "IDFC bank",
                        "debit": float(data["bankamount"]),
                        "credit": 0,
                        "grouping": [e for entry in data["entries"] for e in grouping_entry(entry)]
                    })
            
            entries.append({
                        "Payment_id": 'system',
                        "narration": "Bank Settlement",
                        "ledger_id": "A1",
                        "ledger_name": "Razorpay",
                        "debit": 0,
                        "credit": float(data["amount"]),
                        "grouping": [e for entry in data["entries"] for e in grouping_entry2(entry)]
                    })


            voucher = {
                "date": data["date"],
                "amount": data["amount"],
                "voucher_number": voucher_number,
                "voucher_type": 'Journal',
                "voucher_mode": "Journal",
                "txn": count_txn + 1,
                "doctor_id": doctorId,
                "from_id": "admin",
                "to_id": doctorId,
                "Payment_id": payment_id,
                "narration": 'Bank Settlement',
                "created_by": "system",
                "created_at": datetime.now(ZoneInfo("Asia/Kolkata")),
                "entries": entries
            }

            # print(voucher['entries'])

            # print(voucher)
            vouchers.insert_one(voucher)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



from razorpay_local import pay_link
def opd_msg(from_number,name,no,date,time):
    headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL
    incoming_data = { 
  "messaging_product": "whatsapp", 
  "to": from_number, 
  "type": "template", 
  "template": { 
    "name": "opd_booking", 
    "language": { "code": "en" },
    "components": [
      {
        "type": "body",
        "parameters": [
          {
            "type": "text",
            "text": name 
          },
          {
            "type": "text",
            "text": no
          },
          {
            "type": "text",
            "text": date
          },
          {
            "type": "text",
            "text": time
          }
        ]
      }
    ]
  } 
}
    response = requests.post(external_url, json=incoming_data, headers=headers)
    print(jsonify(response.json()))
    return "OK", 200


@app.route("/book_appointment_current_opd", methods=["POST"])
def book_appointment_current_opd():
    try:
        data = request.get_json()

        name = data.get("name")
        pname = data.get("fatherName")
        date = data.get("appointmentDate")
        slot = data.get("timeSlot")
        doctor_id = data.get("doctor_phone_id")
        email = data.get("email")
        symptoms = data.get("symptoms")
        age = data.get("age")
        timestamp = data.get("timestamp")
        from_number = "91" + data.get("mobile") if len(data.get("mobile")) == 10 else data.get("mobile")
        dob = data.get("dob")
        city = data.get("city")
        address = data.get("address")
        vaccine = data.get("isVaccination")
        sex = data.get("sex")
        
        if data.get("paymentMode")=='Online':

            dataset = {
            'sex':sex,
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
        
            id = str(appointment.insert_one(dataset).inserted_id)
            print(id)

            dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
            fee = float(dxxocument.get('appointmentfee'))
            # paymentlink = dxxocument.get('paymentlink')

            tempdata = {"number":from_number,"current_id":id,"_id":from_number}
            try:
                templog.insert_one(tempdata)
            except:
                templog.update_one({'_id': from_number}, {'$set': tempdata})

            admin = db["admin"] 
            dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
            razorpayid = dxocument.get('razorpayid')
            razorpaykey = dxocument.get('razorpaykey')

            link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)

            # link = paymentlink
            print(link)
            amount = fee
            return send_payment_flow(from_number,name,date,slot,amount,link)
        
        else:

            dataset = {
            'ref_id':data.get("_id"),
            'sex':sex,
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
            "vaccine":vaccine,
            'razorpay_url': 'Offline Transaction',
            'payment_status':'Cash'
                }
            
        
            

            retrieved_data = dataset

            if not retrieved_data:
                 return jsonify({'success':2}),200

            result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":retrieved_data['date_of_appointment'],"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
            data_length = 1
            if result:
                data_length = len(result)+1

            xdate = retrieved_data['date_of_appointment']
            date_obj = datetime.strptime(xdate, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%Y%m%d")

            appoint_number = str(formatted_date)+'-'+str(data_length)

            print('1')

            

            dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
            fee = float(dxxocument.get('otcfee'))
            xfee = float(dxxocument.get('doctorfee'))

            print('1')


            index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)

            print('1')

            dataset.update({'payment_status':'paid','status':'success','pay_id':'offline','appoint_number':appoint_number,'amount':xfee+fee,'appointment_index':index_number})

            id = str(appointment.insert_one(dataset).inserted_id)
            print(id)

            print('1')
            name = str(retrieved_data['patient_name'])
            payment_id = 'Cash'
            doa = str(retrieved_data['date_of_appointment'])
            tm = str(retrieved_data['time_slot'])
            phone = str(retrieved_data['whatsapp_number'])



            try:
                voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))
                date_str = voucher_date.strftime("%Y-%m-%d")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                start = datetime(date_obj.year, date_obj.month, date_obj.day)
                end = start + timedelta(days=1)

                count_txn = vouchers.count_documents({})
                count = vouchers.count_documents({
                    "voucher_type": "Journal",
                    "voucher_mode": "Journal",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })

                voucher_number = "JRV-"+ str(date_str) +'-'+ str(count + 1)
                voucher = {
                    "voucher_number": voucher_number,
                    "voucher_type": 'Journal',
                    "voucher_mode": "Journal",
                    "txn": count_txn + 1,
                    "doctor_id": retrieved_data['doctor_phone_id'],
                    "from_id": phone,
                    "to_id": payment_id,
                    "date": datetime.now(ZoneInfo("Asia/Kolkata")),
                    "Payment_id": payment_id,
                    "narration": 'Platform Fee',
                    "amount":float(fee),
                    "entries": [
                {
                "narration": "Platform Fee",
                "ledger_id": "A2",
                "ledger_name": "Doctor Fee Payble",
                "debit": float(fee),
                "credit": 0
                },
                {
                "narration": "Platform Fee",
                "ledger_id": "A9",
                "ledger_name": "OTC Fee",
                "debit": 0,
                "credit": float(fee)
                }
                
                ],
                    "created_by": "system",
                    "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }
                vouchers.insert_one(voucher)
                
            except:
                print(2)

            whatsapp_url = opd_msg(phone,name,index_number,date,slot)
            # whatsapp_url = success_appointment(doa,index_number,name,doa,tm,phone)

            try:
                opd_requests.delete_one({"_id": ObjectId(data.get("_id"))})
            except:
                print(0)

            

            document = appointment.find_one({"ref_id": data.get("_id")})

            if not document:
                return jsonify({
                    "success": False,
                    "message": "No appointment found"
                }), 404

            # Convert ObjectId to string
            document["_id"] = str(document["_id"])

            return jsonify({
                "success": True,
                "data": document
            }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_appointments_by_ref/<string:ref_id>", methods=["GET"])
def get_appointment_list_by_ref(ref_id):
    try:
        document = appointment.find_one({"ref_id": ref_id})

        if not document:
            return jsonify({
                "success": False,
                "message": "No appointment found"
            }), 404

        # Convert ObjectId to string
        document["_id"] = str(document["_id"])

        return jsonify({
            "success": True,
            "data": document
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500



@app.route("/tv-webhook/<string:id>", methods=["GET"])
def tvwebhook(id):
    try:
        documents = appointment.find_one(
            {"_id": ObjectId(id),"statusC":"checked"},
            {"patient_name": 1}
        )
        if not documents:
            return jsonify({"id": id, "status":False}), 200
        return jsonify({"id": id, "status":True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/redirect_razorpay_payment/<string:id>", methods=["GET"])
def redirect_razorpay_payment(id):
    try:
        retrieved_data = appointment.find_one({"razorpay_url": 'https://rzp.io/rzp/'+id})
        date = retrieved_data['date_of_appointment']
        name = retrieved_data['patient_name']
        time = retrieved_data['time_slot']
        dr = "Dr. Neeraj bansal"
        rs = "220.00"
        return render_template('payment.html', pay_url='https://rzp.io/rzp/'+id , date=date,name=name,time=time, rs=rs, dr=dr)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/redirect_razorpay_payment2/<string:id>", methods=["GET"])
def redirect_razorpay_payment2(id):
    try:
        retrieved_data = appointment.find_one({"razorpay_url": 'https://rzp.io/rzp/'+id})
        date = retrieved_data['date_of_appointment']
        name = retrieved_data['patient_name']
        time = retrieved_data['time_slot']
        dr = "Carelink"
        rs = "3.00"
        return render_template('payment.html', pay_url='https://rzp.io/rzp/'+id , date=date,name=name,time=time, rs=rs, dr=dr)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get_c2c_report", methods=["GET"])
def get_c2c_report():
    try:
        from_date = request.args.get("from")  # e.g. 2025-09-25
        to_date = request.args.get("to")      # e.g. 2025-09-30

        if not from_date or not to_date:
            return jsonify({"error": "from and to dates are required"}), 400

        # Convert "YYYY-MM-DD" → UNIX timestamp (seconds)
        try:
            from_ts = int(datetime.strptime(from_date, "%Y-%m-%d").timestamp())
            to_ts = int(datetime.strptime(to_date, "%Y-%m-%d").timestamp()) + 86399  # include full day
        except:
            return jsonify({"error": "Invalid date format (use YYYY-MM-DD)"}), 400

        # MongoDB query on timestamp field
        query = {
    "$expr": {
        "$and": [
            { "$gte": [ { "$toLong": "$timestamp" }, from_ts ] },
            { "$lte": [ { "$toLong": "$timestamp" }, to_ts ] },
        ]
    },
    "amount": { "$gt": 0 }
}

        docs = list(appointment.find(query, {
            "_id": 0,  # remove ObjectId to prevent JSON error
            "amount": 1,
            "appoint_number": 1,
            "pay_id": 1,
            "timestamp": 1
        }))

        # Convert timestamp → date
        for d in docs:
            try:
                ts = int(d["timestamp"])
                d["date"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            except:
                d["date"] = None
            
            d["platfarm_fee"] = 16.95
            d["gst"] = 3.05
            d["doctor_fee"] = 200

        if not docs:
            return jsonify({"error": "No appointments found"}), 404


        return jsonify(docs), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

from datetime import datetime

@app.route("/get_c2c_report2", methods=["GET"])
def get_c2c_report2():
    try:
        from_date = request.args.get("from")
        to_date = request.args.get("to")

        if not from_date or not to_date:
            return jsonify({"error": "from and to dates are required"}), 400

        # 🔥 Minimum allowed date (01-09-2025)
        min_date = datetime.strptime("2025-09-01", "%Y-%m-%d")

        try:
            user_from = datetime.strptime(from_date, "%Y-%m-%d")
            user_to = datetime.strptime(to_date, "%Y-%m-%d")

            # 🔥 Force from_date >= 01-09-2025
            final_from = max(user_from, min_date)

            from_ts = int(final_from.timestamp())
            to_ts = int(user_to.timestamp()) + 86399

        except:
            return jsonify({"error": "Invalid date format (use YYYY-MM-DD)"}), 400

        # 🔹 MAIN DATA QUERY
        query = {
            "$expr": {
                "$and": [
                    { "$gte": [{ "$toLong": "$timestamp" }, from_ts] },
                    { "$lte": [{ "$toLong": "$timestamp" }, to_ts] },
                ]
            },
            "amount": { "$gt": 0 }
        }

        docs = list(appointment.find(query, {
            "_id": 0,
            "amount": 1,
            "appoint_number": 1,
            "pay_id": 1,
            "timestamp": 1,
            "doctor_phone_id": 1
        }))

        # 🔹 PREVIOUS COUNT (only AFTER 01-09-2025)
        previous_query = {
            "$expr": {
                "$and": [
                    { "$gte": [{ "$toLong": "$timestamp" }, int(min_date.timestamp())] },
                    { "$lt": [{ "$toLong": "$timestamp" }, from_ts] }
                ]
            },
            "amount": { "$gt": 0 }
        }

        previous_count = appointment.count_documents(previous_query)

        # 🔥 RECEIPT NUMBER START
        receipt_counter = previous_count + 109

        updated_docs = []

        for d in docs:
            try:
                ts = int(d["timestamp"])
                d["date"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            except:
                d["date"] = None

            # 🔹 Static charges
            if d["doctor_phone_id"]=="67ee5e1bde4cb48c515073ee":
                d["platfarm_fee"] = 16.95
                d["gst"] = 3.05
                d["doctor_fee"] = 200
            else:
                d["platfarm_fee"] = float(d["amount"])/10 - ((float(d["amount"])/10) * 18 / 118)
                d["gst"] = ((float(d["amount"])/10) * 18 / 118)
                d["doctor_fee"] = float(d["amount"]) - float(d["amount"])/10


            # 🔥 Assign receipt number
            if receipt_counter > 809:
                d["receipt_no"] = f"CC{receipt_counter-809}"
            else:
                d["receipt_no"] = f"A{receipt_counter}"

            receipt_counter += 1
            updated_docs.append(d)

        return jsonify(updated_docs), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# @app.route("/get_c2c_report2", methods=["GET"])
# def get_c2c_report2():
#     try:
#         from_date = request.args.get("from")
#         to_date = request.args.get("to")

#         if not from_date or not to_date:
#             return jsonify({"error": "from and to dates are required"}), 400

#         # 🔹 Convert date → timestamp
#         try:
#             from_ts = int(datetime.strptime(from_date, "%Y-%m-%d").timestamp())
#             to_ts = int(datetime.strptime(to_date, "%Y-%m-%d").timestamp()) + 86399
#         except:
#             return jsonify({"error": "Invalid date format (use YYYY-MM-DD)"}), 400

#         # 🔹 MAIN DATA QUERY
#         query = {
#             "$expr": {
#                 "$and": [
#                     { "$gte": [{ "$toLong": "$timestamp" }, from_ts] },
#                     { "$lte": [{ "$toLong": "$timestamp" }, to_ts] },
#                 ]
#             },
#             "amount": { "$gt": 0 }
#         }

#         docs = list(appointment.find(query, {
#             "_id": 0,
#             "amount": 1,
#             "appoint_number": 1,
#             "pay_id": 1,
#             "timestamp": 1
#         }))

#         # 🔹 PREVIOUS COUNT (from_date se pehle)
#         previous_query = {
#             "$expr": {
#                 "$lt": [{ "$toLong": "$timestamp" }, from_ts]
#             },
#             "amount": { "$gt": 0 }
#         }

#         previous_count = appointment.count_documents(previous_query)

#         # 🔥 RECEIPT NUMBER START
#         receipt_counter = previous_count + 1

#         updated_docs = []

#         for d in docs:
#             try:
#                 ts = int(d["timestamp"])
#                 d["date"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
#             except:
#                 d["date"] = None

#             # 🔹 Static charges
#             d["platfarm_fee"] = 16.95
#             d["gst"] = 3.05
#             d["doctor_fee"] = 200

#             # 🔥 Assign receipt number
#             receipt_no = f"C{receipt_counter}"
#             d["receipt_no"] = receipt_no


#             receipt_counter += 1
#             updated_docs.append(d)

#         return jsonify(updated_docs), 200

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


import razorpay

# ---------- Razorpay Client ----------
razorpay_client = razorpay.Client(
    auth=("rzp_test_RqfTdh1uuEAroY", "N4jInbrfyCmpYmA1tib3TBgm")
)

# ---------- Create Order API ----------
@app.route("/create-order", methods=["POST"])
def create_order():
    try:
        data = request.get_json() or {}

        
        name = data.get("name")
        pname = data.get("fatherName")
        date = data.get("appointmentDate")
        slot = data.get("timeSlot")
        doctor_id = data.get("doctor_phone_id")
        email = data.get("email")
        symptoms = data.get("symptoms")
        age = data.get("age")
        timestamp = data.get("timestamp")
        from_number = "91" + data.get("mobile") if len(data.get("mobile")) == 10 else data.get("mobile")
        dob = data.get("dob")
        city = data.get("city")
        address = data.get("address")
        vaccine = data.get("isVaccination")
        sex = data.get("sex")
        
        if data.get("paymentMode")=='Online':

            dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
            fee = float(dxxocument.get('appointmentfee'))

            amount = fee  
            amount_in_paisa = amount * 100

            order_data = {
                "amount": amount_in_paisa,
                "currency": "INR",
                "receipt": "receipt_001",
            }

            order = razorpay_client.order.create(order_data)

            dataset = {
            'sex':sex,
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
            "vaccine":vaccine,
            'razorpay_url':order['id'],
            'payment_status':'link generated',
            'appointment_type':'qr'
                }
        
            id = str(appointment.insert_one(dataset).inserted_id)
            print(id)

            tempdata = {"number":from_number,"current_id":id,"_id":from_number}
            try:
                templog.insert_one(tempdata)
            except:
                templog.update_one({'_id': from_number}, {'$set': tempdata})

            
            return jsonify(order)


    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------- Payment Verification (Optional) ----------
@app.route("/verify-payment", methods=["POST"])
def verify_payment():
    try:
        data = request.get_json()

        order_id = data.get("razorpay_order_id")
        payment_id = data.get("razorpay_payment_id")
        signature = data.get("razorpay_signature")

        params = {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature
        }

        # Verify signature
        razorpay_client.utility.verify_payment_signature(params)





        short_url = order_id

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

        dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        fee = float(dxxocument.get('appointmentfee'))

        index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)


        doc_id = ObjectId(retrieved_data['_id'])
        appointment.update_one({'_id': doc_id},{'$set':{'payment_status':'paid','status':'success','pay_id':payment_id,'appoint_number':appoint_number,'amount':fee,'appointment_index':index_number}})


        name = str(retrieved_data['patient_name'])
        payment_id = str(payment_id)
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
                        'appointment_type':'qr',
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
                    "ledger_id": "A12",
                    "ledger_name": "CGST",
                    "debit": 0,
                    "credit": 3.05/2
                    },
                     {
                    "narration": "Appointment Fee",
                    "ledger_id": "A13",
                    "ledger_name": "SGST",
                    "debit": 0,
                    "credit": 3.05/2
                    }
                    ],
                        "created_by": "system",
                        "created_at": ist_now
                    }
                    vouchers.insert_one(voucher)
        except:
                print(2)


        senddata = {
            'date_of_appointment':doa,
            'appointment_index':index_number,
            'name':name,
            'payment_id':payment_id,
            'time_slot':tm,
            'phone':phone,
            'appoint_number':appoint_number,
            "status": "Payment Verified"
        }

        return jsonify(senddata)

    except Exception as e:
        return jsonify({"error": "Verification Failed", "details": str(e)}), 400





@app.route("/manage_opd_requests", methods=["POST", "GET", "DELETE"])
def manage_opd_requests():
    try:
        # =====================
        # INSERT DATA
        # =====================
        if request.method == "POST":
            data = request.json

            if not data:
                return jsonify({"error": "No data provided"}), 400

            result = opd_requests.insert_one(data)

            return jsonify({
                "message": "Data inserted successfully",
                "id": str(result.inserted_id)
            }), 201

        # =====================
        # GET LIST
        # =====================
        if request.method == "GET":
            items = []
            for doc in opd_requests.find():
                doc["_id"] = str(doc["_id"])
                items.append(doc)

            return jsonify(items), 200

        # =====================
        # DELETE DATA
        # =====================
        if request.method == "DELETE":
            item_id = request.args.get("id")

            if not item_id:
                return jsonify({"error": "id is required"}), 400

            result = opd_requests.delete_one({"_id": ObjectId(item_id)})

            if result.deleted_count == 0:
                return jsonify({"error": "Data not found"}), 404

            return jsonify({"message": "Data deleted successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
phone_id = '563776386825270'


def book_current_appointment(data):

    from datetime import datetime, time

    now = datetime.now(ZoneInfo("Asia/Kolkata")).time()

    if now < time(8,30) or now > time(18,0):
        return "8:30 AM ke pahle aur 6 PM ke baad booking allowed nahi hai", 200


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

    if response_data.get('date_of_birth'):
        dob = response_data.get('date_of_birth')
    else:
        dob = 'none'

    from_number = message_info.get('from')
    timestamp = message_info.get('timestamp')

    doctor_id = '67ee5e1bde4cb48c515073ee'


    dataset = {
        'appointmenttype':'current',
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

        dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        fee = float(dxxocument.get('appointmentfee'))
        # paymentlink = dxxocument.get('paymentlink')

        tempdata = {"number":from_number,"current_id":id,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        admin = db["admin"] 
        dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
        razorpayid = dxocument.get('razorpayid')
        razorpaykey = dxocument.get('razorpaykey')

        razorpayid = 'rzp_test_RqfTdh1uuEAroY'
        razorpaykey = 'N4jInbrfyCmpYmA1tib3TBgm'


        # link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)

        # link = f"order_{secrets.token_hex(8)}"
        # doc_id = ObjectId(id)
        # appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':link,'payment_status':'link generated'}})

        link = pay_link('name', from_number, 'email', id, 'rs', 'rzid', 'rzk')

        # link = paymentlink
        print(link)
        amount = fee
        return send_payment_flow(from_number,name,date,slot,amount,link)
    
def sameordef(from_number, name):
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

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




def current_flow2(from_number):

    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    incoming_data = { 
    "messaging_product": "whatsapp", 
    "to": from_number, 
    "type": "template", 
    "template": { 
        "name": "new_current_booking", 
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



def send_selection_enroll_current(from_number):

    result = list(appointment.find({"whatsapp_number": from_number,"doctor_phone_id": '67ee5e1bde4cb48c515073ee'}))
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
            "father":str(record["guardian_name"]),
            "sex": record.get('sex','f')
                })

    # all_buttons = latest_appointments + [{"id": "book_appointment", "title": "New Patient"},{"id": "enrole-patient", "title": "Enrole Patient"},{"id": "Re-Appointment", "title": "Re-Appointment"}]


    rows = [
    {
        "id": str(app["id"]),
        "title": app["title"],
        "description": (
            f"S/o {app['father']}" if app["sex"] == "Male"
            else f"D/o {app['father']}" if app["sex"] == "Female"
            else f"Father's Name: {app['father']}"
        )
    }
    for app in latest_appointments[-10:]
]

    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

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
      "text": "Please Proceed for Booking – Existing Patients"
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



def book_current_appointment_by_selectedlist(from_number,cutname,father,timestamp,dob,sex):

    from datetime import datetime, time

    now = datetime.now(ZoneInfo("Asia/Kolkata")).time()

    if now < time(8,30) or now > time(18,0):
        return "8:30 AM ke pahle aur 6 PM ke baad booking allowed nahi hai", 200
    

    name = cutname
    pname = father
    date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    slot = "current"
    vaccine = "No"

    email = 'none'
    symptoms = 'none'
    age = 'none'
    # dob = 'none'
    city = 'none'
    address = 'none'

    from_number = from_number
    timestamp = timestamp

    doctor_id = '67ee5e1bde4cb48c515073ee'


    dataset = {
        'appointmenttype':'current',
        'patient_name': name,
        'guardian_name': pname,
        'date_of_appointment': date,
        'time_slot': slot,
        'doctor_phone_id':doctor_id,
        'email' : email,
        'symptoms' : symptoms,
        'age' : age,
        'sex': sex,
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
            templog2.insert_one({**dataset,'_id': from_number})
        except:
            templog2.update_one({'_id': from_number}, {'$set': dataset})

        return sameordef(from_number,name)

    else:

        id = str(appointment.insert_one(dataset).inserted_id)
        print(id)

        dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        fee = float(dxxocument.get('appointmentfee'))
            # paymentlink = dxxocument.get('paymentlink')

        tempdata = {"number":from_number,"current_id":id,"_id":from_number}
        try:
                templog.insert_one(tempdata)
        except:
                templog.update_one({'_id': from_number}, {'$set': tempdata})
        admin = db["admin"] 
        dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
        razorpayid = dxocument.get('razorpayid')
        razorpaykey = dxocument.get('razorpaykey')

        razorpayid = 'rzp_test_RqfTdh1uuEAroY'
        razorpaykey = 'N4jInbrfyCmpYmA1tib3TBgm'


        # link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)

        # link = f"order_{secrets.token_hex(8)}"
        # doc_id = ObjectId(id)
        # appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':link,'payment_status':'link generated'}})

        link = pay_link('name', from_number, 'email', id, 'rs', 'rzid', 'rzk')


            # link = paymentlink
        # print(link)
        amount = fee
        return send_payment_flow(from_number,name,date,slot,amount,link)
        



def current_success_appointment(name,whatsapp_no,doc_id,fee,fname):
    url = f"https://graph.facebook.com/v22.0/563776386825270/messages"
    payload = { 
        "messaging_product": "whatsapp", 
        "to": whatsapp_no, "type": "template", 
        "template": { 
            "name": "payment_information", 
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
                },
                {
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
                    "text": whatsapp_no
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
    url = f"https://graph.facebook.com/v22.0/563776386825270/messages"
    payload = { 
        "messaging_product": "whatsapp", 
        "to": number, "type": "template", 
        "template": { 
            "name": "dr_payment_info", 
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




def stop_current_booking_request(id):
    try:
        doc_id = ObjectId(id)
        document = doctors.find_one({"_id": doc_id})
        data = document.get('COPDstoptime',{})
    
        # data = {'date': '2026-03-21', 'time': '19:00', 'status': False}
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        currentdate = now.strftime("%Y-%m-%d")
        currenttime = now.time()   # ✅ FIX
    
        # convert string time to time object
        booking_time = datetime.strptime(data.get('time'), "%H:%M").time()
    
        if (
            data.get('date') == currentdate and
            data.get('status') == True and
            booking_time <= currenttime
        ):
            return False
        else:
            return True
    except Exception as e:
        return True
            




def hi_reply(from_number):
    from datetime import datetime, timedelta, time
    headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages" 
    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    date_verify = currentdateverify()

    nextdate_verify = nextdateverify()

    nextdatetrue = True
    if nextdate_verify.get('enabled')==False:
        nextdatetrue = False

    datetrue = True
    if date_verify.get('enabled')==False:
        datetrue = False

    COPD = stop_current_booking_request('67ee5e1bde4cb48c515073ee')

    cutoff = time(8, 30)  # 8:30 AM

    # decide booking date
    if now.time() >= cutoff:
        booking_date = now + timedelta(days=1)
    else:
        booking_date = now

    formatted_date = booking_date.strftime("%d-%m-%Y")
    # formatted_date = booking_date.strftime("%-d %b.")

    incoming_data = {}

    now = datetime.now(ZoneInfo("Asia/Kolkata")).time()
    if time(8,30) <= now < time(18,0) and datetrue and COPD:
        if nextdatetrue:
            incoming_data = {
          "messaging_product": "whatsapp",
          "to": from_number,
          "type": "interactive",
          "interactive": {
            "type": "button",
            "body": {
              "text": "Please choose an option:"
            },
            "action": {
              "buttons": [
                {
                  "type": "reply",
                  "reply": {
                    "id": "today",
                    "title": "Book for Today"
                  }
                },
                {
                  "type": "reply",
                  "reply": {
                    "id": "tomorrow",
                    "title": f"Book for {formatted_date}"
                  }
                }
              ]
            }
          }
        }
        else:
            incoming_data = {
          "messaging_product": "whatsapp",
          "to": from_number,
          "type": "interactive",
          "interactive": {
            "type": "button",
            "body": {
              "text": "Please choose an option:"
            },
            "action": {
              "buttons": [
                {
                  "type": "reply",
                  "reply": {
                    "id": "today",
                    "title": "Book for Today"
                  }
                },
                # {
                #   "type": "reply",
                #   "reply": {
                #     "id": "tomorrow",
                #     "title": f"Book for {formatted_date}"
                #   }
                # }
              ]
            }
          }
        }
            
    else:
        incoming_data = {
  "messaging_product": "whatsapp",
  "to": from_number,
  "type": "interactive",
  "interactive": {
    "type": "button",
    "body": {
      "text": "Please Tap below to:"
    },
    "action": {
      "buttons": [
        # {
        #   "type": "reply",
        #   "reply": {
        #     "id": "today",
        #     "title": "Current Booking"
        #   }
        # },
        {
          "type": "reply",
          "reply": {
            "id": "tomorrow",
            "title": f"Book for {formatted_date}"
          }
        }
      ]
    }
  }
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    # print(jsonify(response.json()))
    return "OK", 200



@app.route("/api/patientsx/<string:did>", methods=["GET"])
def get_patientsxx(did):
    print('hy')


    date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    # date = '2026-03-09'

    documents = list(appointment.find({
        "amount":{"$gt": -1},
        "date_of_appointment": date,
        "doctor_phone_id": did,
        "appointmenttype": 'current'
    }))

    patients = []

    for doc in documents:
        try:
            appointment_index = int(doc.get("appointment_index", 0))
        except:
            appointment_index = 111
        patients.append({
            "id": str(doc["_id"]),
            "name": doc.get("patient_name",""),
            "fatherName": doc.get("guardian_name",""),
            "gender": doc.get("sex",""),
            "mobile": doc.get("whatsapp_number",""),
            "appointmentNo": "" if appointment_index > 110 else appointment_index
        })

    print('hy')

    return jsonify(patients)


def is_before_end(slot):
    # Split slot
    start_str, end_str = slot.split(" - ")

    # Convert end time
    end_time = datetime.strptime(start_str, "%I:%M %p").time()

    # Current time
    now_time = datetime.now(ZoneInfo("Asia/Kolkata")).time()

    print(now_time , end_time)

    # Check
    return now_time > end_time

@app.route("/api/assign", methods=["POST"])
def assign():
    date = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    data = request.json
    timeslot = getNumberToSlot(int(data["number"]))
    appointment.update_one(
        {"_id": ObjectId(data["id"])},
        {"$set": {"appointment_index": data["number"],"time_slot": timeslot}}
    )

    if is_before_end(timeslot):
        timeslot = 'x'


    success_appointment(date,data["number"],data["name"],date,timeslot,data["mobile"])
    return jsonify({"status":"success"})


@app.route("/cb_dashboard")
def dashboardcurrentbooking():
    return render_template("currentbooking.html")


def format_time(t):
    return datetime.strptime(t, "%H:%M").strftime("%I:%M %p")

def getNumberToSlot(num):
    doc_id = ObjectId("67ee5e1bde4cb48c515073ee")
    document = doctors.find_one({"_id": doc_id})

    slots = document['slots']['slotsvalue']

    current = 0

    for s in slots:
        maxno = int(s['maxno'])
        current += maxno

        if num <= current:
            stime = format_time(s['slot']['stime'])
            etime = format_time(s['slot']['etime'])

            return f"{stime} - {etime}"

    return None



def cd_url(fm):
    headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"
    incoming_data ={
  "messaging_product": "whatsapp",
  "to": fm,
  "type": "interactive",
  "interactive": {
    "type": "cta_url",
    "body": {
      "text": "Click below to open Today Booking List"
    },
    "action": {
      "name": "cta_url",
      "parameters": {
        "display_text": "Open List",
        "url": "https://api.care2connect.in/cb_dashboard"
      }
    }
  }
}
    response = requests.post(external_url, json=incoming_data, headers=headers)
    return 'ok',200

def refund_url(fm):
    headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"
    incoming_data ={
  "messaging_product": "whatsapp",
  "to": fm,
  "type": "interactive",
  "interactive": {
    "type": "cta_url",
    "body": {
      "text": "Click below to open List for refund amount"
    },
    "action": {
      "name": "cta_url",
      "parameters": {
        "display_text": "Open List",
        "url": "https://api.care2connect.in/function_refund/refund/67ee5e1bde4cb48c515073ee"
      }
    }
  }
}
    response = requests.post(external_url, json=incoming_data, headers=headers)
    return 'ok',200


@app.route("/testapii", methods=["GET"])
def testapii():
    
    voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))
    date_str = voucher_date.strftime("%Y-%m-%d")
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    start = datetime(date_obj.year, date_obj.month, date_obj.day)
    end = start + timedelta(days=1)

    updatedstart = datetime(date_obj.year, date_obj.month, date_obj.day)
    updatedend = datetime(date_obj.year, date_obj.month, date_obj.day, 23, 59, 59)


    utc_now = datetime.now(ZoneInfo("UTC"))

    # Step 2: IST me convert karo
    ist_now = utc_now.astimezone(ZoneInfo("Asia/Kolkata"))
    voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))


    return jsonify({
            "old_start": start,
            "old_end": end,
            "updatedstart" :updatedstart,
            "updatedend" : updatedend,
            "ist_now_old" :voucher_date,
            "new_date" : ist_now
        }), 200



def delete_copd_time(id,fromnumber):
    try:
        doc_id = ObjectId(id)

        result = doctors.update_one(
            {"_id": doc_id},
            {"$unset": {"COPDstoptime": ""}}
        )

        if result.matched_count == 0:
            return jsonify({"success": False, "message": "Doctor not found"}), 404
        
        headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
        external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"
        incoming_data ={
  "messaging_product": "whatsapp",
  "to": fromnumber,
  "type": "text",
  "text": {
    "body": 'No changes made.Current booking is still active.'
  }
}
        response = requests.post(external_url, json=incoming_data, headers=headers)

        return 'ok', 200

    except Exception as e:
        return 'ok', 200
    
def update_status_copd(id, fromnumber):
    try:
        doc_id = ObjectId(id)

        document = doctors.find_one({"_id": doc_id})
        data = document.get('COPDstoptime',{})

        result = doctors.update_one(
            {"_id": doc_id},
            {"$set":{'COPDstoptime':{"status": True, 'time':data.get('time'), 'date':data.get('date')}} }
        )

        if result.matched_count == 0:
            return jsonify({"success": False, "message": "Doctor not found"}), 404
        
        headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
        external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"
        incoming_data ={
  "messaging_product": "whatsapp",
  "to": fromnumber,
  "type": "text",
  "text": {
    "body": f'The current booking will be closed at {data.get('time')}'
  }
}
        response = requests.post(external_url, json=incoming_data, headers=headers)

        return 'ok', 200

    except Exception as e:
        return 'ok', 500
    

    


headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"

@app.route("/v1/send-stop-booking/<string:id>", methods=["POST"])
def send_stop_msg(id):
    try:
        data = request.get_json()


        date = data.get("date")          # 2026-03-21
        time = data.get("time") 
        
        doctors.update_one(
            {"_id": ObjectId(id)},
            {"$set":{'COPDstoptime':{"status": False, 'time':data.get('time'), 'date':data.get('date')}} }
        )     

        time = datetime.strptime(time, "%H:%M").strftime("%I:%M %p")

        url = external_url

        incoming_data = {
            "messaging_product": "whatsapp",
            "to": '916265578975',
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": f"Do you want to stop current booking on {date} at {time}?"
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "YES_STOP",
                                "title": "Yes"
                            }
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": "NO_CONTINUE",
                                "title": "No"
                            }
                        }
                    ]
                }
            }
        }
        incoming_data2 = {
            "messaging_product": "whatsapp",
            "to": '918128265003',
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": f"Do you want to stop current booking on {date} at {time}?"
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "YES_STOP",
                                "title": "Yes"
                            }
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": "NO_CONTINUE",
                                "title": "No"
                            }
                        }
                    ]
                }
            }
        }
        response = requests.post(url, json=incoming_data, headers=headers)
        response = requests.post(url, json=incoming_data2, headers=headers)

        return jsonify({
            "success": True,
            "whatsapp_response": response.json()
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500



from api_files.utils import duniyape_db
@app.route("/get_test_report_combind", methods=["GET"])
def get_test_report():
    try:
        from_date = request.args.get("from")
        to_date = request.args.get("to")

        if not from_date or not to_date:
            return jsonify({"error": "from and to dates are required"}), 400

        # 🔥 Minimum allowed date (01-09-2025)
        min_date = datetime.strptime("2025-09-01", "%Y-%m-%d")

        try:
            user_from = datetime.strptime(from_date, "%Y-%m-%d")
            user_to = datetime.strptime(to_date, "%Y-%m-%d")

            # 🔥 Force from_date >= 01-09-2025
            final_from = max(user_from, min_date)

            from_ts = int(final_from.timestamp())
            to_ts = int(user_to.timestamp()) + 86399

        except:
            return jsonify({"error": "Invalid date format (use YYYY-MM-DD)"}), 400

        # 🔹 MAIN DATA QUERY
        query = {
            "$expr": {
                "$and": [
                    { "$gte": [{ "$toLong": "$timestamp" }, from_ts] },
                    { "$lte": [{ "$toLong": "$timestamp" }, to_ts] },
                ]
            },
            "amount": { "$gt": 0 }
        }

        docs = list(appointment.find(query, {
            "_id": 0,
            "amount": 1,
            "appoint_number": 1,
            "pay_id": 1,
            "timestamp": 1,
            "doctor_phone_id": 1
        }))

        # 🔹 PREVIOUS COUNT (only AFTER 01-09-2025)
        previous_query = {
            "$expr": {
                "$and": [
                    { "$gte": [{ "$toLong": "$timestamp" }, int(min_date.timestamp())] },
                    { "$lt": [{ "$toLong": "$timestamp" }, from_ts] }
                ]
            },
            "amount": { "$gt": 0 }
        }

        previous_count = appointment.count_documents(previous_query)

        # 🔥 RECEIPT NUMBER START
        receipt_counter = previous_count + 109

        updated_docs = []

        for d in docs:
            try:
                ts = int(d["timestamp"])
                d["date"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
            except:
                d["date"] = None

            # 🔹 Static charges
            if d["doctor_phone_id"]=="67ee5e1bde4cb48c515073ee":
                d["platfarm_fee"] = 16.95
                d["gst"] = 3.05
                d["doctor_fee"] = 200
            else:
                d["platfarm_fee"] = float(d["amount"])/10 - ((float(d["amount"])/10) * 18 / 118)
                d["gst"] = ((float(d["amount"])/10) * 18 / 118)
                d["doctor_fee"] = float(d["amount"]) - float(d["amount"])/10


            # 🔥 Assign receipt number
            if receipt_counter > 809:
                d["receipt_no"] = f"CC{receipt_counter-809}"
            else:
                d["receipt_no"] = f"A{receipt_counter}"

            receipt_counter += 1
            updated_docs.append(d)

        # eefbfeu

        vouchers = duniyape_db["vouchers"] 
        try:
            from_date = datetime.strptime(from_date, "%Y-%m-%d") if from_date else None
            to_date = datetime.strptime(to_date, "%Y-%m-%d") if to_date else None
        except Exception:
            return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

        # ✅ IST → UTC conversion (IMPORTANT)
        if from_date:
            from_date = from_date.replace(tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(ZoneInfo("UTC"))

        if to_date:
            to_date = to_date.replace(hour=23, minute=59, second=59)
            to_date = to_date.replace(tzinfo=ZoneInfo("Asia/Kolkata")).astimezone(ZoneInfo("UTC"))

        # ✅ Opening balance
        opening_balance = 0
        if from_date:
            before_cursor = vouchers.find({
                "entries.ledger_id": "A6",
                "date": {"$lt": from_date}
            })

            for doc in before_cursor:
                for entry in doc.get("entries", []):
                    if entry.get("ledger_id") == "A6":
                        opening_balance += (entry.get("debit", 0) - entry.get("credit", 0))

        # ✅ Query
        query = {"entries.ledger_id": "A6"}

        if from_date and to_date:
            query["date"] = {"$gte": from_date, "$lte": to_date}
        elif from_date:
            query["date"] = {"$gte": from_date}
        elif to_date:
            query["date"] = {"$lte": to_date}

        results = vouchers.find(query)

        ledger_entries = []

        for doc in results:
            for entry in doc.get("entries", []):
                if entry.get("ledger_id") == "A6":

                    # 🔥 UTC → IST convert (response)
                    ist_date = None
                    ist_timestamp = None
                    if doc.get("date"):
                        ist_date = doc["date"].astimezone(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
                        ist_timestamp = int(
                            doc["date"]
                            .astimezone(ZoneInfo("Asia/Kolkata"))
                            .timestamp()
                        )

                    taxable_value = entry.get("credit") * 100 / 18

                    ledger_entries.append({
                        "doctor_phone_id":"Duniyape Technologies Private Limited",
                        "appoint_number":doc.get("Payment_id"),
                        "timestamp" : ist_timestamp,
                        "amount": float(entry.get("credit"))+float(taxable_value),
                        "platfarm_fee": float(taxable_value),
                        "doctor_fee": taxable_value,
                        "pay_id": doc.get("voucher_number"),
                        "receipt_no": doc.get("Payment_id"),
                        "voucher_type": doc.get("voucher_type"),
                        "voucher_mode": doc.get("voucher_mode"),
                        "txn": doc.get("txn"),
                        "ledger_id": entry.get("ledger_id"),
                        "ledger_name": entry.get("ledger_name"),
                        "gst": entry.get("credit"),
                        # "debit": entry.get("debit"),
                        "narration": entry.get("narration"),
                        "date": ist_date,   # ✅ fixed
                    })

        # ⚠️ sort UTC pe karo ya IST string pe?
        

        merged =  ledger_entries + updated_docs

        merged.sort(key=lambda x: x["date"])

        return jsonify(merged), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    app.run(port=5000,host="0.0.0.0")


# if __name__ == "__main__":
#     app.run(port=5001,debug=True)


































