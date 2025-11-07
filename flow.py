from flask import Flask, request, jsonify
import requests
from datetime import datetime

# app = Flask(__name__)

SCREEN_RESPONSES = {
  "APPOINTMENT": {
    "screen": "APPOINTMENT",
    "data": {
      "department": [
        {
          "id": "shopping",
          "title": "Shopping & Groceries"
        },
        {
          "id": "clothing",
          "title": "Clothing & Apparel"
        },
        {
          "id": "home",
          "title": "Home Goods & Decor"
        },
        {
          "id": "electronics",
          "title": "Electronics & Appliances"
        },
        {
          "id": "beauty",
          "title": "Beauty & Personal Care"
        }
      ],
      "location": [
        {
          "id": "1",
          "title": "King’s Cross, London"
        },
        {
          "id": "2",
          "title": "Oxford Street, London"
        },
        {
          "id": "3",
          "title": "Covent Garden, London"
        },
        {
          "id": "4",
          "title": "Piccadilly Circus, London"
        }
      ],
      "is_location_enabled": True,
      "is_date_enabled": True,
      "time": [
        {
          "id": "10:00",
          "title": "10:00"
        },
        {
          "id": "11:21",
          "title": "11:21",
          "enabled": False
        },
        {
          "id": "11:31",
          "title": "11:31"
        },
        {
          "id": "12:11",
          "title": "12:11",
          "enabled": False
        },
        {
          "id": "12:30",
          "title": "12:11"
        }
      ],
      "patient_query":"",
      "guardian_query":"",
      "dob_query":"",
      "is_time_enabled": True,
      "img": "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"
    }
  },
  "DETAILS": {
    "screen": "DETAILS",
    "data": {
      "symptoms": [
        {
          "id": "Cold",
          "title": "cold"
        },
        {
          "id": "Cough",
          "title": "Cough"
        }
      ]
    }
  },
  "SUMMARY": {
    "screen": "SUMMARY",
    "data": {
      "appointment": "Beauty & Personal Care Department at Kings Cross, London\nMon Jan 01 2024 at 11:30.",
      "details": "Name: John Doe\nEmail: john@example.com\nPhone: 123456789\n\nA free skin care consultation, please",
      "department": "beauty",
      "location": "1",
      "date": "2024-01-01",
      "time": "11:30",
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "123456789"
    }
  }
}

def get_data(search):
    response = requests.get(f"https://care2connect.in/fatch_date_and_time/{search}")
    return response.json()
    
def has_numbers(s):
    return not s.replace(" ", "").isalpha()

def get_next_screen(decrypted_body):
    screen = decrypted_body.get("screen")
    data = decrypted_body.get("data", {})
    action = decrypted_body.get("action")
    flow_token = decrypted_body.get("flow_token")

    if action == "ping":
        return {"data": {"status": "active"}}

    if "error" in data:
        print("Received client error:", data)
        return {"data": {"acknowledged": True}}

    if action == "INIT":
        res_date = get_data("date")
        response = SCREEN_RESPONSES["APPOINTMENT"].copy()
        response["data"].update({"date": res_date})
        return response

    if action == "data_exchange":
        if screen == "APPOINTMENT":
            if data.get("trigger") == "Date_selected":
                res_time = get_data(data.get("Date_of_appointment"))
                response = SCREEN_RESPONSES["APPOINTMENT"].copy()
                response["data"].update({"time": res_time, "is_time_enabled": True})
                return response
                

        if screen == "SUMMARY":
            response = SCREEN_RESPONSES["SUCCESS"].copy()
            response["data"] = {"extension_message_response": {"params": {"flow_token": flow_token}}}
            return response

    print("Unhandled request body:", decrypted_body)
    return {"error": "Unhandled request"}, 400

