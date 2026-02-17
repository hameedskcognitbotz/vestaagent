## 📄 PRD: "VestaAgent" – Agentic 2D-to-3D Design Platform

### 1. Executive Summary

**VestaAgent** is an autonomous design platform that converts 2D floor plans into fully furnished, editable 3D BIM (Building Information Modeling) environments. Unlike existing visualizers, it uses **multi-agent orchestration** to source real products, verify building codes, and manage project timelines.

---

### 2. User Personas

| **Persona**               | **Pain Point**                                           | **Platform Value**                                    |
| ------------------------------- | -------------------------------------------------------------- | ----------------------------------------------------------- |
| **Boutique Designer**     | Manual 3D modeling takes 10+ hours per project.                | Converts a sketch to a 3D model in < 5 mins.                |
| **Real Estate Developer** | Hard to visualize "potential" of shell units for buyers.       | Instant "Virtual Staging" with real, purchasable furniture. |
| **Project Manager**       | Sourcing furniture that is actually "in-stock" is a nightmare. | Agent autonomously checks vendor stock and lead times.      |

---

### 3. Functional Requirements

#### **Phase 1: Perception (2D to 3D Reconstruction)**

* **FR1.1: Multi-Format Upload:** Support for PDF blueprints, hand-drawn sketches (JPG/PNG), and .DWG files.
* **FR1.2: Structural Intelligence:** Agent must identify:
  * Load-bearing vs. partition walls.
  * Standard door/window dimensions.
  * Utility points (plumbing stacks, electrical outlets).
* **FR1.3: Autonomous Extrusion:** Generate a 3D "white box" model with 98% dimensional accuracy from 2D inputs.

#### **Phase 2: Cognitive Reasoning (Agentic Design)**

* **FR2.1: Style Interpretation:** Use "Vision-Language Models" to analyze a client’s Pinterest board and map it to a "Design DNA" (colors, textures, eras).
* **FR2.2: Autonomous Layout Agent:** Populate the 3D model with furniture based on **ergonomic rules** (e.g., "ensure 36-inch clearance around dining tables").
* **FR2.3: Regulatory Guardrails:** Cross-reference local building codes (IBC/ADA) for stair widths and bathroom clearances.

#### **Phase 3: Execution (Sourcing & Delivery)**

* **FR3.1: Live-Stock Sourcing Agent:** Connect to APIs (Wayfair, West Elm, Kohler) to find real products matching the 3D assets.
* **FR3.2: Procurement Orchestrator:** Create a "One-Click Cart" that populates purchase orders with quantities, finishes, and shipping estimates.

---

### 4. Technical Architecture

* **Core Logic:**  **Multi-Agent System (MAS)** .
  * *Agent A (The Architect):* Handles geometry and BIM data.
  * *Agent B (The Stylist):* Handles textures, lighting, and aesthetics.
  * *Agent C (The Buyer):* Handles API calls to vendors and budget tracking.
* **Backend:** Python/FastAPI with LangGraph for agent orchestration.
* **Frontend:** WebGL/Three.js for in-browser 3D editing.
* **AI Models:** * **Vision:** GPT-4o or Gemini 1.5 Pro (for plan analysis).
  * **3D Generation:** Gaussian Splatting or specialized Diffusion models for texture mapping.

---

### 5. Success Metrics (KPIs)

* **Time-to-Model:** Reduce manual 3D drafting time from  **8 hours to < 10 minutes** .
* **Conversion Accuracy:** % of auto-identified walls that require manual correction (Target:  **< 5%** ).
* **Sourcing Match Rate:** % of AI-suggested furniture that the user keeps in the final design (Target:  **> 60%** ).

---

### 6. Roadmap

* **Q1:** MVP — 2D Photo to 3D White-box conversion.
* **Q2:** Integration of "Style Agent" for automated furnishing.
* **Q3:** Beta release of the "Sourcing Agent" with 5 major vendor APIs.
* **Q4:** Export compatibility for Revit, SketchUp, and Rhino.

# 🏗️ 1. Technical Architecture Diagram

The architecture is structured as a **Directed Acyclic Graph (DAG)** where each node is a specialized agent and the "State" is the shared memory (the project file).

**Code snippet**

```
graph TD
    User((Designer)) -->|Uploads Floor Plan| Orchestrator{Orchestrator Agent}
  
    subgraph "Perception Layer"
        Orchestrator --> VisionAgent[Vision Agent: Plan Interpreter]
        VisionAgent -->|Extracted Geometry| BIMAgent[BIM Agent: 3D Reconstructor]
    end

    subgraph "Reasoning Layer"
        BIMAgent -->|3D Model| GuardrailAgent[Code & Compliance Agent]
        GuardrailAgent -->|Non-compliant?| BIMAgent
        GuardrailAgent -->|Compliant| StylistAgent[Stylist Agent: Aesthetic Matching]
    end

    subgraph "Execution Layer"
        StylistAgent --> SourcingAgent[Sourcing Agent: API Procurement]
        SourcingAgent -->|Stock Check| BudgetAgent[Budget & Timeline Agent]
    end

    BudgetAgent -->|Final Proposal| HumanGate[Human-in-the-Loop Approval]
    HumanGate -->|Approved| Client((End Client))
    HumanGate -->|Changes Needed| Orchestrator
```

