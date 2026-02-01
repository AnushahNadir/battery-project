from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.pipeline.validation import ValidationReport


@dataclass
class ConfidenceReport:
    confidence: float
    components: Dict[str, float]
    notes: List[str]

    def to_dict(self) -> Dict:
        return {
            "confidence": self.confidence,
            "components": self.components,
            "notes": self.notes,
        }


def compute_confidence(
    *,
    schema_match_ratio: float,
    pattern_agreement_ratio: float,
    validation: ValidationReport,
) -> ConfidenceReport:
    """
    Deterministic confidence score in [0,1].

    Inputs:
      - schema_match_ratio: how many canonical columns successfully mapped (0..1)
      - pattern_agreement_ratio: how strongly value-hints supported the mapping (0..1)
      - validation: pass/fail signals for schema/physics/structure
    """
    notes: List[str] = []

    # Convert validation to a score
    validation_score = 0.0
    validation_score += 0.40 if validation.schema_ok else 0.0
    validation_score += 0.35 if validation.structure_ok else 0.0
    validation_score += 0.25 if validation.physics_ok else 0.0

    if not validation.schema_ok:
        notes.append("Schema validation failed")
    if not validation.structure_ok:
        notes.append("Structural validation failed")
    if not validation.physics_ok:
        notes.append("Physics validation failed")

    # Weighted blend (tweakable)
    w_schema = 0.40
    w_pattern = 0.25
    w_validation = 0.35

    confidence = (
        w_schema * schema_match_ratio
        + w_pattern * pattern_agreement_ratio
        + w_validation * validation_score
    )

    # Clamp
    confidence = max(0.0, min(1.0, float(confidence)))

    components = {
        "schema_match_ratio": float(schema_match_ratio),
        "pattern_agreement_ratio": float(pattern_agreement_ratio),
        "validation_score": float(validation_score),
    }

    return ConfidenceReport(confidence=confidence, components=components, notes=notes)

