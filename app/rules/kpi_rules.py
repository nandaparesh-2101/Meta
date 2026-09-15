"""KPI evaluation rules: is a metric good, borderline, or bad relative to the
business's own targets? These rules never hardcode a "good CTR" number —
performance is only meaningful relative to `KPIConfiguration`.
"""

from __future__ import annotations

from enum import Enum

from app.models.business import KPIConfiguration


class KPIStatus(str, Enum):
    ON_TARGET = "on_target"
    BORDERLINE = "borderline"
    OFF_TARGET = "off_target"
    NOT_CALCULABLE = "not_calculable"


def evaluate_cpl(cpl: float | None, kpis: KPIConfiguration, tolerance: float = 0.15) -> KPIStatus:
    if cpl is None:
        return KPIStatus.NOT_CALCULABLE
    if cpl <= kpis.target_cpl:
        return KPIStatus.ON_TARGET
    if cpl <= kpis.target_cpl * (1 + tolerance):
        return KPIStatus.BORDERLINE
    return KPIStatus.OFF_TARGET


def evaluate_qualified_cpl(
    qualified_cpl: float | None, kpis: KPIConfiguration, tolerance: float = 0.15
) -> KPIStatus:
    if qualified_cpl is None:
        return KPIStatus.NOT_CALCULABLE
    if qualified_cpl <= kpis.target_qualified_cpl:
        return KPIStatus.ON_TARGET
    if qualified_cpl <= kpis.target_qualified_cpl * (1 + tolerance):
        return KPIStatus.BORDERLINE
    return KPIStatus.OFF_TARGET


def evaluate_cac(cac: float | None, kpis: KPIConfiguration, tolerance: float = 0.15) -> KPIStatus:
    if cac is None:
        return KPIStatus.NOT_CALCULABLE
    if cac <= kpis.target_cac:
        return KPIStatus.ON_TARGET
    if cac <= kpis.target_cac * (1 + tolerance):
        return KPIStatus.BORDERLINE
    return KPIStatus.OFF_TARGET


def evaluate_roas(roas: float | None, kpis: KPIConfiguration, tolerance: float = 0.15) -> KPIStatus:
    if roas is None:
        return KPIStatus.NOT_CALCULABLE
    if roas >= kpis.target_roas:
        return KPIStatus.ON_TARGET
    if roas >= kpis.target_roas * (1 - tolerance):
        return KPIStatus.BORDERLINE
    return KPIStatus.OFF_TARGET
