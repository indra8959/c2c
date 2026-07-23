# config.py

import os

# JWT Config
JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "supersecretjwtkey")

# MongoDB Atlas
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://pankajji442:N7EYdibmOQ4vPk0x@cluster1.rapvnpk.mongodb.net/")

# WhatsApp Cloud API
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN", "EACH6PXeLx50BO39th5RhjYBaIEm9WN1DeqyKTanvAM50PQ2cK10GrtVZBZCJiEH5ke8481Dzit3lhhAFB8ZCqZCxhJOIRHTeORvGdiMYYeXWIQRBDjq874W0SvrYqaTP9zsgycuRZCbx4RZAA5SzS2CdEmULMjFsuJBZCboc8cIPPu4oqmzIr178N0fkrQftXQ4uQZDZD")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "638286416039346")

# OTP Settings
OTP_LENGTH = 6
OTP_EXPIRY_SECONDS = 120  # in seconds
OTP_RESEND_INTERVAL = 60  # in seconds