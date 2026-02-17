"""
╔══════════════════════════════════════════════════════════════════╗
║  VESTACODE — URBAN RESIDENCE FULL PIPELINE TEST                  ║
║  Floor Plan: Urban Residence Level 1                             ║
║  Pipeline: Vision → Stylist → Spatial → Compliance → Sourcing    ║
╚══════════════════════════════════════════════════════════════════╝
"""
import requests
import time
import os
import json

BASE_URL = "http://localhost:25678"
FILE_PATH = "/home/cognitbotz/vestaagent/urban_residence_plan.jpg"

def run_test():
    print()
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║  VESTACODE — URBAN RESIDENCE FULL PIPELINE + CLIENT REVIEW      ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print()
    
    # ======= UPLOAD =======
    print("▓" * 66)
    print("  STAGE 1: VISION AGENT — Parsing Floor Plan")
    print("▓" * 66)
    
    with open(FILE_PATH, "rb") as f:
        files = {"file": (os.path.basename(FILE_PATH), f, "image/jpeg")}
        t0 = time.time()
        r = requests.post(f"{BASE_URL}/project/upload-plan", files=files)
        elapsed = time.time() - t0
    
    if r.status_code != 200:
        print(f"  ❌ FAILED: {r.status_code} — {r.text[:200]}")
        return
    
    data = r.json()
    bim = data.get("bim_state", {})
    elements = bim.get("elements", [])
    
    walls = [e for e in elements if e.get("type") == "wall"]
    doors = [e for e in elements if e.get("type") == "door"]
    windows = [e for e in elements if e.get("type") == "window"]
    furniture = [e for e in elements if e.get("type") == "furniture"]
    
    print(f"  ✅ Pipeline complete in {elapsed:.1f}s")
    print(f"  📐 Elements Detected:")
    print(f"     • Walls:     {len(walls)}")
    print(f"     • Doors:     {len(doors)}")
    print(f"     • Windows:   {len(windows)}")
    print(f"     • Furniture: {len(furniture)}")
    print()
    
    # Show wall positions
    if walls:
        print("  Wall Geometry:")
        for w in walls[:15]:
            pos = w.get("position", {})
            dims = w.get("dimensions", {})
            print(f"    [{w['id']}] pos=({pos.get('x',0):.1f}, {pos.get('z',0):.1f}) dims=({dims.get('x',0):.1f} × {dims.get('z',0):.1f})")
        if len(walls) > 15:
            print(f"    ... +{len(walls)-15} more walls")
    print()
    
    # ======= SPATIAL ENGINE =======
    print("▓" * 66)
    print("  STAGE 2: SPATIAL INTELLIGENCE ENGINE")
    print("▓" * 66)
    
    logs = bim.get("compliance_logs", [])
    spatial_log = next((l for l in logs if l.get("agent") == "spatial_engine"), None)
    compliance_log = next((l for l in logs if "summary" in l and l.get("agent") != "spatial_engine"), None)
    
    if spatial_log:
        score = spatial_log.get("flow_score", 0)
        bar_len = 40
        filled = int(score / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        icon = "🟢" if score >= 80 else "🟡" if score >= 50 else "🔴"
        
        print(f"\n  {icon} ERGONOMIC FLOW SCORE")
        print(f"     {bar}  {score}/100")
        print()
        print(f"  ┌─────────────────────┬──────────┐")
        print(f"  │ Metric              │ Value    │")
        print(f"  ├─────────────────────┼──────────┤")
        print(f"  │ Collisions          │ {spatial_log.get('collision_count', 0):>8} │")
        print(f"  │ Clearance Warnings  │ {spatial_log.get('clearance_violations', 0):>8} │")
        print(f"  │ Blocked Paths       │ {spatial_log.get('blocked_paths', 0):>8} │")
        print(f"  │ Density Ratio       │ {(spatial_log.get('density_ratio', 0) * 100):>6.1f}%  │")
        print(f"  │ Auto-Corrections    │ {spatial_log.get('corrections_applied', 0):>8} │")
        print(f"  └─────────────────────┴──────────┘")
        
        issues = spatial_log.get("issues", [])
        if issues:
            print(f"\n  Spatial Issues ({len(issues)}):")
            for i, issue in enumerate(issues[:12]):
                sev = issue.get("severity", "info")
                icon = "🔴" if sev == "critical" else "🟡" if sev == "warning" else "🟢"
                fix = " ✓FIXED" if issue.get("auto_fixed") else ""
                desc = issue.get("description", "")[:55]
                print(f"    {icon} [{issue.get('type', '?').upper():>10}] {desc}{fix}")
            if len(issues) > 12:
                print(f"    ... +{len(issues)-12} more issues")
    else:
        print("  ⚠️ No spatial analysis data")
    print()
    
    # ======= COMPLIANCE =======
    print("▓" * 66)
    print("  STAGE 3: COMPLIANCE AUDIT")
    print("▓" * 66)
    
    if compliance_log:
        status = "✅ ALL CODES PASSED" if compliance_log.get("is_compliant") else "❌ ISSUES FOUND"
        print(f"\n  Status: {status}")
        print(f"  Summary: {compliance_log.get('summary', 'N/A')}")
        viols = compliance_log.get("violations", [])
        if viols:
            print(f"\n  Violations ({len(viols)}):")
            for v in viols[:8]:
                sev = v.get("severity", "warning")
                icon = "🔴" if sev == "critical" else "🟡"
                print(f"    {icon} [{sev.upper():>8}] {v.get('description', 'N/A')[:60]}")
        passed = compliance_log.get("passed_rules", [])
        if passed:
            print(f"\n  Passed Rules ({len(passed)}):")
            for p in passed[:5]:
                print(f"    ✅ {p}")
    else:
        print("  ⚠️ No compliance data")
    print()
    
    # ======= FURNITURE =======
    print("▓" * 66)
    print("  STAGE 4: FURNITURE LAYOUT (Realistic Render Materials)")
    print("▓" * 66)
    
    if furniture:
        print()
        for f_item in furniture:
            pos = f_item.get("position", {})
            dims = f_item.get("dimensions", {})
            meta = f_item.get("metadata", {})
            name = meta.get("item_type", "Unknown")
            cost = meta.get("cost", 0)
            
            name_lc = name.lower()
            if "sofa" in name_lc or "chair" in name_lc or "armchair" in name_lc:
                mat = "Linen Fabric — Warm Taupe"
                mat_hex = "#C4A882"
            elif "table" in name_lc or "desk" in name_lc or "dresser" in name_lc or "stand" in name_lc or "cabinet" in name_lc:
                mat = "Natural Oak Wood"
                mat_hex = "#8B6F47"
            elif "lamp" in name_lc or "light" in name_lc:
                mat = "Brushed Brass + Frosted Glass"
                mat_hex = "#F5E6CC"
            elif "bed" in name_lc:
                mat = "White Linen + Natural Cotton"
                mat_hex = "#E8DDD4"
            elif "rug" in name_lc or "carpet" in name_lc:
                mat = "Persian Wool Blend"
                mat_hex = "#B8A080"
            elif "bookshelf" in name_lc or "shelf" in name_lc:
                mat = "Walnut Veneer"
                mat_hex = "#654321"
            else:
                mat = "Natural Wood Finish"
                mat_hex = "#D4C5B2"
            
            print(f"  🪑 {name}")
            print(f"     📍 Position: ({pos.get('x',0):.1f}, {pos.get('y',0):.1f}, {pos.get('z',0):.1f})")
            print(f"     📏 Size:     {dims.get('x',0):.1f}m × {dims.get('y',0):.1f}m × {dims.get('z',0):.1f}m")
            print(f"     🎨 Material: {mat} ({mat_hex})")
            print(f"     💰 Cost:     ${cost:,.0f}")
            print()
    else:
        print("  ⚠️ No furniture placed")
    
    # ======= STYLE DNA =======
    print("▓" * 66)
    print("  STAGE 5: DESIGN DNA")
    print("▓" * 66)
    
    style = bim.get("style_profile", {})
    palette = style.get("palette", style) if isinstance(style.get("palette"), dict) else style
    print(f"\n  🎨 Theme:          {palette.get('theme', style.get('theme', 'Japandi Modern'))}")
    print(f"  🏠 Wall Color:     {palette.get('wall_color', '#F5F5F0')}")
    print(f"  🪵 Floor Material: {palette.get('floor_material', 'Standard Oak')}")
    print(f"  💡 Lighting Mood:  {palette.get('lighting_mood', 'Warm Ambient')}")
    print(f"  💰 Total Budget:   ${bim.get('budget_total', 0):,.0f}")
    print()
    
    # ======= SOURCING =======
    sourcing = bim.get("sourcing_data", {})
    if sourcing:
        items = sourcing.get("items", sourcing.get("products", []))
        print("▓" * 66)
        print("  STAGE 6: SOURCING REPORT")
        print("▓" * 66)
        if isinstance(items, list) and items:
            for s in items[:5]:
                if isinstance(s, dict):
                    print(f"  🛒 {s.get('name', s.get('item_type', 'Item'))}")
                    print(f"     Vendor:  {s.get('vendor', s.get('source', 'N/A'))}")
                    print(f"     Price:   ${s.get('price', s.get('estimated_cost', 0)):,.0f}")
                    print()
        elif isinstance(sourcing, dict):
            print(f"  Sourcing data: {json.dumps(sourcing, indent=2)[:300]}")
        print()
    
    # ======= CLIENT VERDICT =======
    print("▓" * 66)
    print("  CLIENT REVIEW — FINAL VERDICT")
    print("▓" * 66)
    
    score = spatial_log.get("flow_score", 0) if spatial_log else 0
    is_compliant = compliance_log.get("is_compliant", False) if compliance_log else False
    has_furniture = len(furniture) >= 3
    blocked = spatial_log.get("blocked_paths", 0) if spatial_log else 0
    
    criteria = [
        (score >= 70, f"Flow Score {score}/100 ≥ 70"),
        (blocked == 0, "No blocked egress paths"),
        (has_furniture, f"{len(furniture)} furniture items ≥ 3"),
        (is_compliant, "Compliance audit passed"),
    ]
    
    print()
    for passed, desc in criteria:
        icon = "✅" if passed else "❌"
        print(f"  {icon} {desc}")
    
    all_pass = all(c[0] for c in criteria)
    print()
    if all_pass:
        print("  ╔═══════════════════════════════════════════════════════════╗")
        print("  ║  ✅  URBAN RESIDENCE — DESIGN APPROVED                    ║")
        print("  ║  Ready for Realistic 3D Render in Client Review Modal     ║")
        print("  ╚═══════════════════════════════════════════════════════════╝")
        print()
        print("  Realistic Render Settings:")
        print("  ├── Walls:      White Plaster (#F0EDE8) roughness=0.95")
        print("  ├── Floor:      Oak Hardwood (#D4C1A1)")
        print("  ├── Doors:      Dark Oak (#5C4033)")
        print("  ├── Windows:    Sky Glass (#B8D8E8) opacity=0.35")
        print("  ├── Tone Map:   ACES Filmic, exposure=1.2")
        print("  ├── Key Light:  3200K warm (intensity=3)")
        print("  ├── Fill Light: 5600K cool (intensity=1)")
        print("  └── HDR Probe:  'apartment' environment")
    else:
        failed = [c[1] for c in criteria if not c[0]]
        print("  ╔═══════════════════════════════════════════════════════════╗")
        print("  ║  ⚠️  DESIGN NEEDS REVISION                               ║")
        print("  ╚═══════════════════════════════════════════════════════════╝")
        for f in failed:
            print(f"  ❌ {f}")
    
    print()
    print("═" * 66)
    print("  PIPELINE COMPLETE")
    print("═" * 66)


if __name__ == "__main__":
    print("Connecting to VestaCode API...")
    for _ in range(30):
        try:
            requests.get(BASE_URL)
            break
        except:
            time.sleep(1)
    
    run_test()
