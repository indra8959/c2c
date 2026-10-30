from flask import Flask, jsonify, request, current_app
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from pymongo import ReturnDocument
import re

# MongoDB connection
client = MongoClient("mongodb+srv://igold:gold0011@igold.eazpfbp.mongodb.net/?retryWrites=true&w=majority&appName=igold")

db = client["test_db"]
collection = db["doctor_specialities"]
lab_test = Blueprint("lab_test", __name__)

@lab_test.route("/doctor-specialities", methods=["GET"])
def get_doctor_specialities():
    try:
        specialities = list(
            collection.find(
                {},
                {
                    "_id": 1,
                    "name": 1,
                    "description": 1,
                    "imageurl": 1
                }
            ).sort("name", 1)
        )

        for item in specialities:
            item["_id"] = str(item["_id"])

        return jsonify({
            "success": True,
            "count": len(specialities),
            "data": specialities
        }), 200

    except Exception as e:
        app.logger.exception("Failed to fetch doctor specialities")
        return jsonify({
            "success": False,
            "message": "Failed to fetch doctor specialities"
        }), 500


def error(message, code=400):
    return jsonify({
        "success": False,
        "message": message
    }), code

@lab_test.route("/create-approved", methods=["POST"])
def create_approved_lab():
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return error("Valid JSON object required")

        basic = data.get("basic_info", {})
        address = data.get("address", {})

        required = {
            "lab_name": basic.get("lab_name"),
            "owner_name": basic.get("owner_name"),
            "contact_number": basic.get("contact_number"),
            "email": basic.get("email"),
            "city": address.get("city"),
            "state": address.get("state"),
            "pincode": address.get("pincode"),
            "address_line": address.get("address_line")
        }

        missing = [
            key for key, value in required.items()
            if not value or not str(value).strip()
        ]

        if missing:
            return jsonify({
                "success": False,
                "message": "Required fields missing",
                "missing_fields": missing
            }), 400

        if not re.fullmatch(r"[6-9]\d{9}", str(basic["contact_number"])):
            return error("Invalid mobile number")

        email = basic["email"].strip().lower()

        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            return error("Invalid email address")


        existing = db.labs.find_one({
            "basic_info.email": email
        })

        if existing:
            return error("Lab already exists", 409)

        now = datetime.utcnow()

        # Generate unique lab code
        counter = db.counters.find_one_and_update(
            {"_id": "lab_code"},
            {"$inc": {"sequence": 1}},
            upsert=True,
            return_document=True
        )

        lab_code = f"LAB{counter['sequence']:06d}"

        lab = {
            "lab_code": lab_code,

            "basic_info": {
                "lab_name": basic["lab_name"].strip(),
                "lab_type": basic.get("lab_type", "diagnostic"),
                "owner_name": basic["owner_name"].strip(),
                "contact_number": basic["contact_number"],
                "alternate_number": basic.get("alternate_number"),
                "email": email,
                "website": basic.get("website"),
                "description": basic.get("description"),
                "logo": basic.get("logo")
            },

            "address": address,

            "certifications": data.get("certifications", {}),

            "services": data.get("services", {}),

            "working_hours": data.get("working_hours", []),

            "bank_details": data.get("bank_details", {}),

            "documents": [],

            # Direct approval
            "status": "active",

            "verification": {
                "verified_by": data.get("admin_id"),
                "verified_at": now,
                "remarks": "Directly approved by admin",
                "rejection_reason": None
            },

            "created_at": now,
            "updated_at": now
        }

        result = db.labs.insert_one(lab)

        return jsonify({
            "success": True,
            "message": "Lab created and approved successfully",
            "data": {
                "lab_id": str(result.inserted_id),
                "lab_code": lab_code,
                "lab_name": basic["lab_name"],
                "status": "active",
                "is_approved": True
            }
        }), 201

    except Exception:
        current_app.logger.exception("Direct approved lab error")
        return error("Internal server error", 500)


