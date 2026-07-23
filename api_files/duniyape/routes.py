from flask import Blueprint, request, jsonify
from api_files.utils import duniyape_db, gold_db, care_db
from bson.objectid import ObjectId
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from api_files.duniyape.staff import staff_bp
from api_files.duniyape.trade import trade_bp
from api_files.duniyape.awsfile import aws_bp

duniyape_bp = Blueprint("duniyape_accounting", __name__)
caredb_vouchers = care_db["vouchers"] 
golddb_vouchers = gold_db["vouchers"] 

duniyape_bp.register_blueprint(staff_bp, url_prefix="/staff")
duniyape_bp.register_blueprint(trade_bp, url_prefix="/trade")
duniyape_bp.register_blueprint(aws_bp, url_prefix="/aws")

vouchers = duniyape_db["vouchers"] 
groups_collection = duniyape_db["groups"] 
subgroups_collection = duniyape_db["subgroups"] 
ledgers_collection = duniyape_db["ledgers"] 


@duniyape_bp.route("/payment_voucher", methods=["POST"])
def payment_voucher():
    try:
        data = request.json

        narration = data.get('narration')
        date = data.get("date")
        amt = data.get("amount")
        entries = data.get("entries")
        voucher_mode = data.get('voucher_mode', '')

        # ✅ Handle date safely (string + ISO + fallback)
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

        # ✅ Normalize date (important for daily count)
        start = datetime(voucher_date.year, voucher_date.month, voucher_date.day)
        end = start + timedelta(days=1)

        date_str = start.strftime("%Y-%m-%d")

        count_txn = vouchers.count_documents({})

        count = vouchers.count_documents({
            "voucher_type": "Payment",
            "voucher_mode": voucher_mode,
            "date": {"$gte": start, "$lt": end}
        })

        # ✅ Clean prefix logic
        prefix = "B" if voucher_mode == "Bank" else "C"
        voucher_number = f"{prefix}PV-{date_str}-{count + 1}"

        voucher = {
            "voucher_number": voucher_number,
            "voucher_type": 'Payment',
            "voucher_mode": voucher_mode,
            "txn": count_txn + 1,
            "from_id": "admin",
            "date": start,  # ✅ always normalized datetime
            "narration": narration,
            "amount": float(amt),
            "entries": entries,
            "created_by": "admin",
            "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
        }

        vouchers.insert_one(voucher)

        return jsonify({
            "status": "ok",
            "voucherCode": voucher_number,
            "txn": count_txn + 1
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# @duniyape_bp.route("/payment_voucher", methods=["POST"])
# def payment_voucher():
#     try:
#         data = request.json
#         narration = data.get('narration')
#         date = data.get("date", datetime.now(ZoneInfo("Asia/Kolkata")))
#         amt = data.get("amount")
#         entries=data.get("entries")
#         voucher_mode=data.get('voucher_mode','')
#         voucher_date = date
#         date_str = voucher_date.strftime("%Y-%m-%d")
#         date_obj = datetime.strptime(date_str, "%Y-%m-%d")
#         start = datetime(date_obj.year, date_obj.month, date_obj.day)
#         end = start + timedelta(days=1)

#         count_txn = vouchers.count_documents({})
#         count = vouchers.count_documents({
#                     "voucher_type": "Payment",
#                     "voucher_mode": voucher_mode,
#                     "date": {"$gte": start, "$lt": end}   # between start and end of day
#         })

#         # voucher_number = 'B'+ "PV-" + str(date_str) + '-' + str(count + 1) if voucher_mode == "Bank" else 'C' + "PV-" + str(date_str) + '-' + str(count + 1)
#         voucher_number = (f"{'B' if voucher_mode == 'Bank' else 'C'}PV-{date_str}-{count + 1}")
#         voucher = {
#                     "voucher_number": voucher_number,
#                     "voucher_type": 'Payment',
#                     "voucher_mode": voucher_mode,
#                     "txn": count_txn + 1,
#                     "from_id": "admin",
#                     "date": date,
#                     "narration": narration,
#                     "amount":float(amt),
#                     "entries": entries,
#                     "created_by": "admin",
#                     "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
#                 }
#         vouchers.insert_one(voucher)
#         return jsonify({"status": "ok","voucherCode":voucher_number,"txn":count_txn + 1}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500

# @duniyape_bp.route("/receipt_voucher", methods=["POST"])
# def receipt_voucher():
#     try:
#         data = request.json
#         narration = data.get('narration')
#         date = data.get("date", datetime.now(ZoneInfo("Asia/Kolkata")))
#         amt = data.get("amount")
#         entries=data.get("entries")
#         voucher_mode=data.get('voucher_mode','')
#         voucher_date = date
#         date_str = voucher_date.strftime("%Y-%m-%d")
#         date_obj = datetime.strptime(date_str, "%Y-%m-%d")
#         start = datetime(date_obj.year, date_obj.month, date_obj.day)
#         end = start + timedelta(days=1)

#         count_txn = vouchers.count_documents({})
#         count = vouchers.count_documents({
#                     "voucher_type": "Receipt",
#                     "voucher_mode": voucher_mode,
#                     "date": {"$gte": start, "$lt": end}   # between start and end of day
#         })

#         # voucher_number = 'B'+ "PV-" + str(date_str) + '-' + str(count + 1) if voucher_mode == "Bank" else 'C' + "PV-" + str(date_str) + '-' + str(count + 1)
#         voucher_number = (f"{'B' if voucher_mode == 'Bank' else 'C'}RV-{date_str}-{count + 1}")
#         voucher = {
#                     "voucher_number": voucher_number,
#                     "voucher_type": 'Receipt',
#                     "voucher_mode": voucher_mode,
#                     "txn": count_txn + 1,
#                     "from_id": "admin",
#                     "date": date,
#                     "narration": narration,
#                     "amount":float(amt),
#                     "entries": entries,
#                     "created_by": "admin",
#                     "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
#                 }
#         vouchers.insert_one(voucher)
#         return jsonify({"status": "ok","voucherCode":voucher_number,"txn":count_txn + 1}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


@duniyape_bp.route("/receipt_voucher", methods=["POST"])
def receipt_voucher():
    try:
        data = request.json

        narration = data.get('narration')
        date = data.get("date")
        amt = data.get("amount")
        entries = data.get("entries")
        voucher_mode = data.get('voucher_mode', '')

        # ✅ Handle date properly
        if isinstance(date, str):
            if "T" in date:
                # ISO format
                voucher_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
                voucher_date = voucher_date.astimezone(ZoneInfo("Asia/Kolkata"))
            else:
                # YYYY-MM-DD
                voucher_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))

        # ✅ Normalize date (important)
        start = datetime(voucher_date.year, voucher_date.month, voucher_date.day)
        end = start + timedelta(days=1)

        date_str = start.strftime("%Y-%m-%d")

        count_txn = vouchers.count_documents({})

        count = vouchers.count_documents({
            "voucher_type": "Receipt",
            "voucher_mode": voucher_mode,
            "date": {"$gte": start, "$lt": end}
        })

        # ✅ Clean voucher number
        prefix = "B" if voucher_mode == "Bank" else "C"
        voucher_number = f"{prefix}RV-{date_str}-{count + 1}"

        voucher = {
            "voucher_number": voucher_number,
            "voucher_type": 'Receipt',
            "voucher_mode": voucher_mode,
            "txn": count_txn + 1,
            "from_id": "admin",
            "date": start,  # ✅ always normalized
            "narration": narration,
            "amount": float(amt),
            "entries": entries,
            "created_by": "admin",
            "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
        }

        vouchers.insert_one(voucher)

        return jsonify({
            "status": "ok",
            "voucherCode": voucher_number,
            "txn": count_txn + 1
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@duniyape_bp.route("/journal_voucher", methods=["POST"])
def journal_voucher():
    try:
        data = request.json

        date = data.get("date")
        narration = data.get('narration')
        amt = data.get("amount")
        entries = data.get("entries")

        # ✅ Handle date safely
        if isinstance(date, str):
            # ISO format (2026-03-20T00:00:00.000Z)
            if "T" in date:
                voucher_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
                voucher_date = voucher_date.astimezone(ZoneInfo("Asia/Kolkata"))
            else:
                # simple format (2026-03-20)
                voucher_date = datetime.strptime(date, "%Y-%m-%d")
        else:
            voucher_date = datetime.now(ZoneInfo("Asia/Kolkata"))

        # ✅ Normalize to start of day (important for counting)
        start = datetime(voucher_date.year, voucher_date.month, voucher_date.day)
        end = start + timedelta(days=1)

        date_str = start.strftime("%Y-%m-%d")

        count_txn = vouchers.count_documents({})

        count = vouchers.count_documents({
            "voucher_type": "Journal",
            "voucher_mode": "Journal",
            "date": {"$gte": start, "$lt": end}
        })

        voucher_number = f"JRV-{date_str}-{count + 1}"

        voucher = {
            "voucher_number": voucher_number,
            "voucher_type": 'Journal',
            "voucher_mode": "Journal",
            "txn": count_txn + 1,
            "from_id": "admin",
            "date": start,  # ✅ store normalized date
            "narration": narration,
            "amount": float(amt),
            "entries": entries,
            "created_by": "admin",
            "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
        }

        vouchers.insert_one(voucher)

        return jsonify({
            "status": "ok",
            "voucherCode": voucher_number,
            "txn": count_txn + 1
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @duniyape_bp.route("/journal_voucher", methods=["POST"])
# def journal_voucher():
#     try:
#         data = request.json
#         date = data.get("date", datetime.now(ZoneInfo("Asia/Kolkata")))
#         narration = data.get('narration')
#         amt = data.get("amount")
#         entries=data.get("entries")
#         voucher_date = date
#         date_str = voucher_date.strftime("%Y-%m-%d")
#         date_obj = datetime.strptime(date_str, "%Y-%m-%d")
#         start = datetime(date_obj.year, date_obj.month, date_obj.day)
#         end = start + timedelta(days=1)

#         count_txn = vouchers.count_documents({})
#         count = vouchers.count_documents({
#                     "voucher_type": "Journal",
#                     "voucher_mode": "Journal",
#                     "date": {"$gte": start, "$lt": end}   # between start and end of day
#         })

#         voucher_number = "JRV-"+ str(date_str) +'-'+ str(count + 1)
#         voucher = {
#                     "voucher_number": voucher_number,
#                     "voucher_type": 'Journal',
#                     "voucher_mode": "Journal",
#                     "txn": count_txn + 1,
#                     "from_id": "admin",
#                     "date": date,
#                     "narration": narration,
#                     "amount":float(amt),
#                     "entries": entries,
#                     "created_by": "admin",
#                     "created_at": datetime.now(ZoneInfo("Asia/Kolkata"))
#                 }
#         vouchers.insert_one(voucher)
#         return jsonify({"status": "ok","voucherCode":voucher_number,"txn":count_txn + 1}), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


@duniyape_bp.route("/v1/vouchers", methods=["GET"])
def get_vouchers_filtered():
    from_date = request.args.get("from_date")  # 2025-08-01
    to_date = request.args.get("to_date")      # 2025-08-30
    voucher_type = request.args.get("voucher_type")
    voucher_mode = request.args.get("voucher_mode")
    
    query = {}

    if from_date and to_date:
        # IST timezone
        ist = ZoneInfo("Asia/Kolkata")
        utc = ZoneInfo("UTC")

        # Convert string → IST datetime
        start_ist = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=ist)
        end_ist = datetime.strptime(to_date, "%Y-%m-%d").replace(tzinfo=ist)

        # End of day
        end_ist = end_ist.replace(hour=23, minute=59, second=59)

        # Convert IST → UTC
        start_utc = start_ist.astimezone(utc)
        end_utc = end_ist.astimezone(utc)

        query["date"] = {"$gte": start_utc, "$lte": end_utc}

    if voucher_type:
        query["voucher_type"] = voucher_type

    if voucher_mode:
        query["voucher_mode"] = voucher_mode

    # Fetch data
    voucher_main = list(vouchers.find(query))
    voucher_care = list(caredb_vouchers.find(query))
    voucher_gold = list(golddb_vouchers.find(query))

    def process_list(data_list, company_name):
        for item in data_list:
            item["_id"] = str(item["_id"])
            item["company"] = company_name

            # OPTIONAL: UTC → IST for response
            if "date" in item:
                item["date"] = item["date"].astimezone(ist).strftime("%Y-%m-%d %H:%M:%S")

        return data_list

    voucher_main = process_list(voucher_main, "Duniyape")
    voucher_care = process_list(voucher_care, "Care2connect")
    voucher_gold = process_list(voucher_gold, "Gold App")

    merged_list = voucher_main + voucher_care + voucher_gold

    # latest first
    merged_list.sort(key=lambda x: x.get("date"), reverse=True)

    return jsonify(merged_list)
# Ledger mapping
get_ledger = {
        'A1': {'duniya': "A1", 'gold': "A6", 'care': "A1"},
        'A2': {'duniya': "A2", 'gold': None, 'care': "A2"},
        'A3': {'duniya': "A3", 'gold': None, 'care': "A3"},
        'A4': {'duniya': "A4", 'gold': None, 'care': "A4"},
        'A5': {'duniya': "A5", 'gold': "A2", 'care': "A5"},
        'A6': {'duniya': "A6", 'gold': None, 'care': "A6"},
        'A7': {'duniya': "A7", 'gold': None, 'care': "A7"},
        'A8': {'duniya': "A8", 'gold': "A3", 'care': "A8"},
        'A9': {'duniya': "A9", 'gold': None, 'care': "A9"},
        'A10': {'duniya': "A10", 'gold': None, 'care': "A10"},
        'A11': {'duniya': "A11", 'gold': None, 'care': "A11"},
        'A12': {'duniya': "A12", 'gold': "A1", 'care': None},
        'A13': {'duniya': "A13", 'gold': "A4", 'care': None},
        'A14': {'duniya': "A14", 'gold': "A5", 'care': None},
    'A15': {'duniya': "A15", 'gold': None, 'care': None},
        'A16': {'duniya': "A16", 'gold': None, 'care': None},
    'A17': {'duniya': "A17", 'gold': None, 'care': None},
    'A18': {'duniya': "A18", 'gold': None, 'care': None},
    'A19': {'duniya': "A19", 'gold': None, 'care': None},
    'A20': {'duniya': "A20", 'gold': None, 'care': None},
    'A21': {'duniya': "A21", 'gold': None, 'care': None},
    'A22': {'duniya': "A22", 'gold': None, 'care': "A12"},
    'A23': {'duniya': "A23", 'gold': None, 'care': "A13"},
    'A24': {'duniya': "A24", 'gold': None, 'care': "A14"},
    'A25': {'duniya': "A25", 'gold': None, 'care': None},
    'A26': {'duniya': "A26", 'gold': None, 'care': None},
    'A27': {'duniya': "A27", 'gold': None, 'care': None},
    'A28': {'duniya': "A28", 'gold': None, 'care': None},
    'A29': {'duniya': "A29", 'gold': None, 'care': None},
    'A30': {'duniya': "A30", 'gold': None, 'care': None},
    'A31': {'duniya': "A31", 'gold': None, 'care': None},
    'A32': {'duniya': "A32", 'gold': None, 'care': None},
    'A33': {'duniya': "A33", 'gold': None, 'care': None},
    'A34': {'duniya': "A34", 'gold': None, 'care': None},
    'A35': {'duniya': "A35", 'gold': None, 'care': None},
    'A36': {'duniya': "A36", 'gold': None, 'care': None},
    'A37': {'duniya': "A37", 'gold': None, 'care': None},
    'A38': {'duniya': "A38", 'gold': None, 'care': None},
    'A39': {'duniya': "A39", 'gold': None, 'care': None},
    'A40': {'duniya': "A40", 'gold': None, 'care': None},
    'A41': {'duniya': "A41", 'gold': None, 'care': None},
    'A42': {'duniya': "A42", 'gold': None, 'care': None},
    'A43': {'duniya': "A43", 'gold': None, 'care': None},
    'A44': {'duniya': "A44", 'gold': None, 'care': None},
    }

@duniyape_bp.route('/v1/ledger/<ledger_id>', methods=['GET'])
def get_ledger_entries(ledger_id):
    from_date_str = request.args.get("from")
    to_date_str = request.args.get("to")

    # Validate ledger
    if ledger_id not in get_ledger:
        return jsonify({"error": "Invalid ledger_id"}), 400

    mapped = get_ledger[ledger_id]

    # Parse dates
    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d") if from_date_str else None
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d") if to_date_str else None
    except:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    # Helper → opening balance calculation
    def calc_opening(cursor, mapped_id):
        total = 0
        for doc in cursor:
            for entry in doc.get("entries", []):
                if entry.get("ledger_id") == mapped_id:
                    total += entry.get("debit", 0) - entry.get("credit", 0)
        return total

    # --- Opening Balance ---
    opening_balance = 0
    if from_date:

        # Duniyape opening balance
        if mapped['duniya']:
            q = {"entries.ledger_id": mapped['duniya'], "date": {"$lt": from_date}}
            opening_balance += calc_opening(vouchers.find(q), mapped['duniya'])

        # Care2connect opening balance
        if mapped['care']:
            q = {"entries.ledger_id": mapped['care'], "date": {"$lt": from_date}}
            opening_balance += calc_opening(caredb_vouchers.find(q), mapped['care'])

        # Gold App opening balance
        if mapped['gold']:
            q = {"entries.ledger_id": mapped['gold'], "date": {"$lt": from_date}}
            opening_balance += calc_opening(golddb_vouchers.find(q), mapped['gold'])

    # --- Build date filter query ---
    def build_query(mapped_id):
        if not mapped_id:
            return None
        q = {"entries.ledger_id": mapped_id}
        if from_date and to_date:
            q["date"] = {"$gte": from_date, "$lte": to_date}
        elif from_date:
            q["date"] = {"$gte": from_date}
        elif to_date:
            q["date"] = {"$lte": to_date}
        return q

    # Current period fetch
    duniyape_cursor = vouchers.find(build_query(mapped['duniya'])) if mapped['duniya'] else []
    care_cursor     = caredb_vouchers.find(build_query(mapped['care'])) if mapped['care'] else []
    gold_cursor     = golddb_vouchers.find(build_query(mapped['gold'])) if mapped['gold'] else []

    # Extract entries helper
    def extract_entries(results, company, mapped_id):
        temp = []
        for doc in results:
            for entry in doc.get("entries", []):
                if entry.get("ledger_id") == mapped_id:
                    temp.append({
                        "voucher_number": doc.get("voucher_number"),
                        "voucher_type": doc.get("voucher_type"),
                        "voucher_mode": doc.get("voucher_mode"),
                        "txn": doc.get("txn"),
                        "ledger_id": entry.get("ledger_id"),
                        "ledger_name": entry.get("ledger_name"),
                        "credit": entry.get("credit"),
                        "debit": entry.get("debit"),
                        "narration": entry.get("narration"),
                        "date": doc.get("date"),
                        "company": company,
                        "empId":entry.get("employee_id") if entry.get("employee_id") else ""
                    })
        return temp

    # Merge entries
    all_entries = []
    if mapped['duniya']:
        all_entries += extract_entries(duniyape_cursor, "Duniyape", mapped['duniya'])
    if mapped['care']:
        all_entries += extract_entries(care_cursor, "Care2Connect", mapped['care'])
    if mapped['gold']:
        all_entries += extract_entries(gold_cursor, "Gold App", mapped['gold'])

    # Sort by date ASC
    all_entries.sort(key=lambda x: x["date"])

    # Final response
    return jsonify({
        "ledger_id": ledger_id,
        "opening_balance": opening_balance,
        "transaction_count": len(all_entries),
        "transactions": all_entries
    })

@duniyape_bp.route('/v1/ledger2/<ledger_id>/<emp_name>', methods=['GET'])
def get_ledger_entries2(ledger_id, emp_name):
    from_date_str = request.args.get("from")
    to_date_str = request.args.get("to")

    # Validate ledger
    if ledger_id not in get_ledger:
        return jsonify({"error": "Invalid ledger_id"}), 400

    mapped = get_ledger[ledger_id]

    # Parse dates
    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d") if from_date_str else None
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d") if to_date_str else None
    except:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    # Helper → opening balance calc
    # def calc_opening(cursor, mapped_id):
    #     total = 0
    #     for doc in cursor:
    #         for entry in doc.get("entries", []):
    #             if entry.get("ledger_id") == mapped_id:
    #                 total += entry.get("debit", 0) - entry.get("credit", 0)
    #     return total
    
    def calc_opening(cursor, mapped_id, emp_name):
        total = 0
        for doc in cursor:
            for entry in doc.get("entries", []):
                if entry.get("ledger_id") == mapped_id:
    
                    emp_id = entry.get("employee_id", "")
                    emp_n = entry.get("employee_name", "").lower()
    
                    # ✅ SAME EMPLOYEE FILTER APPLY HERE
                    if emp_name and not (
                        emp_name == emp_id or emp_name.lower() in emp_n
                    ):
                        continue
    
                    total += entry.get("debit", 0) - entry.get("credit", 0)
        return total

    # ---------------- Opening Balance ----------------
    opening_balance = 0
    if from_date:
        # if mapped['duniya']:
        #     q = {"entries.ledger_id": mapped['duniya'], "date": {"$lt": from_date}}
        #     opening_balance += calc_opening(vouchers.find(q), mapped['duniya'])

        # if mapped['care']:
        #     q = {"entries.ledger_id": mapped['care'], "date": {"$lt": from_date}}
        #     opening_balance += calc_opening(caredb_vouchers.find(q), mapped['care'])

        # if mapped['gold']:
        #     q = {"entries.ledger_id": mapped['gold'], "date": {"$lt": from_date}}
        #     opening_balance += calc_opening(golddb_vouchers.find(q), mapped['gold'])

        if mapped['duniya']:
            q = {"entries.ledger_id": mapped['duniya'], "date": {"$lt": from_date}}
            opening_balance += calc_opening(vouchers.find(q), mapped['duniya'], emp_name)

        if mapped['care']:
            q = {"entries.ledger_id": mapped['care'], "date": {"$lt": from_date}}
            opening_balance += calc_opening(caredb_vouchers.find(q), mapped['care'], emp_name)

        if mapped['gold']:
            q = {"entries.ledger_id": mapped['gold'], "date": {"$lt": from_date}}
            opening_balance += calc_opening(golddb_vouchers.find(q), mapped['gold'], emp_name)

    # ---------------- Build Query ----------------
    def build_query(mapped_id):
        if not mapped_id:
            return None
        q = {"entries.ledger_id": mapped_id}
        if from_date and to_date:
            q["date"] = {"$gte": from_date, "$lte": to_date}
        elif from_date:
            q["date"] = {"$gte": from_date}
        elif to_date:
            q["date"] = {"$lte": to_date}
        return q

    # Fetch current period data
    duniyape_cursor = vouchers.find(build_query(mapped['duniya'])) if mapped['duniya'] else []
    care_cursor     = caredb_vouchers.find(build_query(mapped['care'])) if mapped['care'] else []
    gold_cursor     = golddb_vouchers.find(build_query(mapped['gold'])) if mapped['gold'] else []

    # ---------------- Extract Entries with EMPLOYEE FILTER ----------------
    def extract_entries(results, company, mapped_id, emp_name):
        temp = []
        for doc in results:
            for entry in doc.get("entries", []):
                if entry.get("ledger_id") == mapped_id:

                    emp_id = entry.get("employee_id", "")
                    emp_n = entry.get("employee_name", "").lower()

                    # FILTER BY EMPLOYEE
                    if emp_name and not (
                        emp_name == emp_id or emp_name.lower() in emp_n
                    ):
                        continue  # skip if employee does not match

                    temp.append({
                        "voucher_number": doc.get("voucher_number"),
                        "voucher_type": doc.get("voucher_type"),
                        "voucher_mode": doc.get("voucher_mode"),
                        "txn": doc.get("txn"),
                        "ledger_id": entry.get("ledger_id"),
                        "ledger_name": entry.get("ledger_name"),
                        "credit": entry.get("credit"),
                        "debit": entry.get("debit"),
                        "narration": entry.get("narration"),
                        "date": doc.get("date"),
                        "company": company,
                        "employee_id": emp_id,
                        "employee_name": entry.get("employee_name", "")
                    })
        return temp

    # ---------------- Merge all entries ----------------
    all_entries = []

    if mapped['duniya']:
        all_entries += extract_entries(duniyape_cursor, "Duniyape", mapped['duniya'], emp_name)

    if mapped['care']:
        all_entries += extract_entries(care_cursor, "Care2Connect", mapped['care'], emp_name)

    if mapped['gold']:
        all_entries += extract_entries(gold_cursor, "Gold App", mapped['gold'], emp_name)

    # Sort by date ASC
    all_entries.sort(key=lambda x: x["date"])

    # ---------------- Final Response ----------------
    return jsonify({
        "ledger_id": ledger_id,
        "opening_balance": opening_balance,
        "transaction_count": len(all_entries),
        "transactions": all_entries
    })

# ------------------ GROUPS ------------------
@duniyape_bp.route("/groups", methods=["POST"])
def create_or_edit_group():
    try:
        data = request.json

        if "_id" in data and data["_id"]:  # EDIT
            groups_collection.update_one(
                {"_id": ObjectId(data["_id"])},
                {"$set": {
                    "GroupName": data["groupname"],
                    "GroupType": data["grouptype"]
                }}
            )
            return jsonify({"message": "Group updated successfully"}), 200
        else:  # CREATE
            count = groups_collection.count_documents({})
            mcode = f"G{count + 1}"

            new_group = {
                "Code": mcode,
                "GroupName": data["groupname"],
                "GroupType": data["grouptype"]
            }
            inserted = groups_collection.insert_one(new_group)
            new_group["_id"] = str(inserted.inserted_id)

            return jsonify({"message": "Group created successfully", "group": new_group}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@duniyape_bp.route("/groups", methods=["GET"])
def get_all_groups():
    try:
        groups = list(groups_collection.find())
        for g in groups:
            g["_id"] = str(g["_id"])
        return jsonify(groups), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@duniyape_bp.route("/subgroups", methods=["POST"])
def create_or_edit_subgroup():
    try:
        data = request.json

        if not data.get("group_id"):
            return jsonify({"error": "group_id is required"}), 400

        if not data.get("subgroupname"):
            return jsonify({"error": "subgroupname is required"}), 400

        # -------- EDIT --------
        if data.get("_id"):
            subgroups_collection.update_one(
                {"_id": ObjectId(data["_id"])},
                {"$set": {
                    "Group_id": ObjectId(data["group_id"]),
                    "subgroupname": data["subgroupname"]
                }}
            )
            return jsonify({"message": "Subgroup updated successfully"}), 200

        # -------- CREATE --------
        count = subgroups_collection.count_documents({})
        mcode = f"SG{count + 1}"

        subgroups_collection.insert_one({
            "Code": mcode,
            "Group_id": ObjectId(data["group_id"]),
            "subgroupname": data["subgroupname"]
        })

        # 🔥 IMPORTANT: no ObjectId in response
        return jsonify({"message": "Subgroup created successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500





@duniyape_bp.route("/subgroups", methods=["GET"])
def get_all_subgroups():
    try:
        pipeline = [
            {
                "$lookup": {
                    "from": "groups",
                    "localField": "Group_id",
                    "foreignField": "_id",
                    "as": "group_info"
                }
            },
            {"$unwind": {"path": "$group_info", "preserveNullAndEmptyArrays": True}},
            {
                "$project": {
                    "_id": {"$toString": "$_id"},
                    "Code": 1,
                    "subgroupname": 1,

                    # 🔥 MOST IMPORTANT FIX
                    "Group_id": {"$toString": "$Group_id"},

                    "GroupName": {"$ifNull": ["$group_info.GroupName", "-"]},
                    "GroupType": {"$ifNull": ["$group_info.GroupType", "-"]}
                }
            }
        ]

        subgroups = list(subgroups_collection.aggregate(pipeline))
        return jsonify(subgroups), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------ LEDGERS ------------------
@duniyape_bp.route("/ledgers", methods=["POST"])
def create_or_edit_ledger():
    try:
        data = request.json

        # -------- VALIDATION --------
        if not data.get("group_id"):
            return jsonify({"error": "group_id is required"}), 400

        if not data.get("ledgername"):
            return jsonify({"error": "ledgername is required"}), 400

        # -------- EDIT --------
        if data.get("_id"):
            ledgers_collection.update_one(
                {"_id": ObjectId(data["_id"])},
                {"$set": {
                    "Group_id": ObjectId(data["group_id"]),
                    "GroupType": data.get("grouptype"),
                    "LedgerName": data["ledgername"],
                    "subgroupname": data.get("subgroupname", "")
                }}
            )
            return jsonify({"message": "Ledger updated successfully"}), 200

        # -------- CREATE --------
        count = ledgers_collection.count_documents({})
        mcode = f"A{count + 1}"

        ledgers_collection.insert_one({
            "Code": mcode,
            "Group_id": ObjectId(data["group_id"]),
            "GroupType": data.get("grouptype"),
            "LedgerName": data["ledgername"],
            "subgroupname": data.get("subgroupname", "")
        })

        # 🔥 IMPORTANT: do NOT return ObjectId
        return jsonify({"message": "Ledger created successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@duniyape_bp.route("/ledgers", methods=["GET"])
def get_all_ledgers():
    try:
        pipeline = [
            {
                "$lookup": {
                    "from": "groups",
                    "localField": "Group_id",
                    "foreignField": "_id",
                    "as": "group_info"
                }
            },
            {
                "$unwind": {
                    "path": "$group_info",
                    "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$project": {
                    "_id": {"$toString": "$_id"},
                    "Code": 1,
                    "LedgerName": 1,
                    "subgroupname": 1,

                    # 🔥 CRITICAL FIX
                    "Group_id": {"$toString": "$Group_id"},

                    "GroupName": {"$ifNull": ["$group_info.GroupName", "-"]},
                    "GroupType": {"$ifNull": ["$group_info.GroupType", "-"]}
                }
            }
        ]

        ledgers = list(ledgers_collection.aggregate(pipeline))
        return jsonify(ledgers), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    
@duniyape_bp.route("/v1/financial-report", methods=["GET"])
def financial_report():
    report_type = request.args.get("report",'trialbalance')  # trialbalance / pl / balancesheet
    from_date_str = request.args.get("from")
    to_date_str = request.args.get("to")

    # --- 1. Parse dates ---
    try:
        from_date = datetime.strptime(from_date_str, "%Y-%m-%d") if from_date_str else None
        to_date = datetime.strptime(to_date_str, "%Y-%m-%d") if to_date_str else None
    except:
        return jsonify({"error": "Invalid date format, use YYYY-MM-DD"}), 400

    # --- 2. Fetch Ledger Groups and Ledger Names ---
    ledgers_data = {l["Code"]: l for l in ledgers_collection.find()}

    # --- 4. Trial Balance with groupwise and opening balance ---
    if report_type == "trialbalance":
        company = request.args.get("company", "duniya")  # duniya | care | gold

        trial_balance = {}

        for ledger_id, mapped_ids in get_ledger.items():

            # --- Company filter logic ---
            valid_ids = {}

            if company == "duniya":
                valid_ids = mapped_ids   # use all
            elif company == "care":
                if mapped_ids.get("care"):
                    valid_ids["care"] = mapped_ids["care"]
            elif company == "gold":
                if mapped_ids.get("gold"):
                    valid_ids["gold"] = mapped_ids["gold"]
            else:
                return jsonify({"error": "Invalid company. Use duniya, care, or gold"}), 400

            # Opening entries
            opening_entries = []

            if from_date:
                def fetch_before(cursor, m_id):
                    for doc in cursor:
                        for e in doc.get("entries", []):
                            if e.get("ledger_id") == m_id:
                                opening_entries.append({
                                    "debit": e.get("debit", 0),
                                    "credit": e.get("credit", 0)
                                })

                if valid_ids.get("duniya"):
                    fetch_before(
                        vouchers.find({"entries.ledger_id": valid_ids["duniya"], "date": {"$lt": from_date}}),
                        valid_ids["duniya"]
                    )
                if valid_ids.get("care"):
                    fetch_before(
                        caredb_vouchers.find({"entries.ledger_id": valid_ids["care"], "date": {"$lt": from_date}}),
                        valid_ids["care"]
                    )
                if valid_ids.get("gold"):
                    fetch_before(
                        golddb_vouchers.find({"entries.ledger_id": valid_ids["gold"], "date": {"$lt": from_date}}),
                        valid_ids["gold"]
                    )

            opening_balance = sum(e["debit"] - e["credit"] for e in opening_entries)

            # Current period entries
            current_entries = []

            # use your fetch function — but only for filtered company
            def fetch_filtered():
                result = []

                if valid_ids.get("duniya"):
                    q = {"entries.ledger_id": valid_ids["duniya"]}
                    if from_date:
                        q["date"] = {"$gte": from_date}
                    if to_date:
                        q["date"]["$lte"] = to_date
                    for doc in vouchers.find(q):
                        for e in doc.get("entries", []):
                            if e.get("ledger_id") == valid_ids["duniya"]:
                                result.append(e)

                if valid_ids.get("care"):
                    q = {"entries.ledger_id": valid_ids["care"]}
                    if from_date:
                        q["date"] = {"$gte": from_date}
                    if to_date:
                        q["date"]["$lte"] = to_date
                    for doc in caredb_vouchers.find(q):
                        for e in doc.get("entries", []):
                            if e.get("ledger_id") == valid_ids["care"]:
                                result.append(e)

                if valid_ids.get("gold"):
                    q = {"entries.ledger_id": valid_ids["gold"]}
                    if from_date:
                        q["date"] = {"$gte": from_date}
                    if to_date:
                        q["date"]["$lte"] = to_date
                    for doc in golddb_vouchers.find(q):
                        for e in doc.get("entries", []):
                            if e.get("ledger_id") == valid_ids["gold"]:
                                result.append(e)

                return result

            current_entries = fetch_filtered()

            total_debit = sum(e.get("debit", 0) for e in current_entries)
            total_credit = sum(e.get("credit", 0) for e in current_entries)

            group_type = ledgers_data.get(ledger_id, {}).get("GroupType", "Unknown")
            ledger_name = ledgers_data.get(ledger_id, {}).get("LedgerName", ledger_id)

            if group_type not in trial_balance:
                trial_balance[group_type] = []

            closing_raw = opening_balance + total_debit - total_credit
            closing_type = "DR" if closing_raw >= 0 else "CR"

            trial_balance[group_type].append({
                "ledger_id": ledger_id,
                "ledger_name": ledger_name,
                "opening_balance": abs(opening_balance),
                "period_debit": total_debit,
                "period_credit": total_credit,
                "closing_balance": abs(closing_raw),
                "closing_type": closing_type
            })

        return jsonify(trial_balance)
