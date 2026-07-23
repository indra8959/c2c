from flask import Blueprint, request, jsonify, redirect, render_template
import re
from datetime import datetime, timedelta
import time
import requests
from zoneinfo import ZoneInfo
import pyrebase


# ==============================
# Firebase Configuration
# ==============================

firebase_config = {
    'apiKey': "AIzaSyD1r_vMcdSZIFm_Rt3dqk4iYkhZtZdmTpg",
  'authDomain': "swami-vivekanand-55049.firebaseapp.com",
  'databaseURL': "https://swami-vivekanand-55049-default-rtdb.asia-southeast1.firebasedatabase.app",
  'projectId': "swami-vivekanand-55049",
  'storageBucket': "swami-vivekanand-55049.firebasestorage.app",
  'messagingSenderId': "194399605356",
  'appId': "1:194399605356:web:a44fb61d91817f41313e49",
  'measurementId': "G-J13HJWJW23"
}

firebase = pyrebase.initialize_app(firebase_config)
db = firebase.database()
auth = firebase.auth()



vivekanand = Blueprint("vivekanand", __name__)



headers={'Authorization': 'Bearer EAAbAwRr2ZCXsBQwLR9DwNV7dMm89JjxZBxMhHyOQ9gjZCZAhyxRjMWGdeOSoSsUH95YHLYBZBhSKxqFY1ZBmViIjZC0pQ7VfKb004pNvqSK28ZBxvXFS5libET7cBUWHLHDG7N03ATJZAq674bAlazxmFZCkHGdPMQzmqZA1x4RlZB5aL5gT9l4xNaDn6r0b860O9uquwAZDZD','Content-Type': 'application/json'}



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

@vivekanand.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        VERIFY_TOKEN = "vivekanand"
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
            

            message_info = value.get('messages', [])[0]  # Extract first message
            contact_info = value.get('contacts', [])[0]  # Extract first contact

            from_number = message_info.get('from')
            body = message_info.get('text', {}).get('body')
            msg_type = message_info.get('type')
            msg_type = message_info.get('type')
            timestamp = message_info.get('timestamp')
            name = contact_info.get('profile', {}).get('name')

            if is_recent(timestamp)==False:

                try:
                    status_obj = value.get('messages', [])[0] 
                    print(status_obj)
                    if status_obj.get("type") == "location":
                        
                        return attendence(status_obj)
                    else :
                        pass

                except Exception:
                    pass

                if msg_type == 'interactive' and "button_reply" in message_info.get('interactive', {}):
                    button_id = message_info["interactive"]["button_reply"]["id"]
                    print(button_id)
                    if button_id.startswith("o_"):
                        prefix, unique_id = button_id.split("_", 1)
                        return sendattandence(from_number,timestamp,'Official Duty',unique_id,'RO')
                    elif button_id.startswith("l_"):
                        prefix, unique_id = button_id.split("_", 1)
                        return sendattandence(from_number,timestamp,'Leave',unique_id,'RL')
                  
                    else:
                        return "Invalid message type", 400
                else:
                    print(body.lower())
                    return "Invalid message type", 400
            else: 
                return "Invalid message type", 400

        except Exception as e:
            print("Error:", str(e))
            return jsonify({"error": "Invalid request"}), 400


def sendattandence(recipientNumber,timestamp,btntype,id,r):
    external_url = "https://graph.facebook.com/v22.0/10268277353836/messages"
    ist_time = datetime.fromtimestamp(int(timestamp), ZoneInfo("Asia/Kolkata"))
    xist_time = ist_time.strftime("%d %B %Y at %I:%M %p")
    payload = {
  'messaging_product': 'whatsapp',
  'receipient_type':"individual",
  'to': recipientNumber,
  'text':{'body':f"✅ Your request for {btntype} on {xist_time} has been successfully submitted."},
  'type': 'text'
    }

    

    check = db.child('leave_requests') \
            .order_by_child('dates/0') \
            .equal_to(ist_time.strftime("%Y-%m-%d")) \
            .get()

    exists = False

    if check.val():
        for key, value in check.val().items():
            if value.get("staffId") == id:
                exists = True
                break

    if not exists:

        staff_ref = db.child("log").child(id).get()
        data = staff_ref.val()
        data['appliedAt'] = data['timestamp']
        data['dates'] ={ 0:ist_time.strftime("%Y-%m-%d")}
        data['empName'] = data['name']
        data['note'] = f'auto generate for {btntype}'
        data['staffId'] = data['id']
        data['status'] = 'PENDING'
        data['type'] = 'Personal Leave'

        result = db.child('leave_requests').push(data)
        response = requests.post(external_url, json=payload, headers=headers)

        print(response)

    return "OK", 200


