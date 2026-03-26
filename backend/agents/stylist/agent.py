import json
import uuid
import re
from typing import List, Dict, Any, Optional
from langchain_groq import ChatGroq
from backend.core.llm_factory import get_llm
from backend.agents.stylist.schema import StylistDesign, FurnitureRecommendation, MaterialPalette
from backend.core.bim_state import BIMProjectState, BIMElement, ObjectType, Vector3

STYLIST_SYSTEM_PROMPT = """
You are the Lead Interior Architect for VestaCode, a "Cursor for Spatial Design" platform.
Your goal is to transform 2D spatial coordinates into a high-fidelity 3D BIM state.

CRITICAL DESIGN RULES:

1. **Analyze Reference:** Use the `@Style` profile and `@Memory` to identify preferred materials (e.g., 'Scandinavian Oak', 'Matte Black Steel').
2. **Object Matching:** For every room, select specific furniture types that fit the function.
   - Bedroom: Bed (King/Queen), Nightstands, Wardrobe.
   - Living: Sofa (L-Shape/Sectional), Coffee Table, TV Unit.
   - Dining: Dining Table, Chairs (4-6).
   - Kitchen: Cabinets, Island (if space allows).
3. **Smart Alignment:** 
   - Ensure the back of seating faces the wall.
   - Leave a minimum 36" (0.9m) clearance for walkways (Reference: `Compliance_Linter`).
   - Center major pieces (Beds, Dining Tables) within their room polygons.
4. **Custom Millwork (SketchUp Level Detail):**
   - **Integrated Study:** If a bedroom wall has a window, design a "Study Niche" intersecting the wardrobe.
   - **Built-ins:** Prefer floor-to-ceiling wardrobes over standalone units for a premium look.
   - **Dimensions:** Use precise millimeters for joinery (e.g., depth 600mm for wardrobes).
5. **SketchUp Compatibility (3D Warehouse):**
   - Use standard component names found in the SketchUp 3D Warehouse (e.g., "Eames Lounge Chair & Ottoman", "IKEA Billy Bookcase").
   - This allows automated replacement with high-fidelity models.
6. **Constraint Logic:** 
   - You MUST respect the `Room Polygons` provided. 
   - If a placement violates a wall boundary found by the `Vision_Agent`, you MUST adjust the rotation or scale.
   - Do NOT place furniture in "Undefined" space.

Output:
A JSON object matching the StylistDesign schema, with detailed `item_type` names (e.g., "Custom Integrated Wardrobe", "Eames Lounge Chair").
"""

