import uuid
from typing import List, Dict, Any, Optional
from backend.agents.sourcing.schema import SourcingReport, SourcedProduct
from backend.core.bim_state import BIMProjectState, ObjectType
from langchain_groq import ChatGroq
from backend.core.llm_factory import get_llm
import json
import re

SOURCING_SYSTEM_PROMPT = """
You are the 'Sourcing Agent' for VestaAgent. Your role is to match recommended 3D BIM assets 
with real-world products from our partner catalogues.

Given the catalogue and the recommended items, pick the best match for each based on style and price.
Output a valid JSON matching the SourcingReport schema.
"""

class SourcingAgent:
    def __init__(self, model_name: str = None):
        self.llm = get_llm(agent_name="sourcing", model=model_name, temperature=0)
        self.catalogue = {
            "sofa": [
                {"name": "Emery Reversible Sectional", "vendor": "West Elm", "price": 1499.0, "url": "https://westelm.com/emery"},
                {"name": "Burrard Sofa", "vendor": "Article", "price": 1199.0, "url": "https://article.com/burrard"}
            ],
            "coffee_table": [
                {"name": "Noguchi Table", "vendor": "Herman Miller", "price": 895.0, "url": "https://hermanmiller.com/noguchi"},
                {"name": "Mid-Century Table", "vendor": "West Elm", "price": 399.0, "url": "https://westelm.com/mid-century"}
            ]
        }

    async def search_products(self, project: BIMProjectState, knowledge: Optional[Dict[str, Any]] = None) -> SourcingReport:
        # 1. Prepare items to source
        items_to_source = []
        for element in project.elements:
            if element.type == ObjectType.FURNITURE:
                items_to_source.append({
                    "id": element.id,
                    "type": element.metadata.get("item_type", "generic"),
                    "description": element.metadata.get("reasoning", "")
                })

        if not items_to_source:
             return SourcingReport(items=[], total_cart_value=0.0, lead_time_summary="No items to source.")

        # 2. Call LLM for smart matching
        materials = knowledge.get("material_science", {}) if knowledge else {}

        prompt = f"""
        Catalogue: {json.dumps(self.catalogue, indent=2)}
        Items to Source: {json.dumps(items_to_source, indent=2)}
        
        Material Properties & Science:
        {json.dumps(materials, indent=2)}
        """

        try:
            clean_content = ""
            response = await self.llm.ainvoke([
                {"role": "system", "content": SOURCING_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ])
            
            import re
            clean_content = response.content
            
            # Extract all JSON blocks
            blocks = re.findall(r'```json\s*(.*?)\s*```', clean_content, re.DOTALL)
            if not blocks:
                blocks = re.findall(r'(\{.*\})', clean_content, re.DOTALL)
            
            data = {}
            for block in blocks:
                cb = block
                cb = re.sub(r'#.*$', '', cb, flags=re.MULTILINE)
                cb = re.sub(r'//.*$', '', cb, flags=re.MULTILINE)
                cb = re.sub(r'/\*.*?\*/', '', cb, flags=re.DOTALL)
                cb = re.sub(r',\s*([\]}])', r'\1', cb)
                cb = "".join(c for c in cb if ord(c) >= 32 or c in "\n\r\t")
                
                try:
                    temp_data = json.loads(cb, strict=False)
                    if isinstance(temp_data, list):
                         temp_data = {"items": temp_data}
                    if isinstance(temp_data, dict) and any(k in temp_data for k in ["items", "products", "sourcing_report"]):
                        data = temp_data
                        break
                except: continue
            
            if not data and blocks:
                try: 
                    data = json.loads(blocks[0], strict=False)
                    if isinstance(data, list): data = {"items": data}
                except: pass

            if not data:
                raise ValueError("No valid sourcing JSON found in response.")

            if isinstance(data, dict):
                if len(data) == 1 and list(data.keys())[0] in ["sourcing_report", "sourcingReport", "report", "data"]:
                    data = list(data.values())[0]
                    if isinstance(data, list):
                        data = {"items": data}
                if "items" in data and isinstance(data["items"], list):
                    for item in data["items"]:
                        if not isinstance(item, dict): continue
                        if "item_id" in item and "element_id" not in item:
                             item["element_id"] = item.pop("item_id")
                        if "matched_product" in item and isinstance(item["matched_product"], dict):
                            mp = item.pop("matched_product")
                            item["product_name"] = mp.get("name", "Product")
                            item["vendor"] = mp.get("vendor", "Generic")
                            item["price"] = mp.get("price", 0.0)
                            item["product_url"] = mp.get("url", "http://example.com")
                        if "stock_status" not in item: item["stock_status"] = "In Stock"
                        if "match_score" not in item: item["match_score"] = 0.9
                        if "product_name" not in item: item["product_name"] = "Sourced Item"
                        if "vendor" not in item: item["vendor"] = "Vesta Preferred"
                        if "price" not in item: item["price"] = 0.0
                        if "product_url" not in item: item["product_url"] = "http://vesta-design.com"

            if isinstance(data, dict):
                if "total_cart_value" not in data:
                    data["total_cart_value"] = sum(i.get("price", 0) for i in data.get("items", []))
                if "lead_time_summary" not in data:
                    data["lead_time_summary"] = "Ready to order."

            report = SourcingReport(**data)
            
            # 3. Update project element metadata
            for item in report.items:
                for element in project.elements:
                    if element.id == item.element_id:
                        element.metadata.update({
                            "sourced_product": item.model_dump(),
                            "final_price": item.price
                        })
            return report

        except Exception as e:
            print(f"Sourcing AI matching failed: {e}. Data received: {clean_content[:200]}")
            return self._generate_mock_sourcing(project)

    def _generate_mock_sourcing(self, project: BIMProjectState) -> SourcingReport:
        # Fallback to simple matching if AI fails
        items = []
        total_value = 0.0
        for element in project.elements:
            if element.type == ObjectType.FURNITURE:
                 item_type = element.metadata.get("item_type", "sofa")
                 matches = self.catalogue.get(item_type, [{"name": "Generic", "vendor": "Partner", "price": 500.0, "url": "#"}])
                 best = matches[0]
                 sourced = SourcedProduct(
                    element_id=element.id, product_name=best["name"], vendor=best["vendor"],
                    price=best["price"], stock_status="In Stock", product_url=best["url"], match_score=0.9
                 )
                 element.metadata.update({"sourced_product": sourced.model_dump(), "final_price": sourced.price})
                 items.append(sourced)
                 total_value += sourced.price
        return SourcingReport(items=items, total_cart_value=total_value, lead_time_summary="Fallback sourcing.")

def process_sourcing_node(project: BIMProjectState, report: SourcingReport) -> BIMProjectState:
    project.budget_total = report.total_cart_value
    return project