@lab_test.route("/api/labs/list", methods=["GET"])
def get_labs_list():
    try:
        page = max(request.args.get("page", 1, type=int), 1)
        limit = min(max(request.args.get("limit", 20, type=int), 1), 100)

        search = request.args.get("search", "").strip()
        status = request.args.get("status", "").strip()
        city = request.args.get("city", "").strip()
        state = request.args.get("state", "").strip()
        sort = request.args.get("sort", "newest")

        query = {}

        # Search filter
        if search:
            query["$or"] = [
                {"basic_info.lab_name": {"$regex": search, "$options": "i"}},
                {"basic_info.owner_name": {"$regex": search, "$options": "i"}},
                {"basic_info.email": {"$regex": search, "$options": "i"}},
                {"basic_info.contact_number": {"$regex": search, "$options": "i"}},
                {"lab_code": {"$regex": search, "$options": "i"}}
            ]

        # Status filter
        if status:
            query["status"] = status

        # City filter
        if city:
            query["address.city"] = {
                "$regex": f"^{re.escape(city)}$",
                "$options": "i"
            }

        # State filter
        if state:
            query["address.state"] = {
                "$regex": f"^{re.escape(state)}$",
                "$options": "i"
            }

        # Sorting
        sort_order = -1 if sort == "newest" else 1

        total = db.labs.count_documents(query)

        labs = list(
            db.labs.find(query)
            .sort("created_at", sort_order)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        result = []

        for lab in labs:
            result.append({
                "lab_id": str(lab["_id"]),
                "lab_code": lab.get("lab_code"),

                "basic_info": lab.get("basic_info", {}),

                "address": lab.get("address", {}),

                "certifications": lab.get("certifications", {}),

                "services": lab.get("services", {}),

                "working_hours": lab.get("working_hours", []),

                "status": lab.get("status"),

                "verification": lab.get("verification", {}),

                "created_at": lab.get("created_at"),
                "updated_at": lab.get("updated_at")
            })

        return jsonify({
            "success": True,
            "message": "Labs fetched successfully",

            "pagination": {
                "total_records": total,
                "current_page": page,
                "per_page": limit,
                "total_pages": (total + limit - 1) // limit,
                "has_next": page * limit < total,
                "has_previous": page > 1
            },

            "filters": {
                "search": search,
                "status": status,
                "city": city,
                "state": state
            },

            "data": result

        }), 200

    except Exception:
        current_app.logger.exception("Get labs list error")
        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500




from flask import request, jsonify, current_app
from bson import ObjectId
from datetime import datetime
import re

@lab_test.route("/api/lab-tests/create", methods=["POST"])
def create_lab_test():
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "success": False,
                "message": "Valid JSON object required"
            }), 400

        lab_id = str(data.get("lab_id", "")).strip()
        test_name = str(data.get("test_name", "")).strip()
        description = str(data.get("description", "")).strip()
        price = data.get("price")

        # Required validation
        missing = []

        if not lab_id:
            missing.append("lab_id")

        if not test_name:
            missing.append("test_name")

        if not description:
            missing.append("description")

        if price is None:
            missing.append("price")

        if missing:
            return jsonify({
                "success": False,
                "message": "Required fields missing",
                "missing_fields": missing
            }), 400

        # Validate lab ID
        if not ObjectId.is_valid(lab_id):
            return jsonify({
                "success": False,
                "message": "Invalid lab ID"
            }), 400

        # Validate price
        if isinstance(price, bool):
            return jsonify({
                "success": False,
                "message": "Invalid test price"
            }), 400

        try:
            price = float(price)
        except (ValueError, TypeError):
            return jsonify({
                "success": False,
                "message": "Price must be numeric"
            }), 400

        if price < 0:
            return jsonify({
                "success": False,
                "message": "Price cannot be negative"
            }), 400

        # Check lab exists
        lab = db.labs.find_one({
            "_id": ObjectId(lab_id)
        })

        if not lab:
            return jsonify({
                "success": False,
                "message": "Lab not found"
            }), 404

        if lab.get("status") != "active":
            return jsonify({
                "success": False,
                "message": "Lab is not active"
            }), 400

        # Check duplicate test in same lab
        existing = db.lab_tests.find_one({
            "lab_id": ObjectId(lab_id),
            "test_name": {
                "$regex": "^" + re.escape(test_name) + "$",
                "$options": "i"
            }
        })

        if existing:
            return jsonify({
                "success": False,
                "message": "This test already exists for this lab"
            }), 409

        now = datetime.utcnow()

        test = {
            "lab_id": ObjectId(lab_id),

            "test_name": test_name,
            "test_code": data.get("test_code"),
            "category": data.get("category", "General"),

            "price": round(price, 2),

            "description": description,

            "sample_type": data.get("sample_type"),

            "fasting_required": data.get(
                "fasting_required", False
            ),

            "report_time": data.get("report_time"),

            "preparation_instructions": data.get(
                "preparation_instructions"
            ),

            "is_active": data.get("is_active", True),

            "created_at": now,
            "updated_at": now
        }

        result = db.lab_tests.insert_one(test)

        return jsonify({
            "success": True,
            "message": "Lab test created successfully",
            "data": {
                "test_id": str(result.inserted_id),
                "lab_id": lab_id,
                "test_name": test_name,
                "price": round(price, 2),
                "is_active": test["is_active"]
            }
        }), 201

    except Exception:
        current_app.logger.exception("Create lab test error")

        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500



