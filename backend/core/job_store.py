"""
VestaCode Job Store
====================
In-memory async job tracker for non-blocking pipeline execution.
Jobs are keyed by job_id and expire automatically after 1 hour.

Design notes:
  - Single-process only. Upgrade to Redis if you need horizontal scaling.
  - BackgroundTasks run in the same asyncio event loop, so ainvoke works.
  - Expired jobs are pruned lazily on each `create()` call.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional


class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


@dataclass
class Job:
    job_id:      str
    project_id:  str
    user_id:     str
    kind:        str                    # "upload" | "chat"
    status:      JobStatus = JobStatus.PENDING
    current_step: str      = "queued"
    result:      Optional[Dict[str, Any]] = None
    error:       Optional[str]            = None
    created_at:  datetime  = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime]      = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id":       self.job_id,
            "project_id":   self.project_id,
            "kind":         self.kind,
            "status":       self.status,
            "current_step": self.current_step,
            "result":       self.result,
            "error":        self.error,
            "created_at":   self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class JobStore:
    """Thread-safe (asyncio) in-memory job registry."""

    JOB_TTL = timedelta(hours=1)

    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()

    async def create(self, project_id: str, user_id: str, kind: str) -> Job:
        async with self._lock:
            self._prune_expired()
            job = Job(
                job_id=str(uuid.uuid4()),
                project_id=project_id,
                user_id=user_id,
                kind=kind,
            )
            self._jobs[job.job_id] = job
            return job

    async def get(self, job_id: str) -> Optional[Job]:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job_id: str, **kwargs) -> None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for k, v in kwargs.items():
                setattr(job, k, v)
            if kwargs.get("status") in (JobStatus.COMPLETED, JobStatus.FAILED):
                job.completed_at = datetime.now(timezone.utc)

    def _prune_expired(self) -> None:
        cutoff = datetime.now(timezone.utc) - self.JOB_TTL
        expired = [
            jid for jid, j in self._jobs.items()
            if j.status in (JobStatus.COMPLETED, JobStatus.FAILED)
            and j.completed_at
            and j.completed_at < cutoff
        ]
        for jid in expired:
            del self._jobs[jid]
