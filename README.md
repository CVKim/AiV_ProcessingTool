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

### Distributing a built EXE / installer

Two options:

| Method | Output | Notes |
|---|---|---|
| **Directory build** (`pyinstaller APT.spec`) | `dist\APT\` folder | Zip + share the whole folder. EXE alone won't run — `_internal\` carries Python + Qt DLLs. |
| **Installer** (`installer\build.ps1`) | `installer\Output\APT_Setup_v<ver>.exe` | Single self-extracting installer. Requires Inno Setup 6 ([free](https://jrsoftware.org/isdl.php)). Bundles `APT.exe + _internal\ + mim2color.exe + mim_converter_config.ini` and installs to `Program Files\AIVEX\APT\`, registers in Add/Remove Programs, creates Start Menu shortcuts. |

The installer build script parses the version from `apt/brand.py:APP_VERSION` so you only need to bump that one line per release. See [`installer/README.md`](installer/README.md) for details.

### Releasing a new version

새 버전(예: 2.0.1 버그픽스, 2.1.0 마이너, 3.0.0 메이저)을 인스톨러로 배포하는 표준 절차입니다. `apt/brand.py`의 `APP_VERSION` **한 줄**이 single source of truth — 다른 데 손댈 필요 없습니다.

#### 사전 준비 (한 번만)
1. **Inno Setup 6** 설치 — https://jrsoftware.org/isdl.php
   `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` 가 생기면 끝. `build.ps1`이 자동 인식.
2. **PyInstaller** — `AiV_ProTool\Scripts\python.exe -m pip install pyinstaller` (이미 깔려 있으면 skip)

#### 버전 번호 정하기 (Semantic Versioning)
- `MAJOR.MINOR.PATCH` — 예: `2.1.3`
- **PATCH** (`2.0.0` → `2.0.1`): 버그 픽스만. 사용자 작업 흐름 변화 없음.
- **MINOR** (`2.0.x` → `2.1.0`): 새 기능 추가. 기존 동작 호환.
- **MAJOR** (`2.x.x` → `3.0.0`): 기존 동작이 깨지는 변경 (Job 파일 포맷 변경 등).

#### 5단계 릴리즈 절차

**1. 버전 올리기** — `apt/brand.py` 의 한 줄만 수정:

```python
# apt/brand.py
APP_VERSION = "2.1.0"   # ← 여기만 바꾸면 끝
```

**2. 커밋** — 변경 사항이 있으면 commit. 버전 bump도 별도 commit으로 남기면 git log 추적이 쉬워요:

```powershell
git add -A
git commit -m "release: bump version to 2.1.0"
```

**3. 빌드 실행** — 한 줄 명령:

```powershell
cd e:\Dev\DL_Tool\installer
.\build.ps1
```

진행 단계 (~4분):
```
=== Reading version from brand.py ===           ← 2.1.0 자동 감지
=== Generating version_info.txt ===             ← APT.exe 메타데이터 자동 생성
=== Running PyInstaller ===                     ← 가장 오래 걸림 (~3분)
=== Copying mim2color.exe + INI into dist\APT ===
=== Locating Inno Setup compiler (iscc.exe) ===
=== Compiling installer ===                     ← Inno Setup 압축 (~30~60초)

================================================================
  Installer ready:
  E:\Dev\DL_Tool\installer\Output\APT_Setup_v2.1.0.exe
  size: 67.2 MB
================================================================
```

산출물:
- `installer\Output\APT_Setup_v2.1.0.exe` ← **이 한 파일만** 사용자에게 전달
- 파일명에 버전이 자동으로 들어가서 구버전과 헷갈리지 않음

**4. 본인 PC에서 사전 테스트** (필수)
- 새 인스톨러를 본인 PC에서 한 번 실행해보세요. 기존 설치 위에 자동 업그레이드되는지 확인.
- 핵심 패널 (Preprocessing 등) 한 번씩 열어보고 정상 동작 확인.
- 문제 있으면 코드 수정 → `apt/brand.py` 그대로 두고 다시 `.\build.ps1` (덮어쓰기됨)

**5. 사용자에게 배포**
- USB / 공유 드라이브 / Slack / 메일 — 어떤 방법으로든 `APT_Setup_v2.1.0.exe` 전달
- 사용자는 **그냥 더블클릭만** 하면 기존 버전 위에 자동 업그레이드
- 사용자가 편집한 `mim_converter_config.ini`는 보존됨 (인스톨러의 `onlyifdoesntexist` 플래그)

#### Git tag 남기기 (선택 권장)

릴리즈 시점을 git에 기록해두면 나중에 "v2.0.0 시점 코드"로 돌아가기 쉬워요:

```powershell
git tag -a v2.1.0 -m "Release 2.1.0 — <한 줄 요약>"
git push origin v2.1.0
```

GitHub에 가면 [Releases](https://github.com/CVKim/AiV_ProcessingTool/releases) 페이지에서 tag별로 변경 사항을 정리하고 `APT_Setup_v2.1.0.exe` 파일을 첨부 업로드해서 외부 공유용 다운로드 페이지로도 쓸 수 있습니다.

#### 자주 묻는 케이스

| 상황 | 답 |
|---|---|
| **버전만 바꾸고 코드 변화는 없는데도 빌드해도 되나요?** | 네. 이전 빌드를 재현하고 싶을 때 종종 함. |
| **PATCH 빌드인데 사용자 폴더 데이터가 사라지나요?** | 아니요. `_internal\sample\`, INI 파일 모두 보존. 사용자가 만든 `.apt.json` 같은 외부 파일은 어차피 설치 폴더 밖이라 영향 없음. |
| **빌드 중에 PyInstaller가 한참 멈춰 있어요** | 정상. PyInstaller는 의존성 분석 + 압축이라 ~3분 정도 걸림. 진행 표시가 없어도 끝까지 기다리면 됩니다. |
| **`iscc.exe` 못 찾는다고 나옵니다** | Inno Setup 6 설치 안 됨. https://jrsoftware.org/isdl.php 에서 설치 후 재시도. |
| **빌드 실패 — "Permission denied" on `dist\`** | 이전에 빌드한 EXE가 실행 중이거나 폴더가 다른 프로그램에서 열려있음. EXE 종료 + 폴더 닫고 재시도. |
| **새 버전 빌드해도 인스톨러 크기는 비슷한가요?** | 네. Python 런타임 + Qt가 대부분이라 ~67MB 수준에서 변동 거의 없음. |

#### 부분 재빌드 (시간 절약)

빌드 중 어느 한 단계만 다시 돌리고 싶을 때:

```powershell
# PyInstaller 건너뛰기 (dist/가 fresh일 때 인스톨러만 다시)
.\build.ps1 -SkipPyInstaller

