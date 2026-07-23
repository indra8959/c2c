# staff_routes.py
from flask import Blueprint, request, jsonify
from api_files.utils import new_hqz_transport_db as db
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
