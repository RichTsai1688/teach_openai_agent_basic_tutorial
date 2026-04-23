from __future__ import annotations

import argparse
import asyncio

from rich.console import Console
from rich.markdown import Markdown

from agent_runtime import run_equipment_agent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the equipment engineer agent once.")
    parser.add_argument(
        "message",
        nargs="?",
        default="請先使用 MCP 分析 Case 01 自主感測，判斷多個感測訊號是否異常，並用繁體中文摘要。",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    answer = await run_equipment_agent(args.message)
    Console().print(Markdown(answer))


if __name__ == "__main__":
    asyncio.run(main())