import math

def attendence(data):

    fromNum = data.get("from")
    timestamp = int(data.get("timestamp"))
    lat = float(data['location']['latitude'])
    long = float(data['location']['longitude'])

    ist_time_obj = datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Kolkata"))
    ist_time = ist_time_obj.strftime("%d %B %Y at %I:%M %p")

    print(lat, long, ist_time)

    # ==============================
    # Distance Calculation
    # ==============================
    def calculate_distance(lat1, lon1, lat2, lon2):
        R = 6371000

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2) ** 2 + \
            math.cos(phi1) * math.cos(phi2) * \
            math.sin(delta_lambda / 2) ** 2

        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    distance = calculate_distance(22.1696313, 80.0265435, lat, long)
    print("Distance:", distance, "meters")

    payload = {}

    # ==============================
    # Find Employee (Firebase)
    # ==============================

    number = fromNum

    if number.startswith("91"):
        number = number[2:]

    print(number)

    staff_ref = db.child("employees")

    staff_data = staff_ref.order_by_child("mobile").equal_to(number).get()


    employee = None
    employee_key = None

    if staff_data.val():
        for key, value in staff_data.val().items():
            # if value.get("designation") == "699adeffef0f329d90a0f35e":
                employee = value
                # employee_key = key
                break

    if not employee:
        print("User not found")
        return "User not found", 404
    
    print(employee)

    emp_name = employee.get("fullName")
    yist_time = ist_time_obj.strftime("%Y-%m")
    dist_time = ist_time_obj.day
    
    fake = True

    location_name = data.get('location', {}).get('name')

    if location_name and location_name.strip():
        fake = False


    from datetime import time
    now = datetime.now(ZoneInfo("Asia/Kolkata")).time()
     

    # ==============================
    # Within  meters
    # ==============================
    if distance <= 100 and fake and time(10,0) <= now < time(11,0):

        attendance_data = {
            'name': emp_name,
            'phone': number,
            'status': 'present',
            'role': 'attendance',
            'timestamp':timestamp,
            'date': ist_time_obj.isoformat(),
            'lat': lat,
            'long': long
        }
        


        check = db.child('leave_requests') \
                .order_by_child('dates/0') \
                .equal_to(ist_time_obj.strftime("%Y-%m-%d")) \
                .get()

        exists = False

        if check.val():
            for key, value in check.val().items():
                if value.get("staffId") == employee.get("staffId"):
                    exists = True
                    break

        if exists:
            return 'ok',200
        attendance_ref = db.child("attendance").child(employee.get("staffId")).child(yist_time).child(dist_time)
        if attendance_ref.get().val():
            print('exist')
            return 'ok',200
        attendance_ref = db.child("attendance").child(employee.get("staffId")).child(yist_time).child(dist_time)
        attendance_ref.update(attendance_data)

        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': "individual",
            'to': fromNum,
            'type': 'text',
            'text': {
                'body': f"✅ Your attendance for {ist_time} has been successfully recorded."
            }
        }

        print('Attendance marked Present')

    # ==============================
    # Outside 50 meters
    # ==============================
    else:

        attendance_ref = db.child("attendance").child(employee.get("staffId")).child(yist_time).child(dist_time)
        if attendance_ref.get().val():
            print('exist')
            return 'ok',200

        attendance_data = {
            'name': emp_name,
            'phone': fromNum,
            'status': 'pending',
            'role': 'attendance',
            'timestamp':timestamp,
            'date': ist_time_obj.isoformat(),
            'lat': lat,
            'long': long,
            'month': yist_time,
            'dist_time':dist_time,
            'id': employee.get("staffId")
        }

        reff = db.child('log').child(employee.get("staffId"))


        reff.update(attendance_data)
        payload = {
            "messaging_product": "whatsapp",
            "to": fromNum,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": "Location is outside 100 meters"
                },
                "footer": {
                    "text": "Please choose one option:"
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": f"o_{employee.get("staffId")}",
                                "title": "Apply Official Duty"
                            }
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": f"l_{employee.get("staffId")}",
                                "title": "Apply for Leave"
                            }
                        }
                    ]
                }
            }
        }

        print('Attendance marked Outside Location')

    # ==============================
    # Send WhatsApp Message
    # ==============================

    external_url = "https://graph.facebook.com/v22.0/1025068277353836/messages"
    response = requests.post(external_url, json=payload, headers=headers)

    print(response.text)

    return "OK", 200