class StylistAgent:
    def __init__(self, model_name: str = None):
        self.llm = get_llm(agent_name="stylist", model=model_name, temperature=0.2)

    async def generate_layout(self, project: BIMProjectState, style_profile: Dict[str, Any], user_message: Optional[str] = None, memory: Optional[Dict[str, Any]] = None) -> StylistDesign:
        # 1. Prepare context for the LLM
        wall_summary = [
            f"Wall {e.id}: Position({e.position.x}, {e.position.z}), Length: {e.dimensions.x}" 
            for e in project.elements if e.type == ObjectType.WALL
        ]
        
        door_summary = [
            f"Door {e.id}: Position({e.position.x}, {e.position.z}), Width: {e.dimensions.x}"
            for e in project.elements if e.type == ObjectType.DOOR
        ]
        
        window_summary = [
            f"Window {e.id}: Position({e.position.x}, {e.position.z}), Width: {e.dimensions.x}"
            for e in project.elements if e.type == ObjectType.WINDOW
        ]
        
        room_summary = [
            f"Room {r.name}: Polygon Points ({len(r.polygon)})"
            for r in project.rooms
        ]
        
        furniture_summary = [
            f"Furniture {e.id}: {e.metadata.get('item_type')} at ({e.position.x}, {e.position.z})"
            for e in project.elements if e.type == ObjectType.FURNITURE
        ]

        # Dynamic furniture count: estimate rooms from wall count
        n_walls = len(wall_summary)
        n_doors = len(door_summary)
        # Heuristic: rooms ≈ (interior walls) / 2, minimum 2
        estimated_rooms = len(project.rooms) if project.rooms else max(n_doors, max(n_walls // 3, 2))
        min_furniture = max(estimated_rooms * 2, 5)  # At least 2 items per room, minimum 5

        # Extract relevant memory
        preferences = memory.get("preferences", []) if memory else []
        history = memory.get("history", []) if memory else []

        prompt = f"""
        BIM State Context:
        Walls ({len(wall_summary)}): {json.dumps(wall_summary, indent=2)}
        Doors ({len(door_summary)}): {json.dumps(door_summary, indent=2)}
        Windows ({len(window_summary)}): {json.dumps(window_summary, indent=2)}
        Rooms ({len(room_summary)}): {json.dumps(room_summary, indent=2)} (Use these polygons as containers!)
        Existing Furniture: {json.dumps(furniture_summary, indent=2)}
        
        Client Preferences & History:
        - Preferences: {json.dumps([p for p in preferences], indent=2)}
        - Past Decisions: {json.dumps([h for h in history[-3:]], indent=2)} 
        
        Style Profile:
        {json.dumps(style_profile, indent=2)}
        
        User Request/Feedback: {user_message if user_message else "Generate an initial optimal layout."}
        
        Task: Design the interior layout. Return a valid JSON with this EXACT structure:
        {{
          "recommendations": [
            {{
              "item_type": "Sofa",
              "position": {{"x": 3.0, "y": 0.0, "z": 2.0}},
              "dimensions": {{"x": 2.0, "y": 0.85, "z": 0.9}},
              "rotation": {{"x": 0, "y": 0, "z": 0}},
              "style_tag": "Modern",
              "reasoning": "Placed along the east wall for optimal flow.",
              "estimated_cost": 1200.0,
              "model_url": "https://assets.vestacode.ai/models/sofa_modern_01.glb",
              "material_properties": {{"finish": "Scandinavian Oak", "texture": "matte", "color": "#8B4513"}}
            }}
          ],
          "palette": {{
            "theme": "Japandi Modern",
            "wall_color": "#F5F5F0",
            "floor_material": "Light Oak Hardwood",
            "lighting_mood": "Warm Ambient"
          }}
        }}
        
        CRITICAL RULES:
        1. You MUST include at least {min_furniture} furniture items in "recommendations".
        2. Each item MUST have: "item_type", "position" (x,y,z), "dimensions" (x,y,z in meters), and a mock "model_url".
        3. Furniture must fit within the *Room Polygons*.
        4. DO NOT place furniture blocking doors or windows.
        5. For Millwork (Wardrobes/Kitchens), SPECIFY "material_properties" (e.g. Oak Veneer) to match the high-end SketchUp aesthetic.
        6. Return ONLY valid JSON.
        """

        # 2. Call LLM
        response = await self.llm.ainvoke([
            {"role": "system", "content": STYLIST_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ])

        # 3. Parse response with robust extraction
        content = response.content
        try:
            # Extract all JSON blocks
            blocks = re.findall(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if not blocks:
                # Fallback to finding anything between { }
                blocks = re.findall(r'(\{.*\})', content, re.DOTALL)
            
            data = {}
            for block in blocks:
                # Clean block
                clean_block = block
                # Strip comments
                clean_block = re.sub(r'#.*$', '', clean_block, flags=re.MULTILINE)
                clean_block = re.sub(r'//.*$', '', clean_block, flags=re.MULTILINE)
                clean_block = re.sub(r'/\*.*?\*/', '', clean_block, flags=re.DOTALL)
                # Strip trailing commas
                clean_block = re.sub(r',\s*([\]}])', r'\1', clean_block)
                # Strip non-printable control characters
                clean_block = "".join(c for c in clean_block if ord(c) >= 32 or c in "\n\r\t")
                
                try:
                    temp_data = json.loads(clean_block, strict=False)
                    # Look for design keys
                    search_data = temp_data
                    if isinstance(temp_data, dict) and len(temp_data) == 1:
                         search_data = list(temp_data.values())[0]
                    
                    if isinstance(search_data, dict) and any(k in search_data for k in ["layout", "recommendations", "rooms", "furniture"]):
                        data = temp_data
                        break
                except: continue
            
            if not data and blocks:
                try: data = json.loads(blocks[0], strict=False)
                except: pass

            if not data:
                raise ValueError("No valid design JSON found in model response.")
            
            # Handle potential wrapper keys or layout-specific keys
            if isinstance(data, dict):
                # If model wrapped everything in a single key like 'stylist_design'
                if len(data) == 1 and list(data.keys())[0] in ["stylist_design", "design", "layout", "data", "report"]:
                     data = list(data.values())[0]
                
                # If we have a 'layout' or 'rooms' key but no 'recommendations'
                if "layout" in data and "recommendations" not in data:
                    layout = data["layout"]
                    if isinstance(layout, list):
                        recommendations = []
                        for item in layout:
                            if isinstance(item, dict) and "furniture" in item:
                                recommendations.extend(item["furniture"])
                            elif isinstance(item, dict):
                                recommendations.append(item)
                        data["recommendations"] = recommendations
                    elif isinstance(layout, dict):
                        data["recommendations"] = [layout]
                    else:
                        data["recommendations"] = []
                if "rooms" in data and "recommendations" not in data:
                    rooms = data["rooms"]
                    recommendations = []
                    # Handle rooms as dict (keyed by room name)
                    if isinstance(rooms, dict):
                        rooms = list(rooms.values())
                    if isinstance(rooms, list):
                        for room in rooms:
                            if isinstance(room, dict) and "furniture" in room:
                                furn = room["furniture"]
                                if isinstance(furn, list):
                                    recommendations.extend(furn)
                                elif isinstance(furn, dict):
                                    recommendations.extend(furn.values() if all(isinstance(v, dict) for v in furn.values()) else [furn])
                            elif isinstance(room, dict):
                                recommendations.append(room)
                    data["recommendations"] = recommendations
                
                # Critical: Ensure palette exists
                if "palette" not in data:
                    data["palette"] = {
                        "wall_color": "#F5F5F0",
                        "floor_material": "Standard Oak",
                        "lighting_mood": "Warm Ambient"
                    }

                # Ensure recommendations is a list
                if "recommendations" not in data or not isinstance(data["recommendations"], list):
                    data["recommendations"] = []

                # Handle nested furniture in recommendations (some models do this)
                flat_recs = []
                for rec in data["recommendations"]:
                    if not isinstance(rec, dict): continue
                    
                    # UNROLL QUANTITY (if model sent one item with multiple positions)
                    if "quantity" in rec and isinstance(rec.get("position"), list):
                        for pos in rec["position"]:
                            new_rec = rec.copy()
                            new_rec["position"] = pos
                            del new_rec["quantity"]
                            flat_recs.append(new_rec)
                        continue

                    if "furniture" in rec and isinstance(rec["furniture"], list):
                        for f in rec["furniture"]:
                            if isinstance(f, dict):
                                flat_recs.append(f)
                    else:
                        flat_recs.append(rec)
                
                # Final pass: Ensure every rec has mandatory fields and parse string vectors
                processed_recs = []
                for f in flat_recs:
                    if not isinstance(f, dict): continue
                    
                    # Aliases
                    if "item_type" not in f and "type" in f: f["item_type"] = f.pop("type")
                    if "item_type" not in f and "name" in f: f["item_type"] = f.get("name")
                    if "item_type" not in f and "furniture_type" in f: f["item_type"] = f.get("furniture_type")
                    if "item_type" not in f and "item_name" in f: f["item_type"] = f.get("item_name")
                    if "item_type" not in f and "category" in f: f["item_type"] = f.get("category")
                    if "position" not in f and "placement" in f: f["position"] = f.pop("placement")
                    if "furniture" in f and isinstance(f["furniture"], dict):
                        f.update(f.pop("furniture"))
                    
                    # Helper for vector parsing
                    def parse_vector(val, default_val=2.0) -> Dict[str, float]:
                        if isinstance(val, dict):
                            x = float(val.get("x", default_val))
                            y = float(val.get("y", 0)) 
                            z = float(val.get("z", default_val))
                            if "y" in val and "z" not in val:
                                z = float(val["y"])
                                y = 0
                            return {"x": x, "y": y, "z": z}
                        if isinstance(val, list) and len(val) >= 2:
                            return {"x": float(val[0]), "y": 0, "z": float(val[1])}
                        if isinstance(val, str):
                            nums = re.findall(r"[-+]?\d*\.\d+|\d+", val)
                            if len(nums) >= 3:
                                return {"x": float(nums[0]), "y": float(nums[1]), "z": float(nums[2])}
                            if len(nums) == 2:
                                return {"x": float(nums[0]), "y": 0, "z": float(nums[1])}
                            if len(nums) == 1:
                                return {"x": float(nums[0]), "y": float(nums[0]), "z": float(nums[0])}
                        return {"x": default_val, "y": 0, "z": default_val}

                    f["position"] = parse_vector(f.get("position"), 2.0)
                    f["dimensions"] = parse_vector(f.get("dimensions"), 1.0)
                    f["rotation"] = parse_vector(f.get("rotation"), 0.0)
                    
                    if "item_type" not in f: f["item_type"] = "generic"
                    if "style_tag" not in f: f["style_tag"] = "Modern"
                    if "reasoning" not in f: f["reasoning"] = "Placed based on spatial optimization."
                    if "estimated_cost" not in f: f["estimated_cost"] = 500.0
                    processed_recs.append(f)

                data["recommendations"] = processed_recs

                if "design_dna_summary" not in data:
                    if "DesignDNA" in data:
                        data["design_dna_summary"] = str(data["DesignDNA"])
                    elif "summary" in data:
                        data["design_dna_summary"] = data["summary"]
                    else:
                        data["design_dna_summary"] = "AI generated layout."

            return StylistDesign(**data)
        except Exception as e:
            print(f"Stylist parsing error: {e}")
            print(f"RAW CONTENT WAS: {content}")
            raise ValueError(f"Interior Layout Generation Failed: {str(e)}. The model could not determine an optimal furniture arrangement for this space.")


def apply_design_to_bim(design: StylistDesign, project: BIMProjectState) -> BIMProjectState:
    """Updates the project state with the Stylist's recommendations."""
    # 1. Clear existing furniture to avoid duplication on re-runs/chat
    project.elements = [e for e in project.elements if e.type != ObjectType.FURNITURE]

    # 2. Add new recommendations
    for rec in design.recommendations:
        # Snap to floor: y = height/2
        safe_y = rec.dimensions.y / 2
        
        project.elements.append(BIMElement(
            id=f"furniture-{uuid.uuid4().hex[:6]}",
            type=ObjectType.FURNITURE,
            position=Vector3(x=rec.position.x, y=safe_y, z=rec.position.z),
            rotation=rec.rotation,
            dimensions=rec.dimensions,
            model_url=rec.model_url,
            material_properties=rec.material_properties or {},
            metadata={
                "item_type": rec.item_type,
                "reasoning": rec.reasoning,
                "cost": rec.estimated_cost
            }
        ))
    
    project.style_profile = design.palette.model_dump()
    project.budget_total = sum(e.metadata.get("cost", 0) for e in project.elements if e.type == ObjectType.FURNITURE)
    return project
