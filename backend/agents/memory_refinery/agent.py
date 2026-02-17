from langchain_groq import ChatGroq
from backend.core.llm_factory import get_llm
from typing import List, Dict, Any
import json
from backend.core.memory import UserPreference, EpisodicMemory

MEMORY_REFINERY_PROMPT = """
You are the 'Cognitive Bridge' for VestaAgent. Your role is to analyze a conversation 
between a designer and an AI team and extract lasting memories.

### Extract:
1. **User Preferences**: (e.g., "Hates velvet", "Prefers sustainable oak").
2. **Episodic Events**: Key decisions made (e.g., "Approved the open plan layout but rejected the island position").

### Rules:
- Be objective.
- Only extract high-confidence facts.
- Output ONLY a JSON object.

### Schema:
{
  "preferences": [{"category": "materials", "preference": "velvet", "impact": "negative", "confidence": 0.9}],
  "events": [{"event": "Layout approval", "decision": "approved", "reasoning": "Liked the flow"}]
}
"""

class MemoryRefineryAgent:
    def __init__(self, model_name: str = None):
        self.llm = get_llm(agent_name="memory", model=model_name, temperature=0)

    async def refine_memory(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        chat_history = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        
        response = await self.llm.ainvoke([
            {"role": "system", "content": MEMORY_REFINERY_PROMPT},
            {"role": "user", "content": f"Recent Conversation:\n{chat_history}"}
        ])
        
        try:
            content = response.content
            if not content or not isinstance(content, str):
                return {"preferences": [], "events": []}
                
            if "```json" in content:
                content = content.split("```json")[-1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[-1].split("```")[0].strip()
            
            if not content.strip():
                return {"preferences": [], "events": []}
                
            return json.loads(content)
        except Exception as e:
            print(f"Memory refinery failed: {e}")
            return {"preferences": [], "events": []}
