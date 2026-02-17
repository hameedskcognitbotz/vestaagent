from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import json
import os

class UserPreference(BaseModel):
    category: str  # e.g., "materials", "colors", "brands"
    preference: str
    impact: str    # "positive" (likes) or "negative" (hates)
    confidence: float = 1.0

class EpisodicMemory(BaseModel):
    timestamp: str
    event: str
    decision: str
    reasoning: Optional[str] = None

class LongTermMemory(BaseModel):
    user_id: str
    preferences: List[UserPreference] = Field(default_factory=list)
    history: List[EpisodicMemory] = Field(default_factory=list)
    style_dna: Dict[str, Any] = Field(default_factory=dict)

class MemoryManager:
    def __init__(self, storage_path: str = "backend/data/memory"):
        self.storage_path = storage_path
        os.makedirs(self.storage_path, exist_ok=True)

    def _get_path(self, user_id: str) -> str:
        return os.path.join(self.storage_path, f"{user_id}.json")

    def load_memory(self, user_id: str) -> LongTermMemory:
        path = self._get_path(user_id)
        if os.path.exists(path):
            with open(path, "r") as f:
                return LongTermMemory(**json.load(f))
        return LongTermMemory(user_id=user_id)

    def save_memory(self, memory: LongTermMemory):
        path = self._get_path(memory.user_id)
        with open(path, "w") as f:
            f.write(memory.model_dump_json(indent=2))

    def add_preference(self, user_id: str, pref: UserPreference):
        memory = self.load_memory(user_id)
        # Update or add
        existing = next((p for p in memory.preferences if p.category == pref.category and p.preference == pref.preference), None)
        if existing:
            existing.confidence = (existing.confidence + pref.confidence) / 2
        else:
            memory.preferences.append(pref)
        self.save_memory(memory)
