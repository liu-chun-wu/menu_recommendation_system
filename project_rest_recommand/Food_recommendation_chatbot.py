import os
import requests
from typing import List
from dotenv import load_dotenv
import google.generativeai as genai
import fitz  # 要安裝PyMuPDF

import chromadb
from chromadb.api.types import Documents, Embeddings
from chromadb.utils.embedding_functions import EmbeddingFunction

from flask import Flask, request, jsonify
from flask_cors import CORS

import filetype

import ocr


# Download PDF and Extract text from PDF
def download_pdf(url, save_path):
    """
    從指定 URL 下載 PDF 文件並儲存到本地。

    :param url: PDF 文件的網址 (string)
    :param save_path: PDF 文件儲存的本地路徑 (string)
    """
    # 使用 requests 模組發送 HTTP GET 請求以獲取 PDF 文件
    response = requests.get(url)

    # 打開指定的本地儲存路徑，使用二進位寫入模式 ('wb')
    with open(save_path, 'wb') as f:
        # 將下載的文件內容寫入到本地文件中
        f.write(response.content)


def extract_text_from_pdf_file_obj(file):
    """
    從 PDF 檔案物件提取文本內容。

    :param file: PDF 文件的檔案物件 (e.g., 通過 open(file, 'rb') 獲取)
    :return: 提取的文本內容 (string)
    """
    try:
        with fitz.open(file.name) as doc:
            pdf_text = ""
            for page in doc:
                pdf_text += page.get_text()
        return pdf_text
    except Exception as e:
        return f"Error while reading PDF: {str(e)}"


def extract_text_from_pdf_file_path(file_path):
    """
    從 PDF 文件的路徑提取文本內容。

    :param file_path: PDF 文件的檔案路徑 (string)
    :return: 提取的文本內容 (string)
    """
    try:
        with fitz.open(file_path) as doc:
            pdf_text = ""
            for page in doc:
                pdf_text += page.get_text()
        return pdf_text
    except Exception as e:
        return f"Error while reading PDF: {str(e)}"


# 分割文本為小塊
def split_text(text: str,
               max_chunk_size: int = 500,
               overlap: int = 50) -> List[str]:
    """
    將長文本分割為多個小塊，支援塊之間的重疊。

    :param text: 要分割的文本 (string)
    :param max_chunk_size: 每個文本塊的最大大小 (int)
    :param overlap: 每個文本塊之間的重疊大小 (int)
    :return: 分割後的文本塊列表 (List of strings)
    """
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chunk_size, len(text))
        chunks.append(text[start:end].strip())
        start += max_chunk_size - overlap
    return chunks


# 自定義 Gemini 嵌入函數
class GeminiEmbeddingFunction(EmbeddingFunction):

    def __init__(self,
                 api_key: str,
                 model: str = "models/embedding-001",
                 title: str = "Restaurant Menu"):
        self.api_key = api_key
        self.model = model
        self.title = title
        genai.configure(api_key=self.api_key)

    def __call__(self, input: Documents) -> Embeddings:
        return [
            genai.embed_content(model=self.model,
                                content=doc,
                                task_type="retrieval_document",
                                title=self.title)["embedding"] for doc in input
        ]


# 向現有的 ChromaDB 集合中新增文件。
def update_chroma_db(client, collection_name: str, new_documents: List[str]):
    """
    向現有的 ChromaDB 集合中新增文件。

    :param path: ChromaDB 的資料庫路徑 (string)
    :param collection_name: 要更新的集合名稱 (string)
    :param new_documents: 要新增的文件列表 (List of strings)
    """

    # Get the existing collection by name
    collection = client.get_or_create_collection(collection_name)

    # Add new documents to the collection
    for i, document in enumerate(new_documents):
        collection.add(
            ids=[f"new_doc_{i}"],  # New unique ID for each document
            documents=[document],  # New document content
        )

    print(
        f"Added {len(new_documents)} new documents to the collection '{collection_name}'."
    )


