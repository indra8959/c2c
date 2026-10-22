import os
import math
import requests

from datetime import datetime, date
from zoneinfo import ZoneInfo
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
from bson.errors import InvalidId


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

MONGO_URI = os.getenv(
    "MONGO_URI",
    'mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
)
WHATSAPP_ACCESS_TOKEN = os.getenv(
    "WHATSAPP_ACCESS_TOKEN",
    'EAAOOnx48PYMBS5driPPmNxMVyOpEPZC2BDLjSgotkZCT1dpNB5fW0Sd5WXjuUHE2R9vT40K2tZAzBapN6oOkjpcZB8OqmlCZAa1gT161EGU95iccwdLJzOfH6n4MOrvdFJq08dvsskZB3q0xLanc5hZBi0QZA5fSfRlRkL0cWWMpCJeyHAvMSjDMhSmORPZCw4kZBQFeVolcRdTdvklRiLFV7eW4uCvaUUhZAxRIZBjrvcY8MTiV1sKLNYDFuWZCMOsxhnCFbmlOLFZAyNpgJi4Et4yRhZCDuOw'
)
WHATSAPP_PHONE_NUMBER_ID = os.getenv(
    "WHATSAPP_PHONE_NUMBER_ID",
    "593779133824503"
)
WHATSAPP_API_VERSION = os.getenv(
    "WHATSAPP_API_VERSION",
    "v25.0"
)

if not MONGO_URI:
    raise RuntimeError("MONGO_URI environment variable is required")

client = MongoClient(MONGO_URI)
db = client["app_db"]

# Database Collections (Aligned with c2c_app.py)
doctors = db["doctors"]
attendance = db["attendance"]               # Primary attendance collection in c2c_app.py
leave_requests = db["leave_requests"]       # Primary leave requests collection in c2c_app.py
shifts = db["shifts"]                       # Active shifts
attendance_locations = db["attendance_locations"]  # GPS audit logs

# Backward-compatible aliases
attendance_records = attendance
attendance_requests = db["attendance_requests"]

# Ensure Database Indexes match c2c_app.py
try:
    # One attendance record per staff per doctor per day
    attendance.create_index(
        [
            ("doctor_id", ASCENDING),
            ("staff_id", ASCENDING),
            ("date", ASCENDING)
        ],
        unique=True
    )
    attendance.create_index(
        [("doctor_id", ASCENDING), ("date", DESCENDING)]
    )
    attendance.create_index(
        [("whatsapp_message_id", ASCENDING)],
        unique=True,
        partialFilterExpression={
            "whatsapp_message_id": {"$type": "string"}
        }
    )

    # Leave requests indexes
    leave_requests.create_index(
        [
            ("doctor_id", ASCENDING),
            ("staff_id", ASCENDING),
            ("start_date", ASCENDING)
        ]
    )
    leave_requests.create_index(
        [("whatsapp_message_id", ASCENDING)],
        unique=True,
        partialFilterExpression={
            "whatsapp_message_id": {"$type": "string"}
        }
    )
except Exception as e:
    print("Warning creating attendance indexes:", str(e))

IST = ZoneInfo("Asia/Kolkata")
RADIUS_METERS = 100


# --------------------------------------------------
# COMMON HELPERS (Aligned with c2c_app.py)
# --------------------------------------------------

def now_ist():
    return datetime.now(IST)


