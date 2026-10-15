"""Chat orchestration: tool-calling loop plus genuine token streaming.

Two paths, chosen from the model registry:

* Tool calling -- the model requests tools, the backend runs them under the
  teacher's authorization, and the result goes back for a final streamed answer.
* Pre-fetched context -- for models without tool support, a small authorized
  snapshot of the teacher's scope is placed in the prompt instead.

Tokens are forwarded to the client as they arrive from the provider. Nothing is
buffered and no typing effect is simulated.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import date

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from sqlalchemy.orm import Session

from app.ai.model_registry import supports_tools
from app.ai.provider_factory import (
    ProviderConfig,
    ProviderConfigError,
    build_chat_model,
    sanitize_provider_error,
)
from app.ai.tools import build_tools, serialize_tool_result
from app.core.security import TeacherPrincipal
from app.prompts.teacher_assistant import build_system_prompt
from app.services import analytics as A

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4


def _sse(event: str, data: dict) -> str:
    """One Server-Sent Event frame."""
    return f"event: {event}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


def _history_to_messages(history: list[dict]) -> list[BaseMessage]:
    """Convert the client's transcript into LangChain messages.

    Only `role` and `content` are honoured. Anything else a client sends --
    including any claim about identity or permissions -- is discarded here.
    """
    out: list[BaseMessage] = []
    for item in history:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            out.append(HumanMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
    return out


def _fallback_context(
    db: Session, principal: TeacherPrincipal, threshold: float
) -> str:
    """A compact authorized snapshot for models that cannot call tools.

    Deliberately aggregate-only: no student-level rows are placed in the prompt.
    """
    subjects = A.list_subjects_for_teacher(db, principal.teacher_id)
    lines = ["# AUTHORIZED DATA SNAPSHOT (read-only, aggregate)"]
    lines.append(
        f"\nThreshold in use: {threshold}% (illustrative application setting).\n"
    )
    for s in subjects:
        summary = A.subject_attendance_summary(db, s["subject_code"], threshold)
        lines.append(
            f"- {s['subject_code']} ({s['subject_name']}, {s['subject_type']}): "
            f"{summary['enrolled_students']} enrolled, "
            f"{summary['classes_conducted']} classes conducted, "
            f"pooled attendance {summary['class_attendance_percentage']}%, "
            f"{summary['students_below_threshold']} student(s) below threshold."
        )
    lines.append(
        "\nThis snapshot is aggregate only. Student-level detail is not "
        "available to this model because the selected model does not support "
        "tool calling. Tell the teacher to use the application pages, or to "
        "switch to a tool-calling model, for per-student answers."
    )
    return "\n".join(lines)


async def stream_chat(
    *,
    db: Session,
    principal: TeacherPrincipal,
    config: ProviderConfig,
    history: list[dict],
    threshold: float,
    today: date | None = None,
    timeout: int = 120,
) -> AsyncIterator[str]:
    """Yield SSE frames for one chat turn.

    Frames: `status`, `tool`, `token`, `error`, `done`. The client renders
    `token` text progressively and treats `error` as terminal-but-retryable.
    """
    today = today or date.today()

    try:
        model = build_chat_model(config, timeout=timeout)
    except ProviderConfigError as exc:
        yield _sse("error", {"message": str(exc), "kind": "configuration"})
        yield _sse("done", {"ok": False})
        return
    except Exception as exc:  # unexpected construction failure
        logger.warning("Chat model construction failed: %s", type(exc).__name__)
        yield _sse("error", {
            "message": sanitize_provider_error(exc), "kind": "configuration",
        })
        yield _sse("done", {"ok": False})
        return

    subjects = A.list_subjects_for_teacher(db, principal.teacher_id)
    use_tools = supports_tools(config.provider, config.model)

    system = build_system_prompt(
        teacher_name=principal.full_name,
        teacher_id=principal.teacher_id,
        designation=principal.designation,
        is_coordinator=principal.is_coordinator,
        subjects=subjects,
        threshold=threshold,
        today=today.isoformat(),
    )
    if not use_tools:
        system = f"{system}\n\n{_fallback_context(db, principal, threshold)}"

    messages: list[BaseMessage] = [SystemMessage(content=system)]
    messages.extend(_history_to_messages(history))

    tools = build_tools(db, principal, threshold, today=today) if use_tools else []
    tool_map = {t.name: t for t in tools}

    try:
        # ---- tool-calling rounds (non-streamed; we need the full tool call) --
        if use_tools:
            bound = model.bind_tools(tools)
            for _round in range(MAX_TOOL_ROUNDS):
                yield _sse("status", {"state": "thinking"})

                ai: AIMessage = await bound.ainvoke(messages)
                calls = getattr(ai, "tool_calls", None) or []
                if not calls:
                    # The model answered without tools. If it produced text we
                    # still want it streamed, so fall through to the stream
                    # below using the accumulated messages.
                    break

                messages.append(ai)
                for call in calls:
                    name = call.get("name", "")
                    args = call.get("args", {}) or {}
                    tool = tool_map.get(name)

                    yield _sse("tool", {"name": name, "state": "running"})

                    if tool is None:
                        result: object = {
                            "error": "unknown_tool",
                            "message": f"No tool named '{name}' is available.",
                        }
                    else:
                        try:
                            result = await asyncio.to_thread(tool.func, **args)
                        except TypeError as exc:
                            result = {"error": "bad_arguments", "message": str(exc)}
                        except Exception as exc:
                            logger.exception("Tool %s failed", name)
                            result = {
                                "error": "tool_failed",
                                "message": f"{name} could not complete.",
                            }

                    denied = isinstance(result, dict) and result.get("error") == (
                        "authorization_denied"
                    )
                    yield _sse("tool", {
                        "name": name,
                        "state": "denied" if denied else "complete",
                    })

                    messages.append(ToolMessage(
                        content=serialize_tool_result(result),
                        tool_call_id=call.get("id", name),
                    ))
            else:
                messages.append(SystemMessage(content=(
                    "Tool call limit reached. Answer using the results already "
                    "retrieved, and say plainly if the picture is incomplete."
                )))

        # ---- final streamed answer -----------------------------------------
        yield _sse("status", {"state": "streaming"})

        produced = False
        async for chunk in model.astream(messages):
            text = chunk.content
            if isinstance(text, list):  # Anthropic-style content blocks
                text = "".join(
                    part.get("text", "")
                    for part in text
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            if text:
                produced = True
                yield _sse("token", {"text": text})

        if not produced:
            yield _sse("error", {
                "message": "The model returned an empty response. Try again.",
                "kind": "empty",
            })
            yield _sse("done", {"ok": False})
            return

        yield _sse("done", {"ok": True})

    except asyncio.CancelledError:
        # The client disconnected or pressed Stop. Do not emit an error frame;
        # just let the generator close so the upstream request is torn down.
        logger.info("Chat stream cancelled by client")
        raise
    except Exception as exc:
        logger.warning("Chat stream failed: %s", type(exc).__name__)
        yield _sse("error", {
            "message": sanitize_provider_error(exc), "kind": "provider",
        })
        yield _sse("done", {"ok": False})


async def test_provider_connection(
    config: ProviderConfig, *, timeout: int = 30
) -> dict:
    """Make one tiny real call to verify a BYOK configuration."""
    try:
        model = build_chat_model(config, timeout=timeout)
    except ProviderConfigError as exc:
        return {"ok": False, "message": str(exc)}

    try:
        reply = await asyncio.wait_for(
            model.ainvoke([HumanMessage(content="Reply with the single word: ready")]),
            timeout=timeout,
        )
        content = reply.content
        if isinstance(content, list):
            content = "".join(
                p.get("text", "") for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            )
        return {
            "ok": True,
            "message": "Connection succeeded.",
            "model": config.model,
            "provider": config.provider,
            "supports_tool_calling": supports_tools(config.provider, config.model),
            "sample": (content or "").strip()[:120],
        }
    except TimeoutError:
        return {"ok": False, "message": "The provider did not respond in time."}
    except Exception as exc:
        return {"ok": False, "message": sanitize_provider_error(exc)}
