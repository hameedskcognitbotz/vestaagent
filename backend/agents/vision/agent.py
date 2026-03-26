import base64
import os
from typing import Dict, Any, List, Optional, Tuple
from langchain_core.messages import HumanMessage
from backend.core.llm_factory import get_llm
from backend.agents.vision.schema import VisionExtraction, DetectedWall, DetectedOpening
from backend.core.bim_state import BIMProjectState, BIMElement, ObjectType, Vector3
import json
import uuid

VISION_SYSTEM_PROMPT = """
You are the 'Vision Agent' for VestaCode. Your role is to interpret 2D floor plans with 
architectural precision.

CRITICAL EXTRACTION RULES:

1. WALLS — Extract ALL walls:
   - Outer perimeter walls (thick dark lines forming the building boundary)
   - Internal partition walls (thinner lines dividing rooms)
   - Every room visible in the plan MUST have its walls defined
   - Use real-world coordinates in meters. Standard residential scale: outer walls ~0.2m thick, internal ~0.1m

2. DOORS — Extract ALL doors:
   - Look for ARC/SWING marks — quarter-circle arcs show door swing direction
   - Look for GAPS in walls where a door would be placed
   - Door widths: standard interior ~0.8m, bathroom ~0.7m, entry/exterior ~0.9m
   - Set type to "door" for type
   - Position should be at the center of the door opening

3. WINDOWS — Extract ALL windows:
   - Look for PARALLEL LINES on outer walls (double lines indicate glass)
   - Look for HATCHED or CROSS-HATCHED areas on outer walls  
   - Windows are typically 1.0-1.5m wide
   - Set type to "window" for each
   - Position should be at the center of the window

4. ROOMS — Identify room boundaries (polygons):
   - For each room (Living Room, Bedroom, Kitchen, Bath), define a CLOSED POLYGON of coordinates.
   - The polygon should follow the inner face of the walls.
   - List the room Name.

Return ONLY a JSON object matching this schema:
{
  "walls": [{"start": [0,0], "end": [5,0], "thickness": 0.15, "is_load_bearing": true}],
  "openings": [
    {"type": "door", "position": [2,0], "width": 0.9, "rotation": 0},
    {"type": "window", "position": [3,5], "width": 1.2, "rotation": 0}
  ],
  "rooms": [
    {"name": "Master Bedroom", "polygon": [[0,0], [5,0], [5,5], [0,5]]}
  ],
  "scale_ratio": 1.0,
  "confidence_score": 0.9,
  "notes": "Rooms found: Living Room, Master Bedroom, Kitchen, Bath 1, Bath 2, Office. Total: 6 rooms."
}

IMPORTANT:
- You MUST extract at least 1 door and 1 window from any standard residential floor plan.
- Strictly ensure thickness and scores are numeric.
- If you see door swing arcs (quarter circles), those are DOORS — extract them.
- If you see parallel lines on outer walls, those are WINDOWS — extract them.
- Ensure room polygons are closed loops (last point connects to first).
"""

