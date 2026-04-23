#!/usr/bin/env python3
import argparse
import json
import sys
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlparse
import base64
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
import re
import time

sys.path.append(str(Path(__file__).parent.parent / "lib"))

from project_config import load_project_env, resolve_azure_config

LLM_IMAGE_PROMPT = """\
You are a highly knowledgeable image classification assistant specializing in industrial mechanical components.
Your job is to analyze a single image (provided as a Base64‐encoded string) in the context of its web page,
and return exactly one concise English label that best describes what the image depicts.

Requirements:
- Respond with only the label, no additional commentary or punctuation.
- Use Title-Case (e.g. “Horizontal Motor Gear Reducer”).
- Do not include words like “Photo of” or “Image of”; just the component name.
- If the image shows a type of gear reducer, mention its orientation or mounting style
  (e.g. Horizontal, Vertical, Direct-Drive, Dual-Shaft).
- If uncertain between two, choose the more specific label.

Now, based on the following context and image, provide only the best single label.

PAGE CONTEXT:
{page_context}

IMAGE DATA (base64, truncated):
{image_b64_truncated}

Label:"""

LLM_TABLE_PROMPT = """\
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


def fetch_html(url: str, timeout: int = 15) -> str:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def extract_links(html: str, base_url: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    domain = urlparse(base_url).netloc
    urls = set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"].split("#")[0])
        p = urlparse(href)
        if p.scheme in ("http", "https") and p.netloc == domain:
            urls.add(href)
    return urls


def classify_image_with_llm(
    b64: str, page_context: str, client: AzureOpenAI, deployment: str
) -> str:
    truncated = (b64 or "")[:200] + "..."
    ctx = (page_context[:500] + "...") if len(page_context) > 500 else page_context
    prompt = LLM_IMAGE_PROMPT.format(page_context=ctx, image_b64_truncated=truncated)
    resp = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": LLM_IMAGE_PROMPT.split("PAGE CONTEXT:")[0]},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=8,
    )
    return resp.choices[0].message.content.strip()


def embed_text(text: str, model_name: str) -> list[float]:
    model = SentenceTransformer(model_name)
    emb = model.encode([text], normalize_embeddings=True)
    return emb[0].tolist()


def llm_table_to_json(client, deployment, table_html, max_retries=3):
    for attempt in range(max_retries):
        prompt = LLM_TABLE_PROMPT.format(table_html=table_html)
        resp = client.chat.completions.create(
            model=deployment,
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
                if isinstance(js, list) and all(isinstance(x, dict) for x in js) and js:
                    return js
            except Exception as e:
                print(f"Attempt {attempt+1}: JSON decode error: {e}")
        else:
            print(f"Attempt {attempt+1}: LLM did not return valid JSON. Retrying.")
        time.sleep(1)
    print("⚠️ LLM表格結構化失敗，多次重試後無法得到有效JSON，已跳過。")
    return None


def extract_tables_and_main_content(html, base_url):
    soup = BeautifulSoup(html, "lxml")
    tables = []
    # 先抓主要區塊（去除nav/footer/aside）
    for nav in soup(["nav", "footer", "aside"]):
        nav.decompose()
    # 抓所有表格
    for i, tbl in enumerate(soup.find_all("table")):
        tbl_html = str(tbl)
        if not tbl_html.strip().startswith("<table"):
            tbl_html = "<table>" + tbl_html
        if not tbl_html.strip().endswith("</table>"):
            tbl_html = tbl_html + "</table>"
        if "<td" in tbl_html or "<th" in tbl_html:
            tables.append(tbl_html)
            print(
                f"[DEBUG][TABLE] Extracted table #{i+1}: length={len(tbl_html)} | {tbl_html[:60].replace(chr(10),' ')}..."
            )
    # 主要內容段落、標題、列表
    blocks = []
    for el in soup.find_all(["h1", "h2", "h3", "h4", "h5", "p", "ul", "ol"]):
        txt = el.get_text(strip=True)
        if (
            txt
            and len(txt) > 2
            and not re.match(r"^\s*Copyright|^©|\d{4} All Rights", txt, re.I)
        ):
            blocks.append(txt)
            print(
                f"[DEBUG][BLOCK] Content Block: {txt[:30]}{'...' if len(txt)>30 else ''}"
            )
    # 主要圖片
    images = []
    for i, img in enumerate(soup.find_all("img")):
        src = img.get("src", "")
        if src and not src.lower().endswith((".svg", ".gif")):
            url = urljoin(base_url, src)
            alt = img.get("alt", "")
            images.append({"url": url, "alt": alt})
            print(
                f"[DEBUG][IMAGE] Image #{i+1}: url={url} | alt={alt[:30]}{'...' if len(alt)>30 else ''}"
            )
    print(
        f"[DEBUG][SUMMARY] Total: {len(tables)} tables, {len(blocks)} text blocks, {len(images)} images."
    )
    return {"tables": tables, "content_blocks": blocks, "images": images}


def build_json(
    start_url: str,
    out_path: Path,
    model_name: str,
    max_pages: int,
    azure_api_key: str,
    azure_endpoint: str,
    azure_deployment: str,
):
    client = AzureOpenAI(
        api_key=azure_api_key,
        azure_endpoint=azure_endpoint,
        api_version="2024-08-01-preview",
    )
    visited, queue, records = set(), [start_url], []

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        print(f"\n[INFO] Processing: {url}")
        html = fetch_html(url)
        visited.add(url)
        if url == start_url:
            for link in extract_links(html, url):
                if link not in visited and link not in queue:
                    queue.append(link)

        extract = extract_tables_and_main_content(html, url)
        # ---- 1. 一般內容區塊 ----
        fulltext = "\n".join(extract["content_blocks"]).strip()
        text_id = str(uuid.uuid4())
        emb = embed_text(fulltext, model_name)
        records.append(
            {
                "type": "CompositeElement",
                "element_id": text_id,
                "text": fulltext,
                "metadata": {
                    "filename": text_id,
                    "source_url": url,
                    "filetype": "text/html",
                    "embedding": emb,
                    "content_blocks": extract["content_blocks"],
                },
            }
        )

        # ---- 2. 結構化表格 ----
        for i, table_html in enumerate(extract["tables"]):
            print(f"[DEBUG][TABLE->LLM] Table #{i+1} sending to LLM...")
            table_json = llm_table_to_json(
                client, azure_deployment, table_html, max_retries=3
            )
            if table_json:
                print(
                    f"[DEBUG][TABLE->LLM] Table #{i+1} parsed successfully, rows={len(table_json)}"
                )
            else:
                print(f"[DEBUG][TABLE->LLM] Table #{i+1} LLM parse FAILED")
                continue

            # 產生原本全部row組合句
            table_sentences = []
            for row in table_json:
                sent = ", ".join([f"{k}: {v}" for k, v in row.items() if v])
                if sent:
                    table_sentences.append(sent)
            table_id = str(uuid.uuid4())
            emb_table = (
                embed_text("\n".join(table_sentences), model_name)
                if table_sentences
                else []
            )
            records.append(
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

            # 產生查詢導向語句的 CompositeElement（每個row都一組）
            header = list(table_json[0].keys())
            for row in table_json:
                model_val = (
                    row.get("型號") or row.get("Model") or row.get(header[0], "")
                )
                for k, v in row.items():
                    if v and v not in header:
                        # 中文欄位名與內容自動產查詢導向語句
                        q = f"型號為{model_val}的{k}是什麼？答案：{v}"
                        row_id = str(uuid.uuid4())
                        emb_row = embed_text(q, model_name)
                        records.append(
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

        # ---- 3. 圖片（下載/分類/base64） ----
        for i, img in enumerate(extract["images"]):
            full_url = img.get("url", "")
            try:
                r = requests.get(full_url, timeout=10)
                r.raise_for_status()
                b64 = base64.b64encode(r.content).decode()
                mime = r.headers.get("Content-Type", "")
                print(
                    f"[DEBUG][IMAGE] Image #{i+1} download and base64 OK (size={len(b64)})"
                )
            except Exception as e:
                b64, mime = None, None
                print(f"[DEBUG][IMAGE] Image #{i+1} download failed: {e}")
            label = (
                classify_image_with_llm(b64 or "", fulltext, client, azure_deployment)
                if b64
                else str(uuid.uuid4())
            )
            img_id = str(uuid.uuid4())
            records.append(
                {
                    "type": "CompositeElement",
                    "element_id": img_id,
                    "text": "",
                    "metadata": {
                        "filename": label,
                        "source_url": url,
                        "filetype": "image",
                        "image_base64": b64,
                        "image_mime_type": mime,
                        "orig_img": img,
                        "label": label,
                    },
                }
            )
    print(
        f"\n[DEBUG][SUMMARY] Saved {len(records)} CompositeElements for all processed pages."
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Completed: {len(records)} elements saved to {out_path}")


if __name__ == "__main__":
    load_project_env()
    p = argparse.ArgumentParser(description="LLM-centric CompositeElement JSON builder")
    p.add_argument("url", help="Start page URL")
    p.add_argument("-o", "--out", type=Path, default="output/composite.json")
    p.add_argument("-m", "--model", default="paraphrase-multilingual-MiniLM-L12-v2")
    p.add_argument("--max_pages", type=int, default=5)
    p.add_argument(
        "--azure_api_key",
        help="Azure OpenAI API key (or set AZURE_OPENAI_API_KEY in .env)",
    )
    p.add_argument(
        "--azure_endpoint",
        help="Azure OpenAI endpoint (or set AZURE_OPENAI_ENDPOINT in .env)",
    )
    p.add_argument(
        "--azure_deployment",
        help="Azure OpenAI deployment (or set AZURE_OPENAI_DEPLOYMENT in .env)",
    )
    args = p.parse_args()
    azure_api_key, azure_endpoint, azure_deployment = resolve_azure_config(
        args.azure_api_key,
        args.azure_endpoint,
        args.azure_deployment,
    )

    if not all([azure_api_key, azure_endpoint, azure_deployment]):
        p.error(
            "缺少 Azure OpenAI 設定。請在 .env 或 CLI 提供 API key、endpoint、deployment。"
        )

    build_json(
        args.url,
        args.out,
        args.model,
        args.max_pages,
        azure_api_key,
        azure_endpoint,
        azure_deployment,
    )
