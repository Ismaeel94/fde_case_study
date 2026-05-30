from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import Tool
from app.core.config import settings

def init_general_agent(tools: list[Tool]):
    llm = ChatOpenAI(model="gpt-4o", temperature=0.1, api_key=settings.OPENAI_API_KEY)
    agent = create_react_agent(model=llm, tools=tools)
    return agent
    