@lab_test.route("/api/lab-tests/list", methods=["GET"])
def get_lab_tests_list():
    try:
        lab_id = request.args.get("lab_id", "").strip()

        page = max(request.args.get("page", 1, type=int), 1)
        limit = min(
            max(request.args.get("limit", 20, type=int), 1),
            100
        )

        search = request.args.get("search", "").strip()
        category = request.args.get("category", "").strip()
        is_active = request.args.get("is_active")
        sort = request.args.get("sort", "newest")

        # Lab ID required
        if not lab_id:
            return jsonify({
                "success": False,
                "message": "lab_id is required"
            }), 400

        if not ObjectId.is_valid(lab_id):
            return jsonify({
                "success": False,
                "message": "Invalid lab ID"
            }), 400

        query = {
            "lab_id": ObjectId(lab_id)
        }

        # Search test name / code / description
        if search:
            query["$or"] = [
                {
                    "test_name": {
                        "$regex": re.escape(search),
                        "$options": "i"
                    }
                },
                {
                    "test_code": {
                        "$regex": re.escape(search),
                        "$options": "i"
                    }
                },
                {
                    "description": {
                        "$regex": re.escape(search),
                        "$options": "i"
                    }
                }
            ]

        # Category filter
        if category:
            query["category"] = {
                "$regex": "^" + re.escape(category) + "$",
                "$options": "i"
            }

        # Active / Inactive filter
        if is_active is not None:
            if is_active.lower() not in ["true", "false"]:
                return jsonify({
                    "success": False,
                    "message": "is_active must be true or false"
                }), 400

            query["is_active"] = is_active.lower() == "true"

        # Sorting
        sort_options = {
            "newest": ("created_at", -1),
            "oldest": ("created_at", 1),
            "price_low": ("price", 1),
            "price_high": ("price", -1),
            "name_asc": ("test_name", 1),
            "name_desc": ("test_name", -1)
        }

        if sort not in sort_options:
            return jsonify({
                "success": False,
                "message": "Invalid sort parameter"
            }), 400

        sort_field, sort_order = sort_options[sort]

        # Total count
        total = db.lab_tests.count_documents(query)

        # Fetch records
        tests = list(
            db.lab_tests.find(query)
            .sort(sort_field, sort_order)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        result = []

        for test in tests:
            result.append({
                "test_id": str(test["_id"]),
                "lab_id": str(test["lab_id"]),
                "test_name": test.get("test_name"),
                "test_code": test.get("test_code"),
                "category": test.get("category"),
                "price": test.get("price", 0),
                "description": test.get("description"),
                "sample_type": test.get("sample_type"),
                "fasting_required": test.get(
                    "fasting_required", False
                ),
                "report_time": test.get("report_time"),
                "preparation_instructions": test.get(
                    "preparation_instructions"
                ),
                "is_active": test.get("is_active", True),
                "created_at": (
                    test["created_at"].isoformat()
                    if test.get("created_at") else None
                ),
                "updated_at": (
                    test["updated_at"].isoformat()
                    if test.get("updated_at") else None
                )
            })

        return jsonify({
            "success": True,
            "message": "Lab tests fetched successfully",

            "pagination": {
                "total_records": total,
                "current_page": page,
                "per_page": limit,
                "total_pages": (total + limit - 1) // limit,
                "has_next": page * limit < total,
                "has_previous": page > 1
            },

            "data": result

        }), 200

    except Exception:
        current_app.logger.exception("Get lab tests error")

        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500





@lab_test.route("/api/lab-orders/create", methods=["POST"])
def create_lab_order():
    try:
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "success": False,
                "message": "Valid JSON required"
            }), 400

        required_fields = [
            "lab_id",
            "patient_name",
            "patient_phone",
            "address",
            "collection_type",
            "slot_date",
            "tests"
        ]

        missing = [
            field for field in required_fields
            if data.get(field) is None or data.get(field) == ""
        ]

        if missing:
            return jsonify({
                "success": False,
                "message": "Required fields missing",
                "missing_fields": missing
            }), 400

        lab_id = str(data["lab_id"]).strip()

        if not ObjectId.is_valid(lab_id):
            return jsonify({
                "success": False,
                "message": "Invalid lab ID"
            }), 400

        patient_name = str(data["patient_name"]).strip()
        patient_phone = str(data["patient_phone"]).strip()
        collection_type = data["collection_type"]
        address = data["address"]
        tests_data = data["tests"]

        if not patient_name:
            return jsonify({
                "success": False,
                "message": "Patient name is required"
            }), 400

        if not re.fullmatch(r"[6-9]\d{9}", patient_phone):
            return jsonify({
                "success": False,
                "message": "Invalid patient phone number"
            }), 400

        if collection_type not in ["home", "lab"]:
            return jsonify({
                "success": False,
                "message": "collection_type must be home or lab"
            }), 400

        if not isinstance(address, dict):
            return jsonify({
                "success": False,
                "message": "Valid address object required"
            }), 400

        if not isinstance(tests_data, list) or not tests_data:
            return jsonify({
                "success": False,
                "message": "At least one test is required"
            }), 400

        if len(tests_data) > 100:
            return jsonify({
                "success": False,
                "message": "Maximum 100 tests allowed"
            }), 400

        # db = mongo.db

        # Verify active lab
        lab = db.labs.find_one({
            "_id": ObjectId(lab_id),
            "status": "active"
        })

        if not lab:
            return jsonify({
                "success": False,
                "message": "Lab not found or inactive"
            }), 404

        now = datetime.utcnow()

        order_tests = []
        total_amount = 0
        seen_tests = set()

        # Fetch actual test prices from database
        for item in tests_data:

            if not isinstance(item, dict):
                return jsonify({
                    "success": False,
                    "message": "Invalid test data"
                }), 400

            test_id = str(item.get("id", "")).strip()

            if not ObjectId.is_valid(test_id):
                return jsonify({
                    "success": False,
                    "message": "Invalid test ID",
                    "test_id": test_id
                }), 400

            if test_id in seen_tests:
                return jsonify({
                    "success": False,
                    "message": "Duplicate test not allowed",
                    "test_id": test_id
                }), 400

            seen_tests.add(test_id)

            test = db.lab_tests.find_one({
                "_id": ObjectId(test_id),
                "lab_id": ObjectId(lab_id),
                "is_active": True
            })

            if not test:
                return jsonify({
                    "success": False,
                    "message": "Test not found or inactive",
                    "test_id": test_id
                }), 404

            price = float(test.get("price", 0))

            if price < 0:
                return jsonify({
                    "success": False,
                    "message": "Invalid test price"
                }), 400

            order_tests.append({
                "test_id": ObjectId(test_id),
                "test_name": test.get("test_name"),
                "test_code": test.get("test_code"),
                "category": test.get("category"),
                "price": price,
                "sample_type": test.get("sample_type"),
                "report_time": test.get("report_time")
            })

            total_amount += price

        total_amount = round(total_amount, 2)

        # Generate unique order number
        counter = db.counters.find_one_and_update(
            {"_id": "lab_order"},
            {"$inc": {"sequence": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        order_number = f"LABORD{counter['sequence']:06d}"

        order = {
            "order_number": order_number,

            "lab_id": ObjectId(lab_id),
            "lab_name": lab.get("basic_info", {}).get("lab_name"),

            "patient_name": patient_name,
            "patient_phone": patient_phone,

            "address": address,
            "collection_type": collection_type,

            "slot_date": data["slot_date"],

            "tests": order_tests,

            "total_tests": len(order_tests),
            "total_amount": total_amount,

            "payment_status": "pending",
            "payment_method": None,
            "transaction_id": None,

            "order_status": "pending",

            "created_at": now,
            "updated_at": now
        }

        result = db.lab_orders.insert_one(order)

        return jsonify({
            "success": True,
            "message": "Lab booking created successfully",
            "data": {
                "order_id": str(result.inserted_id),
                "order_number": order_number,
                "lab_id": lab_id,
                "lab_name": order["lab_name"],
                "patient_name": patient_name,
                "patient_phone": patient_phone,
                "collection_type": collection_type,
                "slot_date": data["slot_date"],
                "total_tests": len(order_tests),
                "total_amount": total_amount,
                "payment_status": "pending",
                "order_status": "pending",
                "tests": [
                    {
                        "test_id": str(t["test_id"]),
                        "test_name": t["test_name"],
                        "price": t["price"]
                    }
                    for t in order_tests
                ]
            }
        }), 201

    except Exception:
        current_app.logger.exception("Create lab booking error")

        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500




@lab_test.route("/api/lab-orders/list", methods=["GET"])
def get_lab_orders_list():
    try:
        page = max(request.args.get("page", 1, type=int), 1)
        limit = min(max(request.args.get("limit", 20, type=int), 1), 100)

        lab_id = request.args.get("lab_id", "").strip()
        patient_phone = request.args.get("patient_phone", "").strip()
        order_status = request.args.get("order_status", "").strip()
        payment_status = request.args.get("payment_status", "").strip()
        collection_type = request.args.get("collection_type", "").strip()
        search = request.args.get("search", "").strip()
        from_date = request.args.get("from_date", "").strip()
        to_date = request.args.get("to_date", "").strip()

        query = {}

        # Lab filter
        if lab_id:
            if not ObjectId.is_valid(lab_id):
                return jsonify({
                    "success": False,
                    "message": "Invalid lab ID"
                }), 400

            query["lab_id"] = ObjectId(lab_id)

        # Patient phone filter
        if patient_phone:
            query["patient_phone"] = patient_phone

        # Order status
        if order_status:
            allowed_status = [
                "pending",
                "confirmed",
                "sample_collected",
                "processing",
                "completed",
                "cancelled"
            ]

            if order_status not in allowed_status:
                return jsonify({
                    "success": False,
                    "message": "Invalid order status"
                }), 400

            query["order_status"] = order_status

        # Payment status
        if payment_status:
            allowed_payment = [
                "pending",
                "paid",
                "failed",
                "refunded"
            ]

            if payment_status not in allowed_payment:
                return jsonify({
                    "success": False,
                    "message": "Invalid payment status"
                }), 400

            query["payment_status"] = payment_status

        # Collection type
        if collection_type:
            if collection_type not in ["home", "lab"]:
                return jsonify({
                    "success": False,
                    "message": "Invalid collection type"
                }), 400

            query["collection_type"] = collection_type

        # Search
        if search:
            query["$or"] = [
                {
                    "order_number": {
                        "$regex": re.escape(search),
                        "$options": "i"
                    }
                },
                {
                    "patient_name": {
                        "$regex": re.escape(search),
                        "$options": "i"
                    }
                },
                {
                    "patient_phone": {
                        "$regex": re.escape(search),
                        "$options": "i"
                    }
                }
            ]

        # Date filter
        date_filter = {}

        if from_date:
            try:
                start = datetime.strptime(
                    from_date, "%Y-%m-%d"
                )
                date_filter["$gte"] = start
            except ValueError:
                return jsonify({
                    "success": False,
                    "message": "Invalid from_date format. Use YYYY-MM-DD"
                }), 400

        if to_date:
            try:
                end = datetime.strptime(
                    to_date, "%Y-%m-%d"
                )
                from datetime import timedelta
                date_filter["$lt"] = end + timedelta(days=1)
            except ValueError:
                return jsonify({
                    "success": False,
                    "message": "Invalid to_date format. Use YYYY-MM-DD"
                }), 400

        if from_date and to_date and start > end:
            return jsonify({
                "success": False,
                "message": "from_date cannot be after to_date"
            }), 400

        if date_filter:
            query["created_at"] = date_filter

        # Total count
        total = db.lab_orders.count_documents(query)

        # Fetch orders
        orders = list(
            db.lab_orders.find(query)
            .sort("created_at", -1)
            .skip((page - 1) * limit)
            .limit(limit)
        )

        result = []

        for order in orders:

            result.append({
                "order_id": str(order["_id"]),
                "order_number": order.get("order_number"),

                "lab_id": str(order["lab_id"]),
                "lab_name": order.get("lab_name"),

                "patient_name": order.get("patient_name"),
                "patient_phone": order.get("patient_phone"),

                "address": order.get("address"),
                "collection_type": order.get("collection_type"),

                "slot_date": order.get("slot_date"),

                "tests": [
                    {
                        "test_id": str(test["test_id"]),
                        "test_name": test.get("test_name"),
                        "test_code": test.get("test_code"),
                        "price": test.get("price"),
                        "sample_type": test.get("sample_type"),
                        "report_time": test.get("report_time")
                    }
                    for test in order.get("tests", [])
                ],

                "total_tests": order.get("total_tests", 0),
                "total_amount": order.get("total_amount", 0),

                "payment_status": order.get("payment_status"),
                "payment_method": order.get("payment_method"),
                "transaction_id": order.get("transaction_id"),

                "order_status": order.get("order_status"),

                "created_at": (
                    order["created_at"].isoformat()
                    if order.get("created_at") else None
                ),

                "updated_at": (
                    order["updated_at"].isoformat()
                    if order.get("updated_at") else None
                )
            })

        return jsonify({
            "success": True,
            "message": "Lab orders fetched successfully",

            "pagination": {
                "total_records": total,
                "current_page": page,
                "per_page": limit,
                "total_pages": (total + limit - 1) // limit,
                "has_next": page * limit < total,
                "has_previous": page > 1
            },

            "data": result

        }), 200

    except Exception:
        current_app.logger.exception("Get lab orders error")

        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500

