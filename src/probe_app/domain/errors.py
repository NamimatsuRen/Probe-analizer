from __future__ import annotations

from enum import StrEnum
from pathlib import Path


class ProbeAppError(Exception):
    """Base class for errors that can be shown to the user."""


class FolderScanError(ProbeAppError):
    """The selected folder cannot be scanned."""

    def __init__(self, folder: Path, reason: str) -> None:
        self.folder = folder
        self.reason = reason
        super().__init__(f"{folder}: {reason}")


class HeaderParseError(ProbeAppError):
    """A PANTA/Yokogawa header is incomplete or unsupported."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path.name}: {reason}")


class RawDataReadError(ProbeAppError):
    """A waveform file cannot be decoded according to its header."""

    def __init__(self, path: Path, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path.name}: {reason}")


class OperationCancelled(ProbeAppError):
    """A background operation was cancelled by the user."""


class SignalAlignmentFailure(StrEnum):
    """Machine-readable reasons why two physical signals cannot be aligned."""

    WRONG_ROLE = "wrong_role"
    WRONG_UNIT = "wrong_unit"
    NON_FINITE_DATA = "non_finite_data"
    NON_MONOTONIC_TIME = "non_monotonic_time"
    NO_TIME_OVERLAP = "no_time_overlap"
    TOO_FEW_POINTS = "too_few_points"


class SignalAlignmentError(ProbeAppError):
    """Current and sweep-voltage signals cannot share a safe time axis."""

    def __init__(self, failure: SignalAlignmentFailure, detail: str) -> None:
        self.failure = failure
        self.detail = detail
        super().__init__(f"{failure.value}: {detail}")


class SweepSplitFailure(StrEnum):
    """Machine-readable reasons why the legacy sweep split cannot run."""

    INVALID_PARAMETERS = "invalid_parameters"
    INVALID_SAMPLE_WINDOW = "invalid_sample_window"
    INSUFFICIENT_DATA = "insufficient_data"
    MISALIGNED_WINDOW = "misaligned_window"


class SweepSplitError(ProbeAppError):
    """A time-aligned signal pair cannot be divided into complete sweeps."""

    def __init__(self, failure: SweepSplitFailure, detail: str) -> None:
        self.failure = failure
        self.detail = detail
        super().__init__(f"{failure.value}: {detail}")


class RoleAssignmentStoreError(ProbeAppError):
    """Role assignments could not be loaded from or saved to app preferences."""
