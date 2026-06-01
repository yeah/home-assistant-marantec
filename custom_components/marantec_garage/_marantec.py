"""Vendored Marantec RF encoder.

Self-contained copy of the rf_protocols Marantec command (and the minimal base
class it needs), so the integration has no external runtime dependency. Mirrors
yeah/rf-protocols @ add-marantec-protocol. When rf-protocols is released on
PyPI, this file can be removed in favor of a manifest requirement.
"""

from __future__ import annotations

import abc
from enum import StrEnum

_MARANTEC_FREQUENCY = 868_350_000
_MARANTEC_REPEAT_COUNT = 4

_TE_SHORT = 1000
_TE_LONG = 2000
_HEADER_LOW = _TE_LONG * 5
_BIT_COUNT = 49


class ModulationType(StrEnum):
    """RF modulation type."""

    OOK = "OOK"


class RadioFrequencyCommand(abc.ABC):
    """Base class for RF commands."""

    frequency: int
    repeat_count: int
    modulation: ModulationType

    def __init__(
        self,
        *,
        frequency: int,
        modulation: ModulationType,
        repeat_count: int = 0,
    ) -> None:
        """Initialize the RF command."""
        self.frequency = frequency
        self.modulation = modulation
        self.repeat_count = repeat_count

    @abc.abstractmethod
    def get_raw_timings(self) -> list[int]:
        """Return raw timings as signed alternating microseconds."""


class MarantecCommand(RadioFrequencyCommand):
    """Marantec static-code garage door / gate command (49-bit OOK)."""

    code: int

    def __init__(self, *, code: int, frequency: int = _MARANTEC_FREQUENCY) -> None:
        """Initialize from a 49-bit Marantec code (e.g. a Flipper capture)."""
        if code < 0 or code >= (1 << _BIT_COUNT):
            raise ValueError("code must be a 49-bit value (0..2**49-1)")
        super().__init__(
            frequency=frequency,
            modulation=ModulationType.OOK,
            repeat_count=_MARANTEC_REPEAT_COUNT,
        )
        self.code = code

    def get_raw_timings(self) -> list[int]:
        """Compute Marantec frame timings (Manchester-coded OOK).

        Mark-first frame followed by a trailing inter-frame gap; on the
        transmitter's back-to-back replay this reconstructs the reference
        Flipper waveform. See yeah/rf-protocols for the full rationale.
        """
        timings: list[int] = []

        def add(us: int) -> None:
            if timings and (us > 0) == (timings[-1] > 0):
                timings[-1] += us
            else:
                timings.append(us)

        for idx in range(_BIT_COUNT):
            bit = (self.code >> (_BIT_COUNT - 1 - idx)) & 1
            if idx == 0 and bit:
                add(_TE_SHORT)
                continue
            if bit:
                add(-_TE_SHORT)
                add(_TE_SHORT)
            else:
                add(_TE_SHORT)
                add(-_TE_SHORT)

        add(-_HEADER_LOW)
        return timings
