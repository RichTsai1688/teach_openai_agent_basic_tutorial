"""
Shared project configuration helpers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT.parent
DOTENV_PATH = PROJECT_ROOT / ".env"
REPO_DOTENV_PATH = REPO_ROOT / ".env"
EMBEDDER_CONFIG_PATH = PROJECT_ROOT / "docs" / "embedder.json"

_DOTENV_LOADED = False


def load_project_env() -> None:
    """Load repo-level and rag_tools-level environment files once."""
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    load_dotenv(REPO_DOTENV_PATH)
    load_dotenv(DOTENV_PATH)
    _DOTENV_LOADED = True


def pick_value(*values: Any) -> Any:
    """Return the first non-empty value."""
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def get_env_value(*keys: str) -> str | None:
    """Return the first non-empty environment variable."""
    load_project_env()
    for key in keys:
        value = os.getenv(key)
        if value is not None and value.strip():
            return value
    return None


def get_env_int(*keys: str) -> int | None:
    """Return the first non-empty environment variable as an int."""
    value = get_env_value(*keys)
    if value is None:
        return None
    return int(value)


def resolve_provider(provider: str | None, default: str = "openai") -> str:
    """Resolve the LLM provider from CLI or environment."""
    return pick_value(
        provider, get_env_value("LLM_PROVIDER", "RAG_LLM_PROVIDER"), default
    )


def load_embedder_config() -> dict[str, Any]:
    """Load the embedder configuration file."""
    with open(EMBEDDER_CONFIG_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_openai_config(
    api_key: str | None = None,
    model: str | None = None,
) -> tuple[str | None, str | None]:
    """Resolve OpenAI settings from CLI or environment."""
    return (
        pick_value(api_key, get_env_value("OPENAI_API_KEY")),
        pick_value(model, get_env_value("OPENAI_MODEL")),
    )


def resolve_ollama_config(
    url: str | None = None,
    model: str | None = None,
) -> tuple[str | None, str | None]:
    """Resolve Ollama settings from CLI or environment."""
    return (
        pick_value(url, get_env_value("OLLAMA_URL", "OLLAMA_BASE_URL")),
        pick_value(model, get_env_value("OLLAMA_MODEL")),
    )


def resolve_azure_config(
    api_key: str | None = None,
    endpoint: str | None = None,
    deployment: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """Resolve Azure OpenAI settings from CLI or environment."""
    return (
        pick_value(api_key, get_env_value("AZURE_OPENAI_API_KEY", "AZURE_API_KEY")),
        pick_value(endpoint, get_env_value("AZURE_OPENAI_ENDPOINT", "AZURE_ENDPOINT")),
        pick_value(
            deployment,
            get_env_value("AZURE_OPENAI_DEPLOYMENT", "AZURE_DEPLOYMENT"),
        ),
    )


def resolve_embedding_config(
    provider: str,
    embedding_dimension: int | None = None,
    azure_deployment: str | None = None,
    azure_embedding_deployment: str | None = None,
) -> tuple[str | None, int]:
    """Resolve embedding model and dimension for the active provider."""
    config = load_embedder_config()
    generic_model = get_env_value("RAG_EMBEDDING_MODEL")
    generic_dimension = get_env_int("RAG_EMBEDDING_DIMENSION")

    if provider == "ollama":
        model_kwargs = config.get("embedder_ollama", {}).get("model_kwargs", {})
        model = pick_value(
            generic_model,
            get_env_value("OLLAMA_EMBEDDING_MODEL"),
            model_kwargs.get("model"),
        )
        dimension = pick_value(
            embedding_dimension,
            get_env_int("OLLAMA_EMBEDDING_DIMENSION"),
            generic_dimension,
            768,
        )
        return model, int(dimension)

    model_kwargs = config.get("embedder", {}).get("model_kwargs", {})
    if provider == "azure":
        model = pick_value(
            generic_model,
            get_env_value(
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
                "AZURE_EMBEDDING_DEPLOYMENT",
            ),
            azure_embedding_deployment,
            azure_deployment,
            model_kwargs.get("model"),
        )
        dimension = pick_value(
            embedding_dimension,
            get_env_int(
                "AZURE_OPENAI_EMBEDDING_DIMENSION",
                "AZURE_EMBEDDING_DIMENSION",
            ),
            generic_dimension,
            model_kwargs.get("dimensions"),
            256,
        )
        return model, int(dimension)

    model = pick_value(
        generic_model,
        get_env_value("OPENAI_EMBEDDING_MODEL"),
        model_kwargs.get("model"),
    )
    dimension = pick_value(
        embedding_dimension,
        get_env_int("OPENAI_EMBEDDING_DIMENSION"),
        generic_dimension,
        model_kwargs.get("dimensions"),
        256,
    )
    return model, int(dimension)
