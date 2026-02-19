from pydantic import BaseModel, Field
from typing import List, Optional, Tuple

class DetectedWall(BaseModel):
    start: Tuple[float, float]
    end: Tuple[float, float]
    thickness: float = 0.15
    is_load_bearing: bool = False

class DetectedOpening(BaseModel):
    type: str = "unknown" # Allow default if missing
    position: Tuple[float, float] = (0.0, 0.0)
    width: float = 1.0
    rotation: float = 0.0

class DetectedRoom(BaseModel):
    name: str
    polygon: List[Tuple[float, float]]

class VisionExtraction(BaseModel):
    walls: List[DetectedWall]
    openings: List[DetectedOpening] = Field(default_factory=list)
    rooms: List[DetectedRoom] = Field(default_factory=list)
    scale_ratio: float = 1.0  # pixels to meters
    confidence_score: float = 0.0
    notes: Optional[str] = None
