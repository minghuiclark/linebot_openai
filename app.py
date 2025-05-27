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

    full_answer = ""
    try:
            # 獲取流式響應，確保 stream=True

        # 獲取串流響應
        # 注意這裡使用 genai.GenerativeModel 而不是 client.models.generate_content
        # 因為 client 通常就是 genai 模組本身
        # response_stream = client.GenerativeModel(model_name=model_name).generate_content(
        #     contents=contents,            
        # )
        response_stream = client.models.generate_content(
        model=model_name,
        contents=contents,
    )

        # 迭代生成器，逐塊獲取文本
        for chunk in response_stream:
            # **關鍵修改處**
            # 檢查 chunk 是否有 candidates，並且有內容
            if chunk.candidates and chunk.candidates[0].content and chunk.candidates[0].content.parts:
                for part in chunk.candidates[0].content.parts:
                    if hasattr(part, 'text') and part.text:
                        # print('印出 chunk.candidates[0].content.parts[0].text:', part.text) # 用於調試
                        full_answer += part.text
            else:
                # 處理沒有文本內容的 chunk (例如安全過濾或其他非文本內容)
                # print(f"警告：此 chunk 沒有可用的文本內容: {chunk}")
                pass # 您可以選擇跳過這個 chunk

    except Exception as e:
        print(f"處理 Gemini 回應時發生錯誤: {e}. Chunk type: {type(chunk) if 'chunk' in locals() else 'N/A'}, Chunk content: {chunk if 'chunk' in locals() else 'N/A'}")
        # 在實際應用中，您可能需要更好的錯誤處理機制
        return "很抱歉，處理您的請求時發生錯誤。"

    # 印出完整的響應文本 (用於調試，正式部署時可移除)
    print("完整的 Gemini 回應文本:", full_answer)

    # 重組回應
    # 移除句號（如果這是您的需求）
    answer = full_answer.replace('。', '') # 注意：如果模型回應沒有句號，這行不會有效果
    print(f"GPT_response 返回的答案: '{answer}'")
    return answer

# --- 如何使用 (範例) ---
# 假設您已經安裝了 google-generativeai 庫並配置了 API Key
# import os
# genai.configure(api_key=os.environ["GEMINI_API_KEY"]) # 建議從環境變數讀取 API Key

# client_instance = genai # 或者您可以根據您的初始化方式設定
# model_used = "gemini-pro"

# test_message = "你好，請給我一個關於貓的笑話。"
# response_from_gemini = GPT_response(test_message, client_instance, model_used)
# print("最終 Line Bot 回應:", response_from_gemini)


def GPT_response2(text):
    # 接收回應

    contents = [
        {
            "parts": [
                {"text": text}
            ]
        }
    ]

    # 獲取流式響應，確保 stream=True
    response_stream = client.models.generate_content(
        model=model_name,
        contents=contents,
    )

    full_answer = ""
    # 迭代生成器，逐塊獲取文本
    for chunk in response_stream:
        # **關鍵修改開始**
        # 嘗試從 chunk 中獲取文本
        try:
            # 這是最直接的方式，嘗試獲取 chunk.text
            # 如果 chunk 是 GenerateContentResponse 對象，這會成功
            if hasattr(chunk, 'text') and chunk.text:
                print('印出chunk.text',chunk.text)
                full_answer += chunk.text
            # 如果 chunk 是一個具有 parts 屬性的對象 (例如 ResponseCandidate)
            # 並且你想拼接所有 parts 的文本
            elif hasattr(chunk, 'parts'):
                for part in chunk.parts:
                    if hasattr(part, 'text') and part.text:
                        full_answer += part.text
        except Exception as e:
            # 捕獲其他可能的錯誤類型 (例如當 chunk 是 tuple 時)
            print(f"警告：處理 chunk 時發生錯誤: {e}. Chunk type: {type(chunk)}, Chunk content: {chunk}")
            # 您可以選擇跳過這個 chunk，或者根據需要進行其他處理
            pass

    # 印出完整的響應文本 (用於調試，正式部署時可移除)
    print(full_answer) 
    
    # 重組回應
    # 移除句號（如果這是您的需求）
    answer = full_answer.replace('。', '')
    #answer = full_answer['choices'][0]['text'].replace('。','')
    print(f"GPT_response 返回的答案: '{answer}'")
    return answer
    
def GPT_response1(text):
    # 接收回應   
    
    #response = openai.Completion.create(model="gpt-3.5-turbo-instruct", prompt=text, temperature=0.5, max_tokens=500)
    response =client.models.generate_content_stream(model=model_name,contents=text)
    print(response.text)
    # 重組回應
    answer = response['choices'][0]['text'].replace('。','')
    #answer = response.text
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
def handle_message1(event):
    msg = event.message.text
    
    try:
        GPT_answer = GPT_response(msg)
        print(GPT_answer)
        print(f"準備發送給 Line 的訊息: '{GPT_answer}'")
        line_bot_api.reply_message(event.reply_token, TextSendMessage(GPT_answer))
    except:
        print(traceback.format_exc())
        print(f"準備發送給 Line 的訊息: '{GPT_answer}'")
        line_bot_api.reply_message(event.reply_token, TextSendMessage('你所使用的OPENAI API key額度可能已經超過，請於後台Log內確認錯誤訊息'))
        
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
