# AIVEX Processing Tool (APT)

Image dataset workflow toolkit for the AIVEX DL-PM team. Bundles ten file
operations behind a single PyQt5 desktop app: sorting, copying, counting,
cropping, FOV stitching, and format conversion.

> **v2.0 — fully refactored.** The legacy monoliths (`APT.py`, `worker.py`,
> `ui_dialogs.py`) have moved to `legacy/` and the codebase now lives under
> the `apt/` package. The UI was rebuilt with the AIVEX brand (black + orange
> sidebar shell). Behavior of all ten operations is preserved.

---

## 1. Quick start

```powershell
# 1) create a venv (Python 3.10+)
python -m venv .venv
.\.venv\Scripts\activate

# 2) install runtime deps
pip install -r requirements.txt

# 3) run
python main.py
```

For development (test runner included):

```powershell
pip install -r requirements-dev.txt
pytest
```

---

## 2. Features

| Section     | Panel                  | Operation key            | What it does |
|-------------|------------------------|--------------------------|--------------|
| Sorting     | Basic Sorting          | `basic_sorting`          | Inner-ID-list driven prefix copy. Supports `Double Path Folder` (Code/InnerID) and `Only Defect Image Sorting` modes. |
| Sorting     | NG Folder Sorting      | `ng_sorting`             | Inner-ID intersection of multiple NG folders × Matching folder. |
| Sorting     | NG Count               | `ng_count`               | Counts `Cam_*/Defect/*` items and exports a copyable table. |
| Copy        | Date-Based Copy        | `date_copy`              | Picks N folders modified after a chosen timestamp (folder or image mode, with strong / conditional random options). |
| Copy        | Image Format Copy      | `image_copy`             | Format-filtered file copy of a single source folder. |
| Copy        | Simulation Foldering   | `simulation_foldering`   | Placeholder for the simulation directory layout (kept for parity). |
| Image Ops   | Crop                   | `crop`                   | Bulk crop with `ltrb` or `xywh` coords. BMP+JSON pairs are co-cropped and labels are re-projected. |
| Image Ops   | Attach FOV             | `attach_fov`             | Pairs `fov*.jpg` images by FOV number across two folder trees. |
| Image Ops   | BMP to JPG (BTJ)       | `btj`                    | Recursive BMP → JPG conversion. Auto-creates `<source>_JPG` if no target given. |
| Image Ops   | Preprocessing          | (interactive)            | Node-graph editor for image preprocessing pipelines. 28 built-in ops (geometry, color, filter, threshold, edge, morphology, histogram, combine) with live preview and per-leaf batch export. |
| Conversion  | MIM to BMP             | `mim_to_bmp`             | Edits the INI in-place then launches `mim2color.exe` in a new console. |

FOV expressions accepted everywhere: `1,2,3` or with ranges `1,2,3/5`.

Image format checkboxes (consistent across panels): **MIM, fov_jpg,
org_jpg, BMP, PNG**. `org_jpg` matches `*.jpg` whose name does **not**
contain `fov`; `fov_jpg` matches `*.jpg` whose name **does** contain `fov`.

### Preprocessing panel (node graph editor)

- **Load** a single JPG / PNG / BMP as the origin (MIM is not natively
  supported — convert via the *MIM to BMP* panel first).
- **Add** any of the 28 operations from the left sidebar (double-click).
- **Connect** an output port (green, right side of a node) to an input
  port (blue, left side) by drag-and-drop. Origin can fan out to any
  number of downstream nodes. *Combine* nodes (`Blend`, `Add`, …) take
  two inputs.
- Click a node to edit its **parameters** on the right — the preview
  updates live.
- **Export Outputs…** writes every leaf node's result (full resolution,
  computed from the original image — preview uses a 720px downscale for
  speed) as `<origin>__<node-id>.png` into the chosen folder.
- Wheel = zoom · middle-drag = pan · Delete = remove selected node/edge.

Adding a new preprocessing op is a single `Operation(...)` entry in
`apt/preprocessing/operations.py` plus a pure function taking
`[ndarray]` and returning `ndarray`.

---

## 3. Project layout

