# staff_routes.py
from flask import Blueprint, request, jsonify
from api_files.utils import duniyape_db as db
from bson import ObjectId
from datetime import datetime
from zoneinfo import ZoneInfo

staff_bp = Blueprint("staff", __name__)

# ✅ Create / Edit Designation (single API)
@staff_bp.route("/designations", methods=["POST"])
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
@staff_bp.route("/designations", methods=["GET"])
def get_designations():
    designations = list(db.designations.find({}))
    for d in designations:
        d["_id"] = str(d["_id"])
    return jsonify(designations), 200


# ✅ Create or Edit Staff (single API)
@staff_bp.route("/create", methods=["POST"])
def create_or_edit_staff():
    data = request.json
    staff_id = data.get("_id")  # if provided → edit
 
    if staff_id:  # ✅ Edit existing staff
        data.pop("_id", None)
        result = db.staff.update_one(
            {"_id": ObjectId(staff_id)},
            {"$set": data}
        )
        if result.matched_count == 0:
            return jsonify({"error": "Staff not found"}), 404

        data["_id"] = staff_id
        data["designation_id"] = str(data["designation_id"])
        return jsonify({"message": "Staff updated successfully", "data": data}), 200

    else:  # ✅ Create new staff
        data['designation']=ObjectId(data['designation'])
        data["created_at"] = datetime.utcnow()
        result = db.staff.insert_one(data)
        data["_id"] = str(result.inserted_id)
        data["designation"] = str(data["designation"])
        return jsonify({"message": "Staff created successfully", "data": data}), 201


# ✅ Get Staff List
@staff_bp.route("", methods=["GET"])
def list_staff():
    try:
        pipeline = [
            {
                "$lookup": {
                    "from": "designations",          # target collection
                    "localField": "designation",     # field in staff
                    "foreignField": "_id",           # field in designations
                    "as": "designation_info"
                }
            },
            {"$unwind": {"path": "$designation_info", "preserveNullAndEmptyArrays": True}},
            {
                "$addFields": {
                    "designation_name": {
                        "$ifNull": ["$designation_info.name", "-"]
                    },
                    "designation": {
                        "$ifNull": ["$designation_info._id", "-"]
                    }
                }
            },
            {
                "$project": {
                    "designation_info": 0   # hide extra lookup data
                }
            }
        ]

        staff_list = list(db.staff.aggregate(pipeline))

        # Convert ObjectId to string for all _id fields
        for staff in staff_list:
            staff["_id"] = str(staff["_id"])
            staff["designation"] = str(staff["designation"])

        return jsonify(staff_list), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@staff_bp.route('/api/get-attendance-req', methods=['GET'])
