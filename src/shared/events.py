# src/shared/events.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, Field

UseCase = Literal["security"]


def new_id() -> str:
    return str(uuid.uuid4())


class ClipEvent(BaseModel):
    clip_id: str = Field(default_factory=new_id)
    trace_id: str = Field(default_factory=new_id)
    dd_trace_id: int = 0
    dd_parent_id: int = 0
    camera_id: str
    use_case: UseCase = "security"
    clip_index: int
    clip_start_ts: datetime
    clip_end_ts: datetime
    clip_path: str


class ObservationEvent(BaseModel):
    observation_id: str = Field(default_factory=new_id)
    trace_id: str
    dd_trace_id: int = 0
    dd_parent_id: int = 0
    clip_id: str
    camera_id: str
    use_case: UseCase = "security"
    clip_index: int
    ts: datetime
    summary: str
    signals: Dict[str, Any] = Field(default_factory=dict)
    model: Dict[str, Any] = Field(default_factory=dict)


class DecisionEvent(BaseModel):
    decision_id: str = Field(default_factory=new_id)
    trace_id: str
    dd_trace_id: int = 0
    dd_parent_id: int = 0
    clip_id: str
    observation_id: str
    camera_id: str
    use_case: UseCase = "security"
    clip_index: int
    ts: datetime
    assessment: Dict[str, Any]
    recommended_actions: List[Dict[str, Any]]
    rationale: Dict[str, Any] = Field(default_factory=dict)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    model: Dict[str, Any] = Field(default_factory=dict)


class ActionEvent(BaseModel):
    action_id: str = Field(default_factory=new_id)
    trace_id: str
    dd_trace_id: int = 0
    dd_parent_id: int = 0
    decision_id: str
    camera_id: str
    use_case: UseCase = "security"
    ts: datetime
    action: Dict[str, Any]
    status: Literal["sent", "skipped", "failed"]
    provider: str
    error: Optional[str] = None