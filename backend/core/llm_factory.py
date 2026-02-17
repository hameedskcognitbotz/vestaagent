"""
VestaCode LLM Factory
======================
Centralized LLM provider management supporting Groq and Google Gemini.

Usage:
    from backend.core.llm_factory import get_llm, LLMProvider, set_provider, get_config

    # Get an LLM with the global default provider
    llm = get_llm(temperature=0.2)

    # Get an LLM with a specific provider
    llm = get_llm(provider=LLMProvider.GEMINI, temperature=0.1)

    # Switch the global default
    set_provider(LLMProvider.GEMINI)

    # Override per-agent
    set_agent_provider("vision", LLMProvider.GEMINI)
"""

import os
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


class LLMProvider(str, Enum):
    GROQ = "groq"
    GEMINI = "gemini"


# Default model names per provider
DEFAULT_MODELS: Dict[LLMProvider, str] = {
    LLMProvider.GROQ: "meta-llama/llama-4-scout-17b-16e-instruct",
    LLMProvider.GEMINI: "gemini-2.0-flash",
}

# Provider-specific API key env vars
API_KEY_VARS: Dict[LLMProvider, str] = {
    LLMProvider.GROQ: "GROQ_API_KEY",
    LLMProvider.GEMINI: "GOOGLE_API_KEY",
}


@dataclass
class LLMConfig:
    """Global LLM configuration state."""
    default_provider: LLMProvider = LLMProvider.GROQ
    agent_overrides: Dict[str, LLMProvider] = field(default_factory=dict)
    model_overrides: Dict[str, str] = field(default_factory=dict)  # agent_name -> model

    def get_provider_for(self, agent_name: Optional[str] = None) -> LLMProvider:
        """Get the provider for a specific agent, falling back to default."""
        if agent_name and agent_name in self.agent_overrides:
            return self.agent_overrides[agent_name]
        return self.default_provider

    def get_model_for(self, agent_name: Optional[str] = None, provider: Optional[LLMProvider] = None) -> str:
        """Get the model name for a specific agent."""
        if agent_name and agent_name in self.model_overrides:
            return self.model_overrides[agent_name]
        p = provider or self.get_provider_for(agent_name)
        return DEFAULT_MODELS[p]


# Global singleton config
_config = LLMConfig()


def get_config() -> LLMConfig:
    """Get the current LLM configuration."""
    return _config


def set_provider(provider: LLMProvider):
    """Set the global default LLM provider."""
    _config.default_provider = provider
    print(f"🔄 LLM Provider switched to: {provider.value}")


def set_agent_provider(agent_name: str, provider: LLMProvider, model: Optional[str] = None):
    """Override the LLM provider for a specific agent."""
    _config.agent_overrides[agent_name] = provider
    if model:
        _config.model_overrides[agent_name] = model
    print(f"🔄 Agent '{agent_name}' → {provider.value}" + (f" ({model})" if model else ""))


def get_llm(
    agent_name: Optional[str] = None,
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
    temperature: float = 0.1,
    **kwargs
):
    """
    Create an LLM instance.

    Priority:
        1. Explicit `provider` + `model` args (highest)
        2. Per-agent override from config
        3. Global default provider

    Args:
        agent_name: Name of the calling agent (for per-agent overrides)
        provider:   Explicit provider override
        model:      Explicit model override
        temperature: LLM temperature
        **kwargs:   Additional provider-specific args

    Returns:
        A LangChain-compatible LLM instance (ChatGroq or ChatGoogleGenerativeAI)
    """
    # Resolve provider
    resolved_provider = provider or _config.get_provider_for(agent_name)

    # Resolve model
    resolved_model = model or _config.get_model_for(agent_name, resolved_provider)

    # Check API key availability
    api_key_var = API_KEY_VARS[resolved_provider]
    api_key = os.environ.get(api_key_var)

    if not api_key:
        # Fallback: try the other provider
        other = LLMProvider.GEMINI if resolved_provider == LLMProvider.GROQ else LLMProvider.GROQ
        other_key = os.environ.get(API_KEY_VARS[other])
        if other_key:
            print(f"⚠️  {api_key_var} not set. Falling back to {other.value}.")
            resolved_provider = other
            resolved_model = model or DEFAULT_MODELS[other]
        else:
            raise ValueError(
                f"No API key found. Set {API_KEY_VARS[LLMProvider.GROQ]} or "
                f"{API_KEY_VARS[LLMProvider.GEMINI]} in your environment."
            )

    # Create the LLM
    if resolved_provider == LLMProvider.GROQ:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=resolved_model,
            temperature=temperature,
            **kwargs
        )
    elif resolved_provider == LLMProvider.GEMINI:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=resolved_model,
            temperature=temperature,
            google_api_key=api_key,
            **kwargs
        )
    else:
        raise ValueError(f"Unknown provider: {resolved_provider}")


def get_available_providers() -> Dict[str, Any]:
    """Check which providers have valid API keys configured."""
    available = {}
    for provider in LLMProvider:
        key_var = API_KEY_VARS[provider]
        key = os.environ.get(key_var, "")
        available[provider.value] = {
            "available": bool(key),
            "env_var": key_var,
            "default_model": DEFAULT_MODELS[provider],
            "key_preview": f"{key[:8]}...{key[-4:]}" if len(key) > 12 else ("set" if key else "not set"),
        }
    return available


def get_status() -> Dict[str, Any]:
    """Full status report of LLM configuration."""
    return {
        "default_provider": _config.default_provider.value,
        "agent_overrides": {k: v.value for k, v in _config.agent_overrides.items()},
        "model_overrides": _config.model_overrides,
        "providers": get_available_providers(),
    }
