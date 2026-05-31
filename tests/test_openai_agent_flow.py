from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from fastmcp_learning.clients.openai_agent_flow import (
    AgentFlowError,
    mcp_tool_to_openai_tool,
    parse_tool_arguments,
    tool_error_to_text,
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


def test_mcp_tool_to_openai_tool_requires_name() -> None:
    with pytest.raises(AgentFlowError, match="missing a name"):
        mcp_tool_to_openai_tool(SimpleNamespace(inputSchema={}))


def test_parse_tool_arguments_accepts_json_object() -> None:
    call = SimpleNamespace(arguments='{"a": 19, "b": 23}')

    assert parse_tool_arguments(call) == {"a": 19, "b": 23}


def test_parse_tool_arguments_rejects_invalid_json() -> None:
    call = SimpleNamespace(arguments='{"a":')

    with pytest.raises(AgentFlowError, match="invalid JSON"):
        parse_tool_arguments(call)


def test_parse_tool_arguments_requires_json_object() -> None:
    call = SimpleNamespace(arguments='["not", "an", "object"]')

    with pytest.raises(AgentFlowError, match="not a JSON object"):
        parse_tool_arguments(call)


def test_tool_error_to_text_returns_json_payload() -> None:
    assert json.loads(tool_error_to_text(AgentFlowError("bad tool call"))) == {
        "error": "bad tool call"
    }
