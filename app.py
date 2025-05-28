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


# 把 JSON 展平成單一列表形式
def flatten_examples(data_dict):
    examples = []
    for category, items in data_dict.items():
        for entry in items:
            q = entry.get("問題", "").strip()
            a = entry.get("回答", "")
            if not q or not a  == "nan":
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


def get_response(text):
    '''判斷文字內容所屬情境（根據 data_cache）

        回傳一段文字，或一個特殊字串，如 "傳送貼圖"
    '''
    examples = flatten_examples(data_cache)
    prompt = build_prompt(text, examples)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
        )

        full_answer = ""
        # 迭代生成器，逐塊獲取文本
        for chunk in response:
            # print(f"原始 chunk 類型: {type(chunk)}, 內容: {chunk}") # 僅用於調試

            # 檢查 chunk 是否為 tuple
            if isinstance(chunk, tuple) and len(chunk) == 2 and chunk[0] == 'candidates':
                # 如果是 tuple，其內容在 chunk[1]
                candidates_list = chunk[1]
            elif hasattr(chunk, 'candidates'):
                # 如果是預期的 GenerateContentResponse 物件
                candidates_list = chunk.candidates
            else:
                print(f"警告：無法識別的 chunk 結構: {type(chunk)}, 內容: {chunk}")
                continue  # 跳過無法處理的 chunk

            if candidates_list:
                # 遍歷所有候選答案 (通常只有一個)
                for candidate in candidates_list:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                # print('印出文本:', part.text) # 用於調試
                                full_answer += part.text
            else:
                # 處理沒有候選答案的 chunk (例如安全過濾或其他非文本內容)
                # print(f"警告：此 chunk 沒有可用的候選答案或文本內容: {chunk}")
                pass  # 您可以選擇跳過這個 chunk


        # 若 Gemini 多說了，試圖只擷取「系統回應」部分
        match = re.search(r"系統回應[:：]?[「\"](.+?)[」\"]", full_answer)
        if match:
            return match.group(1)

        return full_answer or "請問您能再描述詳細一點嗎？"

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
    '''根據 get_response() 回傳的內容，決定是 TextSendMessage 還是 StickerSendMessage
    '''
    user_message = event.message.text
    print(f"收到的 LINE 訊息: {user_message}")
    
    try:
        ai_response = get_response(user_message)
    
        # 檢查 AI 響應是否為空
        if not ai_response.strip(): # 使用 .strip() 移除空白字元後再檢查
            ai_response = "很抱歉，我暫時無法生成回應。請再試一次或換個問題。"

        if ai_response == "傳送貼圖":
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
