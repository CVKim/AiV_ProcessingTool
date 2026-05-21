# AIVEX Processing Tool — Installer

Windows용 `setup.exe` 인스톨러를 만드는 방법.

## 들어가는 4 셋트

설치된 폴더(기본 `C:\Program Files\AIVEX\APT\`)에는 정확히 이 4 항목이 들어갑니다:

```
<install dir>\
├─ APT.exe                       ← 메인 실행 파일
├─ _internal\                    ← Python 런타임 + Qt DLL + 번들 리소스
│  ├─ sample\000.png · 001.png   (Load Samples 버튼이 가리키는 데모)
│  ├─ AiV_LOGO.ico
│  └─ … (Python / cv2 / PyQt5 / numpy)
├─ mim2color.exe                 ← MIM → BMP 외부 변환기
└─ mim_converter_config.ini      ← MIM to BMP 기본 INI (사용자 편집 대상)
```

INI는 `onlyifdoesntexist` 플래그라 재설치할 때 사용자 편집을 덮어쓰지 않습니다.

## 사전 준비

1. **Python venv 동작 확인**
   `AiV_ProTool\Scripts\python.exe --version` 가 동작해야 합니다.
2. **PyInstaller**
   ```powershell
   AiV_ProTool\Scripts\python.exe -m pip install pyinstaller
   ```
3. **Inno Setup 6** ([다운로드](https://jrsoftware.org/isdl.php))
   설치 후 `iscc.exe`가 기본 위치(`C:\Program Files (x86)\Inno Setup 6\ISCC.exe`)에 있으면 자동 인식됩니다. PATH에 추가해도 됩니다.

## 빌드

```powershell
cd installer
.\build.ps1
```

build.ps1이 하는 일:
1. `apt/brand.py` 의 `APP_VERSION` 파싱 (single source of truth)
2. `installer/version_info.txt` 생성 → APT.exe의 파일 속성에 박힘
3. `build/` `dist/` 정리 후 PyInstaller 실행 → `dist/APT/`
4. `mim2color.exe`와 `mim_converter_config.ini`를 `dist/APT/` 안에 복사 (인스톨러 없이 zip으로 배포할 때도 4 셋트가 완비됨)
5. Inno Setup으로 `installer/Output/APT_Setup_v<버전>.exe` 생성

## 옵션

```powershell
.\build.ps1 -SkipPyInstaller    # dist/가 이미 fresh일 때 (인스톨러만 재생성)
.\build.ps1 -SkipInstaller      # Inno Setup 단계 건너뜀 (dist/APT/만 필요할 때)
```

## 새 버전 릴리즈 절차

1. `apt/brand.py` 의 `APP_VERSION` 을 새 값으로 (예: `"2.0.0"` → `"2.1.0"`)
2. `git commit -am "release: bump version to 2.1.0"`
3. `cd installer; .\build.ps1`
4. `installer/Output/APT_Setup_v2.1.0.exe` 생성
5. 필요 시 git tag: `git tag v2.1.0 && git push --tags`
6. GitHub Release 페이지에 `APT_Setup_v2.1.0.exe` 업로드

버전을 여러 곳에 중복 입력할 필요 없음 — `brand.py` 하나만 바꾸면 다른 곳(EXE 메타, 인스톨러 파일명, 설치 화면 표기)에 자동 전파됩니다.

## 배포 시 사용자 경험

1. 사용자가 `APT_Setup_v2.0.0.exe` 더블클릭
2. (관리자 권한 필요 — `Program Files` 쓰기 때문)
3. 설치 위치 / 데스크톱 아이콘 여부 선택 → 설치
4. 시작 메뉴 `AIVEX\APT` 또는 데스크톱 아이콘으로 실행
5. 제어판 → 프로그램 추가/제거에서 정상적으로 보임 + 제거 가능

## 트러블슈팅

| 증상 | 해결 |
|---|---|
| `Inno Setup compiler (iscc.exe) not found` | https://jrsoftware.org/isdl.php 에서 Inno Setup 6 설치 |
| `PyInstaller failed` | `error.log` 보지 말고 stdout 로그 확인. 패키지 누락이면 `pip install <name>` |
| 설치는 됐는데 EXE 실행 시 `vcruntime140.dll 없음` | Microsoft Visual C++ Redistributable x64 설치 필요 |
| Windows Defender SmartScreen 경고 | 코드 서명이 없어서 발생. 사내 배포면 "추가 정보 → 실행"으로 통과. 외부 배포면 코드 서명 인증서 도입 검토 |
| 재설치 후 INI가 초기화됨 | `onlyifdoesntexist` 플래그라 그럴 일 없음. 만약 새 INI가 필요하면 설치 전에 기존 INI 파일을 백업 후 삭제 |

## 산출물 위치 (gitignored)

- `installer/Output/` — 최종 setup.exe
- `installer/version_info.txt` — build.ps1이 매번 다시 생성
- `dist/`, `build/` — PyInstaller 중간 산출물

모두 `.gitignore`에 들어있어 실수로 커밋되지 않습니다.
