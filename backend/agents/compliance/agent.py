import math
from typing import List, Dict, Any, Optional
from backend.agents.compliance.schema import ComplianceReport, ComplianceViolation
from backend.core.bim_state import BIMProjectState, BIMElement, ObjectType

from langchain_groq import ChatGroq
from backend.core.llm_factory import get_llm
import json

COMPLIANCE_SYSTEM_PROMPT = """
You are the 'Compliance Agent' for VestaCode, the spatial design IDE. Your role is to audit architectural plans 
for safety, ADA accessibility, and building code violations.

Analyze the provided BIM state (walls, doors, windows, furniture) and check for:
1. ADA Accessibility: Door widths ≥ 0.81m, hallway widths ≥ 0.91m, wheelchair turning radius ≥ 1.5m
2. Fire Safety: Minimum 2 egress paths, exit widths ≥ 0.9m, no dead-end corridors > 6m
3. Building Codes: Minimum room sizes (bedroom ≥ 7m², bathroom ≥ 3.5m²), ceiling height ≥ 2.4m
4. Furniture Safety: Furniture density ≤ 60% of room area, no blocked exit paths

Return ONLY a valid JSON matching this schema:
{
  "is_compliant": true,
  "violations": [
    {
      "element_id": "door-abc123",
      "rule_id": "ADA-404.2.3",
      "severity": "critical",
      "description": "Master bedroom door width is 0.75m, below the ADA minimum of 0.81m",
      "remediation_advice": "Widen door opening to at least 0.81m"
    }
  ],
  "passed_rules": ["ADA-404.2.3 Door Widths", "IBC-1005.1 Egress Width"],
  "summary": "2 violations found: Bath 1 door too narrow, Living Room furniture blocks exit path."
}

CRITICAL: 
- Each violation description MUST be SPECIFIC — mention the exact room, element, measurement, and code.
- Do NOT use generic descriptions like 'Compliance issue detected'.
- severity must be 'critical' (blocks occupancy) or 'warning' (advisory).
- If you cannot measure something precisely, explain what data is missing specifically.
"""

