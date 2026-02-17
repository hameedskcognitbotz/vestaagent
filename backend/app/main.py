from dotenv import load_dotenv
import os
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from backend.core.bim_state import BIMProjectState, BIMElement, ObjectType, Vector3
from backend.agents.orchestrator.graph import app_graph, memory_manager, STATIC_KNOWLEDGE
from backend.core.llm_factory import (
    get_status as llm_status, 
    set_provider, 
    set_agent_provider, 
    LLMProvider, 
    get_available_providers
)
from pydantic import BaseModel
from typing import Optional
import uvicorn
import uuid

app = FastAPI(title="VestaCode API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "alive", "message": "VestaCode Orchestrator is ready."}

# ============================================================================
#  LLM PROVIDER MANAGEMENT
# ============================================================================

@app.get("/llm/status")
async def get_llm_status():
    """Check which LLM providers are available and current configuration."""
    return llm_status()

class SetProviderRequest(BaseModel):
    provider: str  # "groq" or "gemini"

@app.post("/llm/provider")
async def switch_llm_provider(request: SetProviderRequest):
    """Switch the global default LLM provider."""
    try:
        provider = LLMProvider(request.provider.lower())
        # Verify API key exists
        available = get_available_providers()
        if not available[provider.value]["available"]:
            return {
                "error": f"API key not set for {provider.value}. "
                         f"Set {available[provider.value]['env_var']} in your environment."
            }
        set_provider(provider)
        return {"status": "ok", "provider": provider.value, "config": llm_status()}
    except ValueError:
        return {"error": f"Unknown provider: {request.provider}. Use 'groq' or 'gemini'."}

class SetAgentProviderRequest(BaseModel):
    agent: str       # "vision", "stylist", "compliance", "sourcing", "memory"
    provider: str    # "groq" or "gemini"
    model: Optional[str] = None  # optional model override

@app.post("/llm/agent-provider")
async def switch_agent_provider(request: SetAgentProviderRequest):
    """Override the LLM provider for a specific agent."""
    valid_agents = ["vision", "stylist", "compliance", "sourcing", "memory"]
    if request.agent not in valid_agents:
        return {"error": f"Unknown agent: {request.agent}. Valid: {valid_agents}"}
    try:
        provider = LLMProvider(request.provider.lower())
        available = get_available_providers()
        if not available[provider.value]["available"]:
            return {
                "error": f"API key not set for {provider.value}. "
                         f"Set {available[provider.value]['env_var']} in your environment."
            }
        set_agent_provider(request.agent, provider, request.model)
        return {"status": "ok", "agent": request.agent, "provider": provider.value, "config": llm_status()}
    except ValueError:
        return {"error": f"Unknown provider: {request.provider}. Use 'groq' or 'gemini'."}

# ============================================================================
#  PROJECT ENDPOINTS
# ============================================================================

@app.post("/project/upload-plan")
async def upload_plan(file: UploadFile = File(...), project_id: str = Form(None)):
    if not project_id:
        project_id = str(uuid.uuid4())
        
    contents = await file.read()
    
    initial_state = {
        "project": BIMProjectState(project_id=project_id, name="New Project"),
        "messages": [],
        "next_agent": "vision",
        "plan_image": contents,
        "user_message": None,
        "extraction_results": None,
        "long_term_memory": memory_manager.load_memory("default_user").model_dump(),
        "semantic_knowledge": STATIC_KNOWLEDGE
    }
    
    final_state = await app_graph.ainvoke(initial_state)
    
    return {
        "project_id": project_id,
        "bim_state": final_state["project"].model_dump(),
        "vision_notes": final_state["extraction_results"].get("notes") if final_state.get("extraction_results") else "Plan processed."
    }

class ChatRequest(BaseModel):
    project_id: str
    message: str
    current_state: BIMProjectState

@app.post("/project/chat")
async def chat_with_agents(request: ChatRequest):
    project = request.current_state
    
    # Run the orchestrator graph with the user message
    initial_state = {
        "project": project,
        "messages": [{"role": "user", "content": request.message}],
        "next_agent": "vision",
        "plan_image": None,
        "user_message": request.message,
        "extraction_results": None,
        "long_term_memory": memory_manager.load_memory("default_user").model_dump(),
        "semantic_knowledge": STATIC_KNOWLEDGE
    }
    
    final_state = await app_graph.ainvoke(initial_state)
    
    # 3. Extract the last agent update
    logs = final_state.get("messages", [])
    last_msg = logs[-1] if logs else {"content": "Processing complete."}
    agent_response = last_msg.get("content") if isinstance(last_msg, dict) else last_msg

    return {
        "bim_state": final_state["project"].model_dump(),
        "agent_response": agent_response
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=25678)

