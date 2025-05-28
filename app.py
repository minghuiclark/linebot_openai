from flask import Flask, request, abort

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
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
with open("customer_responses.json", "r", encoding="utf-8") as f:
    data_cache = json.load(f)


# 把 JSON 展平成單一列表形式
def flatten_examples(data_dict):
    examples = []
    for category, items in data_dict.items():
        for entry in items:
            q = entry.get("問題", "").strip()
            a = entry.get("回答", "").strip()
            if not q or not a or a.lower() == "nan":
                continue  # 略過無效的資料
            examples.append((q, a))
    return examples


def build_prompt(user_input, examples):
    system_prompt = "你是一位親切且專業的客服助手，請用正體中文簡潔且友善地回應客戶問題。"

    few_shot_examples = "\n".join([
        f"使用者輸入：「{q}」\n系統回應：「{a}」"
        for q, a in examples[:3]  # 可視需要取更多範例
    ])

    task_prompt = (
        f"{few_shot_examples}\n\n"
        f"使用者輸入：「{user_input}」\n"
        "請參考上方風格，回應最適合的內容。如果無法判斷，請回傳「請問您能再描述詳細一點嗎？」。"
    )

    return system_prompt + "\n\n" + task_prompt


def get_response(text, client, model_name):
    examples = flatten_examples(raw_data)
    prompt = build_prompt(text, examples)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
        )

        full_answer = ""
        for chunk in response:
            if chunk and chunk[1]:
                for candidate in chunk[1]:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                full_answer += part.text

        answer = full_answer.strip()

        # 若 Gemini 多說了，試圖只擷取「系統回應」部分
        match = re.search(r"系統回應[:：]?[「\"](.+?)[」\"]", answer)
        if match:
            return match.group(1)

        return answer or "請問您能再描述詳細一點嗎？"

    except Exception as e:
        print(f"處理 Gemini 回應時發生錯誤: {e}")
        return "很抱歉，處理您的請求時發生錯誤。"


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
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    print(f"收到的 LINE 訊息: {user_message}")
    
    try:
        ai_response = get_response(user_message)
    
        # 檢查 AI 響應是否為空
        if not ai_response.strip(): # 使用 .strip() 移除空白字元後再檢查
            ai_response = "很抱歉，我暫時無法生成回應。請再試一次或換個問題。"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=ai_response)
        )
    except:
        print(traceback.format_exc())
        print(f"準備發送給 Line 的訊息: '{ai_response}'")
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
