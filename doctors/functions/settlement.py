from flask import Flask, request, jsonify , Blueprint
import hmac
import hashlib
import json
from datetime import datetime, timedelta
import requests
from zoneinfo import ZoneInfo
from pymongo import MongoClient
WEBHOOK_SECRET = "doctor"



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

function_settlement = Blueprint("function_settlement", __name__)

@function_settlement.route("/quick_razorpay_webhook", methods=["POST"])
def razorpay_webhook():

    try:
        payload = request.data
        received_signature = request.headers.get("X-Razorpay-Signature")

        if not received_signature:
            return jsonify({
                "status": False,
                "message": "Signature header missing"
            }), 400

        # Verify signature
        generated_signature = hmac.new(
            WEBHOOK_SECRET.encode("utf-8"),
            payload,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(generated_signature, received_signature):
            print("❌ Invalid Signature")
            return jsonify({
                "status": False,
                "message": "Invalid signature"
            }), 400

        # print("✅ Signature Verified")

        # Convert payload to dict
        data = json.loads(payload)

        event = data.get("event")
        account_id = data.get("account_id")
        print("Event:", event)

        if event == "settlement.processed":

            settlement = data.get("payload", {}).get("settlement", {}).get("entity", {})

            settlement_id = settlement.get("id")
            amount = float(settlement.get("amount"))/100
            utr = settlement.get("utr")

            doctorId = "x"
            MId  = "x"
            d_name = "x"
            from_number = "918959690512"


            if account_id=="acc_T8X5ARF35jezZq":
                doctorId = "69aa8d862e6ce410bad8f99a"
                MId  = "I1003"
                d_name = "Dr. Indiver Kalra"
                from_number = "919478002737"

            if account_id=="acc_T8X9cm343nNPsA":
                doctorId = "69ab14581e106e13ffbd9729"
                MId  = "P1004"
                d_name = "Dr. Pragati Kalra"
                from_number = "919478002737"


            
            if account_id=="acc_T8XClXhmlYd3EA":
                doctorId = "69ab14c71e106e13ffbd972a"
                MId  = "C1005"
                d_name = "Centre For Little Minds"
                from_number = "919478002737"



            if account_id=="acc_T8BUURNqf32EnL":
                doctorId = "67ee5e1bde4cb48c515073ee"
                MId  = "N1001"
                d_name = "Dr. Neeraj Bansal"
                from_number = "918128265003"


            nameshan = "Settlement - "+MId
            k = v1_m_doctor_payment(doctorId,amount,settlement_id,nameshan, utr, d_name, MId, from_number)

        return jsonify({
            "status": True,
            "message": "Webhook received"
        }), 200

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({
            "status": False,
            "message": str(e)
        }), 500


@function_settlement.route("/")
def home():
    return "Webhook Running"


def v1_m_doctor_payment(doctorId,fee,payment_id,nareshan, transactionId, d_name, MId, from_number):
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
                            "doctor_id": doctorId,
                            "from_id": "Razorpay",
                            "to_id": MId,
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
                        "ledger_id": "A1",
                        "ledger_name": "Razorpay",
                        "debit": 0,
                        "credit": float(fee)
                        }
                        ],
                            "created_by": "system",
                            "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                        }
        vouchers.insert_one(voucher)
        k = paymentrequest_msg(from_number,MId,str(fee),d_name,payment_id,transactionId)
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def paymentrequest_msg(from_number,MID,amount,name,settlement_id,utr):
    headers={'Authorization': 'Bearer EAAQNrOr6av0BPojE1zKKzKEDJWVmZBBvtBefl8aS24XBz4QcLzXPeF6wTlCBsIPFeOcwHi5AZBuXwkN6IfpI4uDjyLZAYRvMNF9jdVdeJ2WiNlnY1N1NpmFZBrJCSZAZCALx23ZArZA0jWnn0kEic6gY1Li4TFw8pZAnKZAmJtM0o6ZBfQZC8zi3v2EtcsoEnu9FutphkQZDZD','Content-Type': 'application/json'}
    external_url = "https://graph.facebook.com/v22.0/794530863749639/messages"  # Example API URL
    incoming_data = { 
  "messaging_product": "whatsapp", 
  "to": from_number, 
  "type": "template", 
  "template": { 
    "name": "dr_payment_settlement", 
    "language": { "code": "en" },
    "components": [
      {
        "type": "body",
        "parameters": [
          {
            "type": "text",
            "text": name +" ["+MID+"]"
          },
          {
            "type": "text",
            "text": settlement_id
          },
          {
            "type": "text",
            "text": amount
          },
          {
            "type": "text",
            "text": utr
          }
        ]
      }
    ]
  } 
}
    response = requests.post(external_url, json=incoming_data, headers=headers)
    # print(jsonify(response.json()))
    return "OK", 200