# 查詢相關段落
def get_relevant_passage(query: str,
                         db,
                         name: str,
                         n_results: int = 3) -> List[str]:
    """
    從指定的 ChromaDB 集合中查詢與給定問題相關的段落。

    :param query: 用戶的查詢語句 (string)
    :param db: 連接的 ChromaDB 資料庫對象
    :param name: 要查詢的集合名稱 (string)
    :param n_results: 返回的相關結果數量 (int, 默認為 3)
    :ret
    """
    collection = db.get_collection(name)
    results = collection.query(query_texts=[query], n_results=n_results)
    return results["documents"][0]


# 建構提示詞
def make_rag_prompt(query: str, relevant_passages: List[str]) -> str:
    context = "\n\n".join(relevant_passages)
    history = "\n".join(chat_history[-3:])  # 只保留最近 3 輪對話，避免 token 過多

    return f"""
    You are a thoughtful waiter. Use the following conversation history and menu information to assist the customer.

    Previous Conversation:
    {history}

    Menu:
    {context}

    Customer's Question:
    {query}

    IMPORTANT:
    - If the customer is making a decision, **confirm their choice instead of recommending new dishes**.
    - Only recommend a new dish if the customer explicitly asks for suggestions.
    - If the customer asks about "it," infer that "it" refers to the last mentioned dish.
    - Always answer based on the context and prior recommendations.
    - **If the customer explicitly says "NOT" or "another" when asking for a recommendation, exclude the previously mentioned dish from the response.**

    Provide a concise but friendly response.
    """


# Generate answer using Gemini Pro API
def generate_answer(prompt: str):

    load_dotenv()
    api_key = os.getenv('Geminiapikey')
    gemini_api_key = api_key
    if not gemini_api_key:
        raise ValueError(
            "Gemini API Key not provided. Please provide GEMINI_API_KEY as an environment variable"
        )
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')
    result = model.generate_content(prompt)
    return result.text


# 從 PDF 文件提取文本，分割文本為小塊，並更新 ChromaDB 集合。
def add_document_to_db_PDF(client, db_name, file_path):
    """
    :param db_path: ChromaDB 資料庫的路徑 (string)
    :param db_name: 要更新的 ChromaDB 集合名稱 (string)
    :param file_path: PDF 文件的路徑
    """
    pdf_text = extract_text_from_pdf_file_path(file_path)

    # Split text into chunks
    chunked_text = split_text(pdf_text)

    update_chroma_db(client, db_name, chunked_text)

    print(f"{db_name} is updated")


# 從 PDF 文件提取文本，分割文本為小塊，並更新 ChromaDB 集合。
def add_document_to_db_PICTURE(client, db_name, file_path):
    """
    :param db_path: ChromaDB 資料庫的路徑 (string)
    :param db_name: 要更新的 ChromaDB 集合名稱 (string)
    :param file_path: PDF 文件的路徑
    """
    pdf_text = ocr.ocr_api(file_path)

    # Split text into chunks
    chunked_text = split_text(pdf_text)

    update_chroma_db(client, db_name, chunked_text)

    print(f"{db_name} is updated")


# 基於 RAG (Retrieval-Augmented Generation) 流程生成回答。
def rag_response(query, client, db_name):
    """
    :param query: 用戶的查詢語句 (string)
    :param client: 連接的 ChromaDB 資料庫客戶端
    :param db_name: 查詢的集合名稱 (string)
    :return: 生成的回答或錯誤信息 (string)
    """
    # Process user query
    relevant_text = get_relevant_passage(query, client, db_name, n_results=3)

    # Generate and display answer
    if relevant_text:
        final_prompt = make_rag_prompt(query, "".join(relevant_text))
        answer = generate_answer(final_prompt)
        response = "Your Waiter:\n"+answer

        # 更新 chat_history，保持最近的 3 輪對話
        # 強制記錄推薦的菜品
        if "recommend" in answer.lower():
            chat_history.append(f"Waiter (previous recommendation): {answer}")
        
        chat_history.append(f"User: {query}")
        chat_history.append(f"Your Waiter: {answer}")
        chat_history[:] = chat_history[-6:]  # 確保 chat_history 不會過長
    else:
        response = "No relevant information found for the given query."

    return response


