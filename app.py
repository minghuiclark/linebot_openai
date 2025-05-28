from flask import Flask, request, abort

from linebot import (LineBotApi, WebhookHandler)
from linebot.exceptions import (InvalidSignatureError)
from linebot.models import *
#======python的函數庫==========
import tempfile, os
import datetime
from google import genai
import time
import json
import re
import math  # 為了處理 NaN
import traceback
from dotenv import load_dotenv
#======python的函數庫==========
# 載入 .env 檔案
load_dotenv()

app = Flask(__name__)
static_tmp_path = os.path.join(os.path.dirname(__file__), 'static', 'tmp')
# Channel Access Token
line_bot_api = LineBotApi(os.getenv('CHANNEL_ACCESS_TOKEN'))
# Channel Secret
handler = WebhookHandler(os.getenv('CHANNEL_SECRET'))
# OPENAI API Key初始化設定
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
# genai.configure(api_key="gemini-2.0-flash-lite")
model_name = "gemini-2.0-flash-lite"
client = genai.Client(api_key=GOOGLE_API_KEY)


# 預載入 JSON

with open("customer_service.json", "r", encoding="utf-8") as f:
    data_cache = json.load(f)

def get_response(user_input):
    '''判斷文字內容所屬情境（根據 data_cache）

        回傳一段文字，或一個特殊字串，如 "傳送貼圖"
    '''
    system_prompt = "你是一位專業的客服助手，請用正體中文回應客戶問題。"

    prompt = f'請判斷 {user_input} 裡面的文字情境屬於 {data_cache} 裡面的哪一項？符合條件請回傳對應的文字就好，不要有其他的文字與字元。'
    content = system_prompt+prompt
    print(f"發送給 Gemini 的內容: {content}")

    response = client.models.generate_content(
        model=model_name,
        contents=content,)
    
    print('='*10)
    answer = response.text
    print('從ai 收到的回應',answer)

    return answer


# 監聽所有來自 /callback 的 Post Request
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


# 處理訊息        
#@handler.add(MessageEvent, message=TextMessage)
@handler.add(MessageEvent, message=Message)
def handle_message(event):
    '''根據 get_response() 回傳的內容，決定是 TextSendMessage 還是 StickerSendMessage
    '''
    msg_type = event.message.type
    user_id = event.source.user_id

    if msg_type== 'sticker':
        print(f"收到的 LINE貼圖 訊息:從{user_id} 收到 貼圖")

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請問有什麼需要協助的嗎？')
        )
        
    else:
        user_message = event.message.text
        print(f"收到的 LINE 文字訊息:從{user_id} 收到 {user_message}")
        try:
            ai_response = get_response(user_message)
            print(f"準備發送給 Line 的訊息: '{ai_response}'")
        
            # 檢查 AI 響應是否為空
            if not ai_response.strip(): # 使用 .strip() 移除空白字元後再檢查
                ai_response = "很抱歉，我暫時無法生成回應。請再試一次或換個問題。"

            if ai_response == "傳送貼圖":
                print(f"進入貼圖區")
                sticker = StickerSendMessage(package_id='789', sticker_id='10856')
                line_bot_api.reply_message(event.reply_token, sticker)

                
            else:
                # 回傳純文字        
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=ai_response)
                )
        except:
            print(traceback.format_exc())
            #print(f"準備發送給 Line 的訊息: '{ai_response}'")
            line_bot_api.reply_message(event.reply_token, TextSendMessage('你所使用的OPENAI API key額度可能已經超過，請於後台Log內確認錯誤訊息'))

@handler.add(PostbackEvent)
def handle_message(event):
    print(event.postback.data)


@handler.add(MemberJoinedEvent)
def welcome(event):
    uid = event.joined.members[0].user_id
    gid = event.source.group_id
    profile = line_bot_api.get_group_member_profile(gid, uid)
    name = profile.display_name
    message = TextSendMessage(text=f'{name}歡迎加入')
    line_bot_api.reply_message(event.reply_token, message)
        
        
import os
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
