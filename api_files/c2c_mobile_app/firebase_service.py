import firebase_admin

from firebase_admin import (
    credentials,
    messaging
)

cred = credentials.Certificate(
    "firebase-service-account.json"
)

firebase_admin.initialize_app(cred)


def send_push_notification(
    token,
    title,
    body,
    data=None
):

    try:

        message = messaging.Message(

            notification=messaging.Notification(
                title=title,
                body=body
            ),

            data=data or {},

            token=token
        )

        response = messaging.send(message)

        return {
            "success": True,
            "response": response
        }

    except Exception as e:

        print("FCM SEND ERROR:", str(e))

        return {
            "success": False,
            "error": str(e)
        }
    
def send_bulk_notifications(
    tokens,
    title,
    body,
    data=None
):

    try:

        message = messaging.MulticastMessage(

            notification=messaging.Notification(
                title=title,
                body=body
            ),

            data=data or {},

            tokens=tokens
        )

        response = messaging.send_each_for_multicast(
            message
        )

        return {
            "success": True,
            "success_count":
            response.success_count,

            "failure_count":
            response.failure_count
        }

    except Exception as e:

        print("BULK FCM ERROR:", str(e))

        return {
            "success": False,
            "error": str(e)
        }