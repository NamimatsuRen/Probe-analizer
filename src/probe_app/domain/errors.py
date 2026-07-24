from __future__ import annotations

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
