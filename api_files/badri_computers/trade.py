# staff_routes.py
from flask import Blueprint, request, jsonify
from bson import ObjectId
from werkzeug.exceptions import BadRequest
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from config import MONGO_URI
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash

client = MongoClient(MONGO_URI)
db = client["badri_enterprises"] # If URI has a DB, it picks it


trade_bp = Blueprint("trade", __name__)

# ✅ Create / Edit Designation (single API)
@trade_bp.route("/products", methods=["POST"])
def create_or_edit_products():
    data = request.json
    designation_id = data.get("_id")
    designation_name = data.get("productName")

    if not designation_name:
        return jsonify({"error": "designation_name is required"}), 400

    if designation_id: 
        data.pop("_id", None)
        # 🔹 Edit existing designation
        result = db.products.update_one(
            {"_id": ObjectId(designation_id)},
            {"$set": data}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Designation not found"}), 404
        return jsonify({"message": "Designation updated successfully", "_id": designation_id}), 200

    else:  
        # 🔹 Create new designation
        result = db.products.insert_one(data)
        return jsonify({"message": "Designation created successfully"}), 201


# ✅ Get All Designations
@trade_bp.route("/products", methods=["GET"])
def get_products():
    designations = list(db.products.find({}))
    for d in designations:
        d["_id"] = str(d["_id"])
    return jsonify(designations), 200

@trade_bp.route("/categories/<action>", methods=["POST"])
def handle_categories(action):
    data = request.get_json() or {}

    # 🔹 GET ALL
    if action == "get":
        categories = list(db.categories.find({}))
        for c in categories:
            c["_id"] = str(c["_id"])
        return jsonify(categories), 200


    # 🔹 ADD CATEGORY
    elif action == "add":
        if "name" not in data:
            return jsonify({"error": "Category name is required"}), 400

        # Prevent duplicate
        existing = db.categories.find_one({"name": data["name"]})
        if existing:
            return jsonify({"error": "Category already exists"}), 400

        category = {
            "name": data["name"],
            "created_at": datetime.utcnow()
        }

        result = db.categories.insert_one(category)
        category["_id"] = str(result.inserted_id)

        return jsonify({
            "message": "Category added successfully",
            "category": category
        }), 201


    # 🔹 DELETE CATEGORY
    elif action == "delete":
        if "id" not in data:
            return jsonify({"error": "Category id is required"}), 400

        try:
            result = db.categories.delete_one({
                "_id": ObjectId(data["id"])
            })

            if result.deleted_count == 0:
                return jsonify({"error": "Category not found"}), 404

            return jsonify({"message": "Category deleted successfully"}), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 400


    else:
        return jsonify({"error": "Invalid action"}), 400

@trade_bp.route("/billing", methods=["POST"])
def create_billing():
    """
    Create a new billing document.
    """
    try:
        data = request.get_json(force=True)

        if not data:
            raise BadRequest("Request JSON is missing")
        
        count_bills = db.bills.count_documents({})


        date = data.get("date")

        if isinstance(date, str):
            if "T" in date:
                date_obj = datetime.fromisoformat(date.replace("Z", "+00:00"))
                date_obj = date_obj.astimezone(ZoneInfo("Asia/Kolkata"))
            else:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
        else:
            date_obj = datetime.now(ZoneInfo("Asia/Kolkata"))
        
        date_str = date_obj.strftime("%Y-%m-%d")
        
        # final bill number
        bill_number = f"{date_str}-{count_bills + 1}"

        count_bills = bill_number
        # count_bills = "D"+str(int(count_bills+1001))
        

        # Insert new billing
        data["id"] = count_bills
        result = db.bills.insert_one(data)
        


        paymentled = 'Cash in Hand'
        paymentcode = 'A11'
        voucher_type = 'Receipt'
        voucher_mode = 'Journal'
        bankref = count_bills

        if data.get('paymentMethod')=='cash':
            paymentled = 'Cash in Hand'
            paymentcode = 'A11'
            voucher_type = 'Receipt'

            voucher_mode = 'Cash'


        elif data.get('paymentMethod')=='bank' or data.get('paymentMethod')=='cheque':
            paymentled = 'IDBI Bank'
            paymentcode = 'A4'
            voucher_type = 'Receipt'
            bankref = data.get('bankref')
            voucher_mode = 'Bank'

        elif data.get('paymentMethod')=='Director':
            paymentled = "Sundry Debtors"
            paymentcode = "A20"
            voucher_type = 'Journal'
            voucher_mode = 'Journal'
            if data.get('director')=='Harish Kumar Bhardwaj':
                dvendor = 'Harish Kumar Bhardwaj'
                dvendorid = '693949c8d0d7415a7087cf1d'
            else:
                dvendor = 'Indrajeet Ajit'
                dvendorid = '69394a96d0d7415a7087cf1f'
        else:
            paymentled = "Sundry Debtors"
            paymentcode = "A20"
            voucher_type = 'Journal'
            voucher_mode = 'Journal'



        if isinstance(date, str):
            if "T" in date:
                # ISO format (from frontend toISOString)
                voucher_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
                voucher_date = voucher_date.astimezone(ZoneInfo("Asia/Kolkata"))
            else:
                # YYYY-MM-DD
                voucher_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))

        try:
                # voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))
                date_str = voucher_date.strftime("%Y-%m-%d")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                start = datetime(date_obj.year, date_obj.month, date_obj.day)
                end = start + timedelta(days=1)


                # voucher_date = voucher_date
                # date_str = voucher_date.strftime("%Y-%m-%d")
                # date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                # start = datetime(date_obj.year, date_obj.month, date_obj.day)
                # end = start + timedelta(days=1)

                


                count_txn = db.vouchers.count_documents({})
                count = 0
                voucher_number = 1

                if data.get('paymentMethod')=='cash':
                    count = db.vouchers.count_documents({
                    "voucher_type": "Receipt",
                    "voucher_mode": "Cash",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })
                    voucher_number = "CRV-"+ str(date_str) +'-'+ str(count + 1)
                elif data.get('paymentMethod')=='bank' or data.get('paymentMethod')=='cheque':
                    count = db.vouchers.count_documents({
                    "voucher_type": "Receipt",
                    "voucher_mode": "Bank",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })
                    voucher_number = "BRV-"+ str(date_str) +'-'+ str(count + 1)
                else:
                    count = db.vouchers.count_documents({
                    "voucher_type": "Journal",
                    "voucher_mode": "Journal",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })
                    voucher_number = "JRV-"+ str(date_str) +'-'+ str(count + 1)

                


                # count_txn = db.vouchers.count_documents({})
                # count = db.vouchers.count_documents({
                #     "voucher_type": "Journal",
                #     "voucher_mode": "Journal",
                #     "date": {"$gte": start, "$lt": end}   # between start and end of day
                # })

                # voucher_number = "JRV-"+ str(date_str) +'-'+ str(count + 1)
                voucher = {

                    "voucher_number": voucher_number,
                    "voucher_type": voucher_type,
                    "voucher_mode": voucher_mode,
                    "txn": count_txn + 1,
                    "from_id": "admin",
                    "to_id": count_bills,
                    "date": start,
                    "Payment_id": bankref,
                    "narration": bankref,
                    "amount":float(data['totalAmount']),
                    "entries": [
                        {
                "narration": bankref,
                "ledger_id": "A24",
                "ledger_name": "IGST Payable",
                "debit": 0,
                "credit": float(data['cgstAmount']+data['sgstAmount']),
                "employee_id" : data['custid'],
                "employee_name":data['clientName']
                },
                
                {
                "narration": bankref,
                "ledger_id": "A12",
                "ledger_name": "Sales Account",
                "debit": 0,
                "credit": float(data['subtotalAmount']),
                "employee_id" : data['custid'],
                "employee_name":data['clientName']
                },
                {
                "narration": bankref,
                "ledger_id": paymentcode,
                "ledger_name": paymentled,
                "debit": float(data['totalAmount']),
                "credit": 0,
                "employee_id" : data['custid'],
                "employee_name":data['clientName']
                }
                
                ],
                    "created_by": "system",
                    "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }
                voucher2 = {

                    "voucher_number": voucher_number,
                    "voucher_type": voucher_type,
                    "voucher_mode": voucher_mode,
                    "txn": count_txn + 1,
                    "from_id": "admin",
                    "to_id": count_bills,
                    "date": start,
                    "Payment_id": bankref,
                    "narration": bankref,
                    "amount":float(data['totalAmount']),
                    "entries": [
                        {
                "narration": bankref,
                "ledger_id": "A22",
                "ledger_name": "CGST Payable",
                "debit": 0,
                "credit": float(data['cgstAmount']),
                "employee_id" : data['custid'],
                "employee_name":data['clientName']
                },
                {
                "narration": bankref,
                "ledger_id": "A23",
                "ledger_name": "SGST Payable",
                "debit": 0,
                "credit": float(data['cgstAmount']),
                "employee_id" : data['custid'],
                "employee_name":data['clientName']
                },
                
                {
                "narration": bankref,
                "ledger_id": "A12",
                "ledger_name": "Sales Account",
                "debit": 0,
                "credit": float(data['subtotalAmount']),
                "employee_id" : data['custid'],
                "employee_name":data['clientName']
                },
                {
                "narration": bankref,
                "ledger_id": paymentcode,
                "ledger_name": paymentled,
                "debit": float(data['totalAmount']),
                "credit": 0,
                "employee_id" : data['custid'],
                "employee_name":data['clientName']
                }
                
                ],
                    "created_by": "system",
                    "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }
                if data.get('clientAddress', {}).get('state', '').lower() == 'punjab':
                    db.vouchers.insert_one(voucher2)
                else:
                    db.vouchers.insert_one(voucher)

        except:
                print(2)


        if data['adjustmentVoucher']=='yes':
            try:
                # voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))
                date_str = voucher_date.strftime("%Y-%m-%d")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                start = datetime(date_obj.year, date_obj.month, date_obj.day)
                end = start + timedelta(days=1)

                


                count_txn = db.vouchers.count_documents({})
                count = db.vouchers.count_documents({
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
                    "from_id": "admin",
                    "to_id": data['custid'],
                    "date": start,
                    "Payment_id": "Journal",
                    "narration": 'Adjustment',
                    "amount":float(data['advance']),
                    "entries": [
                        {
                "narration": "Adjustment",
                "ledger_id": "A19",
                "ledger_name": "Sundry Creditors",
                "debit": float(data['advance']),
                "credit": 0,
                "employee_id" : data['custid'],
                "employee_name":data['clientName']
                },
                {
                "narration": "Adjustment",
                "ledger_id": "A20",
                "ledger_name": "Sundry Debtors",
                "debit": 0,
                "credit": float(data['advance']),
                "employee_id" : data['custid'],
                "employee_name":data['clientName']
                }
                
                ],
                    "created_by": "system",
                    "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }
                db.vouchers.insert_one(voucher)
                
            except:
                print(2)


        return jsonify({
            "message": "Billing created successfully",
            "inserted_id": str(result.inserted_id)
        }), 201

    except BadRequest as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": "Server error", "details": str(e)}), 500


# -----------------------
# GET BILLING LIST
# -----------------------
@trade_bp.route("/billing", methods=["GET"])
def get_billing():
    """
    Return billing list sorted by latest created.
    """
    try:
        bills = list(db.bills.find({}).sort("_id", -1))

        for bill in bills:
            bill["_id"] = str(bill["_id"])

        return jsonify(bills), 200

    except Exception as e:
        return jsonify({"error": "Server error", "details": str(e)}), 500





@trade_bp.route("/customer", methods=["POST"])
def create_or_edit_customer():
    data = request.json
    designation_id = data.get("_id")

    if designation_id: 
        data.pop("_id", None)
        # 🔹 Edit existing designation
        result = db.customers.update_one(
            {"_id": ObjectId(designation_id)},
            {"$set": data}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Designation not found"}), 404
        return jsonify({"message": "Designation updated successfully", "_id": designation_id}), 200

    else:  
        # 🔹 Create new designation
        result = db.customers.insert_one(data)
        return jsonify({"message": "Designation created successfully"}), 201


# -----------------------
# GET ALL CUSTOMERS
# -----------------------
@trade_bp.route("/customer", methods=["GET"])
def get_customers():
    """
    Return full customer list sorted by newest first.
    """
    try:
        customers = list(db.customers.find({}).sort("_id", -1))

        for c in customers:
            c["_id"] = str(c["_id"])

        return jsonify(customers), 200

    except Exception as e:
        return jsonify({"error": "Server error", "details": str(e)}), 500

def convert_objectid(data):
    if isinstance(data, dict):
        return {key: convert_objectid(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_objectid(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    else:
        return data

@trade_bp.route("/search-data", methods=["GET"])
def get_merged_data():
    """
    Return customers + staff in a single merged array.
    """

    try:
        merged = []

        # --- Get Customers ---
        customers = list(db.customers.find({}))
        customers = convert_objectid(customers)
        for c in customers:
            c["usertype"] = "customers"
            
        merged.extend(customers)

        vendors = list(db.vendors.find({}))
        vendors = convert_objectid(vendors)
        for c in vendors:
            c["usertype"] = "vendors"
            
        merged.extend(vendors)


        # --- Get Staff ---
        staff = list(db.staff.find({}))
        staff = convert_objectid(staff)
        for c in staff:
            c["usertype"] = "staff"
            
        merged.extend(staff)

        return jsonify(merged), 200

    except Exception as e:
        return jsonify({
            "error": "Server error",
            "details": str(e)
        }), 500

@trade_bp.route("/assign-data/<id>", methods=["POST"])
def assign_update_data(id):
    try:
        data = request.json
        record_type = data.get("usertype")

        if not record_type:
            return jsonify({"error": "type is required (customer/staff)"}), 400

        # remove type from update fields
        update_fields = {k: v for k, v in data.items() if k != "usertype"}

        if not update_fields:
            return jsonify({"error": "No fields to update"}), 400

        # choose collection
        if record_type == "customers":
            collection = db.customers
        elif record_type == "staff":
            collection = db.staff
        elif record_type == "vendors":
            collection = db.vendors
        else:
            return jsonify({"error": "Invalid type"}), 400

        # update
        result = collection.update_one(
            {"_id": ObjectId(id)},
            {"$set": update_fields}
        )

        if result.matched_count == 0:
            return jsonify({"error": "Record not found"}), 404

        return jsonify({
            "message": f"{record_type} updated successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "error": "Server error",
            "details": str(e)
        }), 500


@trade_bp.route("/vendors", methods=["POST"])
def create_or_edit_vendors():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data provided"}), 400

        vendor_id = data.get("_id")

        # 🔹 UPDATE VENDOR
        if vendor_id:
            obj_id = ObjectId(vendor_id)
            data.pop("_id", None)
            result = db.vendors.update_one(
                {"_id": obj_id},
                {"$set": data}
            )

            if result.matched_count == 0:
                return jsonify({"error": "Vendor not found"}), 404

            return jsonify({
                "message": "Vendor updated successfully",
                "_id": vendor_id
            }), 200

        # 🔹 CREATE NEW VENDOR
        result = db.vendors.insert_one(data)

        return jsonify({
            "message": "Vendor created successfully",
            "_id": str(result.inserted_id)
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@trade_bp.route("/vendors", methods=["GET"])
def get_vendors():
    """
    Return full customer list sorted by newest first.
    """
    try:
        vendors = list(db.vendors.find({}).sort("_id", -1))

        for c in vendors:
            c["_id"] = str(c["_id"])

        return jsonify(vendors), 200

    except Exception as e:
        return jsonify({"error": "Server error", "details": str(e)}), 500



@trade_bp.route('/api/calculate-expense', methods=['POST'])
def calculate_expense():
    data = request.get_json()

    # print(data)
    items = data.get('items', [])

    vendor = data['vendor']['name']
    vendorid = data['vendor']['_id']

    dvendor = data['vendor']['name']
    dvendorid = data['vendor']['_id']

    total_gst = 0
    total_base = 0
    final_amount = 0

    utc_time_str = data['date']

# Parse as UTC
    utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.%fZ")
    utc_time = utc_time.replace(tzinfo=ZoneInfo("UTC"))

    # Convert to IST
    ist_time = utc_time.astimezone(ZoneInfo("Asia/Kolkata"))
    

    for item in items:
        total_gst += float(item.get('gstAmount', 0))
        total_base += float(item.get('basePrice', 0))
        final_amount += float(item.get('total', 0))

    data['total_gst'] = total_gst
    data['total_base'] = total_base
    data['final_amount'] = final_amount

    print({
        "totalBaseAmount": round(total_base, 2),
        "totalGST": total_gst,
        "finalAmount": round(final_amount, 2)
    })

    paymentled = 'IDBI Bank'
    paymentcode = 'A4'

    voucher_type = 'Journal'

    voucher_mode = data.get('paymentMode')

    nareshan = data.get('invoiceId')

    bankref = data.get('invoiceId')

    date = data.get("date")


    if isinstance(date, str):
        if "T" in date:
                # ISO format (from frontend toISOString)
            voucher_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
            voucher_date = voucher_date.astimezone(ZoneInfo("Asia/Kolkata"))
        else:
                # YYYY-MM-DD
            voucher_date = datetime.strptime(date, "%Y-%m-%d")
    else:
        voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))




    if data.get('paymentMode')=='Cash':
        paymentled = 'Cash in Hand'
        paymentcode = 'A11'
        voucher_type = 'Payment'
    elif data.get('paymentMode')=='Bank':
        paymentled = 'IDBI Bank'
        paymentcode = 'A4'
        voucher_type = 'Payment'
        bankref = data.get('bankref')
    elif data.get('paymentMode')=='Director':
        paymentled = 'Loan From Directors'
        paymentcode = 'A25'
        voucher_type = 'Journal'
        voucher_mode = 'Journal'
        if data.get('director')=='Harish Kumar Bhardwaj':
            dvendor = 'Harish Kumar Bhardwaj'
            dvendorid = '693949c8d0d7415a7087cf1d'
        else:
            dvendor = 'Indrajeet Ajit'
            dvendorid = '69394a96d0d7415a7087cf1f'
    else:
        paymentled = data.get('CreditLedgerName')
        paymentcode = data.get('CreditLedger')
        voucher_type = 'Journal'
        voucher_mode = 'Journal'


    try:
                
            if data.get('invType')=='GST':


                voucher_date = voucher_date
                date_str = voucher_date.strftime("%Y-%m-%d")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                start = datetime(date_obj.year, date_obj.month, date_obj.day)
                end = start + timedelta(days=1)

                


                count_txn = db.vouchers.count_documents({})
                count = 0
                voucher_number = 1

                if data.get('paymentMode')=='Cash':
                    count = db.vouchers.count_documents({
                    "voucher_type": "Payment",
                    "voucher_mode": "Cash",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })
                    voucher_number = "CPV-"+ str(date_str) +'-'+ str(count + 1)
                elif data.get('paymentMode')=='Bank':
                    count = db.vouchers.count_documents({
                    "voucher_type": "Payment",
                    "voucher_mode": "Bank",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })
                    voucher_number = "BPV-"+ str(date_str) +'-'+ str(count + 1)
                else:
                    count = db.vouchers.count_documents({
                    "voucher_type": "Journal",
                    "voucher_mode": "Journal",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })
                    voucher_number = "JRV-"+ str(date_str) +'-'+ str(count + 1)

                voucher = {}
                if data.get('POS')=='Punjab':

                    voucher = {
                    "voucher_number": voucher_number,
                    "voucher_type": voucher_type,
                    "voucher_mode": voucher_mode,
                    "txn": count_txn + 1,
                    "from_id": "admin",
                    "to_id": 'xxx',
                    "date": start,
                    "Payment_id": bankref,
                    "narration": nareshan,
                    "amount":float(round(final_amount, 2)),
                    "data": data,
                    "entries": [
                        {
                "narration": nareshan,
                "ledger_id": "A8",
                "ledger_name": "CGST ITC",
                "debit": float(total_gst)/2,
                "credit": 0,
                "employee_id" : vendorid,
                "employee_name":vendor
                },
                        {
                "narration": nareshan,
                "ledger_id": "A26",
                "ledger_name": "SGST ITC",
                "debit": float(total_gst)/2,
                "credit": 0,
                "employee_id" : vendorid,
                "employee_name":vendor
                },
                {
                "narration":nareshan,
                "ledger_id": data.get('ledgerAccount'),
                "ledger_name": data.get('ledgerName'),
                "debit": float(total_base),
                "credit": 0,
               "employee_id" : vendorid,
                "employee_name":vendor
                },
                {
                "narration": nareshan,
                "ledger_id": paymentcode,
                "ledger_name": paymentled,
                "debit": 0,
                "credit": float(round(final_amount, 2)),
               "employee_id" : dvendorid,
                "employee_name":dvendor
                }
                
                ],
                    "created_by": "system",
                    "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }
                else:
                    voucher = {
                    "voucher_number": voucher_number,
                    "voucher_type": voucher_type,
                    "voucher_mode": voucher_mode,
                    "txn": count_txn + 1,
                    "from_id": "admin",
                    "to_id": 'xxx',
                    "date": start,
                    "Payment_id": bankref,
                    "narration": nareshan,
                    "amount":float(round(final_amount, 2)),
                    "data": data,
                    "entries": [
                        {
                "narration": nareshan,
                "ledger_id": "A27",
                "ledger_name": "IGST ITC",
                "debit": float(total_gst),
                "credit": 0,
                "employee_id" : vendorid,
                "employee_name":vendor
                },
              
                {
                "narration":nareshan,
                "ledger_id": data.get('ledgerAccount'),
                "ledger_name": data.get('ledgerName'),
                "debit": float(total_base),
                "credit": 0,
               "employee_id" : vendorid,
                "employee_name":vendor
                },
                {
                "narration": nareshan,
                "ledger_id": paymentcode,
                "ledger_name": paymentled,
                "debit": 0,
                "credit": float(round(final_amount, 2)),
               "employee_id" : dvendorid,
                "employee_name":dvendor
                }
                
                ],
                    "created_by": "system",
                    "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }
                db.vouchers.insert_one(voucher)

            else:

                voucher_date = voucher_date
                date_str = voucher_date.strftime("%Y-%m-%d")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                start = datetime(date_obj.year, date_obj.month, date_obj.day)
                end = start + timedelta(days=1)

                


                count_txn = db.vouchers.count_documents({})
                count = 0
                voucher_number = 1

                if data.get('paymentMode')=='Cash':
                    count = db.vouchers.count_documents({
                    "voucher_type": "Payment",
                    "voucher_mode": "Cash",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })
                    voucher_number = "CPV-"+ str(date_str) +'-'+ str(count + 1)
                elif data.get('paymentMode')=='Bank':
                    count = db.vouchers.count_documents({
                    "voucher_type": "Payment",
                    "voucher_mode": "Bank",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })
                    voucher_number = "BPV-"+ str(date_str) +'-'+ str(count + 1)
                else:
                    count = db.vouchers.count_documents({
                    "voucher_type": "Journal",
                    "voucher_mode": "Journal",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })
                    voucher_number = "JRV-"+ str(date_str) +'-'+ str(count + 1)

                voucher = {
                    "voucher_number": voucher_number,
                    "voucher_type": voucher_type,
                    "voucher_mode": voucher_mode,
                    "txn": count_txn + 1,
                    "from_id": "admin",
                    "to_id": 'xxx',
                    "date": start,
                    "Payment_id": bankref,
                    "narration": nareshan,
                    "amount":float(round(total_base, 2)),
                    "data": data,
                    "entries": [
                        
                {
                "narration":nareshan,
                "ledger_id": data.get('ledgerAccount'),
                "ledger_name": data.get('ledgerName'),
                "debit": float(round(total_base, 2)),
                "credit": 0,
               "employee_id" : vendorid,
                "employee_name":vendor
                },
                {
                "narration": nareshan,
                "ledger_id": paymentcode,
                "ledger_name": paymentled,
                "debit": 0,
                "credit": float(round(total_base, 2)),
               "employee_id" : dvendorid,
                "employee_name":dvendor
                }
                
                ],
                    "created_by": "system",
                    "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }
                db.vouchers.insert_one(voucher)


                # Autometic voucher

                voucher_date = voucher_date
                date_str = voucher_date.strftime("%Y-%m-%d")
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                start = datetime(date_obj.year, date_obj.month, date_obj.day)
                end = start + timedelta(days=1)

                


                count_txn = db.vouchers.count_documents({})
                count = 0
                voucher_number = 1

                count = db.vouchers.count_documents({
                    "voucher_type": "Journal",
                    "voucher_mode": "Journal",
                    "date": {"$gte": start, "$lt": end}   # between start and end of day
                })
                voucher_number = "JRV-"+ str(date_str) +'-'+ str(count + 1)

                voucher={}

                if data.get('POS')=='Punjab':

                    voucher = {
                    "voucher_number": voucher_number,
                    "voucher_type": "Journal",
                    "voucher_mode": "Journal",
                    "txn": count_txn + 1,
                    "from_id": "admin",
                    "to_id": 'xxx',
                    "date": start,
                    "Payment_id": nareshan,
                    "narration": nareshan,
                    "amount":float(round(total_gst, 3)),
                    # "data": data,
                    "entries": [
                        {
                "narration": nareshan,
                "ledger_id": "A31",
                "ledger_name": "RCM CGST Payable",
                "debit": 0,
                "credit": float(total_gst)/2,
                "employee_id" : vendorid,
                "employee_name":vendor
                },
                        {
                "narration": nareshan,
                "ledger_id": "A30",
                "ledger_name": "RCM SGST Payable",
                "debit": 0,
                "credit": float(total_gst)/2,
                "employee_id" : vendorid,
                "employee_name":vendor
                },
                {
                "narration": nareshan,
                "ledger_id": "A14",
                "ledger_name": "RCM CGST ITC",
                "debit": float(total_gst)/2,
                "credit": 0,
                "employee_id" : vendorid,
                "employee_name":vendor
                },
                        {
                "narration": nareshan,
                "ledger_id": "A28",
                "ledger_name": "RCM SGST ITC",
                "debit": float(total_gst)/2,
                "credit": 0,
                "employee_id" : vendorid,
                "employee_name":vendor
                },
                
                ],
                    "created_by": "system",
                    "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }
                else:
                    voucher = {
                    "voucher_number": voucher_number,
                    "voucher_type": "Journal",
                    "voucher_mode": "Journal",
                    "txn": count_txn + 1,
                    "from_id": "admin",
                    "to_id": 'xxx',
                    "date": start,
                    "Payment_id": nareshan,
                    "narration": nareshan,
                    "amount":float(round(total_gst, 3)),
                    # "data": data,
                    "entries": [
                      
                        {
                "narration": nareshan,
                "ledger_id": "A32",
                "ledger_name": "RCM IGST Payable",
                "debit": 0,
                "credit": float(total_gst),
                "employee_id" : vendorid,
                "employee_name":vendor
                },
               
                        {
                "narration": nareshan,
                "ledger_id": "A29",
                "ledger_name": "RCM IGST ITC",
                "debit": float(total_gst),
                "credit": 0,
                "employee_id" : vendorid,
                "employee_name":vendor
                },
                
                ],
                    "created_by": "system",
                    "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }

                db.vouchers.insert_one(voucher)
                
    except:
                print(2)

    return jsonify({
        "totalBaseAmount": round(total_base, 2),
        "totalGST": round(total_gst, 2),
        "finalAmount": round(final_amount, 2)
    })

@trade_bp.route('/api/get-vouchers', methods=['GET'])
def get_vouchers_expence():
    try:
        vouchers = list(
            db.vouchers.find(
                {"data": {"$exists": True}},   # filter
                {"_id": 0, "data": 1}          # projection (only data)
            ).sort("date", -1)
        )

        if len(vouchers) == 0:
            return jsonify({
                "status": "success",
                "message": "No vouchers found",
                "data": []
            }), 200

        return jsonify({
            "status": "success",
            "count": len(vouchers),
            "data": vouchers
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500




@trade_bp.route("/get_all_items", methods=["GET"])
def get_all_items():
    try:
        final_items = []

        # =========================
        # 🔹 PURCHASE (VOUCHERS)
        # =========================
        vouchers = list(
            db.vouchers.find(
                {"data": {"$exists": True}},
                {
                    "_id": 0,
                    "voucher_number": 1,
                    "date": 1,
                    "data": 1
                }
            ).sort("date", -1)
        )

        for v in vouchers:
            items = v.get("data", {}).get("items", [])

            # 🔹 Date
            raw_date = v.get("date") or v.get("data", {}).get("date")
            if raw_date:
                if isinstance(raw_date, str):
                    date = raw_date[:10]
                else:
                    date = raw_date.strftime("%Y-%m-%d")
            else:
                date = None

            # 🔹 Vendor
            vendor = v.get("data", {}).get("vendor", {})
            vendor_name = vendor.get("name")
            vendor_id = str(vendor.get("_id")) if vendor.get("_id") else None

            voucher_number = v.get("voucher_number")

            for item in items:
                final_items.append({
                    "type": "purchase",
                    "date": date,
                    "voucher_number": voucher_number,
                    "party_name": vendor_name,
                    "party_id": vendor_id,

                    "productName": item.get("productName"),
                    "category": item.get("category"),
                    "hsnCode": item.get("hsnCode"),

                    "quantity": item.get("quantity"),
                    "price": item.get("price"),
                    "total": item.get("total"),

                    # ✅ Purchase taxable (already available)
                    "taxable_value": float(item.get("basePrice"))/float(item.get("quantity")),

                    "gstRate": item.get("gstRate"),
                    "cgst": float(item.get("cgst", 0)),
                    "sgst": float(item.get("sgst", 0)),
                    "igst": float(item.get("igst", 0))
                })

        # =========================
        # 🔹 SALES (BILLS)
        # =========================
        bills = list(
            db.bills.find(
                {},
                {
                    "_id": 0,
                    "id": 1,
                    "invoiceDate": 1,
                    "items": 1,
                    "clientName": 1,
                    "custid": 1,
                    "gstsummary": 1
                }
            ).sort("invoiceDate", -1)
        )

        for b in bills:
            items = b.get("items", [])
            date = b.get("invoiceDate")

            gst_summary = b.get("gstsummary", {})

            for item in items:
                rate = item.get("rate", 0)
                qty = item.get("qty", 0)
                total = rate * qty

                gst_rate = float(item.get("gstslab") or 0)

                # ✅ SALE is ALWAYS EXCLUSIVE
                taxable_value = total

                gst_data = gst_summary.get(str(int(gst_rate)), {})

                final_items.append({
                    "type": "sale",
                    "date": date,
                    "voucher_number": b.get("id"),
                    "party_name": b.get("clientName"),
                    "party_id": b.get("custid"),

                    "productName": item.get("description"),
                    "category": None,
                    "hsnCode": item.get("hsnCode"),

                    "quantity": qty,
                    "price": rate,
                    "total": total,

                    # ✅ simple
                    "taxable_value": taxable_value/qty,

                    "gstRate": gst_rate,
                    "cgst": gst_data.get("cgst", 0),
                    "sgst": gst_data.get("sgst", 0),
                    "igst": gst_data.get("igst", 0)
                })

        product = list(db.products.find({}))
        for d in product:
            d["_id"] = str(d["_id"])

        return jsonify({
            "status": "success",
            "count": len(final_items),
            "data": final_items,
            "product": product
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

def get_next_emp_id():
    counter = db.counters.find_one_and_update(
        {"_id": "staff_emp_id"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )

    return f"EMP{counter['seq']:04d}"

@trade_bp.route("/create-staff", methods=["POST"])
def create_or_edit_staff():
    try:
        data = request.json
        staff_id = data.get("_id")
        password = data.get("password")
        confirm_password = data.get("confirmPassword")
        designation = data.get("designation")

        # Remove confirm password from DB data
        data.pop("confirmPassword", None)

        # Validate password while creating or changing password
        if password:
            if password != confirm_password:
                return jsonify({
                    "success": False,
                    "message": "Password and Confirm Password do not match"
                }), 400

        # Convert designation to ObjectId
        if designation:
            data["designation"] = ObjectId(designation)

        # ================= UPDATE STAFF =================
        if staff_id:

            data.pop("_id", None)

            # Update password only if provided
            if password:
                data["password"] = generate_password_hash(password)
            else:
                data.pop("password", None)

            data["updated_at"] = datetime.utcnow()

            result = db.staff.update_one(
                {"_id": ObjectId(staff_id)},
                {"$set": data}
            )

            if result.matched_count == 0:
                return jsonify({
                    "success": False,
                    "message": "Staff not found"
                }), 404

            return jsonify({
                "success": True,
                "message": "Staff updated successfully"
            }), 200

        # ================= CREATE STAFF =================
        else:

            if not password:
                return jsonify({
                    "success": False,
                    "message": "Password is required"
                }), 400

            data["empID"] = get_next_emp_id()
            data["password"] = generate_password_hash(password)
            data["created_at"] = datetime.utcnow()

            result = db.staff.insert_one(data)

            return jsonify({
                "success": True,
                "message": "Staff created successfully",
                "staff_id": str(result.inserted_id),
                "empID": data["empID"]
            }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@trade_bp.route("/list-staff", methods=["GET"])
def list_staff():
    try:
        staff_list = list(
            db.staff.aggregate([
                {
                    "$lookup": {
                        "from": "designations",      # collection name
                        "localField": "designation",
                        "foreignField": "_id",
                        "as": "designation"
                    }
                },
                {
                    "$unwind": {
                        "path": "$designation",
                        "preserveNullAndEmptyArrays": True
                    }
                },
                {
                    "$project": {
                        "_id": {"$toString": "$_id"},
                        "name": 1,
                        "phone": 1,
                        "email": 1,
                        "empID": 1,
                        "designation": "$designation.name",
                        "created_at": 1
                    }
                },
                {
                    "$sort": {"created_at": -1}
                }
            ])
        )

        return jsonify(staff_list), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@trade_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    emp_id = data.get("empId")
    password = data.get("password")

    if not emp_id or not password:
        return jsonify({
            "success": False,
            "message": "Employee ID and Password are required"
        }), 400

    user = db.staff.find_one({"empID": emp_id})

    if not user:
        return jsonify({
            "success": False,
            "message": "Invalid Employee ID"
        }), 401

    if not check_password_hash(user.get("password"), password):
        return jsonify({
            "success": False,
            "message": "Invalid Password"
        }), 401

    # Fetch designation details
    designation = db.designations.find_one(
        {"_id": user["designation"]}
    )

    permissions = []
    designation_name = None

    if designation:
        permissions = designation.get("permissions", [])
        designation_name = designation.get("name")

    user["_id"] = str(user["_id"])
    user["designation"] = str(user["designation"])

    # Remove password before sending response
    user.pop("password", None)

    return jsonify({
        "success": True,
        "message": "Login Successful",
        "user": user,
        "designation": designation_name,
        "permissions": permissions
    }), 200


# ✅ Create / Edit Designation (single API)
@trade_bp.route("/designation", methods=["POST"])
def create_or_edit_designation():
    data = request.json
    designation_id = data.get("_id")
    designation_name = data.get("name")

    if not designation_name:
        return jsonify({"error": "designation_name is required"}), 400

    if designation_id: 
        data.pop("_id", None)
        # 🔹 Edit existing designation
        result = db.designations.update_one(
            {"_id": ObjectId(designation_id)},
            {"$set": data}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Designation not found"}), 404
        return jsonify({"message": "Designation updated successfully", "_id": designation_id}), 200

    else:  
        # 🔹 Create new designation
        result = db.designations.insert_one(data)
        return jsonify({"message": "Designation created successfully"}), 201


# ✅ Get All Designations
@trade_bp.route("/designations", methods=["GET"])
def get_designations():
    designations = list(db.designations.find({}))
    for d in designations:
        d["_id"] = str(d["_id"])
    return jsonify(designations), 200





