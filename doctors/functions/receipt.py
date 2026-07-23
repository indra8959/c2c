from fpdf import FPDF
from pymongo import MongoClient
from bson.objectid import ObjectId
import requests

from datetime import datetime

MONGO_URI = "mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.get_database("caredb")
doctors = db["doctors"] 
appointment = db["appointment"] 
templog = db["logs"] 


def receiptselection(from_number,a_id):

    # document = templog.find_one({'_id':from_number})
    appoint_data = appointment.find_one({"_id": ObjectId(a_id)})

#     R_number = appointment.count_documents({"doctor_phone_id":'67ee5e1bde4cb48c515073ee',"amount":{"$gt": -1}})

    R_number = appointment.count_documents({
        "doctor_phone_id": "67ee5e1bde4cb48c515073ee",
        "amount": {"$gt": -1},
        "_id": {"$lte": ObjectId(a_id)}
        })

    name = appoint_data.get('patient_name')
    doa = appoint_data.get('date_of_appointment')
    date_str = doa
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    dformatted_date = str(date_obj.strftime("%d-%m-%Y"))

    time = appoint_data.get('time_slot')
    
    pay_id = str(appoint_data.get('pay_id'))
    
    amount = 0
    pfee = 0

    if float(appoint_data.get('amount', 0)) > 0:
        amount = "200"
        pfee = "20"



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
            self.cell(0, 10, "Duniyape Technologies Private Limited", ln=True, fill=True , align='C')

            self.set_font("Arial", "", 12)
            self.cell(0, 10, "Shop No-28, ModelTown, Phase-3, Bathinda-151001, Punjab, India", ln=True, fill=True, align='C')
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
            self.cell(50, 10, "Clinic / Hospital Name:", 1)
            self.set_font("Arial", "", 12)
            self.cell(0, 10, "Dr. Neeraj Bansal Child Care Centre", 1, ln=True)

            self.set_font("Arial", "B", 10)
            self.cell(50, 10, "Clinic / Hospital Address:", 1)
            self.set_font("Arial", "", 10)
            self.cell(0, 10, "Kalra Multispeciality Hospital, Opposite Street no 4, Ajit Road, Bathinda-151001, Punjab", 1, ln=True)

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




        #     self.set_font("Arial", "B", 12)
        #     self.cell(50, 10, "Consultation fee:", 1)
        #     self.set_font("Arial", "", 12)
        #     self.cell(0, 10,amount+"/-", 1, ln=True)

            self.set_font("Arial", "B", 12)
            self.cell(50, 10, "Doctor fee:", 1)
            self.set_font("Arial", "", 12)
            self.cell(0, 10,amount+"/-", 1, ln=True)

            self.set_font("Arial", "B", 10)
            self.cell(50, 10, "Platfarm Fee (Inclusive GST)", 1)
            self.set_font("Arial", "", 12)
            self.cell(0, 10,pfee+"/-", 1, ln=True)

            # self.set_font("Arial", "B", 12)
            # self.cell(50, 10, "Total GST:", 1)
            # self.set_font("Arial", "", 12)
            # self.cell(0, 10,"3.05"+"/-", 1, ln=True)



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
        WHATSAPP_ACCESS_TOKEN = "EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD"
        PDF_FILE_PATH = 'receipt.pdf'

        PHONE_NUMBER_ID = "563776386825270"


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
    "to": from_number,
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


def download_receipt_selection(from_number):

    result = list(
        appointment.find(
            {
                "whatsapp_number": from_number,
                "amount": {"$gt": -1},
                "doctor_phone_id": "67ee5e1bde4cb48c515073ee"
            }
        ).sort("appointment_index", -1).limit(10)     # Latest first (optional)
    )

    final_rows = []

    for item in result:
        final_rows.append({
            "id": "rcp_"+str(item["_id"]),   # या appointment_index भी रख सकते हैं
            "title": item.get("patient_name", "Unknown"),
            "description": f"Date: {item.get('date_of_appointment')} | Appointment No: {item.get('appointment_index')}"
        })

    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"
    headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}

    incoming_data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": from_number,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {
                "text": "Select the patient to download the receipt."
            },
            "action": {
                "button": "Choose Patient",
                "sections": [
                    {
                        "title": "Patients",
                        "rows": final_rows
                    }
                ]
            }
        }
    }

    response = requests.post(
        external_url,
        json=incoming_data,
        headers=headers
    )
    print(response.json())

    return "OK", 200