def calculate_distance(lat1, lon1, lat2, lon2):
    """Return the distance between two GPS points in meters."""

    lat1, lon1, lat2, lon2 = map(
        float, (lat1, lon1, lat2, lon2)
    )

    if not (
        -90 <= lat1 <= 90
        and -180 <= lon1 <= 180
        and -90 <= lat2 <= 90
        and -180 <= lon2 <= 180
    ):
        raise ValueError("Invalid GPS coordinates")

    earth_radius = 6371000

    lat1, lon1, lat2, lon2 = map(
        math.radians, (lat1, lon1, lat2, lon2)
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    a = max(0.0, min(1.0, a))

    return earth_radius * 2 * math.atan2(
        math.sqrt(a), math.sqrt(1 - a)
    )


def get_staff_name(staff):
    """Derive staff name using the exact precedence from c2c_app.py."""
    if not staff or not isinstance(staff, dict):
        return ""
    return (
        staff.get("name")
        or staff.get("doctor_name")
        or staff.get("staff_name")
        or staff.get("FirstName")
        or ""
    )


def calculate_working_hours(check_in, check_out):
    """Calculate working hours between check_in and check_out ISO strings."""
    if not check_in or not check_out:
        return None

    try:
        start = datetime.fromisoformat(str(check_in))
        end = datetime.fromisoformat(str(check_out))
        seconds = max(0, (end - start).total_seconds())
        return round(seconds / 3600, 2)
    except Exception:
        return None


def safe_staff_info(staff):
    return {
        "_id": str(staff["_id"]),
        "staffId": staff.get("staffId"),
        "name": get_staff_name(staff),
        "phone": staff.get("phone"),
        "doctorId": staff.get("doctorId"),
        "role": staff.get("role")
    }


def safe_doctor_info(doctor):
    return {
        "_id": str(doctor["_id"]),
        "name": doctor.get("name"),
        "phone": doctor.get("phone"),
        "email": doctor.get("email"),
        "speciality": doctor.get("speciality")
    }


def get_doctor(doctor_id):
    """The supplied ID is the doctor's MongoDB ObjectId."""
    try:
        return doctors.find_one({
            "_id": ObjectId(str(doctor_id)),
            "role": "doctor"
        })
    except (InvalidId, TypeError):
        return None


def get_staff(doctor_id, mobile_number):
    """
    Find staff in the doctors collection with flexible phone format matching
    (handles +91, 91, or 10-digit mobile numbers).
    """
    if not mobile_number:
        return None

    raw_phone = str(mobile_number).strip().replace("+", "")
    phone_candidates = [raw_phone]
    if len(raw_phone) >= 10:
        last10 = raw_phone[-10:]
        phone_candidates.extend([last10, f"91{last10}", f"+91{last10}"])
    phone_candidates = list(dict.fromkeys(phone_candidates))

    return doctors.find_one({
        "role": "staff",
        "doctorId": str(doctor_id),
        "phone": {"$in": phone_candidates}
    })


# --------------------------------------------------
# WHATSAPP CLOUD API
# --------------------------------------------------

def send_whatsapp_payload(payload):
    if not WHATSAPP_ACCESS_TOKEN:
        raise RuntimeError("WhatsApp access token is not configured")

    url = (
        f"https://graph.facebook.com/"
        f"{WHATSAPP_API_VERSION}/"
        f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        timeout=20
    )

    try:
        result = response.json()
    except ValueError:
        result = {"response": response.text}

    if not response.ok:
        print("WhatsApp API error:", response.status_code, result)
        raise RuntimeError(
            f"WhatsApp API returned HTTP {response.status_code}: "
            f"{result.get('error', {}).get('message', result.get('error', {}).get('code', 'unknown error'))}"
        )

    return result


def send_whatsapp_text(mobile_number, text):
    """Send a plain text message to the staff member."""
    payload = {
        "messaging_product": "whatsapp",
        "to": str(mobile_number),
        "type": "text",
        "text": {
            "body": text
        }
    }
    return send_whatsapp_payload(payload)


def send_checkout_button(mobile_number, attendance_id, check_in_time):
    """Send an interactive reply button offering Check Out."""
    payload = {
        "messaging_product": "whatsapp",
        "to": str(mobile_number),
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": (
                    "📍 Location verified inside the clinic.\n"
                    f"Today's Check-in time: {check_in_time}.\n\n"
                    "Would you like to complete your Check-Out now?"
                )
            },
            "footer": {
                "text": "Tap button to check out"
            },
            "action": {
                "buttons": [
                    {
                        "type": "reply",
                        "reply": {
                            "id": f"checkout_{str(attendance_id)}",
                            "title": "Check Out"
                        }
                    }
                ]
            }
        }
    }
    return send_whatsapp_payload(payload)


def send_outside_location_message(
    mobile_number,
    distance,
    staff_id=None,
    is_checked_in=False,
    check_in_time=None
):
    """
    Send interactive reply buttons when staff is outside clinic radius.
    If already checked in today, offers Official Duty Check-Out.
    """
    if is_checked_in:
        body_text = (
            "📍 You are outside the permitted work location.\n"
            f"Today's Check-in time: {check_in_time or 'Recorded'}.\n\n"
            "Would you like to request official duty check-out?"
        )
        buttons = [
            {
                "type": "reply",
                "reply": {
                    "id": "a_official_duty",
                    "title": "Duty Check Out"
                }
            }
        ]
        footer_text = "Tap button to request check-out"
    else:
        body_text = (
            "📍 You are outside the permitted work location.\n\n"
            "Choose an option:"
        )
        buttons = [
            {
                "type": "reply",
                "reply": {
                    "id": "a_official_duty",
                    "title": "Apply Official Duty"
                }
            },
            {
                "type": "reply",
                "reply": {
                    "id": "a_leave_request",
                    "title": "Apply for Leave"
                }
            }
        ]
        footer_text = "Choose an option:"

    payload = {
        "messaging_product": "whatsapp",
        "to": str(mobile_number),
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {
                "text": body_text
            },
            "footer": {
                "text": footer_text
            },
            "action": {
                "buttons": buttons
            }
        }
    }

    return send_whatsapp_payload(payload)


def send_attendance_template(mobile_number):
    """Fallback template when 24h WhatsApp window has expired."""
    template_name = os.getenv("ATTENDANCE_TEMPLATE_NAME")
    template_language = os.getenv(
        "ATTENDANCE_TEMPLATE_LANGUAGE", "en"
    )

    if not template_name:
        raise RuntimeError(
            "24-hour window expired and "
            "ATTENDANCE_TEMPLATE_NAME is not configured"
        )

    payload = {
        "messaging_product": "whatsapp",
        "to": str(mobile_number),
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": template_language}
        }
    }

    return send_whatsapp_payload(payload)


def notify_outside_location(
    mobile_number,
    distance,
    staff_id=None,
    is_checked_in=False,
    check_in_time=None
):
    try:
        return send_outside_location_message(
            mobile_number,
            distance,
            staff_id=staff_id,
            is_checked_in=is_checked_in,
            check_in_time=check_in_time
        )
    except RuntimeError as exc:
        if "131047" not in str(exc):
            raise
        return send_attendance_template(mobile_number)


