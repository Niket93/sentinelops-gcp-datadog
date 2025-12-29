# src/security/detectors.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

INJECTION_PATTERNS = [
    r"ignore (all|previous) instructions",
    r"reveal (the )?(system prompt|prompt)",
    r"bypass",
    r"override",
    r"developer message",
    r"show me your hidden",
    r"api key|credentials|secret",
]

HIJACK_PATTERNS = [
    r"\bstop[_ ]?line\b",
    r"\btrigger\b.*\bP1\b",
    r"\bexecute\b.*\balert\b",
    r"\bsend\b.*\bpager\b",
]

@dataclass(frozen=True)
class DetectResult:
    hit: bool
    kind: str
    reason: str

def detect_injection(text: str) -> DetectResult:
    t = (text or "").lower()
    for p in INJECTION_PATTERNS:
        if re.search(p, t):
            return DetectResult(True, "prompt_injection", p)
    return DetectResult(False, "none", "")

def detect_hijack(text: str) -> DetectResult:
    t = (text or "").lower()
    for p in HIJACK_PATTERNS:
        if re.search(p, t):
            return DetectResult(True, "action_hijack", p)
    return DetectResult(False, "none", "")