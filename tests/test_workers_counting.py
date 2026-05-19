"""NG Count worker — verifies the bug-fixed finished signal and table shape."""

from __future__ import annotations

from apt.workers.counting import ng_count


class FakeSignal:
    def __init__(self) -> None:
        self.records: list = []

    def emit(self, value) -> None:
        self.records.append(value)


class FakeWorker:
    def __init__(self) -> None:
        self.progress = FakeSignal()
        self.log = FakeSignal()
        self.ng_count_result = FakeSignal()
        self.finished = FakeSignal()
        self._is_stopped = False

    def is_stopped(self) -> bool:
        return self._is_stopped


def test_ng_count_emits_finished_and_result(ng_count_tree):
    worker = FakeWorker()
    ng_count(worker, {"ng_folder": str(ng_count_tree)})

    # Bug fix: success path now ends with a finished emit.
    assert worker.finished.records, "ng_count must emit finished on success"
    assert "NG Count 완료" in worker.finished.records[-1]

    # Result tuple shape: (rows, total_top_folders, total_cams, total_defects)
    assert worker.ng_count_result.records, "ng_count must emit a result tuple"
    rows, total_top, total_cams, total_defects = worker.ng_count_result.records[-1]
    # Cam_01 + Cam_02 = 2 cams; 3 + 1 + 2 = 6 defects.
    assert total_cams == 2
    assert total_defects == 6
    # Parent of ng_folder is lot01/, which has ng/ ok/ ng_info/ extra_top/ →
    # excluding ng/ ok/ ng_info leaves a single eligible top folder.
    assert total_top == 1
    # 3 rows total (one per Cam+Defect combination)
    assert len(rows) == 3
    counts = {(cam, defect): count for cam, defect, count in rows}
    assert counts[("Cam_01", "Defect_A")] == 3
    assert counts[("Cam_01", "Defect_B")] == 1
    assert counts[("Cam_02", "Defect_A")] == 2


def test_ng_count_handles_missing_folder(tmp_path):
    worker = FakeWorker()
    ng_count(worker, {"ng_folder": str(tmp_path / "nope")})
    assert worker.finished.records[-1] == "NG Count 중지됨."
