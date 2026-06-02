from langchain_core.messages import AIMessage, ToolMessage


def extract_tool_calls_for_react_agent(messages: list) -> list[dict]:
    """
    Extract tool calls, inputs and outputs from a LangGraph prebuilt
    ReAct agent message history.
    """

    tool_outputs_by_id = {}

    # First collect outputs
    for message in messages:
        if isinstance(message, ToolMessage):
            tool_outputs_by_id[message.tool_call_id] = {
                "output": message.content,
                "tool_name": getattr(message, "name", None),
            }

    results = []

    # Then collect tool calls
    for message in messages:
        if not isinstance(message, AIMessage):
            continue

        for tool_call in message.tool_calls or []:
            call_id = tool_call["id"]

            results.append(
                {
                    "tool_name": tool_call["name"],
                    "tool_input": tool_call.get("args", {}),
                    "tool_output": tool_outputs_by_id.get(call_id, {}).get(
                        "output"
                    ),
                }
            )

    return results