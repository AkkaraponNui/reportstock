"""Tests for the chat agent's tool dispatch and agentic loop.

The loop talks to the Anthropic API, so these drive it with a fake client. No
credentials are needed and no request is made. What is checked is the mechanics
that would otherwise only fail in front of a user: tool dispatch, result shaping,
how history is built, the tool_use to end_turn transition, the round cap, refusal
handling, and the exact shape of the request the SDK is handed.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "ui"))

import chat_agent  # noqa: E402


# --------------------------------------------------------------------------
# a fake Anthropic client
# --------------------------------------------------------------------------

class Blk:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeStream:
    def __init__(self, message, text):
        self._message = message
        self._text = text

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def __iter__(self):
        for ch in self._text:
            yield types.SimpleNamespace(
                type="content_block_delta",
                delta=types.SimpleNamespace(type="text_delta", text=ch),
            )

    def get_final_message(self):
        return self._message


class FakeMessages:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def stream(self, **kwargs):
        # Snapshot the history length now: run_turn mutates the caller's list in
        # place, so keeping the reference would report the final length for every
        # call. The real SDK serializes the request at this same moment.
        self.calls.append(dict(kwargs, _n_messages=len(kwargs["messages"])))
        message, text = self.script.pop(0)
        return FakeStream(message, text)


class FakeClient:
    def __init__(self, script):
        self.messages = FakeMessages(script)


def msg(stop_reason, content, stop_details=None):
    return Blk(stop_reason=stop_reason, content=content, stop_details=stop_details)


def text_block(t):
    return Blk(type="text", text=t)


def tool_block(tool_id, name, tool_input):
    return Blk(type="tool_use", id=tool_id, name=name, input=tool_input)


def tool_results(messages, index):
    """The tool_result blocks in one message. A message's content is a string or
    a block list depending on the turn, and only the tool-result turns are lists."""
    content = messages[index]["content"]
    assert isinstance(content, list), "expected a block list at index {}".format(index)
    return content


# --------------------------------------------------------------------------
# tool definitions
# --------------------------------------------------------------------------

class TestToolDefinitions:
    def test_every_tool_has_a_dispatcher(self):
        declared = {t["name"] for t in chat_agent.TOOLS}
        assert declared == set(chat_agent.DISPATCH), (
            "a tool Claude can call with no implementation fails at runtime"
        )

    def test_schemas_are_well_formed(self):
        for t in chat_agent.TOOLS:
            schema = t["input_schema"]
            assert t["name"] and t["description"]
            assert schema["type"] == "object"
            for required in schema.get("required", []):
                assert required in schema.get("properties", {}), (
                    "{} requires {} but never declares it".format(t["name"], required)
                )

    def test_descriptions_say_when_to_use_the_tool(self):
        # A bare restatement of the name gives the model nothing to choose on.
        for t in chat_agent.TOOLS:
            assert len(t["description"]) > 60, "{} is underspecified".format(t["name"])

    def test_side_effect_tools_are_declared(self):
        assert chat_agent.SIDE_EFFECT_TOOLS <= set(chat_agent.DISPATCH)


class TestToolDispatch:
    def test_unknown_tool_returns_an_error_not_an_exception(self):
        out = chat_agent.execute_tool("no_such_tool", {})
        assert "error" in out

    def test_missing_ticker_returns_a_usable_error(self):
        out = chat_agent.execute_tool("get_fundamentals", {"ticker": "ZZZZNOPE"})
        assert "error" in out
        assert "hint" in out, "an error should tell the model what to do next"

    def test_a_raising_tool_is_caught(self, monkeypatch):
        def boom(_tool_input):
            raise RuntimeError("upstream exploded")

        monkeypatch.setitem(chat_agent.DISPATCH, "list_stocks", boom)
        out = chat_agent.execute_tool("list_stocks", {})
        assert "error" in out and "upstream exploded" in out["error"]

    def test_non_us_listing_explains_the_gap(self):
        out = chat_agent.execute_tool("get_risk_factors", {"ticker": "7203.T"})
        # Either real data or a clear explanation; never a bare failure.
        assert "error" not in out or "note" in out


# --------------------------------------------------------------------------
# the loop
# --------------------------------------------------------------------------

class TestRunTurn:
    def test_plain_answer(self):
        client = FakeClient([(msg("end_turn", [text_block("สวัสดีครับ")]), "สวัสดีครับ")])
        messages = [{"role": "user", "content": "สวัสดี"}]
        streamed = []
        res = chat_agent.run_turn(client, messages, on_text=streamed.append)

        assert res["text"] == "สวัสดีครับ"
        assert "".join(streamed) == "สวัสดีครับ"
        assert res["tools"] == []
        assert [m["role"] for m in messages] == ["user", "assistant"]

    def test_one_tool_then_an_answer(self):
        client = FakeClient([
            (msg("tool_use", [tool_block("t1", "list_stocks", {})]), ""),
            (msg("end_turn", [text_block("มี 40 ตัว")]), "มี 40 ตัว"),
        ])
        messages = [{"role": "user", "content": "มีหุ้นอะไรบ้าง"}]
        started = []
        res = chat_agent.run_turn(client, messages,
                                  on_tool_start=lambda n, _i: started.append(n))

        assert res["text"] == "มี 40 ตัว"
        assert started == ["list_stocks"]
        assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]

        result = tool_results(messages, 2)[0]
        assert result["type"] == "tool_result"
        assert result["tool_use_id"] == "t1"
        assert result["is_error"] is False
        assert json.loads(result["content"])["count"] >= 0

    def test_history_grows_between_requests(self):
        client = FakeClient([
            (msg("tool_use", [tool_block("t1", "list_stocks", {})]), ""),
            (msg("end_turn", [text_block("ok")]), "ok"),
        ])
        chat_agent.run_turn(client, [{"role": "user", "content": "x"}])
        assert client.messages.calls[0]["_n_messages"] == 1
        assert client.messages.calls[1]["_n_messages"] == 3

    def test_failed_tool_is_flagged_and_the_loop_recovers(self):
        client = FakeClient([
            (msg("tool_use", [tool_block("t2", "get_fundamentals", {"ticker": "NOPE"})]), ""),
            (msg("end_turn", [text_block("ไม่มีข้อมูล")]), "ไม่มีข้อมูล"),
        ])
        messages = [{"role": "user", "content": "NOPE"}]
        res = chat_agent.run_turn(client, messages)

        result = tool_results(messages, 2)[0]
        assert result["is_error"] is True
        assert "error" in json.loads(result["content"])
        assert res["text"] == "ไม่มีข้อมูล"

    def test_parallel_tools_return_in_one_user_message(self):
        # Splitting them across messages silently trains the model to stop
        # calling tools in parallel.
        client = FakeClient([
            (msg("tool_use", [tool_block("a", "list_stocks", {}),
                              tool_block("b", "get_sector_medians", {})]), ""),
            (msg("end_turn", [text_block("เทียบแล้ว")]), "เทียบแล้ว"),
        ])
        messages = [{"role": "user", "content": "เทียบ"}]
        res = chat_agent.run_turn(client, messages)

        assert len(messages) == 4
        assert len(tool_results(messages, 2)) == 2
        assert len(res["tools"]) == 2

    def test_round_cap_stops_a_runaway_loop(self):
        client = FakeClient([(msg("tool_use", [tool_block("x", "list_stocks", {})]), "")] * 40)
        res = chat_agent.run_turn(client, [{"role": "user", "content": "loop"}], max_rounds=3)
        assert len(client.messages.calls) == 3
        assert "3" in res["text"]

    def test_refusal_is_surfaced(self):
        client = FakeClient([
            (msg("refusal", [], stop_details=Blk(category="cyber", explanation="x")), ""),
        ])
        res = chat_agent.run_turn(client, [{"role": "user", "content": "..."}])
        assert res["refused"] is True
        assert "cyber" in res["text"]

    def test_assistant_turns_are_echoed_whole(self):
        # Thinking blocks must go back unchanged on the same model, so the loop
        # appends response.content rather than extracting the text.
        blocks = [Blk(type="thinking", thinking=""), text_block("hi")]
        client = FakeClient([(msg("end_turn", blocks), "hi")])
        messages = [{"role": "user", "content": "hi"}]
        chat_agent.run_turn(client, messages)
        assert messages[1]["content"] is blocks


class TestRequestShape:
    @pytest.fixture
    def sent(self):
        client = FakeClient([(msg("end_turn", [text_block("hi")]), "hi")])
        chat_agent.run_turn(client, [{"role": "user", "content": "hi"}], effort="medium")
        return client.messages.calls[0]

    def test_model_is_opus_5(self, sent):
        assert sent["model"] == "claude-opus-5"

    def test_adaptive_thinking_without_a_token_budget(self, sent):
        assert sent["thinking"] == {"type": "adaptive"}

    def test_effort_is_nested_in_output_config(self, sent):
        assert sent["output_config"] == {"effort": "medium"}

    def test_sampling_params_are_absent(self, sent):
        # Removed on this model family; sending them is a 400.
        assert "temperature" not in sent
        assert "top_p" not in sent
        assert "top_k" not in sent

    def test_system_prompt_and_tools_are_sent(self, sent):
        assert isinstance(sent["system"], str) and len(sent["system"]) > 500
        assert len(sent["tools"]) == len(chat_agent.TOOLS)

    def test_system_prompt_keeps_its_load_bearing_rules(self):
        prompt = chat_agent.SYSTEM_PROMPT
        assert "อย่าตอบตัวเลขจากความจำ" in prompt, "the read-before-quoting rule is gone"
        assert "get_peer_comparison" in prompt, "peer context rule is gone"
        assert "dividend_contribution" in prompt, "the dividend split rule is gone"