def send_approval_request_to_doctor(doctor_id, request_id, request_doc):
    """
    Send interactive Approve / Reject buttons to doctor's WhatsApp
    whenever a staff member requests Official Duty or Leave.
    """
    try:
        doctor = get_doctor(doctor_id)
        if not doctor or not doctor.get("phone"):
            print(f"[send_approval_request_to_doctor] Doctor {doctor_id} has no phone configured.")
            return None

        raw_phone = str(doctor.get("phone")).strip().replace("+", "")
        if len(raw_phone) == 10:
            doctor_phone = f"91{raw_phone}"
        else:
            doctor_phone = raw_phone

        staff_name = request_doc.get("staff_name") or "Staff"
        staff_phone = request_doc.get("mobile_number") or ""
        req_type = request_doc.get("request_type")
        duty_action = request_doc.get("duty_action")
        shift_name = request_doc.get("shift_name") or "Shift"
        date_str = request_doc.get("start_date") or ""

        if req_type == "official_duty":
            action_label = "Check-Out" if duty_action == "check_out" else "Check-In"
            body_text = (
                f"📋 *Staff Duty Request*\n\n"
                f"👤 Staff: {staff_name}\n"
                f"📞 Mobile: {staff_phone}\n"
                f"📌 Type: Official Duty ({action_label})\n"
                f"⏰ Shift: {shift_name}\n"
                f"📅 Date: {date_str}\n\n"
                "Please approve or reject this request:"
            )
        else:
            end_date = request_doc.get("end_date") or date_str
            date_display = date_str if date_str == end_date else f"{date_str} to {end_date}"
            reason = request_doc.get("reason") or "Personal"
            body_text = (
                f"📋 *Staff Leave Request*\n\n"
                f"👤 Staff: {staff_name}\n"
                f"📞 Mobile: {staff_phone}\n"
                f"📌 Type: Leave Application\n"
                f"📅 Date: {date_display}\n"
                f"📝 Reason: {reason}\n\n"
                "Please approve or reject this request:"
            )

        buttons = [
            {
                "type": "reply",
                "reply": {
                    "id": f"appr_{str(request_id)}",
                    "title": "Approve"
                }
            },
            {
                "type": "reply",
                "reply": {
                    "id": f"rej_{str(request_id)}",
                    "title": "Reject"
                }
            }
        ]

        payload = {
            "messaging_product": "whatsapp",
            "to": str(doctor_phone),
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body_text
                },
                "footer": {
                    "text": "Tap to Approve or Reject"
                },
                "action": {
                    "buttons": buttons
                }
            }
        }

        res = send_whatsapp_payload(payload)
        print(f"[send_approval_request_to_doctor] Approval request sent to Doctor ({doctor_phone}):", res)
        return res
    except Exception as e:
        print(f"[send_approval_request_to_doctor] Failed to send approval to doctor: {e}")
        return None


# --------------------------------------------------
# PROCESS LOCATION MESSAGE
# --------------------------------------------------

def process_location(message, doctor_id):
    mobile_number = message.get("from")
    location = message.get("location", {})

    latitude = location.get("latitude")
    longitude = location.get("longitude")

    if not mobile_number or latitude is None or longitude is None:
        return {"error": "Mobile number or location missing"}, 400

    doctor = get_doctor(doctor_id)
    if not doctor:
        return {"error": "Doctor not found"}, 404

    staff = get_staff(doctor_id, mobile_number)
    if not staff:
        return {"error": "Staff not found"}, 404

    doctor_lat = doctor.get("latitude")
    doctor_lon = doctor.get("longitude")

    if doctor_lat is None or doctor_lon is None:
        return {"error": "Doctor location not configured"}, 400

    try:
        distance = calculate_distance(
            doctor_lat,
            doctor_lon,
            latitude,
            longitude
        )
    except (TypeError, ValueError):
        return {"error": "Invalid GPS coordinates"}, 400

    status = "inside" if distance <= RADIUS_METERS else "outside"
    current = now_ist()
    staff_id = str(staff["_id"])
    today = current.date().isoformat()

    # Check existing attendance in the aligned 'attendance' collection
    existing = attendance.find_one({
        "doctor_id": str(doctor_id),
        "staff_id": staff_id,
        "date": today
    })

    # Log location check in audit collection
    result = {
        "mobile_number": mobile_number,
        "staff_info": safe_staff_info(staff),
        "doctor_info": safe_doctor_info(doctor),
        "staff_latitude": float(latitude),
        "staff_longitude": float(longitude),
        "doctor_latitude": float(doctor_lat),
        "doctor_longitude": float(doctor_lon),
        "distance_meters": round(distance, 2),
        "status": status,
        "created_at": current.isoformat()
    }
    attendance_locations.insert_one(result.copy())

    if status == "inside":
        if existing and not existing.get("check_out"):
            # Already checked in today, offer Check Out!
            try:
                check_in_raw = existing.get("check_in", "")
                try:
                    check_in_dt = datetime.fromisoformat(str(check_in_raw))
                    check_in_display = check_in_dt.strftime("%I:%M %p")
                except Exception:
                    check_in_display = str(check_in_raw)

                whatsapp_result = send_checkout_button(
                    mobile_number=mobile_number,
                    attendance_id=str(existing["_id"]),
                    check_in_time=check_in_display
                )
                return {
                    "success": True,
                    "status": "inside",
                    "action": "checkout_offered",
                    "distance_meters": round(distance, 2),
                    "message": "Already checked in. Checkout option sent.",
                    "whatsapp_result": whatsapp_result
                }, 200
            except Exception as e:
                print("Failed to send checkout button:", str(e))
                return {
                    "success": False,
                    "status": "inside",
                    "error": "Failed to send checkout button"
                }, 502

        elif existing and existing.get("check_out"):
            # Already checked in and checked out for today
            try:
                hours = calculate_working_hours(
                    existing.get("check_in"),
                    existing.get("check_out")
                )
                msg = f"Your attendance and check-out for today are already completed (Working hours: {hours or 0} hrs)."
                whatsapp_result = send_whatsapp_text(mobile_number, msg)
                return {
                    "success": True,
                    "status": "inside",
                    "action": "already_completed",
                    "message": msg,
                    "whatsapp_result": whatsapp_result
                }, 200
            except Exception as e:
                return {"success": False, "error": str(e)}, 502

        else:
            # Not checked in yet -> Send active shift buttons
            try:
                whatsapp_result = send_shift_buttons(
                    mobile_number=mobile_number,
                    doctor_id=doctor_id
                )

                return {
                    "success": True,
                    "status": "inside",
                    "action": "shift_selection_sent",
                    "distance_meters": round(distance, 2),
                    "message": "Location verified. Shift buttons sent.",
                    "whatsapp_result": whatsapp_result
                }, 200

            except Exception as e:
                print("Failed to send shift buttons:", str(e))
                return {
                    "success": False,
                    "status": "inside",
                    "distance_meters": round(distance, 2),
                    "error": "Location verified but failed to send shift buttons"
                }, 502

    else:
        # OUTSIDE CLINIC (> 50m)
        if existing and existing.get("check_out"):
            # Already checked in and checked out for today
            try:
                hours = calculate_working_hours(
                    existing.get("check_in"),
                    existing.get("check_out")
                )
                msg = f"Your attendance and check-out for today are already completed (Working hours: {hours or 0} hrs)."
                whatsapp_result = send_whatsapp_text(mobile_number, msg)
                return {
                    "success": True,
                    "status": "outside",
                    "action": "already_completed",
                    "message": msg,
                    "whatsapp_result": whatsapp_result
                }, 200
            except Exception as e:
                return {"success": False, "error": str(e)}, 502

        is_checked_in = bool(existing and not existing.get("check_out"))
        check_in_display = None
        if is_checked_in:
            check_in_raw = existing.get("check_in", "")
            try:
                check_in_dt = datetime.fromisoformat(str(check_in_raw))
                check_in_display = check_in_dt.strftime("%I:%M %p")
            except Exception:
                check_in_display = str(check_in_raw)

        try:
            whatsapp_result = notify_outside_location(
                mobile_number=mobile_number,
                distance=distance,
                staff_id=staff.get("staffId"),
                is_checked_in=is_checked_in,
                check_in_time=check_in_display
            )

            return {
                "success": True,
                "status": "outside",
                "distance_meters": round(distance, 2),
                "is_checked_in": is_checked_in,
                "message": (
                    "Outside location options sent (Duty Check Out offered)"
                    if is_checked_in
                    else "Outside location options sent"
                ),
                "whatsapp_result": whatsapp_result
            }, 200

        except Exception as e:
            print("Failed to send outside-location message:", str(e))
            return {
                "success": False,
                "status": "outside",
                "distance_meters": round(distance, 2),
                "error": "Failed to send WhatsApp message"
            }, 502


