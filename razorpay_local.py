import requests
import json
import re
import time
from threading import Thread
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pymongo import MongoClient
import secrets
from bson.objectid import ObjectId

MONGO_URI = "mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.get_database("caredb")
doctors = db["doctors"] 
appointment = db["appointment"] 
templog = db["logs"] 
disableslot = db["disableslot"] 

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


# def pay_link(name, number, email, id, rs, rzid, rzk):
#     """
#     Creates a Razorpay payment link and schedules it to expire after 5 minutes.
#     Returns the payment ID or 'x' if failed.
#     """
#     # Razorpay API URL
#     url = "https://api.razorpay.com/v1/payment_links"

#     # Payment Data
#     data = {
#         "amount": int(rs * 100),  # Convert to paise
#         "currency": "INR",
#         "description": "Payment for service",
#         "customer": {
#             "name": name,
#             # "email": email,
#             "contact": number
#         },
#         "notify": {
#             "sms": False,
#             "email": False
#         },
#         "callback_url": f"https://api.care2connect.in/payment_callback2/{id}/",
#         "callback_method": "get"
#     }

#     # Send Request
#     response = requests.post(url, auth=(rzid, rzk), json=data)

#     if response.status_code == 200:
#         payment_data = response.json()
#         short_url = payment_data.get("short_url")
#         payment_link_id = payment_data.get("id")

#         print("Payment Link Created:", short_url)

#         doc_id = ObjectId(id)
#         appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':short_url,'payment_status':'link generated'}})

#         # Start a background thread to auto-expire the link after 5 minutes
#         expiry_thread = Thread(target=expire_payment_link, args=(payment_link_id, rzid, rzk))
#         expiry_thread.start()

#         # Extract and return payment ID from short_url
#         match = re.search(r"/rzp/([\w\d]+)", short_url)
#         if match:
#             return match.group(1)
#     else:
#         print("Error creating payment link:", response.text)

#     return 'x'


def payment_link_canceled(link, from_number):
    """Expires a Razorpay payment link by sending a POST to /cancel."""
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"

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
        headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
        response = requests.post(external_url, json=incoming_data, headers=headers)

        if response.status_code == 200:
            print("Payment link expired successfully.")
        else:
            print("Failed to expire payment link:", response.text)



def pay_link(name, number, email, id, rs, rzid, rzk):
    link = f"order_{secrets.token_hex(8)}"
    doc_id = ObjectId(id)
    appointment.update_one({'_id': doc_id}, {'$set': {'razorpay_url':link,'payment_status':'link generated'}})

    expiry_thread = Thread(target=payment_link_canceled, args=(link, number))
    expiry_thread.start()

    return link
