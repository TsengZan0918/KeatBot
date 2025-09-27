# 1. 匯入所有需要的工具
import os
import google.generativeai as genai

print("--- Gemini 診斷工具已啟動 ---")

# 2. 從環境變數讀取您的祕密金鑰
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    print("\n[錯誤] 找不到 GEMINI_API_KEY 環境變數。")
    print("請確認您已在部署平台的 Secrets 或環境變數設定中，正確填寫了您的 API 金鑰。")
else:
    print("\n[成功] 已讀取到 GEMINI_API_KEY。")
    genai.configure(api_key=GEMINI_API_KEY)

    try:
        # 3. 嘗試列出您的帳戶所有可用的 AI 模型
        print("\n步驟 1: 正在嘗試列出您帳戶可用的模型...")
        
        found_models = False
        for m in genai.list_models():
            # 我們只關心能用來「生成內容」的模型
            if 'generateContent' in m.supported_generation_methods:
                print(f"  - 找到可用模型: {m.name}")
                found_models = True
        
        if not found_models:
            print("  [警告] 您的帳戶下找不到任何可用於內容生成的模型。")

        # 4. 嘗試用一個具體的模型來生成內容
        target_model = 'gemini-1.5-flash'
        print(f"\n步驟 2: 正在嘗試使用 '{target_model}' 模型生成內容...")
        
        model = genai.GenerativeModel(target_model)
        response = model.generate_content("這是一句測試。")
        
        print("\n--- 診斷結果 ---")
        print(f"[成功] 您的 API 金鑰可以正常使用 '{target_model}' 模型！")
        print(f"AI 回應: {response.text}")

    except Exception as e:
        print("\n--- 診斷結果 ---")
        print(f"[失敗] 在執行過程中發生了錯誤。")
        print("\n詳細錯誤訊息如下：")
        print(e)
```

### 第三步：執行「診斷工具」並回報結果

現在，我們要來運行這個診斷工具。

1.  在您部署的平台（例如 Replit），找到一個叫做「**Shell**」或「**終端機 (Terminal)**」的視窗。
2.  請在這個 Shell 視窗中，輸入以下指令，然後按下 Enter：
    ```bash
    python test_gemini.py
    
