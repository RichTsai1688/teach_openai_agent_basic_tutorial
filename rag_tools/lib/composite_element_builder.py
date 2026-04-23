"""
composite_element_builder.py

Defines CompositeElementBuilder for building CompositeElements JSON via web scraping,
LLM-enhanced table and image processing, embedding generation, and FAISS indexing.
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
from openai import AzureOpenAI
from tqdm import tqdm

from project_config import (
    load_project_env,
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

LLM_TABLE_PROMPT = """
You are a data extraction expert specializing in web tables.
Given the following HTML table, your task is to convert it to a structured JSON array with these strict requirements:
1. If the header row spans multiple layers (multi-level columns), flatten them into one header row by joining header texts with a double __.
2. Use the (flattened) first row as the header. Use exact cell text as keys.
3. Each subsequent row must be parsed as one JSON object, with keys from the header row.
4. If a row has missing cells (colspan/rowspan), leave missing values as empty strings ("").
5. Preserve all cell text as-is, do not interpret or abbreviate values.
6. Output ONLY a valid JSON array (no explanations or markdown).
7. Trim whitespace from all cell values.
8. Flatten merged cells using empty strings for missing values.

Here is the HTML table:
{table_html}
"""


class CompositeElementBuilder:
    """
    Builds JSON of CompositeElements by crawling web pages, extracting text, tables, and images,
    generating embeddings, and classifying content via LLMs.
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
    ):
        """
        Initialize builder with crawling and LLM parameters.

        Args:
            start_url: URL to begin crawling.
            out_path: Path to save JSON output.
            max_pages: Maximum pages to process.
            llm_provider: LLM service provider, either 'openai' or 'ollama'.
            openai_api_key: API key for OpenAI.
            openai_model: Model name for OpenAI.
            ollama_url: Ollama server URL (if llm_provider is 'ollama').
            ollama_model: Ollama model name (if llm_provider is 'ollama').
        """
        self.start_url = start_url
        self.out_path = out_path
        self.max_pages = max_pages
        # 選擇 LLM 服務供應商: openai 或 ollama
        load_project_env()
        self.llm_provider = resolve_provider(llm_provider)
        # Initialize unified OpenAI client (supports both OpenAI and Ollama endpoints)
        from openai import OpenAI

        if self.llm_provider == "openai":
            openai_api_key, openai_model = resolve_openai_config(
                openai_api_key,
                openai_model,
            )
            if not openai_api_key:
                raise ValueError("缺少 OPENAI_API_KEY，請在 .env 或 CLI 提供。")
            self.client = OpenAI(api_key=openai_api_key)
        else:
            # Ollama emulates OpenAI API; api_key required but ignored
            ollama_url, ollama_model = resolve_ollama_config(ollama_url, ollama_model)
            if not ollama_url:
                raise ValueError("缺少 OLLAMA_URL，請在 .env 或 CLI 提供。")
            self.client = OpenAI(api_key="ollama", base_url=ollama_url)
        self.deployment = (
            openai_model if self.llm_provider == "openai" else ollama_model
        )
        self.embedding_model, _ = resolve_embedding_config(self.llm_provider)
        self.records = []
        self.visited = set()
        self.queue = [start_url]

    def fetch_html(self, url: str, timeout: int = 15) -> str:
        """Fetch page HTML."""
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
            if urlparse(href).netloc == domain:
                urls.add(href)
        return urls

    def classify_image(self, b64: str, context: str) -> str:
        """Classify image via LLM."""
        truncated = (b64 or "")[:200] + "..."
        ctx = (context[:500] + "...") if len(context) > 500 else context
        prompt_text = LLM_IMAGE_PROMPT.format(
            page_context=ctx, image_b64_truncated=truncated
        )
        # 構建指令與圖像 payload
        system_prompt = LLM_IMAGE_PROMPT.split("PAGE CONTEXT:")[0]
        user_prompt_text = f"PAGE CONTEXT: {ctx}\nLABEL:"

        messages = [
            # {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt_text},
                    {"type": "image_url", "image_url": f"data:image/png;base64,{b64}"},
                ],
            }
        ]
        resp = self.client.chat.completions.create(
            model=self.deployment, messages=messages, temperature=0, max_tokens=8
        )
        # extract content
        choice = resp.choices[0]
        return (
            choice.message.content.strip()
            if hasattr(choice.message, "content")
            else choice["message"]["content"].strip()
        )

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding via OpenAI-compatible embeddings API."""
        # input must be list
        resp = self.client.embeddings.create(model=self.embedding_model, input=[text])
        # return first embedding vector
        return (
            resp.data[0].embedding
            if hasattr(resp.data[0], "embedding")
            else resp["data"][0]["embedding"]
        )

    def llm_table_to_json(
        self, table_html: str, max_retries: int = 3
    ) -> list[dict] | None:
        """Convert HTML table to JSON via LLM."""
        for _ in range(max_retries):
            prompt = LLM_TABLE_PROMPT.format(table_html=table_html)
            resp = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strict data extraction agent.",
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
                    if isinstance(js, list) and all(isinstance(x, dict) for x in js):
                        return js
                except:
                    pass
            time.sleep(1)
        return None

    def extract_tables_and_main_content(self, html: str, base_url: str) -> dict:
        """Extract tables, text blocks, and images."""
        soup = BeautifulSoup(html, "lxml")
        for nav in soup(["nav", "footer", "aside"]):
            nav.decompose()
        tables, blocks, images = [], [], []
        # Tables
        for tbl in soup.find_all("table"):
            tbl_html = str(tbl)
            if "<td" in tbl_html:
                tables.append(tbl_html)
        # Text blocks
        for el in soup.find_all(["h1", "h2", "p", "ul", "ol"]):
            txt = el.get_text(strip=True)
            if txt and not re.match(r"^©", txt):
                blocks.append(txt)
        # Images
        for img in soup.find_all("img"):
            src = img.get("src", "")
            if src and not src.lower().endswith((".svg", ".gif")):
                images.append(
                    {"url": urljoin(base_url, src), "alt": img.get("alt", "")}
                )
        return {"tables": tables, "content_blocks": blocks, "images": images}

    def build(self) -> None:
        """Run crawling, extraction, embedding, and save JSON."""
        # Initialize progress bar
        progress = tqdm(total=self.max_pages, desc="Processing pages", unit="page")
        while self.queue and len(self.visited) < self.max_pages:
            url = self.queue.pop(0)
            if url in self.visited:
                continue
            self.visited.add(url)
            html = self.fetch_html(url)
            if url == self.start_url:
                for link in self.extract_links(html, url):
                    if link not in self.visited:
                        self.queue.append(link)
            data = self.extract_tables_and_main_content(html, url)
            # Process text blocks
            fulltext = "\n".join(data["content_blocks"]).strip()
            text_id = str(uuid.uuid4())
            emb = self.embed_text(fulltext)
            self.records.append(
                {
                    "type": "CompositeElement",
                    "element_id": text_id,
                    "text": fulltext,
                    "metadata": {
                        "filename": text_id,
                        "source_url": url,
                        "filetype": "text/html",
                        "embedding": emb,
                    },
                }
            )
            # Update progress bar after processing a page
            progress.update(1)
        # Save
        # Close progress bar
        progress.close()
        self.out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.out_path, "w", encoding="utf-8") as f:
            json.dump(self.records, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CompositeElementBuilder CLI")
    parser.add_argument("url", help="Start URL")
    parser.add_argument("-o", "--out", type=Path, default=Path("output/composite.json"))
    parser.add_argument("--max_pages", type=int, default=5)
    parser.add_argument(
        "--llm_provider",
        choices=["openai", "ollama"],
        default="openai",
        help="LLM provider",
    )
    # OpenAI parameters
    parser.add_argument("--openai_api_key", required=False, help="OpenAI API key")
    parser.add_argument("--openai_model", required=False, help="OpenAI model name")
    # Ollama parameters
    parser.add_argument("--ollama_url", required=False, help="Ollama server URL")
    parser.add_argument("--ollama_model", required=False, help="Ollama model name")
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
    )
    builder.build()
