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

memory_manager = MemoryManager()

# Helper: Context Resolver
def resolve_context_references(message: str, project: BIMProjectState) -> str:
    """Detects @ references and appends relevant context data to the prompt."""
    if not message: return message
    
    context_injection = "\n\n[VESTACODE CONTEXT REFERENCES]:"
    found_ref = False

    if "@Code" in message:
        found_ref = True
        codes = STATIC_KNOWLEDGE.get("building_codes", {})
        context_injection += f"\n- @Code: Building Regulations Active: {json.dumps(codes)}"
    
    if "@Budget" in message:
        found_ref = True
        context_injection += f"\n- @Budget: Current Total: ${project.budget_total:.2f}. Constraints: Maximize value/cost ratio."
    
    if "@FloorPlan" in message:
        found_ref = True
        wall_count = len([e for e in project.elements if e.type == ObjectType.WALL])
        context_injection += f"\n- @FloorPlan: Existing geometry contains {wall_count} walls. Focus on structural alignment."
        
    if "@Style" in message:
        found_ref = True
        style = project.style_profile or {"theme": "Japandi Modern"}
        context_injection += f"\n- @Style: Active Style DNA: {json.dumps(style)}"

    return message + (context_injection if found_ref else "")

# Define the Nodes
async def vision_node(state: AgentState):
    print("--- 🔍 VISION: ANALYZING/REFINING STRUCTURE ---")
    vision = VisionAgent()
    image = state.get("plan_image")
    user_msg = state.get("user_message")
    project = state["project"]

    # Resolve @refs early
    enriched_msg = resolve_context_references(user_msg, project)

    try:
        if image:
            # Initial upload
            extraction = await vision.process_plan(image)
            elements = map_extraction_to_bim(extraction)
            project.elements.extend(elements)
        elif enriched_msg and any(k in enriched_msg.lower() or "@" in enriched_msg for k in ["wall", "room", "door", "structure", "move", "remove"]):
            # Structural refinement via chat
            extraction = await vision.refine_structure(project, enriched_msg)
            elements = map_extraction_to_bim(extraction)
            # Clear old walls before adding refined ones
            project.elements = [e for e in project.elements if e.type != ObjectType.WALL]
            project.elements.extend(elements)
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
            "next_agent": END, # Stop the pipeline if we can't extract geometry
            "messages": [{"role": "assistant", "content": f"[ERROR]: {str(e)}"}]
        }

async def stylist_node(state: AgentState):
    print("--- 🛋️ STYLIST: DESIGNING INTERIOR ---")
    stylist = StylistAgent()
    project = state["project"]
    style_profile = project.style_profile or {"theme": "Japandi Modern"}
    
    # Inject Memory Layer
    memory = state.get("long_term_memory")
    user_msg = resolve_context_references(state.get("user_message"), project)
    
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
    
    # Inject Knowledge Layer (Building Codes)
    knowledge = state.get("semantic_knowledge")
    user_msg = state.get("user_message")
    
    # If @Code is mentioned, ensure compliance agent is extra strict
    if user_msg and "@Code" in user_msg:
        print("   -> Explicit @Code reference detected. Running deep audit.")
    
    report = await compliance.check_compliance(project, knowledge=knowledge)
    updated_project = process_compliance_node(project, report)
    return {
        "project": updated_project, 
        "next_agent": "sourcing", 
        "messages": [{"role": "assistant", "content": f"[Compliance]: {report.summary}"}]
    }

async def sourcing_node(state: AgentState):
    print("--- 🛒 SOURCING: FINDING REAL PRODUCTS ---")
    sourcing = SourcingAgent()
    project = state["project"]
    
    # Inject Knowledge Layer (Material Science)
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

workflow.add_node("vision", vision_node)
workflow.add_node("stylist", stylist_node)
workflow.add_node("spatial_validation", spatial_validation_node)
workflow.add_node("compliance", compliance_node)
workflow.add_node("sourcing", sourcing_node)
workflow.add_node("memory_refinery", memory_refinery_node)

workflow.set_entry_point("vision")

workflow.add_edge("vision", "stylist")
workflow.add_edge("stylist", "spatial_validation")
workflow.add_edge("spatial_validation", "compliance")
workflow.add_edge("compliance", "sourcing")
workflow.add_edge("sourcing", "memory_refinery")
workflow.add_edge("memory_refinery", END)

app_graph = workflow.compile()