### Key Components:

* **The Orchestrator:** Acts as the "Project Manager." It routes tasks and manages the "State" (a JSON object containing walls, furniture, costs, and compliance logs).
* **Vision Agent:** Uses a Vision-Language Model (VLM) like Gemini 1.5 Pro to identify symbols (toilets, swings of doors) and dimensions.
* **BIM Agent:** Converts 2D coordinates into 3D objects (walls, floors, ceilings) with semantic tags.

---

## 🛡️ 2. Regulatory Guardrails (The "Safety" Layer)

This is the most critical part of an "Agentic" system. You cannot let an AI suggest a layout that is illegal or unsafe.

### A. The "Code-as-Code" Engine

Instead of the AI "guessing" if a hallway is wide enough, the **Guardrail Agent** uses a symbolic rule-engine:

* **Input:** The 3D model geometry.
* **Logic:** It queries a database of IBC (International Building Code) and ADA (Americans with Disabilities Act) standards.
* **Function:** `check_clearance(object1, object2)` -> If distance < 36", flag a violation.

### B. Proactive vs. Reactive Guardrails

| **Guardrail Type**   | **Execution Point** | **Example Action**                                                 |
| -------------------------- | ------------------------- | ------------------------------------------------------------------------ |
| **Input Guardrail**  | Pre-processing            | Rejects the floor plan if it’s too blurry or missing a scale bar.       |
| **Logic Guardrail**  | Mid-design                | Prevents the Stylist Agent from placing a rug over a floor heating vent. |
| **Output Guardrail** | Final Review              | Flags if the total FF&E (Furniture) exceeds the client's $50k budget.    |

---

## 🛠️ 3. Implementation Stack (2026)

* **Framework:** **LangGraph** (for the state machine and loops).
* **3D Engine:** **Three.js** (frontend visualization) + **Blender/Python API** (backend geometry processing).
* **Compliance DB:** **Pinecone (Vector DB)** containing chunks of building codes for RAG (Retrieval-Augmented Generation).
* **Sourcing:** **Unified Sourcing API** (e.g., a middleware that aggregates APIs from Crate & Barrel, West Elm, etc.).

---

## 🚦 HITL Strategy: The Three "Intervention" Points

### 1. The "Ambiguity" Trap (Pre-Design)

The Agent pauses when it lacks the context to proceed with 100% certainty.

* **The Trigger:** The Vision Agent identifies a wall but can't tell if it’s a 12" structural column or a decorative bump-out.
* **The HITL Interaction:** The system highlights the area in red on the 2D plan.
* **The Prompt:** *"I’ve identified an anomaly in the Living Room North Wall. Is this a load-bearing column or a closet? (Estimated impact on layout: High)"*

### 2. The "Aesthetic Pivot" (Mid-Design)

Design is subjective. The Agent shouldn't finish a whole house in "Minimalist" if the designer hates the specific wood tone chosen.

* **The Trigger:** The Stylist Agent completes the first "Zone" (e.g., the Foyer).
* **The HITL Interaction:** A "Stop-and-Go" checkpoint. The designer reviews the 3D materials and lighting.
* **The Action:** The designer can say, *"Less oak, more walnut,"* and the Agent propagates that change across all remaining rooms automatically.

### 3. The "Financial & Legal" Gatekeeper (Post-Design)

The Agent is ready to execute, but it needs a "Human Signature."

* **The Trigger:** The Sourcing Agent has filled the cart with $42,000 of furniture.
* **The HITL Interaction:** A side-by-side comparison dashboard.
  * **Left Side:** AI's optimized selection (Best price/Lead time).
  * **Right Side:** Designer’s "Swap" options.
* **The Action:** The designer clicks **"Finalize & Send to Client,"** which triggers the automated email and invoice.

---

## 🛠️ Feature Requirement: The "Agentic Chat" Sidebar

To make HITL seamless, your platform needs a **Command & Control** sidebar where the designer talks to the sub-agents.

| **Agent**           | **What the Designer Sees** | **Common Command**                                                               |
| ------------------------- | -------------------------------- | -------------------------------------------------------------------------------------- |
| **Architect Agent** | "Verifying 3D mesh..."           | *"Move that partition wall 2 feet to the left and re-calculate the floor area."*     |
| **Stylist Agent**   | "Generating Mood A & B..."       | *"I like the layout of Option A, but use the color palette from Option B."*          |
| **Sourcing Agent**  | "Checking lead times..."         | *"The sofa is 16 weeks out. Find me a similar velvet option that ships in 4 weeks."* |

---

## ⚠️ The "Rollback" Protocol

The most important technical part of HITL is the  **Version Control** .

If a designer hates what the Agent did in the last 10 minutes, they need a **"Design Git"** style rollback.

> **PRD Requirement:** "The system must allow for granular rollbacks. A user can undo 'Furniture Placement' without losing 'Wall Modifications' made in the same session."

---
