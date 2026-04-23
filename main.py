import asyncio
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

load_dotenv()

from agents import (
    Agent,
    Runner,
    ToolSearchTool,
    WebSearchTool,
    function_tool,
    tool_namespace,
)
from rag_agent_tools import rag_index_status, rag_retrieve, rag_search


@function_tool(defer_loading=True)
def get_current_time():
    from datetime import datetime

    return datetime.now().isoformat()


crm_tools = tool_namespace(
    name="custom",
    description="custom tools for customer lookups.",
    tools=[get_current_time],
)

local_rag_tools = tool_namespace(
    name="rag",
    description="local FAISS RAG tools for searching the prepared composite_v2 knowledge index.",
    tools=[rag_search, rag_retrieve, rag_index_status],
)


agent = Agent(
    name="設備工程師",
    instructions=(
        "必須簡單但是專業的回答使用者的問題。"
        "如果問題需要查詢本地教材、課程、文件或 composite_v2 知識庫，先使用 rag tools。"
        "需要直接根據資料回答時用 rag_search；需要先檢視來源片段再自行整合時用 rag_retrieve。"
    ),
    model="gpt-5.4-mini",
    tools=[WebSearchTool(), ToolSearchTool(), *crm_tools, *local_rag_tools],
)

async def main():
    result = await Runner.run(agent, "歷史對話：剛剛我查1. RAG 命中資料：`source=0d10b8cb-92dc-4267-9c3e-42e962b605a1`。以上回歷史路。 本次對話："+"我剛剛問了什麼？")
    Console().print(Markdown(str(result.final_output)))


if __name__ == "__main__":
    asyncio.run(main())
