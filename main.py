# 1. 匯入所有需要的工具
import os
import re
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread
import html # 用於處理 HTML 字元實體

# 2. 從環境變數讀取我們的祕密金鑰
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 3. 設定 Gemini AI 模型
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

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
    await update.message.reply_text('您好！我是您的中文-高棉文-英文三向翻譯助理。\n\n請直接傳送任何這三種語言的句子給我。')

# 6. 輔助函式：判斷訊息是否應該跳過翻譯
def should_skip_translation(text: str) -> bool:
    """
    判斷訊息是否應該被跳過，不進行翻譯。
    """
    # 檢查是否為被忽略的詞彙 (不分大小寫)
    ignored_words = {"yes", "no", "ohh", "ok", "okey", "hmmm", "ha", "haha", "good"}
    if text.strip().lower() in ignored_words:
        return True

    if not text or text.isspace():
        return True # 空訊息也跳過

    # 修正版：使用更精準的 emoji 正規表示式，避免誤判中文字元
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Symbols & Pictographs
        "\U0001F680-\U0001F6FF"  # Transport & Map Symbols
        "\U0001F1E0-\U0001F1FF"  # Flags (iOS)
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\u2600-\u26FF"          # Miscellaneous Symbols
        "\u2700-\u27BF"          # Dingbats
        "]+", flags=re.UNICODE)

    text_without_emojis_and_space = emoji_pattern.sub('', text).strip()

    if not text_without_emojis_and_space:
        return True

    return False

# 7. 核心功能：定義處理所有文字訊息的翻譯功能 (Prompt 強化版)
async def translate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    chat_id = update.message.chat_id
    
    if should_skip_translation(user_text):
        return

    thinking_message = await context.bot.send_message(chat_id=chat_id, text='翻譯中，請稍候...')

    try:
        if not model:
            raise ValueError("Gemini 模型未被初始化，請檢查 GEMINI_API_KEY。")

        # --- 這部分是修改的核心 ---
        # 我們給予 AI 更明確的步驟，先識別語言，再根據結果執行翻譯和排序
        prompt = f"""
        **身分**: 你是一位頂級的、精通繁體中文、英文、柬埔寨高棉文的專業同步口譯員。
        **核心任務**: 你的唯一任務是精準傳達原文的意圖。翻譯必須忠實於原文的精確含義、語氣和所有細微差別。

        **執行流程 (必須嚴格遵守):**
        1.  **識別語言**: 首先，判斷以下「待翻譯原文」是 `繁體中文`、`高棉文` 還是 `英文`。
        2.  **應用規則**: 根據你識別出的語言，將其翻譯成另外兩種語言，並嚴格按照以下格式輸出：
            * **如果原文是 `繁體中文`**: 第一行輸出 `高棉文`，第二行輸出 `英文`。
            * **如果原文是 `高棉文`**: 第一行輸出 `繁體中文`，第二行輸出 `英文`。
            * **如果原文是 `英文`**: 第一行輸出 `繁體中文`，第二行輸出 `高棉文`。

        **格式化規則 (必須嚴格遵守):**
        * **禁止包含原文**: 絕對不要在你的回覆中包含原始文字。
        * **禁止包含語言標籤**: 絕對不要加上 "英文:" 或 "高棉文:" 這樣的標籤。
        * **禁止任何額外對話**: 你的回覆只能有兩行翻譯文字，禁止任何解釋或問候。
        * **Emoji 規則**: 只有在原文的句末有 emoji 時，才在每句譯文的句末附上完全相同的 emoji。
        * **失敗處理**: 如果無法提供某種語言的翻譯，必須在該行輸出 `[翻譯無法提供]`，絕不允許省略。

        ---
        **範例 1:**
        待翻譯原文: "你好嗎？"
        你的回覆:
        អ្នកសុខសប្បាយទេ?
        How are you?
        ---
        **範例 2:**
        待翻譯原文: "Good morning! ☀️"
        你的回覆:
        早安！☀️
        អរុណសួស្តី! ☀️
        ---
        **待翻譯原文**: "{user_text}"
        """

        response = await model.generate_content_async(prompt)
        
        # 增加一個健全性檢查，確保 AI 有回傳內容
        if not response.text or response.text.isspace():
            raise ValueError("Gemini 模型返回了空的翻譯結果。")
        
        # Gemini 有時會輸出 Markdown，我們清理一下，並處理HTML實體
        clean_text = html.unescape(response.text.strip())

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=thinking_message.message_id,
            text=clean_text
        )

    except Exception as e:
        print(f"發生錯誤: {e}")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=thinking_message.message_id,
            text='抱歉，翻譯時發生了一點問題，請稍後再試。'
        )

# 8. 主程式：設定機器人並讓它開始運作
def main() -> None:
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
        print("錯誤：TELEGRAM_BOT_TOKEN 或 GEMINI_API_KEY 環境變數未設定。")
        return
        
    if not model:
        print("錯誤：Gemini 模型初始化失敗，請檢查 GEMINI_API_KEY 是否有效。")
        return

    print("機器人啟動中...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_message))
    print("機器人已上線，正在監聽...")
    application.run_polling()

# 9. 程式的進入點：先啟動小網站，再啟動機器人
if __name__ == '__main__':
    keep_alive()
    main()
