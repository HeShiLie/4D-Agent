"""Evidence schemas for the Coding Agent pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal


@dataclass
class Observation:
    name: str
    value: Any
    confidence: float
    supporting_frames: list[int] = field(default_factory=list)
    method: str = ""


@dataclass
class Measurement:
    name: str
    value: float
    unit: str = ""
    method: str = ""


@dataclass
class EvidenceBundle:
    execution_status: Literal["success", "partial", "failed"] = "failed"
    observations: list[Observation] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary_text(self) -> str:
        """Human-readable evidence summary for verifier prompt."""
        parts = [f"Status: {self.execution_status}"]
        if self.observations:
            parts.append("Observations:")
            for o in self.observations:
                parts.append(f"  - {o.name}: {o.value} (conf={o.confidence:.2f}, method={o.method})")
        if self.measurements:
            parts.append("Measurements:")
            for m in self.measurements:
                parts.append(f"  - {m.name} = {m.value:.4g} {m.unit} (method={m.method})")
        if self.warnings:
            parts.append("Warnings: " + "; ".join(self.warnings))
        if self.limitations:
            parts.append("Limitations: " + "; ".join(self.limitations))
        return "\n".join(parts)
