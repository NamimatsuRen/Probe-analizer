from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class AuditAction(StrEnum):
    EXCLUDE = "exclude"
    RESTORE = "restore"
    METADATA_UPDATE = "metadata_update"
    PROJECT_SAVE = "project_save"
    PROJECT_LOAD = "project_load"
    EXPORT_CREATE = "export_create"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_id: str
    timestamp_utc: str
    action: AuditAction
    subject_id: str
    operator: str
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.subject_id.strip():
            raise ValueError("audit event identity cannot be empty")
        if not self.operator.strip():
            raise ValueError("audit operator cannot be empty")
        datetime.fromisoformat(self.timestamp_utc.replace("Z", "+00:00"))
        keys = tuple(key for key, _ in self.details)
        if any(not key.strip() for key in keys) or len(keys) != len(set(keys)):
            raise ValueError("audit detail keys must be unique and non-empty")
        if tuple(sorted(self.details)) != self.details:
            raise ValueError("audit details must be sorted by key")

    @classmethod
    def create(
        cls,
        action: AuditAction,
        subject_id: str,
        *,
        operator: str = "local-user",
        details: tuple[tuple[str, str], ...] = (),
        timestamp: datetime | None = None,
    ) -> AuditEvent:
        occurred = timestamp or datetime.now(UTC)
        timestamp_utc = occurred.astimezone(UTC).isoformat().replace("+00:00", "Z")
        normalized_details = tuple(sorted(details))
        payload = json.dumps(
            {
                "action": action.value,
                "details": normalized_details,
                "operator": operator,
                "subject_id": subject_id,
                "timestamp_utc": timestamp_utc,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return cls(
            event_id=hashlib.sha256(payload.encode()).hexdigest(),
            timestamp_utc=timestamp_utc,
            action=action,
            subject_id=subject_id,
            operator=operator,
            details=normalized_details,
        )


@dataclass(frozen=True, slots=True)
class AuditTrail:
    events: tuple[AuditEvent, ...] = ()

    def append(self, event: AuditEvent) -> AuditTrail:
        if any(item.event_id == event.event_id for item in self.events):
            return self
        return AuditTrail((*self.events, event))
