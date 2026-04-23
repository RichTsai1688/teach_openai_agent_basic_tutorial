#!/usr/bin/env python3
"""
rag_cli.py

RAG 系統的命令行介面，支援建立嵌入索引和執行查詢。
"""
import sys
import argparse
import json
from pathlib import Path
import os

from dotenv import load_dotenv

# 添加庫目錄到路徑
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.append(str(PROJECT_ROOT / "lib"))

from rag_system import RAGSystem


def first_non_empty(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def main():
    parser = argparse.ArgumentParser(description="RAGSystem CLI")
    parser.add_argument(
        "--embeddings", type=str, required=False, help="Path to embeddings JSON"
    )
    parser.add_argument("--query", type=str, required=True, help="Query string")
    parser.add_argument("--top_k", type=int, default=5, help="Number of results")
    parser.add_argument(
        "--model_path",
        type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Model path (unused, kept for compatibility)",
    )
    parser.add_argument(
        "--embedding_dim",
        type=int,
        default=None,
        help="Embedding dimension (optional, defaults to docs/embedder.json)",
    )
    parser.add_argument(
        "--save_index", type=str, default=None, help="Path to save the FAISS index"
    )
    parser.add_argument(
        "--load_index",
        type=str,
        default=None,
        help="Path to load a pre-built FAISS index",
    )
    parser.add_argument(
        "--llm_provider",
        choices=["openai", "ollama"],
        default=None,
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

    # 檢查參數合理性
    if not args.embeddings and not args.load_index:
        print("錯誤: 必須提供 --embeddings 或 --load_index 參數")
        sys.exit(1)

    llm_provider = first_non_empty(
        args.llm_provider,
        os.getenv("RAG_LLM_PROVIDER"),
        os.getenv("LLM_PROVIDER"),
        "openai",
    )
    openai_api_key = first_non_empty(args.openai_api_key, os.getenv("OPENAI_API_KEY"))
    openai_model = first_non_empty(args.openai_model, os.getenv("OPENAI_MODEL"))
    ollama_url = first_non_empty(
        args.ollama_url, os.getenv("OLLAMA_URL"), os.getenv("OLLAMA_BASE_URL")
    )
    ollama_model = first_non_empty(args.ollama_model, os.getenv("OLLAMA_MODEL"))

    if llm_provider not in {"openai", "ollama"}:
        parser.error(
            "RAG CLI 目前只支援 openai 或 ollama；可用 --llm_provider 或在 .env 設定 LLM_PROVIDER"
        )

    if llm_provider == "openai" and not openai_api_key:
        parser.error(
            "使用 OpenAI 時，請提供 --openai_api_key 或在 .env 設定 OPENAI_API_KEY"
        )

    if llm_provider == "ollama" and not ollama_url:
        parser.error("使用 Ollama 時，請提供 --ollama_url 或在 .env 設定 OLLAMA_URL")

    # 建立 RAG 系統，可選擇載入現有索引
    rag = RAGSystem(
        model_path=args.model_path,
        embedding_dimension=args.embedding_dim,
        llm_provider=llm_provider,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        debug_mode=args.debug,
        index_file_path=args.load_index,
    )

    # 如果提供了 embeddings 參數且沒有成功載入索引，則處理數據
    if args.embeddings and (not args.load_index or not rag.index.ntotal):
        with open(args.embeddings, "r", encoding="utf-8") as input_file:
            entries = json.load(input_file)
        print(f"載入 {len(entries)} 個項目...")

        # 建立索引並可選擇保存
        try:
            rag.ingest_entries(entries, save_index_path=args.save_index)
            print(f"索引建立完成，包含 {rag.index.ntotal} 個向量")
            if rag.index.ntotal == 0:
                print("錯誤: 索引為空，請確認 embedding service / model 可用。")
                sys.exit(1)
        except Exception as e:
            print(f"索引建立過程中發生錯誤: {e}")
            if args.save_index:
                print("嘗試保存已處理的部分...")
                try:
                    if rag.save_index(args.save_index):
                        print(f"部分索引已保存到 {args.save_index}")
                    else:
                        print("無法保存部分索引")
                except Exception as save_err:
                    print(f"保存部分索引時發生錯誤: {save_err}")

            if rag.index.ntotal == 0 or not args.query:
                sys.exit(1)
    elif rag.index.ntotal > 0:
        print(f"使用已載入的索引，包含 {rag.index.ntotal} 個向量")

    # 執行查詢
    if args.query:
        try:
            results = rag.query(args.query, args.top_k)
            rag.display_results(results)
        except Exception as e:
            print(f"查詢過程中發生錯誤: {e}")
            sys.exit(1)


if __name__ == "__main__":
    """
    CLI usage examples:

    使用 OpenAI（先在 .env 填 OPENAI_API_KEY / OPENAI_MODEL）:
    $ python scripts/rag_cli.py --embeddings output/sections_embeddings.json --query "你的問題" --llm_provider openai

    使用 Ollama（先在 .env 填 OLLAMA_URL / OLLAMA_MODEL）:
    $ python scripts/rag_cli.py --embeddings output/gear_full_output.json --query "幫我找系統表格" --llm_provider ollama --top_k 20

    python scripts/rag_cli.py --embeddings output/composite_v2.json \
                    --save_index output/composite_v2_index \
                    --query "介紹一下T大使" \
                    --llm_provider ollama \
                    --top_k 5

    python scripts/rag_cli.py --load_index output/composite_v2_index \
                    --query "介紹一下培育對象" \
                    --llm_provider ollama \
                    --top_k 10

    啟用調試模式:
    $ python scripts/rag_cli.py --embeddings output/sections_embeddings.json --query "你的問題" --llm_provider ollama --debug

    保存索引:
    $ python scripts/rag_cli.py --embeddings output/gear_composite.json --query "你是什麼公司" --save_index output/gear_index --llm_provider ollama

    載入現有索引:
    $ python scripts/rag_cli.py --load_index output/gear_index --query "機械設備有哪些資訊" --llm_provider ollama
    """
    main()
