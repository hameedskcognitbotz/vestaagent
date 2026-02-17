from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from backend.core.bim_state import Vector3, ObjectType

class FurnitureRecommendation(BaseModel):
    item_type: str  # e.g., "sofa", "dining_table", "bed"
    style_tag: str  # e.g., "Mid-Century Modern", "Japandi"
    position: Vector3
    rotation: Vector3
    dimensions: Vector3
    reasoning: str  # Why did the agent place it here? (Ergonomic rationale)
    estimated_cost: float

class MaterialPalette(BaseModel):
    wall_color: str
    floor_material: str
    accent_material: Optional[str] = None
    lighting_mood: str # e.g., "Warm Ambient", "High Contrast Gallery"

class StylistDesign(BaseModel):
    recommendations: List[FurnitureRecommendation] = Field(default_factory=list)
    palette: MaterialPalette
    total_estimated_budget: float = 0.0
    design_dna_summary: str = "A customized design layout."
