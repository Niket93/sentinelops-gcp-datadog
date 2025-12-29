# src/obs/tokens.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class TokenCost:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float

def estimate_tokens(text: str) -> int:
    t = (text or "").strip()
    if not t:
        return 0
    return max(1, len(t) // 4)

def estimate_cost(input_tokens: int, output_tokens: int, cost_per_1k_input: float, cost_per_1k_output: float) -> TokenCost:
    it = max(0, int(input_tokens))
    ot = max(0, int(output_tokens))
    ic = (it / 1000.0) * float(cost_per_1k_input)
    oc = (ot / 1000.0) * float(cost_per_1k_output)
    return TokenCost(
        input_tokens=it,
        output_tokens=ot,
        total_tokens=it + ot,
        input_cost=ic,
        output_cost=oc,
        total_cost=ic + oc,
    )