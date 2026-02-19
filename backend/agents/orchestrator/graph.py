from langgraph.graph import StateGraph, END
from backend.agents.orchestrator.graph_state import AgentState
from backend.agents.vision.agent import VisionAgent, map_extraction_to_bim
from backend.agents.stylist.agent import StylistAgent, apply_design_to_bim
from backend.agents.compliance.agent import ComplianceAgent, process_compliance_node
from backend.agents.sourcing.agent import SourcingAgent, process_sourcing_node
from backend.agents.memory_refinery.agent import MemoryRefineryAgent
from backend.core.memory import MemoryManager, UserPreference, EpisodicMemory
from backend.core.bim_state import BIMProjectState, ObjectType
from backend.core.spatial_engine import run_spatial_analysis
import uuid
import json
import os

# Load Static Knowledge (The Designer's Encyclopedia)
KB_PATH = "backend/data/knowledge_base.json"
if os.path.exists(KB_PATH):
    with open(KB_PATH, "r") as f:
        STATIC_KNOWLEDGE = json.load(f)
else:
    STATIC_KNOWLEDGE = {"building_codes": {}, "material_science": {}}

from backend.agents.context.agent import ContextAgent

memory_manager = MemoryManager()
context_agent = ContextAgent()

# Define the Nodes
async def context_enrichment_node(state: AgentState):
    print("--- 🧠 CONTEXT: RESOLVING REFERENCES ---")
    project = state["project"]
    user_msg = state.get("user_message") or ""
    
    # Run the new ContextAgent
    result = await context_agent.run(project, user_msg)
    
    # Append the enriched context to the user message for downstream agents
    enriched_msg = user_msg + result["context_str"]
    
    # Update active selection if resolved
    if result["resolution"]["target_elements"]:
        project.active_selection = [e.id for e in result["resolution"]["target_elements"]]
        
    return {
        "project": project,
        "user_message": enriched_msg,
        "next_agent": "vision" # Default next step, though graph logic controls flow
    }

async def vision_node(state: AgentState):
    print("--- 🔍 VISION: ANALYZING/REFINING STRUCTURE ---")
    vision = VisionAgent()
    image = state.get("plan_image")
    # Message is already enriched by context node
    enriched_msg = state.get("user_message") 
    project = state["project"]

    try:
        if image:
            # Initial upload
            extraction = await vision.process_plan(image)
            elements, rooms = map_extraction_to_bim(extraction)
            project.elements.extend(elements)
            project.rooms = rooms # Overwrite rooms on new upload
        elif enriched_msg and any(k in enriched_msg.lower() or "@" in enriched_msg for k in ["wall", "room", "door", "structure", "move", "remove"]):
            # Structural refinement via chat
            extraction = await vision.refine_structure(project, enriched_msg)
            elements, rooms = map_extraction_to_bim(extraction)
            # Clear old walls before adding refined ones
            project.elements = [e for e in project.elements if e.type != ObjectType.WALL]
            project.elements.extend(elements)
            # Update rooms if any returned
            if rooms:
                project.rooms = rooms
        else:
            # Skip vision for non-structural messages
            return {"project": project, "next_agent": "stylist"}

        return {
            "project": project, 
            "next_agent": "stylist", 
            "extraction_results": extraction.model_dump(),
            "messages": [{"role": "assistant", "content": f"[Architect]: {extraction.notes}"}]
        }
    except Exception as e:
        print(f"Vision Node Error: {e}")
        return {
            "project": project,
            "next_agent": END, 
            "messages": [{"role": "assistant", "content": f"[ERROR]: {str(e)}"}]
        }

async def stylist_node(state: AgentState):
    print("--- 🛋️ STYLIST: DESIGNING INTERIOR ---")
    stylist = StylistAgent()
    project = state["project"]
    style_profile = project.style_profile or {"theme": "Japandi Modern"}
    
    memory = state.get("long_term_memory")
    user_msg = state.get("user_message")
    
    try:
        design = await stylist.generate_layout(project, style_profile, user_message=user_msg, memory=memory)
        updated_project = apply_design_to_bim(design, project)
        return {
            "project": updated_project, 
            "next_agent": "spatial_validation",
            "messages": [{"role": "assistant", "content": f"[Stylist]: {design.design_dna_summary}"}]
        }
    except Exception as e:
        print(f"Stylist Node Error: {e}")
        return {
            "project": project,
            "next_agent": "spatial_validation",
            "messages": [{"role": "assistant", "content": f"[ERROR]: {str(e)}"}]
        }