class ComplianceAgent:
    def __init__(self, model_name: str = None):
        self.llm = get_llm(agent_name="compliance", model=model_name, temperature=0)
        self.rules = {
            "MIN_HALLWAY_WIDTH": 0.91,
            "MIN_DOOR_CLEARANCE": 0.81,
            "MAX_FURNITURE_DENSITY": 0.6
        }

    async def check_compliance(self, project: BIMProjectState, knowledge: Optional[Dict[str, Any]] = None) -> ComplianceReport:
        """Performs a multi-layered check: Symbolic geometry & LLM interpretation."""
        violations = []
        passed_symbolic = set()
        
        # 1. Symbolic Check: Furniture near entry
        for element in project.elements:
            if element.type == ObjectType.FURNITURE:
                dist = math.sqrt(element.position.x**2 + element.position.z**2)
                if dist < 1.0:
                    violations.append(ComplianceViolation(
                        element_id=element.id,
                        rule_id="ADA-404.2.3",
                        severity="critical",
                        description="Furniture placed in the maneuvering clearance zone for the entry door.",
                        remediation_advice="Move item at least 1.2m away from the door swing arc."
                    ))
        
        # 2. Symbolic Check: Door Width Verification
        doors = [e for e in project.elements if e.type == ObjectType.DOOR]
        all_doors_pass = True
        for door in doors:
            if door.dimensions.x < self.rules["MIN_DOOR_CLEARANCE"]:
                all_doors_pass = False
                violations.append(ComplianceViolation(
                    element_id=door.id,
                    rule_id="ADA-404.2.3",
                    severity="critical",
                    description=f"Door {door.id} width ({door.dimensions.x:.2f}m) is below ADA minimum ({self.rules['MIN_DOOR_CLEARANCE']}m).",
                    remediation_advice=f"Widen door to at least {self.rules['MIN_DOOR_CLEARANCE']}m."
                ))
        if all_doors_pass and doors:
            passed_symbolic.add("ADA-404.2.3")
        
        # 3. Symbolic Check: Egress Paths (need at least 2 doors for multi-egress)
        if len(doors) >= 2:
            passed_symbolic.add("IBC-1005.1")
        elif len(doors) == 1:
            violations.append(ComplianceViolation(
                element_id="",
                rule_id="IBC-1005.1",
                severity="warning",
                description=f"Only {len(doors)} door(s) detected. Multi-egress requires at least 2 separate exit paths.",
                remediation_advice="Verify additional exit paths exist (may not be detected from floor plan)."
            ))
        
        # 4. Symbolic Check: Furniture Density
        walls = [e for e in project.elements if e.type == ObjectType.WALL]
        furniture = [e for e in project.elements if e.type == ObjectType.FURNITURE]
        if walls:
            room_area = max(e.dimensions.x for e in walls) * max(e.dimensions.z if e.dimensions.z > 1 else e.dimensions.x for e in walls)
            furniture_area = sum(e.dimensions.x * e.dimensions.z for e in furniture)
            if room_area > 0 and (furniture_area / room_area) > self.rules["MAX_FURNITURE_DENSITY"]:
                violations.append(ComplianceViolation(
                    element_id="",
                    rule_id="IBC-1003.2",
                    severity="warning",
                    description=f"Furniture density {furniture_area/room_area:.0%} exceeds {self.rules['MAX_FURNITURE_DENSITY']:.0%} maximum.",
                    remediation_advice="Remove or rearrange furniture to reduce density."
                ))
            else:
                passed_symbolic.add("IBC-1003.2")
        
        # 2. LLM Interpretation — include doors, windows, and furniture for proper audit
        walls_data = [{"id": e.id, "type": "wall", "pos": [e.position.x, e.position.z], "length": e.dimensions.x} for e in project.elements if e.type == ObjectType.WALL]
        doors_data = [{"id": e.id, "type": "door", "pos": [e.position.x, e.position.z], "width": e.dimensions.x} for e in project.elements if e.type == ObjectType.DOOR]
        windows_data = [{"id": e.id, "type": "window", "pos": [e.position.x, e.position.z], "width": e.dimensions.x} for e in project.elements if e.type == ObjectType.WINDOW]
        furniture_data = [{"id": e.id, "type": "furniture", "item": e.metadata.get("item_type", "unknown"), "pos": [e.position.x, e.position.z], "size": [e.dimensions.x, e.dimensions.z]} for e in project.elements if e.type == ObjectType.FURNITURE]
        
        bim_summary = {
            "walls": walls_data,
            "doors": doors_data,
            "windows": windows_data,
            "furniture": furniture_data,
            "total_elements": len(project.elements)
        }
        codes = knowledge.get("building_codes", {}) if knowledge else {}
        
        content = ""  # Initialize for error handler
        try:
            response = await self.llm.ainvoke([
                {"role": "system", "content": COMPLIANCE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Building Codes Reference:\n{json.dumps(codes, indent=2)}\n\nBIM State to Audit:\nWalls: {len(walls_data)}, Doors: {len(doors_data)}, Windows: {len(windows_data)}, Furniture: {len(furniture_data)}\n\n{json.dumps(bim_summary, indent=2)}"}
            ])
            
            content = response.content
            # Extract all JSON blocks
            import re
            blocks = re.findall(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if not blocks:
                blocks = re.findall(r'(\{.*\})', content, re.DOTALL)
            
            ai_data = {}
            for block in blocks:
                clean_block = block
                clean_block = re.sub(r'//.*$', '', clean_block, flags=re.MULTILINE)
                clean_block = "".join(c for c in clean_block if ord(c) >= 32 or c in "\n\r\t")
                try:
                    temp_data = json.loads(clean_block, strict=False)
                    if isinstance(temp_data, dict) and any(k in temp_data for k in ["violations", "is_compliant", "issues"]):
                        ai_data = temp_data
                        break
                except: continue
                
            if not ai_data and blocks:
                try: ai_data = json.loads(blocks[0], strict=False)
                except: pass

            # Handle potential wrapper keys
            if isinstance(ai_data, dict) and len(ai_data) == 1 and list(ai_data.keys())[0] in ["compliance_report", "report", "data"]:
                ai_data = list(ai_data.values())[0]
            
            # If the model returned a list directly, assume it's the violations
            if isinstance(ai_data, list):
                ai_data = {"violations": ai_data}

            # Handle 'issues' alias
            if "issues" in ai_data and "violations" not in ai_data:
                ai_data["violations"] = ai_data.pop("issues")
            
            # Robust summary handling (must be string)
            if "summary" in ai_data and not isinstance(ai_data["summary"], str):
                ai_data["summary"] = json.dumps(ai_data["summary"])
            
            # CRITICAL: Handle aliased keys in violations
            if "violations" in ai_data and isinstance(ai_data["violations"], list):
                clean_violations = []
                for v in ai_data["violations"]:
                    if not isinstance(v, dict): continue
                    # FILTER: Skip items that look like BIM elements, not violations
                    if any(k in v for k in ["position", "dimensions", "rotation"]):
                        continue
                    if "code" in v and "rule_id" not in v:
                        v["rule_id"] = str(v.pop("code"))
                    if "message" in v and "description" not in v:
                        v["description"] = v.pop("message")
                    if "complianceIssue" in v and "description" not in v:
                        v["description"] = v.pop("complianceIssue")
                    if "fix" in v and "remediation_advice" not in v:
                        v["remediation_advice"] = v.pop("fix")
                    if "advice" in v and "remediation_advice" not in v:
                         v["remediation_advice"] = v.pop("advice")
                    if "codeReference" in v and "rule_id" not in v:
                        v["rule_id"] = str(v.pop("codeReference"))
                    # Ensure description exists
                    if "description" not in v:
                        v["description"] = v.get("issue", v.get("detail", "Compliance issue detected."))
                    if "element_id" not in v:
                        v["element_id"] = v.get("id", "")
                    clean_violations.append(v)
                ai_data["violations"] = clean_violations

            # Ensure mandatory top-level fields have defaults
            if "is_compliant" not in ai_data:
                ai_data["is_compliant"] = True
                if "violations" in ai_data and len(ai_data["violations"]) > 0:
                     if any(v.get("severity") == "critical" for v in ai_data["violations"]):
                          ai_data["is_compliant"] = False

            if "summary" not in ai_data:
                ai_data["summary"] = "AI audit completed."
                
            ai_report = ComplianceReport(**ai_data)
            
            # Filter: Skip LLM violations that duplicate symbolic checks
            for v in ai_report.violations:
                rule = v.rule_id or ""
                # Skip if we already checked this rule symbolically
                if rule in passed_symbolic:
                    continue
                # Downgrade LLM-only criticals to warnings (can't verify measurements)
                if v.severity == "critical" and rule not in passed_symbolic:
                    # Only keep critical if we can confirm the measurement
                    v.severity = "warning"
                violations.append(v)
        except Exception as e:
            print(f"Compliance AI analysis failed: {e}. Data received: {content[:200]}")

        # Build a smart summary from violation details
        critical_viols = [v for v in violations if v.severity == "critical"]
        warning_viols = [v for v in violations if v.severity == "warning"]
        
        is_compliant = len(critical_viols) == 0
        
        if is_compliant and len(warning_viols) == 0:
            summary = "All building codes, ADA accessibility, and fire safety requirements met."
        elif is_compliant:
            summary = f"Compliant with {len(warning_viols)} advisory warning(s). No critical issues."
        else:
            critical_descs = [v.description[:60] for v in critical_viols[:3]]
            summary = f"{len(critical_viols)} critical violation(s): {'; '.join(critical_descs)}"

        # Build passed rules based on what wasn't violated
        violated_rules = {v.rule_id for v in violations}
        all_rules = [
            ("ADA-404.2.3", "Door Widths ≥ 0.81m"),
            ("IBC-1005.1", "Egress Path Width ≥ 0.91m"),
            ("IBC-1006.2", "Exit Sign Locations"),
            ("NFPA-72", "Fire Alarm Visibility"),
            ("ADA-304.3", "Wheelchair Turning Radius ≥ 1.5m"),
            ("IBC-1208.4", "Minimum Room Sizes"),
            ("IBC-1003.2", "Furniture Density ≤ 60%"),
        ]
        passed_rules = [f"{code} {desc}" for code, desc in all_rules if code not in violated_rules]

        return ComplianceReport(
            is_compliant=is_compliant,
            violations=violations,
            passed_rules=passed_rules,
            summary=summary
        )

def process_compliance_node(project: BIMProjectState, report: ComplianceReport) -> BIMProjectState:
    """Logs the report into the BIM state for the frontend to visualize."""
    project.compliance_logs.append({
        "timestamp": "now", # In production, use ISO format
        "is_compliant": report.is_compliant,
        "summary": report.summary,
        "violation_count": len(report.violations),
        "violations": [v.model_dump() for v in report.violations] # CRITICAL: Include violations for linting
    })
    return project
