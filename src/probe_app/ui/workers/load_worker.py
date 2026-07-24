from __future__ import annotations

import threading
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from probe_app.application.use_cases.open_folder import OpenFolder
from probe_app.domain.errors import OperationCancelled
from probe_app.domain.models.raw_series import RawSeriesDescriptor
from probe_app.infrastructure.readers.panta_reader import PantaRawReader


class WorkerSignals(QObject):
    succeeded = Signal(int, object)
    failed = Signal(int, str, str)
    cancelled = Signal(int)


class CancellableTask(QRunnable):
    def __init__(self, generation: int) -> None:
        super().__init__()
        self.generation = generation
        self.signals = WorkerSignals()
        self._cancelled = threading.Event()

    def cancel(self) -> None:
        self._cancelled.set()

    def is_cancelled(self) -> bool:
        return self._cancelled.is_set()


class FolderScanTask(CancellableTask):
    def __init__(self, generation: int, folder: Path) -> None:
        super().__init__(generation)
        self._folder = folder

    @Slot()
    def run(self) -> None:
        try:
            catalog = OpenFolder().execute(self._folder, is_cancelled=self.is_cancelled)
            if self.is_cancelled():
                raise OperationCancelled()
            self.signals.succeeded.emit(self.generation, catalog)
        except OperationCancelled:
            self.signals.cancelled.emit(self.generation)
        except Exception as exc:
            self.signals.failed.emit(self.generation, str(exc), traceback.format_exc())


class SeriesLoadTask(CancellableTask):
    def __init__(self, generation: int, descriptor: RawSeriesDescriptor) -> None:
        super().__init__(generation)
        self._descriptor = descriptor

    @Slot()
    def run(self) -> None:
        try:
            series = PantaRawReader().read(
                self._descriptor,
                is_cancelled=self.is_cancelled,
            )
            if self.is_cancelled():
                raise OperationCancelled()
            self.signals.succeeded.emit(self.generation, series)
        except OperationCancelled:
            self.signals.cancelled.emit(self.generation)
        except Exception as exc:
            self.signals.failed.emit(self.generation, str(exc), traceback.format_exc())