# --------------------------------------------------
# DOCTOR APPROVAL / REJECTION HANDLER
# --------------------------------------------------

def process_doctor_approval_reply(message, doctor_id, button_id):
    """
    Handle Doctor clicking 'Approve' or 'Reject' on WhatsApp.
    Marks attendance if official duty is approved, updates leave_requests,
    and notifies both Doctor and Staff on WhatsApp.
    """
    mobile_number = str(message.get("from", ""))
    is_approve = button_id.startswith("appr_")
    prefix = "appr_" if is_approve else "rej_"
    request_id = button_id[len(prefix):]

    if not ObjectId.is_valid(request_id):
        send_whatsapp_text(mobile_number, "Invalid request ID.")
        return {"status": "error", "message": "Invalid request ID"}

    req = leave_requests.find_one({"_id": ObjectId(request_id)})
    if not req:
        send_whatsapp_text(mobile_number, "Request record not found.")
        return {"status": "error", "message": "Request not found"}

    current_status = req.get("status")
    if current_status != "pending":
        msg = f"This request has already been {current_status.upper()}."
        send_whatsapp_text(mobile_number, msg)
        return {"status": "already_reviewed", "message": msg}

    doc_id = str(req.get("doctor_id") or doctor_id)
    doctor = get_doctor(doc_id)
    doctor_name = (doctor.get("name") if doctor else None) or "Doctor"
    now = now_ist()
    new_status = "approved" if is_approve else "rejected"

    # Update leave_requests document
    leave_requests.update_one(
        {"_id": ObjectId(request_id)},
        {
            "$set": {
                "status": new_status,
                "reviewed_by": str(doctor.get("_id") if doctor else doc_id),
                "reviewed_by_name": doctor_name,
                "review_remarks": f"{'Approved' if is_approve else 'Rejected'} via WhatsApp by {doctor_name}",
                "updated_at": now.isoformat()
            }
        }
    )

    # Backward compatibility with attendance_requests
    attendance_requests.update_one(
        {
            "staff_id": str(req.get("staff_id")),
            "doctor_id": doc_id,
            "status": "pending"
        },
        {
            "$set": {
                "status": new_status,
                "updated_at": now.isoformat()
            }
        }
    )

    staff_name = req.get("staff_name") or "Staff"
    staff_phone = req.get("mobile_number")
    stf_id = str(req.get("staff_id"))

    if not staff_phone:
        if ObjectId.is_valid(stf_id):
            st_doc = doctors.find_one({"_id": ObjectId(stf_id)})
            if st_doc and st_doc.get("phone"):
                staff_phone = str(st_doc.get("phone"))

    if staff_phone:
        clean_staff_phone = str(staff_phone).strip().replace("+", "")
        if len(clean_staff_phone) == 10:
            clean_staff_phone = f"91{clean_staff_phone}"
    else:
        clean_staff_phone = None

    req_type = req.get("request_type")
    duty_action = req.get("duty_action")
    target_date = req.get("start_date") or now.date().isoformat()
    shift_id = req.get("shift_id")
    shift_name = req.get("shift_name") or "Shift"

    if is_approve:
        if req_type == "official_duty" or "official duty" in str(req.get("reason", "")).lower():
            existing_att = attendance.find_one({
                "doctor_id": doc_id,
                "staff_id": stf_id,
                "date": target_date
            })

            if not duty_action or duty_action == "auto":
                if existing_att and not existing_att.get("check_out"):
                    duty_action = "check_out"
                else:
                    duty_action = "check_in"

            if duty_action == "check_out":
                check_out_time = req.get("created_at") or now.isoformat()
                if existing_att:
                    attendance.update_one(
                        {"_id": existing_att["_id"]},
                        {
                            "$set": {
                                "check_out": check_out_time,
                                "updated_at": now.isoformat(),
                                "remarks": (
                                    str(existing_att.get("remarks", ""))
                                    + f" | Official Duty Check-Out Approved ({shift_name})"
                                ).strip(" |")
                            }
                        }
                    )
                    hours = calculate_working_hours(existing_att.get("check_in"), check_out_time)
                else:
                    att_new = {
                        "doctor_id": doc_id,
                        "staff_id": stf_id,
                        "staff_name": staff_name,
                        "date": target_date,
                        "check_in": check_out_time,
                        "check_out": check_out_time,
                        "status": "present",
                        "attendance_type": "official_duty",
                        "shift_id": shift_id,
                        "shift_name": shift_name,
                        "remarks": f"Official Duty Check-Out Approved ({shift_name})",
                        "official_duty_id": str(request_id),
                        "created_at": now.isoformat(),
                        "updated_at": now.isoformat()
                    }
                    attendance.insert_one(att_new)
                    hours = 0

                if clean_staff_phone:
                    try:
                        send_whatsapp_text(
                            clean_staff_phone,
                            f"✅ *Official Duty Check-Out Approved*\n\n"
                            f"Your official duty check-out for {shift_name} has been APPROVED by {doctor_name}.\n"
                            f"Working hours: {hours or 0} hrs.\nHave a great day!"
                        )
                    except Exception as e:
                        print("Failed to notify staff:", e)

            else:
                # check_in
                check_in_time = req.get("created_at") or now.isoformat()
                if existing_att:
                    attendance.update_one(
                        {"_id": existing_att["_id"]},
                        {
                            "$set": {
                                "status": "present",
                                "attendance_type": "official_duty",
                                "shift_id": shift_id or existing_att.get("shift_id"),
                                "shift_name": shift_name or existing_att.get("shift_name"),
                                "updated_at": now.isoformat(),
                                "remarks": (
                                    str(existing_att.get("remarks", ""))
                                    + f" | Official Duty Check-In Approved ({shift_name})"
                                ).strip(" |")
                            }
                        }
                    )
                else:
                    att_new = {
                        "doctor_id": doc_id,
                        "staff_id": stf_id,
                        "staff_name": staff_name,
                        "date": target_date,
                        "check_in": check_in_time,
                        "check_out": None,
                        "status": "present",
                        "attendance_type": "official_duty",
                        "shift_id": shift_id,
                        "shift_name": shift_name,
                        "remarks": f"Official Duty Check-In Approved ({shift_name})",
                        "official_duty_id": str(request_id),
                        "created_at": now.isoformat(),
                        "updated_at": now.isoformat()
                    }
                    attendance.insert_one(att_new)

                if clean_staff_phone:
                    try:
                        send_whatsapp_text(
                            clean_staff_phone,
                            f"✅ *Official Duty Check-In Approved*\n\n"
                            f"Your official duty check-in for {shift_name} has been APPROVED by {doctor_name}.\n"
                            f"Check-in time: {now.strftime('%I:%M %p')}.\nHave a productive day!"
                        )
                    except Exception as e:
                        print("Failed to notify staff:", e)

        else:
            # Leave request approved
            if clean_staff_phone:
                try:
                    send_whatsapp_text(
                        clean_staff_phone,
                        f"✅ *Leave Application Approved*\n\n"
                        f"Your leave request for {target_date} has been APPROVED by {doctor_name}."
                    )
                except Exception as e:
                    print("Failed to notify staff:", e)

        doc_msg = f"✅ Request for *{staff_name}* ({shift_name if req_type == 'official_duty' else 'Leave'}) has been APPROVED."
        send_whatsapp_text(mobile_number, doc_msg)
        return {"status": "success", "message": doc_msg}

    else:
        # Rejected
        if clean_staff_phone:
            try:
                type_label = f"Official Duty ({'Check-Out' if duty_action == 'check_out' else 'Check-In'})" if req_type == "official_duty" else "Leave"
                send_whatsapp_text(
                    clean_staff_phone,
                    f"❌ *{type_label} Request Rejected*\n\n"
                    f"Your {type_label.lower()} request has been REJECTED by {doctor_name}."
                )
            except Exception as e:
                print("Failed to notify staff:", e)

        doc_msg = f"❌ Request for *{staff_name}* has been REJECTED."
        send_whatsapp_text(mobile_number, doc_msg)
        return {"status": "success", "message": doc_msg}


