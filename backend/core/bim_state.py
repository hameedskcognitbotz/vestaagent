from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

class ObjectType(str, Enum):
    WALL = "wall"
    DOOR = "door"
    WINDOW = "window"
    FURNITURE = "furniture"
    ROOM = "room"
    DECOR = "decor"
    LIGHTING = "lighting"

class Vector3(BaseModel):
    x: float
    y: float
    z: float

class BIMElement(BaseModel):
    id: str
    type: ObjectType
    position: Vector3
    rotation: Vector3
    dimensions: Vector3
    model_url: Optional[str] = None  # URL to .glb/.gltf asset
    material_properties: Dict[str, Any] = Field(default_factory=dict) # PBR props: roughness, metalness, generic texture
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Room(BaseModel):
    id: str
    name: str
    polygon: List[Tuple[float, float]] = Field(default_factory=list) # 2D coordinates of the room perimeter (x, z)
    elements: List[str] = Field(default_factory=list)   # IDs of elements in this room

class BIMElementDelta(BaseModel):
    timestamp: str
    author: str  # "user", "stylist_agent", etc.
    description: str
    added_elements: List[BIMElement] = Field(default_factory=list)
    modified_elements: List[Dict[str, Any]] = Field(default_factory=list) # {id, field, old_value, new_value}
    removed_element_ids: List[str] = Field(default_factory=list)

class SpatialRule(BaseModel):
    id: str
    description: str
    target_ids: List[str] # Elements this rule applies to
    rule_type: str # "clearance", "structural", "budget"
    parameters: Dict[str, Any] # e.g. {"min_distance": 36}
    active: bool = True

class BIMProjectState(BaseModel):
    project_id: str
    name: str
    version: int = 1
    elements: List[BIMElement] = Field(default_factory=list)
    rooms: List[Room] = Field(default_factory=list)
    style_profile: Dict[str, Any] = Field(default_factory=dict)
    compliance_logs: List[Dict[str, Any]] = Field(default_factory=list)
    budget_total: float = 0.0
    
    # Cursor-like features
    history: List[BIMElementDelta] = Field(default_factory=list)
    active_selection: List[str] = Field(default_factory=list)
    constraints: List[SpatialRule] = Field(default_factory=list)
    semantic_context: str = "" # Current "Design Intent" summary

    class Config:
        schema_extra = {
            "example": {
                "project_id": "p001",
                "name": "Luxury Penthouse",
                "elements": [],
                "rooms": [],
                "style_profile": {"theme": "Contemporary Minimalist"}
            }
        }
