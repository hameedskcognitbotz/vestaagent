from dotenv import load_dotenv
import os
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, Response, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.core.bim_state import BIMProjectState, BIMElement, ObjectType, Vector3, BIMElementDelta
from backend.agents.orchestrator.graph import app_graph, memory_manager, STATIC_KNOWLEDGE
from backend.core.ifc_compiler import IFCCompiler
from backend.core.project_store import ProjectStore
from backend.core.job_store import JobStore, JobStatus
from backend.core.llm_factory import LLMProvider
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import uuid
import json
import asyncio

from backend.core.auth import router as auth_router
from backend.core.report import generate_report_html

app = FastAPI(title="VestaCode API", version="0.2.0")

# Mount auth routes: POST /auth/register, POST /auth/login, GET /auth/me
app.include_router(auth_router, prefix="/auth")

# CORS — read origins from env so production deployments never use wildcard
_raw_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

project_store = ProjectStore()
job_store = JobStore()

@app.get("/")
async def root():
    return {"status": "alive", "message": "VestaCode Orchestrator is ready."}



# ============================================================================
#  PROJECT ENDPOINTS
# ============================================================================

# ---------- Background pipeline runner ----------
async def _run_pipeline_job(job_id: str, project_id: str, contents: bytes):
    """Execute the full AI pipeline in the background, updating job status."""
    await job_store.update(job_id, status=JobStatus.RUNNING, current_step="vision")
    try:
        initial_state = {
            "project": BIMProjectState(project_id=project_id, name="New Project"),
            "messages": [],
            "next_agent": "vision",
            "plan_image": contents,
            "user_message": None,
            "extraction_results": None,
            "long_term_memory": memory_manager.load_memory("default_user").model_dump(),
            "semantic_knowledge": STATIC_KNOWLEDGE
        }
        final_state = await app_graph.ainvoke(initial_state)

        result = {
            "project_id": project_id,
            "bim_state": final_state["project"].model_dump(),
            "vision_notes": final_state["extraction_results"].get("notes") if final_state.get("extraction_results") else "Plan processed."
        }

        # Auto-persist the finished project
        project_store.save(final_state["project"])

        await job_store.update(job_id, status=JobStatus.COMPLETED, result=result, current_step="done")
    except Exception as exc:
        await job_store.update(job_id, status=JobStatus.FAILED, error=str(exc), current_step="failed")


@app.post("/project/upload-plan")
async def upload_plan(file: UploadFile = File(...), project_id: str = Form(None)):
    """Accept a plan and start the AI pipeline asynchronously. Returns a job_id for polling."""
    if not project_id:
        project_id = str(uuid.uuid4())

    contents = await file.read()
    job = await job_store.create(project_id=project_id, user_id="default_user", kind="upload")

    # Fire-and-forget background task in the asyncio loop
    asyncio.create_task(_run_pipeline_job(job.job_id, project_id, contents))

    return {
        "job_id": job.job_id,
        "project_id": project_id,
        "status": "pending"
    }


@app.get("/project/job/{job_id}")
async def poll_job(job_id: str):
    """Poll the status of a background pipeline job."""
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job.to_dict()

class ChatRequest(BaseModel):
    project_id: str
    message: str
    current_state: BIMProjectState

@app.post("/project/chat")
async def chat_with_agents(request: ChatRequest):
    project = request.current_state
    
    # Run the orchestrator graph with the user message
    initial_state = {
        "project": project,
        "messages": [{"role": "user", "content": request.message}],
        "next_agent": "vision",
        "plan_image": None,
        "user_message": request.message,
        "extraction_results": None,
        "long_term_memory": memory_manager.load_memory("default_user").model_dump(),
        "semantic_knowledge": STATIC_KNOWLEDGE
    }
    
    final_state = await app_graph.ainvoke(initial_state)
    
    # 3. Extract the last agent update
    logs = final_state.get("messages", [])
    last_msg = logs[-1] if logs else {"content": "Processing complete."}
    agent_response = last_msg.get("content") if isinstance(last_msg, dict) else last_msg

    return {
        "bim_state": final_state["project"].model_dump(),
        "agent_response": agent_response
    }

class DiffAcceptRequest(BaseModel):
    project_id: str
    current_state: BIMProjectState
    delta: BIMElementDelta
    
@app.post("/project/diff/accept")
async def accept_diff(request: DiffAcceptRequest):
    """
    Applies a specific delta (partially committed change) to the BIM state.
    This simulates the 'Cursor' functionality of accepting a suggestion.
    """
    project = request.current_state
    delta = request.delta
    
    # 1. Apply Additions
    if delta.added_elements:
        project.elements.extend(delta.added_elements)
    
    # 2. Apply Removals
    if delta.removed_element_ids:
        project.elements = [e for e in project.elements if e.id not in delta.removed_element_ids]
        
    # 3. Apply Modifications
    if delta.modified_elements:
        for mod in delta.modified_elements:
            target_id = mod.get("id")
            for el in project.elements:
                if el.id == target_id:
                    # Update field dynamically (e.g., position, rotation)
                    # This is a simplified patch logic
                    field = mod.get("field")
                    new_val = mod.get("new_value")
                    if hasattr(el, field):
                        setattr(el, field, new_val)
    
    # 4. Log to history
    project.history.append(delta)
    
    return {
        "status": "committed",
        "bim_state": project.model_dump()
    }

