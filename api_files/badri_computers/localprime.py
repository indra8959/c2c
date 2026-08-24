from flask import Blueprint, request, jsonify,json
from bson import ObjectId
from werkzeug.exceptions import BadRequest
from api_files.badri_computers.trade import db
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from decimal import Decimal
from werkzeug.utils import secure_filename
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from math import pow
import uuid




AWS_ACCESS_KEY = "AKIAZVK5JOP7HUCRINR2"
AWS_SECRET_KEY = "0TPWkUv0vumNgnsfDlcsGOP4jmadNUHt9nGg2Of9"
AWS_REGION = "eu-north-1"  # e.g. ap-south-1 for Mumbai
S3_BUCKET = "c2c-files-bucket"

# Initialize boto3 client
s3 = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=AWS_REGION
)

members = db["members"]
counters = db["counters"]
localprime_bp = Blueprint("localprime", __name__)



def upload_file_to_s3(file_obj, folder="localprime"):
    if not file_obj or file_obj.filename == "":
        return None

    filename = secure_filename(file_obj.filename)
    s3_file_name = f"{folder}/{filename}"

    s3.upload_fileobj(
        Fileobj=file_obj,
        Bucket=S3_BUCKET,
        Key=s3_file_name,
        ExtraArgs={'ContentType': file_obj.content_type}
    )

    return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_file_name}"

def convert_objectids(obj):
    if isinstance(obj, ObjectId):
        return str(obj)

    if isinstance(obj, list):
        return [convert_objectids(item) for item in obj]

    if isinstance(obj, dict):
        return {key: convert_objectids(value) for key, value in obj.items()}

    return obj


def upload_member_files():
    items = [ "UploadId",
            "UploadAddress",
            "UploadId2",
            "UploadAddress2",
            "UploadPhoto",]
       
    uploaded = {}

    for field_name in items:
        file_obj = request.files.get(field_name)
        if file_obj and file_obj.filename:
            uploaded[field_name] = upload_file_to_s3(file_obj,"localprime/members")

    return uploaded

def get_next_sequence(name):
    counter = counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True
    )
    if "seq" not in counter:
        counters.update_one({"_id": name}, {"$setOnInsert": {"seq": 1}}, upsert=True)
        counter = counters.find_one({"_id": name})
    return counter["seq"]


@localprime_bp.route("/create-member-request", methods=["POST"])
def create_member_request():
    data = request.form.to_dict() if request.form else (
        request.get_json(silent=True) or {}
    )

    if not data:
        raise BadRequest("Data is required")

    introducer_id = data.get("introducer_id")
    introducer_doc = None

    if introducer_id:
        introducer_doc = members.find_one({"_id": ObjectId(introducer_id)})
        if not introducer_doc:
            return jsonify({
                "success": False,
                "message": "Introducer member not found"
            }), 404

    try:
        uploaded_files = upload_member_files()
    except FileNotFoundError:
        return jsonify({"success": False, "message": "File not found"}), 404
    except NoCredentialsError:
        return jsonify({"success": False, "message": "AWS credentials not available"}), 403
    except ClientError as e:
        return jsonify({"success": False, "message": str(e)}), 500

    now = datetime.utcnow()

    payload = {
        **data,
        **uploaded_files,
        "status": "pending",
        "memberId": None,
        "introducer_id": ObjectId(introducer_id) if introducer_id else None,
        "introducer_memberId": introducer_doc.get("memberId") if introducer_doc else None,
        "approved_by": None,
        "approved_at": None,
        "rejected_reason": None,
        "created_at": now,
        "updated_at": now,
    }

    payload = {k: v for k, v in payload.items() if v is not None}

    result = members.insert_one(payload)

    payload["_id"] = str(result.inserted_id)

    return jsonify({
        "success": True,
        "message": "Membership request submitted successfully",
        "data": convert_objectids(payload)
    }), 201

@localprime_bp.route("/update-member-request/<request_id>", methods=["POST"])
def update_member_request(request_id):
    data = request.get_json(silent=True) or {}

    status = data.get("status")  # approved / rejected

    if status not in ["approved", "rejected"]:
        return jsonify({
            "success": False,
            "message": "Status must be 'approved' or 'rejected'"
        }), 400

    member = members.find_one({"_id": ObjectId(request_id)})

    if not member:
        return jsonify({
            "success": False,
            "message": "Member request not found"
        }), 404

    # Prevent updating already processed requests
    if member.get("status") != "pending":
        return jsonify({
            "success": False,
            "message": f"Request already {member.get('status')}"
        }), 400

    update_data = {
        "status": status,
        "updated_at": datetime.utcnow(),
        # "updated_by": ObjectId(current_user.id)  # If authentication exists
    }

    if status == "approved":
        member_seq = get_next_sequence("memberId")
        member_id = f"001{member_seq:04d}"

        update_data.update({
            "memberId": member_id,
            "approved_at": datetime.utcnow(),
        })

    elif status == "rejected":
        update_data.update({
            "rejected_reason": data.get("rejected_reason", ""),
            "rejected_at": datetime.utcnow(),
        })

    members.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": update_data}
    )

    member.update(update_data)

    return jsonify({
        "success": True,
        "message": f"Request {status} successfully",
        "data": convert_objectids(member)
    }), 200

@localprime_bp.route("/member-requests", methods=["GET"])
def get_member_requests():
    status = request.args.get("status")  # pending, approved, rejected

    query = {}

    if status:
        if status not in ["pending", "approved", "rejected"]:
            return jsonify({
                "success": False,
                "message": "Invalid status"
            }), 400
        query["status"] = status

    member_requests = list(
        members.find(query).sort("created_at", -1)
    )

    return jsonify({
        "success": True,
        "count": len(member_requests),
        "data": convert_objectids(member_requests)
    }), 200

@localprime_bp.route("/members/<string:member_id>", methods=["POST"])
def edit_member(member_id):
    try:
        oid = ObjectId(member_id)
    except Exception:
        raise BadRequest("Invalid member_id")

    existing = members.find_one({"_id": oid})
    if not existing:
        return jsonify({"success": False, "message": "Member not found"}), 404

    update_data = request.form.to_dict()

    # update_data = {}
    # allowed_fields = ["name", "phone", "email", "role", "address", "city", "state", "pincode", "introducer_id"]

    # for field in allowed_fields:
    #     if field in data:
    #         update_data[field] = data[field]

    if "introducer_id" in update_data:
        try:
            intro_oid = ObjectId(update_data["introducer_id"])
            introducer_doc = members.find_one({"_id": intro_oid})
            if not introducer_doc:
                return jsonify({"success": False, "message": "Introducer member not found"}), 404
            update_data["introducer_id"] = intro_oid
            update_data["introducer_memberId"] = introducer_doc.get("memberId")
        except Exception:
            return jsonify({"success": False, "message": "Invalid introducer_id"}), 400

    try:
        uploaded_files = upload_member_files()
        update_data.update(uploaded_files)
    except FileNotFoundError:
        return jsonify({"success": False, "message": "File not found"}), 404
    except NoCredentialsError:
        return jsonify({"success": False, "message": "AWS credentials not available"}), 403
    except ClientError as e:
        return jsonify({"success": False, "message": str(e)}), 500

    if not update_data:
        raise BadRequest("No valid fields to update")

    update_data["updated_at"] = datetime.utcnow()

    result = members.update_one({"_id": oid}, {"$set": update_data})

    if result.matched_count == 0:
        return jsonify({"success": False, "message": "Member not found"}), 404

    member = members.find_one({"_id": oid})
    return jsonify({
        "success": True,
        "message": "Member updated",
        "data": convert_objectids(member)
    }), 200

@localprime_bp.route("/get-members", methods=["GET"])
def get_all_members():
    docs = members.find().sort("created_at", -1)
    data = [convert_objectids(doc) for doc in docs]
    return jsonify({
        "success": True,
        "count": len(data),
        "data": data
    }), 200

@localprime_bp.route("/members", methods=["GET"])
def get_single_member():
    member_id = request.args.get("memberId")
    mongo_id = request.args.get("_id") or request.args.get("id")

    if not member_id and not mongo_id:
        return jsonify({
            "success": False,
            "message": "Provide memberId or _id as query parameter"
        }), 400

    doc = None

    if member_id:
        doc = members.find_one({"memberId": member_id})

    if not doc and mongo_id:
        try:
            oid = ObjectId(mongo_id)
            doc = members.find_one({"_id": oid})
        except Exception:
            doc = None

    if not doc:
        return jsonify({
            "success": False,
            "message": "Member not found"
        }), 404

    return jsonify({
        "success": True,
        "data": convert_objectids(doc)
    }), 200

@localprime_bp.route("/branches", methods=["POST"])
def create_branch():
    data = request.get_json(silent=True) or {}

    now = datetime.utcnow()

    # Generate branch code (001, 002, 003...)
    branch_seq = get_next_sequence("branchCode")
    branch_code = f"{branch_seq:03d}"

    payload = {
        **data,
        "branch_code": branch_code,
        "created_at": now,
        "updated_at": now
    }

    result = db.branches.insert_one(payload)
    payload["_id"] = str(result.inserted_id)

    return jsonify({
        "success": True,
        "message": "Branch created successfully",
        "data": convert_objectids(payload)
    }), 201

@localprime_bp.route("/branches", methods=["GET"])
def get_branches():
    status = request.args.get("status")

    query = {}

    if status:
        query["status"] = status

    data = list(
        db.branches.find(query).sort("created_at", -1)
    )

    return jsonify({
        "success": True,
        "count": len(data),
        "data": convert_objectids(data)
    }), 200

@localprime_bp.route("/branches/<branch_id>", methods=["POST"])
def update_branch(branch_id):
    data = request.get_json(silent=True) or {}

    branch = db.branches.find_one({"_id": ObjectId(branch_id)})

    if not branch:
        return jsonify({
            "success": False,
            "message": "Branch not found"
        }), 404

    if "branch_code" in data:
        duplicate = db.branches.find_one({
            "branch_code": data["branch_code"],
            "_id": {"$ne": ObjectId(branch_id)}
        })

        if duplicate:
            return jsonify({
                "success": False,
                "message": "Branch code already exists"
            }), 400

    data["updated_at"] = datetime.utcnow()

    db.branches.update_one(
        {"_id": ObjectId(branch_id)},
        {"$set": data}
    )

    branch.update(data)

    return jsonify({
        "success": True,
        "message": "Branch updated successfully",
        "data": convert_objectids(branch)
    }), 200


@localprime_bp.route("/loan-products", methods=["POST"])
def create_loan_product():
    data = request.get_json(silent=True) or {}

    if not data.get("loanName"):
        return jsonify({
            "success": False,
            "message": "Product name is required"
        }), 400

    # Duplicate name check
    if db.loan_products.find_one({
        "loanName": {
            "$regex": f"^{data['loanName']}$",
            "$options": "i"
        }
    }):
        return jsonify({
            "success": False,
            "message": "Loan product already exists"
        }), 400

    now = datetime.utcnow()

    seq = get_next_sequence("loanCode")
    product_code = f"LP{seq:03d}"

    payload = {
        **data,
        "loanCode": product_code,
        "created_at": now,
        "updated_at": now
    }

    result = db.loan_products.insert_one(payload)
    payload["_id"] = str(result.inserted_id)

    return jsonify({
        "success": True,
        "message": "Loan product created successfully",
        "data": convert_objectids(payload)
    }), 201

@localprime_bp.route("/loan-products/<product_id>", methods=["POST"])
def update_loan_product(product_id):

    data = request.get_json(silent=True) or {}

    product = db.loan_products.find_one({
        "_id": ObjectId(product_id)
    })

    if not product:
        return jsonify({
            "success": False,
            "message": "Loan product not found"
        }), 404

    if "loanName" in data:
        duplicate = db.loan_products.find_one({
            "loanName": {
                "$regex": f"^{data['loanName']}$",
                "$options": "i"
            },
            "_id": {"$ne": ObjectId(product_id)}
        })

        if duplicate:
            return jsonify({
                "success": False,
                "message": "Loan already exists"
            }), 400



    data["updated_at"] = datetime.utcnow()

    db.loan_products.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": data}
    )

    product.update(data)

    return jsonify({
        "success": True,
        "message": "Loan product updated successfully",
        "data": convert_objectids(product)
    }), 200


@localprime_bp.route("/loan-products", methods=["GET"])
def get_loan_products():

    status = request.args.get("status")

    query = {}

    if status:
        query["status"] = status

    products = list(
        db.loan_products.find(query).sort("created_at", -1)
    )

    return jsonify({
        "success": True,
        "count": len(products),
        "data": convert_objectids(products)
    }), 200

@localprime_bp.route("/loan-parameters", methods=["POST"])
def create_loan_parameter():
    data = request.get_json(silent=True) or {}

    if not data.get("loan_id"):
        return jsonify({
            "success": False,
            "message": "Loan_id is required"
        }), 400

    # # Prevent duplicate loan types
    # if db.loan_parameters.find_one({"loan_id": data["loan_id"]}):
    #     return jsonify({
    #         "success": False,
    #         "message": "Loan_id already exists"
    #     }), 400

    now = datetime.utcnow()

    payload = {
        **data,
        "created_at": now,
        "updated_at": now
    }

    result = db.loan_parameters.insert_one(payload)
    payload["_id"] = str(result.inserted_id)

    return jsonify({
        "success": True,
        "message": "Loan parameter created successfully",
        "data": convert_objectids(payload)
    }), 201

@localprime_bp.route("/loan-parameters", methods=["GET"])
def get_loan_parameters():

    status = request.args.get("status")

    query = {}

    if status:
        query["status"] = status

    data = list(
        db.loan_parameters.find(query).sort("created_at", -1)
    )

    return jsonify({
        "success": True,
        "count": len(data),
        "data": convert_objectids(data)
    }), 200

@localprime_bp.route("/loan-parameters/<parameter_id>", methods=["POST"])
def update_loan_parameter(parameter_id):

    data = request.get_json(silent=True) or {}

    parameter = db.loan_parameters.find_one({
        "_id": ObjectId(parameter_id)
    })

    if not parameter:
        return jsonify({
            "success": False,
            "message": "Loan parameter not found"
        }), 404

    if "loan_id" in data:
        duplicate = db.loan_parameters.find_one({
            "loan_id": data["loan_id"],
            "_id": {"$ne": ObjectId(parameter_id)}
        })

        if duplicate:
            return jsonify({
                "success": False,
                "message": "Loan type already exists"
            }), 400

    data["updated_at"] = datetime.utcnow()

    db.loan_parameters.update_one(
        {"_id": ObjectId(parameter_id)},
        {"$set": data}
    )

    parameter.update(data)

    return jsonify({
        "success": True,
        "message": "Loan parameter updated successfully",
        "data": convert_objectids(parameter)
    }), 200

@localprime_bp.route("/designations", methods=["POST"])
def create_designation():
    data = request.get_json(silent=True) or {}

    designation_name = data.get("designationName")

    if not designation_name:
        return jsonify({
            "success": False,
            "message": "Designation name is required"
        }), 400

    # Duplicate check
    if db.agent_designations.find_one({
        "designationName": {
            "$regex": f"^{designation_name}$",
            "$options": "i"
        }
    }):
        return jsonify({
            "success": False,
            "message": "Designation already exists"
        }), 400

    seq = get_next_sequence("designationCode")
    designation_code = f"DES{seq:03d}"

    now = datetime.utcnow()

    payload = {
        "designationCode": designation_code,
        "designationName": designation_name,
        "level": data.get("level", ""),
        "status": data.get("status", "active"),
        "created_at": now,
        "updated_at": now
    }

    result = db.agent_designations.insert_one(payload)
    payload["_id"] = str(result.inserted_id)

    return jsonify({
        "success": True,
        "message": "Designation created successfully",
        "data": convert_objectids(payload)
    }), 201

