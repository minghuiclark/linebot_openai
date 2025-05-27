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

def GPT_response(text):
    """
    處理 Line Bot 接收到的訊息，並透過 Gemini 模型獲取回應。

    Args:
        text (str): Line Bot 接收到的輸入文字。
        client: 已配置好的 Google Generative AI 客戶端物件 (例如 genai 模組本身)。
        model_name (str): 要使用的 Gemini 模型名稱 (例如 "gemini-pro")。

    Returns:
        str: 從 Gemini 模型獲取並處理過的回應文字。
    """
    contents = [
        {
            "parts": [
                {"text": text}
            ]
        }
    ]
    con_text='你現在是專業的中文客服，請用正體中文回應，口氣輕鬆有禮。'
    content=con_text+text
    full_answer = ""
    try:
        response_stream = client.models.generate_content(
        model=model_name,
        contents=content,
    )

        # 迭代生成器，逐塊獲取文本
        for chunk in response_stream:
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
                continue # 跳過無法處理的 chunk

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
                pass # 您可以選擇跳過這個 chunk

    except Exception as e:
        print(f"處理 Gemini 回應時發生錯誤: {e}")
        # 在實際應用中，您可能需要更好的錯誤處理機制
        return "很抱歉，處理您的請求時發生錯誤。"

    # 印出完整的響應文本 (用於調試，正式部署時可移除)
    print("完整的 Gemini 回應文本:", full_answer)

    # 重組回應
    # 移除句號（如果這是您的需求）
    answer = full_answer.replace('。', '')
    print(f"GPT_response 返回的答案: '{answer}'")
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
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_message = event.message.text
    print(f"收到的 LINE 訊息: {user_message}")
    
    try:
        ai_response = GPT_response(user_message)
    
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
