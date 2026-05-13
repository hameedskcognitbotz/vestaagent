"""
VestaCode LLM Factory (Refined)
===============================
Standardized interface for Google Gemini and Groq with 
intelligent agent-to-model mapping.
"""

import os
from enum import Enum
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field

class LLMProvider(str, Enum):
    GROQ = "groq"
    GEMINI = "gemini"

# --- CONFIGURATION ---

# Updated for April 2026 Production API
AGENT_MODEL_MAP: Dict[str, str] = {
    "vision": "gemini-3.1-pro-preview",        # Best for floor plan feature extraction
    "stylist": "gemini-3-flash-preview",       # Best for rapid design variants
    "compliance": "gemini-3.1-pro-preview",    # Best for 200pg Indian Tariff Orders
    "orchestrator": "gemini-3.1-pro-preview",  # Best for complex LangGraph routing
}

DEFAULT_MODELS: Dict[LLMProvider, str] = {
    LLMProvider.GROQ: "llama-3.3-70b-versatile",
    LLMProvider.GEMINI: "gemini-3-flash-preview",
}

API_KEY_VARS: Dict[LLMProvider, str] = {
    LLMProvider.GROQ: "GROQ_API_KEY",
    LLMProvider.GEMINI: "GOOGLE_API_KEY",
}

@dataclass
class LLMConfig:
    default_provider: LLMProvider = LLMProvider.GEMINI
    agent_overrides: Dict[str, LLMProvider] = field(default_factory=dict)
    model_overrides: Dict[str, str] = field(default_factory=dict)

    def get_target_provider(self, agent_name: Optional[str]) -> LLMProvider:
        if agent_name and agent_name in self.agent_overrides:
            return self.agent_overrides[agent_name]
        return self.default_provider

    def get_target_model(self, agent_name: Optional[str], provider: LLMProvider) -> str:
        # 1. Manual override takes top priority
        if agent_name and agent_name in self.model_overrides:
            return self.model_overrides[agent_name]
        
        # 2. Agent-specific optimized defaults
        if agent_name in AGENT_MODEL_MAP:
            return AGENT_MODEL_MAP[agent_name]
            
        # 3. Provider general default
        return DEFAULT_MODELS[provider]

# Global Singleton
_config = LLMConfig()

# --- FACTORY INTERFACE ---

def get_llm(
    agent_name: Optional[str] = None,
    provider: Optional[LLMProvider] = None,
    model: Optional[str] = None,
    temperature: float = 0.1,
    **kwargs
):
    """
    Returns a LangChain-compatible LLM instance with fallback logic.
    """
    # 1. Resolve Provider and Model
    res_provider = provider or _config.get_target_provider(agent_name)
    res_model = model or _config.get_target_model(agent_name, res_provider)

    # 2. Key Check & Fallback Logic
    api_key = os.environ.get(API_KEY_VARS[res_provider])
    
    if not api_key:
        # If primary fails, check if the other is available
        other_p = LLMProvider.GEMINI if res_provider == LLMProvider.GROQ else LLMProvider.GROQ
        other_key = os.environ.get(API_KEY_VARS[other_p])
        
        if other_key:
            print(f"⚠️ {res_provider.value} key missing. Falling back to {other_p.value}.")
            res_provider = other_p
            res_model = DEFAULT_MODELS[other_p] # Reset to other's safe default
            api_key = other_key
        else:
            raise EnvironmentError(f"No API keys found for {res_provider.value} or {other_p.value}.")

    # 3. Instantiate
    if res_provider == LLMProvider.GROQ:
        from langchain_groq import ChatGroq
        return ChatGroq(model=res_model, temperature=temperature, **kwargs)
    
    elif res_provider == LLMProvider.GEMINI:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=res_model, 
            temperature=temperature, 
            google_api_key=api_key,
            **kwargs
        )

# --- UTILS ---

def set_global_provider(provider: LLMProvider):
    _config.default_provider = provider

def set_agent_config(agent_name: str, provider: LLMProvider, model: Optional[str] = None):
    _config.agent_overrides[agent_name] = provider
    if model:
        _config.model_overrides[agent_name] = model