@localprime_bp.route("/designations/<designation_id>", methods=["POST"])
def update_designation(designation_id):
    data = request.get_json(silent=True) or {}

    designation = db.agent_designations.find_one({
        "_id": ObjectId(designation_id)
    })

    if not designation:
        return jsonify({
            "success": False,
            "message": "Designation not found"
        }), 404

    if "designationName" in data:
        duplicate = db.agent_designations.find_one({
            "designationName": {
                "$regex": f"^{data['designationName']}$",
                "$options": "i"
            },
            "_id": {"$ne": ObjectId(designation_id)}
        })

        if duplicate:
            return jsonify({
                "success": False,
                "message": "Designation already exists"
            }), 400

    editable_fields = [
        "designationName",
        "level",
        "status"
    ]

    update_data = {}

    for field in editable_fields:
        if field in data:
            update_data[field] = data[field]

    update_data["updated_at"] = datetime.utcnow()

    db.agent_designations.update_one(
        {"_id": ObjectId(designation_id)},
        {"$set": update_data}
    )

    designation.update(update_data)

    return jsonify({
        "success": True,
        "message": "Designation updated successfully",
        "data": convert_objectids(designation)
    }), 200 

@localprime_bp.route("/designations", methods=["GET"])
def get_designations():

    query = {}

    status = request.args.get("status")

    if status:
        query["status"] = status

    data = list(
        db.agent_designations.find(query).sort("designationName", 1)
    )

    return jsonify({
        "success": True,
        "count": len(data),
        "data": convert_objectids(data)
    }), 200

@localprime_bp.route("/agent-requests", methods=["POST"])
def create_agent_request():
    data = request.get_json(silent=True) or {}

    required_fields = ["member_id", "branch_id", "designation_id","IntroCode"]

    for field in required_fields:
        if not data.get(field):
            return jsonify({
                "success": False,
                "message": f"{field} is required"
            }), 400

    member = members.find_one({
        "_id": ObjectId(data["member_id"])
    })

    if not member:
        return jsonify({
            "success": False,
            "message": "Member not found"
        }), 404

    if member.get("status") != "approved":
        return jsonify({
            "success": False,
            "message": "Only approved members can become agents"
        }), 400

    if member.get("isAgent", False):
        return jsonify({
            "success": False,
            "message": "Member is already an agent"
        }), 400

    existing_request = db.agent_requests.find_one({
        "member_id": member["_id"],
        "status": "pending"
    })

    if existing_request:
        return jsonify({
            "success": False,
            "message": "Pending request already exists"
        }), 400

    branch = db.branches.find_one({
        "_id": ObjectId(data["branch_id"])
    })

    if not branch:
        return jsonify({
            "success": False,
            "message": "Branch not found"
        }), 404

    designation = db.agent_designations.find_one({
        "_id": ObjectId(data["designation_id"])
    })

    if not designation:
        return jsonify({
            "success": False,
            "message": "Designation not found"
        }), 404

    now = datetime.utcnow()

    payload = {
        "member_id": member["_id"],
        "memberId": member["memberId"],
        "memberName": member.get("name"),
        "password": member.get("password"),
        "IntroCode": data.get("IntroCode"),
        "branch_id": branch["_id"],
        "branchCode": branch["branch_code"],
        "branchName": branch["branchName"],

        "designation_id": designation["_id"],
        "designationCode": designation["designationCode"],
        "designationName": designation["designationName"],

        "remarks": data.get("remarks"),

        "status": "pending",

        "approvedBy": None,
        "approvedAt": None,
        "rejectedReason": None,

        "created_at": now,
        "updated_at": now
    }

    result = db.agent_requests.insert_one(payload)
    payload["_id"] = str(result.inserted_id)

    return jsonify({
        "success": True,
        "message": "Agent request submitted successfully",
        "data": convert_objectids(payload)
    }), 201

@localprime_bp.route("/agent-requests", methods=["GET"])
def get_agent_requests():

    query = {}

    status = request.args.get("status")
    member_id = request.args.get("member_id")
    branch_id = request.args.get("branch_id")

    if status:
        query["status"] = status

    if member_id:
        query["member_id"] = ObjectId(member_id)

    if branch_id:
        query["branch_id"] = ObjectId(branch_id)

    data = list(
        db.agent_requests.find(query).sort("created_at", -1)
    )

    return jsonify({
        "success": True,
        "count": len(data),
        "data": convert_objectids(data)
    }), 200

