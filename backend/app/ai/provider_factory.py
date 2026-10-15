"""Build a LangChain chat model from a per-request BYOK provider configuration.

Credentials arrive on the request, are used to construct a client, and are never
written to the database, a log, or a response. Nothing is cached between
requests, so a key cannot outlive the call it was sent for.

Custom endpoint URLs are validated before use to limit SSRF exposure.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from langchain_core.language_models.chat_models import BaseChatModel

from app.ai.model_registry import get_provider

# Hosts that are always allowed to be loopback, because a developer running
# Ollama locally is an expected and documented setup.
LOCAL_PROVIDER_IDS = {"ollama"}


class ProviderConfigError(ValueError):
    """Raised for a configuration problem the teacher can fix themselves."""


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    model: str
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.1


def _validate_base_url(url: str, provider_id: str) -> str:
    """Reject endpoints that could be used to probe internal infrastructure."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ProviderConfigError("Endpoint URL must use http or https.")
    if not parsed.hostname:
        raise ProviderConfigError("Endpoint URL is missing a hostname.")

    host = parsed.hostname
    allow_private = provider_id in LOCAL_PROVIDER_IDS

    # Resolve and check every address the hostname maps to.
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ProviderConfigError(f"Endpoint hostname could not be resolved: {host}") from exc

    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        if addr.is_loopback and allow_private:
            continue
        if (
            addr.is_private
            or addr.is_loopback
            or addr.is_link_local
            or addr.is_reserved
            or addr.is_multicast
        ):
            raise ProviderConfigError(
                "Endpoint URL resolves to a private or loopback address, which "
                "is not permitted for this provider."
            )
    if parsed.scheme == "http" and not allow_private:
        raise ProviderConfigError("Remote endpoints must use https.")
    return url.rstrip("/")


def build_chat_model(config: ProviderConfig, *, timeout: int = 120) -> BaseChatModel:
    """Instantiate the LangChain chat model for this provider configuration."""
    spec = get_provider(config.provider)
    if spec is None:
        raise ProviderConfigError(f"Unknown provider '{config.provider}'.")
    if not config.model.strip():
        raise ProviderConfigError("A model ID is required.")

    api_key = (config.api_key or "").strip() or None
    if spec.requires_api_key and not api_key:
        raise ProviderConfigError(
            f"{spec.label} requires an API key. Add one in Settings."
        )

    base_url = (config.base_url or "").strip() or spec.default_base_url
    if base_url:
        if not spec.supports_custom_base_url and config.base_url:
            raise ProviderConfigError(
                f"{spec.label} does not accept a custom endpoint URL."
            )
        base_url = _validate_base_url(base_url, spec.id)
    elif spec.id == "openai_compatible":
        raise ProviderConfigError(
            "An endpoint URL is required for an OpenAI-compatible provider."
        )

    common = {"model": config.model, "temperature": config.temperature}

    if config.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            **common, api_key=api_key, timeout=timeout, max_tokens=4096,
        )

    if config.provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            **common, google_api_key=api_key, timeout=timeout,
        )

    if config.provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(**common, api_key=api_key, timeout=timeout)

    if config.provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=config.model,
            temperature=config.temperature,
            base_url=base_url,
            client_kwargs={"timeout": timeout},
        )

    # openai, openrouter, deepseek, together and any other OpenAI-style service
    # all speak the same wire protocol.
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        **common,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=1,
    )


def sanitize_provider_error(exc: Exception) -> str:
    """Turn an upstream exception into a message that is safe to show a teacher.

    Provider SDKs routinely echo the request -- including the Authorization
    header -- into their exception text, so the raw message is never returned.
    """
    from app.core.logging import redact

    name = type(exc).__name__
    text = redact(str(exc))

    lowered = text.lower()
    if "api key" in lowered or "unauthorized" in lowered or "401" in lowered:
        return "The provider rejected the API key. Check the key in Settings."
    if "quota" in lowered or "insufficient" in lowered or "429" in lowered:
        return "The provider reported a rate limit or quota problem. Try again shortly."
    if "not found" in lowered or "404" in lowered:
        return "The provider does not recognise that model ID. Check it in Settings."
    if "timeout" in lowered or "timed out" in lowered:
        return "The provider did not respond in time. Try again or pick another model."
    if "connect" in lowered or "connection" in lowered:
        return (
            "Could not reach the provider endpoint. If you are using Ollama, "
            "confirm the backend can reach that URL."
        )

    # Fall back to a short, redacted excerpt rather than the full payload.
    excerpt = text[:200]
    return f"The provider request failed ({name}): {excerpt}"
