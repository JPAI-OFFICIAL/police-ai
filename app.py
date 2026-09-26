import os
import requests
from fastapi import FastAPI, Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
import google.generativeai as genai

app = FastAPI()

# -------------------------------------------------------------
# Keys สำหรับเชื่อมต่อระบบ
# -------------------------------------------------------------
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "ad7d23568fbd9f0dc72bba51880f1827")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "วาง_CHANNEL_ACCESS_TOKEN_ตรงนี้")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "วาง_GEMINI_API_KEY_ตรงนี้")

# Setup Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Setup LINE SDK
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

SYSTEM_PROMPT = """
คุณคือ VIP Cyber Security Risk Analyst ผู้เชี่ยวชาญการประเมินภัยไซเบอร์และคดีหลอกลวง (Romance Scam, Investment Fraud, สลิปปลอม)
หน้าที่ของคุณ:
1. ประเมินความเสี่ยงจากรูปภาพหรือข้อความที่ส่งมา (ต่ำ / กลาง / สูง / วิกฤต)
2. สรุปจุดน่าสงสัยเป็นข้อๆ อย่างเป็นมืออาชีพ สุภาพ และเป็นทางการ
3. ให้คำแนะนำขั้นตอนถัดไป (เช่น อย่าเพิ่งโอนเงิน, รวบรวมหลักฐานแชท)
"""

@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    user_text = event.message.text
    prompt = f"{SYSTEM_PROMPT}\n\nข้อมูลจากลูกค้า: {user_text}"
    response = model.generate_content(prompt)
    reply_text = response.text

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    message_id = event.message.id
    image_url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
    img_data = requests.get(image_url, headers=headers).content

    image_part = {
        "mime_type": "image/jpeg",
        "data": img_data
    }
    prompt = f"{SYSTEM_PROMPT}\n\nช่วยตรวจสอบรูปภาพนี้ (สลิปโอนเงิน/รูปแชท/รูปโปรไฟล์) ว่ามีจุดน่าสงสัยหรือเป็นมิจฉาชีพหรือไม่"
    response = model.generate_content([prompt, image_part])
    reply_text = response.text

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )
