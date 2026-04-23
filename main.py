import asyncio
from dotenv import load_dotenv
load_dotenv()

from agents import Agent, Runner, ToolSearchTool, WebSearchTool, function_tool, tool_namespace

@function_tool(defer_loading=True)
def get_current_time():
    from datetime import datetime
    return datetime.now().isoformat()


crm_tools = tool_namespace(
    name="custom",
    description="custom tools for customer lookups.",
    tools=[get_current_time],
)


agent = Agent(
    name="設備工程師",
    instructions="必須簡單但是專業的回答使用者的問題",
    model="gpt-5.4-mini",
    tools=[WebSearchTool(), ToolSearchTool(), *crm_tools],
)

async def main():
    result = await Runner.run(agent, "請問現在幾點了 （台灣時間），還有台灣台中現在的天氣如何？")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
