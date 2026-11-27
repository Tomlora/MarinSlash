import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest
from ollama import ChatResponse

from cogs.llm import DEFAULT_MODEL, DISCORD_MESSAGE_LIMIT, LLM


def chunk(content="", thinking=None, done_reason=None):
    return ChatResponse(
        message={"role": "assistant", "content": content, "thinking": thinking},
        done=done_reason is not None,
        done_reason=done_reason,
    )


async def stream(*chunks):
    for item in chunks:
        yield item


def invoke(reasoning, *streams, model=DEFAULT_MODEL):
    cog = object.__new__(LLM)
    cog.generation_lock = asyncio.Semaphore(1)
    cog.ollama = SimpleNamespace(chat=AsyncMock(side_effect=streams))
    ctx = AsyncMock()
    status, continuation = AsyncMock(), AsyncMock()
    ctx.send.side_effect = [status, continuation]
    asyncio.run(LLM.llm_leger.callback(cog, ctx, "Une question", model, reasoning))
    return cog.ollama.chat, status, continuation


def test_reasoning_only_retries_same_question_once_without_thinking():
    first = stream(chunk(thinking="privé"), chunk(thinking="privé"), chunk("\n", done_reason="length"))
    chat, status, _ = invoke(True, first, stream(chunk("Réponse directe.")), model="qwen3.5:2b")
    requests = [item.kwargs for item in chat.await_args_list]
    assert [request["think"] for request in requests] == [True, False]
    assert [request["model"] for request in requests] == ["qwen3.5:2b"] * 2
    assert requests[0]["messages"] == requests[1]["messages"]
    assert requests[0]["options"]["num_predict"] > requests[1]["options"]["num_predict"]
    assert requests[0]["options"]["num_ctx"] == requests[1]["options"]["num_ctx"] == 4096
    edits = [item.kwargs["content"] for item in status.edit.await_args_list]
    assert sum("réfléchit" in edit for edit in edits) == 1
    assert "mode direct" in edits[-2]
    assert edits[-1] == "Réponse directe."
    assert all("privé" not in edit for edit in edits)


@pytest.mark.parametrize("reasoning", [False, True])
def test_visible_answer_is_kept_even_at_token_limit(reasoning):
    first_part = "A" * DISCORD_MESSAGE_LIMIT
    chat, status, continuation = invoke(
        reasoning, stream(chunk(thinking="privé"), chunk(first_part), chunk(" suite", done_reason="length"))
    )
    chat.assert_awaited_once()
    assert status.edit.await_args == call(content=first_part)
    continuation.edit.assert_awaited_once_with(content="suite")


@pytest.mark.parametrize("reasoning", [False, True])
def test_empty_or_whitespace_only_streams_stop_after_allowed_attempts(reasoning):
    attempts = [stream(), stream(chunk(" \n"))] if reasoning else [stream(chunk(" \n"))]
    chat, status, _ = invoke(reasoning, *attempts)
    assert chat.await_count == len(attempts)
    assert "aucune réponse" in status.edit.await_args.kwargs["content"]
