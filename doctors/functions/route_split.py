import requests
from requests.auth import HTTPBasicAuth

# Razorpay Credentials
RAZORPAY_KEY_ID = "rzp_live_R9tGl7bLSIBV6f"
RAZORPAY_KEY_SECRET = "dTvrApHzGc2VGCw8olP3xVOL"

def create_transfers(pay_id,ac,amount):
    try:
        url = f"https://api.razorpay.com/v1/payments/{pay_id}/transfers"

        payload = {
            "transfers": [
                {
                    "account": ac,
                    "amount": amount*100,
                    "currency": "INR",
                    "notes": {
                        "name": "Auto generated transfer",
                        "roll_no": "IEC2011026"
                    },
                    "linked_account_notes": [
                        "roll_no"
                    ],
                    "on_hold": False
                }
            ]
        }

        response = requests.post(
            url,
            json=payload,
            auth=HTTPBasicAuth(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
            headers={
                "Content-Type": "application/json"
            }
        ) 

        res = response.json()
        transfer_id = res["items"][0]["id"]
        
        return transfer_id

    except Exception as e:
        return "x"