@localprime_bp.route("/agent-requests/<request_id>", methods=["POST"])
def update_agent_request(request_id):

    data = request.get_json(silent=True) or {}

    status = data.get("status")

    if status not in ["approved", "rejected"]:
        return jsonify({
            "success": False,
            "message": "Status must be approved or rejected"
        }), 400

    request_doc = db.agent_requests.find_one({
        "_id": ObjectId(request_id)
    })

    if not request_doc:
        return jsonify({
            "success": False,
            "message": "Request not found"
        }), 404

    if request_doc["status"] != "pending":
        return jsonify({
            "success": False,
            "message": "Request already processed"
        }), 400

    update_request = {
        "status": status,
        "IntroCode": request_doc.get("IntroCode"),
        "updated_at": datetime.utcnow()
    }

    if status == "approved":

        seq = get_next_sequence("agentCode")
        agent_code = f"AG{seq:03d}"

        members.update_one(
            {
                "_id": request_doc["member_id"]
            },
            {
                "$set": {
                    "isAgent": True,
                    "agentCode": agent_code,

                    "branch_id": request_doc["branch_id"],
                    "branchCode": request_doc["branchCode"],
                    "branchName": request_doc["branchName"],
                    "IntroCode": request_doc.get("IntroCode"),
                    "password": request_doc.get("password"),

                    "designation_id": request_doc["designation_id"],
                    "designationCode": request_doc["designationCode"],
                    "designationName": request_doc["designationName"],

                    "agentStatus": "active",
                    "joiningDate": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        update_request["approvedAt"] = datetime.utcnow()
        update_request["approvedBy"] = data.get("approvedBy")

    else:
        update_request["rejectedReason"] = data.get(
            "rejectedReason", ""
        )

    db.agent_requests.update_one(
        {
            "_id": ObjectId(request_id)
        },
        {
            "$set": update_request
        }
    )

    request_doc.update(update_request)

    return jsonify({
        "success": True,
        "message": f"Request {status} successfully",
        "data": convert_objectids(request_doc)
    }), 200


@localprime_bp.route("/agent/change-password", methods=["POST"])
def change_agent_password():

    data = request.get_json(silent=True) or {}

    member_id = data.get("member_id")
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    # Validation
    if not member_id or not old_password or not new_password:
        return jsonify({
            "success": False,
            "message": "member_id, old_password and new_password are required"
        }), 400

    if len(new_password) < 6:
        return jsonify({
            "success": False,
            "message": "New password must be at least 6 characters"
        }), 400

    # Find agent
    try:
        member = members.find_one({
            "_id": ObjectId(member_id),
            "isAgent": True
        })
    except Exception:
        return jsonify({
            "success": False,
            "message": "Invalid member_id"
        }), 400

    if not member:
        return jsonify({
            "success": False,
            "message": "Agent not found"
        }), 404

    # Check agent status
    if member.get("agentStatus") != "active":
        return jsonify({
            "success": False,
            "message": "Agent is not active"
        }), 403

    # Check old password
    if member.get("password") != old_password:
        return jsonify({
            "success": False,
            "message": "Old password is incorrect"
        }), 401

    # Update password
    result = members.update_one(
        {
            "_id": member["_id"]
        },
        {
            "$set": {
                "password": new_password,
                "updated_at": datetime.utcnow()
            }
        }
    )

    if result.modified_count == 0:
        return jsonify({
            "success": False,
            "message": "Password was not changed"
        }), 400

    return jsonify({
        "success": True,
        "message": "Password changed successfully"
    }), 200

@localprime_bp.route("/agent/login", methods=["POST"])
def agent_login():

    data = request.get_json(silent=True) or {}

    agent_code = data.get("agentCode")
    password = data.get("password")

    # -----------------------------------------
    # Validation
    # -----------------------------------------
    if not agent_code:
        return jsonify({
            "success": False,
            "message": "agentCode is required"
        }), 400

    if not password:
        return jsonify({
            "success": False,
            "message": "password is required"
        }), 400

    # -----------------------------------------
    # Find Agent
    # -----------------------------------------
    agent = members.find_one({
        "agentCode": agent_code,
        "isAgent": True
    })

    if not agent:
        return jsonify({
            "success": False,
            "message": "Invalid agent ID or password"
        }), 401

    # -----------------------------------------
    # Check Agent Status
    # -----------------------------------------
    if agent.get("agentStatus") != "active":
        return jsonify({
            "success": False,
            "message": "Agent account is not active"
        }), 403

    # -----------------------------------------
    # Password Check - WITHOUT HASH
    # -----------------------------------------
    if agent.get("password") != password:
        return jsonify({
            "success": False,
            "message": "Invalid agent ID or password"
        }), 401

    # -----------------------------------------
    # Login Data
    # -----------------------------------------
    login_data = {
        "_id": agent.get("_id"),
        "memberId": agent.get("memberId"),

        "agentCode": agent.get("agentCode"),
        "isAgent": agent.get("isAgent"),
        "agentStatus": agent.get("agentStatus"),

        "name": agent.get("name"),
        "FirstName": agent.get("FirstName"),
        "LastName": agent.get("LastName"),

        "MobileNo": agent.get("MobileNo"),
        "Email": agent.get("Email"),

        "Gender": agent.get("Gender"),
        "DateOfBirth": agent.get("DateOfBirth"),
        "UploadPhoto": agent.get("UploadPhoto"),

        # Branch
        "branch_id": agent.get("branch_id"),
        "branchCode": agent.get("branchCode"),
        "branchName": agent.get("branchName"),

        # Designation
        "designation_id": agent.get("designation_id"),
        "designationCode": agent.get("designationCode"),
        "designationName": agent.get("designationName"),

        "joiningDate": agent.get("joiningDate")
    }

    return jsonify({
        "success": True,
        "message": "Login successful",
        "data": convert_objectids(login_data)
    }), 200


@localprime_bp.route("/agents", methods=["GET"])
def get_agents():

    query = {
        "isAgent": True
    }

    branch_code = request.args.get("branchCode")
    status = request.args.get("status")
    agent_code = request.args.get("agentCode")

    if branch_code:
        query["BranchCode"] = branch_code

    if status:
        query["agentStatus"] = status

    if agent_code:
        query["agentCode"] = agent_code

    agents = list(
        members.find(query).sort("created_at", -1)
    )

    data = []

    for agent in agents:

        first_name = agent.get("FirstName", "")
        last_name = agent.get("LastName", "")

        agent_name = f"{first_name} {last_name}".strip()

        # -----------------------------------------
        # Get Branch Name using BranchCode
        # -----------------------------------------

        agent_branch_code = agent.get("BranchCode")

        branch = None

        if agent_branch_code:
            branch = db.branches.find_one({
                "branch_code": agent_branch_code
            })

        branch_name = (
            branch.get("branchName")
            if branch
            else ""
        )

        data.append({

            "_id": agent.get("_id"),

            # Member
            "MemberId": agent.get("MemberId"),
            "MemberName": agent.get("MemberName"),
            "IndroCode": agent.get("IntroCode"),

            # Agent
            "agentCode": agent.get("agentCode"),
            "agentName": agent_name,

            # Personal
            "Title": agent.get("Title"),
            "FirstName": first_name,
            "LastName": last_name,

            "MobileNo": agent.get("MobileNo"),
            "Email": agent.get("Email"),

            "Gender": agent.get("Gender"),
            "DateOfBirth": agent.get("DateOfBirth"),

            "UploadPhoto": agent.get("UploadPhoto"),

            # Branch
            "BranchCode": agent_branch_code,
            "BranchName": branch_name,

            # Designation
            "designation_id": agent.get("designation_id"),
            "designationCode": agent.get("designationCode"),
            "designationName": agent.get("designationName"),

            # Agent status
            "isAgent": agent.get("isAgent", False),
            "agentStatus": agent.get("agentStatus"),

            "joiningDate": agent.get("joiningDate"),

            "Status": agent.get("Status"),
            "status": agent.get("status"),

            "created_at": agent.get("created_at"),
            "updated_at": agent.get("updated_at")
        })

    return jsonify({
        "success": True,
        "count": len(data),
        "data": convert_objectids(data)
    }), 200

def upload_loan_documents():

    documents = []

    docs_json = request.form.get("additionalDocs")

    if not docs_json:
        return documents

    docs = json.loads(docs_json)

    for doc in docs:

        uploaded_doc = {
            "id": doc.get("id"),
            "name": doc.get("name"),
            "number": doc.get("number"),
            "fileKey": doc.get("fileKey")
        }

        file = request.files.get(doc["fileKey"])

        if file and file.filename:

            uploaded_doc["fileName"] = file.filename
            uploaded_doc["fileUrl"] = upload_file_to_s3(
                file,
                f"localprime/loan-documents"
            )

        documents.append(uploaded_doc)

    return documents

@localprime_bp.route("/loan-requests", methods=["POST"])
def create_loan_request():

     # Supports multipart/form-data and JSON
    data = request.form.to_dict() if request.form else (
        request.get_json(silent=True) or {}
    )

    print('formData',data)

    if not data:
        raise BadRequest("Data is required")

    required = [
        "member_id",
        "branch_id",
        "loan_product_id",
        "requestedAmount",
        "requestedTenure",
        "agent_id"
    ]

    for field in required:
        if not data.get(field):
            return jsonify({
                "success": False,
                "message": f"{field} is required"
            }), 400

    member = members.find_one({
        "_id": ObjectId(data["member_id"])
    })

    if not member:
        return jsonify({
            "success": False,
            "message": "Member not found"
        }), 404

    if member.get("status") != "approved":
        return jsonify({
            "success": False,
            "message": "Member is not approved"
        }), 400

    branch = db.branches.find_one({
        "_id": ObjectId(data["branch_id"])
    })

    if not branch:
        return jsonify({
            "success": False,
            "message": "Branch not found"
        }), 404

    agent = members.find_one({
        "_id": ObjectId(data["agent_id"])
    })

    if not agent:
        return jsonify({
            "success": False,
            "message": "Agent not found"
        }), 404

    loan_product = db.loan_products.find_one({
        "_id": ObjectId(data["loan_product_id"])
    })

    if not loan_product:
        return jsonify({
            "success": False,
            "message": "Loan product not found"
        }), 404

    # amount = float(data["requestedAmount"])
    # tenure = int(data["requestedTenure"])

    # if amount < loan_product["minAmount"] or amount > loan_product["maxAmount"]:
    #     return jsonify({
    #         "success": False,
    #         "message": "Invalid loan amount"
    #     }), 400

    # if tenure < loan_product["minTenure"] or tenure > loan_product["maxTenure"]:
    #     return jsonify({
    #         "success": False,
    #         "message": "Invalid tenure"
    #     }), 400

     # Upload documents to S3
    try:
        uploaded_files = upload_loan_documents()   # or upload_loan_files()
    except FileNotFoundError:
        return jsonify({
            "success": False,
            "message": "File not found"
        }), 404

    except NoCredentialsError:
        return jsonify({
            "success": False,
            "message": "AWS credentials not available"
        }), 403

    except ClientError as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    seq = get_next_sequence("loanRequestCode")
    request_code = f"LR{seq:06d}"

    now = datetime.utcnow()

    payload = {
        **data,
        'additionalDocs': uploaded_files,
        "loanRequestId": request_code,

        "member_id": member["_id"],
        "memberId": member["memberId"],
        "memberName": f'{member["FirstName"]} {member["LastName"]}',

        "agent_id": agent["_id"],
        "agentId": agent["memberId"],
        "agentName": f'{agent["FirstName"]} {agent["LastName"]}',

        "branch_id": branch["_id"],
        "branchCode": branch["branch_code"],
        "branchName": branch["branchName"],

        "loan_product_id": loan_product["_id"],
        "loanCode": loan_product["loanCode"],
        "loanName": loan_product["loanName"],

        "approvedAmount": None,

        "approvedTenure": None,

        "status": "pending",

        "approvedBy": None,
        "approvedAt": None,

        "rejectedReason": None,

        "loanId": None,

        "created_at": now,
        "updated_at": now
    }

    result = db.loan_requests.insert_one(payload)

    payload["_id"] = str(result.inserted_id)

    return jsonify({
        "success": True,
        "message": "Loan request submitted successfully",
        "data": convert_objectids(payload)
    }), 200

@localprime_bp.route("/loan-requests", methods=["GET"])
def get_loan_requests():

    query = {}

    if request.args.get("status"):
        query["status"] = request.args.get("status")

    if request.args.get("member_id"):
        query["member_id"] = ObjectId(request.args.get("member_id"))

    if request.args.get("branch_id"):
        query["branch_id"] = ObjectId(request.args.get("branch_id"))

    if request.args.get("loan_product_id"):
        query["loan_product_id"] = ObjectId(request.args.get("loan_product_id"))

    data = list(
        db.loan_requests.find(query).sort("created_at", -1)
    )

    return jsonify({
        "success": True,
        "count": len(data),
        "data": convert_objectids(data)
    }), 200

@localprime_bp.route("/loan-requests/<request_id>", methods=["POST"])
def update_loan_request(request_id):

    data = request.form.to_dict() if request.form else (
        request.get_json(silent=True) or {}
    )

    request_doc = db.loan_requests.find_one({
        "_id": ObjectId(request_id)
    })

    if not request_doc:
        return jsonify({
            "success": False,
            "message": "Loan request not found"
        }), 404

    if request_doc.get("status") != "pending":
        return jsonify({
            "success": False,
            "message": "Only pending loan requests can be updated"
        }), 400

    update_data = {}

    # Update branch if changed
    if data.get("branch_id"):
        branch = db.branches.find_one({
            "_id": ObjectId(data["branch_id"])
        })

        if not branch:
            return jsonify({
                "success": False,
                "message": "Branch not found"
            }), 404

        update_data.update({
            "branch_id": branch["_id"],
            "branchCode": branch["branch_code"],
            "branchName": branch["branchName"]
        })

    # Update loan product if changed
    if data.get("loan_product_id"):

        loan_product = db.loan_products.find_one({
            "_id": ObjectId(data["loan_product_id"])
        })

        if not loan_product:
            return jsonify({
                "success": False,
                "message": "Loan product not found"
            }), 404

        update_data.update({
            "loan_product_id": loan_product["_id"],
            "loanCode": loan_product["loanCode"],
            "loanName": loan_product["loanName"],
            "interestRate": loan_product["interestRate"]
        })

    # Editable fields
    editable_fields = [
        "requestedAmount",
        "requestedTenure",
        "purpose",
        "remarks",
        "agent_id"
    ]

    for field in editable_fields:
        if field in data:
            update_data[field] = data[field]

    # Update uploaded documents if new files are provided
    if request.files or request.form.get("additionalDocs"):
        try:
            uploaded_documents = upload_loan_documents()
            update_data["additionalDocs"] = uploaded_documents
        except FileNotFoundError:
            return jsonify({
                "success": False,
                "message": "File not found"
            }), 404
        except NoCredentialsError:
            return jsonify({
                "success": False,
                "message": "AWS credentials not available"
            }), 403
        except ClientError as e:
            return jsonify({
                "success": False,
                "message": str(e)
            }), 500

    update_data["updated_at"] = datetime.utcnow()

    if data.get("updatedBy"):
        update_data["updatedBy"] = data["updatedBy"]

    if data.get("updatedByName"):
        update_data["updatedByName"] = data["updatedByName"]

    db.loan_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": update_data}
    )

    request_doc.update(update_data)

    return jsonify({
        "success": True,
        "message": "Loan request updated successfully",
        "data": convert_objectids(request_doc)
    }), 200


@localprime_bp.route("/loans", methods=["GET"])
def get_loans():

    query = {}

    # Filters
    status = request.args.get("status")
    member_id = request.args.get("member_id")
    branch_id = request.args.get("branch_id")
    agent_id = request.args.get("agent_id")
    loan_product_id = request.args.get("loan_product_id")
    loan_id = request.args.get("loanId")

    if status:
        query["status"] = status

    if member_id:
        query["member_id"] = ObjectId(member_id)

    if branch_id:
        query["branch_id"] = ObjectId(branch_id)

    if agent_id:
        query["agent_id"] = ObjectId(agent_id)

    if loan_product_id:
        query["loan_product_id"] = ObjectId(loan_product_id)

    if loan_id:
        query["loanId"] = loan_id

    loans = list(
        db.loans.find(query).sort("created_at", -1)
    )

    return jsonify({
        "success": True,
        "count": len(loans),
        "data": convert_objectids(loans)
    }), 200

@localprime_bp.route("/loans/<loan_id>", methods=["GET"])
def get_loan(loan_id):

    loan = db.loans.find_one({
        "_id": ObjectId(loan_id)
    })

    if not loan:
        return jsonify({
            "success": False,
            "message": "Loan not found"
        }), 404

    return jsonify({
        "success": True,
        "data": convert_objectids(loan)
    }), 200


# ============================================================
# WALLET
# ============================================================

@localprime_bp.route("/wallet/create", methods=["POST"])
def create_wallet():
    data = request.get_json(silent=True) or {}

    agent_id = data.get("agent_id")

    if not agent_id:
        return jsonify({
            "success": False,
            "message": "agent_id is required"
        }), 400

    # Validate ObjectId
    try:
        agent_oid = ObjectId(agent_id)
    except Exception:
        return jsonify({
            "success": False,
            "message": "Invalid agent_id"
        }), 400

    # Find agent
    agent = members.find_one({
        "_id": agent_oid,
        "isAgent": True
    })

    if not agent:
        return jsonify({
            "success": False,
            "message": "Agent not found"
        }), 404

    # Check wallet already exists
    existing_wallet = db.wallets.find_one({
        "agent_id": agent_oid
    })

    if existing_wallet:
        return jsonify({
            "success": False,
            "message": "Wallet already exists for this agent",
            "data": convert_objectids(existing_wallet)
        }), 400

    now = datetime.utcnow()

    # Generate wallet number
    seq = get_next_sequence("walletNumber")
    wallet_number = f"WAL{seq:06d}"

    # Credit limit
    credit_limit = 5000.0

    wallet = {
        "walletNumber": wallet_number,

        # Agent
        "agent_id": agent_oid,
        "agentCode": agent.get("agentCode"),
        "agentName": agent.get("name"),

        # Branch
        "branch_id": agent.get("branch_id"),
        "branchCode": agent.get("branchCode"),
        "branchName": agent.get("branchName"),

        # Credit Wallet
        "creditLimit": credit_limit,
        "usedCredit": 0.0,
        "availableCredit": credit_limit,

        # Summary
        "totalWithdraw": 0.0,
        "totalDeposit": 0.0,

        "currency": "INR",
        "status": "active",

        "created_at": now,
        "updated_at": now
    }

    result = db.wallets.insert_one(wallet)

    wallet["_id"] = str(result.inserted_id)

    return jsonify({
        "success": True,
        "message": "Wallet created successfully",
        "data": convert_objectids(wallet)
    }), 201


# ============================================================
# GET WALLET LIST
# ============================================================

@localprime_bp.route("/wallet/list", methods=["GET"])
def get_wallet_list():

    query = {}

    agent_id = request.args.get("agent_id")
    branch_id = request.args.get("branch_id")
    status = request.args.get("status")

    # Agent filter
    if agent_id:
        try:
            query["agent_id"] = ObjectId(agent_id)
        except Exception:
            return jsonify({
                "success": False,
                "message": "Invalid agent_id"
            }), 400

    # Branch filter
    if branch_id:
        try:
            query["branch_id"] = ObjectId(branch_id)
        except Exception:
            return jsonify({
                "success": False,
                "message": "Invalid branch_id"
            }), 400

    # Status filter
    if status:
        query["status"] = status

    wallets = list(
        db.wallets.find(query).sort("created_at", -1)
    )

    return jsonify({
        "success": True,
        "count": len(wallets),
        "data": convert_objectids(wallets)
    }), 200



def create_wallet_voucher(
    wallet,
    amount,
    voucher_type,
    voucher_mode,
    narration,
    debit_ledger_id,
    debit_ledger_name,
    credit_ledger_id,
    credit_ledger_name,
    created_by="admin"
):
    now = datetime.utcnow()

    # Sequential transaction number
    txn = get_next_sequence("voucherTxn")

    # Voucher number
    date_string = now.strftime("%Y-%m-%d")
    voucher_number = f"BRV-{date_string}-{txn}"

    agent_id = str(wallet.get("agent_id"))
    agent_name = wallet.get("agentName", "")

    entries = [
        {
            "ledger_id": debit_ledger_id,
            "ledger_name": debit_ledger_name,
            "narration": narration,
            "debit": float(amount),
            "credit": 0.0,
            "employee_id": agent_id,
            "employee_name": agent_name
        },
        {
            "ledger_id": credit_ledger_id,
            "ledger_name": credit_ledger_name,
            "narration": narration,
            "debit": 0.0,
            "credit": float(amount),
            "employee_id": agent_id,
            "employee_name": agent_name
        }
    ]

    voucher = {
        "voucher_number": voucher_number,
        "voucher_type": voucher_type,
        "voucher_mode": voucher_mode,
        "txn": txn,
        "from_id": created_by,
        "date": now,
        "narration": narration,
        "amount": float(amount),
        "entries": entries,
        "created_by": created_by,
        "created_at": now
    }

    result = db.vouchers.insert_one(voucher)

    voucher["_id"] = str(result.inserted_id)

    return voucher

# ============================================================
# WITHDRAW FROM CREDIT WALLET
# ============================================================
@localprime_bp.route("/wallet/withdraw", methods=["POST"])
def wallet_withdraw():

    data = request.get_json(silent=True) or {}

    wallet_id = data.get("wallet_id")
    amount = data.get("amount")
    remarks = data.get("remarks", "")
    created_by = data.get("created_by", "admin")

    if not wallet_id:
        return jsonify({
            "success": False,
            "message": "wallet_id is required"
        }), 400

    if amount is None:
        return jsonify({
            "success": False,
            "message": "amount is required"
        }), 400

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid amount"
        }), 400

    if amount <= 0:
        return jsonify({
            "success": False,
            "message": "Amount must be greater than 0"
        }), 400

    try:
        wallet_oid = ObjectId(wallet_id)
    except Exception:
        return jsonify({
            "success": False,
            "message": "Invalid wallet_id"
        }), 400

    wallet = db.wallets.find_one({
        "_id": wallet_oid
    })

    if not wallet:
        return jsonify({
            "success": False,
            "message": "Wallet not found"
        }), 404

    if wallet.get("status") != "active":
        return jsonify({
            "success": False,
            "message": "Wallet is not active"
        }), 400

    available_credit = float(
        wallet.get("availableCredit", 0)
    )

    if amount > available_credit:
        return jsonify({
            "success": False,
            "message": "Credit limit exceeded",
            "creditLimit": wallet.get("creditLimit", 0),
            "usedCredit": wallet.get("usedCredit", 0),
            "availableCredit": available_credit,
            "requestedAmount": amount
        }), 400

    now = datetime.utcnow()

    old_used_credit = float(
        wallet.get("usedCredit", 0)
    )

    new_used_credit = round(
        old_used_credit + amount,
        2
    )

    new_available_credit = round(
        float(wallet.get("creditLimit", 0)) -
        new_used_credit,
        2
    )

    new_total_withdraw = round(
        float(wallet.get("totalWithdraw", 0)) +
        amount,
        2
    )

    # ------------------------------------------------
    # UPDATE WALLET
    # ------------------------------------------------

    db.wallets.update_one(
        {
            "_id": wallet_oid
        },
        {
            "$set": {
                "usedCredit": new_used_credit,
                "availableCredit": new_available_credit,
                "totalWithdraw": new_total_withdraw,
                "updated_at": now
            }
        }
    )

    # ------------------------------------------------
    # CREATE VOUCHER
    # ------------------------------------------------

    narration = remarks or "Agent wallet withdrawal"

    voucher = create_wallet_voucher(
        wallet=wallet,
        amount=amount,

        voucher_type="Receipt",
        voucher_mode="Bank",

        narration=narration,

        # Bank / Cash
        debit_ledger_id=data.get("debit_ledger_id", "A4"),
        debit_ledger_name=data.get(
            "debit_ledger_name",
            "IDBI Bank"
        ),

        # Agent wallet / credit ledger
        credit_ledger_id=data.get(
            "credit_ledger_id",
            "A41"
        ),
        credit_ledger_name=data.get(
            "credit_ledger_name",
            "Other Income"
        ),

        created_by=created_by
    )

    # ------------------------------------------------
    # WALLET TRANSACTION
    # ------------------------------------------------

    transaction_seq = get_next_sequence(
        "walletTransaction"
    )

    transaction = {
        "transactionNumber": f"WT{transaction_seq:08d}",

        "wallet_id": wallet_oid,
        "walletNumber": wallet.get("walletNumber"),

        "agent_id": wallet.get("agent_id"),
        "agentCode": wallet.get("agentCode"),
        "agentName": wallet.get("agentName"),

        "type": "withdraw",
        "amount": amount,

        "balanceBefore": old_used_credit,
        "balanceAfter": new_used_credit,

        "availableCreditBefore": available_credit,
        "availableCreditAfter": new_available_credit,

        "voucher_id": voucher["_id"],
        "voucher_number": voucher["voucher_number"],

        "remarks": remarks,

        "status": "success",

        "created_at": now
    }

    db.wallet_transactions.insert_one(transaction)

    updated_wallet = db.wallets.find_one({
        "_id": wallet_oid
    })

    return jsonify({
        "success": True,
        "message": "Amount withdrawn successfully",

        "data": {
            "wallet": convert_objectids(updated_wallet),

            "transaction": convert_objectids(
                transaction
            ),

            "voucher": convert_objectids(
                voucher
            )
        }
    }), 200


