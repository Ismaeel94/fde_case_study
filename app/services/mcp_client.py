import ast
import json
import re
from contextlib import asynccontextmanager
from typing import Any
from datetime import datetime

from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import CallToolResult

from app.core.config import settings

REAL_DICT_ROW_RE = re.compile(r"RealDictRow\(\[(.*?)\]\)", re.DOTALL)
DATETIME_RE = re.compile(r"datetime\.datetime\((.*?)\)")


class MCPQueryError(Exception):
    """Raised when an MCP postgres query fails."""


@asynccontextmanager
async def postgres_mcp_tools():
    async with sse_client(settings.MCP_URL) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)
            yield tools


async def call_postgres_tool(tool_name: str, arguments: dict) -> CallToolResult:
    async with sse_client(settings.MCP_URL) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


def _extract_error_text(result: CallToolResult) -> str:
    parts: list[str] = []
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts) or "MCP tool call failed"

def _replace_datetime_repr(value: str) -> str:
    def repl(match: re.Match) -> str:
        parts = [int(p.strip()) for p in match.group(1).split(",")]
        return repr(datetime(*parts).isoformat())

    return DATETIME_RE.sub(repl, value)

def _parse_real_dict_rows_from_string(value: str) -> list[dict]:
    rows: list[dict] = []
    for match in REAL_DICT_ROW_RE.finditer(value):
        try:
            row_text = f"[{match.group(1)}]"
            row_text = _replace_datetime_repr(row_text)

            pairs = ast.literal_eval(row_text)
            rows.append(dict(pairs))
        except (SyntaxError, ValueError, TypeError):
            continue
    return rows


def _normalize_row(row: dict) -> dict:
    result_value = row.get("result")
    if isinstance(result_value, str) and "RealDictRow" in result_value:
        parsed_rows = _parse_real_dict_rows_from_string(result_value)
        if parsed_rows:
            return parsed_rows[0]
    return row


def _rows_from_payload(payload: Any) -> list[dict]:
    if payload is None:
        return []

    if isinstance(payload, str) and "RealDictRow" in payload:
        return _parse_real_dict_rows_from_string(payload)

    if isinstance(payload, list):
        rows: list[dict] = []
        for item in payload:
            if isinstance(item, dict):
                rows.append(_normalize_row(item))
            elif isinstance(item, str) and "RealDictRow" in item:
                rows.extend(_parse_real_dict_rows_from_string(item))
        return rows

    if isinstance(payload, dict):
        result_value = payload.get("result")
        if isinstance(result_value, str) and "RealDictRow" in result_value:
            parsed_rows = _parse_real_dict_rows_from_string(result_value)
            if parsed_rows:
                return parsed_rows

        for key in ("rows", "data", "results", "records"):
            if key in payload:
                nested_rows = _rows_from_payload(payload[key])
                if nested_rows:
                    return nested_rows

        columns = payload.get("columns")
        values = payload.get("rows")
        if isinstance(columns, list) and isinstance(values, list):
            return [
                dict(zip(columns, row))
                for row in values
                if isinstance(row, (list, tuple))
            ]

        if payload and not (len(payload) == 1 and "result" in payload):
            return [_normalize_row(payload)]

    return []


def parse_mcp_query_rows(result: CallToolResult) -> list[dict]:
    if result.isError:
        raise MCPQueryError(_extract_error_text(result))

    if result.structuredContent is not None:
        rows = _rows_from_payload(result.structuredContent)
        if rows:
            return rows

    for block in result.content or []:
        text = getattr(block, "text", None)
        if not text:
            continue
        rows = _rows_from_payload(text)
 
        if rows:
            return rows

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        rows = _rows_from_payload(payload)
        if rows:
            return rows

    return []


async def query_postgres(sql: str) -> list[dict]:
    result = await call_postgres_tool("query", {"sql": sql})
    return parse_mcp_query_rows(result)


def get_first_row(rows: list[dict]) -> dict | None:
    return rows[0] if rows else None


def get_column(row: dict | None, column_name: str, default: Any = None) -> Any:
    if not row:
        return default

    if column_name in row:
        return row[column_name]

    result_value = row.get("result")
    if isinstance(result_value, str) and "RealDictRow" in result_value:
        parsed_rows = _parse_real_dict_rows_from_string(result_value)
        if parsed_rows:
            return parsed_rows[0].get(column_name, default)

    return default
