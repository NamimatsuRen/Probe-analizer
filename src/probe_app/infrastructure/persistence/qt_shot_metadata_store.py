from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PySide6.QtCore import QSettings

from probe_app.domain.models.shot_metadata import (
    ProbePosition,
    ProbePositionUnit,
    ShotMetadata,
)


class QSettingsShotMetadataStore:
    """Small preference store; project files remain the portable source of truth."""

    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    def load(self, folder: Path, shot_id: str) -> ShotMetadata:
        folder_key = str(folder.resolve())
        raw = str(
            self._settings.value(
                self._key(folder_key, shot_id),
                "",
                type=str,
            )
        )
        if not raw:
            return ShotMetadata(folder_key=folder_key, shot_id=shot_id)
        try:
            payload = json.loads(raw)
            position_payload = payload.get("position")
            position = (
                ProbePosition(
                    value=float(position_payload["value"]),
                    unit=ProbePositionUnit(position_payload["unit"]),
                    label=str(position_payload.get("label", "")),
                )
                if isinstance(position_payload, dict)
                else None
            )
            return ShotMetadata(
                folder_key=folder_key,
                shot_id=shot_id,
                position=position,
                note=str(payload.get("note", "")),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return ShotMetadata(folder_key=folder_key, shot_id=shot_id)

    def save(self, folder: Path, metadata: ShotMetadata) -> None:
        folder_key = str(folder.resolve())
        if metadata.folder_key != folder_key:
            raise ValueError("metadata folder does not match the selected folder")
        position = metadata.position
        payload = {
            "note": metadata.note,
            "position": (
                {
                    "label": position.label,
                    "unit": position.unit.value,
                    "value": position.value,
                }
                if position is not None
                else None
            ),
            "schema_version": 1,
            "shot_id": metadata.shot_id,
        }
        self._settings.setValue(
            self._key(folder_key, metadata.shot_id),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        )
        self._settings.sync()

    @staticmethod
    def _key(folder_key: str, shot_id: str) -> str:
        digest = hashlib.sha256(f"{folder_key}\0{shot_id}".encode()).hexdigest()
        return f"shotMetadata/v1/{digest}"
