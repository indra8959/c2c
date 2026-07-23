import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from pymongo import MongoClient

app = Flask(__name__)

# ===== CONFIGURATION =====
MONGO_URI = "mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.get_database("caredb")
vouchers = db["vouchers"]

# WhatsApp API Credentials
WHATSAPP_ACCESS_TOKEN = "EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD"
PHONE_NUMBER_ID = "563776386825270"


# ===== HELPER FUNCTION: EXCEL MAKE & SEND VIA WHATSAPP =====
def send_excel_vouchers_on_whatsapp(from_number, transactions, doctor_id):
    filename = f"Doctor_Vouchers_{doctor_id}.xlsx"

    try:
        df = pd.DataFrame(transactions)
        df.to_excel(filename, index=False, engine="openpyxl")

        upload_url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/media"
        headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}
        excel_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        with open(filename, "rb") as file_handle:
            files = {
                "file": (filename, file_handle, excel_mime),
                "type": (None, excel_mime),
                "messaging_product": (None, "whatsapp")
            }
            upload_res = requests.post(upload_url, headers=headers, files=files)

        upload_data = upload_res.json()
        if upload_res.status_code != 200 or "id" not in upload_data:
            return jsonify({"error": "Media upload failed", "details": upload_data}), 400

        media_id = upload_data["id"]

        message_url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"
        msg_headers = {
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": from_number,
            "type": "document",
            "document": {
                "id": media_id,
                "caption": f"Doctor {doctor_id} ke Vouchers ki Excel Report",
                "filename": filename
            }
        }

        msg_res = requests.post(message_url, headers=msg_headers, json=payload)

        if os.path.exists(filename):
            os.remove(filename)

        return jsonify({"status": "success", "response": msg_res.json()}), 200

    except Exception as e:
        if os.path.exists(filename):
            os.remove(filename)
        return jsonify({"error": str(e)}), 500


# ===== MAIN FUNCTION: GET VOUCHERS AND SEND =====
def send_doctor_vouchers_excel(doctor_id, recipient_phone, from_date_str="2025-08-01", to_date_str="x" ,filetype="pdf"):
    if to_date_str=="x":
        to_date_str = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d")
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d")
    except Exception:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    # ----------------------------------------------------
    # STEP 1: Calculate Opening Balance (before `from_date`)
    # ----------------------------------------------------
    prior_query = {
        "doctor_id": doctor_id,
        "date": {"$lt": from_date}
    }
    prior_vouchers = vouchers.find(prior_query)
    
    opening_balance = 0.0
    for doc in prior_vouchers:
        for entry in doc.get("entries", []):
            if entry.get("ledger_id") == "A2":
                debit = float(entry.get("debit", 0) or 0)
                credit = float(entry.get("credit", 0) or 0)
                opening_balance += (credit - debit)

    transactions = []
    running_balance = opening_balance

    # Record 1: Opening Balance Row in Excel
    op_suffix = "Cr" if opening_balance >= 0 else "Dr"
    transactions.append({
        "date": from_date.strftime("%a, %d %b %Y 00:00:00 GMT"),
        "Payment_id": "OPENING BALANCE",
        "debit": 0.0,
        "credit": 0.0,
        "balance": f"{abs(opening_balance):,.2f} {op_suffix}"
    })

    # ----------------------------------------------------
    # STEP 2: Fetch Current Date Range Transactions
    # ----------------------------------------------------
    query = {
        "doctor_id": doctor_id,
        "date": {"$gte": from_date, "$lte": to_date}
    }
    results = vouchers.find(query).sort("date", 1)

    for doc in results:
        for entry in doc.get("entries", []):
            if entry.get("ledger_id") == "A2":
                
                voucher_date = doc.get("date")
                if isinstance(voucher_date, datetime):
                    formatted_date = voucher_date.strftime("%a, %d %b %Y")
                else:
                    formatted_date = str(voucher_date)

                debit = float(entry.get("debit", 0) or 0)
                credit = float(entry.get("credit", 0) or 0)

                # Update Running Balance seamlessly from Opening Balance
                running_balance += (credit - debit)
                balance_suffix = "Cr" if running_balance >= 0 else "Dr"
                formatted_balance = f"{abs(running_balance):,.2f} {balance_suffix}"

                transactions.append({
                    "date": formatted_date,
                    "Payment_id": doc.get("Payment_id", ""),
                    "debit": debit,
                    "credit": credit,
                    "balance": formatted_balance
                })

    # Agar koi transaction na ho fir bhi Opening Balance rahega
    if len(transactions) == 1 and transactions[0]["Payment_id"] == "OPENING BALANCE":
        # Check if user wants report even if only opening balance exists
        pass 

    if filetype=="pdf":
        return send_pdf_vouchers_on_whatsapp(recipient_phone, transactions, doctor_id)
    else:
        return send_excel_vouchers_on_whatsapp(recipient_phone, transactions, doctor_id)

    # return send_excel_vouchers_on_whatsapp(recipient_phone, transactions, doctor_id)
    # return send_pdf_vouchers_on_whatsapp(recipient_phone, transactions, doctor_id)




