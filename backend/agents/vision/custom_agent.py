"""
VestaCode Custom Vision Agent
==============================
Replaces LLM-based floor plan analysis with a locally-trained YOLOv11 model.

Usage:
    # Standalone
    agent = CustomVisionAgent("models/floorplan_best.pt")
    extraction = await agent.process_plan(image_bytes)
    
    # Integrated (set env var)
    VESTA_VISION_MODEL=custom python3 backend/app/main.py
"""

import numpy as np
import cv2
import uuid
import math
import os
from typing import List, Optional
from backend.agents.vision.schema import VisionExtraction, DetectedWall, DetectedOpening
from backend.core.bim_state import BIMElement, ObjectType, Vector3


# Class mapping (must match training config in training_guide.py)
CLASS_NAMES = {
    0: "wall",
    1: "door", 
    2: "window",
    3: "room",
    4: "stairs",
    5: "bathroom_fixture",
    6: "kitchen_fixture",
}


class CustomVisionAgent:
    """
    Custom-trained vision model for floor plan analysis.
    Uses YOLOv11-seg instead of LLM for deterministic, fast detection.
    
    Advantages over LLM-based Vision Agent:
    ┌───────────────────┬──────────────────┬──────────────────┐
    │ Feature           │ LLM (Groq/Gemini)│ Custom YOLO      │
    ├───────────────────┼──────────────────┼──────────────────┤
    │ Speed             │ 3-15 seconds     │ 50-200ms         │
    │ Consistency       │ Non-deterministic│ Deterministic    │
    │ Cost              │ API call ($)     │ Free (local)     │
    │ Offline           │ ✗                │ ✓                │
    │ Pixel accuracy    │ Approximate      │ Pixel-perfect    │
    │ Complex plans     │ Limited          │ Scales well      │
    │ Setup effort      │ Zero             │ Dataset + train  │
    └───────────────────┴──────────────────┴──────────────────┘
    """
    
    def __init__(self, model_path: str = "backend/models/floorplan_best.pt"):
        if not os.path.exists(model_path):
            raise FileNotFoundError(
                f"Custom vision model not found at '{model_path}'. "
                f"Train one using: python3 training_guide.py train"
            )
        
        # Import here to avoid requiring ultralytics when not using custom model
        from ultralytics import YOLO
        self.model = YOLO(model_path)
        self.confidence_threshold = 0.4
        self.iou_threshold = 0.5
        # Default scale: 1 pixel = 0.02 meters (50px per meter)
        self.scale = 0.02
        print(f"✅ Custom Vision Model loaded: {model_path}")
    
    def _estimate_scale(self, image: np.ndarray, detections: list) -> float:
        """
        Auto-calibrate pixel-to-meter scale from detected doors.
        Uses standard door width (0.8m) as reference measurement.
        """
        door_widths_px = []
        for det in detections:
            if det["class"] == "door":
                w = det["bbox"][2] - det["bbox"][0]
                h = det["bbox"][3] - det["bbox"][1]
                door_widths_px.append(min(w, h))
        
        if door_widths_px:
            avg_door_px = np.mean(door_widths_px)
            if avg_door_px > 0:
                self.scale = 0.8 / avg_door_px
        
        return self.scale
    
    async def process_plan(self, image_bytes: bytes) -> VisionExtraction:
        """
        Process floor plan image and extract geometry.
        Returns the same VisionExtraction schema as the LLM-based agent.
        """
        
        # 1. Decode image
        is_pdf = image_bytes.startswith(b"%PDF")
        if is_pdf:
            import fitz
            doc = fitz.open(stream=image_bytes, filetype="pdf")
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            if pix.n == 4:  # RGBA → RGB
                img_array = img_array[:, :, :3]
            doc.close()
        else:
            img_array = np.frombuffer(image_bytes, dtype=np.uint8)
            img_array = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        if img_array is None:
            raise ValueError("Failed to decode image")
        
        # 2. Run YOLO inference
        results = self.model.predict(
            img_array,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            imgsz=1024,
            verbose=False
        )[0]
        
        # 3. Parse all detections
        detections = []
        for i, box in enumerate(results.boxes):
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            
            det = {
                "class": CLASS_NAMES.get(cls_id, "unknown"),
                "confidence": conf,
                "bbox": [x1, y1, x2, y2],
                "mask": None
            }
            
            # Get segmentation mask polygon if available
            if results.masks is not None and i < len(results.masks):
                det["mask"] = results.masks[i].xy[0].tolist()
            
            detections.append(det)
        
        # 4. Auto-calibrate scale from detected doors
        scale = self._estimate_scale(img_array, detections)
        
        # 5. Convert detections to VestaAgent schema
        walls = []
        openings = []
        room_labels = []
        
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            cx = (x1 + x2) / 2 * scale
            cy = (y1 + y2) / 2 * scale
            w = (x2 - x1) * scale
            h = (y2 - y1) * scale
            
            if det["class"] == "wall":
                if w > h:
                    # Horizontal wall
                    walls.append(DetectedWall(
                        start=[cx - w/2, cy],
                        end=[cx + w/2, cy],
                        thickness=max(h, 0.1),
                        is_load_bearing=(h > 0.15)
                    ))
                else:
                    # Vertical wall
                    walls.append(DetectedWall(
                        start=[cx, cy - h/2],
                        end=[cx, cy + h/2],
                        thickness=max(w, 0.1),
                        is_load_bearing=(w > 0.15)
                    ))
            
            elif det["class"] == "door":
                openings.append(DetectedOpening(
                    type="door",
                    position=[cx, cy],
                    width=round(min(w, h), 2),
                    rotation=0 if w > h else 90
                ))
            
            elif det["class"] == "window":
                openings.append(DetectedOpening(
                    type="window",
                    position=[cx, cy],
                    width=round(max(w, h), 2),
                    rotation=0 if w > h else 90
                ))
            
            elif det["class"] == "room":
                room_labels.append(f"Room at ({cx:.1f}, {cy:.1f})")
        
        # 6. Build result
        n_doors = len([o for o in openings if o.type == "door"])
        n_windows = len([o for o in openings if o.type == "window"])
        avg_conf = np.mean([d["confidence"] for d in detections]) if detections else 0.5
        
        notes = (
            f"[Custom Model] Detected {len(walls)} walls, "
            f"{n_doors} doors, {n_windows} windows. "
            f"Rooms found: {', '.join(room_labels) if room_labels else 'N/A'}. "
            f"Total: {len(room_labels)} rooms. "
            f"Scale: {scale:.4f} m/px. "
            f"Avg confidence: {avg_conf:.2f}."
        )
        
        # Fallback: ensure at least basic geometry
        if not walls:
            walls = [
                DetectedWall(start=[0, 0], end=[10, 0], thickness=0.2, is_load_bearing=True),
                DetectedWall(start=[10, 0], end=[10, 8], thickness=0.2, is_load_bearing=True),
                DetectedWall(start=[10, 8], end=[0, 8], thickness=0.2, is_load_bearing=True),
                DetectedWall(start=[0, 8], end=[0, 0], thickness=0.2, is_load_bearing=True),
            ]
            notes += " [FALLBACK: Using default walls due to low detection count.]"
        
        return VisionExtraction(
            walls=walls,
            openings=openings,
            scale_ratio=scale,
            confidence_score=round(avg_conf, 2),
            notes=notes
        )
    
    async def refine_structure(self, project, user_message: str) -> VisionExtraction:
        """
        For structural refinement via chat, fall back to LLM
        since the custom model only handles image input.
        """
        from backend.core.llm_factory import get_llm
        llm = get_llm(agent_name="vision", temperature=0.1)
        
        # Delegate text-based refinement to LLM
        from backend.agents.vision.agent import VisionAgent
        fallback = VisionAgent.__new__(VisionAgent)
        fallback.llm = llm
        return await fallback.refine_structure(project, user_message)
