# RAG_teach_demo 入門指南

這份指南將幫助您快速開始使用 RAG_teach_demo 系統。

## 環境設置

1. 克隆儲存庫（如果尚未完成）：
   ```bash
   git clone <儲存庫URL>
   cd RAG_teach_demo
   ```

2. 建議建立虛擬環境並安裝執行依賴：
   ```bash
   python -m venv .venv
   ```

   macOS / Linux：
   ```bash
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

   Windows PowerShell：
   ```powershell
   .venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

3. 建立 `.env`：
   ```bash
   cp .env.example .env
   ```

4. 填好 `.env`。至少需要一組可用設定：
   - `OPENAI_API_KEY` + `OPENAI_MODEL`
   - 或 `OLLAMA_URL` + `OLLAMA_MODEL`
   - 或 `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` + `AZURE_OPENAI_DEPLOYMENT`
   - 如果走 Ollama，請先在新電腦執行 `ollama pull nomic-embed-text`，以及你要用的 chat model

5. 確保 `docs/embedder.json` 檔案配置正確，包含您要使用的嵌入模型設定。

## 快速開始

### 網頁抓取和處理

從抓取網頁並生成結構化 JSON 開始：

```bash
python scripts/composite_builder_cli.py https://example.com \
  --llm_provider ollama \
  --max_pages 5 \
  --debug
```

這將會：
- 抓取 example.com 網站上最多 5 個頁面
- 提取文本、表格和圖片
- 生成嵌入向量
- 將結果保存為 JSON 檔案（預設在 output 目錄）

### 查詢處理後的內容

一旦您有了生成的 JSON 檔案，您可以使用 RAG 系統進行查詢：

```bash
python scripts/rag_cli.py \
  --embeddings output/composite_v2.json \
  --query "您的問題" \
  --llm_provider ollama \
  --top_k 5
```

這將會：
- 載入您的 JSON 檔案
- 使用您的問題查詢索引
- 找到相關的上下文
- 使用 LLM 生成答案

## 進階使用

查看 `README.md` 文件以獲取更多詳細信息，包括：
- 完整的命令行選項
- API 文檔
- 自定義配置
- 效能調整技巧

## 常見問題排解

1. **錯誤：找不到模組**
   
   確保您已安裝所有依賴項，並且從項目根目錄運行命令。

2. **錯誤：找不到 embedder.json**

   確保 `docs/embedder.json` 文件存在並且可讀。

3. **錯誤：OpenAI API 錯誤**

   檢查 `.env` 內的 `OPENAI_API_KEY` / `OPENAI_MODEL` 和網路連線。

4. **錯誤：Ollama 連接失敗**

   確保 Ollama 服務正在運行，並且 `.env` 內的 `OLLAMA_URL` / `OLLAMA_MODEL` 正確。

5. **錯誤：No module named 'faiss'**

   請確認目前使用的是安裝過 `requirements.txt` 的虛擬環境。

6. **錯誤：model "nomic-embed-text" not found**

   代表 Ollama 的 embedding model 還沒準備好。請先執行 `ollama pull nomic-embed-text`。

7. **查詢結果不精確**

   嘗試調整 `top_k` 參數，或使用更精確的查詢關鍵詞。

## 轉移與分享

分享給別人或搬到新電腦時，建議只帶這些：
- 原始碼
- `requirements.txt`
- `.env.example`
- 必要的示範資料

不要把 `.env`、`.venv/`、`.myvenv/` 一起帶走。

## 獲取幫助

如果您遇到任何問題，請：
- 查看項目文檔
- 檢查項目 issues
- 在 issues 中提交新問題

祝您使用愉快！