# ---------------------------------
# PROCESS BUTTON REPLY
# ---------------------------------

def process_button_reply(message, doctor_id):
    mobile_number = str(message.get("from", ""))
    message_id = message.get("id")

    interactive = message.get("interactive", {})
    button_reply = interactive.get("button_reply", {})
    list_reply = interactive.get("list_reply", {})

    button_id = button_reply.get("id") or list_reply.get("id") or ""

    # ---------------------------------
    # 0. Doctor Approval / Rejection Action
    # ---------------------------------
    if button_id.startswith("appr_") or button_id.startswith("rej_"):
        return process_doctor_approval_reply(message, doctor_id, button_id)

    staff = get_staff(doctor_id, mobile_number)
    if not staff:
        return {"status": "error", "message": "Staff not found"}

    staff_id = str(staff.get("_id"))
    staff_name = get_staff_name(staff)
    now = now_ist()
    today = now.date().isoformat()

    # ---------------------------------
    # 1. Check Out action
    # ---------------------------------
    if button_id.startswith("checkout_"):
        attendance_id = button_id[len("checkout_"):]

        if not ObjectId.is_valid(attendance_id):
            return {"status": "error", "message": "Invalid attendance ID"}

        result = attendance.update_one(
            {
                "_id": ObjectId(attendance_id),
                "check_out": None
            },
            {
                "$set": {
                    "check_out": now.isoformat(),
                    "updated_at": now.isoformat()
                }
            }
        )

        if result.matched_count == 0:
            existing = attendance.find_one({"_id": ObjectId(attendance_id)})
            if existing and existing.get("check_out"):
                msg = "Check-out is already completed for today."
            else:
                msg = "Attendance record not found."
            send_whatsapp_text(mobile_number, msg)
            return {"status": "error", "message": msg}

        rec = attendance.find_one({"_id": ObjectId(attendance_id)})
        hours = calculate_working_hours(rec.get("check_in"), rec.get("check_out"))

        msg = (
            f"✅ Check-out successful at {now.strftime('%I:%M %p')}.\n"
            f"Total working hours: {hours or 0} hrs. Have a great day!"
        )
        send_whatsapp_text(mobile_number, msg)

        return {
            "status": "success",
            "message": msg,
            "working_hours": hours
        }

    # ---------------------------------
    # 2. Official Duty button selected
    # ---------------------------------
    if button_id == "a_official_duty":
        existing_att = attendance.find_one({
            "doctor_id": str(doctor_id),
            "staff_id": staff_id,
            "date": today
        })
        is_checkout = bool(existing_att and not existing_att.get("check_out"))

        if is_checkout:
            # User already checked in: use existing shift directly!
            shift_id = existing_att.get("shift_id")
            shift_name = existing_att.get("shift_name") or "Shift"

            existing_req = leave_requests.find_one({
                "doctor_id": str(doctor_id),
                "staff_id": staff_id,
                "start_date": today,
                "status": "pending",
                "request_type": "official_duty",
                "duty_action": "check_out"
            })

            if existing_req:
                msg = f"Your Official Duty (Check-Out) request for {shift_name} is already pending."
                send_whatsapp_text(mobile_number, msg)
                return {
                    "status": "success",
                    "message": msg
                }

            duty_doc = {
                "doctor_id": str(doctor_id),
                "staff_id": staff_id,
                "staff_name": staff_name,
                "start_date": today,
                "end_date": today,
                "reason": f"Official Duty (Check-Out) applied via WhatsApp - Shift: {shift_name}",
                "request_type": "official_duty",
                "duty_action": "check_out",
                "shift_id": shift_id,
                "shift_name": shift_name,
                "mobile_number": mobile_number,
                "status": "pending",
                "reviewed_by": None,
                "review_remarks": "",
                "whatsapp_message_id": message_id,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }

            try:
                leave_requests.insert_one(duty_doc)
                attendance_requests.insert_one({
                    "staff_id": staff_id,
                    "doctor_id": str(doctor_id),
                    "shift_id": shift_id,
                    "shift_name": shift_name,
                    "request_type": "official_duty",
                    "duty_action": "check_out",
                    "attendance_date": today,
                    "status": "pending",
                    "whatsapp_message_id": message_id,
                    "created_at": now.isoformat()
                })
                # Send approval request with buttons to Doctor's WhatsApp
                send_approval_request_to_doctor(doctor_id, str(duty_doc["_id"]), duty_doc)

                msg = (
                    f"✅ Official Duty Check-Out request for {shift_name} has been sent to the doctor for approval.\n"
                    "Your check-out will be marked once approved."
                )
            except DuplicateKeyError:
                msg = "Your Official Duty request has already been recorded."

            send_whatsapp_text(mobile_number, msg)
            return {
                "status": "success",
                "message": msg
            }

        # User is NOT checked in yet: send shift options to choose for Check-In
        whatsapp_res = send_shift_buttons_for_official_duty(
            mobile_number,
            str(doctor_id),
            is_checkout=False
        )
        return {
            "status": "success",
            "message": "Official duty shift options sent.",
            "whatsapp_result": whatsapp_res
        }

    # ---------------------------------
    # 3. Leave request (Aligned with c2c_app.py leave_requests schema)
    # ---------------------------------
    if button_id == "a_leave_request":
        existing = leave_requests.find_one({
            "doctor_id": str(doctor_id),
            "staff_id": staff_id,
            "start_date": today,
            "status": "pending"
        })

        if existing:
            msg = "Your leave request is already pending."
            send_whatsapp_text(mobile_number, msg)
            return {
                "status": "success",
                "message": msg
            }

        leave_doc = {
            "doctor_id": str(doctor_id),
            "staff_id": staff_id,
            "staff_name": staff_name,
            "mobile_number": mobile_number,
            "start_date": today,
            "end_date": today,
            "reason": "Leave applied via WhatsApp",
            "request_type": "leave",
            "status": "pending",
            "reviewed_by": None,
            "review_remarks": "",
            "whatsapp_message_id": message_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }

        try:
            leave_requests.insert_one(leave_doc)
            # Duplicate into attendance_requests for backward compatibility
            attendance_requests.insert_one({
                "staff_id": staff_id,
                "doctor_id": str(doctor_id),
                "request_type": "leave",
                "attendance_date": today,
                "status": "pending",
                "whatsapp_message_id": message_id,
                "created_at": now.isoformat()
            })
            # Send approval request with buttons to Doctor's WhatsApp
            send_approval_request_to_doctor(doctor_id, str(leave_doc["_id"]), leave_doc)

            msg = "✅ Your leave request has been sent to the doctor for approval."
        except DuplicateKeyError:
            msg = "Your leave request has already been recorded."

        send_whatsapp_text(mobile_number, msg)
        return {
            "status": "success",
            "message": msg
        }

    # ---------------------------------
    # 4. Identify selected shift
    # ---------------------------------
    is_official_duty = button_id.startswith("official_shift_")
    is_normal_shift = button_id.startswith("shift_")

    if not (is_official_duty or is_normal_shift):
        return {
            "status": "error",
            "message": "Invalid button selection"
        }

    prefix = "official_shift_" if is_official_duty else "shift_"
    shift_id = button_id[len(prefix):]

    if not ObjectId.is_valid(shift_id):
        return {"status": "error", "message": "Invalid shift ID"}

    shift = shifts.find_one({
        "_id": ObjectId(shift_id),
        "doctor_id": str(doctor_id),
        "status": "active"
    })

    if not shift:
        msg = "The selected shift is not active."
        send_whatsapp_text(mobile_number, msg)
        return {
            "status": "error",
            "message": msg
        }

    shift_name = shift.get("shift_name", "Shift")

    # ---------------------------------
    # 5. Official Duty shift request:
    # ---------------------------------
    if is_official_duty:
        # Check if staff already has a check-in for today (to determine if duty is for check-in or check-out)
        existing_att = attendance.find_one({
            "doctor_id": str(doctor_id),
            "staff_id": staff_id,
            "date": today
        })
        duty_action = "check_out" if (existing_att and not existing_att.get("check_out")) else "check_in"
        action_label = "Check-Out" if duty_action == "check_out" else "Check-In"

        existing = leave_requests.find_one({
            "doctor_id": str(doctor_id),
            "staff_id": staff_id,
            "start_date": today,
            "status": "pending",
            "shift_id": shift_id,
            "duty_action": duty_action
        })

        if existing:
            msg = f"Your Official Duty ({action_label}) request for {shift_name} is already pending."
            send_whatsapp_text(mobile_number, msg)
            return {
                "status": "success",
                "message": msg
            }

        duty_doc = {
            "doctor_id": str(doctor_id),
            "staff_id": staff_id,
            "staff_name": staff_name,
            "start_date": today,
            "end_date": today,
            "reason": f"Official Duty ({action_label}) applied via WhatsApp - Shift: {shift_name}",
            "request_type": "official_duty",
            "duty_action": duty_action,
            "shift_id": shift_id,
            "shift_name": shift_name,
            "mobile_number": mobile_number,
            "status": "pending",
            "reviewed_by": None,
            "review_remarks": "",
            "whatsapp_message_id": message_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }

        try:
            leave_requests.insert_one(duty_doc)
            attendance_requests.insert_one({
                "staff_id": staff_id,
                "doctor_id": str(doctor_id),
                "shift_id": shift_id,
                "shift_name": shift_name,
                "request_type": "official_duty",
                "duty_action": duty_action,
                "attendance_date": today,
                "status": "pending",
                "whatsapp_message_id": message_id,
                "created_at": now.isoformat()
            })
            # Send approval request with buttons to Doctor's WhatsApp
            send_approval_request_to_doctor(doctor_id, str(duty_doc["_id"]), duty_doc)

            msg = f"✅ Official Duty ({action_label}) request for {shift_name} has been sent to the doctor for approval."
        except DuplicateKeyError:
            msg = "Your Official Duty request has already been recorded."

        send_whatsapp_text(mobile_number, msg)
        return {
            "status": "success",
            "message": msg
        }

    # ---------------------------------
    # 6. Normal shift:
    #    Mark check-in in aligned 'attendance' collection
    # ---------------------------------
    existing_attendance = attendance.find_one({
        "doctor_id": str(doctor_id),
        "staff_id": staff_id,
        "date": today
    })

    if existing_attendance:
        if existing_attendance.get("check_out"):
            msg = "Today's attendance and check-out are already completed."
        else:
            msg = f"Today's check-in is already marked for {existing_attendance.get('shift_name', 'Shift')}."
        send_whatsapp_text(mobile_number, msg)
        return {
            "status": "success",
            "message": msg
        }

    # Record schema exactly matching c2c_app.py check_in endpoint
    record = {
        "doctor_id": str(doctor_id),
        "staff_id": staff_id,
        "staff_name": staff_name,
        "date": today,
        "check_in": now.isoformat(),
        "check_out": None,
        "status": "present",
        "shift_id": shift_id,
        "shift_name": shift_name,
        "remarks": f"WhatsApp Check-in - Shift: {shift_name}",
        "whatsapp_message_id": message_id,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }

    try:
        attendance.insert_one(record)
        msg = f"✅ Check-in successfully marked!\nShift: {shift_name}\nTime: {now.strftime('%I:%M %p')}\nHave a great shift!"
    except DuplicateKeyError:
        msg = "Today's attendance has already been recorded."

    send_whatsapp_text(mobile_number, msg)
    return {
        "status": "success",
        "message": msg
    }