# Inno Setup 건너뛰기 (dist/APT/만 필요할 때)
.\build.ps1 -SkipInstaller
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
| Image Ops   | Preprocessing          | (interactive)            | Node-graph editor for image preprocessing pipelines. 31 built-in ops with live preview, multi-image batch (grid view), portable job files (`.apt.json`), and full-resolution export. |
| Conversion  | MIM to BMP             | `mim_to_bmp`             | Edits the INI in-place then launches `mim2color.exe` in a new console. |

FOV expressions accepted everywhere: `1,2,3` or with ranges `1,2,3/5`.

Image format checkboxes (consistent across panels): **MIM, fov_jpg,
org_jpg, BMP, PNG**. `org_jpg` matches `*.jpg` whose name does **not**
contain `fov`; `fov_jpg` matches `*.jpg` whose name **does** contain `fov`.

### Preprocessing panel (node graph editor)

- **Load Images / Add Images** — bring in any number of JPG / PNG / BMP
  files. Thumbnails appear in the strip below the canvas. Click a
  thumbnail to mark it the *active* image (parameter tuning runs against
  this one). MIM is not natively supported — convert via the *MIM to
  BMP* panel first.
- **Add** any of the 31 operations from the left sidebar (double-click).
  Use the search box at the top to filter; categories are colour-coded
  in the sidebar AND on every node title bar / edge.
- **Connect** an output port (right side of a node) to an input port
  (left) by drag-and-drop. Origin can fan out to any number of
  downstream nodes. *Combine* nodes (`Blend`, `Add`, …) take two inputs.
- Click a node to edit its **parameters** on the right. The inspector
  has two preview tabs:
  - **Active** — selected node's output on the active image
  - **All Images** — same op on every loaded image, side-by-side grid
  Default tab switches to *All Images* automatically when more than one
  image is loaded.
- **Save Job / Load Job** — save the entire graph (nodes, parameters,
  connections, positions) to a `.apt.json` file and reload it later
  against any image set. Job files are portable across machines.
- **Save Outputs…** writes every (image × leaf node) combination at
  **full resolution** as `<image-stem>__<node-id>.png` into the chosen
  folder. Errors are reported per file — one bad node does not abort the
  whole batch.
- Wheel = zoom · middle-drag = pan · Delete = remove selected node/edge.

**Operations (31 in 8 categories):**

| Category | Operations |
|---|---|
| Geometry | Resize · Rotate · Flip · **Crop (XYWH)** |
| Color | Grayscale · Invert · Brightness/Contrast · Gamma · **Window Stretch** |
| Filter | Gaussian / Median / Bilateral / Box Blur · Unsharp Mask · **Resize Smooth (down→up)** |
| Threshold | Binary · Otsu · Adaptive (gaussian / mean) |
| Edge | Canny · Sobel · Laplacian |
| Morphology | Erode · Dilate · Open · Close |
| Histogram | Equalise · CLAHE |
| Combine (2-input) | Blend · Add · Subtract · Max · Min |

Median Blur and Bilateral Filter expose an `iterations` parameter to
match the crack-defect preprocessing recipes used internally.

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
│  │  ├─ image_strip.py         # horizontal thumbnail strip of loaded images
│  │  ├─ batch_grid.py          # grid of leaf results across all images
│  │  ├─ op_picker.py           # search + category-coloured op cards
│  │  ├─ parameter_form.py      # dynamic form from ParamSpec list
│  │  └─ node_graph/            # QGraphicsScene/View node editor
│  │     ├─ scene.py · view.py · node_item.py · edge_item.py
│  ├─ preprocessing/            # Qt-free image ops + DAG executor
│  │  ├─ operations.py          # 31 ops (Geometry / Color / Filter / Threshold / Edge / Morph / Histogram / Combine)
│  │  ├─ pipeline.py            # Node, Pipeline, duplicate_with_origin (batch / export)
│  │  ├─ categories.py          # Category colour palette + hints
│  │  └─ job.py                 # .apt.json save / load with version + validation
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
│  ├─ test_preprocessing_job.py
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
..................................................................................................................
114 passed
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
