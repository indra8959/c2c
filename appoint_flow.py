from flask import Flask, request, jsonify
from pymongo import MongoClient
import requests
from datetime import datetime, timedelta
import time
import json
from bson.objectid import ObjectId
from razorpay_local import pay_link
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from zoneinfo import ZoneInfo
from pay_link_with_image import pay_now_image



MONGO_URI = "mongodb+srv://care2connect:connect0011@cluster0.gjjanvi.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client.get_database("caredb")
doctors = db["doctors"] 
appointment = db["appointment"] 
templog = db["logs"] 
admin = db["admin"] 
templog2 = db["tempdata"]

headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}
phone_id = '563776386825270'


# def checkoldappointment(phonenumber,fdate,name,doctorid):
#     result = list(appointment.find({"whatsapp_number":phonenumber,"doctor_phone_id":doctorid,"patient_name":name,"amount":{"$gt": 0}}))
# # print(appoint.val())

#     try:

#         date_str = fdate
#         date = datetime.strptime(date_str, "%Y-%m-%d")
#         new_date = date - timedelta(days=2)

#         print(new_date.strftime("%Y-%m-%d"))

#         from_date = datetime.strptime(new_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
#         to_date = datetime.strptime(date_str, "%Y-%m-%d")

#     except:
#         return 0
    
def send_payment_flow(from_number,name,date,slot,amount,link):



    # print(from_number,name,date,slot,amount,link)

    formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%m-%Y")

    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    incoming_data = { 
        "messaging_product": "whatsapp", 
        "to": from_number, "type": "template", 
        "template": { 
            "name": "multi_payment_option", 
            "language": { 
                "code": "en" 
            },
            "components": [
                {
                    "type": "header",
                    "parameters":  []

                },
                 {
        "type": "body",
        "parameters": [ {
                    "type": "text",
                    "text": amount
                }
         
        ]
      }, {
                "type": "button",
                "index": "0",
                "sub_type": "url",
                "parameters": [
                    {
                        "type": "text",
                        "text": link
                    }
                ]}

            ]} 
        }

#     incoming_data = { 
#   "messaging_product": "whatsapp", 
#   "to": from_number, 
#   "type": "template", 
#   "template": { 
#     "name": "ulility_pay_now2", 
#     "language": { "code": "en" },
#     "components": [
#       {
#         "type": "body",
#         "parameters": [
#           {
#             "type": "text",
#             "text": amount 
#           },
#           {
#             "type": "text",
#             "text": "https://rzp.io/rzp/"+link
#           }
#         ]
#       }
#     ]
#   } 
# }

    response = requests.post(external_url, json=incoming_data, headers=headers)
    return 'ok', 200
    # return pay_now_image(from_number,name,amount,formatted_date,slot,link)

# print(send_payment_flow('918959690512','name','date','slot','amount','link'))

