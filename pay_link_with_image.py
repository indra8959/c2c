from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
import requests


def imagesend(whatsapp_no, PDF_FILE_PATH, link):

    WHATSAPP_ACCESS_TOKEN = "EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD"
    # PDF_FILE_PATH = 'img.jpg'

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

    headers={'Authorization': 'Bearer EACHqNPEWKbkBO33utbtE1EMW5T1B8KlYqSpLDepuZCdrEY9unIfGmwnlZB4XgfEFQw2ohjGAAoBL1OHY08kftSW0ZBEvX5eXIodrY2gghys3IEoyoKwZCvHh0ZBd7I6eB9ttTEV1fsghWvpzycfIr5pIVIeftLpO0jlFLp9FZB31dd48QZCzmYSxSvKuIFkZAOlchwZDZD','Content-Type': 'application/json'}

        
    url = f"https://graph.facebook.com/v22.0/563776386825270/messages"

    payload = {
  "messaging_product": "whatsapp",
  "to": whatsapp_no,
  "type": "template",
  "template": {
    "name": "razorpay_with_image",
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
      },
  
                {
                "type": "button",
                "index": "0",
                "sub_type": "url",
                "parameters": [
                    {
                        "type": "text",
                        "text": link
                    }
                ]}
    ]
  }
}


    

    response = requests.post(url, json=payload, headers=headers)

    print(response)

    return "OK", 200





def pay_now_image(number,user_name,amount,date,slot,link):
    # Load background image
    bg_image_path = "de.png"
    background = Image.open(bg_image_path).convert("RGB")
    background = background.resize((600, 400))

    # Create drawing context
    draw = ImageDraw.Draw(background)

    # Load fonts with increased sizes
    font_header = ImageFont.truetype("pp.ttf", 36)       # For "Dear User"
    font_regular = ImageFont.truetype("pp.ttf", 28)      # For body lines
    font_warning = ImageFont.truetype("pp.ttf", 30)      # For red warning

    # Colors
    primary_color = "#4439A1"
    bottom_color = "red"

    # Dynamic user data
    # user_name = "Indrajeet"
    # amount = 220
    # date = "25-07-2025"
    # slot = "10:00 AM - 10:30 AM"

    # Function to draw centered text
    def draw_centered_text(text, y, font, fill):
        text_width = draw.textlength(text, font=font)
        x = (background.width - text_width) // 2
        draw.text((x, y), text, font=font, fill=fill)

    # Draw text lines (centered, bigger)
    draw_centered_text(f"Dear {user_name}", 25, font_header, primary_color)
    draw_centered_text(f"You are booking appointment for {date}", 80, font_regular, primary_color)
    draw_centered_text(f"& Slot {slot}. Please pay    {int(amount)}", 120, font_regular, primary_color)
    draw_centered_text(f"by tapping on the *Pay Now* link below to", 160, font_regular, primary_color)
    draw_centered_text(f"confirm this appointment.", 200, font_regular, primary_color)
    # draw_centered_text("*This payment link will be valid for next five", 290, font_warning, bottom_color)
    # draw_centered_text("minutes only", 330, font_warning, bottom_color)

    # Save the result
    background.save("centered_text_bigger_fonts.png")

    return imagesend(number, 'centered_text_bigger_fonts.png',link)







