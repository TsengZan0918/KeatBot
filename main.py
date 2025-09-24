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

# 3. 設定 Gemini AI 模型 (升級版)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # --- 使用更強大的 Pro 模型以提升翻譯品質 ---
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
else:
    model = None

# 新增：建立一個全域變數來儲存每個對話的歷史紀錄
chat_histories = {}

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
    await update.message.reply_text(
        '您好！我是您的中文-高棉文-英文三向翻譯助理。\n\n'
        '我會記住最近的對話以提升翻譯準確度。\n'
        '如果需要開始新的對話，請傳送 /clear 清除歷史紀錄。'
    )

# 新增：定義 /clear 指令的功能
async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    if chat_id in chat_histories:
        del chat_histories[chat_id]
        await update.message.reply_text('對話歷史已清除。')
    else:
        await update.message.reply_text('目前沒有對話歷史可供清除。')

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

# 7. 核心功能：定義處理所有文字訊息的翻譯功能 (上下文強化版)
async def translate_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_text = update.message.text
    chat_id = update.message.chat_id
    
    if should_skip_translation(user_text):
        return

    thinking_message = await context.bot.send_message(chat_id=chat_id, text='翻譯中，請稍候...')

    try:
        if not model:
            raise ValueError("Gemini 模型未被初始化，請檢查 GEMINI_API_KEY。")

        # --- 上下文升級 ---
        # 1. 取得此對話的歷史紀錄
        history = chat_histories.get(chat_id, [])
        formatted_history = "\n".join(history)
        if not formatted_history:
            formatted_history = "[無歷史紀錄]"

        prompt = f"""
        **身分**: 你是一位頂級的、精通繁體中文、英文、柬埔寨高棉文的專業同步口譯員。
        **核心任務**: 你的唯一任務是精準傳達原文的意圖。翻譯必須忠實於原文的精確含義、語氣和所有細微差別。
        **最高原則**: 準確性永遠高於流暢性。在忠於原文和使譯文聽起來更自然之間，永遠選擇前者。

        **執行流程 (必須嚴格遵守):**
        1.  **參考對話歷史**: 仔細閱讀下面的「對話歷史」，以理解當前對話的上下文、語氣和任何特定術語。
        2.  **識別語言**: 判斷以下「待翻譯原文」是 `繁體中文`、`高棉文` 還是 `英文`。
        3.  **應用規則**: 根據你識別出的語言和對話上下文，將其翻譯成另外兩種語言，並嚴格按照以下格式輸出：
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
        **對話歷史 (用於提供上下文):**
        {formatted_history}
        ---
        **待翻譯原文**: "{user_text}"
        """
        
        generation_config = genai.types.GenerationConfig(
            temperature=0.1
        )

        response = await model.generate_content_async(
            prompt,
            generation_config=generation_config
        )
        
        if not response.text or response.text.isspace():
            raise ValueError("Gemini 模型返回了空的翻譯結果。")
        
        clean_text = html.unescape(response.text.strip())

        # --- 上下文升級 ---
        # 2. 更新歷史紀錄
        history.append(f"原文: {user_text}")
        history.append(f"譯文:\n{clean_text}")
        
        # 3. 管理歷史紀錄大小 (保留最近 3 次對話，共 6 則訊息)
        if len(history) > 6:
            chat_histories[chat_id] = history[-6:]
        else:
            chat_histories[chat_id] = history

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
    application.add_handler(CommandHandler("clear", clear_history)) # 新增 clear 指令
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, translate_message))
    
    print("機器人已上線，正在監聽...")
    application.run_polling()

# 9. 程式的進入點：先啟動小網站，再啟動機器人
if __name__ == '__main__':
    keep_alive()
    main()

