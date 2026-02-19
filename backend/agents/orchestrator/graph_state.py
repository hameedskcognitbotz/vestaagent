from typing import TypedDict, Annotated, List, Union, Dict, Any, Optional
from backend.core.bim_state import BIMProjectState
import operator

class AgentState(TypedDict):
    # The BIM state is the primary memory
    project: BIMProjectState
    
    # Message history for the agentic conversation
    messages: Annotated[List[Dict[str, Any]], operator.add]
    
    # Cognitive Memory Layers
    long_term_memory: Optional[Dict[str, Any]]  # Episodic & Semantic
    semantic_knowledge: Optional[Dict[str, Any]] # Building codes, Material facts
    
    # Tracking current step/focus
    next_agent: str
    
    # User intent
    user_message: Optional[str]
    
    # Loop prevention
    loop_count: int = 0
    
    # Raw data from vision
    plan_image: Optional[bytes]
    extraction_results: Optional[Dict[str, Any]]
