from __future__ import annotations

from app.models.metrics import DataSufficiencyLevel
from app.rules.data_sufficiency import assess_data_sufficiency, confidence_ceiling


def test_insufficient_data_below_half_threshold():
    result = assess_data_sufficiency(days_of_data=1, sample_size=2, minimum_days_required=7, minimum_sample_required=30)
    assert result.level == DataSufficiencyLevel.INSUFFICIENT_DATA
    assert "need at least" in result.reason


def test_early_signal_between_half_and_minimum():
    result = assess_data_sufficiency(days_of_data=5, sample_size=20, minimum_days_required=7, minimum_sample_required=30)
    assert result.level == DataSufficiencyLevel.EARLY_SIGNAL


def test_promising_meets_minimum():
    result = assess_data_sufficiency(days_of_data=8, sample_size=35, minimum_days_required=7, minimum_sample_required=30)
    assert result.level == DataSufficiencyLevel.PROMISING


def test_confident_well_beyond_minimum():
    result = assess_data_sufficiency(days_of_data=30, sample_size=200, minimum_days_required=7, minimum_sample_required=30)
    assert result.level == DataSufficiencyLevel.CONFIDENT


def test_confidence_ceiling_caps_insufficient_data_low():
    assert confidence_ceiling(DataSufficiencyLevel.INSUFFICIENT_DATA) == 0.25
    assert confidence_ceiling(DataSufficiencyLevel.CONFIDENT) == 0.95


def test_worst_axis_determines_level():
    # Plenty of days but almost no samples should not be CONFIDENT.
    result = assess_data_sufficiency(days_of_data=60, sample_size=5, minimum_days_required=7, minimum_sample_required=30)
    assert result.level == DataSufficiencyLevel.INSUFFICIENT_DATA
