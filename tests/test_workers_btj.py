"""Smoke tests for the BTJ (BMP→JPG) worker.

We avoid needing a real QThread by driving the worker logic synchronously
through a fake WorkerThread that records its signals into lists.
"""

from __future__ import annotations

import os

from apt.workers.btj import btj_operation


class FakeSignal:
    def __init__(self) -> None:
        self.records: list = []

    def emit(self, value) -> None:  # noqa: D401
        self.records.append(value)


class FakeWorker:
    def __init__(self) -> None:
        self.progress = FakeSignal()
        self.log = FakeSignal()
        self.ng_count_result = FakeSignal()
        self.finished = FakeSignal()
        self.max_workers = 2
        self._is_stopped = False

    def is_stopped(self) -> bool:
        return self._is_stopped

    def ensure_target_folder(self, path: str) -> bool:
        os.makedirs(path, exist_ok=True)
        return True


def test_btj_converts_every_bmp(bmp_tree, tmp_path):
    target = tmp_path / "out"
    worker = FakeWorker()
    btj_operation(worker, {"source": str(bmp_tree), "target": str(target)})

    finished = worker.finished.records[-1]
    assert "변환 완료" in finished or "처리 대상 0" in finished

    # 3 BMP inputs → 3 JPG outputs preserved under the same relative paths.
    produced = sorted(str(p.relative_to(target)).replace("\\", "/") for p in target.rglob("*.jpg"))
    assert produced == ["sub/1_a.jpg", "sub/2_b.jpg", "top.jpg"]


def test_btj_uses_default_suffix_when_target_blank(bmp_tree):
    worker = FakeWorker()
    btj_operation(worker, {"source": str(bmp_tree), "target": ""})
    expected_target = f"{bmp_tree}_JPG"
    assert os.path.isdir(expected_target)
    assert any(name.endswith(".jpg") for _r, _d, fs in os.walk(expected_target) for name in fs)


def test_btj_rejects_invalid_source(tmp_path):
    worker = FakeWorker()
    btj_operation(worker, {"source": str(tmp_path / "does-not-exist"), "target": ""})
    assert worker.finished.records[-1].endswith("중지됨.")
