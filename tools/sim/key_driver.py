"""Evidence-backed ADC classification from the resident M30 key driver.

The driver supplies the normalized value table from RAM, so this module keeps
those values caller-provided and does not assign physical button names.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


ADC_SAMPLE_MASK = 0x7F
ADC_THRESHOLDS: tuple[int, ...] = (0x03, 0x18, 0x2A, 0x3A, 0x4A, 0x5F, 0x6F)
UNMAPPED_KEY_VALUE = 0xFF


@dataclass(frozen=True)
class AdcClassification:
    """One normalized result without assigning a physical key name."""

    sampled_value: int
    normalized_value: int
    override_applied: bool


def classify_adc_sample(
    sample: int,
    normalized_values: Sequence[int],
    *,
    override: bool = False,
    override_value: int | None = None,
) -> AdcClassification:
    """Apply the recovered threshold loop to one hardware sample.

    The firmware masks the hardware value to seven bits, returns the first
    RAM-table value whose threshold is greater than the sample, and returns
    ``0xff`` when no threshold matches. Its override path replaces the sample
    with zero and returns a separate RAM-table value; that value is explicit
    here because the driver does not initialize the table itself.
    """
    if not 0 <= sample <= 0xFF:
        raise ValueError("ADC sample must fit an unsigned byte")
    if len(normalized_values) != len(ADC_THRESHOLDS):
        raise ValueError("key normalization table must contain seven values")
    if any(not 0 <= value <= 0xFF for value in normalized_values):
        raise ValueError("normalized key values must fit an unsigned byte")
    if override_value is not None and not 0 <= override_value <= 0xFF:
        raise ValueError("override key value must fit an unsigned byte")

    if override:
        if override_value is None:
            raise ValueError("override path requires an explicit table value")

        return AdcClassification(0, override_value, True)

    sampled_value = sample & ADC_SAMPLE_MASK
    for threshold, normalized_value in zip(ADC_THRESHOLDS, normalized_values):
        if sampled_value < threshold:
            return AdcClassification(sampled_value, normalized_value, False)

    return AdcClassification(sampled_value, UNMAPPED_KEY_VALUE, False)
