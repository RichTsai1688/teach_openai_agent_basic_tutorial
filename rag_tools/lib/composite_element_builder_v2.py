"""
composite_element_builder_v2.py

CompositeElementBuilder 的增強版本，整合了 build_text_embeddings_json_multi.py 的功能。
支援更豐富的圖片處理、表格處理和查詢導向語句生成。
同時支援 OpenAI 和 Ollama 作為 LLM 提供者。
"""

from __future__ import annotations

import argparse
import json
import uuid
import time
import re
import base64
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# 移除不再需要的 SentenceTransformer 導入
# from sentence_transformers import SentenceTransformer

# OpenAI 相關
try:
    from openai import OpenAI, AzureOpenAI
except ImportError:
    print("Warning: OpenAI package not installed. Use pip install openai")

from project_config import (
    load_project_env,
    resolve_azure_config,
    resolve_embedding_config,
    resolve_ollama_config,
    resolve_openai_config,
    resolve_provider,
)

LLM_IMAGE_PROMPT = """
You are a highly knowledgeable image classification assistant specializing in industrial mechanical components.
Your job is to analyze a single image (provided as a Base64‐encoded string) in the context of its web page,
and return exactly one concise English label that best describes what the image depicts.

Requirements:
- Respond with only the label, no additional commentary or punctuation.
- Use Title-Case (e.g. "Horizontal Motor Gear Reducer").
- Do not include words like "Photo of" or "Image of"; just the component name.
- If the image shows a type of gear reducer, mention its orientation or mounting style
  (e.g. Horizontal, Vertical, Direct-Drive, Dual-Shaft).
- If uncertain between two, choose the more specific label.

Now, based on the following context and image, provide only the best single label.

PAGE CONTEXT:
{page_context}

IMAGE DATA (base64, truncated):
{image_b64_truncated}

Label:"""

LLM_TABLE_PROMPT = """
You are a data extraction expert specializing in web tables.
Given the following HTML table, your task is to convert it to a structured JSON array with these strict requirements:
1. If the header row spans multiple layers (multi-level columns), flatten them into one header row by joining header texts with a double underscore '__'. For example: 'Main__Sub'.
2. Use the (flattened) first row as the header. Use exact cell text as keys.
3. Each subsequent row must be parsed as one JSON object, with keys from the header row.
4. If a row has missing cells (colspan/rowspan), leave missing values as empty strings ("").
5. Preserve all cell text as-is, do not interpret or abbreviate values.
6. Output ONLY a valid JSON array (do not include explanations, comments, markdown, or other text).
7. Trim whitespace from all cell values.
8. If the table has merged cells (colspan/rowspan), flatten so that each JSON object still contains all header keys, using empty strings for missing cells.

Here is the HTML table:
{table_html}
"""