@localprime_bp.route("/wallet/deposit", methods=["POST"])
def wallet_deposit():

    data = request.get_json(silent=True) or {}

    wallet_id = data.get("wallet_id")
    amount = data.get("amount")
    remarks = data.get("remarks", "")
    created_by = data.get("created_by", "admin")

    if not wallet_id:
        return jsonify({
            "success": False,
            "message": "wallet_id is required"
        }), 400

    if amount is None:
        return jsonify({
            "success": False,
            "message": "amount is required"
        }), 400

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({
            "success": False,
            "message": "Invalid amount"
        }), 400

    if amount <= 0:
        return jsonify({
            "success": False,
            "message": "Amount must be greater than 0"
        }), 400

    try:
        wallet_oid = ObjectId(wallet_id)
    except Exception:
        return jsonify({
            "success": False,
            "message": "Invalid wallet_id"
        }), 400

    wallet = db.wallets.find_one({
        "_id": wallet_oid
    })

    if not wallet:
        return jsonify({
            "success": False,
            "message": "Wallet not found"
        }), 404

    if wallet.get("status") != "active":
        return jsonify({
            "success": False,
            "message": "Wallet is not active"
        }), 400

    used_credit = float(
        wallet.get("usedCredit", 0)
    )

    # Cannot repay more than used credit
    if amount > used_credit:
        return jsonify({
            "success": False,
            "message": "Deposit amount cannot be greater than used credit",
            "usedCredit": used_credit,
            "requestedAmount": amount
        }), 400

    now = datetime.utcnow()

    old_available_credit = float(
        wallet.get("availableCredit", 0)
    )

    new_used_credit = round(
        used_credit - amount,
        2
    )

    new_available_credit = round(
        float(wallet.get("creditLimit", 0)) -
        new_used_credit,
        2
    )

    new_total_deposit = round(
        float(wallet.get("totalDeposit", 0)) +
        amount,
        2
    )

    # ------------------------------------------------
    # UPDATE WALLET
    # ------------------------------------------------

    db.wallets.update_one(
        {
            "_id": wallet_oid
        },
        {
            "$set": {
                "usedCredit": new_used_credit,
                "availableCredit": new_available_credit,
                "totalDeposit": new_total_deposit,
                "updated_at": now
            }
        }
    )

    # ------------------------------------------------
    # CREATE PAYMENT VOUCHER
    # ------------------------------------------------

    narration = remarks or "Agent wallet deposit"

    voucher = create_wallet_voucher(
        wallet=wallet,
        amount=amount,

        voucher_type="Payment",
        voucher_mode="Bank",

        narration=narration,

        # Agent wallet / credit ledger
        debit_ledger_id=data.get(
            "debit_ledger_id",
            "A41"
        ),
        debit_ledger_name=data.get(
            "debit_ledger_name",
            "Other Income"
        ),

        # Bank
        credit_ledger_id=data.get(
            "credit_ledger_id",
            "A4"
        ),
        credit_ledger_name=data.get(
            "credit_ledger_name",
            "IDBI Bank"
        ),

        created_by=created_by
    )

    # ------------------------------------------------
    # WALLET TRANSACTION
    # ------------------------------------------------

    transaction_seq = get_next_sequence(
        "walletTransaction"
    )

    transaction = {
        "transactionNumber": f"WT{transaction_seq:08d}",

        "wallet_id": wallet_oid,
        "walletNumber": wallet.get("walletNumber"),

        "agent_id": wallet.get("agent_id"),
        "agentCode": wallet.get("agentCode"),
        "agentName": wallet.get("agentName"),

        "type": "deposit",
        "amount": amount,

        "balanceBefore": used_credit,
        "balanceAfter": new_used_credit,

        "availableCreditBefore": old_available_credit,
        "availableCreditAfter": new_available_credit,

        "voucher_id": voucher["_id"],
        "voucher_number": voucher["voucher_number"],

        "remarks": remarks,

        "status": "success",

        "created_at": now
    }

    db.wallet_transactions.insert_one(transaction)

    updated_wallet = db.wallets.find_one({
        "_id": wallet_oid
    })

    return jsonify({
        "success": True,
        "message": "Amount deposited successfully",

        "data": {
            "wallet": convert_objectids(updated_wallet),

            "transaction": convert_objectids(
                transaction
            ),

            "voucher": convert_objectids(
                voucher
            )
        }
    }), 200


@localprime_bp.route("/wallet/details", methods=["GET"])
def get_wallet_details():

    wallet_id = request.args.get("wallet_id")
    agent_id = request.args.get("agent_id")

    if not wallet_id and not agent_id:
        return jsonify({
            "success": False,
            "message": "wallet_id or agent_id is required"
        }), 400

    # -----------------------------------------
    # Find Wallet
    # -----------------------------------------

    query = {}

    if wallet_id:
        try:
            query["_id"] = ObjectId(wallet_id)
        except Exception:
            return jsonify({
                "success": False,
                "message": "Invalid wallet_id"
            }), 400

    elif agent_id:
        try:
            query["agent_id"] = ObjectId(agent_id)
        except Exception:
            return jsonify({
                "success": False,
                "message": "Invalid agent_id"
            }), 400

    wallet = db.wallets.find_one(query)

    if not wallet:
        return jsonify({
            "success": False,
            "message": "Wallet not found"
        }), 404

    # -----------------------------------------
    # Wallet Values
    # -----------------------------------------

    credit_limit = float(
        wallet.get("creditLimit", 0)
    )

    used_credit = float(
        wallet.get("usedCredit", 0)
    )

    available_credit = float(
        wallet.get("availableCredit", 0)
    )

    total_withdraw = float(
        wallet.get("totalWithdraw", 0)
    )

    total_deposit = float(
        wallet.get("totalDeposit", 0)
    )

    # -----------------------------------------
    # Recent Transactions
    # -----------------------------------------

    transactions = list(
        db.wallet_transactions.find({
            "wallet_id": wallet["_id"]
        })
        .sort("created_at", -1)
        .limit(20)
    )

    # -----------------------------------------
    # Response
    # -----------------------------------------

    response_data = {
        "wallet": {
            "_id": wallet["_id"],
            "walletNumber": wallet.get("walletNumber"),

            "agent_id": wallet.get("agent_id"),
            "agentCode": wallet.get("agentCode"),
            "agentName": wallet.get("agentName"),

            "branch_id": wallet.get("branch_id"),
            "branchCode": wallet.get("branchCode"),
            "branchName": wallet.get("branchName"),

            "creditLimit": credit_limit,
            "usedCredit": used_credit,
            "availableCredit": available_credit,

            "totalWithdraw": total_withdraw,
            "totalDeposit": total_deposit,

            "currency": wallet.get("currency", "INR"),
            "status": wallet.get("status", "active"),

            "created_at": wallet.get("created_at"),
            "updated_at": wallet.get("updated_at")
        },

        "transactions": transactions
    }

    return jsonify({
        "success": True,
        "message": "Wallet details fetched successfully",
        "data": convert_objectids(response_data)
    }), 200




















































loan_collection = db["loans"]
disbursement_collection = db["loan_disbursements"]
interest_collection = db["loan_interest_posting"]
emi_due_collection = db["loan_emi_due"]
payment_collection = db["loan_payments"]
penalty_collection = db["loan_penalties"]


VOUCHER_PREFIX_MAP = {
    ("Receipt", "Bank"): "BRV",
    ("Receipt", "Cash"): "CRV",
    ("Payment", "Bank"): "BPV",
    ("Payment", "Cash"): "CPV",
    ("Journal", "Journal"): "JRV",
}

# def generate_voucher_number(voucher_type, voucher_mode):
#     voucher_type = voucher_type.strip().title()
#     voucher_mode = voucher_mode.strip().title()
#     prefix = VOUCHER_PREFIX_MAP.get((voucher_type, voucher_mode))
#     if not prefix:
#         raise ValueError(f"Invalid voucher type/mode: {voucher_type}/{voucher_mode}")
#     now = datetime.utcnow()
#     txn = get_next_sequence("voucherTxn")
#     voucher_number = f"{prefix}-{now.strftime('%Y-%m-%d')}-{txn}"
#     return voucher_number, txn
# =========================================================
# GENERATE VOUCHER NUMBER
# PREFIX + DATE + DAILY SEQUENCE
# =========================================================

def generate_voucher_number(voucher_type, voucher_mode):

    voucher_type = voucher_type.strip().title()
    voucher_mode = voucher_mode.strip().title()

    prefix = VOUCHER_PREFIX_MAP.get(
        (voucher_type, voucher_mode)
    )

    if not prefix:
        raise ValueError(
            f"Invalid voucher type/mode: "
            f"{voucher_type}/{voucher_mode}"
        )

    # Current date
    now = datetime.utcnow()

    date_str = now.strftime("%Y-%m-%d")

    sequence_name = (
        f"voucherTxn_{prefix}_{date_str}"
    )

    txn = get_next_sequence(sequence_name)

    voucher_number = (
        f"{prefix}-{date_str}-{txn}"
    )

    return voucher_number, txn

def create_voucher(voucher_type, voucher_mode, narration, entries, amount=None, created_by="admin", from_id=None):
    voucher_type = voucher_type.strip().title()
    voucher_mode = voucher_mode.strip().title()
    if (voucher_type, voucher_mode) not in VOUCHER_PREFIX_MAP:
        raise ValueError(f"Invalid voucher type/mode: {voucher_type}/{voucher_mode}")
    if not entries:
        raise ValueError("Voucher must contain at least one ledger entry")
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    formatted_entries = []
    for entry in entries:
        ledger_id = entry.get("ledger_id")
        ledger_name = entry.get("ledger_name")
        if not ledger_id:
            raise ValueError("ledger_id is required")
        if not ledger_name:
            raise ValueError("ledger_name is required")
        debit = Decimal(str(entry.get("debit", 0) or 0))
        credit = Decimal(str(entry.get("credit", 0) or 0))
        if debit < 0 or credit < 0:
            raise ValueError("Debit and credit cannot be negative")
        if debit > 0 and credit > 0:
            raise ValueError(f"Ledger '{ledger_name}' cannot have both debit and credit")
        total_debit += debit
        total_credit += credit
        formatted_entries.append({
            "ledger_id": ledger_id,
            "ledger_name": ledger_name,
            "narration": entry.get("narration", narration),
            "debit": float(debit),
            "credit": float(credit),
            "employee_id": entry.get("employee_id"),
            "employee_name": entry.get("employee_name"),
        })
    if total_debit != total_credit:
        raise ValueError(f"Voucher is not balanced. Debit: {total_debit}, Credit: {total_credit}")
    if total_debit <= 0:
        raise ValueError("Voucher amount must be greater than zero")
    amount = total_debit if amount is None else Decimal(str(amount))
    if amount <= 0:
        raise ValueError("Voucher amount must be greater than zero")
    amount = amount.quantize(Decimal("0.01"))
    now = datetime.utcnow()
    voucher_number, txn = generate_voucher_number(voucher_type, voucher_mode)
    voucher = {
        "voucher_number": voucher_number,
        "voucher_type": voucher_type,
        "voucher_mode": voucher_mode,
        "txn": txn,
        "from_id": from_id or created_by,
        "date": now,
        "narration": narration,
        "amount": float(amount),
        "entries": formatted_entries,
        "created_by": created_by,
        "created_at": now,
    }
    result = db.vouchers.insert_one(voucher)
    voucher["_id"] = str(result.inserted_id)
    return voucher


