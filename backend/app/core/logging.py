"""Logging setup with credential redaction.

Anything that smells like an API key or a connection string is masked before it
reaches a log handler, so BYOK credentials never land in logs.
"""
import logging
import re

_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{8,})"),
    re.compile(r"(gsk_[A-Za-z0-9_\-]{8,})"),
    re.compile(r"(AIza[A-Za-z0-9_\-]{8,})"),
    re.compile(r"(Bearer\s+[A-Za-z0-9._\-]{8,})", re.IGNORECASE),
    re.compile(r"(postgres(?:ql)?(?:\+\w+)?://[^\s]+)", re.IGNORECASE),
    re.compile(r"((?:api[_-]?key|authorization|x-api-key)\"?\s*[:=]\s*\"?)([^\s\"',}]+)",
               re.IGNORECASE),
]


def redact(text: str) -> str:
    out = text
    for pattern in _PATTERNS:
        if pattern.groups == 2:
            out = pattern.sub(r"\1[REDACTED]", out)
        else:
            out = pattern.sub("[REDACTED]", out)
    return out


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            record.args = tuple(
                redact(a) if isinstance(a, str) else a for a in record.args
            )
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    )
    handler.addFilter(RedactingFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
