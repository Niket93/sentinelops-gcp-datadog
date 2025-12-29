from __future__ import annotations
import queue
from dataclasses import dataclass
from typing import Any, Dict


@dataclass(frozen=True)
class Topic:
    name: str


TOPIC_CLIPS = Topic("clips")
TOPIC_OBSERVATIONS = Topic("observations")
TOPIC_DECISIONS = Topic("decisions")
TOPIC_ACTIONS = Topic("actions")


class Bus:
    TOPIC_CLIPS = TOPIC_CLIPS
    TOPIC_OBSERVATIONS = TOPIC_OBSERVATIONS
    TOPIC_DECISIONS = TOPIC_DECISIONS
    TOPIC_ACTIONS = TOPIC_ACTIONS

    def __init__(self) -> None:
        self._q: Dict[str, "queue.Queue[dict[str, Any]]"] = {
            self.TOPIC_CLIPS.name: queue.Queue(),
            self.TOPIC_OBSERVATIONS.name: queue.Queue(),
            self.TOPIC_DECISIONS.name: queue.Queue(),
            self.TOPIC_ACTIONS.name: queue.Queue(),
        }

    def publish(self, topic: Topic, msg: dict[str, Any]) -> None:
        self._q[topic.name].put(msg)

    def consume(self, topic: Topic, timeout_s: float = 1.0) -> dict[str, Any] | None:
        try:
            return self._q[topic.name].get(timeout=timeout_s)
        except queue.Empty:
            return None
    
    def qsize(self, topic: Topic) -> int:
        return int(self._q[topic.name].qsize())