class CompositeElementBuilder:
    """
    Builds JSON of CompositeElements by crawling web pages, extracting text, tables, and images,
    generating embeddings, and classifying content via LLMs.

    Enhanced version with full table parsing, image downloading and classification,
    and query-oriented sentence generation.
    """

    def __init__(
        self,
        start_url: str,
        out_path: Path,
        max_pages: int,
        llm_provider: str = "openai",
        openai_api_key: str = None,
        openai_model: str = None,
        ollama_url: str = "",
        ollama_model: str = "",
        azure_api_key: str = None,
        azure_endpoint: str = None,
        azure_deployment: str = None,
        azure_embedding_deployment: str = None,
        debug_mode: bool = False,
    ):
        """
        Initialize builder with crawling and LLM parameters.

        Args:
            start_url: URL to begin crawling.
            out_path: Path to save JSON output.
            max_pages: Maximum pages to process.
            embedding_model: SentenceTransformer model name for embeddings.
            llm_provider: LLM service provider ('openai', 'ollama', or 'azure').
            openai_api_key: API key for OpenAI.
            openai_model: Model name for OpenAI.
            ollama_url: Ollama server URL (if llm_provider is 'ollama').
            ollama_model: Ollama model name (if llm_provider is 'ollama').
            azure_api_key: API key for Azure OpenAI (if llm_provider is 'azure').
            azure_endpoint: Endpoint URL for Azure OpenAI (if llm_provider is 'azure').
            azure_deployment: Deployment name for Azure OpenAI (if llm_provider is 'azure').
            azure_embedding_deployment: Embedding deployment name for Azure OpenAI.
            debug_mode: Whether to print detailed debug information.
        """
        self.start_url = start_url
        self.out_path = out_path
        self.max_pages = max_pages
        load_project_env()
        self.llm_provider = resolve_provider(llm_provider)
        self.debug_mode = debug_mode
        self.last_embedding_error: str | None = None
        self.embedding_model, self.embedding_dimension = resolve_embedding_config(
            self.llm_provider,
            azure_deployment=azure_deployment,
            azure_embedding_deployment=azure_embedding_deployment,
        )

        # 初始化 LLM 客戶端
        if self.llm_provider == "azure":
            azure_api_key, azure_endpoint, azure_deployment = resolve_azure_config(
                azure_api_key,
                azure_endpoint,
                azure_deployment,
            )
            if not all([azure_api_key, azure_endpoint, azure_deployment]):
                raise ValueError(
                    "Azure OpenAI 需要 AZURE_OPENAI_API_KEY、AZURE_OPENAI_ENDPOINT 與 AZURE_OPENAI_DEPLOYMENT。"
                )
            self.client = AzureOpenAI(
                api_key=azure_api_key,
                azure_endpoint=azure_endpoint,
                api_version="2024-08-01-preview",
            )
            self.deployment = azure_deployment
        elif self.llm_provider == "openai":
            openai_api_key, openai_model = resolve_openai_config(
                openai_api_key,
                openai_model,
            )
            if not openai_api_key:
                raise ValueError(
                    "OpenAI provider 需要 OPENAI_API_KEY（可放在 .env 或 CLI）。"
                )
            if not openai_model:
                raise ValueError(
                    "OpenAI provider 需要 OPENAI_MODEL（可放在 .env 或 CLI）。"
                )
            self.client = OpenAI(api_key=openai_api_key)
            self.deployment = openai_model
        elif self.llm_provider == "ollama":
            ollama_url, ollama_model = resolve_ollama_config(ollama_url, ollama_model)
            if not ollama_url or not ollama_model:
                raise ValueError(
                    "Ollama provider 需要 OLLAMA_URL 與 OLLAMA_MODEL（可放在 .env 或 CLI）。"
                )
            self.client = OpenAI(api_key="ollama", base_url=ollama_url)
            self.deployment = ollama_model
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

        if not self.embedding_model:
            raise ValueError(
                "找不到 embedding model 設定，請檢查 docs/embedder.json 或 .env。"
            )

        # 初始化爬蟲資料結構
        self.records = []
        self.visited = set()
        self.queue = [start_url]

        print(f"Initialized CompositeElementBuilder v2 with provider: {llm_provider}")

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding via OpenAI-compatible embeddings API."""
        if not text or len(text.strip()) == 0:
            return []

        try:
            # input must be list
            resp = self.client.embeddings.create(
                model=self.embedding_model, input=[text]
            )
            # return first embedding vector
            self.last_embedding_error = None
            return (
                resp.data[0].embedding
                if hasattr(resp.data[0], "embedding")
                else resp["data"][0]["embedding"]
            )
        except Exception as e:
            self.last_embedding_error = str(e)
            self.log_debug(f"Embedding error: {e}")
            return []

    def llm_table_to_json(
        self, table_html: str, max_retries: int = 3
    ) -> list[dict] | None:
        """Convert HTML table to JSON via LLM."""
        for attempt in range(max_retries):
            try:
                prompt = LLM_TABLE_PROMPT.format(table_html=table_html)
                resp = self.client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a strict and reliable data extraction agent.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0,
                    max_tokens=2048,
                )
                content = resp.choices[0].message.content.strip()
                match = re.search(r"(\[.*\])", content, re.DOTALL)
                if match:
                    try:
                        js = json.loads(match.group(1))
                        if (
                            isinstance(js, list)
                            and all(isinstance(x, dict) for x in js)
                            and js
                        ):
                            self.log_debug(f"Table parsed successfully, rows={len(js)}")
                            return js
                    except Exception as e:
                        self.log_debug(f"JSON decode error (attempt {attempt+1}): {e}")
                else:
                    self.log_debug(
                        f"LLM did not return valid JSON (attempt {attempt+1})"
                    )
                time.sleep(1)
            except Exception as e:
                self.log_debug(f"Table parsing error (attempt {attempt+1}): {e}")
                time.sleep(1)
        self.log_debug("Table parsing failed after multiple attempts")
        return None

    def extract_tables_and_main_content(self, html: str, base_url: str) -> dict:
        """Extract tables, text blocks, and images."""
        soup = BeautifulSoup(html, "lxml")
        tables, blocks, images = [], [], []

        # 移除導航、頁尾和側邊欄
        for nav in soup(["nav", "footer", "aside"]):
            nav.decompose()

        # 表格抽取
        for i, tbl in enumerate(soup.find_all("table")):
            tbl_html = str(tbl)
            # 確保表格標籤完整
            if not tbl_html.strip().startswith("<table"):
                tbl_html = "<table>" + tbl_html
            if not tbl_html.strip().endswith("</table>"):
                tbl_html = tbl_html + "</table>"
            if "<td" in tbl_html or "<th" in tbl_html:
                tables.append(tbl_html)
                self.log_debug(
                    f"Table #{i+1}: length={len(tbl_html)} | {tbl_html[:60].replace(chr(10),' ')}..."
                )

        # 文本區塊抽取
        for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "ul", "ol"]):
            txt = el.get_text(strip=True)
            if (
                txt
                and len(txt) > 2
                and not re.match(r"^\s*Copyright|^©|\d{4} All Rights", txt, re.I)
            ):
                blocks.append(txt)
                self.log_debug(
                    f"Content Block: {txt[:30]}{'...' if len(txt)>30 else ''}"
                )

        # 圖片抽取
        for i, img in enumerate(soup.find_all("img")):
            src = img.get("src", "")
            if src and not src.lower().endswith((".svg", ".gif")):
                url = urljoin(base_url, src)
                alt = img.get("alt", "")
                images.append({"url": url, "alt": alt})
                self.log_debug(
                    f"Image #{i+1}: url={url} | alt={alt[:30]}{'...' if len(alt)>30 else ''}"
                )

        self.log_debug(
            f"Total: {len(tables)} tables, {len(blocks)} text blocks, {len(images)} images"
        )
        return {"tables": tables, "content_blocks": blocks, "images": images}

    def process_text_blocks(self, content_blocks: list, url: str) -> dict:
        """Process text blocks into a CompositeElement."""
        fulltext = "\n".join(content_blocks).strip()
        if not fulltext:
            return None

        text_id = str(uuid.uuid4())
        emb = self.embed_text(fulltext)

        return {
            "type": "CompositeElement",
            "element_id": text_id,
            "text": fulltext,
            "metadata": {
                "filename": text_id,
                "source_url": url,
                "filetype": "text/html",
                "embedding": emb,
                "content_blocks": content_blocks,
            },
        }

    def process_table(self, table_html: str, url: str) -> list[dict]:
        """Process a table into multiple CompositeElements."""
        table_records = []

        # 使用 LLM 解析表格
        table_json = self.llm_table_to_json(table_html)
        if not table_json:
            return []

        # 1. 創建表格整體的 CompositeElement
        table_sentences = []
        for row in table_json:
            sent = ", ".join([f"{k}: {v}" for k, v in row.items() if v])
            if sent:
                table_sentences.append(sent)

        if table_sentences:
            table_id = str(uuid.uuid4())
            emb_table = self.embed_text("\n".join(table_sentences))
            table_records.append(
                {
                    "type": "CompositeElement",
                    "element_id": table_id,
                    "text": "\n".join(table_sentences),
                    "metadata": {
                        "filename": table_id,
                        "source_url": url,
                        "filetype": "table/html",
                        "embedding": emb_table,
                        "table_html": table_html,
                        "table_json": table_json,
                        "table_sentences": table_sentences,
                    },
                }
            )

        # 2. 創建表格行的查詢導向語句的 CompositeElement
        if table_json:
            header = list(table_json[0].keys())
            for row in table_json:
                model_val = (
                    row.get("型號") or row.get("Model") or row.get(header[0], "")
                )
                for k, v in row.items():
                    if v and v not in header:
                        # 生成查詢導向語句
                        q = f"型號為{model_val}的{k}是什麼？答案：{v}"
                        row_id = str(uuid.uuid4())
                        emb_row = self.embed_text(q)
                        table_records.append(
                            {
                                "type": "CompositeElement",
                                "element_id": row_id,
                                "text": q,
                                "metadata": {
                                    "filename": row_id,
                                    "source_url": url,
                                    "filetype": "table_row_query",
                                    "embedding": emb_row,
                                    "table_html": table_html,
                                    "row_data": row,
                                },
                            }
                        )

        return table_records

    def process_image(self, img_data: dict, context: str, url: str) -> dict:
        """Process an image into a CompositeElement."""
        img_url = img_data.get("url", "")
        if not img_url:
            return None

        # 下載圖片並轉換為 base64
        try:
            r = requests.get(img_url, timeout=10)
            r.raise_for_status()
            b64 = base64.b64encode(r.content).decode()
            mime = r.headers.get("Content-Type", "")
            self.log_debug(f"Image downloaded and base64 encoded (size={len(b64)})")
        except Exception as e:
            self.log_debug(f"Image download failed: {e}")
            b64, mime = None, None

        # 使用 LLM 對圖片進行分類
        label = self.classify_image(b64 or "", context) if b64 else str(uuid.uuid4())
        img_id = str(uuid.uuid4())

        return {
            "type": "CompositeElement",
            "element_id": img_id,
            "text": label,  # 使用標籤作為文本
            "metadata": {
                "filename": label,
                "source_url": url,
                "filetype": "image",
                "image_base64": b64,
                "image_mime_type": mime,
                "orig_img": img_data,
                "label": label,
            },
        }

    def log_debug(self, msg: str) -> None:
        """Print debug message if debug_mode is enabled."""
        if self.debug_mode:
            print(f"[DEBUG] {msg}")

    def fetch_html(self, url: str, timeout: int = 15) -> str:
        """Fetch page HTML."""
        self.log_debug(f"Fetching HTML from {url}")
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text

    def extract_links(self, html: str, base_url: str) -> set[str]:
        """Extract same-domain links."""
        soup = BeautifulSoup(html, "lxml")
        domain = urlparse(base_url).netloc
        urls = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"].split("#")[0])
            p = urlparse(href)
            if p.scheme in ("http", "https") and p.netloc == domain:
                urls.add(href)
        self.log_debug(f"Extracted {len(urls)} links from {base_url}")
        return urls

    def classify_image(self, b64: str, context: str) -> str:
        """Classify image via LLM."""
        if not b64:
            return "Unknown Image"

        truncated = (b64 or "")[:200] + "..."
        ctx = (context[:500] + "...") if len(context) > 500 else context

        # 根據不同 LLM 提供者處理圖片分類
        if self.llm_provider == "ollama":
            # Ollama 支援多模態
            # user_prompt_text = f"PAGE CONTEXT: {ctx}\nLABEL:"
            prompt = LLM_IMAGE_PROMPT.format(
                page_context=ctx, image_b64_truncated=truncated
            )
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": f"data:image/png;base64,{b64}",
                        },
                    ],
                }
            ]
        else:
            # OpenAI 和 Azure OpenAI
            prompt = LLM_IMAGE_PROMPT.format(
                page_context=ctx, image_b64_truncated=truncated
            )
            messages = [
                {
                    "role": "system",
                    "content": LLM_IMAGE_PROMPT.split("PAGE CONTEXT:")[0],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                },
            ]

        try:
            resp = self.client.chat.completions.create(
                model=self.deployment, messages=messages, temperature=0, max_tokens=16
            )
            # 提取內容
            content = resp.choices[0].message.content.strip()
            self.log_debug(f"Image classified as: {content}")
            return content
        except Exception as e:
            self.log_debug(f"Image classification error: {e}")
            return "Classification Error"

    def build(self) -> None:
        """Run crawling, extraction, embedding, and save JSON."""
        # 初始化進度條
        progress = tqdm(total=self.max_pages, desc="Processing pages", unit="page")

        while self.queue and len(self.visited) < self.max_pages:
            url = self.queue.pop(0)
            if url in self.visited:
                continue

            self.log_debug(f"\nProcessing: {url}")

            try:
                # 獲取和處理頁面
                html = self.fetch_html(url)
                self.visited.add(url)

                # 對於起始 URL，提取並加入所有連結到佇列
                if url == self.start_url:
                    for link in self.extract_links(html, url):
                        if link not in self.visited and link not in self.queue:
                            self.queue.append(link)

                # 提取頁面內容
                data = self.extract_tables_and_main_content(html, url)

                # 1. 處理文本區塊
                text_record = self.process_text_blocks(data["content_blocks"], url)
                if text_record:
                    self.records.append(text_record)
                    # 使用文本作為圖片分類的上下文
                    context_for_images = text_record.get("text", "")
                else:
                    context_for_images = ""

                # 2. 處理表格
                for table_html in data["tables"]:
                    table_records = self.process_table(table_html, url)
                    self.records.extend(table_records)

                # 3. 處理圖片
                for img_data in data["images"]:
                    img_record = self.process_image(img_data, context_for_images, url)
                    if img_record:
                        self.records.append(img_record)

                # 更新進度條
                progress.update(1)

            except Exception as e:
                self.log_debug(f"Error processing {url}: {e}")

        # 關閉進度條
        progress.close()

        # 保存結果
        self.log_debug(f"Saved {len(self.records)} CompositeElements")
        embedded_records = sum(
            1
            for record in self.records
            if record.get("metadata", {}).get("embedding")
        )
        if self.records and embedded_records == 0:
            detail = (
                f" 最後的 embedding 錯誤: {self.last_embedding_error}"
                if self.last_embedding_error
                else ""
            )
            raise RuntimeError(
                "沒有任何內容成功產生 embedding，請確認 embedding service / model 可用。"
                + detail
            )
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.out_path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)
        print(f"✅ Completed: {len(self.records)} elements saved to {self.out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enhanced CompositeElementBuilder CLI")
    parser.add_argument("url", help="Start URL")
    parser.add_argument(
        "-o", "--out", type=Path, default=Path("output/composite_v2.json")
    )
    parser.add_argument("--max_pages", type=int, default=5)
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    # LLM 提供者選擇
    parser.add_argument(
        "--llm_provider",
        choices=["openai", "ollama", "azure"],
        default=None,
        help="LLM provider",
    )

    # OpenAI 參數
    parser.add_argument("--openai_api_key", help="OpenAI API key")
    parser.add_argument("--openai_model", help="OpenAI model name")

    # Ollama 參數
    parser.add_argument("--ollama_url", help="Ollama server URL")
    parser.add_argument("--ollama_model", help="Ollama model name")

    # Azure OpenAI 參數
    parser.add_argument("--azure_api_key", help="Azure OpenAI API key")
    parser.add_argument("--azure_endpoint", help="Azure OpenAI endpoint")
    parser.add_argument("--azure_deployment", help="Azure OpenAI deployment name")
    parser.add_argument(
        "--azure_embedding_deployment", help="Azure OpenAI embedding deployment name"
    )

    args = parser.parse_args()

    builder = CompositeElementBuilder(
        start_url=args.url,
        out_path=args.out,
        max_pages=args.max_pages,
        llm_provider=args.llm_provider,
        openai_api_key=args.openai_api_key,
        openai_model=args.openai_model,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
        azure_api_key=args.azure_api_key,
        azure_endpoint=args.azure_endpoint,
        azure_deployment=args.azure_deployment,
        azure_embedding_deployment=args.azure_embedding_deployment,
        debug_mode=args.debug,
    )
    builder.build()
