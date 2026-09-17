#!/usr/bin/env python3
"""PACMAN-inspired supervisory layer for TCT.

Architecture borrowed, not implementation: diagnostics -> predictor proposals ->
latency/safety arbitration -> actuator command. Mirnov/toroidal remains the TCT
precursor authority. The supervisor fails closed: if physical-time calibration,
precursor confidence, latency, or safety is inadequate, standing bias remains
and the bounded boost is NOT authorized.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(frozen=True)
class DiagnosticFrame:
    precursor_detected: bool
    precursor_kind: str
    confidence: float
    lead_ms: Optional[float]
    physical_time_calibrated: bool


@dataclass(frozen=True)
class ActuatorState:
    standing_bias_active: bool
    healthy: bool
    boost_available: bool
    response_budget_ms: float
    safety_margin_ms: float = 0.25


@dataclass(frozen=True)
class Proposal:
    controller: str
    action: str
    priority: int
    reason: str


@dataclass(frozen=True)
class Decision:
    action: str
    standing_bias: bool
    bounded_boost: bool
    reason: str
    available_lead_ms: Optional[float]
    required_lead_ms: float
    winning_controller: str

    def as_dict(self) -> dict:
        return asdict(self)


def precursor_proposal(frame: DiagnosticFrame, confidence_floor: float = 0.5) -> Proposal:
    if frame.precursor_kind not in {"mirnov", "mirnov_toroidal", "oracle"}:
        return Proposal("precursor", "NO_ACTION", 100, "non-authoritative trigger source")
    if not frame.precursor_detected:
        return Proposal("precursor", "NO_ACTION", 100, "no precursor")
    if frame.confidence < confidence_floor:
        return Proposal("precursor", "NO_ACTION", 100, "precursor confidence below floor")
    return Proposal("precursor", "REQUEST_BOOST", 50, "authoritative precursor accepted")


def arbitrate(frame: DiagnosticFrame, actuator: ActuatorState,
              proposals: list[Proposal], confidence_floor: float = 0.5) -> Decision:
    required = actuator.response_budget_ms + actuator.safety_margin_ms
    deny = [p for p in proposals if p.action == "NO_ACTION" and p.priority >= 100]
    request = [p for p in proposals if p.action == "REQUEST_BOOST"]

    reason = None
    if not frame.physical_time_calibrated:
        reason = "NO ACTION: physical-time calibration absent"
    elif not actuator.standing_bias_active:
        reason = "NO ACTION: standing preventative bias absent"
    elif not actuator.healthy or not actuator.boost_available:
        reason = "NO ACTION: actuator unavailable or unhealthy"
    elif frame.lead_ms is None:
        reason = "NO ACTION: precursor lead unavailable"
    elif frame.lead_ms < required:
        reason = "NO ACTION: precursor is too late for bounded boost"
    elif deny:
        reason = "NO ACTION: " + deny[0].reason
    elif not request:
        reason = "NO ACTION: no controller requested bounded boost"

    if reason:
        return Decision("STANDING_BIAS_ONLY", True, False, reason,
                        frame.lead_ms, required, "safety_arbiter")
    winner = sorted(request, key=lambda p: p.priority, reverse=True)[0]
    return Decision("STANDING_BIAS_PLUS_BOUNDED_BOOST", True, True,
                    winner.reason, frame.lead_ms, required, winner.controller)


def decide(frame: DiagnosticFrame, actuator: ActuatorState,
           confidence_floor: float = 0.5) -> Decision:
    return arbitrate(frame, actuator,
                     [precursor_proposal(frame, confidence_floor)], confidence_floor)