def send_shift_buttons(mobile_number, doctor_id):
    # Fetch active shifts for this doctor
    doctor_shifts = list(shifts.find({
        "doctor_id": str(doctor_id),
        "status": "active"
    }))

    if not doctor_shifts:
        return send_whatsapp_text(
            mobile_number,
            "No active shifts are available. Please contact your administrator."
        )

    # WhatsApp reply buttons support max 3 options; if > 3 use an interactive list (supports up to 10)
    if len(doctor_shifts) <= 3:
        buttons = []
        for shift in doctor_shifts:
            shift_id = str(shift["_id"])
            shift_name = shift.get("shift_name", "Shift")

            buttons.append({
                "type": "reply",
                "reply": {
                    "id": f"shift_{shift_id}",
                    "title": shift_name[:20]
                }
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": str(mobile_number),
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": "Your location is verified. Please select your shift to mark attendance."
                },
                "footer": {
                    "text": "Select your assigned shift"
                },
                "action": {
                    "buttons": buttons
                }
            }
        }
    else:
        rows = []
        for shift in doctor_shifts[:10]:
            shift_id = str(shift["_id"])
            shift_name = shift.get("shift_name", "Shift")
            time_desc = f"{shift.get('start_time', '')} - {shift.get('end_time', '')}".strip(" -")
            rows.append({
                "id": f"shift_{shift_id}",
                "title": shift_name[:24],
                "description": time_desc[:72] if time_desc else "Select to mark attendance"
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": str(mobile_number),
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {
                    "type": "text",
                    "text": "Shift Selection"
                },
                "body": {
                    "text": "Your location is verified. Please select your shift from the list below to mark attendance."
                },
                "footer": {
                    "text": "Tap button below to view shifts"
                },
                "action": {
                    "button": "View Shifts",
                    "sections": [
                        {
                            "title": "Available Shifts",
                            "rows": rows
                        }
                    ]
                }
            }
        }

    return send_whatsapp_payload(payload)


