import asyncio
from dotenv import load_dotenv
from agents import Agent, Runner
load_dotenv()

agent = Agent(
    name="設備工程師",
    instructions="必須簡單但是專業的回答使用者的問題",
    model="gpt-5.4-mini",
)

async def main():
    result = await Runner.run(agent, "請問冷氣機怎麼挑選好的品質")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())
