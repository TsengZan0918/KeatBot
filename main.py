# 1. 匯入所有需要的工具
import os
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

# 2. 從環境變數讀取我們的祕密金鑰
TELEGRAM_BOT_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']

# 3. 設定 Gemini AI 模型
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 4. 建立一個小網站來讓部署平台保持服務清醒
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 5. 定義當使用者輸入 /start 指令時，機器人該如何回應
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """當使用者發送 /start 時，發送歡迎訊息"""
    await update.message.reply_text('您好！我是您的中文-高棉文-英文三向翻譯助理。\n\n請直接傳送任何這三種語言的句子給我。')

# 6. 定義處理所有文字訊息的核心翻譯功能
async def translate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """接收使用者的訊息，並使用 Gemini AI 進行三向翻譯"""
    user_text = update.message.text
    chat_id = update.message.chat_id
    
    thinking_message = await context.bot.send_message(chat_id=chat_id, text='翻譯中，請稍候...')

    try:
        # --- 這是我們給 AI 的核心指令 (Prompt)，決定了翻譯的品質和方向 ---
        prompt = f"""
        你是一位精通繁體中文、英文、柬埔寨高棉文，且**極具文筆與文化敏感度**的本地化專家。

        **你的唯一、且最重要的核心任務：**
        進行**風格轉換翻譯**。你不僅要翻譯字面意思，更必須**深度理解**原文的**語氣、風格、情境和情感**（例如：可愛、俏皮、正式、專業、俚語、網路用語等），然後用目標語言**最自然、最貼切的文筆**來**重現**這種感覺。你的價值在於詞彙的選擇和句型的建構，而不僅是字面翻譯。

        **執行流程：**
        1.  **分析風格**: 深度分析原文的風格和意圖。
        2.  **翻譯**: 根據分析，將其完整意思翻譯成另外兩種語言。
        3.  **排序**: 嚴格遵守下面的排序規則。

        **翻譯與排序規則：**
        - 如果原文主要是**繁體中文**，回覆必須是**第一行高棉文**，**第二行英文**。
        - 如果原文主要是**高棉文**，回覆必須是**第一行繁體中文**，**第二行英文**。
        - 如果原文主要是**英文**，回覆必須是**第一行繁體中文**，**第二行高棉文**。

        **Emoji 規則：**
        - 如果原文包含 emoji，可以在翻譯中保留它們以輔助語氣，但**傳達風格的主要方法必須是透過文字的「選詞」和「句法結構」**。

        **絕對禁止**：
        1.  禁止包含原文。
        2.  禁止包含任何語言標籤 (例如 "英文:")。
        3.  禁止任何除了翻譯文本和原文 emoji 之外的解釋或對話。

        要翻譯的原文是："{user_text}"
        """

        # 將指令傳送給 Gemini AI
        response = await model.generate_content_async(prompt)
        
        # 編輯剛剛「思考中」的訊息，更新為最終的翻譯結果
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=thinking_message.message_id,
            text=response.text
        )

    except Exception as e:
        # 如果發生任何錯誤，印出錯誤訊息並通知使用者
        print(f"發生錯誤: {e}")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=thinking_message.message_id,
            text='抱歉，翻譯時發生了一點問題，請稍後再試。'
        )

# 7. 主程式：設定機器人並讓它開始運作
def main() -> None:
    """啟動機器人並開始監聽訊息"""
    print("機器人啟動中...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # 設定指令處理器 (/start)
    application.add_handler(CommandHandler("start", start))

    # 設定訊息處理器 (處理所有非指令的文字訊息)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_message))

    print("機器人已上線，正在監聽...")
    # 開始運行機器人
    application.run_polling()

# 8. 程式的進入點：先啟動小網站，再啟動機器人
if __name__ == '__main__':
    keep_alive() 
    main()
