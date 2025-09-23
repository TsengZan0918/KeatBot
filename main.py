# 1. 匯入所有需要的工具
import os
import re
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

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

# 6. 輔助函式：判斷訊息是否應該跳過翻譯 (正式版)
def should_skip_translation(text: str) -> bool:
    """
    判斷訊息是否應該被跳過，不進行翻譯。
    """
    # 檢查是否為被忽略的詞彙 (不分大小寫)
    ignored_words = {"yes", "no", "ohh", "ok", "okey", "hmmm", "ha", "haha", "good"}
    if text.strip().lower() in ignored_words:
        return True

    # 檢查是否只包含表情符號和空白字元
    if not text or text.isspace():
        return False

    # 包含絕大多數 Unicode emoji 的正規表示式
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f900-\U0001f9ff"  # supplemental symbols and pictographs
        "\u2600-\u26FF"        # miscellaneous symbols
        "\u2700-\u27BF"        # dingbats
        "]+", flags=re.UNICODE)

    # 移除所有 emoji 和空白字元
    text_without_emojis_and_space = emoji_pattern.sub('', text).strip()

    # 如果移除後字串為空，代表原文只包含 emoji，應該跳過
    if not text_without_emojis_and_space:
        return True

    return False

# 7. 核心功能：定義處理所有文字訊息的翻譯功能
async def translate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    chat_id = update.message.chat_id
    
    if should_skip_translation(user_text):
        return

    thinking_message = await context.bot.send_message(chat_id=chat_id, text='翻譯中，請稍候...')

    try:
        if not model:
            raise ValueError("Gemini 模型未被初始化，請檢查 GEMINI_API_KEY。")

        prompt = f"""
        你是一位頂級的、精通繁體中文、英文、柬埔寨高棉文的**專業同步口譯員**。
        **你的唯一、且最重要的核心任務：**
        精準傳達**說話者的原始意圖**。你的翻譯必須極度**忠實於原文的精確含義、語氣和所有細微差別**。
        **執行流程：**
        1.  **分析意圖**: 深度分析原文的精準意圖和語氣。
        2.  **精準翻譯**: 將其完整意思翻譯成另外兩種語言。
        3.  **排序**: 嚴格遵守下面的排序規則。
        **翻譯與排序規則：**
        - 如果原文主要是**繁體中文**，回覆必須是**第一行高棉文**，**第二行英文**。
        - 如果原文主要是**高棉文**，回覆必須是**第一行繁體中文**，**第二行英文**。
        - 如果原文主要是**英文**，回覆必須是**第一行繁體中文**，**第二行高棉文**。
        **Emoji 規則：**
        - **只有在**使用者的原文句末帶有 emoji 時，才可以在每一句翻譯結果的句末，附上**完全相同**的 emoji。
        **強制執行規則：**
        - **你必須永遠輸出兩行翻譯**。如果你因任何原因無法提供其中一種語言的翻譯，**絕不允許**默默地省略它。你必須在該行輸出 `[翻譯無法提供]` 的文字。
        **絕對禁止**：
        1.  禁止包含原文。
        2.  禁止包含任何語言標籤 (例如 "英文:")。
        3.  禁止任何除了翻譯文本和原文 emoji 之外的解釋或對話。
        ---
        **範例:**
        使用者輸入: "你好嗎？"
        你的回覆:
        អ្នកសុខសប្បាយទេ?
        How are you?
        ---
        要翻譯的原文是："{user_text}"
        """

        response = await model.generate_content_async(prompt)
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=thinking_message.message_id,
            text=response.text
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
