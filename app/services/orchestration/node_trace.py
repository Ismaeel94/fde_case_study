from pydantic import BaseModel, Field


class NodeTrace(BaseModel):
    node_name: str
    user_id: int
    user_roles: list[str]
    tool_calls: list[dict] = Field(default_factory=list)


def node_trace_update(
    *,
    node_name: str,
    user_id: int,
    user_roles: list[str],
    tool_calls: list[dict] | None = None,
) -> dict:
    return {
        "node_traces": [
            NodeTrace(
                node_name=node_name,
                user_id=user_id,
                user_roles=user_roles,
                tool_calls=tool_calls or [],
            ).model_dump()
        ]
    }
