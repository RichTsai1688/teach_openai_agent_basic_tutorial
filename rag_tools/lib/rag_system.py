"""
rag_system.py

This module defines the RAGSystem class for Retrieval-Augmented Generation (RAG).
It integrates FAISS vector search with OpenAI or Ollama for answering queries based on ingested content.

Features:
- Text embedding generation via OpenAI-compatible API
- FAISS L2 index construction for similarity search
- OpenAI/Ollama integration for generating final answers
- Support for text and image (base64) in retrieved context
- Debug mode for troubleshooting
"""

import os
import uuid
import json
import base64
import requests  # 添加 requests 模組
import re  # 添加 re 模組
import time  # 添加 time 模組
import pickle  # 添加 pickle 模組用於序列化
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import faiss

# 不再需要 AutoTokenizer
# from transformers import AutoTokenizer

from project_config import (
    load_project_env,
    resolve_embedding_config,
    resolve_ollama_config,
    resolve_openai_config,
    resolve_provider,
)


class RAGSystem:
    """
    RAGSystem provides methods to ingest text entries, build a FAISS index, and
    perform retrieval-augmented generation queries using OpenAI or Ollama.

    Attributes:
        index: FAISS IndexFlatL2 for similarity search.
        id_to_text: Dict mapping vector IDs to text content.
        id_to_source: Dict mapping vector IDs to source identifiers.
        id_to_images: Dict mapping vector IDs to list of base64-encoded images.
        client: OpenAI-compatible client for embeddings and chat completions.
        deployment: Model name/deployment to use with the client.
        embedding_model: Name of the embedding model to use.
        debug_mode: Whether to print detailed debug information.
    """

    def __init__(
        self,
        model_path: str,
        embedding_dimension: Optional[int],
        llm_provider: str = "openai",
        openai_api_key: str = None,
        openai_model: str = None,
        ollama_url: str = None,
        ollama_model: str = None,
        debug_mode: bool = False,
        index_file_path: Optional[str] = None,
    ):
        """
        Initialize RAGSystem with embedding model and LLM configuration.

        Args:
            model_path: Path to model config (unused, kept for backward compatibility).
            embedding_dimension: Dimensionality of embedding vectors.
            llm_provider: Provider for LLM, either 'openai' or 'ollama'.
            openai_api_key: API key for OpenAI (if provider is 'openai').
            openai_model: Model name to use with OpenAI (if provider is 'openai').
            ollama_url: Base URL for Ollama server (if provider is 'ollama').
            ollama_model: Model name to use with Ollama (if provider is 'ollama').
            debug_mode: Whether to print detailed debug information.
            index_file_path: Optional path to a previously saved index file to load.
        """
        # 是否顯示除錯訊息
        self.debug_mode = debug_mode
        self.last_embedding_error: Optional[str] = None
        load_project_env()
        self.llm_provider = resolve_provider(llm_provider)
        self.embedding_model, self.embedding_dimension = resolve_embedding_config(
            self.llm_provider,
            embedding_dimension=embedding_dimension,
        )

        if not self.embedding_model:
            raise ValueError(
                "找不到 embedding model 設定，請檢查 docs/embedder.json 或 .env。"
            )

        if self.llm_provider == "openai":
            openai_api_key, openai_model = resolve_openai_config(
                openai_api_key,
                openai_model,
            )
            if not openai_api_key:
                raise ValueError(
                    "缺少 OpenAI API key。請在 .env 設定 OPENAI_API_KEY 或傳入 --openai_api_key。"
                )
            from openai import OpenAI

            self.client = OpenAI(api_key=openai_api_key)
            self.deployment = openai_model
        elif self.llm_provider == "ollama":
            ollama_url, ollama_model = resolve_ollama_config(ollama_url, ollama_model)
            if not ollama_url:
                raise ValueError(
                    "缺少 Ollama URL。請在 .env 設定 OLLAMA_URL 或傳入 --ollama_url。"
                )
            from openai import OpenAI

            self.client = OpenAI(api_key="ollama", base_url=ollama_url)
            self.deployment = ollama_model
        else:
            raise ValueError(f"Unsupported LLM provider: {self.llm_provider}")

        # 如果提供了索引文件路徑，嘗試載入現有索引
        if index_file_path and os.path.exists(f"{index_file_path}.index"):
            self.log_debug(f"嘗試從 {index_file_path} 載入現有索引...")
            loaded_successfully = self.load_index(index_file_path)

            if loaded_successfully:
                self.embedding_dimension = self.index.d
                self.log_debug("成功載入索引")
            else:
                self.log_debug("無法載入索引，將創建新索引")
                # 創建 FAISS 索引
                self.index = faiss.IndexFlatL2(self.embedding_dimension)

                # 初始化內部映射
                self.id_to_text: Dict[str, str] = {}
                self.id_to_source: Dict[str, str] = {}
                self.id_to_images: Dict[str, List[str]] = {}
        else:
            # 直接創建 FAISS 索引
            self.index = faiss.IndexFlatL2(self.embedding_dimension)

            # Internal mappings from index ID to content
            self.id_to_text: Dict[str, str] = {}
            self.id_to_source: Dict[str, str] = {}
            self.id_to_images: Dict[str, List[str]] = {}

    def get_embedding(self, text: str) -> np.ndarray:
        """
        Generate embeddings for a text string using the configured embedder.

        Args:
            text: Text to generate embeddings for.

        Returns:
            Numpy array of the embedding vector.
        """
        try:
            if not text or len(text.strip()) == 0:
                self.log_debug("警告: 遇到空文本")
                return np.zeros(self.embedding_dimension, dtype=np.float32)

            # 簡單 truncate 超長文本
            if len(text) > 8000:
                self.log_debug(f"截斷超長文本：{len(text)} -> 8000 字符")
                text = text[:8000]

            # 設定重試計數和超時
            max_retries = 3
            retry_count = 0
            base_wait_time = 2  # 秒

            while retry_count < max_retries:
                try:
                    # 調用 OpenAI 或 Ollama 的嵌入 API
                    embedding_kwargs = {
                        "input": text,
                        "model": self.embedding_model,
                    }
                    if (
                        self.llm_provider == "openai"
                        and self.embedding_dimension
                        and self.embedding_model.startswith("text-embedding-3")
                    ):
                        embedding_kwargs["dimensions"] = self.embedding_dimension

                    resp = self.client.embeddings.create(**embedding_kwargs)

                    # 處理回應中的向量
                    emb = (
                        resp.data[0].embedding
                        if hasattr(resp.data[0], "embedding")
                        else resp.data[0]["embedding"]
                    )

                    # 檢查向量質量
                    if not emb or len(emb) == 0:
                        self.log_debug("警告: API 返回空向量")
                        return np.zeros(self.embedding_dimension, dtype=np.float32)

                    if len(emb) != self.embedding_dimension:
                        self.last_embedding_error = (
                            f"Embedding 維度不符: 預期 {self.embedding_dimension}, 實際 {len(emb)}"
                        )
                        self.log_debug(self.last_embedding_error)
                        return np.zeros(self.embedding_dimension, dtype=np.float32)

                    # Convert to numpy array
                    self.last_embedding_error = None
                    return np.array(emb, dtype=np.float32)

                except (
                    requests.exceptions.ConnectionError,
                    requests.exceptions.Timeout,
                ) as e:
                    retry_count += 1
                    wait_time = base_wait_time * (2 ** (retry_count - 1))  # 指數退避
                    self.log_debug(
                        f"連線錯誤，嘗試第 {retry_count}/{max_retries} 次重試，等待 {wait_time} 秒: {e}"
                    )

                    if retry_count >= max_retries:
                        self.log_debug(f"達到最大重試次數，使用空向量替代")
                        break

                    time.sleep(wait_time)
                except Exception as e:
                    self.last_embedding_error = str(e)
                    self.log_debug(f"非連線相關錯誤: {e}")
                    break

            # 如果所有重試都失敗，返回空向量
            self.log_debug("Embedding 失敗，返回空向量")
            return np.zeros(self.embedding_dimension, dtype=np.float32)

        except Exception as e:
            self.last_embedding_error = str(e)
            self.log_debug(f"Embedding 錯誤: {e}")
            # Fallback to a zero vector
            return np.zeros(self.embedding_dimension, dtype=np.float32)

    def ingest_entries(
        self, entries: List[Dict[str, Any]], save_index_path: Optional[str] = None
    ) -> None:
        """
        Ingest a list of entries into the FAISS index.

        Each entry must be a dict containing:
          - 'text' or 'chunk': the text content
          - 'source': identifier (e.g., URL or filename)
          - 'metadata': optional dict with 'image_base64' list

        Args:
            entries: List of entry dictionaries.
            save_index_path: Optional path to save the index after ingestion.
        """
        vectors = []
        processed = 0
        skipped = 0
        tables = 0
        images = 0

        self.log_debug(f"開始處理 {len(entries)} 個項目...")

        for item in entries:
            # 取得文本內容
            text = item.get("chunk") or item.get("text", "")
            filetype = item.get("metadata", {}).get("filetype", "")

            # 記錄項目類型
            if "table" in filetype:
                tables += 1
            elif "image" in filetype:
                images += 1

            # 檢查是否有現有的 embedding
            existing_emb = item.get("metadata", {}).get("embedding", None)

            # 生成或使用現有的 embedding
            if (
                existing_emb
                and isinstance(existing_emb, list)
                and len(existing_emb) > 0
            ):
                # 使用現有的 embedding
                emb = np.array(existing_emb, dtype=np.float32)
                self.log_debug(f"使用現有 embedding: 長度={len(existing_emb)}")
            else:
                # 生成新的 embedding
                if not text or len(text.strip()) == 0:
                    self.log_debug(f"跳過空文本項目")
                    skipped += 1
                    continue

                try:
                    emb = self.get_embedding(text)
                    if not emb.any():  # 檢查是否為全零向量
                        self.log_debug(f"跳過無法嵌入的項目: {text[:50]}...")
                        skipped += 1
                        continue
                except Exception as e:
                    self.log_debug(f"嵌入過程中發生錯誤: {e}")
                    skipped += 1
                    continue

            # 生成唯一 ID 並記錄中繼資料
            node_id = str(uuid.uuid4())
            vectors.append(emb)

            # 記錄中繼資料
            source = item.get("source") or item.get("metadata", {}).get("filename", "")
            images_data = item.get("metadata", {}).get("image_base64", [])
            if isinstance(images_data, str):
                images_data = [images_data]

            self.id_to_text[node_id] = text
            self.id_to_source[node_id] = source
            self.id_to_images[node_id] = images_data
            processed += 1

            # 定期報告進度
            if processed % 50 == 0:
                self.log_debug(f"已處理 {processed} 項目...")

        # 將向量添加到 FAISS 索引
        if vectors:
            matrix = np.vstack(vectors)
            self.index.add(matrix)
            self.log_debug(
                f"添加 {len(vectors)} 個向量到 FAISS 索引，維度: {vectors[0].shape}"
            )
        elif entries:
            detail = (
                f" 最後的 embedding 錯誤: {self.last_embedding_error}"
                if self.last_embedding_error
                else ""
            )
            raise ValueError(
                "沒有任何項目成功建立向量索引，請確認 embedding service / model 可用。"
                + detail
            )

        # 報告處理結果
        self.log_debug(
            f"處理完成: 成功={processed}, 跳過={skipped}, 表格={tables}, 圖片={images}"
        )

        # 檢查索引狀態
        if hasattr(self.index, "ntotal"):
            self.log_debug(f"FAISS 索引中的總向量數: {self.index.ntotal}")

        # 如果提供了保存路徑，則保存索引
        if save_index_path:
            try:
                success = self.save_index(save_index_path)
                if success:
                    self.log_debug(f"索引已保存到 {save_index_path}")
                else:
                    self.log_debug(f"無法保存索引到 {save_index_path}")
            except Exception as e:
                self.log_debug(f"保存索引時發生錯誤: {e}")
                raise

    def query(self, query_text: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Search the index for top_k similar entries and generate an answer via GPT.

        Args:
            query_text: User query string.
            top_k: Number of nearest neighbors to retrieve.

        Returns:
            Dict containing 'answer' string and 'retrieved' list of context dicts.
        """
        try:
            # Generate query embedding
            q_emb = self.get_embedding(query_text)
            if not q_emb.any():
                detail = (
                    f" 最後的 embedding 錯誤: {self.last_embedding_error}"
                    if self.last_embedding_error
                    else ""
                )
                return {
                    "answer": "無法為查詢生成 embedding，請確認 embedding service / model 可用。"
                    + detail,
                    "retrieved": [],
                }
            distances, indices = self.index.search(
                np.array([q_emb], dtype=np.float32), top_k
            )
            sims = distances[0].tolist()
            idxs = indices[0].tolist()

            # Collect retrieved contexts
            retrieved = []
            all_texts = []
            node_ids = list(self.id_to_text.keys())
            for idx, sim in zip(idxs, sims):
                if idx < 0 or idx >= len(node_ids):
                    continue
                node_id = node_ids[idx]
                text = self.id_to_text[node_id]
                retrieved.append(
                    {
                        "text": text,
                        "source": self.id_to_source[node_id],
                        "distance": sim,
                        "images": self.id_to_images.get(node_id, []),
                    }
                )
                all_texts.append(f"來源: {self.id_to_source[node_id]}\n\n{text}")

            if not retrieved:
                return {"answer": "索引中沒有可用的檢索結果。", "retrieved": []}

            # Combine contexts with prompt
            context_text = "\n\n---\n\n".join(all_texts)
            prompt = f"""根據以下提供的資訊回答問題，如果提供的資訊不足以回答，請清楚表明。不要擅自添加未在資料中提及的資訊。
            
提供的資訊:
{context_text}

問題: {query_text}

回答:"""

            # Generate answer via LLM
            try:
                if self.deployment:  # Check if we have a model configured
                    try:
                        response = self.client.chat.completions.create(
                            model=self.deployment,
                            messages=[
                                {
                                    "role": "system",
                                    "content": "你是一個專業、精確、有幫助的助手。請根據提供的資訊回答問題。",
                                },
                                {"role": "user", "content": prompt},
                            ],
                            #  temperature=0.2,
                            #  max_tokens=800
                        )
                        answer = response.choices[0].message.content
                    except Exception as e:
                        self.log_debug(f"LLM 連線錯誤: {e}")
                        answer = "無法連線到 LLM 服務，但已成功檢索相關內容。請查看檢索結果或稍後再試。"
                else:
                    answer = "未配置 LLM 模型，僅提供檢索結果。"
            except Exception as e:
                self.log_debug(f"LLM 調用錯誤: {e}")
                answer = f"生成回答時發生錯誤: {str(e)}"

            return {"answer": answer, "retrieved": retrieved}
        except Exception as e:
            self.log_debug(f"查詢過程中發生錯誤: {e}")
            return {"answer": f"查詢過程中發生錯誤: {str(e)}", "retrieved": []}

    def log_debug(self, msg: str) -> None:
        """Print debug message if debug_mode is enabled."""
        if self.debug_mode:
            print(f"[DEBUG] {msg}")

    def display_results(self, results: Dict[str, Any]) -> None:
        """
        Display the answer and references (including images) in a notebook or console.

        Args:
            results: Dict returned by query().
        """
        # Print answer
        print("Answer:\n", results["answer"])
        print("\nReferences and images:\n")
        for i, ref in enumerate(results["retrieved"]):
            print(f"- Source: {ref['source']} (distance={ref['distance']:.3f})")

            # 顯示文本內容
            print(f"  Content:")
            text = ref["text"]
            # 如果文本超過 500 個字符，則只顯示前 500 個字符
            if len(text) > 500:
                print(
                    f"  {text[:500]}... (truncated, total length: {len(text)} characters)"
                )
            else:
                print(f"  {text}")

            # 顯示圖片資訊
            if ref["images"] and len(ref["images"]) > 0:
                print(f"  Images: {len(ref['images'])} found")
                for b64 in ref["images"]:
                    if not b64:
                        continue
                    try:
                        img_data = base64.b64decode(b64)
                        display(Image(data=img_data))  # type: ignore
                    except Exception:
                        print("  [Invalid image data]")
            print("")  # 添加空行以分隔參考項目

    def save_index(self, file_path: str) -> bool:
        """
        Save the FAISS index and related mapping data to a file.

        Args:
            file_path: Path where the index and mapping data will be saved.

        Returns:
            Boolean indicating whether the save was successful.
        """
        try:
            # 確保目標目錄存在
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

            # 準備要保存的資料
            data_to_save = {
                "id_to_text": self.id_to_text,
                "id_to_source": self.id_to_source,
                "id_to_images": self.id_to_images,
            }

            # 使用 pickle 序列化映射資料
            with open(f"{file_path}.pickle", "wb") as f:
                pickle.dump(data_to_save, f)

            # 使用 FAISS 內建函數保存索引
            faiss.write_index(self.index, f"{file_path}.index")

            self.log_debug(
                f"已成功保存索引到 {file_path}.index 和映射資料到 {file_path}.pickle"
            )

            return True
        except Exception as e:
            self.log_debug(f"保存索引時發生錯誤: {e}")
            return False

    def load_index(self, file_path: str) -> bool:
        """
        Load the FAISS index and related mapping data from a file.

        Args:
            file_path: Path where the index and mapping data are saved.

        Returns:
            Boolean indicating whether the load was successful.
        """
        try:
            # 檢查文件是否存在
            index_path = f"{file_path}.index"
            pickle_path = f"{file_path}.pickle"

            if not os.path.exists(index_path) or not os.path.exists(pickle_path):
                self.log_debug(f"索引文件不存在: {index_path} 或 {pickle_path}")
                return False

            # 載入 FAISS 索引
            self.index = faiss.read_index(index_path)

            # 載入映射資料
            with open(pickle_path, "rb") as f:
                data = pickle.load(f)

            # 恢復映射資料
            self.id_to_text = data["id_to_text"]
            self.id_to_source = data["id_to_source"]
            self.id_to_images = data["id_to_images"]

            self.log_debug(
                f"已成功載入索引，包含 {self.index.ntotal} 個向量和 {len(self.id_to_text)} 個文本項目"
            )

            return True
        except Exception as e:
            self.log_debug(f"載入索引時發生錯誤: {e}")
            return False


if __name__ == "__main__":
    """
    CLI usage examples:

    使用 OpenAI:
    $ python rag_system.py --embeddings sections_embeddings.json --query "你的問題" --llm_provider openai --openai_api_key YOUR_OPENAI_API_KEY --openai_model gpt-3.5-turbo

    使用 Ollama:
    $ python rag_system.py --embeddings output/gear_full_output.json --query "幫我找RGL表格" --llm_provider ollama --ollama_url http://your.ollama.server:11434/v1 --ollama_model qwen3:4b --top_k 20

    啟用調試模式:
    $ python rag_system.py --embeddings sections_embeddings.json --query "你的問題" --llm_provider ollama --ollama_url http://localhost:11434/v1 --ollama_model llama2 --debug

    參數說明:
    --embeddings: 包含文本和嵌入的JSON文件路徑
    --query: 用戶查詢文本
    --top_k: 檢索的最相似條目數量
    --llm_provider: 選擇LLM提供者 (openai 或 ollama)
    --debug: 啟用調試模式，顯示詳細日誌
    """
    import argparse

    parser = argparse.ArgumentParser(description="RAG System Command Line Interface")
    parser.add_argument(
        "--model_path",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Path to the model directory",
    )
    parser.add_argument(
        "--embedding_dim",
        type=int,
        default=None,
        help="Dimension of embedding vectors (defaults to provider config)",
    )
    parser.add_argument(
        "--embeddings",
        required=False,
        help="JSON file containing text entries to embed",
    )
    parser.add_argument("--query", required=True, help="Query to search for")
    parser.add_argument(
        "--top_k", type=int, default=5, help="Number of top results to return"
    )
    parser.add_argument(
        "--save_index",
        required=False,
        help="Path to save the FAISS index after ingestion",
    )
    parser.add_argument(
        "--load_index", required=False, help="Path to load a pre-built FAISS index"
    )
    parser.add_argument(
        "--llm_provider",
        choices=["openai", "ollama"],
        default="openai",
        help="LLM provider",
    )
    # OpenAI parameters
    parser.add_argument("--openai_api_key", required=False, help="OpenAI API key")
    parser.add_argument("--openai_model", required=False, help="OpenAI chat model")
    # Ollama parameters
    parser.add_argument("--ollama_url", required=False, help="Ollama server URL")
    parser.add_argument("--ollama_model", required=False, help="Ollama model name")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Initialize RAG system, optionally loading a pre-built index
    rag = RAGSystem(
        model_path=args.model_path,
        embedding_dimension=args.embedding_dim,
        llm_provider=args.llm_provider,
        openai_api_key=args.openai_api_key,
        openai_model=args.openai_model,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model,
        debug_mode=args.debug,
        index_file_path=args.load_index,
    )

    # If entries were provided, ingest them
    if args.embeddings and (
        not args.load_index or not os.path.exists(f"{args.load_index}.index")
    ):
        # Load entries
        entries = json.load(open(args.embeddings, "r", encoding="utf-8"))

        # Build index and optionally save it
        rag.ingest_entries(entries, save_index_path=args.save_index)

    # Run query
    results = rag.query(args.query, args.top_k)
    rag.display_results(results)