```
DL_Tool/
├─ main.py                      # entry point (boots apt.app:main)
├─ apt/                         # application package
│  ├─ __init__.py
│  ├─ brand.py                  # APP_NAME, APP_VERSION, brand constants
│  ├─ constants.py              # format codes, ignored dirs, operation keys
│  ├─ theme.py                  # AIVEX black/orange QSS + palette
│  ├─ app.py                    # MainWindow (sidebar + stacked pages)
│  ├─ widgets/
│  │  ├─ path_picker.py         # QPushButton + QLineEdit picker
│  │  ├─ format_selector.py     # 5-checkbox image-format row
│  │  ├─ fov_input.py           # FOV QLineEdit with placeholder
│  │  ├─ log_console.py         # read-only log + Clear button
│  │  ├─ sidebar.py             # branded navigation column
│  │  ├─ image_preview.py       # numpy → QPixmap auto-scaling preview
│  │  ├─ parameter_form.py      # dynamic form from ParamSpec list
│  │  └─ node_graph/            # QGraphicsScene/View node editor
│  │     ├─ scene.py · view.py · node_item.py · edge_item.py
│  ├─ preprocessing/            # Qt-free image ops + DAG executor
│  │  ├─ operations.py          # 28 ops (Geometry / Color / Filter / Threshold / Edge / Morph / Histogram / Combine)
│  │  └─ pipeline.py            # Node, Pipeline with per-node result cache
│  ├─ utils/                    # Qt-free pure helpers (unit-tested)
│  │  ├─ fov.py                 # parse_fov_numbers, extract_fov_from_filename
│  │  ├─ formats.py             # is_valid_file (org_jpg / fov_jpg semantics)
│  │  └─ fs.py                  # ensure_target_folder, copy_file_chunked, …
│  ├─ workers/                  # QThread-based task runner
│  │  ├─ base.py                # WorkerThread + operation registry / dispatcher
│  │  ├─ sorting.py             # ng_sorting, basic_sorting
│  │  ├─ copying.py             # date_copy, image_copy, simulation_foldering
│  │  ├─ counting.py            # ng_count
│  │  ├─ cropping.py            # crop + BMP/JSON pair handling
│  │  ├─ fov.py                 # attach_fov
│  │  ├─ mim.py                 # mim_to_bmp (subprocess.Popen)
│  │  └─ btj.py                 # bmp -> jpg
│  ├─ dialogs/                  # one panel per operation
│  │  ├─ base.py                # BaseTaskPanel (form / log / progress / start-stop)
│  │  ├─ preprocessing.py       # node-graph editor panel (custom layout)
│  │  └─ … (basic_sorting, ng_sorting, ng_count, date_copy, image_copy,
│  │        simulation, crop, mim_to_bmp, attach_fov, btj)
│  └─ resources/AiV_LOGO.ico    # bundled icon
├─ tests/
│  ├─ conftest.py               # tmp_path tree fixtures + QApplication
│  ├─ fixtures/tree_factory.py  # dummy filesystem trees for worker tests
│  ├─ test_fov.py               # parse_fov_numbers / extract_fov
│  ├─ test_formats.py           # is_valid_file edge cases
│  ├─ test_fs.py                # chunked copy + folder-filtered copy
│  ├─ test_workers_dispatcher.py
│  ├─ test_workers_btj.py
│  ├─ test_workers_counting.py
│  ├─ test_preprocessing_operations.py
│  ├─ test_preprocessing_pipeline.py
│  └─ test_panels.py            # headless construction of every panel
├─ legacy/                      # the pre-refactor monoliths (for reference)
│  ├─ APT.py
│  ├─ worker.py
│  └─ ui_dialogs.py
├─ requirements.txt
├─ requirements-dev.txt
├─ pytest.ini
├─ APT.spec                     # PyInstaller spec
├─ AiV_LOGO.ico
├─ mim2color.exe                # external converter used by MIM to BMP
└─ mim_converter_config.ini     # default INI template
```

### Why two `__init__.py` packages

`apt.utils` is intentionally Qt-free so that unit tests can run in any
environment. Everything that touches `PyQt5` lives under `apt.widgets`,
`apt.dialogs`, `apt.workers`, or `apt.app`.

---

## 4. Adding a new task

1. **Worker** — create `apt/workers/<your_task>.py`:

   ```python
   from apt.constants import OP_MY_TASK   # add the key in apt/constants.py
   from apt.workers.base import register

   def my_task(worker, task):
       worker.log.emit("------ My Task 시작 ------")
       # …do work, emit progress / finished…
       worker.finished.emit("My Task 완료.")

   register(OP_MY_TASK, my_task)
   ```

