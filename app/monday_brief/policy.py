"""Typed, internal policy for deterministic demo behavior."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class ScoringWeights:
    gap: float = 1.0
    deadline: float = 1.0
    consequence: float = 1.0


@dataclass(frozen=True, slots=True)
class KnownBelief:
    text: str
    note_id: str


type ShockRange = tuple[float, float]
type ShockTable = Mapping[str, Mapping[str, ShockRange]]


@dataclass(frozen=True, slots=True)
class DemoPolicy:
    meetings: Mapping[str, str]
    known_beliefs: Mapping[str, KnownBelief]
    openings: Mapping[str, str]
    scoring: ScoringWeights
    shocks: ShockTable
    scenario_disclaimer: str


POLICY = DemoPolicy(
    meetings=MappingProxyType(
        {"CL-0003": "Mon 10:30", "CL-0014": "Tue 14:00", "CL-0019": "Thu 09:00"}
    ),
    known_beliefs=MappingProxyType(
        {
            "CL-0003": KnownBelief(text="I have never taken a risk with money.", note_id="N-005"),
            "CL-0014": KnownBelief(
                text="The Hong Kong property market turns this year.", note_id="N-018"
            ),
            "CL-0019": KnownBelief(
                text="The Asia portfolio should be uncorrelated with the Gulf business.",
                note_id="N-025",
            ),
        }
    ),
    openings=MappingProxyType(
        {
            "CL-0003": (
                "Sie wünschen ein sicheres, ruhiges Portfolio. Heute sind jedoch 71,5 % in "
                "Aktien investiert. Darf ich Ihnen die Lücke zeigen?"
            ),
            "CL-0014": (
                "劉先生，您希望保留物業復甦的上升空間，也要確保重建資金。"
                "我們可以先看看信貸額度在不同情境下還有多少緩衝嗎？"
            ),
            "CL-0019": (
                "You asked for the Asia portfolio to diversify the Gulf business. "
                "May I show where shipping conditions now drive both?"
            ),
        }
    ),
    scoring=ScoringWeights(),
    shocks=MappingProxyType(
        {
            "reopens": MappingProxyType(
                {
                    "Shipping": (-0.18, -0.08),
                    "Energy": (-0.12, -0.05),
                    "Gold": (-0.06, -0.02),
                    "Bonds": (0.01, 0.04),
                    "Structured products": (-0.10, -0.03),
                    "Other assets": (-0.01, 0.03),
                    "Cash": (0.0, 0.0),
                }
            ),
            "escalates": MappingProxyType(
                {
                    "Shipping": (0.06, 0.18),
                    "Energy": (0.06, 0.15),
                    "Gold": (0.04, 0.10),
                    "Bonds": (-0.05, -0.01),
                    "Structured products": (-0.08, 0.05),
                    "Other assets": (-0.08, -0.02),
                    "Cash": (0.0, 0.0),
                }
            ),
        }
    ),
    scenario_disclaimer="Precomputed range, not a forecast.",
)
