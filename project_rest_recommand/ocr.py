import os
from dotenv import load_dotenv
import google.generativeai as genai

# 圖像辨識API
import google.generativeai as genai

from PIL import Image

from dotenv import load_dotenv
import os


def ocr_api(file_path):

    # 載入 .env 文件中的所有變數
    load_dotenv()

    # 使用 os.getenv 獲取環境變數
    api_key = os.getenv("Geminiapikey")

    # 設定 API 金鑰
    genai.configure(api_key=api_key)

    # 選擇模型（Gemini Pro）
    model = genai.GenerativeModel("gemini-1.5-flash-8b")

    # 讀取圖片
    image = Image.open(file_path)

    # 發送圖片 + 提示詞

    response = model.generate_content(["這是一張菜單的圖片，幫我用文字辨識找出其中的文字", image])

    text = response.text

    return text


def main():
    print(ocr_api())


# 標註進入點
if __name__ == "__main__":
    main()
