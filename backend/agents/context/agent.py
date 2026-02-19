from typing import List, Dict, Any, Optional
from backend.core.bim_state import BIMProjectState, ObjectType, Vector3
import json

class ContextAgent:
    def __init__(self):
        # In a real scenario, this would load a knowledge graph or embeddings
        pass

    def resolve_references(self, state: BIMProjectState, message: str) -> Dict[str, Any]:
        """
        Parses the user message for @ references and resolves them to:
        1. Specific BIMElement IDs
        2. Spatial coordinates (e.g., @EastWall -> vector/plane)
        3. External Knowledge (e.g., @Code -> IBC snippets)
        """
        resolved_context = {
            "target_elements": [],
            "spatial_anchors": [],
            "knowledge_snippets": []
        }

        if not message:
            return resolved_context

        # 1. Resolve Element IDs (Simplified: exact match or partial match)
        # In production, use fuzzy matching or vector search
        words = message.split()
        for word in words:
            if word.startswith("@"):
                ref = word[1:].strip(".,?!")
                
                # Check for Element Matches
                for el in state.elements:
                    if ref.lower() in el.id.lower() or (el.metadata.get("name") and ref.lower() in el.metadata["name"].lower()):
                        resolved_context["target_elements"].append(el)
                
                # Check for Spatial Anchors (Mock logic)
                if "Wall" in ref:
                    # e.g. @EastWall -> Find wall with max X ? 
                    # For now just tagging it as a spatial intent
                    resolved_context["spatial_anchors"].append({"ref": ref, "type": "wall_relative"})

                # Check for Knowledge
                if "Code" in ref:
                    resolved_context["knowledge_snippets"].append({
                        "source": "IBC 2024",
                        "content": "Minimum corridor width is 36 inches."
                    })

        return resolved_context

    async def run(self, state: BIMProjectState, message: str) -> Dict[str, Any]:
        """
        Main entry point for the agent. Returns an enriched prompt or updated state.
        """
        resolution = self.resolve_references(state, message)
        
        # Enriched context string to append to the system prompt
        context_str = ""
        if resolution["target_elements"]:
            ids = [e.id for e in resolution["target_elements"]]
            state.active_selection = ids # Update 'Cursor' selection
            context_str += f"\n[CONTEXT] User is pointing at elements: {json.dumps([e.dict() for e in resolution['target_elements']])}"
            
        if resolution["knowledge_snippets"]:
            for k in resolution["knowledge_snippets"]:
                context_str += f"\n[CONTEXT] Relevant Regulation: {k['content']}"

        return {
            "resolution": resolution,
            "context_str": context_str
        }