from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Optional (for better fonts)
try:
    pdfmetrics.registerFont(TTFont("Arial", "arial.ttf"))
    FONT_NAME = "Arial"
except:
    FONT_NAME = "Helvetica"


def create_pdf(filename, transactions, doctor_id):
    doc = SimpleDocTemplate(
        filename,
        pagesize=(11.7 * inch, 8.3 * inch),  # A4 Landscape
    )

    elements = []

    styles = getSampleStyleSheet()

    title = Paragraph(
        f"<b>Doctor Voucher Report</b><br/>Doctor ID : {doctor_id}",
        styles["Heading2"],
    )
    elements.append(title)

    data = [["Date", "Payment ID", "Debit", "Credit", "Balance"]]

    for row in transactions:
        data.append([
            str(row["date"]),
            str(row["Payment_id"]),
            str(row["debit"]),
            str(row["credit"]),
            str(row["balance"]),
        ])

    table = Table(
        data,
        colWidths=[180, 120, 70, 70, 90],
        repeatRows=1,
    )

    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ])
    )

    elements.append(table)

    doc.build(elements)


def send_pdf_vouchers_on_whatsapp(from_number, transactions, doctor_id):

    filename = f"Doctor_Vouchers_{doctor_id}.pdf"

    try:

        create_pdf(filename, transactions, doctor_id)

        upload_url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/media"

        headers = {
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"
        }

        pdf_mime = "application/pdf"

        with open(filename, "rb") as file_handle:

            files = {
                "file": (filename, file_handle, pdf_mime),
                "type": (None, pdf_mime),
                "messaging_product": (None, "whatsapp")
            }

            upload_res = requests.post(upload_url, headers=headers, files=files)

        upload_data = upload_res.json()

        if upload_res.status_code != 200 or "id" not in upload_data:
            return jsonify(upload_data), 400

        media_id = upload_data["id"]

        message_url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/messages"

        msg_headers = {
            "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": from_number,
            "type": "document",
            "document": {
                "id": media_id,
                "filename": filename,
                "caption": "Doctor Voucher Report"
            }
        }

        response = requests.post(
            message_url,
            headers=msg_headers,
            json=payload
        )

        if os.path.exists(filename):
            os.remove(filename)

        return jsonify(response.json()), 200

    except Exception as e:

        if os.path.exists(filename):
            os.remove(filename)

        return jsonify({"error": str(e)}), 500






def report_reply(from_number, btn_id="2026"):
    headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"

    button_payload  = []
    if btn_id=="2025":
        button_payload = [
        {
          "type": "reply",
          "reply": {
            "id": "REPORT_DOWNLOAD_PDF_2025",
            "title": "PDF"
          }
        },
        {
          "type": "reply",
          "reply": {
            "id": "REPORT_DOWNLOAD_EXCEL_2025",
            "title": "Excel"
          }
        }
      ]
    else:
        button_payload = [
        {
          "type": "reply",
          "reply": {
            "id": "REPORT_DOWNLOAD_PDF_2026",
            "title": "PDF"
          }
        },
        {
          "type": "reply",
          "reply": {
            "id": "REPORT_DOWNLOAD_EXCEL_2026",
            "title": "Excel"
          }
        }
      ]


    incoming_data = {
  "messaging_product": "whatsapp",
  "to": from_number,
  "type": "interactive",
  "interactive": {
    "type": "button",
    "body": {
      "text": "📄 Please choose the report format."
    },
    "action": {
      "buttons": button_payload
    }
  }
}
    response = requests.post(external_url, json=incoming_data, headers=headers)
    return "OK", 200

# print(report_reply("918959690512"))


# print(send_doctor_vouchers_excel("67ee5e1bde4cb48c515073ee", "918959690512","2025-04-01","x","pdf"))
