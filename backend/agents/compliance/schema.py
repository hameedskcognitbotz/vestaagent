from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ComplianceViolation(BaseModel):
    element_id: str = ""
    rule_id: str = "CODE-GENERIC"  # e.g., "ADA-404.2.3"
    severity: str = "warning"  # "critical", "warning"
    description: str
    remediation_advice: str = "Review the spatial constraints and adjust placement."

class ComplianceReport(BaseModel):
    is_compliant: bool
    violations: List[ComplianceViolation] = Field(default_factory=list)
    passed_rules: List[str] = Field(default_factory=list)
    summary: str
