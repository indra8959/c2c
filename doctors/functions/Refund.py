from flask import Flask, request, jsonify, Blueprint, render_template
from pymongo import MongoClient
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bson.objectid import ObjectId

function_refund = Blueprint("function_refund", __name__)

# MongoDB Connection
client = MongoClient("mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client["caredb"]
appointment = db["appointment"]
vouchers = db["vouchers"] 
doctors = db["doctors"]

# Razorpay Credentials
RAZORPAY_KEY_ID = "rzp_live_R9tGl7bLSIBV6f"
RAZORPAY_KEY_SECRET = "dTvrApHzGc2VGCw8olP3xVOL"


@function_refund.route("/refund-payments", methods=["POST"])
def refund_payments():
    try:
        data = request.get_json()

        if not isinstance(data, list):
            return jsonify({
                "status": False,
                "message": "Request body should be an array"
            }), 400

        results = []

        for item in data:

            pay_id = item.get("pay_id")
            amount = item.get("amount")
            doctor_phone_id = item.get("doctor_phone_id")
            phone = item.get("phone")
            name = item.get("name")
            appointmentdate = item.get("appointmentdate")
            timeslot = item.get("timeslot")

            doc_id = ObjectId(doctor_phone_id)
            document = doctors.find_one({"_id": doc_id})

            doctor_name = document['name']


            if not pay_id or not amount:
                results.append({
                    "pay_id": pay_id,
                    "status": "failed",
                    "message": "pay_id and amount are required"
                })
                continue

            refund_url = f"https://api.razorpay.com/v1/payments/{pay_id}/refund"

            payload = {
                "amount": int(float(amount) * 100)
            }

            response = requests.post(
                refund_url,
                auth=HTTPBasicAuth(
                    RAZORPAY_KEY_ID,
                    RAZORPAY_KEY_SECRET
                ),
                json=payload
            )

            response_data = response.json()

            if response.status_code in [200, 201]:

                refund_id = response_data.get("id")
                refund_created_at = response_data.get("created_at")
                refund_status = response_data.get("status")

                refund_date = None

                if refund_created_at:
                    refund_date = datetime.fromtimestamp(
                        refund_created_at
                    ).strftime("%d-%m-%Y %H:%M:%S")

                

                appointment.update_one(
                    {"pay_id": pay_id},
                    {
                        "$set": {
                            "refund_amount": str(amount),
                            "refund_id": refund_id,
                            "refund_created_at": str(refund_created_at),
                            "refund_date": refund_date,
                            "refund_status": refund_status
                        }
                    }
                )

                vs = make_voucher(amount,pay_id ,refund_id,doctor_phone_id, phone)
                msg = send_whatsapp_message(phone, name, appointmentdate, timeslot, doctor_name, amount)

                results.append({
                    "pay_id": pay_id,
                    "status": "success",
                    "refund_id": refund_id
                })

            else:

                # print(f"Refund failed for pay_id {pay_id}: {response_data}")

                appointment.update_one(
                    {"pay_id": pay_id},
                    {
                        "$set": {
                            "refund_status": "failed",
                            "refund_error": response_data
                        }
                    }
                )

                results.append({
                    "pay_id": pay_id,
                    "status": "failed",
                    "error": response_data
                })

        return jsonify({
            "status": True,
            "results": results
        })

    except Exception as e:
        return jsonify({
            "status": False,
            "message": str(e)
        }), 500




def make_voucher(amount,payment_id ,refund_id,doctor_phone_id, phone):
    try:
        duplicatepayment = vouchers.find_one({'Payment_id': refund_id})
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
                        "amount":float(amount),
                        "voucher_number": voucher_number,
                        "voucher_type": 'Journal',
                        "voucher_mode": "Journal",
                        "txn": count_txn + 1,
                        "doctor_id": doctor_phone_id,
                        "from_id": refund_id,
                        "to_id": phone,
                        "date": datetime.now(ZoneInfo("Asia/Kolkata")),
                        "Payment_id": refund_id,
                        "narration": f"Refund - {payment_id}",
                        "entries": [

                                
                    {
                    "narration": f"Refund - {payment_id}",
                    "ledger_id": "A2",
                    "ledger_name": "Doctor Fee Payble",
                    "debit": float(amount),
                    "credit": 0
                    }   ,
                    {
                    "narration": f"Refund - {payment_id}",
                    "ledger_id": "A1",
                    "ledger_name": "Razorpay",
                    "debit": 0,
                    "credit": float(amount)
                    } 
                    ],
                        "created_by": "system",
                        "created_at": ist_now
                    }
            vouchers.insert_one(voucher)
        return 200
    except Exception as e:
        print(f"Error in make_voucher: {str(e)}")
        return 500
    
headers={'Authorization': 'Bearer EAAQNrOr6av0BPojE1zKKzKEDJWVmZBBvtBefl8aS24XBz4QcLzXPeF6wTlCBsIPFeOcwHi5AZBuXwkN6IfpI4uDjyLZAYRvMNF9jdVdeJ2WiNlnY1N1NpmFZBrJCSZAZCALx23ZArZA0jWnn0kEic6gY1Li4TFw8pZAnKZAmJtM0o6ZBfQZC8zi3v2EtcsoEnu9FutphkQZDZD','Content-Type': 'application/json'}

def send_whatsapp_message(from_number, name, date, timeslot, doctor_name, amount):
    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"       
    incoming_data =   { 
        "messaging_product": "whatsapp", 
        "to": from_number, 
        "type": "template", 
        "template": { 
            "name": "payment_refund_order", 
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
                    "text": date 
                },
                {
                    "type": "text",
                    "text": timeslot 
                },
                {
                    "type": "text",
                    "text": doctor_name 
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
    return 'ok', 200


@function_refund.route("/refund/<string:doctor_id>", methods=["GET"])
def redirect_refund(doctor_id):
    try:
        return render_template('refund.html', doctor_id=doctor_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 500






@function_refund.route("/refund-payments-request/<string:doctor_phone_id>", methods=["POST"])
def refund_payments_request(doctor_phone_id):
    try:
        data = request.get_json()

        if not isinstance(data, list):
            return jsonify({
                "status": False,
                "message": "Request body should be an array"
            }), 400

        for item in data:

            pay_id = item.get("pay_id")
            appointment.update_one(
                    {"pay_id": pay_id},
                    {
                        "$set": {
                            "refund_status": "processing"
                        }
                    }
                )
            
        doc_id = ObjectId(doctor_phone_id)
        document = doctors.find_one({"_id": doc_id})

        accessToken = document['accessToken']
        phonenumberID = document['phonenumberID']
        phone = document['phone']

        headers={'Authorization': f'Bearer {accessToken}','Content-Type': 'application/json'}
        external_url = f"https://graph.facebook.com/v22.0/{phonenumberID}/messages" 

            
        incoming_data = {
            "messaging_product": "whatsapp",
            "to": "918959690512",
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": f"Do you want to refund selected patient?"
                },
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": "YES_REFUND",
                                "title": "Refund"
                            }
                        },
                        {
                            "type": "reply",
                            "reply": {
                                "id": "NO_REJECT",
                                "title": "Reject"
                            }
                        }
                    ]
                }
            }
        }

        response = requests.post(external_url, json=incoming_data, headers=headers)

        return jsonify({
            "status": True,
        })

    except Exception as e:
        return jsonify({
            "status": False,
        }), 500


