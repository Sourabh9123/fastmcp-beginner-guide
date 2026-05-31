from __future__ import annotations

import json

import pytest

from fastmcp_learning.server import mcp


@pytest.mark.asyncio
async def test_add_tool_returns_structured_result() -> None:
    result = await mcp.call_tool("add", {"a": 4, "b": 6})

    assert result.structured_content == {"result": 10}


@pytest.mark.asyncio
async def test_learning_resource_template_returns_topic_note() -> None:
    content = await mcp.read_resource("learning://topic/tools?detail=long")

    payload = json.loads(content.contents[0].content)
    assert payload["topic"] == "tools"
    assert payload["detail"] == "long"
    assert "active capabilities" in payload["explanation"]


@pytest.mark.asyncio
async def test_prompt_template_renders_message() -> None:
    prompt = await mcp.render_prompt(
        "teach_mcp_concept",
        {"concept": "resources", "audience": "beginner"},
    )

    assert len(prompt.messages) == 1
    assert prompt.messages[0].role == "user"
    assert "resources" in prompt.messages[0].content.text