2. Import the new module at the bottom of `apt/workers/base.py` so the
   registry sees it (an assertion in `base.py` will fail at startup if you
   declare a constant without a handler).

3. **Panel** — create `apt/dialogs/<your_task>.py` extending `BaseTaskPanel`
   and supply `build_form`, `get_parameters`, and `validate_parameters`. Use
   the reusable widgets in `apt.widgets`.

4. **Wire it up** — add the panel to `apt/app.py`'s `self.pages` list under
   whichever sidebar section it belongs to, and export it from
   `apt/dialogs/__init__.py`.

5. **Test** — add fixtures to `tests/fixtures/tree_factory.py` if you need a
   filesystem layout, then write `tests/test_workers_<name>.py` using the
   `FakeWorker` pattern from `tests/test_workers_btj.py`.

---

## 5. Building a Windows executable

```powershell
pip install pyinstaller
pyinstaller APT.spec
# Output: dist/APT/APT.exe
```

The spec includes `apt/resources/AiV_LOGO.ico` in the bundle so the window
icon survives `--onefile` packaging.

---

## 6. Threading model

* Every panel owns one `WorkerThread` (a `QThread`) which runs one operation
  at a time.
* Heavy I/O inside each task fans out via `ThreadPoolExecutor(max_workers =
  min(12, cpu*2))`. On Windows the worker threads are dropped to
  `THREAD_PRIORITY_BELOW_NORMAL` so they do not starve the UI.
* `stop()` is cooperative — the dispatcher loops poll `worker.is_stopped()`
  between futures.

If you find a task that needs to run alongside another, open a separate
panel; each panel runs an independent worker.

---

## 7. Bugfixes vs v1.x

| Issue | Fix |
|---|---|
| `NGCount` worker never emitted `finished` on success, leaving the Start button permanently disabled. | Always emit a terminal `finished` message in `apt/workers/counting.py`. |
| Dead commented-out block in legacy `MainWindow.initUI()` (lines 1458-1521). | Eliminated by the new `Sidebar` / `QStackedWidget` shell. |
| `worker.py` line 1091 had a corrupted backtick comment. | Removed; comments are now inline and concise. |
| Reusable widgets (`PathPicker`, `FormatSelector`) were copy-pasted across all dialogs. | Centralised under `apt/widgets`. |

---

## 8. Test coverage today

```
$ pytest -q
..............................................................................................
94 passed
```

The dummy tree factory under `tests/fixtures/tree_factory.py` generates
small real BMPs (Pillow) so worker code that opens images runs end-to-end
without requiring access to production data shares.

---

## 9. Git workflow

The repository uses a simple **two long-lived branches + short-lived feature
branches** model.

```
main            ──●────────────●────────────●───────  (production / tagged releases)
                  ▲            ▲            ▲
                  │  merge     │  merge     │
                  │            │            │
dev      ──●──●───┴──●──●──●───┴──●──●──●───┴──●──   (integration / next release)
           ▲     ▲                ▲     ▲
           │     │ merge          │     │
feature/x  └──●──┘                │     │
feature/y                feature/y└──●──┘
```

### Rules

- **`main`** — always shippable. Only fast-forward or PR merges from `dev`.
  Never commit directly.
- **`dev`** — integration branch. New work lands here first via PRs from
  feature branches; periodically rolled into `main` once stable.
- **`feature/<short-name>`** — branched off `dev`, one branch per
  task/ticket. Deleted after merge.
- **`fix/<short-name>`** — same as feature, for bug fixes.
- **`hotfix/<short-name>`** — branched off `main` for urgent production
  fixes; merged back into both `main` and `dev`.

### Day-to-day commands

```powershell
# Start a new feature
git checkout dev
git pull
git checkout -b feature/add-resize-panel

# …work, commit, push…
git push -u origin feature/add-resize-panel

# Open a PR on GitHub: feature/add-resize-panel → dev
# After review + merge, delete the branch:
git branch -d feature/add-resize-panel
git push origin --delete feature/add-resize-panel

# When dev is stable enough to release, PR dev → main on GitHub
# (no fast-forward — leave the merge commit so release history is visible).
```

### Suggested PR titles

```
feat:  add resize panel
fix:   handle empty NG folder in counting worker
docs:  update FOV expression examples
chore: bump Pillow to 11
test:  cover crop_image bounds clamping
```

---

## 10. License & ownership

Internal AIVEX DL-PM team tool. Not for external distribution.
