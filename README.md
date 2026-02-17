# 🏰 VestaAgent: Architect's Dashboard

Welcome to the future of automated spatial design. **VestaAgent** is an agentic BIM platform that bridges the gap between a 2D sketch and a code-compliant 3D environment.

## 🛠️ System Architecture

### 1. The Backend (Python/LangGraph)
The backend is a **Multi-Agent System (MAS)** where state is managed as a **BIM Project State**.
- **Orchestrator:** Routes requests and handles state transitions.
- **Vision Agent:** Interprets floor plans using VLMs (Gemini/GPT-4o).
- **Compliance Agent:** Validates geometry against IBC/ADA rules.
- **Stylist Agent:** Generates furniture layouts and material palettes.

### 2. The Frontend (React/Three.js)
A real-time 3D studio where agents stream their decisions visually.
- **Three.js Core:** Renders the BIM state into a viewport.
- **Agent Sidebar:** Command-and-control center for HITL (Human-in-the-Loop) feedback.

## 🚦 Getting Started

### Backend
```bash
cd backend
pip install -r requirements.txt
python -m app.main
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

---
*Created by the VestaAgent Architecture Team (AI Architect & Interior Designer)*