@app.post("/project/export/ifc")
async def export_ifc(project: BIMProjectState):
    """
    Compile the current BIM State into an IFC file for Revit/ArchiCAD import.
    """
    try:
        compiler = IFCCompiler(project)
        filename = f"vesta_export_{project.project_id}.ifc"
        output_path = f"/tmp/{filename}"
        compiler.compile(output_path)
        return FileResponse(
            path=output_path,
            filename=filename,
            media_type="application/x-step"
        )
    except Exception as e:
        return Response(content=f"IFC Export Failed: {str(e)}", status_code=500)

@app.post("/project/export/dxf")
async def export_dxf(project: BIMProjectState):
    """
    Compile the current BIM State into a 2D DXF file for AutoCAD import.
    """
    try:
        import ezdxf
        import math
        
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()
        
        for element in project.elements:
            if element.type == "wall":
                x = element.position.x
                y = element.position.z 
                w = element.dimensions.x
                d = element.dimensions.z
                
                p1 = (x - w/2, y - d/2)
                p2 = (x + w/2, y - d/2)
                p3 = (x + w/2, y + d/2)
                p4 = (x - w/2, y + d/2)
                
                rot_y = element.rotation.y
                
                def rotate_point(px, py, cx, cy, angle):
                    s = math.sin(angle)
                    c = math.cos(angle)
                    px -= cx
                    py -= cy
                    xnew = px * c - py * s
                    ynew = px * s + py * c
                    return xnew + cx, ynew + cy
                
                poly_pts = [p1, p2, p3, p4, p1]
                if rot_y != 0:
                    poly_pts = [rotate_point(px, py, x, y, rot_y) for px, py in poly_pts]
                    
                msp.add_lwpolyline(poly_pts)
        
        filename = f"vesta_export_{project.project_id}.dxf"
        output_path = f"/tmp/{filename}"
        doc.saveas(output_path)
        
        return FileResponse(
            path=output_path,
            filename=filename,
            media_type="application/dxf"
        )
    except Exception as e:
        return Response(content=f"DXF Export Failed: {str(e)}", status_code=500)

# ============================================================================
#  PROJECT PERSISTENCE
# ============================================================================

@app.post("/project/save")
async def save_project(project: BIMProjectState):
    """Persist the current BIM state to the local SQLite store."""
    project_store.save(project)
    return {"status": "saved", "project_id": project.project_id}

@app.get("/project/{project_id}")
async def load_project(project_id: str):
    """Load a saved BIM project by ID."""
    project = project_store.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return {"bim_state": project.model_dump()}

@app.get("/projects")
async def list_projects():
    """Return all saved projects (id, name, updated_at) — no heavy BIM data."""
    return {"projects": project_store.list_projects()}

@app.delete("/project/{project_id}")
async def delete_project(project_id: str):
    deleted = project_store.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    return {"status": "deleted", "project_id": project_id}

# ============================================================================
#  DEMO PROJECT
# ============================================================================

DEMO_PATH = "backend/data/demo_project.json"

@app.get("/project/demo/load")
async def load_demo():
    """Return the pre-built Japandi Penthouse demo so users can try the product instantly."""
    if not os.path.exists(DEMO_PATH):
        raise HTTPException(status_code=404, detail="Demo project file not found.")
    with open(DEMO_PATH, "r") as f:
        data = json.load(f)
    project = BIMProjectState(**data)
    return {
        "project_id": project.project_id,
        "bim_state": project.model_dump(),
        "vision_notes": "Demo loaded: Japandi Penthouse — 10m×8m, 4 rooms, 20 furniture items, flow score 84/100."
    }

# ============================================================================
#  STYLE PROFILE
# ============================================================================

class StyleProfileRequest(BaseModel):
    project_id: str
    style_profile: dict

@app.post("/project/style-profile")
async def update_style_profile(req: StyleProfileRequest):
    """Set the style profile from the onboarding quiz (or manual update)."""
    project = project_store.load(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{req.project_id}' not found.")
    project.style_profile = req.style_profile
    project_store.save(project)
    return {"status": "updated", "style_profile": project.style_profile}

# ============================================================================
#  DESIGN REPORT
# ============================================================================

@app.get("/project/{project_id}/report", response_class=HTMLResponse)
async def design_report(project_id: str):
    """Generate a printable HTML design report for a project."""
    project = project_store.load(project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")
    html = generate_report_html(project)
    return HTMLResponse(content=html, status_code=200)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=25678)
