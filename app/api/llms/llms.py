from langchain_openai import ChatOpenAI
from app.core.config import settings

def get_llm() -> ChatOpenAI:
    return ChatOpenAI(model="gpt-4o", temperature=0.1, api_key=settings.OPENAI_API_KEY)