class VisionAgent:
    def __init__(self, model_name: str = None):
        """
        Supports two modes:
        1. LLM (default): Uses Groq/Gemini for analysis.
        2. Custom: Uses locally trained YOLO model (set VESTA_VISION_MODEL=custom).
        """
        self.use_custom = os.environ.get("VESTA_VISION_MODEL", "llm") == "custom"
        self.custom_agent = None
        
        if self.use_custom:
            try:
                from backend.agents.vision.custom_agent import CustomVisionAgent
                model_path = os.environ.get("VESTA_VISION_MODEL_PATH", "backend/models/floorplan_best.pt")
                self.custom_agent = CustomVisionAgent(model_path)
                print(f"🤖 Vision Agent using CUSTOM YOLO MODEL: {model_path}")
            except Exception as e:
                print(f"⚠️ Failed to load CustomVisionAgent: {e}. Falling back to LLM.")
                self.use_custom = False
        
        if not self.use_custom:
            # Uses centralized LLM factory — supports Groq + Gemini
            self.llm = get_llm(agent_name="vision", model=model_name, temperature=0.1)
            provider = "Gemini" if os.getenv("GOOGLE_API_KEY") else "Groq" if os.getenv("GROQ_API_KEY") else "None"
            print(f"🧠 Vision Agent using LLM Provider: {provider}")

    async def refine_structure(self, project: BIMProjectState, user_message: str) -> VisionExtraction:
        """Refines the existing structure based on user text commands."""
        if self.use_custom and self.custom_agent:
            return await self.custom_agent.refine_structure(project, user_message)
            
        wall_summary = [
            {"id": e.id, "start": [e.position.x - e.dimensions.x/2, e.position.z], "end": [e.position.x + e.dimensions.x/2, e.position.z]}
            for e in project.elements if e.type == ObjectType.WALL
        ]
        
        prompt = f"""
        Current Architectural State: {json.dumps(wall_summary, indent=2)}
        User Instruction: {user_message}
        
        Task: Modify the structure as requested. Return ONLY a valid JSON matching the schema.
        You can rename or move walls, change thicknesses, etc.
        """
        
        response = await self.llm.ainvoke([
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ])
        
        # Parse response (using same robust logic)
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[-1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[-1].split("```")[0].strip()
            
            data = json.loads(content)
            if isinstance(data, dict) and len(data) == 1 and list(data.keys())[0] in ["vision_extraction", "data", "result"]:
                data = list(data.values())[0]
            if "scale" in data and "scale_ratio" not in data:
                data["scale_ratio"] = data["scale"]
                
            return VisionExtraction(**data)
        except Exception as e:
            print(f"Vision refinement parsing failed: {e}. Data: {content[:200]}")
            # Mock extraction for fallback testing
            from backend.agents.vision.schema import DetectedWall
            return VisionExtraction(walls=[DetectedWall(start=(0,0), end=(5,0))], confidence_score=0.1, notes="Refinement failed fallback.")

    async def process_plan(self, image_bytes: bytes) -> VisionExtraction:
        if self.use_custom and self.custom_agent:
            return await self.custom_agent.process_plan(image_bytes)
            
        # Detect PDF and convert to image if necessary
        is_pdf = image_bytes.startswith(b"%PDF")
        
        if is_pdf:
            import fitz
            doc = fitz.open(stream=image_bytes, filetype="pdf")
            page = doc.load_page(0)  # first page
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # upscale for better quality
            image_bytes = pix.tobytes("jpg")
            doc.close()

        # 1. Encode image to base64
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        
        # 2. Build messages — compatible with both Groq and Gemini
        from langchain_core.messages import SystemMessage
        
        system_msg = SystemMessage(content=VISION_SYSTEM_PROMPT)
        human_msg = HumanMessage(
            content=[
                {"type": "text", "text": "Analyze this floor plan and extract the geometry JSON including room polygons."},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                },
            ]
        )

        # 3. Call model
        response = await self.llm.ainvoke([system_msg, human_msg])
        
        # Parse response with robust extraction
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[-1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[-1].split("```")[0].strip()
            
            # CRITICAL: Strip architectural comments and clean JSON for model hallucinations
            import re
            # Strip python-style comments (# ...)
            content = re.sub(r'#.*$', '', content, flags=re.MULTILINE)
            # Strip C-style single line comments (// ...)
            content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
            # Strip C-style multi-line comments (/* ... */)
            content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
            # Strip trailing commas in lists/dicts
            content = re.sub(r',\s*([\]}])', r'\1', content)
            
            data = json.loads(content)
            
            # Handle potential wrapper keys
            if isinstance(data, dict) and len(data) == 1 and list(data.keys())[0] in ["vision_extraction", "data", "result"]:
                data = list(data.values())[0]
            
            # Handle aliases
            if "scale" in data and "scale_ratio" not in data:
                data["scale_ratio"] = data["scale"]

             # CRITICAL FIX: If we have walls, return them even if Pydantic is strict about other fields
            if "walls" in data and isinstance(data["walls"], list) and len(data["walls"]) > 0:
                print(f"SUCCESS: Extracted {len(data['walls'])} walls from Vision Agent.")
                # Ensure fields exist
                if "openings" not in data: data["openings"] = []
                if "rooms" not in data: data["rooms"] = []
                if "scale_ratio" not in data: data["scale_ratio"] = 1.0
                if "confidence_score" not in data: data["confidence_score"] = 0.8
                return VisionExtraction(**data)
                
            return VisionExtraction(**data)
        except Exception as e:
            print(f"Vision parsing error: {e}")
            print(f"RAW CONTENT WAS: {content}")
            
            raise ValueError(f"Spatial Extraction Failed: {str(e)}. The model could not interpret this floor plan geometry accurately.")


def map_extraction_to_bim(extraction: VisionExtraction) -> Tuple[List[BIMElement], List[Any]]:
    """
    Converts 2D detection into 3D BIM elements (initial extrusion) AND Room objects.
    Returns: (elements, rooms)
    """
    elements = []
    
    # Process Walls
    for i, w in enumerate(extraction.walls):
        dx = w.end[0] - w.start[0]
        dy = w.end[1] - w.start[1]
        length = (dx**2 + dy**2)**0.5
        
        center_x = (w.start[0] + w.end[0]) / 2
        center_y = (w.start[1] + w.end[1]) / 2
        
        import math
        angle = math.atan2(dy, dx)
        
        elements.append(BIMElement(
            id=f"wall-{uuid.uuid4().hex[:6]}",
            type=ObjectType.WALL,
            position=Vector3(x=center_x, y=1.4, z=center_y),
            rotation=Vector3(x=0, y=angle, z=0),
            dimensions=Vector3(x=length, y=2.8, z=w.thickness),
            metadata={"load_bearing": w.is_load_bearing}
        ))
    
    # Process Openings (Doors & Windows)
    for i, o in enumerate(extraction.openings):
        o_type = o.type.lower().strip()
        if o_type in ["door", "entry_door", "exterior_door", "interior_door"]:
            obj_type = ObjectType.DOOR
            height = 2.1
            y_pos = height / 2
        elif o_type in ["window", "picture_window", "casement_window"]:
            obj_type = ObjectType.WINDOW
            height = 1.2
            y_pos = 1.5  # windows sit higher on the wall
        else:
            obj_type = ObjectType.DOOR  # default to door
            height = 2.1
            y_pos = height / 2
        
        elements.append(BIMElement(
            id=f"{o_type}-{uuid.uuid4().hex[:6]}",
            type=obj_type,
            position=Vector3(x=o.position[0], y=y_pos, z=o.position[1]),
            rotation=Vector3(x=0, y=o.rotation, z=0),
            dimensions=Vector3(x=o.width, y=height, z=0.1),
            metadata={"opening_type": o.type}
        ))
        
    # Process Rooms
    from backend.core.bim_state import Room
    rooms = []
    for r in extraction.rooms:
        rooms.append(Room(
            id=f"room-{uuid.uuid4().hex[:6]}",
            name=r.name,
            polygon=r.polygon,
            elements=[]
        ))
    
    return elements, rooms


def count_rooms_from_notes(extraction: VisionExtraction) -> int:
    """Extract room count from vision notes for Stylist to use."""
    notes = extraction.notes or ""
    import re
    # Look for "Total: N rooms" pattern
    match = re.search(r'[Tt]otal[:\s]+(\d+)\s*rooms?', notes)
    if match:
        return int(match.group(1))
    # Count room names mentioned
    room_keywords = ['bedroom', 'living', 'kitchen', 'bath', 'office', 'dining', 
                     'balcony', 'pantry', 'closet', 'laundry', 'garage', 'foyer',
                     'study', 'library', 'nursery', 'guest', 'utility']
    count = sum(1 for kw in room_keywords if kw.lower() in notes.lower())
    return max(count, 1)