def get_attendance_req():

    try:
        result = list(
            db.attendance.find(
                {'status': {'$in': ['RL', 'RO']}}
            ).sort("date", -1)
        )

        # Convert ObjectId to string
        for doc in result:
            doc['_id'] = str(doc['_id'])

        return jsonify({
            "status": "success",
            "count": len(result),
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    
@staff_bp.route('/api/get-attendance/<string:num>', methods=['GET'])
def get_attendance(num):

    try:
        result = list(
            db.attendance.find(
                {
                    'status': {'$in': ['L', 'O', 'P']},
                    'phone': num
                }
            ).sort("date", -1)
        )

        for doc in result:

            # Convert ObjectId
            doc['_id'] = str(doc['_id'])

            # Handle datetime safely
            if isinstance(doc.get('date'), datetime):
                dt = doc['date']
            else:
                dt = datetime.fromisoformat(doc['date'])

            # Extract values
            doc['month'] = dt.month - 1   # JS month indexing ke liye
            doc['year'] = dt.year
            doc['day'] = dt.day

        return jsonify({
            "status": "success",
            "count": len(result),
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    

@staff_bp.route('/api/update-attendance-status', methods=['POST'])
def update_attendance_status():
    try:
        data = request.get_json()

        attendance_id = data.get("attendance_id")
        new_status = data.get("status")

        if not attendance_id or not new_status:
            return jsonify({
                "status": "error",
                "message": "attendance_id and status are required"
            }), 400

        result = db.attendance.update_one(
            {"_id": ObjectId(attendance_id)},
            {
                "$set": {
                    "status": new_status,
                    "updated_at": datetime.now(ZoneInfo("Asia/Kolkata"))
                }
            }
        )

        if result.matched_count == 0:
            return jsonify({
                "status": "error",
                "message": "Attendance record not found"
            }), 404

        return jsonify({
            "status": "success",
            "message": "Attendance status updated successfully"
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500



@staff_bp.route('/api/attendance-summary', methods=['GET'])
def attendance_summary():
    try:
        start_date = request.args.get('start')
        end_date = request.args.get('end')

        if not start_date or not end_date:
            return jsonify({
                "status": "error",
                "message": "start and end date required"
            }), 400

        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)

        pipeline = [
            {
                "$lookup": {
                    "from": "attendance",
                    "let": { "staff_phone": { "$toString": "$phone" } },
                    "pipeline": [
                        {
                            "$addFields": {
                                "normalized_phone": {
                                    "$let": {
                                        "vars": {
                                            "p": { "$toString": "$phone" }
                                        },
                                        "in": {
                                            "$cond": [
                                                {
                                                    "$regexMatch": {
                                                        "input": "$$p",
                                                        "regex": "^(\\+91|91)"
                                                    }
                                                },
                                                {
                                                    "$substrBytes": [
                                                        "$$p",
                                                        {
                                                            "$cond": [
                                                                {
                                                                    "$regexMatch": {
                                                                        "input": "$$p",
                                                                        "regex": "^\\+91"
                                                                    }
                                                                },
                                                                3,
                                                                2
                                                            ]
                                                        },
                                                        10
                                                    ]
                                                },
                                                "$$p"
                                            ]
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {
                                            "$eq": [
                                                { "$toString": "$normalized_phone" },
                                                { "$toString": "$$staff_phone" }
                                            ]
                                        },
                                        { "$gte": ["$date", start_dt] },
                                        { "$lte": ["$date", end_dt] }
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "attendance_data"
                }
            },
        #          {
        #     "$lookup": {
        #         "from": "attendance",
        #         "localField": "phone",
        #         "foreignField": "phone",
        #         "pipeline": [
        #             {
        #                 "$match": {
        #                     "date": {
        #                         "$gte": start_dt,
        #                         "$lte": end_dt
        #                     }
        #                 }
        #             }
        #         ],
        #         "as": "attendance_data"
        #     }
        # },

            # ✅ Only keep counts
            {
                "$addFields": {
                    "present": {
                        "$size": {
                            "$filter": {
                                "input": "$attendance_data",
                                "as": "att",
                                "cond": { "$eq": ["$$att.status", "P"] }
                            }
                        }
                    },
                    "leave": {
                        "$size": {
                            "$filter": {
                                "input": "$attendance_data",
                                "as": "att",
                                "cond": { "$eq": ["$$att.status", "L"] }
                            }
                        }
                    },
                    "other": {
                        "$size": {
                            "$filter": {
                                "input": "$attendance_data",
                                "as": "att",
                                "cond": { "$eq": ["$$att.status", "O"] }
                            }
                        }
                    }
                }
            },

            # ✅ Clean output
            {
                "$project": {
                    "_id": 0,
                    "phone": { "$toString": "$phone" },
                    "name": 1,
                    "salary": {
                        "$ifNull": ["$salary", 0]
                    },
                    "role": 1,
                    "present": 1,
                    "leave": 1,
                    "other": 1
                }
            }
        ]

        result = list(db.staff.aggregate(pipeline))
        # return jsonify(result)

        # 🔥 =========================
        # ✅ Python-side calculations
        # 🔥 =========================

        # 1. Total calendar days
        total_days = (end_dt - start_dt).days + 1

        # 2. Calculate weekends
        weekends = 0
        current = start_dt
        while current <= end_dt:
            if current.weekday() in [6]:  # Sat, Sun
                weekends += 1
            current += timedelta(days=1)

        # 3. Holidays from DB
        holiday_count = db.holidays.count_documents({
            "date": {"$gte": start_dt, "$lte": end_dt}
        })

        # 4. Working days
        working_days = total_days - weekends - holiday_count

        # 5. Update each staff
        for staff in result:
            present = staff.get("present", 0)
            leave = staff.get("leave", 0)
            monthly_salary = staff.get("salary", 0)

            staff["total_days"] = total_days
            staff["working_days"] = working_days

            # Absent calculation
            staff["absent"] = working_days - (present + leave)

            # Safety check
            if staff["absent"] < 0:
                staff["absent"] = 0

            # ✅ Per day salary (choose one method)

            # Method 1: Based on total days (recommended for MNC style)
            per_day_salary = monthly_salary / total_days if total_days else 0

            # Method 2 (optional): Based on working days
            # per_day_salary = monthly_salary / working_days if working_days else 0

            # ✅ Payable days
            payable_days = present + leave

            # Make sure payable days do not exceed working days
            if payable_days > working_days:
                payable_days = working_days

            # ✅ Net payable salary
            staff["net_payable_salary"] = round(per_day_salary * payable_days, 2)

        return jsonify({
            "status": "success",
            "count": len(result),
            "data": result
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