# 初始化 ChromaDB 資料庫，創建資料庫目錄並設置集合。
def initialize_database(db_folder: str,
                        db_name: str) -> chromadb.PersistentClient:
    """
    :param db_folder: 資料庫文件夾名稱 (string)
    :param db_name: 資料庫集合名稱 (string)
    :return: 已初始化的 ChromaDB 客戶端 (chromadb.PersistentClient)
    """
    # 獲取當前工作目錄，構建完整的資料庫路徑
    db_path = os.path.join(os.getcwd(), db_folder)

    # 如果資料庫目錄不存在，則創建該目錄
    if not os.path.exists(db_folder):
        os.makedirs(db_folder)

    # 創建一個 PersistentClient 連接到指定的資料庫路徑
    client = chromadb.PersistentClient(path=db_path)

    # 在資料庫中創建或獲取指定名稱的集合
    client.get_or_create_collection(db_name)

    # 打印提示信息，確認集合已創建或存在
    print(f"Collection '{db_name}' is initialized in {db_folder}.")

    # 返回已初始化的客戶端對象
    return client


# 定義用戶輸入的交互邏輯
def respond(input_text, history):
    """
    處理用戶輸入，生成回應並更新聊天歷史。
    Args:
        input_text (str): 用戶的輸入訊息。
        history (list): 聊天歷史記錄。
    Returns:
        tuple: 清空的輸入框和更新後的聊天歷史。
    """
    # 確保聊天歷史初始化為空列表
    if history is None:
        history = []

    # 使用 RAG 模型生成回應
    bot_response = rag_response(input_text, client, db_name)

    # 將用戶輸入和機器人回應追加到歷史記錄
    history.append([input_text, bot_response])  # 每次對話為 [用戶訊息, 機器人回應]

    return "", history  # 返回清空的輸入框和新的聊天歷史


def get_file_type(file_path):
    kind = filetype.guess(file_path)
    if kind is None:
        return "unknown"

    if kind.mime.startswith("image"):
        return "image"
    elif kind.mime == "application/pdf":
        return "pdf"
    return "unknown"


app = Flask(__name__)

#允許跨域請求
CORS(app)

# 初始化聊天歷史
chat_history = []  # 用於存儲用戶和機器人之間的所有對話
client = None
db_name = None


@app.route('/respond', methods=['POST'])
def respond_api():
    data = request.json
    message = data.get('user_message')
    # 初始化 history 為空列表
    history = []

    # 呼叫 respond 函數，並將 message 和 history 作為參數
    _, updated_history = respond(message, history)
    bot_response = updated_history[-1][1] if updated_history else "無回應"

    return jsonify({"bot_message": bot_response})


@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']

    # Define the path where you want to save the file locally
    file_path = os.path.join("project_rest_recommand", file.filename)

    # Save the file locally
    file.save(file_path)

    # 檢查檔案類型
    file_type = get_file_type(file_path)

    if file_type == "image":
        answer = "成功上傳圖片"
        add_document_to_db_PICTURE(client, db_name, file_path)

    elif file_type == "pdf":
        answer = "成功上傳PDF"
        add_document_to_db_PDF(client, db_name, file_path)
    else:
        answer = "不支援這類型的檔案"

    return jsonify(answer)


def main():
    # 主程式邏輯
    global client, db_name
    db_folder = "project_rest_recommand/chromaDB"
    db_name = "rag_experiment"

    client = initialize_database(db_folder, db_name)
    app.run(host="0.0.0.0", port=5000, debug=True)


# 標註進入點
if __name__ == "__main__":
    main()