async def spatial_validation_node(state: AgentState):
    """Deterministic geometry validation — no LLM calls."""
    print("--- 📐 SPATIAL: VALIDATING GEOMETRY ---")
    project = state["project"]
    
    try:
        spatial_report = run_spatial_analysis(project, auto_fix=True)
        
        # Log the spatial report into the BIM state
        project.compliance_logs.append({
            "timestamp": "now",
            "agent": "spatial_engine",
            "flow_score": spatial_report["flow_score"],
            "collision_count": spatial_report["collision_count"],
            "clearance_violations": spatial_report["clearance_violations"],
            "blocked_paths": spatial_report["blocked_paths"],
            "density_ratio": spatial_report["density_ratio"],
            "corrections_applied": spatial_report["corrections_applied"],
            "issues": spatial_report["issues"]
        })
        
        score = spatial_report["flow_score"]
        fixes = spatial_report["corrections_applied"]
        msg = f"Flow Score: {score}/100. {fixes} auto-corrections applied."
        
        return {
            "project": project,
            "next_agent": "compliance",
            "messages": [{"role": "assistant", "content": f"[Spatial Engine]: {msg}"}]
        }
    except Exception as e:
        print(f"Spatial Engine Error: {e}")
        return {
            "project": project,
            "next_agent": "compliance",
            "messages": [{"role": "assistant", "content": f"[Spatial Engine]: Skipped due to error: {e}"}]
        }

async def compliance_node(state: AgentState):
    print("--- 🛡️ COMPLIANCE: VERIFYING REGULATIONS ---")
    compliance = ComplianceAgent()
    project = state["project"]
    knowledge = state.get("semantic_knowledge")
    
    report = await compliance.check_compliance(project, knowledge=knowledge)
    updated_project = process_compliance_node(project, report)
    
    # Decide next step based on compliance
    if report.is_compliant:
        next_step = "sourcing"
        msg = f"[Compliance]: Passed. {report.summary}"
    else:
        # Check loop count to avoid infinite loops
        current_loops = state.get("loop_count", 0)
        if current_loops < 3:
            print(f"   -> Compliance Failed. Looping back to Stylist (Attempt {current_loops+1}/3)")
            next_step = "stylist"
            msg = f"[Compliance]: Rejected. {report.summary}. Requesting revision."
        else:
            print("   -> Max loops reached. Proceeding with warnings.")
            next_step = "sourcing"
            msg = f"[Compliance]: Failed but proceeding (Max Persistence). {report.summary}"
            
    return {
        "project": updated_project, 
        "next_agent": next_step, 
        "messages": [{"role": "assistant", "content": msg}],
        "loop_count": state.get("loop_count", 0) + 1
    }

async def sourcing_node(state: AgentState):
    print("--- 🛒 SOURCING: FINDING REAL PRODUCTS ---")
    sourcing = SourcingAgent()
    project = state["project"]
    knowledge = state.get("semantic_knowledge")
    
    report = await sourcing.search_products(project, knowledge=knowledge)
    updated_project = process_sourcing_node(project, report)
    return {
        "project": updated_project, 
        "next_agent": "memory_refinery", 
        "messages": [{"role": "assistant", "content": f"[Sourcing]: Found {len(report.items)} products. Total Budget: ${report.total_cart_value:.2f}"}]
    }

async def memory_refinery_node(state: AgentState):
    print("--- 🧠 MEMORY: REFINING USER COGNITION ---")
    refinery = MemoryRefineryAgent()
    messages = state["messages"]
    project = state["project"]
    
    # 1. Extract new facts via LLM
    new_facts = await refinery.refine_memory(messages)
    
    # 2. Persist to Long-Term Memory
    user_id = "default_user" # In production, pull from auth/project
    memory = memory_manager.load_memory(user_id)
    
    for p in new_facts.get("preferences", []):
        memory.preferences.append(UserPreference(**p))
    for e in new_facts.get("events", []):
        memory.history.append(EpisodicMemory(timestamp="now", **e))
        
    memory_manager.save_memory(memory)
    
    return {
        "long_term_memory": memory.model_dump(),
        "next_agent": "human"
    }

# Define the Graph
workflow = StateGraph(AgentState)

workflow.add_node("context_enrichment", context_enrichment_node)
workflow.add_node("vision", vision_node)
workflow.add_node("stylist", stylist_node)
workflow.add_node("spatial_validation", spatial_validation_node)
workflow.add_node("compliance", compliance_node)
workflow.add_node("sourcing", sourcing_node)
workflow.add_node("memory_refinery", memory_refinery_node)

workflow.set_entry_point("context_enrichment")

workflow.add_edge("context_enrichment", "vision")
workflow.add_edge("vision", "stylist")
workflow.add_edge("stylist", "spatial_validation")
workflow.add_edge("spatial_validation", "compliance")

# Conditional Edge for Compliance Loop
def should_continue_compliance(state: AgentState):
    last_msg = state["messages"][-1]["content"] if state["messages"] else ""
    if "Rejected" in last_msg and state.get("loop_count", 0) <= 3:
        return "retry"
    return "proceed"

workflow.add_conditional_edges(
    "compliance",
    should_continue_compliance,
    {
        "retry": "stylist",
        "proceed": "sourcing"
    }
)

workflow.add_edge("sourcing", "memory_refinery")
workflow.add_edge("memory_refinery", END)

app_graph = workflow.compile()
