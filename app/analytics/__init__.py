"""Deterministic fact formulas and the priority scorer.

Owned by Member 4 (data team, analysis and verification). The code here was moved verbatim
from the original ``app/pipeline.py`` monolith (ADR-0002) so that every displayed number has a
tested starting point. Formulas change only in this package; the pipeline publishes them and the
agent layer narrates them.
"""

from app.analytics.facts import AS_OF, BASELINE, SNAPSHOT, fact_engine
from app.analytics.scoring import ScoringWeights, build_priority

__all__ = [
    "AS_OF",
    "BASELINE",
    "SNAPSHOT",
    "ScoringWeights",
    "build_priority",
    "fact_engine",
]