def send_shift_buttons_for_official_duty(mobile_number, doctor_id, is_checkout=False):
    # Fetch active shifts for this doctor
    doctor_shifts = list(shifts.find({
        "doctor_id": str(doctor_id),
        "status": "active"
    }))

    if not doctor_shifts:
        return send_whatsapp_text(
            mobile_number,
            "No active shifts are available. Please contact your administrator."
        )

    action_label = "Check-Out" if is_checkout else "Check-In"
    body_text = (
        "Official duty check-out selected. Please choose your shift to submit check-out request:"
        if is_checkout
        else "Official duty selected. Please choose your shift:"
    )
    header_text = f"Official Duty {action_label}"

    if len(doctor_shifts) <= 3:
        buttons = []
        for shift in doctor_shifts:
            shift_id = str(shift["_id"])
            shift_name = shift.get("shift_name", "Shift")

            buttons.append({
                "type": "reply",
                "reply": {
                    "id": f"official_shift_{shift_id}",
                    "title": shift_name[:20]
                }
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": str(mobile_number),
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": body_text
                },
                "footer": {
                    "text": f"Select shift for {action_label.lower()}"
                },
                "action": {
                    "buttons": buttons
                }
            }
        }
    else:
        rows = []
        for shift in doctor_shifts[:10]:
            shift_id = str(shift["_id"])
            shift_name = shift.get("shift_name", "Shift")
            time_desc = f"{shift.get('start_time', '')} - {shift.get('end_time', '')}".strip(" -")
            rows.append({
                "id": f"official_shift_{shift_id}",
                "title": shift_name[:24],
                "description": time_desc[:72] if time_desc else f"Select for official duty {action_label.lower()}"
            })

        payload = {
            "messaging_product": "whatsapp",
            "to": str(mobile_number),
            "type": "interactive",
            "interactive": {
                "type": "list",
                "header": {
                    "type": "text",
                    "text": header_text[:60]
                },
                "body": {
                    "text": body_text
                },
                "footer": {
                    "text": "Tap button below to view shifts"
                },
                "action": {
                    "button": "View Shifts",
                    "sections": [
                        {
                            "title": "Available Shifts",
                            "rows": rows
                        }
                    ]
                }
            }
        }

    return send_whatsapp_payload(payload)