def custom_book_appointment(data):

    entry = data.get('entry', [])[0]  # Extract first entry
    changes = entry.get('changes', [])[0]  # Extract first change
    value = changes.get('value', {})

    message_info = value.get('messages', [])[0] 
    from_number = message_info.get('from')

    document = templog.find_one({'_id':from_number})
    appoint_data = appointment.find_one({"_id": ObjectId(document["id_value"])})

    print(appoint_data)

    response_json_str = data['entry'][0]['changes'][0]['value']['messages'][0]['interactive']['nfm_reply']['response_json']
    response_data = json.loads(response_json_str)
    print(response_data)

    

    name = appoint_data.get('patient_name')
    pname = appoint_data.get('guardian_name')
    date = response_data.get('Date_of_appointment_0')
    slot = response_data.get('Time_Slot_1')
    vaccine = response_data.get('vaccine')
    email = 'none'
    symptoms = 'none'
    age = 'none'
    dob = 'none'
    city = 'none'
    address = 'none'

    if response_data.get('Guardian_Name'):
        pname = response_data.get('Guardian_Name')
    else:
        pname = pname

    if appoint_data.get('email'):
        email = appoint_data.get('email')
    else:
        email = 'none'

    if response_data.get('Other_Symptoms_5'):
        symptoms = response_data.get('Other_Symptoms_5')
    else:
        symptoms = 'none'

    if appoint_data.get('age'):
        age = appoint_data.get('age')
    else:
        age = 'none'

    if appoint_data.get('date_of_birth'):
        dob = appoint_data.get('date_of_birth')
    else:
        dob = 'none'

    if appoint_data.get('city'):
        city = appoint_data.get('city')
    else:
        city = 'none'

    if appoint_data.get('address'):
        address = appoint_data.get('address')
    else:
        address = 'none'

    from_number = message_info.get('from')
    timestamp = message_info.get('timestamp')

    doctor_id = '67ee5e1bde4cb48c515073ee'

    # result = list(doctors.find({"doctor_phone_id": doctor_id}, {"_id": 0}))  # Convert cursor to list
    # data_length = len(result)

    dataset = {
        'patient_name': name,
        'guardian_name': pname,
        'date_of_appointment': date,
        'time_slot': slot,
        'doctor_phone_id':doctor_id,
        'email' : email,
        'symptoms' : symptoms,
        'age' : age,
        'timestamp' : timestamp,
        'whatsapp_number' : from_number,
        'date_of_birth' : dob,
        'city' : city,
        'address' : address,
        'role':'appointment',
        'status':'created',
        "createdAt": 'x',
        "vaccine":vaccine
            }
    
    date_str = date
    xdate = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = xdate - timedelta(days=2)

    
    from_date = datetime.strptime(new_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
    todate = datetime.strptime(date_str, "%Y-%m-%d")
    todate = todate.replace(hour=23, minute=59, second=59)  # Ensure full-day inclusion

# Query with date filtering (Convert date_of_appointment to datetime in query)
    result = list(appointment.find({
    "whatsapp_number": from_number,
    "patient_name": name,
    "doctor_phone_id": doctor_id,
    "amount":{"$gt": 0},
    "$expr": {
        "$and": [
            {"$gte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, from_date]},
            {"$lte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, todate]}
        ]
    }
    }).sort("date_of_appointment", -1).limit(1)) 

    if len(result)>0:
        retrieved_data = result[0]
        result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":date,"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
        data_length = 1
        if result:
            data_length = len(result)+1

        xdate = date
        date_obj = datetime.strptime(xdate, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y%m%d")

        pay_id = str(retrieved_data['pay_id'])
        pay_id = "old_"+pay_id

        img_date = str(retrieved_data['date_of_appointment'])

        appoint_number = str(formatted_date)+'-'+str(data_length)




        dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        fee = float(dxxocument.get('appointmentfee'))




        index_number = getindex(retrieved_data['doctor_phone_id'],slot,xdate)

        



        xid = appointment.insert_one({**dataset,'status':'success','pay_id':pay_id,'appoint_number':appoint_number,'amount':0,'appointment_index':index_number}).inserted_id


        tempdata = {"number":from_number,"current_id":xid,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        name = str(retrieved_data['patient_name'])
        payment_id = str(pay_id)
        doa = str(retrieved_data['date_of_appointment'])
        tm = str(retrieved_data['time_slot'])
        phone = str(retrieved_data['whatsapp_number'])


        # pay_id = str(retrieved_data['pay_id'])
        # pay_id = "old_"+pay_id

        # appoint_number = str(formatted_date)+'-'+str(data_length)

        # appointment.insert_one({**dataset,'status':'success','pay_id':pay_id,'appoint_number':appoint_number,'amount':0})

        # name = str(retrieved_data['patient_name'])
        # phone = str(retrieved_data['whatsapp_number'])

        return success_appointment(img_date,index_number,name,date,slot,phone)
    
        # doc_id = ObjectId(id)
        # retrieved_data = appointment.find_one({"_id": doc_id})

        # print(retrieved_data['doctor_phone_id'])

        # result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":retrieved_data['date_of_appointment'],"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
        # data_length = 1
        # if result:
        #     data_length = len(result)+1

        # xdate = retrieved_data['date_of_appointment']
        # date_obj = datetime.strptime(xdate, "%Y-%m-%d")
        # formatted_date = date_obj.strftime("%Y%m%d")

        # appoint_number = str(formatted_date)+'-'+str(data_length)

        # print('1')


        # dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        # fee = float(dxxocument.get('appointmentfee'))

        # print('1')


        # index_number = getindex(retrieved_data['doctor_phone_id'],retrieved_data['time_slot'],xdate)

        # print('1')


        # appointment.update_one({'_id': doc_id},{'$set':{'status':'success','pay_id':callback_data.get('razorpay_payment_id'),'appoint_number':appoint_number,'amount':fee,'appointment_index':index_number}})

        # print('1')
        # name = str(retrieved_data['patient_name'])
        # payment_id = str(callback_data.get('razorpay_payment_id'))
        # doa = str(retrieved_data['date_of_appointment'])
        # tm = str(retrieved_data['time_slot'])
        # phone = str(retrieved_data['whatsapp_number'])

        # print('1')


        # whatsapp_url = success_appointment(payment_id,index_number,name,doa,tm,phone)

        # print('1')

        # return redirect(whatsapp_url)
    



    else:
        id = str(appointment.insert_one(dataset).inserted_id)
        print(id)

        dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        fee = float(dxxocument.get('appointmentfee'))
        # paymentlink = dxxocument.get('paymentlink')

        tempdata = {"number":from_number,"current_id":id,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})


        dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
        razorpayid = dxocument.get('razorpayid')
        razorpaykey = dxocument.get('razorpaykey')

        link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)
        # link = paymentlink
        print(link)
        amount = fee
        return send_payment_flow(from_number,name,date,slot,amount,link)



# def getindex(docter_id,tslot,date):

#     doc_id = ObjectId(docter_id)
#     document = doctors.find_one({"_id": doc_id})
#     xslot = document['slots']['slotsvalue']

#     formatted_output = [
#                 {
#                      "id": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+ datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
#                     "slot": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
#                     "length": item["maxno"]
#                 }
#                 for index, item in enumerate(xslot)
#                 ]

#     target_id = tslot
#     total_length = 1

#     for slot in formatted_output:
#         if slot['id'] == target_id:
#             total_length += int(slot['length'])
#             break
#         total_length += int(slot['length'])


#     result = list(appointment.find({"doctor_phone_id": docter_id,'time_slot':tslot ,"date_of_appointment":date,"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
#     data_length = 0
#     if result:
#         data_length = len(result)

#     appointment_number = total_length-data_length-1
#     print(appointment_number)
#     return appointment_number

def getindex(docter_id,tslot,date):

    doc_id = ObjectId(docter_id)
    document = doctors.find_one({"_id": doc_id})
    xslot = document['slots']['slotsvalue']

    formatted_output = [
                {
                     "id": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+ datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                    "slot": datetime.strptime(item["slot"]["stime"], "%H:%M").strftime("%I:%M %p")+" - "+datetime.strptime(item["slot"]["etime"], "%H:%M").strftime("%I:%M %p"),
                    "length": item["maxno"]
                }
                for index, item in enumerate(xslot)
                ]

    target_id = tslot
    total_length = 0

    for slot in formatted_output:
        if slot['id'] == target_id:
            break
        total_length += int(slot['length'])


    result = list(appointment.find({"doctor_phone_id": docter_id,'time_slot':tslot ,"date_of_appointment":date,"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
    data_length = 1
    if result:
        data_length = len(result)+1

    appointment_number = data_length+total_length
    print(appointment_number)
    return appointment_number

def book_appointment(data):

    entry = data.get('entry', [])[0]  # Extract first entry
    changes = entry.get('changes', [])[0]  # Extract first change
    value = changes.get('value', {})

    message_info = value.get('messages', [])[0] 
    response_json_str = data['entry'][0]['changes'][0]['value']['messages'][0]['interactive']['nfm_reply']['response_json']
    response_data = json.loads(response_json_str)
    print(response_data)

    if response_data.get('role')=='personal_flow':
        return custom_book_appointment(data)

    name = response_data.get('Patient_Name_2')
    pname = 'none'
    date = response_data.get('Date_of_appointment_0')
    slot = response_data.get('Time_Slot_1')
    vaccine = response_data.get('vaccine')

    email = 'none'
    symptoms = 'none'
    age = 'none'
    dob = 'none'
    city = 'none'
    address = 'none'

    if response_data.get('Guardian_Name'):
        pname = response_data.get('Guardian_Name')
    else:
        pname = 'none'


    if response_data.get('Email_4'):
        email = response_data.get('Email_4')
    else:
        email = 'none'

    if response_data.get('Other_Symptoms_5'):
        symptoms = response_data.get('Other_Symptoms_5')
    else:
        symptoms = 'none'

    if response_data.get('Age_3'):
        age = response_data.get('Age_3')
    else:
        age = 'none'

    if response_data.get('Date_Of_Birth'):
        dob = response_data.get('Date_Of_Birth')
    else:
        dob = 'none'

    if response_data.get('City'):
        city = response_data.get('City')
    else:
        city = 'none'

    if response_data.get('Address'):
        address = response_data.get('Address')
    else:
        address = 'none'

    from_number = message_info.get('from')
    timestamp = message_info.get('timestamp')

    doctor_id = '67ee5e1bde4cb48c515073ee'

    # result = list(doctors.find({"doctor_phone_id": doctor_id}, {"_id": 0}))  # Convert cursor to list
    # data_length = len(result)

    dataset = {
        'patient_name': name,
        'guardian_name': pname,
        'date_of_appointment': date,
        'time_slot': slot,
        'doctor_phone_id':doctor_id,
        'email' : email,
        'symptoms' : symptoms,
        'age' : age,
        'timestamp' : timestamp,
        'whatsapp_number' : from_number,
        'date_of_birth' : dob,
        'city' : city,
        'address' : address,
        'role':'appointment',
        'status':'created',
        "createdAt": 'x',
        "vaccine":vaccine
            }
    
    date_str = date
    xdate = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = xdate - timedelta(days=2)

    
    from_date = datetime.strptime(new_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
    todate = datetime.strptime(date_str, "%Y-%m-%d")
    todate = todate.replace(hour=23, minute=59, second=59)  # Ensure full-day inclusion

# Query with date filtering (Convert date_of_appointment to datetime in query)
    result = list(appointment.find({
    "whatsapp_number": from_number,
    "patient_name": name,
    "doctor_phone_id": doctor_id,
    "amount":{"$gt": 0},
    "$expr": {
        "$and": [
            {"$gte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, from_date]},
            {"$lte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, todate]}
        ]
    }
    }).sort("date_of_appointment", -1).limit(1)) 

    if len(result)>0:

        try:
            templog2.insert_one({**data,'_id': from_number})
        except:
            templog2.update_one({'_id': from_number}, {'$set': data})

        return sameordef(from_number,name)

        # retrieved_data = result[0]
        # result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":date,"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
        # data_length = 1
        # if result:
        #     data_length = len(result)+1

        # xdate = date
        # date_obj = datetime.strptime(xdate, "%Y-%m-%d")
        # formatted_date = date_obj.strftime("%Y%m%d")

        # pay_id = str(retrieved_data['pay_id'])
        # pay_id = "old_"+pay_id

        # appoint_number = str(formatted_date)+'-'+str(data_length)

        # dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        # fee = float(dxxocument.get('appointmentfee'))




        # index_number = getindex(retrieved_data['doctor_phone_id'],slot,xdate)


        # xid = appointment.insert_one({**dataset,'status':'success','pay_id':pay_id,'appoint_number':appoint_number,'amount':0,'appointment_index':index_number}).inserted_id


        # tempdata = {"number":from_number,"current_id":xid,"_id":from_number}
        # try:
        #     templog.insert_one(tempdata)
        # except:
        #     templog.update_one({'_id': from_number}, {'$set': tempdata})

        

        # name = str(retrieved_data['patient_name'])
        # phone = str(retrieved_data['whatsapp_number'])

        # return success_appointment(pay_id,index_number,name,date,slot,phone)
    else:
        id = str(appointment.insert_one(dataset).inserted_id)
        print(id)

        dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        fee = float(dxxocument.get('appointmentfee'))
        # paymentlink = dxxocument.get('paymentlink')

        tempdata = {"number":from_number,"current_id":id,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
        razorpayid = dxocument.get('razorpayid')
        razorpaykey = dxocument.get('razorpaykey')


        link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)


        # link = paymentlink
        print(link)
        amount = fee
        return send_payment_flow(from_number,name,date,slot,amount,link)
    




def custom_appointment_flow(from_number):

    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    incoming_data = { 
    "messaging_product": "whatsapp", 
    "to": from_number, 
    "type": "template", 
    "template": { 
        "name": "clone_appointment_flow_4", 
        "language": { "code": "en" },
        "components": [
            {
                "type": "header"
            },
            {
                "type": "body",
                "parameters": []
            },
            {
                "type": "button",
                "sub_type": "flow",  
                "index": "0"  
            }
        ]
    } 
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    print(response)
    return "OK", 200


def appointment_flow(from_number):

    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    incoming_data = { 
    "messaging_product": "whatsapp", 
    "to": from_number, 
    "type": "template", 
    "template": { 
        "name": "final_appointment2", 
        "language": { "code": "en" },
        "components": [
            {
                "type": "header"
            },
            {
                "type": "body",
                "parameters": []
            },
            {
                "type": "button",
                "sub_type": "flow",  
                "index": "0"  
            }
        ]
    } 
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    print(jsonify(response.json()))
    return "OK", 200


def appointment_flow_expire(from_number):

    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    incoming_data = { 
    "messaging_product": "whatsapp", 
    "to": from_number, 
    "type": "template", 
    "template": { 
        "name": "expire_after_send", 
        "language": { "code": "en" },
        "components": [
            {
                "type": "header"
            },
            {
                "type": "body",
                "parameters": []
            },
            {
                "type": "button",
                "sub_type": "flow",  
                "index": "0"  
            }
        ]
    } 
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    print(jsonify(response.json()))
    return "OK", 200

def call_external_post_api(from_number):

    last_object = appointment.find_one({"whatsapp_number": from_number}, sort=[("_id", -1)])
    # last_object = False

    print(last_object)

    if last_object:
        name = last_object['patient_name']
        print(name)
        return start_automation(from_number)
    else:
        external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

        incoming_data = { 
    "messaging_product": "whatsapp", 
    "to": from_number, 
    "type": "template", 
    "template": { 
        "name": "final_appointment2", 
        "language": { "code": "en" },
        "components": [
            {
                "type": "header"
            },
            {
                "type": "body",
                "parameters": []
            },
            {
                "type": "button",
                "sub_type": "flow",  
                "index": "0"  
            }
        ]
    } 
}

        response = requests.post(external_url, json=incoming_data, headers=headers)
        print(jsonify(response.json()))
        return "OK", 200
    

def start_automation(from_number):
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    all_buttons = [
    {"id": "Receipt", "title": "Yes"},
    {"id": "no", "title": "No"}
    ]

# Function to send buttons in batches of 3
    def send_whatsapp_buttons(to_number, buttons_list):
        for i in range(0, len(buttons_list), 3):  # Send in groups of 3
            buttons = buttons_list[i:i+3]  # Get 3 buttons at a time

            payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Download Transaction Receipt?"},
                "action": {
                    "buttons": [{"type": "reply", "reply": btn} for btn in buttons]
                }
            }
        }

            response = requests.post(external_url, headers=headers, json=payload)
       
         

# Send multiple messages with 3 buttons per message
    send_whatsapp_buttons(from_number, all_buttons)

    # response = requests.post(external_url, json=payloadx, headers={'Authorization': 'Bearer EAAJdr829Xj4BOxyhp8MzkQqZCr92HwzYQMyDjZBhWZBqUej9YnYqTBefwyGeIZAUOhSk3y9AspLT69frxyYsWb6ea7jAGP4xm3BCxkAF5SXMqLeY3SpYt5AUUi0CkUIhk8AC6S1H6TIr0RLQHf3Tfo6ZBblcMZCBoc81nqVTidywfSK4FoWZAZCXenHHqRr5wAtE5D2tIGf87f8B7wuXUcWyK77Wca1ZBR3tqxQMOkK6L6BUZD','Content-Type': 'application/json'})
    # print(jsonify(response.json()))
    return "OK", 200



def success_appointment(payment_id,appoint_no,name,doa,time,whatsapp_no):
    url = f"https://graph.facebook.com/v22.0/563776386825270/messages"

    formatted_date = datetime.strptime(doa, "%Y-%m-%d").strftime("%d-%m-%Y")


    # payload = { 
    #     "messaging_product": "whatsapp", 
    #     "to": whatsapp_no, "type": "template", 
    #     "template": { 
    #         "name": "success_book_2", 
    #         "language": { 
    #             "code": "en" 
    #         },
    #         "components": [
    #             {
    #                 "type": "header",
    #                 "parameters":  [{
    #         "type": "location",
    #         'location': {
    #       'latitude': 30.210875294402626, 
    #       'longitude': 74.94743978282561, 
    #       'name': "Kalra Multispeciality Hospital",
    #       'address': "Bathinda, India"
    #     }
    #       }]

    #             },
    #              {
    #     "type": "body",
    #     "parameters": [ {
    #                 "type": "text",
    #                 "text": name
    #             }, {
    #                 "type": "text",
    #                 "text": appoint_no
    #             }, {
    #                 "type": "text",
    #                 "text": formatted_date
    #             }, {
    #                 "type": "text",
    #                 "text": time
    #             },
    #       {
    #                 "type": "text",
    #                 "text": payment_id
    #             }
    #     ]
    #   }

    #         ]} 
    #     }


    payload = { 
        "messaging_product": "whatsapp", 
        "to": whatsapp_no, "type": "template", 
        "template": { 
            "name": "success_location", 
            "language": { 
                "code": "en" 
            },
            "components": [
                {
                    "type": "header",
                    "parameters":  [{
            "type": "location",
            'location': {
          'latitude': 30.210875294402626, 
          'longitude': 74.94743978282561, 
          'name': "Kalra Multispeciality Hospital",
          'address': "Bathinda, India"
        }
          }]

                },
                 {
        "type": "body",
        "parameters": [ 
        ]
      }

            ]} 
        }
    

    # response = requests.post(url, json=payload, headers=headers)

    appoint_no = str(appoint_no)

    
    
    img = generate_appointment_image(appoint_no,formatted_date,time,name,payment_id)
    # ok = compress_to_10kb(img, output_path="img.jpg")
    
    kk = imagesend(whatsapp_no)

    start_automation(whatsapp_no)

    # response = requests.post(url, json=payload, headers=headers)
    return f"whatsapp://send?phone=+919646465003"






def imagesend(whatsapp_no):

    WHATSAPP_ACCESS_TOKEN = "EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD"
    PDF_FILE_PATH = 'img.jpg'

    PHONE_NUMBER_ID = "563776386825270"


# API endpoint for media upload
    upload_url = f"https://graph.facebook.com/v22.0/{PHONE_NUMBER_ID}/media"

# Headers
    headers = {
    "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"
    }

# File upload
    files = {
        "file": (PDF_FILE_PATH, open(PDF_FILE_PATH, "rb"), "image/jpeg"),
        "type": (None, "image/jpeg"),
        "messaging_product": (None, "whatsapp")
        }

    response = requests.post(upload_url, headers=headers, files=files)

    print(response)

# Print response
    print(response.json()['id'])


    PDF_FILE_ID = response.json()['id']  # Extracted from your provided data


        
    url = f"https://graph.facebook.com/v22.0/563776386825270/messages"

    payload = {
  "messaging_product": "whatsapp",
  "to": whatsapp_no,
  "type": "template",
  "template": {
    "name": "success_image",
    "language": {
      "code": "en"
    },
    "components": [
      {
        "type": "header",
        "parameters": [
          {
            "type": "image",
            "image": {
            #   "link": "https://78b9-2409-40c4-21c8-f1ea-8026-7db7-c465-cdae.ngrok-free.app/static/img.jpg"
            "id": PDF_FILE_ID
         
            }
          }
        ]
      },
      {
        "type": "body",
        "parameters": [
        ]
      }
    ]
  }
}


    

    response = requests.post(url, json=payload, headers=headers)

    print(response)

    return "OK", 200

def draw_justified_text(draw, text_lines, font, start_x, start_y, line_width, line_height, fill="black"):
    for line in text_lines:
        words = line.strip().split()
        if not words:
            start_y += line_height
            continue

        # Measure total width of words without spaces
        total_words_width = sum(draw.textlength(word, font=font) for word in words)
        total_spaces = len(words) - 1
        if total_spaces > 0:
            space_width = (line_width - total_words_width) / total_spaces
        else:
            space_width = 0

        x = start_x
        for i, word in enumerate(words):
            draw.text((x, start_y), word, font=font, fill=fill)
            x += draw.textlength(word, font=font) + (space_width if i < total_spaces else 0)
        start_y += line_height


def generate_appointment_image(number, date, time, name,c_date):



    date_str =c_date

# Convert string to datetime object
    given_date = datetime.strptime(date_str, "%Y-%m-%d")

# Add 3 days
    new_date = given_date + timedelta(days=2)

# Format the result back to string
    result = new_date.strftime("%d-%m-%Y")

    # Load background image
    background_path = "bgdr.jpg"  # Replace with actual path to your image
    background = Image.open(background_path).convert("RGB")
    background = background.resize((800, 800))

    draw = ImageDraw.Draw(background)
    scale = 800 / 800

    texts = [
        {"text": "Hello Dear " + name, "font_size": int(32 * scale), "y_offset": int(50 * scale)},
        {"text": "Your appointment has been confirmed", "font_size": int(32 * scale), "y_offset": int(90 * scale)},
        {"text": "Appointment No.", "font_size": int(28 * scale), "y_offset": int(200 * scale)},
        {"text": number, "font_size": int(150 * scale), "y_offset": int(240 * scale), "color": "green"},
        {"text": "Date - " + date, "font_size": int(36 * scale), "y_offset": int(460 * scale)},
        {"text": "Time - " + time, "font_size": int(36 * scale), "y_offset": int(520 * scale)},
    ]

    # Font path (Ensure the font file exists or change to a system font path)
    bold_font_path = "pt.ttf"

    # Draw main text items
    for item in texts:
        text = item["text"]
        font_size = item["font_size"]
        y_offset = item["y_offset"]
        color = item.get("color", "black")

        try:
            font = ImageFont.truetype(bold_font_path, font_size)
        except OSError:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (background.width - text_width) / 2
        draw.text((x, y_offset), text, font=font, fill=color)

    # Disclaimer text (justified)
    disclaimer_points = [
        "*Disclaimer:",
        f"1. Your appointment is valid till {result} during regular",
        "OPD hours. No consultation fee will be charged during this period.",
        "2. While we strive to honor all appointment times, please note that",
        "there may be delays due to unforeseen emergencies or circumstances",
        "beyond our control. We appreciate your patience and understanding."
    ]

    try:
        disclaimer_font = ImageFont.truetype(bold_font_path, 24)
    except OSError:
        disclaimer_font = ImageFont.load_default()

    # Calculate bottom margin positioning
    line_height = 30
    total_lines = len(disclaimer_points)
    total_disclaimer_height = total_lines * line_height
    start_y = 800 - 20 - total_disclaimer_height  # Ensure 20px bottom margin

    draw_justified_text(
        draw=draw,
        text_lines=disclaimer_points,
        font=disclaimer_font,
        start_x=40,
        start_y=start_y,
        line_width=720,  # 800 width minus 2*40 padding
        line_height=line_height,
        fill="black"
    )

    # Save the image
    background.save("img.jpg")
    return background

# def compress_to_10kb(image, output_path="img.jpg", target_kb=20):
#     quality = 95
#     step = 5
#     target_bytes = target_kb * 1024

#     while quality > 5:
#         buffer = BytesIO()
#         image.save(buffer, format='JPEG', quality=quality, optimize=True)
#         size = buffer.tell()

#         if size <= target_bytes:
#             with open(output_path, "wb") as f:
#                 f.write(buffer.getvalue())
#             print(f"✅ Compressed to {size / 1024:.2f} KB at quality {quality}")
#             return

#         quality -= step

#     print("❌ Could not compress under 10KB without major loss.")
#     return 2




def old_user_send(from_number):
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    result = list(appointment.find({"whatsapp_number": from_number}))
# Store only the latest appointment per patient
    unique_patients = {}
    latest_appointments = []

    if len(result)<1:
        return appointment_flow(from_number)

    # for record in result:
    #     patient_name = record.get("patient_name")
    #     display_name = (patient_name[:15] + "...") if len(patient_name) > 10 else patient_name
    #     if patient_name and patient_name not in unique_patients:
    #         unique_patients[patient_name] = True
        
    #         latest_appointments.append({
    #         "id": "appoint_id"+str(record["_id"]) if "_id" in record else "",  # Handle missing _id
    #         "title": display_name
    #             })

    all_buttons = latest_appointments + [{"id": "book_appointment", "title": "New Patient"},{"id": "enrole-patient", "title": "Enrole Patient"},{"id": "Re-Appointment", "title": "Re-Appointment"}]

# Function to send buttons in batches of 3
    def send_whatsapp_buttons(to_number, buttons_list):
        # for i in range(0, len(buttons_list), 3): 
            # buttons = buttons_list[i:i+3] 

            last_three_buttons = buttons_list[-3:]

            payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": "Choose Option:"},
                "action": {
                    "buttons": [{"type": "reply", "reply": btn} for btn in last_three_buttons]
                }
            }
        }

            response = requests.post(external_url, headers=headers, json=payload)

       
         

# Send multiple messages with 3 buttons per message
    send_whatsapp_buttons(from_number, all_buttons)

    
    # response = requests.post(external_url, json=payloadx, headers={'Authorization': 'Bearer EAAJdr829Xj4BOxyhp8MzkQqZCr92HwzYQMyDjZBhWZBqUej9YnYqTBefwyGeIZAUOhSk3y9AspLT69frxyYsWb6ea7jAGP4xm3BCxkAF5SXMqLeY3SpYt5AUUi0CkUIhk8AC6S1H6TIr0RLQHf3Tfo6ZBblcMZCBoc81nqVTidywfSK4FoWZAZCXenHHqRr5wAtE5D2tIGf87f8B7wuXUcWyK77Wca1ZBR3tqxQMOkK6L6BUZD','Content-Type': 'application/json'})
    # print(jsonify(response.json()))
    return "OK", 200



def sendthankyou(recipientNumber):
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"
    payload = {
  'messaging_product': 'whatsapp',
  'receipient_type':"individual",
  'to': recipientNumber,
  'text':{'body':'Thank You & Have a Good Day'},
  'type': 'text'
    }
    response = requests.post(external_url, json=payload, headers=headers)

    print(response)

    return "OK", 200



def sameordef(from_number, name):
    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    all_buttons = [
    {"id": "Same_person", "title": "Same patient"},
    {"id": "Different_person", "title": "Different patient"}
    ]

# Function to send buttons in batches of 3
    def send_whatsapp_buttons(to_number, buttons_list):
        for i in range(0, len(buttons_list), 3):  # Send in groups of 3
            buttons = buttons_list[i:i+3]  # Get 3 buttons at a time

            payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": f"We noticed that someone with the same name *{name}* has already booked an appointment.\n Are you the same patient who already booked, or someone different?"},
                "action": {
                    "buttons": [{"type": "reply", "reply": btn} for btn in buttons]
                }
            }
        }

            response = requests.post(external_url, headers=headers, json=payload)
       
         

# Send multiple messages with 3 buttons per message
    send_whatsapp_buttons(from_number, all_buttons)

    # response = requests.post(external_url, json=payloadx, headers={'Authorization': 'Bearer EAAJdr829Xj4BOxyhp8MzkQqZCr92HwzYQMyDjZBhWZBqUej9YnYqTBefwyGeIZAUOhSk3y9AspLT69frxyYsWb6ea7jAGP4xm3BCxkAF5SXMqLeY3SpYt5AUUi0CkUIhk8AC6S1H6TIr0RLQHf3Tfo6ZBblcMZCBoc81nqVTidywfSK4FoWZAZCXenHHqRr5wAtE5D2tIGf87f8B7wuXUcWyK77Wca1ZBR3tqxQMOkK6L6BUZD','Content-Type': 'application/json'})
    # print(jsonify(response.json()))
    return "OK", 200



def same_name(from_number,ap_type):

    data = templog2.find_one({'_id':from_number})

    entry = data.get('entry', [])[0]  # Extract first entry
    changes = entry.get('changes', [])[0]  # Extract first change
    value = changes.get('value', {})

    message_info = value.get('messages', [])[0] 
    response_json_str = data['entry'][0]['changes'][0]['value']['messages'][0]['interactive']['nfm_reply']['response_json']
    response_data = json.loads(response_json_str)
    print(response_data)

    if response_data.get('role')=='personal_flow':
        return custom_book_appointment(data)

    name = response_data.get('Patient_Name_2')
    pname = 'none'
    date = response_data.get('Date_of_appointment_0')
    slot = response_data.get('Time_Slot_1')
    vaccine = response_data.get('vaccine')

    email = 'none'
    symptoms = 'none'
    age = 'none'
    dob = 'none'
    city = 'none'
    address = 'none'

    if response_data.get('Guardian_Name'):
        pname = response_data.get('Guardian_Name')
    else:
        pname = 'none'


    if response_data.get('Email_4'):
        email = response_data.get('Email_4')
    else:
        email = 'none'

    if response_data.get('Other_Symptoms_5'):
        symptoms = response_data.get('Other_Symptoms_5')
    else:
        symptoms = 'none'

    if response_data.get('Age_3'):
        age = response_data.get('Age_3')
    else:
        age = 'none'

    if response_data.get('Date_Of_Birth'):
        dob = response_data.get('Date_Of_Birth')
    else:
        dob = 'none'

    if response_data.get('City'):
        city = response_data.get('City')
    else:
        city = 'none'

    if response_data.get('Address'):
        address = response_data.get('Address')
    else:
        address = 'none'

    from_number = message_info.get('from')
    timestamp = message_info.get('timestamp')

    doctor_id = '67ee5e1bde4cb48c515073ee'

    # result = list(doctors.find({"doctor_phone_id": doctor_id}, {"_id": 0}))  # Convert cursor to list
    # data_length = len(result)

    dataset = {
        'patient_name': name,
        'guardian_name': pname,
        'date_of_appointment': date,
        'time_slot': slot,
        'doctor_phone_id':doctor_id,
        'email' : email,
        'symptoms' : symptoms,
        'age' : age,
        'timestamp' : timestamp,
        'whatsapp_number' : from_number,
        'date_of_birth' : dob,
        'city' : city,
        'address' : address,
        'role':'appointment',
        'status':'created',
        "createdAt": 'x',
        "vaccine":vaccine
            }
    
    date_str = date
    xdate = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = xdate - timedelta(days=2)

    
    from_date = datetime.strptime(new_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
    todate = datetime.strptime(date_str, "%Y-%m-%d")
    todate = todate.replace(hour=23, minute=59, second=59)  # Ensure full-day inclusion

# Query with date filtering (Convert date_of_appointment to datetime in query)
    result = list(appointment.find({
    "whatsapp_number": from_number,
    "patient_name": name,
    "doctor_phone_id": doctor_id,
    "amount":{"$gt": 0},
    "$expr": {
        "$and": [
            {"$gte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, from_date]},
            {"$lte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, todate]}
        ]
    }
    }).sort("date_of_appointment", -1).limit(1)) 

    if len(result)>0 and ap_type=='same':

        retrieved_data = result[0]
        result = list(appointment.find({"doctor_phone_id": retrieved_data['doctor_phone_id'], "date_of_appointment":date,"amount":{"$gt": -1}}, {"_id": 0}))  # Convert cursor to list
        data_length = 1
        if result:
            data_length = len(result)+1

        xdate = date
        date_obj = datetime.strptime(xdate, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y%m%d")

        pay_id = str(retrieved_data['pay_id'])
        pay_id = "old_"+pay_id

        img_date = str(retrieved_data['date_of_appointment'])

        appoint_number = str(formatted_date)+'-'+str(data_length)

        dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        fee = float(dxxocument.get('appointmentfee'))




        index_number = getindex(retrieved_data['doctor_phone_id'],slot,xdate)


        xid = appointment.insert_one({**dataset,'status':'success','pay_id':pay_id,'appoint_number':appoint_number,'amount':0,'appointment_index':index_number}).inserted_id


        tempdata = {"number":from_number,"current_id":xid,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        

        name = str(retrieved_data['patient_name'])
        phone = str(retrieved_data['whatsapp_number'])

        return success_appointment(img_date,index_number,name,date,slot,phone)
    else:
        id = str(appointment.insert_one(dataset).inserted_id)
        print(id)

        dxxocument = doctors.find_one({'_id':ObjectId('67ee5e1bde4cb48c515073ee')})
        fee = float(dxxocument.get('appointmentfee'))
        # paymentlink = dxxocument.get('paymentlink')

        tempdata = {"number":from_number,"current_id":id,"_id":from_number}
        try:
            templog.insert_one(tempdata)
        except:
            templog.update_one({'_id': from_number}, {'$set': tempdata})

        dxocument = admin.find_one({'_id':ObjectId('67ee6000fd6181e38ec1181c')})
        razorpayid = dxocument.get('razorpayid')
        razorpaykey = dxocument.get('razorpaykey')


        link = pay_link(name,from_number,'care2connect.cc@gmail.com',id,fee,razorpayid,razorpaykey)


        # link = paymentlink
        print(link)
        amount = fee
        return send_payment_flow(from_number,name,date,slot,amount,link)
    


def send_selection(from_number):

    doctor_id = '67ee5e1bde4cb48c515073ee'

    date_str = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d")
    # date_str = '2025-05-30'
    xdate = datetime.strptime(date_str, "%Y-%m-%d")
    new_date = xdate - timedelta(days=2)

    
    from_date = datetime.strptime(new_date.strftime("%Y-%m-%d"), "%Y-%m-%d")
    todate = datetime.strptime(date_str, "%Y-%m-%d")
    todate = todate.replace(hour=23, minute=59, second=59)  # Ensure full-day inclusion

    print(from_date,todate)

# Query with date filtering (Convert date_of_appointment to datetime in query)
    result = list(appointment.find({
    "whatsapp_number": from_number,
    # "patient_name": name,
    "doctor_phone_id": doctor_id,
    "amount":{"$gt": 0},
    "$expr": {
        "$and": [
            {"$gte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, from_date]},
            {"$lte": [{"$dateFromString": {"dateString": "$date_of_appointment"}}, todate]}
        ]
    }
    }).sort("date_of_appointment", -1).limit(10))

    print(result)

    def dateme(date):
        original_date = datetime.strptime(date, "%Y-%m-%d")
        new_date = original_date + timedelta(days=2)
        formatted_date = new_date.strftime("%d-%m-%Y")
        return formatted_date

    rows = [
    {
        "id": str(app["_id"]),
        "title": app["patient_name"],
        "description": 'Appointment Valid Till 08:30AM (Morning) of '+dateme(app["date_of_appointment"]),
    }
    for app in result
    ]

    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    incoming_data = {
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": from_number,
  "type": "interactive",
  "interactive": {
    "type": "list",
    "header": {
      "type": "text",
      "text": "Re-Appointment"
    },
    "body": {
      "text": "Subject to Availability of Appointments Slot"
    },
    # "footer": {
    #   "text": "Powered by WhatsApp Cloud API"
    # },
    "action": {
      "button": "Active Appointments",
      "sections": [
        {
          "title": "Options",
          "rows": rows
        }
      ]
    }
  }
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    return "OK", 200



def send_selection_enroll(from_number):

    result = list(appointment.find({"whatsapp_number": from_number}))
# Store only the latest appointment per patient
    unique_patients = {}
    latest_appointments = []

    # if len(result)<1:
    #     return appointment_flow(from_number)

    for record in result:
        patient_name = record.get("patient_name")
        display_name = (patient_name[:15] + "...") if len(patient_name) > 10 else patient_name
        if patient_name and patient_name not in unique_patients:
            unique_patients[patient_name] = True
            

            latest_appointments.append({
            "id": str(record["_id"]) if "_id" in record else "",  # Handle missing _id
            "title": display_name,
            "father":str(record["guardian_name"])
                })

    # all_buttons = latest_appointments + [{"id": "book_appointment", "title": "New Patient"},{"id": "enrole-patient", "title": "Enrole Patient"},{"id": "Re-Appointment", "title": "Re-Appointment"}]


    rows = [
    {
        "id": str(app["id"]),
        "title": app["title"],
        "description": 'S/o '+app["father"],
    }
    for app in latest_appointments[-10:]
]

    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    incoming_data = {
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": from_number,
  "type": "interactive",
  "interactive": {
    "type": "list",
    "header": {
      "type": "text",
      "text": ""
    },
    "body": {
      "text": "Book Appointment – Existing Patients"
    },
    # "footer": {
    #   "text": "Powered by WhatsApp Cloud API"
    # },
    "action": {
      "button": "Choose Patient",
      "sections": [
        {
          "title": "Options",
          "rows": rows
        }
      ]
    }
  }
}

    response = requests.post(external_url, json=incoming_data, headers=headers)
    return "OK", 200






def send_pdf_utility(from_number):

    external_url = "https://graph.facebook.com/v22.0/563776386825270/messages"  # Example API URL

    incoming_data = {
  "messaging_product": "whatsapp",
  "to": from_number,
  "type": "template",
  "template": {
    "name": "pdf_download",
    "language": {
      "code": "en"
    },
    "components": [
      {
        "type": "body",
        "parameters": [
          
        ]
      }
    ]
  }
}


    response = requests.post(external_url, json=incoming_data, headers=headers)
    return "OK", 200





