"""What each supported provider can actually do.

Providers differ in whether they need a key, whether they accept a custom
endpoint, and whether their models reliably support tool calling. The
orchestrator reads this registry to decide between the tool-calling path and the
pre-fetched-context fallback, rather than assuming every provider behaves the
same way.

`tool_calling` here describes the provider's TYPICAL current models. A specific
model may still refuse; the orchestrator degrades gracefully if it does.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    requires_api_key: bool
    supports_tool_calling: bool
    supports_custom_base_url: bool
    default_base_url: str | None = None
    suggested_models: list[str] = field(default_factory=list)
    notes: str = ""
    api_key_url: str | None = None


PROVIDERS: dict[str, ProviderSpec] = {
    "openai": ProviderSpec(
        id="openai",
        label="OpenAI",
        requires_api_key=True,
        supports_tool_calling=True,
        supports_custom_base_url=True,
        suggested_models=["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"],
        api_key_url="https://platform.openai.com/api-keys",
    ),
    "anthropic": ProviderSpec(
        id="anthropic",
        label="Anthropic",
        requires_api_key=True,
        supports_tool_calling=True,
        supports_custom_base_url=False,
        suggested_models=[
            "claude-sonnet-4-5", "claude-opus-4-5", "claude-haiku-4-5-20251001",
        ],
        api_key_url="https://console.anthropic.com/settings/keys",
    ),
    "google": ProviderSpec(
        id="google",
        label="Google Gemini",
        requires_api_key=True,
        supports_tool_calling=True,
        supports_custom_base_url=False,
        suggested_models=["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
        api_key_url="https://aistudio.google.com/apikey",
    ),
    "groq": ProviderSpec(
        id="groq",
        label="Groq",
        requires_api_key=True,
        supports_tool_calling=True,
        supports_custom_base_url=False,
        suggested_models=[
            "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
        ],
        api_key_url="https://console.groq.com/keys",
    ),
    "openrouter": ProviderSpec(
        id="openrouter",
        label="OpenRouter",
        requires_api_key=True,
        supports_tool_calling=True,
        supports_custom_base_url=True,
        default_base_url="https://openrouter.ai/api/v1",
        suggested_models=[
            "openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.3-70b-instruct",
        ],
        notes="Tool-calling support varies by the underlying model you select.",
        api_key_url="https://openrouter.ai/keys",
    ),
    "deepseek": ProviderSpec(
        id="deepseek",
        label="DeepSeek",
        requires_api_key=True,
        supports_tool_calling=True,
        supports_custom_base_url=True,
        default_base_url="https://api.deepseek.com/v1",
        suggested_models=["deepseek-chat", "deepseek-reasoner"],
        notes="deepseek-reasoner does not support tool calling; the assistant "
              "falls back to pre-fetched context for it.",
        api_key_url="https://platform.deepseek.com/api_keys",
    ),
    "together": ProviderSpec(
        id="together",
        label="Together AI",
        requires_api_key=True,
        supports_tool_calling=True,
        supports_custom_base_url=True,
        default_base_url="https://api.together.xyz/v1",
        suggested_models=[
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
        ],
        api_key_url="https://api.together.ai/settings/api-keys",
    ),
    "ollama": ProviderSpec(
        id="ollama",
        label="Ollama (local or self-hosted)",
        requires_api_key=False,
        supports_tool_calling=True,
        supports_custom_base_url=True,
        default_base_url="http://localhost:11434",
        suggested_models=["llama3.1", "qwen2.5", "mistral-nemo"],
        notes=(
            "A localhost endpoint only works when the BACKEND itself can reach "
            "it. A browser or a deployed backend cannot reach the teacher's own "
            "machine. For deployed use, point this at a reachable Ollama "
            "service."
        ),
    ),
    "openai_compatible": ProviderSpec(
        id="openai_compatible",
        label="Other OpenAI-compatible endpoint",
        requires_api_key=True,
        supports_tool_calling=True,
        supports_custom_base_url=True,
        suggested_models=[],
        notes="Supply the full /v1 base URL of any OpenAI-compatible service.",
    ),
}

# Models known NOT to support tool calling, despite the provider generally doing so.
NO_TOOL_CALLING_MODELS = {
    "deepseek-reasoner",
    "o1-mini",
    "o1-preview",
}


def get_provider(provider_id: str) -> ProviderSpec | None:
    return PROVIDERS.get(provider_id)


def supports_tools(provider_id: str, model: str) -> bool:
    """Whether this provider+model pair should be given tools."""
    spec = PROVIDERS.get(provider_id)
    if spec is None or not spec.supports_tool_calling:
        return False
    base = model.split("/")[-1].strip().lower()
    return base not in NO_TOOL_CALLING_MODELS


def list_providers() -> list[dict]:
    """Serializable catalogue for the Settings page."""
    return [
        {
            "id": s.id,
            "label": s.label,
            "requires_api_key": s.requires_api_key,
            "supports_tool_calling": s.supports_tool_calling,
            "supports_custom_base_url": s.supports_custom_base_url,
            "default_base_url": s.default_base_url,
            "suggested_models": s.suggested_models,
            "notes": s.notes,
            "api_key_url": s.api_key_url,
        }
        for s in PROVIDERS.values()
    ]
