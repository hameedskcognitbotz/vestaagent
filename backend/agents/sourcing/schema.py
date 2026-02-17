from pydantic import BaseModel, Field
from typing import List, Optional

class SourcedProduct(BaseModel):
    element_id: str
    product_name: str
    vendor: str
    price: float
    currency: str = "USD"
    stock_status: str # "In Stock", "Out of Stock", "Lead Time: X weeks"
    product_url: str
    image_url: Optional[str] = None
    match_score: float # How well it matches the agent's initial recommendation

class SourcingReport(BaseModel):
    items: List[SourcedProduct]
    total_cart_value: float
    lead_time_summary: str
