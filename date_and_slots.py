

import time
from datetime import datetime, timedelta
from bson.objectid import ObjectId
from pymongo import MongoClient
from collections import Counter
from zoneinfo import ZoneInfo

MONGO_URI = "mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.get_database("caredb")
doctors = db["doctors"] 
appointment = db["appointment"] 
templog = db["logs"] 
disableslot = db["disableslot"] 

def dateandtime(id):
        if id == 'date':
            doc_id = ObjectId("67ee5e1bde4cb48c515073ee")
            document = doctors.find_one({"_id": doc_id})
            datas = document

            def get_next_7_days():
                today = datetime.now(ZoneInfo("Asia/Kolkata"))
                dates = [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(8)]
                return dates

            disabled_dates = get_next_7_days()

            data = datas['date']['disabledate']
            data_names = {item["name"] for item in data}
            formatted_output = [
                {"id": date, "title": date, "enabled": False} if date in data_names else {"id": date, "title": date}
                for date in disabled_dates
                ]
    
            current_time = datetime.now(ZoneInfo("Asia/Kolkata")).time()

            cutoff_time = datetime.strptime("08:30AM", "%I:%M%p").time()

            print(cutoff_time)

            is_before_8am = current_time < cutoff_time

            if not is_before_8am and data:
                formatted_output.pop(0)
            

            return formatted_output

        else:


            doc_id = ObjectId("67ee5e1bde4cb48c515073ee")
            document = doctors.find_one({"_id": doc_id})
            datas = document


            appoint = list(appointment.find({"doctor_phone_id": "67ee5e1bde4cb48c515073ee", "date_of_appointment":id,"amount":{"$gt": -1}}, {"_id": 0}))
            
            if appoint:

                time_slots = [entry['time_slot'] for entry in appoint]

                time_counts = Counter(time_slots)

# Convert to required format
                result = [{"time": time, "number": count} for time, count in time_counts.items()]

                xslot = datas['slots']['slotsvalue']

                formatted_output = [
                {
                    "id": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+ datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                    "title": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                    "maxno": item["maxno"]
                }
                for index, item in enumerate(xslot)
                ]

                arry1 = result
                arry2 = formatted_output

# Convert arry1 into a dictionary for quick lookup
                time_counts = {item['time']: item['number'] for item in arry1}

# Process and apply conditions
                result = [
                {
                "id": item['id'],
                "title": item['title'],
                "enabled": False if time_counts.get(item['title'], 0) >= int(item['maxno']) else True
                }
                for item in arry2
                ]

# Remove "enabled": True for cleaner output
                for obj in result:
                    if obj["enabled"]:
                        del obj["enabled"]

                disabled_slots = []

                documentsst = list(disableslot.find({'date':id}))
                if documentsst:


                    disabled_slots = documentsst

# Create a set of disabled slot times for easy lookup
                disabled_set = {item["slot"] for item in disabled_slots if not item["enable"]}

                print(disabled_set)

# Add 'enabled' field to slots accordingly
                updated_slots = []
                for slot in result:
                    if slot["id"] in disabled_set:
                        updated_slots.append({**slot, "enabled": False})
                    else:
                        updated_slots.append(slot)
                        
                return updated_slots
            else:
                xslot = datas['slots']['slotsvalue']

                formatted_output = [
                {
                     "id": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+ datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                    "title": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                }
                for index, item in enumerate(xslot)
                ]

                disabled_slots = []

                documentsst = list(disableslot.find({'date':id}))
                if documentsst:
                    disabled_slots = documentsst

                # disabled_slots = [
                #     {"date": "2025-04-09", "slot": "09:00 AM - 10:00 AM", "enable": False},
                #     {"date": "2025-04-09", "slot": "02:00 PM - 03:00 PM", "enable": False},
                # ]

# Create a set of disabled slot times for easy lookup
                disabled_set = {item["slot"] for item in disabled_slots if not item["enable"]}

                print(disabled_set)

# Add 'enabled' field to slots accordingly
                updated_slots = []
                for slot in formatted_output:
                    if slot["id"] in disabled_set:
                        updated_slots.append({**slot, "enabled": False})
                    else:
                        updated_slots.append(slot)

                return updated_slots



