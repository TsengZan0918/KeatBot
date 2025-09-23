# 1. 匯入所有需要的工具
import os
import re
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from flask import Flask
from threading import Thread

# 2. 從環境變數讀取我們的祕密金鑰
# 請確保您在部署環境中已設定 TELEGRAM_BOT_TOKEN 和 GEMINI_API_KEY
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# 3. 設定 Gemini AI 模型
# 只有在金鑰存在時才設定
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
    """當使用者發送 /start 時，發送歡迎訊息"""
    await update.message.reply_text('您好！我是您的中文-高棉文-英文三向翻譯助理。\n\n請直接傳送任何這三種語言的句子給我。')

# 6. 輔助函式：判斷訊息是否應該跳過翻譯
def should_skip_translation(text: str) -> bool:
    """
    判斷訊息是否應該被跳過，不進行翻譯。
    """
    ignored_words = {"yes", "no", "ohh", "ok", "okey", "hmmm", "ha", "haha", "good"}
    if text.strip().lower() in ignored_words:
        return True
    if not text or text.isspace():
        return False
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
    text_without_emojis_and_space = emoji_pattern.sub('', text).strip()
    if not text_without_emojis_and_space:
        return True
    return False


# 7. 核心功能：定義處理所有文字訊息的翻譯功能 (偵錯版本)
async def translate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """接收使用者的訊息，並使用 Gemini AI 進行三向翻譯 (偵錯模式)"""
    user_text = update.message.text
    chat_id = update.message.chat_id
    
    print(f"--- 收到新訊息 ---")
    print(f"使用者 ({chat_id}) 傳送: {user_text}")

    if should_skip_translation(user_text):
        print("判斷為無需翻譯的訊息，已跳過。")
        return

    print("訊息需要翻譯，準備發送 '翻譯中...'")
    thinking_message = await context.bot.send_message(chat_id=chat_id, text='翻譯中，請稍候...')
    print("'翻譯中...' 訊息已發送。")

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
        要翻譯的原文是："{user_text}"
        """

        print("準備呼叫 Gemini API...")
        response = await model.generate_content_async(prompt)
        print("成功從 Gemini API 收到回應。")
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=thinking_message.message_id,
            text=response.text
        )
        print("成功編輯訊息，顯示翻譯結果。")

    except Exception as e:
        print("!!!!!!!!!!!!!! 發生嚴重錯誤 !!!!!!!!!!!!!!")
        print(f"錯誤類型: {type(e).__name__}")
        print(f"錯誤詳細資訊: {e}")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        
        error_message_to_user = f"抱歉，翻譯時發生了嚴重錯誤。\n\n[偵錯資訊]:\n{type(e).__name__}\n請檢查主控台(console)的詳細資訊。"
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=thinking_message.message_id,
            text=error_message_to_user
        )

# 8. 主程式：設定機器人並讓它開始運作
def main() -> None:
    """啟動機器人並開始監聽訊息"""
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
        print("!!!!!!!!!!!!!! 啟動失敗 !!!!!!!!!!!!!!")
        print("錯誤：TELEGRAM_BOT_TOKEN 或 GEMINI_API_KEY 環境變數未設定。")
        print("請檢查您的部署平台中的環境變數/Secrets設定。")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        return
        
    if not model:
        print("!!!!!!!!!!!!!! 啟動失敗 !!!!!!!!!!!!!!")
        print("錯誤：Gemini 模型初始化失敗，請檢查 GEMINI_API_KEY 是否有效。")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
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

---

### **下一步：請您執行並回報狀況**

換上這份完整程式碼後，請**重新啟動**您的機器人。

然後**最重要的**，請您：

1.  **再次確認您的 `TELEGRAM_BOT_TOKEN` 和 `GEMINI_API_KEY` 環境變數都設定正確。**
2.  傳送一個詞給機器人（例如「晚安」）。
3.  **把您部署平台「主控台 (Console)」裡印出來的所有文字，完整地複製給我。**

主控台的輸出是我們現在唯一能找出問題的線索，所以請務必將那些訊息提供給我。
