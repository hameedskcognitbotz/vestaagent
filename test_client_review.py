"""
╔══════════════════════════════════════════════════════════════╗
║         VESTACODE — CLIENT REVIEW SIMULATION                 ║
║         Simulates a client reviewing and accepting design    ║
╚══════════════════════════════════════════════════════════════╝
"""
import requests
import time
import os
import json

BASE_URL = "http://localhost:25678"
FILE_PATH = "/home/cognitbotz/vestaagent/ai_test_plan.png"

def client_review():
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║         VESTACODE — CLIENT REVIEW SIMULATION                ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    
    # ======= STEP 1: Upload Floor Plan =======
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  STEP 1: UPLOADING FLOOR PLAN TO AI PIPELINE")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    with open(FILE_PATH, "rb") as f:
        files = {"file": (os.path.basename(FILE_PATH), f, "image/png")}
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/project/upload-plan", files=files)
        duration = time.time() - start_time
    
    if response.status_code != 200:
        print(f"  ❌ FAILED: {response.text}")
        return
    
    data = response.json()
    bim = data.get("bim_state", {})
    elements = bim.get("elements", [])
    
    walls = [e for e in elements if e.get("type") == "wall"]
    doors = [e for e in elements if e.get("type") == "door"]
    windows = [e for e in elements if e.get("type") == "window"]
    furniture = [e for e in elements if e.get("type") == "furniture"]
    
    print(f"  ✅ Pipeline complete in {duration:.1f}s")
    print(f"  📐 {len(walls)} walls | {len(doors)} doors | {len(windows)} windows | {len(furniture)} furniture")
    print()
    
    # ======= STEP 2: Spatial Intelligence Report =======
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  STEP 2: SPATIAL INTELLIGENCE ENGINE REPORT")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    logs = bim.get("compliance_logs", [])
    spatial_log = None
    compliance_log = None
    for log in logs:
        if log.get("agent") == "spatial_engine":
            spatial_log = log
        elif "summary" in log and log.get("agent") != "spatial_engine":
            compliance_log = log
    
    if spatial_log:
        score = spatial_log.get("flow_score", 0)
        bar_len = 30
        filled = int(score / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        icon = "🟢" if score >= 80 else "🟡" if score >= 50 else "🔴"
        
        print(f"  {icon} Flow Score: {score}/100  [{bar}]")
        print(f"  ⚡ Collisions:         {spatial_log.get('collision_count', 0)}")
        print(f"  🚪 Clearance Warnings: {spatial_log.get('clearance_violations', 0)}")
        print(f"  🛤️  Blocked Paths:      {spatial_log.get('blocked_paths', 0)}")
        print(f"  📊 Density Ratio:      {(spatial_log.get('density_ratio', 0) * 100):.1f}%")
        print(f"  🔧 Auto-Corrections:   {spatial_log.get('corrections_applied', 0)}")
        
        issues = spatial_log.get("issues", [])
        if issues:
            print(f"\n  Issues ({len(issues)}):")
            for issue in issues[:8]:
                sev = issue.get("severity", "info")
                icon = "🔴" if sev == "critical" else "🟡" if sev == "warning" else "🟢"
                fix = " ✓FIXED" if issue.get("auto_fixed") else ""
                print(f"    {icon} {issue['type'].upper()}: {issue['description'][:60]}{fix}")
    else:
        print("  ⚠️ No spatial analysis data found")
    print()
    
    # ======= STEP 3: Compliance Audit =======
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  STEP 3: COMPLIANCE AUDIT")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    if compliance_log:
        status = "✅ PASSED" if compliance_log.get("is_compliant") else "❌ ISSUES FOUND"
        print(f"  Status: {status}")
        print(f"  Summary: {compliance_log.get('summary', 'N/A')}")
        viols = compliance_log.get("violations", [])
        if viols:
            print(f"  Violations ({len(viols)}):")
            for v in viols[:5]:
                print(f"    • [{v.get('severity', '?')}] {v.get('description', 'N/A')[:70]}")
    else:
        print("  ⚠️ No compliance data found")
    print()
    
    # ======= STEP 4: Furniture Placement Review =======
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  STEP 4: FURNITURE PLACEMENT (Realistic Render Data)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    if furniture:
        for f_item in furniture:
            pos = f_item.get("position", {})
            dims = f_item.get("dimensions", {})
            meta = f_item.get("metadata", {})
            name = meta.get("item_type", "Unknown")
            material = meta.get("material", "Standard")
            
            # Map to realistic render material
            name_lc = name.lower()
            if "sofa" in name_lc or "chair" in name_lc or "armchair" in name_lc:
                render_mat = "Linen Fabric — Warm Taupe (#C4A882)"
            elif "table" in name_lc or "desk" in name_lc or "dresser" in name_lc or "stand" in name_lc:
                render_mat = "Natural Oak Wood (#8B6F47)"
            elif "lamp" in name_lc or "light" in name_lc:
                render_mat = "Brushed Brass + Frosted Glass (#F5E6CC)"
            elif "bed" in name_lc:
                render_mat = "White Linen + Natural Cotton (#E8DDD4)"
            else:
                render_mat = "Natural Wood Finish (#D4C5B2)"
            
            print(f"  🪑 {name}")
            print(f"     Position: ({pos.get('x',0):.1f}, {pos.get('y',0):.1f}, {pos.get('z',0):.1f})")
            print(f"     Size:     {dims.get('x',0):.1f}m × {dims.get('y',0):.1f}m × {dims.get('z',0):.1f}m")
            print(f"     Render Material: {render_mat}")
            print()
    else:
        print("  ⚠️ No furniture placed yet")
    
    # ======= STEP 5: Design DNA =======
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  STEP 5: DESIGN DNA PROFILE")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    style = bim.get("style_profile", {})
    palette = style.get("palette", {})
    print(f"  🎨 Theme: {style.get('theme', 'Japandi Modern')}")
    print(f"  🏠 Wall Color: {palette.get('wall_color', '#F5F5F0')}")
    print(f"  🪵 Floor: {palette.get('floor_material', 'Standard Oak')}")
    print(f"  💡 Mood: {palette.get('lighting_mood', 'Warm Ambient')}")
    print(f"  💰 Budget: ${bim.get('budget_total', 0):,.0f}")
    print()
    
    # ======= STEP 6: Client Decision =======
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  STEP 6: CLIENT DECISION")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Auto-review logic
    score = spatial_log.get("flow_score", 0) if spatial_log else 0
    is_compliant = compliance_log.get("is_compliant", False) if compliance_log else False
    has_furniture = len(furniture) > 0
    blocked = spatial_log.get("blocked_paths", 0) if spatial_log else 0
    
    approval_criteria = [
        (score >= 70, f"Flow Score {score}/100 ≥ 70"),
        (blocked == 0, f"No blocked egress paths"),
        (has_furniture, f"{len(furniture)} furniture items placed"),
        (is_compliant, f"Compliance audit passed"),
    ]
    
    all_pass = all(c[0] for c in approval_criteria)
    
    for passed, desc in approval_criteria:
        icon = "✅" if passed else "❌"
        print(f"  {icon} {desc}")
    
    print()
    if all_pass:
        print("  ╔════════════════════════════════════════════════════╗")
        print("  ║  ✅  DESIGN APPROVED — READY FOR REALISTIC RENDER  ║")
        print("  ╚════════════════════════════════════════════════════╝")
        print()
        print("  The 3D viewport will now switch to Realistic Mode with:")
        print("  • PBR Materials (meshPhysicalMaterial)")
        print("  • ACES Filmic Tone Mapping")
        print("  • Warm directional lighting (3200K key, 5600K fill)")
        print("  • Oak hardwood floor plane")
        print("  • White plaster walls (roughness: 0.95)")
        print("  • Environment: 'apartment' HDR probe")
        print("  • Contact shadows (opacity: 0.6, blur: 1.5)")
        print()
        print("  Client Review Modal features:")
        print("  • Full 3D realistic preview viewport (380px)")
        print("  • Summary stats (walls, furniture, flow score, budget)")
        print("  • Furniture placement coordinates")
        print("  • Compliance badge with status")
        print("  • Design DNA with color palette")
        print("  • 'Approve Design' / 'Request Changes' actions")
    else:
        failed = [c[1] for c in approval_criteria if not c[0]]
        print("  ╔════════════════════════════════════════════════════╗")
        print("  ║  ⚠️  DESIGN NEEDS REVISION                        ║")
        print("  ╚════════════════════════════════════════════════════╝")
        print(f"  Failed criteria: {', '.join(failed)}")
        print("  The client would click 'Request Changes' in the modal.")
    
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                    REVIEW COMPLETE                          ║")
    print("╚══════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    print("Waiting for server to be ready...")
    for _ in range(30):
        try:
            requests.get(BASE_URL)
            break
        except:
            time.sleep(1)
    
    client_review()
