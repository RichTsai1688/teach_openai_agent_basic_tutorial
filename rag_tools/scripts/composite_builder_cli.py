#!/usr/bin/env python3
"""
composite_builder_cli.py

CompositeElementBuilder 的命令行介面，用於爬取網頁並生成結構化 JSON 資料。
"""
import sys
import argparse
from pathlib import Path
import os

from dotenv import load_dotenv

# 添加庫目錄到路徑
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
sys.path.append(str(PROJECT_ROOT / "lib"))

from composite_element_builder_v2 import CompositeElementBuilder


def first_non_empty(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def main():
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

    llm_provider = first_non_empty(
        args.llm_provider,
        os.getenv("BUILDER_LLM_PROVIDER"),
        os.getenv("LLM_PROVIDER"),
        "openai",
    )
    openai_api_key = first_non_empty(args.openai_api_key, os.getenv("OPENAI_API_KEY"))
    openai_model = first_non_empty(args.openai_model, os.getenv("OPENAI_MODEL"))
    ollama_url = first_non_empty(
        args.ollama_url, os.getenv("OLLAMA_URL"), os.getenv("OLLAMA_BASE_URL")
    )
    ollama_model = first_non_empty(args.ollama_model, os.getenv("OLLAMA_MODEL"))
    azure_api_key = first_non_empty(
        args.azure_api_key,
        os.getenv("AZURE_OPENAI_API_KEY"),
        os.getenv("AZURE_API_KEY"),
    )
    azure_endpoint = first_non_empty(
        args.azure_endpoint,
        os.getenv("AZURE_OPENAI_ENDPOINT"),
        os.getenv("AZURE_ENDPOINT"),
    )
    azure_deployment = first_non_empty(
        args.azure_deployment,
        os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        os.getenv("AZURE_DEPLOYMENT"),
    )
    azure_embedding_deployment = first_non_empty(
        args.azure_embedding_deployment,
        os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        os.getenv("AZURE_EMBEDDING_DEPLOYMENT"),
    )

    if llm_provider not in {"openai", "ollama", "azure"}:
        parser.error(
            "Builder 只支援 openai、ollama、azure；可用 --llm_provider 或在 .env 設定 LLM_PROVIDER"
        )

    if llm_provider == "openai":
        missing = []
        if not openai_api_key:
            missing.append("OPENAI_API_KEY")
        if not openai_model:
            missing.append("OPENAI_MODEL")
        if missing:
            parser.error(
                f"使用 OpenAI 時，請提供 {'、'.join(missing)}（CLI 參數或 .env）"
            )

    if llm_provider == "ollama":
        missing = []
        if not ollama_url:
            missing.append("OLLAMA_URL")
        if not ollama_model:
            missing.append("OLLAMA_MODEL")
        if missing:
            parser.error(
                f"使用 Ollama 時，請提供 {'、'.join(missing)}（CLI 參數或 .env）"
            )

    if llm_provider == "azure":
        missing = []
        if not azure_api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if not azure_endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not azure_deployment:
            missing.append("AZURE_OPENAI_DEPLOYMENT")
        if missing:
            parser.error(
                f"使用 Azure OpenAI 時，請提供 {'、'.join(missing)}（CLI 參數或 .env）"
            )

    # 確保輸出目錄存在
    out_path = args.out
    if not out_path.is_absolute():
        out_path = PROJECT_ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)

    builder = CompositeElementBuilder(
        start_url=args.url,
        out_path=out_path,
        max_pages=args.max_pages,
        llm_provider=llm_provider,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        azure_api_key=azure_api_key,
        azure_endpoint=azure_endpoint,
        azure_deployment=azure_deployment,
        azure_embedding_deployment=azure_embedding_deployment,
        debug_mode=args.debug,
    )
    try:
        builder.build()
    except Exception as exc:
        print(f"錯誤: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    """
    CLI usage examples:

    使用 OpenAI（先在 .env 填 OPENAI_API_KEY / OPENAI_MODEL）:
    $ python scripts/composite_builder_cli.py https://example.com --llm_provider openai --max_pages 10

    使用 Ollama（先在 .env 填 OLLAMA_URL / OLLAMA_MODEL）:
    $ python scripts/composite_builder_cli.py https://example.com --llm_provider ollama --max_pages 10

    python scripts/composite_builder_cli.py "https://www.3t.org.tw/News2.aspx?n=541&sms=47411" \
                                            --llm_provider ollama \
                                            --max_pages 10

    啟用調試模式:
    $ python scripts/composite_builder_cli.py https://example.com --debug --max_pages 3
    """
    main()