# --------------------------------------------------
# WEBHOOK HANDLER
# --------------------------------------------------

def attendence(data, id):
    """
    Main webhook entry point for staff attendance.
    Returns (result_dict, status_code) with result_dict['handled'] = True
    if the message was an attendance event, or {'handled': False} if not.
    """
    try:
        if not data or not isinstance(data, dict):
            return {"handled": False, "message": "Empty or invalid data"}, 200

        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})

                for message in value.get("messages", []):
                    message_type = message.get("type")

                    if message_type == "location":
                        res, status_code = process_location(message, id)
                        if isinstance(res, dict):
                            res["handled"] = True
                        return res, status_code

                    elif message_type == "interactive":
                        interactive = message.get("interactive", {})
                        interactive_type = interactive.get("type")

                        button_id = ""
                        if interactive_type == "button_reply":
                            button_id = interactive.get("button_reply", {}).get("id", "")
                        elif interactive_type == "list_reply":
                            button_id = interactive.get("list_reply", {}).get("id", "")

                        if button_id and (
                            button_id in ("a_leave_request", "a_official_duty")
                            or button_id.startswith("shift_")
                            or button_id.startswith("official_shift_")
                            or button_id.startswith("checkout_")
                            or button_id.startswith("appr_")
                            or button_id.startswith("rej_")
                        ):
                            res = process_button_reply(message, id)
                            if isinstance(res, tuple):
                                if isinstance(res[0], dict):
                                    res[0]["handled"] = True
                                return res
                            if isinstance(res, dict):
                                res["handled"] = True
                                return res, 200
                            return {"handled": True, "data": res}, 200

                        # Not an attendance interactive message (e.g., patient booking buttons)
                        return {
                            "handled": False,
                            "message": "Non-attendance interactive action"
                        }, 200

                    else:
                        pass

        return {
            "handled": False,
            "message": "No attendance message in payload"
        }, 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"handled": False, "error": str(e)}, 500


# Alias with correct spelling
attendance_handler = attendence
