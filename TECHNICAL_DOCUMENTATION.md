# VestaAgent Technical Documentation

## 1. System Overview

VestaAgent is an autonomous design platform that converts 2D floor plans into 3D BIM (Building Information Modeling) environments using a Multi-Agent System (MAS).

### Key Components

- **Backend**: Python-based service using FastAPI and LangGraph for agent orchestration.
- **Frontend**: React application with Vite, using Three.js (@react-three/fiber) for 3D visualization.
- **AI/ML**: Integrates with LLMs (Gemini/Groq) for vision and reasoning tasks.

## 2. Directory Structure

```
/home/cognitbotz/vestaagent/
├── backend/                  # Python Backend
│   ├── agents/               # Individual Agent Implementations
│   │   ├── compliance/       # Regulatory checks (IBC/ADA)
│   │   ├── memory_refinery/  # Long-term memory management
│   │   ├── orchestrator/     # Main control graph (LangGraph)
│   │   ├── sourcing/         # Product sourcing logic
│   │   ├── stylist/          # Design aesthetics and furnishing
│   │   └── vision/           # Plan interpretation (VLM)
│   ├── app/                  # FastAPI Application
│   │   └── main.py           # Entry point
│   ├── core/                 # Core utilities and data structures
│   │   ├── bim_state.py      # BIMProjectState definition
│   │   ├── llm_factory.py    # LLM provider management
│   │   ├── memory.py         # Memory primitives
│   │   └── spatial_engine.py # Geometry processing
│   └── requirements.txt      # Python dependencies
├── frontend/                 # React Frontend
│   ├── src/                  # Source code
│   └── vite.config.ts        # Vite configuration
├── vesta.md                  # PRD / High-level Overview
└── README.md                 # Quick start guide
```

## 3. Setup and Running

### Prerequisites

- Python 3.10+
- Node.js & npm/bun

### Backend Setup

1. **Navigate to the project root:**
   ```bash
   cd /home/cognitbotz/vestaagent
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```
   *Note: Ensure you are installing from the project root.*

3. **Run the Backend Server:**
   **CRITICAL:** You must run the server from the **project root** directory so that the `backend` module is correctly resolved.
   ```bash
   python -m backend.app.main
   ```
   The server will start at `http://0.0.0.0:25678`.

   *Common Error:* If you run `python -m app.main` from inside the `backend` folder, you will get `ModuleNotFoundError: No module named 'backend'`. Always run from the root.

### Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   npm install
   ```

3. **Run the Development Server:**
   ```bash
   npm run dev
   ```
   The frontend will be available at `http://localhost:5173`.

## 4. Backend Architecture Details

### Agents

The system uses a graph-based orchestration (LangGraph) found in `backend/agents/orchestrator/graph.py`.

- **Orchestrator**: The central node that routes tasks based on the current state.
- **Vision Agent**: Analyzes uploaded images (floor plans) to extract geometry.
- **Stylist Agent**: Suggests furniture and materials based on user input or style descriptions.
- **Compliance Agent**: Checks the generated model against predefined rules.
- **Sourcing Agent**: Handles product identification (simulated or API-based).

### State Management

The core state is defined in `backend/core/bim_state.py` as `BIMProjectState`. Key fields include:

- `project_id` & `name`: Project identifiers.
- `elements`: List of `BIMElement` (Walls, Doors, Furniture). each with position/rotation/dimensions.
- `rooms`: List of `Room` definitions (floor polygons).
- `style_profile`: Dictionary containing design preferences (e.g., "Contemporary Minimalist").
- `compliance_logs`: List of regulatory check results.
- `budget_total`: Current estimated cost.

### API Endpoints (`backend/app/main.py`)

- `POST /project/upload-plan`: Upload a floor plan image to start a project.
- `POST /project/chat`: meaningful interaction with the agents (e.g., "Move the sofa").
- `GET /llm/status`: Check status of configured LLM providers.
- `POST /llm/provider`: Switch the global LLM provider (Groq/Gemini).

## 5. Troubleshooting

### ModuleNotFoundError: No module named 'backend'
**Cause:** Running the python script from the wrong directory.
**Fix:** Run `python -m backend.app.main` from the **root** folder (`/home/cognitbotz/vestaagent`).

### API Connection Failed
**Cause:** Frontend cannot reach Backend.
**Fix:** 
- Ensure Backend is running on port `25678`.
- Check `frontend/vite.config.ts` proxy settings. It currently proxies `/api` to `http://localhost:25678`.
