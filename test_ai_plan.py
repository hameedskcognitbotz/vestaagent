import requests
import time
import os
import json

BASE_URL = "http://localhost:25678"
FILE_PATH = "/home/cognitbotz/vestaagent/ai_test_plan.png"

def test_spatial_engine():
    print(f"{'='*60}")
    print(f"  VESTACODE SPATIAL ENGINE — END-TO-END TEST")
    print(f"  Input: AI-Generated 1-Bedroom Floor Plan")
    print(f"{'='*60}\n")
    
    if not os.path.exists(FILE_PATH):
        print(f"ERROR: File {FILE_PATH} not found.")
        return

    with open(FILE_PATH, "rb") as f:
        files = {"file": (os.path.basename(FILE_PATH), f, "image/png")}
        start_time = time.time()
        try:
            response = requests.post(f"{BASE_URL}/project/upload-plan", files=files)
            duration = time.time() - start_time
            
            print(f"⏱  Processing Time: {duration:.2f}s")
            print(f"📡 HTTP Status: {response.status_code}\n")
            
            if response.status_code == 200:
                data = response.json()
                bim = data.get("bim_state", {})
                elements = bim.get("elements", [])
                
                walls = [e for e in elements if e.get("type") == "wall"]
                doors = [e for e in elements if e.get("type") == "door"]
                windows = [e for e in elements if e.get("type") == "window"]
                furniture = [e for e in elements if e.get("type") == "furniture"]
                
                print(f"🔍 VISION AGENT")
                print(f"   Walls extracted: {len(walls)}")
                print(f"   Doors found:     {len(doors)}")
                print(f"   Windows found:   {len(windows)}")
                print(f"   Notes: {data.get('vision_notes', 'N/A')}\n")
                
                print(f"🛋️  STYLIST AGENT")
                print(f"   Furniture placed: {len(furniture)}")
                for f_item in furniture:
                    pos = f_item.get("position", {})
                    dims = f_item.get("dimensions", {})
                    name = f_item.get("metadata", {}).get("item_type", "Unknown")
                    print(f"     • {name}: pos({pos.get('x',0):.1f}, {pos.get('z',0):.1f}) "
                          f"size({dims.get('x',0):.1f}×{dims.get('z',0):.1f}m)")
                
                # Find spatial engine log
                logs = bim.get("compliance_logs", [])
                spatial_log = None
                compliance_log = None
                for log in logs:
                    if log.get("agent") == "spatial_engine":
                        spatial_log = log
                    elif "summary" in log:
                        compliance_log = log
                
                if spatial_log:
                    print(f"\n📐 SPATIAL ENGINE")
                    print(f"   Flow Score:          {spatial_log.get('flow_score', '?')}/100")
                    print(f"   Collisions:          {spatial_log.get('collision_count', '?')}")
                    print(f"   Clearance Warnings:  {spatial_log.get('clearance_violations', '?')}")
                    print(f"   Blocked Paths:       {spatial_log.get('blocked_paths', '?')}")
                    print(f"   Density Ratio:       {spatial_log.get('density_ratio', '?')}")
                    print(f"   Auto-Corrections:    {spatial_log.get('corrections_applied', '?')}")
                    
                    issues = spatial_log.get("issues", [])
                    if issues:
                        print(f"   Issues ({len(issues)}):")
                        for issue in issues[:10]:
                            icon = "🔴" if issue["severity"] == "critical" else "🟡" if issue["severity"] == "warning" else "🟢"
                            fix_tag = " [AUTO-FIXED]" if issue.get("auto_fixed") else ""
                            print(f"     {icon} [{issue['type'].upper()}] {issue['description']}{fix_tag}")
                else:
                    print("\n📐 SPATIAL ENGINE: No spatial report found in logs.")
                
                if compliance_log:
                    print(f"\n🛡️  COMPLIANCE AGENT")
                    print(f"   Summary: {compliance_log.get('summary', 'N/A')}")
                    print(f"   Violations: {compliance_log.get('violation_count', '?')}")
                
                print(f"\n{'='*60}")
                print(f"  ✅ PIPELINE COMPLETE — {len(elements)} total BIM elements")
                print(f"{'='*60}")
            else:
                print(f"❌ FAILURE: {response.text}")
        except Exception as e:
            print(f"❌ ERROR connecting to server: {e}")

if __name__ == "__main__":
    print("Waiting for server to be ready...")
    for _ in range(30):
        try:
            requests.get(BASE_URL)
            print("Server is UP!\n")
            break
        except:
            time.sleep(1)
    
    test_spatial_engine()
