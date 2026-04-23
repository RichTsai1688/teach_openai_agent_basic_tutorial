from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    case_root = Path(__file__).resolve().parent.parent
    repo_root = case_root.parent
    python_path = repo_root / ".venv" / "bin" / "python"
    server_path = case_root / "fastmcp_stats_agent" / "server.py"
    db_path = case_root / "data" / "air_compressor_teaching_cases.sqlite"
    output_dir = case_root / "fastmcp_stats_agent" / "mcp_configs" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    server_name = "air-compressor-stats"
    server_block = {
        "command": str(python_path),
        "args": [str(server_path)],
        "cwd": str(case_root),
        "env": {
            "PYTHONPATH": str(case_root),
            "AIR_COMPRESSOR_DB_PATH": str(db_path),
        },
        "transport": "stdio",
        "description": "Air compressor statistics tools for AI-agent classroom demos",
    }

    canonical_config = {
        "mcpServers": {
            server_name: server_block,
        }
    }

    claude_desktop_config = canonical_config

    with open(output_dir / "mcpServers.local.json", "w", encoding="utf-8") as handle:
        json.dump(canonical_config, handle, ensure_ascii=False, indent=2)

    with open(output_dir / "claude_desktop_config.local.json", "w", encoding="utf-8") as handle:
        json.dump(claude_desktop_config, handle, ensure_ascii=False, indent=2)

    print(f"Generated config: {output_dir / 'mcpServers.local.json'}")
    print(f"Generated config: {output_dir / 'claude_desktop_config.local.json'}")
    print(f"Python: {python_path}")
    print(f"Server: {server_path}")
    print(f"SQLite: {db_path}")


if __name__ == "__main__":
    sys.exit(main())