@localprime_bp.route("/loan-calculator", methods=["POST"])
def loan_calculator():
    try:
        data = request.get_json()

        principal = float(data.get("loan_amount", 0))
        annual_rate = float(data.get("interest_rate", 0))
        tenure = int(data.get("tenure", 0))

        frequency = data.get("frequency", "monthly").lower()
        interest_type = data.get("interest_type", "reducing").lower()

        if principal <= 0:
            return jsonify({"success": False, "message": "Invalid loan amount"}), 400

        if annual_rate < 0:
            return jsonify({"success": False, "message": "Invalid interest rate"}), 400

        if tenure <= 0:
            return jsonify({"success": False, "message": "Invalid tenure"}), 400

        if frequency == "daily":
            periods_per_year = 365
        elif frequency == "weekly":
            periods_per_year = 52
        elif frequency == "fortnightly":
            periods_per_year = 26
        elif frequency == "monthly":
            periods_per_year = 12
        else:
            return jsonify({
                "success": False,
                "message": "Frequency must be daily, weekly, fortnightly or monthly"
            }), 400

        if interest_type not in ["flat", "reducing"]:
            return jsonify({
                "success": False,
                "message": "Interest type must be flat or reducing"
            }), 400

        period_rate = annual_rate / (periods_per_year * 100)

        schedule = []

        #############################################
        # REDUCING BALANCE
        #############################################

        if interest_type == "reducing":

            if period_rate == 0:
                installment = principal / tenure
            else:
                installment = (
                    principal *
                    period_rate *
                    pow((1 + period_rate), tenure)
                ) / (
                    pow((1 + period_rate), tenure) - 1
                )

            total_payment = installment * tenure
            total_interest = total_payment - principal

            balance = principal

            for i in range(1, tenure + 1):

                interest = balance * period_rate
                principal_paid = installment - interest

                if i == tenure:
                    principal_paid = balance
                    installment = principal_paid + interest

                balance -= principal_paid

                schedule.append({
                    "period": i,
                    "installment": round(installment),
                    "principal": round(principal_paid),
                    "interest": round(interest),
                    "balance": round(max(balance, 0))
                })

        #############################################
        # FLAT INTEREST
        #############################################

        else:

            total_interest = principal * period_rate * tenure
            total_payment = principal + total_interest

            installment = total_payment / tenure

            principal_paid = principal / tenure
            interest_each = total_interest / tenure

            balance = principal

            for i in range(1, tenure + 1):

                balance -= principal_paid

                schedule.append({
                    "period": i,
                    "installment": round(installment),
                    "principal": round(principal_paid),
                    "interest": round(interest_each),
                    "balance": round(max(balance, 0))
                })

        return jsonify({
            "success": True,
            "loan_amount": round(principal),
            "interest_rate": annual_rate,
            "frequency": frequency,
            "interest_type": interest_type,
            "tenure": tenure,
            "installment": round(installment),
            "total_interest": round(total_interest),
            "total_payment": round(total_payment),
            "schedule": schedule
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@localprime_bp.route("/loan-requests-approval/<request_id>", methods=["POST"])
def loan_request_approval(request_id):

    try:

        data = request.get_json(silent=True) or {}

        status = data.get("status")

        if status not in ["approved", "rejected"]:
            return jsonify({
                "success": False,
                "message": "Status must be 'approved' or 'rejected'"
            }), 400

        # -------------------------------------------------
        # FIND REQUEST
        # -------------------------------------------------

        try:
            request_object_id = ObjectId(request_id)
        except Exception:
            return jsonify({
                "success": False,
                "message": "Invalid request_id"
            }), 400

        request_doc = db.loan_requests.find_one({
            "_id": request_object_id
        })

        if not request_doc:
            return jsonify({
                "success": False,
                "message": "Loan request not found"
            }), 404

        if request_doc.get("status") != "pending":
            return jsonify({
                "success": False,
                "message": "Request already processed"
            }), 400

        now = datetime.utcnow()

        # =================================================
        # REJECTED
        # =================================================

        if status == "rejected":

            update_data = {
                "status": "rejected",
                "rejectedReason": data.get("rejectedReason", ""),
                "rejectedBy": data.get("rejectedBy"),
                "rejectedByName": data.get("rejectedByName"),
                "rejectedAt": now,
                "updated_at": now
            }

            db.loan_requests.update_one(
                {"_id": request_object_id},
                {"$set": update_data}
            )

            request_doc.update(update_data)

            return jsonify({
                "success": True,
                "message": "Loan request rejected successfully",
                "data": convert_objectids(request_doc)
            }), 200

        # =================================================
        # APPROVED / SANCTIONED
        # =================================================

        # -------------------------------------------------
        # APPROVED LOAN DETAILS
        # -------------------------------------------------

        approved_amount = float(
            data.get(
                "approvedAmount",
                request_doc.get("requestedAmount", 0)
            )
        )

        approved_tenure = int(
            data.get(
                "approvedTenure",
                request_doc.get("requestedTenure", 0)
            )
        )

        interest_rate = float(
            data.get(
                "interestRate",
                request_doc.get("interestRate", 0)
            )
        )

        interest_type = data.get(
            "interestType",
            request_doc.get("interestType", "reducing")
        ).lower()

        frequency = data.get(
            "frequency",
            request_doc.get("frequency", "monthly")
        ).lower()

        processing_fee = float(
            data.get(
                "processingFee",
                request_doc.get("processingFee", 0)
            )
        )

        purpose = data.get(
            "purpose",
            request_doc.get("purpose", "")
        )

        first_installment_date = data.get(
            "firstInstallmentDate",
            request_doc.get("firstInstallmentDate")
        )

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if approved_amount <= 0:
            return jsonify({
                "success": False,
                "message": "Invalid approved amount"
            }), 400

        if approved_tenure <= 0:
            return jsonify({
                "success": False,
                "message": "Invalid approved tenure"
            }), 400

        if interest_type not in ["flat", "reducing"]:
            return jsonify({
                "success": False,
                "message": "Invalid interest type"
            }), 400

        # -------------------------------------------------
        # PERIODS PER YEAR
        # -------------------------------------------------

        periods_map = {
            "daily": 365,
            "weekly": 52,
            "fortnightly": 26,
            "monthly": 12
        }

        if frequency not in periods_map:
            return jsonify({
                "success": False,
                "message": "Invalid frequency"
            }), 400

        periods_per_year = periods_map[frequency]

        # -------------------------------------------------
        # PERIODIC INTEREST RATE
        # -------------------------------------------------

        period_rate = (
            interest_rate /
            (periods_per_year * 100)
        )

        # =================================================
        # FLAT INTEREST
        # =================================================

        if interest_type == "flat":

            total_interest = (
                approved_amount
                * period_rate
                * approved_tenure
            )

            total_payment = (
                approved_amount
                + total_interest
            )

            installment = (
                total_payment /
                approved_tenure
            )

        # =================================================
        # REDUCING INTEREST
        # =================================================

        else:

            if period_rate == 0:

                installment = (
                    approved_amount /
                    approved_tenure
                )

            else:

                installment = (
                    approved_amount
                    * period_rate
                    * pow(
                        1 + period_rate,
                        approved_tenure
                    )
                ) / (
                    pow(
                        1 + period_rate,
                        approved_tenure
                    ) - 1
                )

            total_payment = (
                installment *
                approved_tenure
            )

            total_interest = (
                total_payment -
                approved_amount
            )

        # =================================================
        # GENERATE LOAN NUMBER
        # =================================================

        seq = get_next_sequence("loanNumber")

        loan_number = f"LN{seq:06d}"

        # =================================================
        # CREATE LOAN DOCUMENT
        # =================================================

        loan_data = {

            # ---------------------------------------------
            # IDENTIFICATION
            # ---------------------------------------------

            "loan_number": loan_number,

            "loanRequestId": request_id,

            "customer_id": request_doc.get(
                "customer_id",
                request_doc.get("customerId")
            ),

            "member_id": request_doc.get("member_id"),

            "branch_id": request_doc.get("branch_id"),

            "loan_product_id": request_doc.get(
                "loan_product_id"
            ),

            "agent_id": request_doc.get("agent_id"),

            # ---------------------------------------------
            # LOAN DETAILS
            # ---------------------------------------------

            "purpose": purpose,

            "loan_amount": round(approved_amount),

            "approved_amount": round(
                approved_amount
            ),

            "outstanding_principal": round(
                approved_amount
            ),

            "interest_rate": interest_rate,

            "interest_type": interest_type,

            "frequency": frequency,

            "tenure": approved_tenure,

            "approved_tenure": approved_tenure,

            # ---------------------------------------------
            # FINANCIAL DETAILS
            # ---------------------------------------------

            "processing_fee": round(
                processing_fee
            ),

            "installment": round(
                installment
            ),

            "total_interest": round(
                total_interest
            ),

            "total_payment": round(
                total_payment
            ),

            # ---------------------------------------------
            # DATES
            # ---------------------------------------------

            "sanction_date": now,

            "first_installment_date":
                first_installment_date,
                
            # ---------------------------------------------
            # STATUS
            # ---------------------------------------------

            "loan_status": "SANCTIONED",

            "disbursement_status": "PENDING",

            # ---------------------------------------------
            # APPROVAL
            # ---------------------------------------------

            "approvedBy": data.get(
                "approvedBy"
            ),

            "approvedByName": data.get(
                "approvedByName"
            ),

            "approvedAt": now,

            # ---------------------------------------------
            # TIMESTAMPS
            # ---------------------------------------------

            "created_at": now,

            "updated_at": now
        }

        # =================================================
        # INSERT LOAN
        # =================================================

        loan_result = db.loans.insert_one(
            loan_data
        )

        # =================================================
        # UPDATE LOAN REQUEST
        # =================================================

        update_data = {

            "status": "approved",

            "loanId": loan_number,

            "approvedAmount":
                round(approved_amount),

            "approvedTenure":
                approved_tenure,

            "approvedBy":
                data.get("approvedBy"),

            "approvedByName":
                data.get("approvedByName"),

            "approvedAt": now,

            "updated_at": now
        }

        db.loan_requests.update_one(
            {"_id": request_object_id},
            {"$set": update_data}
        )

        request_doc.update(update_data)

        # =================================================
        # RESPONSE
        # =================================================

        return jsonify({

            "success": True,

            "message":
                "Loan request approved and sanctioned successfully",

            "data": {

                "loan_id":
                    str(loan_result.inserted_id),

                "loan_number":
                    loan_number,

                "loan_status":
                    "SANCTIONED",

                "disbursement_status":
                    "PENDING",

                "loan_amount":
                    round(approved_amount),

                "interest_rate":
                    interest_rate,

                "interest_type":
                    interest_type,

                "frequency":
                    frequency,

                "tenure":
                    approved_tenure,

                "installment":
                    round(installment),

                "total_interest":
                    round(total_interest),

                "total_payment":
                    round(total_payment),

                "processing_fee":
                    round(processing_fee),

                "sanction_date":
                    now
            }

        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@localprime_bp.route("/loan-disbursement", methods=["POST"])
def loan_disbursement():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request"
            }), 400

        loan_number = data.get("loan_number")
        disbursement_date = data.get("disbursement_date")
        payment_mode = data.get("payment_mode")
        transaction_id = data.get("transaction_id")

        if not loan_number:
            return jsonify({
                "success": False,
                "message": "loan_number is required"
            }), 400

        if not disbursement_date:
            return jsonify({
                "success": False,
                "message": "disbursement_date is required"
            }), 400

        try:
            disbursement_date = datetime.strptime(
                disbursement_date,
                "%Y-%m-%d"
            )
        except:
            return jsonify({
                "success": False,
                "message": "disbursement_date format should be YYYY-MM-DD"
            }), 400

        loan = loan_collection.find_one({
            "loan_number": loan_number
        })

        if not loan:
            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        if loan.get("loan_status") != "SANCTIONED":
            return jsonify({
                "success": False,
                "message": "Loan is not sanctioned"
            }), 400

        if loan.get("disbursement_status") == "DISBURSED":
            return jsonify({
                "success": False,
                "message": "Loan already disbursed"
            }), 400

        # -------------------------------------------------
        # Amount Calculation
        # -------------------------------------------------

        loan_amount = float(loan.get("loan_amount", 0))
        processing_fee = float(loan.get("processing_fee", 0))

        # GST rate - change if required
        gst_rate = float(data.get("gst_rate", 18))

        gst_amount = round(
            processing_fee * gst_rate / 100,
            2
        )

        net_disbursement = round(
            loan_amount - processing_fee - gst_amount,
            2
        )

        if net_disbursement < 0:
            return jsonify({
                "success": False,
                "message": "Processing fee and GST cannot exceed loan amount"
            }), 400

        # -------------------------------------------------
        # Ledger IDs
        # Change these defaults manually as required
        # -------------------------------------------------

        CONSUMER_LOAN_LEDGER_ID = "A1"
        CONSUMER_LOAN_LEDGER_NAME = "Consumer Loan"

        PROCESSING_FEE_LEDGER_ID = "PROCESSING_FEE"
        PROCESSING_FEE_LEDGER_NAME = "Processing Fee Income"

        GST_LEDGER_ID = "GST"
        GST_LEDGER_NAME = "GST Payable"

        if payment_mode == "Bank":
            PAYMENT_LEDGER_ID = "BANK"
            PAYMENT_LEDGER_NAME = "Bank"

        else:
            PAYMENT_LEDGER_ID = "CASH"
            PAYMENT_LEDGER_NAME = "Cash"

        # -------------------------------------------------
        # Voucher Entries
        # -------------------------------------------------

        voucher_entries = [
            {
                "ledger_id": CONSUMER_LOAN_LEDGER_ID,
                "ledger_name": CONSUMER_LOAN_LEDGER_NAME,
                "narration": f"Loan disbursement - {loan_number}",
                "debit": round(loan_amount, 2),
                "credit": 0
            },
            {
                "ledger_id": PROCESSING_FEE_LEDGER_ID,
                "ledger_name": PROCESSING_FEE_LEDGER_NAME,
                "narration": f"Processing fee - {loan_number}",
                "debit": 0,
                "credit": round(processing_fee, 2)
            },
            {
                "ledger_id": GST_LEDGER_ID,
                "ledger_name": GST_LEDGER_NAME,
                "narration": f"GST on processing fee - {loan_number}",
                "debit": 0,
                "credit": round(gst_amount, 2)
            },
            {
                "ledger_id": PAYMENT_LEDGER_ID,
                "ledger_name": PAYMENT_LEDGER_NAME,
                "narration": f"Net loan disbursement - {loan_number}",
                "debit": 0,
                "credit": round(net_disbursement, 2)
            }
        ]

        # -------------------------------------------------
        # Create Voucher
        # -------------------------------------------------

        voucher = create_voucher(
            voucher_type="Payment",
            voucher_mode=payment_mode,
            narration=f"Loan disbursement - {loan_number}",
            entries=voucher_entries,
            amount=loan_amount,
            created_by=data.get("created_by", "admin"),
            from_id=data.get("created_by", "admin")
        )

        # -------------------------------------------------
        # Update Loan
        # -------------------------------------------------

        loan_collection.update_one(
            {
                "_id": loan["_id"]
            },
            {
                "$set": {
                    "loan_status": "DISBURSED",
                    "disbursement_status": "DISBURSED",
                    "disbursement_date": disbursement_date,
                    "gross_disbursement": round(loan_amount),
                    "processing_fee": round(processing_fee),
                    "gst_amount": round(gst_amount),
                    "net_disbursement": round(net_disbursement),
                    "payment_mode": payment_mode,
                    "transaction_id": transaction_id,
                    "bank_name": data.get("bank_name"),
                    "account_number": data.get("account_number"),
                    "ifsc_code": data.get("ifsc_code"),
                    "remarks": data.get("remarks"),
                    "voucher_id": voucher["_id"],
                    "voucher_number": voucher["voucher_number"],
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # -------------------------------------------------
        # Save Disbursement History
        # -------------------------------------------------

        disbursement_collection.insert_one({
            "loan_id": loan["_id"],
            "loan_number": loan_number,
            "customer_id": loan.get("customer_id"),
            "loan_amount": round(loan_amount),
            "processing_fee": round(processing_fee),
            "gst_rate": gst_rate,
            "gst_amount": round(gst_amount),
            "net_disbursement": round(net_disbursement),
            "payment_mode": payment_mode,
            "transaction_id": transaction_id,
            "bank_name": data.get("bank_name"),
            "account_number": data.get("account_number"),
            "ifsc_code": data.get("ifsc_code"),
            "remarks": data.get("remarks"),
            "voucher_id": voucher["_id"],
            "voucher_number": voucher["voucher_number"],
            "disbursement_date": disbursement_date,
            "created_at": datetime.utcnow()
        })

        # -------------------------------------------------
        # Next Interest Date
        # -------------------------------------------------

        if loan["frequency"] == "daily":
            next_interest_date = disbursement_date + timedelta(days=1)

        elif loan["frequency"] == "weekly":
            next_interest_date = disbursement_date + timedelta(days=7)

        elif loan["frequency"] == "monthly":
            next_interest_date = disbursement_date + relativedelta(months=1)

        else:
            next_interest_date = disbursement_date

        loan_collection.update_one(
            {
                "_id": loan["_id"]
            },
            {
                "$set": {
                    "next_interest_date": next_interest_date.strftime("%Y-%m-%d")
                }
            }
        )

        return jsonify({
            "success": True,
            "message": "Loan disbursed successfully",
            "loan_number": loan_number,
            "loan_amount": round(loan_amount),
            "processing_fee": round(processing_fee),
            "gst_amount": round(gst_amount),
            "net_disbursement": round(net_disbursement),
            "voucher_id": voucher["_id"],
            "voucher_number": voucher["voucher_number"],
            "loan_status": "DISBURSED",
            "disbursement_status": "DISBURSED"
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@localprime_bp.route("/interest-posting", methods=["POST"])
def interest_posting():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request"
            }), 400

        loan_number = data.get("loan_number")

        if not loan_number:
            return jsonify({
                "success": False,
                "message": "loan_number required"
            }), 400

        loan = loan_collection.find_one({
            "loan_number": loan_number
        })

        if not loan:
            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        if loan.get("loan_status") != "DISBURSED":
            return jsonify({
                "success": False,
                "message": "Loan not disbursed"
            }), 400

        # -------------------------------------------------
        # Check whether interest already posted today
        # -------------------------------------------------

        today_start = datetime.combine(
            datetime.today(),
            datetime.min.time()
        )

        today_end = datetime.combine(
            datetime.today(),
            datetime.max.time()
        )

        exists = interest_collection.find_one({
            "loan_number": loan_number,
            "posting_date": {
                "$gte": today_start,
                "$lt": today_end
            }
        })

        if exists:
            return jsonify({
                "success": False,
                "message": "Interest already posted today."
            }), 400

        # -------------------------------------------------
        # Principal
        # -------------------------------------------------

        principal = float(
            loan.get("outstanding_principal", 0)
        )

        # -------------------------------------------------
        # Interest Rate
        # -------------------------------------------------

        annual_rate = float(
            loan.get("interest_rate", 0)
        )

        # -------------------------------------------------
        # Frequency
        # -------------------------------------------------

        frequency = loan.get(
            "frequency",
            "monthly"
        ).lower()

        # -------------------------------------------------
        # Posting Date
        # -------------------------------------------------

        posting_date = datetime.strptime(
            loan["next_interest_date"],
            "%Y-%m-%d"
        )

        # -------------------------------------------------
        # Calculate Interest
        # -------------------------------------------------

        if frequency == "daily":
            interest = principal * annual_rate / (365 * 100)
            next_date = posting_date + timedelta(days=1)

        elif frequency == "weekly":
            interest = principal * annual_rate / (52 * 100)
            next_date = posting_date + timedelta(days=7)

        elif frequency == "monthly":
            interest = principal * annual_rate / (12 * 100)
            next_date = posting_date + relativedelta(months=1)

        else:
            return jsonify({
                "success": False,
                "message": "Invalid frequency"
            }), 400

        interest = round(interest, 2)

        if interest <= 0:
            return jsonify({
                "success": False,
                "message": "Interest amount must be greater than zero"
            }), 400

        # -------------------------------------------------
        # Ledger IDs
        # Change these manually
        # -------------------------------------------------

        INTEREST_RECEIVABLE_LEDGER_ID = "INTEREST_RECEIVABLE"
        INTEREST_RECEIVABLE_LEDGER_NAME = "Interest Receivable"

        INTEREST_INCOME_LEDGER_ID = "INTEREST_INCOME"
        INTEREST_INCOME_LEDGER_NAME = "Interest Income"

        # -------------------------------------------------
        # Create Journal Voucher
        # -------------------------------------------------

        voucher = create_voucher(
            voucher_type="Journal",
            voucher_mode="Journal",
            narration=f"Interest posting - {loan_number}",
            amount=interest,
            created_by=data.get("created_by", "admin"),
            from_id=data.get("created_by", "admin"),
            entries=[
                {
                    "ledger_id": INTEREST_RECEIVABLE_LEDGER_ID,
                    "ledger_name": INTEREST_RECEIVABLE_LEDGER_NAME,
                    "narration": f"Interest receivable - {loan_number}",
                    "debit": interest,
                    "credit": 0
                },
                {
                    "ledger_id": INTEREST_INCOME_LEDGER_ID,
                    "ledger_name": INTEREST_INCOME_LEDGER_NAME,
                    "narration": f"Interest income - {loan_number}",
                    "debit": 0,
                    "credit": interest
                }
            ]
        )

        # -------------------------------------------------
        # Save Interest History
        # -------------------------------------------------

        interest_result = interest_collection.insert_one({
            "loan_id": loan["_id"],
            "loan_number": loan_number,
            "customer_id": loan["customer_id"],
            "posting_date": posting_date,
            "interest_amount": interest,
            "principal": principal,
            "interest_rate": annual_rate,
            "frequency": frequency,
            "status": "UNPAID",
            "voucher_id": voucher["_id"],
            "voucher_number": voucher["voucher_number"],
            "created_at": datetime.utcnow()
        })

        # -------------------------------------------------
        # Update Loan
        # -------------------------------------------------

        loan_collection.update_one(
            {
                "_id": loan["_id"]
            },
            {
                "$inc": {
                    "interest_outstanding": interest
                },
                "$set": {
                    "next_interest_date": next_date.strftime("%Y-%m-%d"),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return jsonify({
            "success": True,
            "message": "Interest posted successfully",
            "loan_number": loan_number,
            "principal": principal,
            "interest_posted": interest,
            "voucher_id": voucher["_id"],
            "voucher_number": voucher["voucher_number"],
            "next_interest_date": next_date.strftime("%Y-%m-%d")
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500



@localprime_bp.route("/interest-posting-list", methods=["GET"])
def interest_posting_list():

    try:

        date = request.args.get("date")

        if not date:
            return jsonify({
                "success": False,
                "message": "date is required (YYYY-MM-DD)"
            }), 400

        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return jsonify({
                "success": False,
                "message": "Invalid date format. Use YYYY-MM-DD"
            }), 400

        loans = loan_collection.find({

            "loan_status": "DISBURSED",

            "next_interest_date": date

        })

        data = []

        for loan in loans:

            data.append({

                "loan_number": loan.get("loan_number"),

                "customer_id": loan.get("customer_id"),

                "loan_amount": loan.get("loan_amount"),

                "outstanding_principal": loan.get("outstanding_principal"),

                "interest_rate": loan.get("interest_rate"),

                "frequency": loan.get("frequency"),

                "next_interest_date": loan.get("next_interest_date"),

                "interest_outstanding": loan.get("interest_outstanding", 0)

            })

        return jsonify({

            "success": True,

            "date": date,

            "total_loans": len(data),

            "data": data

        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@localprime_bp.route("/interest-posting-batch", methods=["POST"])
def interest_posting_batch():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request"
            }), 400

        posting_date = data.get("posting_date")

        if not posting_date:
            return jsonify({
                "success": False,
                "message": "posting_date is required (YYYY-MM-DD)"
            }), 400

        try:
            post_date = datetime.strptime(
                posting_date,
                "%Y-%m-%d"
            )
        except:
            return jsonify({
                "success": False,
                "message": "Invalid posting_date format"
            }), 400

        # -------------------------------------------------
        # Ledger IDs
        # Change these manually
        # -------------------------------------------------

        INTEREST_RECEIVABLE_LEDGER_ID = "INTEREST_RECEIVABLE"
        INTEREST_RECEIVABLE_LEDGER_NAME = "Interest Receivable"

        INTEREST_INCOME_LEDGER_ID = "INTEREST_INCOME"
        INTEREST_INCOME_LEDGER_NAME = "Interest Income"

        # -------------------------------------------------
        # Find loans
        # -------------------------------------------------

        loans = loan_collection.find({
            "loan_status": "DISBURSED",
            "next_interest_date": posting_date
        })

        total_processed = 0
        total_interest = 0
        processed_loans = []

        for loan in loans:
            try:
                principal = float(
                    loan.get("outstanding_principal", 0)
                )

                annual_rate = float(
                    loan.get("interest_rate", 0)
                )

                frequency = loan.get(
                    "frequency",
                    "monthly"
                ).lower()

                # -------------------------------------------------
                # Calculate Interest
                # -------------------------------------------------

                if frequency == "daily":
                    interest = principal * annual_rate / (365 * 100)
                    next_date = post_date + timedelta(days=1)

                elif frequency == "weekly":
                    interest = principal * annual_rate / (52 * 100)
                    next_date = post_date + timedelta(days=7)

                elif frequency == "monthly":
                    interest = principal * annual_rate / (12 * 100)
                    next_date = post_date + relativedelta(months=1)

                else:
                    continue

                interest = round(interest, 2)

                if interest <= 0:
                    continue

                # -------------------------------------------------
                # Duplicate Check
                # -------------------------------------------------

                already_posted = interest_collection.find_one({
                    "loan_number": loan["loan_number"],
                    "posting_date": post_date
                })

                if already_posted:
                    continue

                # -------------------------------------------------
                # Create Journal Voucher
                # -------------------------------------------------

                voucher = create_voucher(
                    voucher_type="Journal",
                    voucher_mode="Journal",
                    narration=f"Interest posting - {loan['loan_number']}",
                    amount=interest,
                    created_by=data.get(
                        "created_by",
                        "admin"
                    ),
                    from_id=data.get(
                        "created_by",
                        "admin"
                    ),
                    entries=[
                        {
                            "ledger_id": INTEREST_RECEIVABLE_LEDGER_ID,
                            "ledger_name": INTEREST_RECEIVABLE_LEDGER_NAME,
                            "narration": f"Interest receivable - {loan['loan_number']}",
                            "debit": interest,
                            "credit": 0
                        },
                        {
                            "ledger_id": INTEREST_INCOME_LEDGER_ID,
                            "ledger_name": INTEREST_INCOME_LEDGER_NAME,
                            "narration": f"Interest income - {loan['loan_number']}",
                            "debit": 0,
                            "credit": interest
                        }
                    ]
                )

                # -------------------------------------------------
                # Save Interest History
                # -------------------------------------------------

                interest_collection.insert_one({
                    "loan_id": loan["_id"],
                    "loan_number": loan["loan_number"],
                    "customer_id": loan["customer_id"],
                    "posting_date": post_date,
                    "principal": principal,
                    "interest_rate": annual_rate,
                    "interest_amount": interest,
                    "frequency": frequency,
                    "status": "UNPAID",
                    "voucher_id": voucher["_id"],
                    "voucher_number": voucher["voucher_number"],
                    "created_at": datetime.utcnow()
                })

                # -------------------------------------------------
                # Update Loan
                # -------------------------------------------------

                loan_collection.update_one(
                    {
                        "_id": loan["_id"]
                    },
                    {
                        "$inc": {
                            "interest_outstanding": interest
                        },
                        "$set": {
                            "next_interest_date": next_date.strftime(
                                "%Y-%m-%d"
                            ),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

                total_processed += 1
                total_interest += interest

                processed_loans.append({
                    "loan_number": loan["loan_number"],
                    "interest": interest,
                    "voucher_number": voucher["voucher_number"],
                    "next_interest_date": next_date.strftime(
                        "%Y-%m-%d"
                    )
                })

            except Exception as loan_error:
                processed_loans.append({
                    "loan_number": loan.get(
                        "loan_number"
                    ),
                    "success": False,
                    "message": str(loan_error)
                })

        return jsonify({
            "success": True,
            "posting_date": posting_date,
            "total_processed": total_processed,
            "total_interest_posted": round(
                total_interest,
                2
            ),
            "data": processed_loans
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@localprime_bp.route("/generate-emi-due", methods=["POST"])
def generate_emi_due():

    try:

        data = request.get_json()

        loan_number = data.get("loan_number")
        due_date = data.get("due_date")

        if not loan_number or not due_date:
            return jsonify({
                "success": False,
                "message": "loan_number and due_date are required"
            }), 400

        try:
            due_date_obj = datetime.strptime(
                due_date,
                "%Y-%m-%d"
            )
        except:
            return jsonify({
                "success": False,
                "message": "Invalid due_date format. Use YYYY-MM-DD"
            }), 400

        loan = loan_collection.find_one({
            "loan_number": loan_number
        })

        if not loan:
            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        # Loan Status
        if loan.get("loan_status") != "DISBURSED":
            return jsonify({
                "success": False,
                "message": "EMI can be generated only for disbursed loans"
            }), 400

        # Closed Loan
        if loan.get("loan_status") == "CLOSED":
            return jsonify({
                "success": False,
                "message": "Loan already closed"
            }), 400

        # Outstanding Principal
        outstanding_principal = float(
            loan.get("outstanding_principal", 0)
        )

        if outstanding_principal <= 0:
            return jsonify({
                "success": False,
                "message": "Loan already fully paid"
            }), 400

        # Previous EMI Pending (block if any EMI is UNPAID or PARTIAL)
        unpaid = emi_due_collection.find_one({
            "loan_number": loan_number,
            "status": {"$in": ["UNPAID", "PARTIAL"]}
        })

        if unpaid:
            return jsonify({
                "success": False,
                "message": f"Previous EMI #{unpaid.get('emi_number')} is still {unpaid.get('status', 'unpaid').lower()}. Please clear it before generating next EMI."
            }), 400

        # Duplicate Due Date
        already = emi_due_collection.find_one({
            "loan_number": loan_number,
            "due_date": due_date
        })

        if already:
            return jsonify({
                "success": False,
                "message": "EMI already generated for this due date"
            }), 400

        installment = float(
            loan.get("installment", 0)
        )

        # interest_due = total interest already posted but not yet collected
        interest_due = round(
            float(
                loan.get("interest_outstanding", 0)
            ),
            2
        )

        # principal_due = installment minus the interest component due
        principal_due = installment - interest_due

        if principal_due < 0:
            principal_due = 0

        if principal_due > outstanding_principal:
            principal_due = outstanding_principal

        principal_due = round(principal_due, 2)

        # total the customer needs to pay this EMI
        total_emi_due = round(principal_due + interest_due, 2)

        remaining_balance = round(
            outstanding_principal - principal_due,
            2
        )

        emi_number = (
            emi_due_collection.count_documents({
                "loan_number": loan_number
            }) + 1
        )

        emi_due_collection.insert_one({

            "loan_id": loan["_id"],

            "loan_number": loan_number,

            "customer_id": loan["customer_id"],

            "emi_number": emi_number,

            "due_date": due_date,

            "installment": total_emi_due,

            "principal_due": principal_due,

            "interest_due": interest_due,

            "remaining_balance": remaining_balance,

            "interest_rate": loan["interest_rate"],

            "frequency": loan["frequency"],

            "status": "UNPAID",

            "created_at": datetime.utcnow()

        })

        return jsonify({

            "success": True,

            "message": "EMI generated successfully",

            "loan_number": loan_number,

            "emi_number": emi_number,

            "due_date": due_date,

            "installment": total_emi_due,

            "principal_due": principal_due,

            "interest_due": interest_due,

            "remaining_balance": remaining_balance,

            "status": "UNPAID"

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500


@localprime_bp.route("/customer-payment", methods=["POST"])
def customer_payment():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                
                "success": False,
                "message": "Invalid request"
            }), 400

        loan_number = data.get("loan_number")
        emi_number = data.get("emi_number")

        try:
            payment_amount = float(
                data.get("payment_amount", 0)
            )
        except:
            payment_amount = 0

        payment_mode = data.get("payment_mode")

        if not loan_number or emi_number is None:
            return jsonify({
                "success": False,
                "message": "loan_number and emi_number are required"
            }), 400

        if payment_amount <= 0:
            return jsonify({
                "success": False,
                "message": "Invalid payment amount"
            }), 400

        if payment_mode not in ["Bank", "Cash"]:
            return jsonify({
                "success": False,
                "message": "payment_mode must be Bank or Cash"
            }), 400

        loan = loan_collection.find_one({
            "loan_number": loan_number
        })

        if not loan:
            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        if loan.get("loan_status") == "CLOSED":
            return jsonify({
                "success": False,
                "message": "Loan already closed"
            }), 400

        emi = emi_due_collection.find_one({
            "loan_number": loan_number,
            "emi_number": emi_number
        })

        if not emi:
            return jsonify({
                "success": False,
                "message": "EMI not found"
            }), 404

        if emi.get("status") == "PAID":
            return jsonify({
                "success": False,
                "message": "EMI already paid"
            }), 400

        # -------------------------------------------------
        # Amounts Due
        # -------------------------------------------------

        interest_due = float(
            emi.get("interest_due", 0)
        )

        principal_due = float(
            emi.get("principal_due", 0)
        )

        penalty_due = float(
            loan.get("penalty_outstanding", 0)
        )

        balance = payment_amount

        # -------------------------------------------------
        # Payment Allocation
        # Penalty -> Interest -> Principal
        # -------------------------------------------------

        penalty_paid = min(
            balance,
            penalty_due
        )

        balance -= penalty_paid

        interest_paid = min(
            balance,
            interest_due
        )

        balance -= interest_paid

        principal_paid = min(
            balance,
            principal_due
        )

        balance -= principal_paid

        # -------------------------------------------------
        # Prevent Excess Payment
        # -------------------------------------------------

        if balance > 0:
            return jsonify({
                "success": False,
                "message": "Payment amount exceeds the total amount due",
                "excess_amount": round(balance, 2)
            }), 400

        # -------------------------------------------------
        # New Loan Outstanding
        # -------------------------------------------------

        new_principal = round(
            float(
                loan.get(
                    "outstanding_principal",
                    0
                )
            ) - principal_paid,
            2
        )

        new_interest = round(
            float(
                loan.get(
                    "interest_outstanding",
                    0
                )
            ) - interest_paid,
            2
        )

        new_penalty = round(
            penalty_due - penalty_paid,
            2
        )

        new_principal = max(
            new_principal,
            0
        )

        new_interest = max(
            new_interest,
            0
        )

        new_penalty = max(
            new_penalty,
            0
        )

        # -------------------------------------------------
        # Ledger IDs
        # Change these manually
        # -------------------------------------------------

        if payment_mode == "Bank":
            PAYMENT_LEDGER_ID = "BANK"
            PAYMENT_LEDGER_NAME = "Bank"
        else:
            PAYMENT_LEDGER_ID = "CASH"
            PAYMENT_LEDGER_NAME = "Cash"

        CONSUMER_LOAN_LEDGER_ID = "A1"
        CONSUMER_LOAN_LEDGER_NAME = "Consumer Loan"

        INTEREST_RECEIVABLE_LEDGER_ID = "INTEREST_RECEIVABLE"
        INTEREST_RECEIVABLE_LEDGER_NAME = "Interest Receivable"

        PENALTY_INCOME_LEDGER_ID = "PENALTY_INCOME"
        PENALTY_INCOME_LEDGER_NAME = "Penalty Income"

        # -------------------------------------------------
        # Voucher Entries
        # -------------------------------------------------

        voucher_entries = [
            {
                "ledger_id": PAYMENT_LEDGER_ID,
                "ledger_name": PAYMENT_LEDGER_NAME,
                "narration": f"Loan payment received - {loan_number}",
                "debit": payment_amount,
                "credit": 0
            }
        ]

        if principal_paid > 0:
            voucher_entries.append({
                "ledger_id": CONSUMER_LOAN_LEDGER_ID,
                "ledger_name": CONSUMER_LOAN_LEDGER_NAME,
                "narration": f"Principal received - {loan_number}",
                "debit": 0,
                "credit": round(principal_paid, 2)
            })

        if interest_paid > 0:
            voucher_entries.append({
                "ledger_id": INTEREST_RECEIVABLE_LEDGER_ID,
                "ledger_name": INTEREST_RECEIVABLE_LEDGER_NAME,
                "narration": f"Interest received - {loan_number}",
                "debit": 0,
                "credit": round(interest_paid, 2)
            })

        if penalty_paid > 0:
            voucher_entries.append({
                "ledger_id": PENALTY_INCOME_LEDGER_ID,
                "ledger_name": PENALTY_INCOME_LEDGER_NAME,
                "narration": f"Penalty received - {loan_number}",
                "debit": 0,
                "credit": round(penalty_paid, 2)
            })

        # -------------------------------------------------
        # Create Receipt Voucher
        # -------------------------------------------------

        voucher = create_voucher(
            voucher_type="Receipt",
            voucher_mode=payment_mode,
            narration=f"Customer payment - {loan_number}, EMI {emi_number}",
            entries=voucher_entries,
            amount=payment_amount,
            created_by=data.get(
                "created_by",
                "admin"
            ),
            from_id=data.get(
                "created_by",
                "admin"
            )
        )

        # -------------------------------------------------
        # Update Loan
        # -------------------------------------------------

        loan_collection.update_one(
            {
                "_id": loan["_id"]
            },
            {
                "$set": {
                    "outstanding_principal": max(new_principal, 0),
                    "interest_outstanding": max(new_interest, 0),
                    "penalty_outstanding": max(new_penalty, 0),
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # -------------------------------------------------
        # EMI Status
        # -------------------------------------------------

        total_due = (
            principal_due +
            interest_due
        )

        paid_amount = (
            principal_paid +
            interest_paid
        )

        emi_status = "PAID"

        if paid_amount < total_due:
            emi_status = "PARTIAL"

        emi_due_collection.update_one(
            {
                "_id": emi["_id"]
            },
            {
                "$set": {
                    "status": emi_status,
                    "paid_date": data.get(
                        "payment_date"
                    ),
                    "principal_paid": principal_paid,
                    "interest_paid": interest_paid,
                    "penalty_paid": penalty_paid,
                    "payment_amount": payment_amount,
                    "voucher_id": voucher["_id"],
                    "voucher_number": voucher["voucher_number"],
                    "updated_at": datetime.utcnow()
                }
            }
        )

        # -------------------------------------------------
        # Mark interest_collection records as PAID
        # when interest is fully collected
        # -------------------------------------------------

        if interest_paid > 0:
            interest_collection.update_many(
                {
                    "loan_number": loan_number,
                    "status": "UNPAID"
                },
                {
                    "$set": {
                        "status": "PAID",
                        "paid_date": data.get("payment_date"),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

        # -------------------------------------------------
        # Payment History
        # -------------------------------------------------

        payment_collection.insert_one({
            "loan_id": loan["_id"],
            "loan_number": loan_number,
            "emi_number": emi_number,
            "customer_id": loan["customer_id"],
            "payment_date": data.get(
                "payment_date"
            ),
            "payment_amount": payment_amount,
            "principal_paid": principal_paid,
            "interest_paid": interest_paid,
            "penalty_paid": penalty_paid,
            "payment_mode": payment_mode,
            "transaction_id": data.get(
                "transaction_id"
            ),
            "voucher_id": voucher["_id"],
            "voucher_number": voucher["voucher_number"],
            "created_at": datetime.utcnow()
        })

        # -------------------------------------------------
        # Auto Loan Closure
        # -------------------------------------------------

        unpaid_emi_count = emi_due_collection.count_documents({
            "loan_number": loan_number,
            "status": {"$in": ["UNPAID", "PARTIAL"]}
        })

        loan_closed = (
            new_principal == 0 and
            new_interest == 0 and
            new_penalty == 0 and
            unpaid_emi_count == 0
        )

        if loan_closed:
            loan_collection.update_one(
                {
                    "_id": loan["_id"]
                },
                {
                    "$set": {
                        "loan_status": "CLOSED",
                        "closure_date": datetime.utcnow().strftime(
                            "%Y-%m-%d"
                        ),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

        # -------------------------------------------------
        # Response
        # -------------------------------------------------

        return jsonify({
            "success": True,
            "message": "Payment received successfully",
            "loan_number": loan_number,
            "emi_number": emi_number,
            "payment_amount": payment_amount,
            "principal_paid": round(
                principal_paid,
                2
            ),
            "interest_paid": round(
                interest_paid,
                2
            ),
            "penalty_paid": round(
                penalty_paid,
                2
            ),
            "remaining_principal": new_principal,
            "remaining_interest": new_interest,
            "remaining_penalty": new_penalty,
            "emi_status": emi_status,
            "loan_status": "CLOSED" if loan_closed else "DISBURSED",
            "voucher_id": voucher["_id"],
            "voucher_number": voucher["voucher_number"]
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@localprime_bp.route("/penalty-posting", methods=["POST"])
def penalty_posting():
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "message": "Invalid request"
            }), 400

        loan_number = data.get("loan_number")
        posting_date = data.get("posting_date")
        penalty_type = data.get(
            "penalty_type",
            "daily"
        )
        penalty_value = float(
            data.get(
                "penalty_value",
                100
            )
        )

        if not loan_number or not posting_date:
            return jsonify({
                "success": False,
                "message": "loan_number and posting_date are required"
            }), 400

        try:
            posting_date = datetime.strptime(
                posting_date,
                "%Y-%m-%d"
            )
        except:
            return jsonify({
                "success": False,
                "message": "posting_date format should be YYYY-MM-DD"
            }), 400

        loan = loan_collection.find_one({
            "loan_number": loan_number
        })

        if not loan:
            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        if loan.get("loan_status") != "DISBURSED":
            return jsonify({
                "success": False,
                "message": "Penalty can only be posted on disbursed loans"
            }), 400

        emi = emi_due_collection.find_one({
            "loan_number": loan_number,
            "status": "UNPAID"
        })

        if not emi:
            return jsonify({
                "success": False,
                "message": "No unpaid EMI found"
            }), 404

        due_date = datetime.strptime(
            emi["due_date"],
            "%Y-%m-%d"
        )

        delay_days = (
            posting_date - due_date
        ).days

        if delay_days <= 0:
            return jsonify({
                "success": False,
                "message": "Penalty not applicable"
            }), 400

        # -------------------------------------------------
        # Duplicate penalty check
        # -------------------------------------------------

        already = penalty_collection.find_one({
            "loan_number": loan_number,
            "due_date": emi["due_date"]
        })

        if already:
            return jsonify({
                "success": False,
                "message": "Penalty already posted"
            }), 400

        # -------------------------------------------------
        # Calculate Penalty
        # -------------------------------------------------

        installment = float(
            emi["installment"]
        )

        if penalty_type == "daily":
            penalty_amount = (
                delay_days *
                penalty_value
            )

        elif penalty_type == "percentage":
            penalty_amount = (
                installment *
                penalty_value /
                100
            )

        else:
            return jsonify({
                "success": False,
                "message": "Invalid penalty_type. Use daily or percentage"
            }), 400

        penalty_amount = round(
            penalty_amount,
            2
        )

        if penalty_amount <= 0:
            return jsonify({
                "success": False,
                "message": "Penalty amount must be greater than zero"
            }), 400

        # -------------------------------------------------
        # Ledger IDs
        # Change these manually
        # -------------------------------------------------

        PENALTY_RECEIVABLE_LEDGER_ID = "PENALTY_RECEIVABLE"
        PENALTY_RECEIVABLE_LEDGER_NAME = "Penalty Receivable"

        PENALTY_INCOME_LEDGER_ID = "PENALTY_INCOME"
        PENALTY_INCOME_LEDGER_NAME = "Penalty Income"

        # -------------------------------------------------
        # Create Journal Voucher
        # -------------------------------------------------

        voucher = create_voucher(
            voucher_type="Journal",
            voucher_mode="Journal",
            narration=f"Penalty posting - {loan_number}",
            amount=penalty_amount,
            created_by=data.get(
                "created_by",
                "admin"
            ),
            from_id=data.get(
                "created_by",
                "admin"
            ),
            entries=[
                {
                    "ledger_id": PENALTY_RECEIVABLE_LEDGER_ID,
                    "ledger_name": PENALTY_RECEIVABLE_LEDGER_NAME,
                    "narration": f"Penalty receivable - {loan_number}",
                    "debit": penalty_amount,
                    "credit": 0
                },
                {
                    "ledger_id": PENALTY_INCOME_LEDGER_ID,
                    "ledger_name": PENALTY_INCOME_LEDGER_NAME,
                    "narration": f"Penalty income - {loan_number}",
                    "debit": 0,
                    "credit": penalty_amount
                }
            ]
        )

        # -------------------------------------------------
        # Save Penalty History
        # -------------------------------------------------

        penalty_collection.insert_one({
            "loan_id": loan["_id"],
            "loan_number": loan_number,
            "customer_id": loan["customer_id"],
            "due_date": emi["due_date"],
            "posting_date": posting_date,
            "delay_days": delay_days,
            "penalty_type": penalty_type,
            "penalty_value": penalty_value,
            "penalty_amount": penalty_amount,
            "status": "UNPAID",
            "voucher_id": voucher["_id"],
            "voucher_number": voucher["voucher_number"],
            "created_at": datetime.utcnow()
        })

        # -------------------------------------------------
        # Update Loan
        # -------------------------------------------------

        current_penalty = float(
            loan.get(
                "penalty_outstanding",
                0
            )
        )

        new_penalty_outstanding = round(
            current_penalty +
            penalty_amount,
            2
        )

        loan_collection.update_one(
            {
                "_id": loan["_id"]
            },
            {
                "$inc": {
                    "penalty_outstanding": penalty_amount
                },
                "$set": {
                    "updated_at": datetime.utcnow()
                }
            }
        )

        return jsonify({
            "success": True,
            "message": "Penalty posted successfully",
            "loan_number": loan_number,
            "due_date": emi["due_date"],
            "posting_date": posting_date.strftime(
                "%Y-%m-%d"
            ),
            "delay_days": delay_days,
            "penalty_type": penalty_type,
            "penalty_value": penalty_value,
            "penalty_amount": penalty_amount,
            "penalty_outstanding": new_penalty_outstanding,
            "voucher_id": voucher["_id"],
            "voucher_number": voucher["voucher_number"]
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@localprime_bp.route("/loan-closure-list", methods=["GET"])
def loan_closure_list():

    try:

        loans = loan_collection.find({
            "loan_status": "DISBURSED",
            "outstanding_principal": 0,
            "interest_outstanding": {
                "$in": [0, 0.0, None]
            },
            "penalty_outstanding": {
                "$in": [0, 0.0, None]
            }
        })

        data = []

        for loan in loans:

            # Check unpaid EMI
            unpaid_emi = emi_due_collection.count_documents({
                "loan_number": loan["loan_number"],
                "status": "UNPAID"
            })

            if unpaid_emi > 0:
                continue

            total_paid = loan.get("loan_amount", 0) \
                       + loan.get("total_interest", 0) \
                       + loan.get("penalty_paid", 0)

            data.append({

                "loan_number": loan["loan_number"],

                "customer_id": loan["customer_id"],

                "loan_amount": loan["loan_amount"],

                "interest_rate": loan["interest_rate"],

                "frequency": loan["frequency"],

                "sanction_date": loan.get("sanction_date"),

                "disbursement_date": loan.get("disbursement_date"),

                "outstanding_principal": loan.get("outstanding_principal", 0),

                "interest_outstanding": loan.get("interest_outstanding", 0),

                "penalty_outstanding": loan.get("penalty_outstanding", 0),

                "total_paid": total_paid,

                "eligible_for_closure": True

            })

        return jsonify({

            "success": True,

            "total_records": len(data),

            "data": data

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500



@localprime_bp.route("/loan-closure", methods=["POST"])
def loan_closure():

    try:

        data = request.get_json()

        loan_number = data.get("loan_number")
        closure_date = data.get(
            "closure_date",
            datetime.now().strftime("%Y-%m-%d")
        )
        closed_by = data.get("closed_by", "SYSTEM")
        remarks = data.get("remarks", "")

        if not loan_number:
            return jsonify({
                "success": False,
                "message": "loan_number is required"
            }), 400

        loan = loan_collection.find_one({
            "loan_number": loan_number
        })

        if not loan:
            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        if loan["loan_status"] == "CLOSED":
            return jsonify({
                "success": False,
                "message": "Loan already closed"
            }), 400

        if loan["loan_status"] != "DISBURSED":
            return jsonify({
                "success": False,
                "message": "Only disbursed loans can be closed"
            }), 400

        outstanding_principal = float(
            loan.get("outstanding_principal", 0)
        )

        interest_outstanding = float(
            loan.get("interest_outstanding", 0)
        )

        penalty_outstanding = float(
            loan.get("penalty_outstanding", 0)
        )

        if outstanding_principal > 0:
            return jsonify({
                "success": False,
                "message": "Outstanding principal exists"
            }), 400

        if interest_outstanding > 0:
            return jsonify({
                "success": False,
                "message": "Outstanding interest exists"
            }), 400

        if penalty_outstanding > 0:
            return jsonify({
                "success": False,
                "message": "Outstanding penalty exists"
            }), 400

        unpaid_emi = emi_due_collection.count_documents({

            "loan_number": loan_number,

            "status": "UNPAID"

        })

        if unpaid_emi > 0:

            return jsonify({
                "success": False,
                "message": "Unpaid EMI exists"
            }), 400

        loan_collection.update_one(

            {
                "_id": loan["_id"]
            },

            {
                "$set": {

                    "loan_status": "CLOSED",

                    "closure_date": closure_date,

                    "closed_by": closed_by,

                    "closure_remarks": remarks,

                    "next_interest_date": None,

                    "updated_at": datetime.utcnow()

                }

            }

        )

        return jsonify({

            "success": True,

            "message": "Loan closed successfully",

            "loan_number": loan_number,

            "loan_status": "CLOSED",

            "closure_date": closure_date,

            "closed_by": closed_by

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,

            "message": str(e)

        }), 500













# =========================================================
# HELPER
# =========================================================

def serialize_value(value):

    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")

    return value


def serialize_document(doc):

    if not doc:
        return None

    result = {}

    for key, value in doc.items():
        result[key] = serialize_value(value)

    return result


# =========================================================
# GET NEXT DUE DATE
# =========================================================

def get_next_due_date(current_date, frequency):

    frequency = frequency.lower()

    if frequency == "daily":
        return current_date + relativedelta(days=1)

    elif frequency == "weekly":
        return current_date + relativedelta(weeks=1)

    elif frequency == "fortnightly":
        return current_date + relativedelta(weeks=2)

    elif frequency == "monthly":
        return current_date + relativedelta(months=1)

    else:
        raise ValueError(
            "Frequency must be daily, weekly, fortnightly or monthly"
        )


# =========================================================
# 1. CREATE COMPLETE REPAYMENT SCHEDULE
# =========================================================

@localprime_bp.route("/repayment-schedule", methods=["POST"])
def create_repayment_schedule():

    try:

        data = request.get_json(silent=True) or {}

        loan_number = data.get("loan_number")
        first_installment_date = data.get(
            "first_installment_date"
        )

        if not loan_number:
            return jsonify({
                "success": False,
                "message": "loan_number is required"
            }), 400

        if not first_installment_date:
            return jsonify({
                "success": False,
                "message": "first_installment_date is required"
            }), 400

        # -------------------------------------------------
        # DATE
        # -------------------------------------------------

        try:

            current_date = datetime.strptime(
                first_installment_date,
                "%Y-%m-%d"
            )

        except ValueError:

            return jsonify({
                "success": False,
                "message": "first_installment_date must be YYYY-MM-DD"
            }), 400

        # -------------------------------------------------
        # FIND LOAN
        # -------------------------------------------------

        loan = loan_collection.find_one({
            "loan_number": loan_number
        })

        if not loan:

            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        # -------------------------------------------------
        # VALIDATE STATUS
        # -------------------------------------------------

        if loan.get("loan_status") != "DISBURSED":

            return jsonify({
                "success": False,
                "message": "Repayment schedule can be generated only for disbursed loan"
            }), 400

        # -------------------------------------------------
        # CHECK EXISTING SCHEDULE
        # -------------------------------------------------

        existing = emi_due_collection.find_one({
            "loan_number": loan_number
        })

        if existing:

            return jsonify({
                "success": False,
                "message": "Repayment schedule already exists"
            }), 400

        # -------------------------------------------------
        # LOAN DATA
        # -------------------------------------------------

        customer_id = loan.get("customer_id")

        tenure = int(
            loan.get("tenure", 0)
        )

        installment = float(
            loan.get("installment", 0)
        )

        interest_rate = float(
            loan.get("interest_rate", 0)
        )

        frequency = loan.get(
            "frequency",
            "monthly"
        ).lower()

        interest_type = loan.get(
            "interest_type",
            "reducing"
        ).lower()

        outstanding_principal = float(
            loan.get(
                "outstanding_principal",
                loan.get("loan_amount", 0)
            )
        )

        if tenure <= 0:

            return jsonify({
                "success": False,
                "message": "Invalid loan tenure"
            }), 400

        if installment <= 0:

            return jsonify({
                "success": False,
                "message": "Invalid installment amount"
            }), 400

        # -------------------------------------------------
        # PERIODS
        # -------------------------------------------------

        periods_map = {
            "daily": 365,
            "weekly": 52,
            "fortnightly": 26,
            "monthly": 12
        }

        if frequency not in periods_map:

            return jsonify({
                "success": False,
                "message": "Invalid frequency"
            }), 400

        periods_per_year = periods_map[frequency]

        period_rate = (
            interest_rate /
            (periods_per_year * 100)
        )

        # -------------------------------------------------
        # GENERATE
        # -------------------------------------------------

        schedule = []

        balance = outstanding_principal

        for i in range(1, tenure + 1):

            # ---------------------------------------------
            # INTEREST
            # ---------------------------------------------

            if interest_type == "reducing":

                interest_due = (
                    balance *
                    period_rate
                )

                principal_due = (
                    installment -
                    interest_due
                )

            else:

                interest_due = (
                    loan.get(
                        "total_interest",
                        0
                    ) / tenure
                )

                principal_due = (
                    loan.get(
                        "loan_amount",
                        0
                    ) / tenure
                )

            # ---------------------------------------------
            # LAST EMI
            # ---------------------------------------------

            if i == tenure:

                principal_due = balance

                installment_amount = (
                    principal_due +
                    interest_due
                )

            else:

                installment_amount = installment

            # ---------------------------------------------
            # ROUND
            # ---------------------------------------------

            interest_due = round(
                max(interest_due, 0),
                2
            )

            principal_due = round(
                max(principal_due, 0),
                2
            )

            installment_amount = round(
                installment_amount,
                2
            )

            # ---------------------------------------------
            # NEW BALANCE
            # ---------------------------------------------

            balance = round(
                max(
                    balance -
                    principal_due,
                    0
                ),
                2
            )

            # ---------------------------------------------
            # INSERT
            # ---------------------------------------------

            emi_doc = {

                "loan_id": loan["_id"],

                "loan_number":
                    loan_number,

                "customer_id":
                    customer_id,

                "emi_number":
                    i,

                "due_date":
                    current_date.strftime(
                        "%Y-%m-%d"
                    ),

                "installment":
                    installment_amount,

                "principal_due":
                    principal_due,

                "interest_due":
                    interest_due,

                "penalty_due":
                    0,

                "principal_paid":
                    0,

                "interest_paid":
                    0,

                "penalty_paid":
                    0,

                "payment_amount":
                    0,

                "pending_amount":
                    installment_amount,

                "remaining_balance":
                    balance,

                "interest_rate":
                    interest_rate,

                "frequency":
                    frequency,

                "interest_type":
                    interest_type,

                "status":
                    "UNPAID",

                "created_at":
                    datetime.utcnow(),

                "updated_at":
                    datetime.utcnow()
            }

            result = emi_due_collection.insert_one(
                emi_doc
            )

            emi_doc["_id"] = result.inserted_id

            schedule.append(
                serialize_document(
                    emi_doc
                )
            )

            # ---------------------------------------------
            # NEXT DATE
            # ---------------------------------------------

            current_date = get_next_due_date(
                current_date,
                frequency
            )

        return jsonify({

            "success": True,

            "message":
                "Repayment schedule generated successfully",

            "loan_number":
                loan_number,

            "total_emi":
                len(schedule),

            "schedule":
                schedule

        }), 201

    except Exception as e:

        return jsonify({

            "success": False,
            "message": str(e)

        }), 500


# =========================================================
# 2. COMPLETE REPAYMENT SCHEDULE
# =========================================================

@localprime_bp.route(
    "/repayment-schedule/<loan_number>",
    methods=["GET"]
)
def get_repayment_schedule(loan_number):

    try:

        loan = loan_collection.find_one({
            "loan_number": loan_number
        })

        if not loan:

            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        emis = list(
            emi_due_collection.find(
                {
                    "loan_number":
                        loan_number
                }
            ).sort(
                "emi_number",
                1
            )
        )

        today = datetime.now().strftime(
            "%Y-%m-%d"
        )

        data = []

        total_due = 0
        total_paid = 0
        total_pending = 0

        paid_emi = 0
        partial_emi = 0
        unpaid_emi = 0
        overdue_emi = 0

        for emi in emis:

            installment = float(
                emi.get(
                    "installment",
                    0
                )
            )

            paid_amount = float(
                emi.get(
                    "payment_amount",
                    0
                )
            )

            penalty = float(
                emi.get(
                    "penalty_due",
                    0
                )
            )

            pending = max(
                installment +
                penalty -
                paid_amount,
                0
            )

            status = emi.get(
                "status",
                "UNPAID"
            )

            due_date = emi.get(
                "due_date"
            )

            # ------------------------------------------------
            # AUTOMATIC STATUS
            # ------------------------------------------------

            if pending <= 0:

                status = "PAID"
                paid_emi += 1

            elif paid_amount > 0:

                status = "PARTIAL"
                partial_emi += 1

            elif due_date < today:

                status = "OVERDUE"
                overdue_emi += 1

            else:

                status = "UNPAID"
                unpaid_emi += 1

            total_due += (
                installment +
                penalty
            )

            total_paid += paid_amount

            total_pending += pending

            data.append({

                "emi_number":
                    emi.get("emi_number"),

                "due_date":
                    due_date,

                "installment":
                    installment,

                "principal_due":
                    emi.get(
                        "principal_due",
                        0
                    ),

                "interest_due":
                    emi.get(
                        "interest_due",
                        0
                    ),

                "penalty_due":
                    penalty,

                "principal_paid":
                    emi.get(
                        "principal_paid",
                        0
                    ),

                "interest_paid":
                    emi.get(
                        "interest_paid",
                        0
                    ),

                "penalty_paid":
                    emi.get(
                        "penalty_paid",
                        0
                    ),

                "paid_amount":
                    paid_amount,

                "pending_amount":
                    round(
                        pending,
                        2
                    ),

                "remaining_balance":
                    emi.get(
                        "remaining_balance",
                        0
                    ),

                "status":
                    status
            })

        # -------------------------------------------------
        # NEXT PAYMENT
        # -------------------------------------------------

        next_payment = None

        for item in data:

            if item["pending_amount"] > 0:

                next_payment = item
                break

        return jsonify({

            "success": True,

            "loan": {

                "loan_number":
                    loan_number,

                "customer_id":
                    loan.get(
                        "customer_id"
                    ),

                "loan_amount":
                    loan.get(
                        "loan_amount",
                        0
                    ),

                "interest_rate":
                    loan.get(
                        "interest_rate",
                        0
                    ),

                "interest_type":
                    loan.get(
                        "interest_type"
                    ),

                "frequency":
                    loan.get(
                        "frequency"
                    ),

                "tenure":
                    loan.get(
                        "tenure"
                    )
            },

            "summary": {

                "total_due":
                    round(
                        total_due,
                        2
                    ),

                "total_paid":
                    round(
                        total_paid,
                        2
                    ),

                "total_pending":
                    round(
                        total_pending,
                        2
                    ),

                "paid_emi":
                    paid_emi,

                "partial_emi":
                    partial_emi,

                "unpaid_emi":
                    unpaid_emi,

                "overdue_emi":
                    overdue_emi
            },

            "next_payment":
                next_payment,

            "schedule":
                data

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,
            "message": str(e)

        }), 500


# =========================================================
# 3. CUSTOMER CURRENT DUE
# =========================================================

@localprime_bp.route(
    "/customer-payment-due/<loan_number>",
    methods=["GET"]
)
def customer_payment_due(loan_number):

    try:

        loan = loan_collection.find_one({
            "loan_number": loan_number
        })

        if not loan:

            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        today = datetime.now().strftime(
            "%Y-%m-%d"
        )

        emis = list(
            emi_due_collection.find({
                "loan_number":
                    loan_number
            }).sort(
                "emi_number",
                1
            )
        )

        current_due = []

        total_due = 0

        for emi in emis:

            installment = float(
                emi.get(
                    "installment",
                    0
                )
            )

            paid = float(
                emi.get(
                    "payment_amount",
                    0
                )
            )

            penalty = float(
                emi.get(
                    "penalty_due",
                    0
                )
            )

            pending = max(
                installment +
                penalty -
                paid,
                0
            )

            if pending <= 0:
                continue

            due_date = emi.get(
                "due_date"
            )

            if due_date <= today:

                current_due.append({

                    "emi_number":
                        emi.get(
                            "emi_number"
                        ),

                    "due_date":
                        due_date,

                    "installment":
                        installment,

                    "principal_due":
                        emi.get(
                            "principal_due",
                            0
                        ),

                    "interest_due":
                        emi.get(
                            "interest_due",
                            0
                        ),

                    "penalty_due":
                        penalty,

                    "paid_amount":
                        paid,

                    "pending_amount":
                        round(
                            pending,
                            2
                        ),

                    "status":
                        "OVERDUE"
                        if due_date < today
                        else "DUE"
                })

                total_due += pending

        return jsonify({

            "success": True,

            "loan_number":
                loan_number,

            "customer_id":
                loan.get(
                    "customer_id"
                ),

            "date":
                today,

            "total_due":
                round(
                    total_due,
                    2
                ),

            "emi_count":
                len(current_due),

            "data":
                current_due

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,
            "message": str(e)

        }), 500


# =========================================================
# 4. PAYMENT HISTORY
# =========================================================

@localprime_bp.route(
    "/customer-payment-history/<loan_number>",
    methods=["GET"]
)
def customer_payment_history(loan_number):

    try:

        loan = loan_collection.find_one({
            "loan_number":
                loan_number
        })

        if not loan:

            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        payments = list(
            payment_collection.find({
                "loan_number":
                    loan_number
            }).sort(
                "payment_date",
                -1
            )
        )

        data = []

        total_paid = 0

        for payment in payments:

            amount = float(
                payment.get(
                    "payment_amount",
                    0
                )
            )

            total_paid += amount

            data.append({

                "emi_number":
                    payment.get(
                        "emi_number"
                    ),

                "payment_date":
                    payment.get(
                        "payment_date"
                    ),

                "payment_amount":
                    amount,

                "principal_paid":
                    payment.get(
                        "principal_paid",
                        0
                    ),

                "interest_paid":
                    payment.get(
                        "interest_paid",
                        0
                    ),

                "penalty_paid":
                    payment.get(
                        "penalty_paid",
                        0
                    ),

                "payment_mode":
                    payment.get(
                        "payment_mode"
                    ),

                "transaction_id":
                    payment.get(
                        "transaction_id"
                    ),

                "voucher_number":
                    payment.get(
                        "voucher_number"
                    )
            })

        return jsonify({

            "success": True,

            "loan_number":
                loan_number,

            "total_paid":
                round(
                    total_paid,
                    2
                ),

            "total_payments":
                len(data),

            "data":
                data

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,
            "message": str(e)

        }), 500


# =========================================================
# 5. CUSTOMER LOAN SUMMARY
# =========================================================

@localprime_bp.route(
    "/customer-loan-summary/<loan_number>",
    methods=["GET"]
)
def customer_loan_summary(loan_number):

    try:

        loan = loan_collection.find_one({
            "loan_number":
                loan_number
        })

        if not loan:

            return jsonify({
                "success": False,
                "message": "Loan not found"
            }), 404

        emis = list(
            emi_due_collection.find({
                "loan_number":
                    loan_number
            })
        )

        total_due = 0
        total_paid = 0

        principal_due = 0
        interest_due = 0

        principal_paid = 0
        interest_paid = 0

        penalty_due = 0
        penalty_paid = 0

        paid_count = 0
        partial_count = 0
        overdue_count = 0
        unpaid_count = 0

        today = datetime.now().strftime(
            "%Y-%m-%d"
        )

        next_payment = None

        for emi in emis:

            installment = float(
                emi.get(
                    "installment",
                    0
                )
            )

            payment = float(
                emi.get(
                    "payment_amount",
                    0
                )
            )

            emi_penalty = float(
                emi.get(
                    "penalty_due",
                    0
                )
            )

            pending = max(
                installment +
                emi_penalty -
                payment,
                0
            )

            total_due += (
                installment +
                emi_penalty
            )

            total_paid += payment

            principal_due += float(
                emi.get(
                    "principal_due",
                    0
                )
            )

            interest_due += float(
                emi.get(
                    "interest_due",
                    0
                )
            )

            principal_paid += float(
                emi.get(
                    "principal_paid",
                    0
                )
            )

            interest_paid += float(
                emi.get(
                    "interest_paid",
                    0
                )
            )

            penalty_due += emi_penalty

            penalty_paid += float(
                emi.get(
                    "penalty_paid",
                    0
                )
            )

            if pending <= 0:

                paid_count += 1

            elif payment > 0:

                partial_count += 1

            elif emi.get(
                "due_date"
            ) < today:

                overdue_count += 1

            else:

                unpaid_count += 1

            if (
                pending > 0
                and next_payment is None
            ):

                next_payment = {

                    "emi_number":
                        emi.get(
                            "emi_number"
                        ),

                    "due_date":
                        emi.get(
                            "due_date"
                        ),

                    "amount":
                        round(
                            pending,
                            2
                        )
                }

        total_pending = max(
            total_due -
            total_paid,
            0
        )

        return jsonify({

            "success": True,

            "loan_number":
                loan_number,

            "customer_id":
                loan.get(
                    "customer_id"
                ),

            "summary": {

                "loan_amount":
                    loan.get(
                        "loan_amount",
                        0
                    ),

                "total_due":
                    round(
                        total_due,
                        2
                    ),

                "total_paid":
                    round(
                        total_paid,
                        2
                    ),

                "total_pending":
                    round(
                        total_pending,
                        2
                    ),

                "principal_due":
                    round(
                        principal_due,
                        2
                    ),

                "principal_paid":
                    round(
                        principal_paid,
                        2
                    ),

                "principal_pending":
                    round(
                        principal_due -
                        principal_paid,
                        2
                    ),

                "interest_due":
                    round(
                        interest_due,
                        2
                    ),

                "interest_paid":
                    round(
                        interest_paid,
                        2
                    ),

                "interest_pending":
                    round(
                        interest_due -
                        interest_paid,
                        2
                    ),

                "penalty_due":
                    round(
                        penalty_due,
                        2
                    ),

                "penalty_paid":
                    round(
                        penalty_paid,
                        2
                    ),

                "penalty_pending":
                    round(
                        penalty_due -
                        penalty_paid,
                        2
                    ),

                "paid_emi":
                    paid_count,

                "partial_emi":
                    partial_count,

                "overdue_emi":
                    overdue_count,

                "unpaid_emi":
                    unpaid_count
            },

            "next_payment":
                next_payment,

            "loan_status":
                loan.get(
                    "loan_status"
                )

        }), 200

    except Exception as e:

        return jsonify({

            "success": False,
            "message": str(e)

        }), 500

@localprime_bp.route("/emi-dues", methods=["GET"])
def emi_dues_list():
    try:
        loan_number = request.args.get("loan_number")
        
        if not loan_number:
            return jsonify({
                "success": False,
                "message": "loan_number is required"
            }), 400
            
        emis = emi_due_collection.find({"loan_number": loan_number}).sort("emi_number", 1)
        
        data = []
        for emi in emis:
            data.append({
                "emi_number": emi.get("emi_number"),
                "due_date": emi.get("due_date"),
                "installment": emi.get("installment"),
                "principal_due": emi.get("principal_due"),
                "interest_due": emi.get("interest_due"),
                "remaining_balance": emi.get("remaining_balance"),
                "status": emi.get("status"),
                "paid_date": emi.get("paid_date"),
                "principal_paid": emi.get("principal_paid", 0),
                "interest_paid": emi.get("interest_paid", 0),
                "penalty_paid": emi.get("penalty_paid", 0),
                "payment_amount": emi.get("payment_amount", 0)
            })
            
        return jsonify({
            "success": True,
            "total_records": len(data),
            "data": data
        }), 200
        
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
