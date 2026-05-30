# app/agent/mcp_client.py

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.client.sse import sse_client
from langchain_mcp_adapters.tools import load_mcp_tools

from contextlib import asynccontextmanager
from app.core.config import settings

@asynccontextmanager
async def postgres_mcp_tools():
    async with sse_client(settings.MCP_URL) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)
            yield tools


async def call_postgres_tool(tool_name: str, arguments: dict):
    async with sse_client(settings.MCP_URL) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result