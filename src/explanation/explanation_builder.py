"""
ExplanationBuilder — high-level interface for battery-specific RAG explanations.
Wraps BatteryRAG with domain-specific query construction for each pipeline output.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ExplanationBuilder:
    """
    Builds grounded natural-language explanations for battery pipeline outputs.
    The LLM (Llama 3.1 8B) is loaded lazily on the first explain_* call.
    """

    def __init__(self, project_root: Path):
        from src.explanation.local_rag import BatteryRAG

        self._rag = BatteryRAG(project_root)

    # ── Anomaly explanation ────────────────────────────────────────────────────

    def explain_anomaly(
        self,
        battery_id: str,
        anomaly_records: List[Dict[str, Any]],
    ) -> Tuple[str, List[str]]:
        """Explain what the detected anomalies indicate about degradation state."""
        n = len(anomaly_records)

        if n == 0:
            return (
                f"No anomalies were detected for battery {battery_id}. "
                "The degradation trajectory was smooth and within model expectations.",
                [],
            )

        types = ", ".join(sorted({r.get("anomaly_type", "unknown") for r in anomaly_records}))
        scores = [float(r.get("anomaly_score", 0)) for r in anomaly_records]
        max_score = max(scores)
        top_idx = scores.index(max_score)
        top_cycle = anomaly_records[top_idx].get("cycle_index", "?")

        query = (
            f"Battery {battery_id} has {n} anomalous cycles (types: {types}). "
            f"The highest anomaly score is {max_score:.1f} at cycle {top_cycle}. "
            f"What do these anomaly types indicate about the battery's degradation state? "
            f"Are they cause for concern, or could they reflect normal formation behavior?"
        )
        extra = "Detected anomalies (up to 5 shown):\n" + "\n".join(
            f"  - Cycle {r.get('cycle_index', '?')}: "
            f"score={float(r.get('anomaly_score', 0)):.1f}, "
            f"type={r.get('anomaly_type', '?')}, "
            f"note={r.get('explanation', '')}"
            for r in anomaly_records[:5]
        )
        return self._rag.explain(query, extra_context=extra)

    # ── RUL explanation ────────────────────────────────────────────────────────

    def explain_rul(
        self,
        battery_id: str,
        rul_estimate: float,
        lower: Optional[float] = None,
        upper: Optional[float] = None,
    ) -> Tuple[str, List[str]]:
        """Explain what physical mechanisms drive the RUL estimate."""
        interval_str = (
            f" with a 90% confidence interval of [{lower:.0f}, {upper:.0f}] cycles"
            if lower is not None and upper is not None
            else ""
        )
        query = (
            f"Battery {battery_id} has a predicted remaining useful life of "
            f"{rul_estimate:.0f} cycles{interval_str}. "
            f"What physical degradation mechanisms are likely driving this estimate? "
            f"Which features are most predictive of RUL at this stage of life?"
        )
        extra = (
            f"RUL estimate: {rul_estimate:.1f} cycles\n"
            + (
                f"90% confidence interval: [{lower:.1f}, {upper:.1f}] cycles\n"
                if lower is not None and upper is not None
                else ""
            )
        )
        return self._rag.explain(query, extra_context=extra)

    # ── Risk explanation ───────────────────────────────────────────────────────

    def explain_risk(
        self,
        battery_id: str,
        failure_prob: float,
        risk_category: str,
        horizon_cycles: int = 20,
    ) -> Tuple[str, List[str]]:
        """Explain what the failure risk level means operationally."""
        query = (
            f"Battery {battery_id} has a {risk_category} failure risk: "
            f"{failure_prob * 100:.1f}% probability of reaching end-of-life "
            f"within the next {horizon_cycles} cycles. "
            f"What does this risk level mean operationally? "
            f"What actions are recommended based on this risk classification?"
        )
        extra = (
            f"Failure probability: {failure_prob:.3f}\n"
            f"Risk category: {risk_category}\n"
            f"Prediction horizon: {horizon_cycles} cycles\n"
        )
        return self._rag.explain(query, extra_context=extra)

    # ── Free-form question ─────────────────────────────────────────────────────

    def explain_free(self, question: str) -> Tuple[str, List[str]]:
        """Answer any free-form question grounded in the knowledge base."""
        return self._rag.explain(question)
