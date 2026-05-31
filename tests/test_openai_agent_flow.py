from __future__ import annotations

import json
from types import SimpleNamespace

from fastmcp_learning.clients.openai_agent_flow import (
    mcp_tool_to_openai_tool,
    tool_result_to_text,
)


def test_mcp_tool_to_openai_tool_uses_tool_schema() -> None:
    tool = SimpleNamespace(
        name="add",
        description="Add two integers.",
        inputSchema={
            "type": "object",
            "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
            "required": ["a", "b"],
        },
    )

    converted = mcp_tool_to_openai_tool(tool)

    assert converted["type"] == "function"
    assert converted["name"] == "add"
    assert converted["parameters"] == tool.inputSchema
    assert converted["strict"] is False


def test_tool_result_to_text_prefers_fastmcp_data() -> None:
    result = SimpleNamespace(data={"result": 42}, structured_content={"result": "ignored"})

    assert json.loads(tool_result_to_text(result)) == {"result": 42}
