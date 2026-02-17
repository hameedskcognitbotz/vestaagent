from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class ObjectType(str, Enum):
    WALL = "wall"
    DOOR = "door"
    WINDOW = "window"
    FURNITURE = "furniture"
    ROOM = "room"

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
    metadata: Dict[str, Any] = Field(default_factory=dict)

class Room(BaseModel):
    id: str
    name: str
    points: List[Vector3]  # Floor polygon
    elements: List[str]    # IDs of elements in this room

class BIMProjectState(BaseModel):
    project_id: str
    name: str
    version: int = 1
    elements: List[BIMElement] = Field(default_factory=list)
    rooms: List[Room] = Field(default_factory=list)
    style_profile: Dict[str, Any] = Field(default_factory=dict)
    compliance_logs: List[Dict[str, Any]] = Field(default_factory=list)
    budget_total: float = 0.0

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
