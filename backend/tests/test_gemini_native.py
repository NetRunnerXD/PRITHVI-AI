import json

from app.llm.gemini_native import (
    build_payload,
    openai_messages_to_gemini,
    openai_tools_to_gemini,
    parse_gemini_response,
)


def test_system_and_user_to_contents():
    sys_text, contents = openai_messages_to_gemini(
        [
            {"role": "system", "content": "You are PRITHVI-AI."},
            {"role": "user", "content": "Rain in Haldia?"},
        ]
    )
    assert "PRITHVI-AI" in sys_text
    assert contents[0]["role"] == "user"
    assert contents[0]["parts"][0]["text"] == "Rain in Haldia?"


def test_tool_roundtrip_shape():
    _, contents = openai_messages_to_gemini(
        [
            {"role": "user", "content": "AQI?"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "data", "arguments": '{"need":"aqi"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"aqi": 112})},
        ]
    )
    assert contents[1]["role"] == "model"
    assert contents[1]["parts"][0]["functionCall"]["name"] == "data"
    assert contents[2]["parts"][0]["functionResponse"]["response"]["aqi"] == 112


def test_parse_text_and_function_call():
    parsed = parse_gemini_response(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "AQI is 112."},
                            {"functionCall": {"name": "data", "args": {"need": "forecast"}}},
                        ]
                    }
                }
            ]
        }
    )
    assert parsed["content"] == "AQI is 112."
    assert parsed["tool_calls"][0]["name"] == "data"
    assert "forecast" in parsed["tool_calls"][0]["arguments"]


def test_tool_response_keeps_function_name():
    _, contents = openai_messages_to_gemini(
        [
            {"role": "user", "content": "rank floods"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c1", "function": {"name": "data", "arguments": '{"need":"rank"}'}},
                ],
            },
            {"role": "tool", "tool_call_id": "c1", "content": json.dumps({"need": "rank"})},
        ]
    )
    assert contents[1]["parts"][0]["functionCall"]["name"] == "data"
    assert contents[2]["parts"][0]["functionResponse"]["name"] == "data"
    assert contents[1]["role"] == "model"
    assert contents[2]["role"] == "user"


def test_does_not_merge_call_and_response():
    _, contents = openai_messages_to_gemini(
        [
            {"role": "user", "content": "AQI?"},
            {
                "role": "assistant",
                "tool_calls": [{"function": {"name": "data", "arguments": '{"need":"aqi"}'}}],
            },
            {"role": "tool", "content": '{"aqi":1}'},
            {"role": "user", "content": "and rain?"},
        ]
    )
    roles = [c["role"] for c in contents]
    assert roles == ["user", "model", "user", "user"]
    assert "functionCall" in contents[1]["parts"][0]
    assert "functionResponse" in contents[2]["parts"][0]
    assert contents[3]["parts"][0]["text"] == "and rain?"


def test_plain_user_turns_still_merge():
    _, contents = openai_messages_to_gemini(
        [
            {"role": "user", "content": "Hi"},
            {"role": "user", "content": "Rain?"},
        ]
    )
    assert len(contents) == 1
    assert [p["text"] for p in contents[0]["parts"]] == ["Hi", "Rain?"]


def test_build_payload_is_narration_only():
    payload = build_payload(
        [
            {"role": "system", "content": "You are PRITHVI-AI."},
            {"role": "user", "content": "Rain in Haldia?"},
        ],
        tools=[{"function": {"name": "data", "parameters": {"type": "object"}}}],
    )
    gc = payload["generationConfig"]
    assert gc["thinkingConfig"]["thinkingLevel"] == "minimal"
    assert gc["maxOutputTokens"] >= 400
    assert gc["maxOutputTokens"] <= 512
    assert "temperature" not in gc
    assert "tools" not in payload
    assert "toolConfig" not in payload


def test_skips_thought_only_parts():
    parsed = parse_gemini_response(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"thought": True, "text": "internal"},
                            {"text": "AQI is 112."},
                        ]
                    }
                }
            ]
        }
    )
    assert parsed["content"] == "AQI is 112."
    assert parsed["tool_calls"] == []


def test_xml_prose_becomes_tool_calls():
    parsed = parse_gemini_response(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": '<function=data{"need":"forecast"}>'}],
                    }
                }
            ]
        }
    )
    assert parsed["tool_calls"][0]["name"] == "data"
    assert parsed["content"] == ""


def test_tools_drop_additional_properties():
    g = openai_tools_to_gemini(
        [
            {
                "type": "function",
                "function": {
                    "name": "data",
                    "description": "facts",
                    "parameters": {
                        "type": "object",
                        "properties": {"need": {"type": "string"}},
                        "additionalProperties": False,
                    },
                },
            }
        ]
    )
    params = g[0]["functionDeclarations"][0]["parameters"]
    assert "additionalProperties" not in params
