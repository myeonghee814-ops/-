# BLIP 데스크톱 실행 (Windows, 콘솔 창 없이)

개발자가 아닌 사용자가 바탕화면 아이콘을 더블클릭해서 BLIP을 쓸 수 있도록 만든
런처입니다. 백엔드(FastAPI)와 프론트엔드(Vite)를 백그라운드로 조용히 띄우고,
두 서버가 실제로 응답할 때까지 기다린 뒤 Chrome을 앱 모드(주소창 없는 창)로
자동으로 엽니다.

## 사전 준비

한 번은 개발 환경이 설치되어 있어야 합니다 (최초 실행 시 자동으로
`pip install`/`npm install`을 해주지만, Python·Node.js 자체는 미리 설치돼
있어야 합니다):

- [Python 3.11+](https://www.python.org/downloads/) — 설치 시 "Add python.exe
  to PATH" 체크
- [Node.js 20+](https://nodejs.org/)
- [Google Chrome](https://www.google.com/chrome/) — 없으면 기본 브라우저로
  대신 열립니다

## 최초 1회 설정 — 바탕화면 바로가기 만들기

1. `desktop` 폴더 안의 **`Create-Desktop-Shortcut.vbs`** 를 더블클릭합니다.
2. "Desktop shortcuts created" 메시지가 뜨면 완료입니다.
3. 바탕화면에 **`BLIP`** (실행)과 **`Stop BLIP`** (종료) 아이콘 두 개가
   생깁니다. 아이콘은 원하면 나중에 우클릭 → 속성 → 아이콘 변경으로 바꿀 수
   있습니다.

## 사용법

- **실행:** 바탕화면 `BLIP` 아이콘을 더블클릭합니다. 콘솔 창은 전혀 뜨지
  않고, 준비가 끝나면 Chrome이 자동으로 열립니다.
  - **처음 실행할 때는** 백엔드 가상환경 생성 + 패키지 설치, 프론트엔드
    `npm install`이 백그라운드에서 진행되므로 **1~3분 정도 걸릴 수
    있습니다.** 두 번째 실행부터는 훨씬 빠릅니다 (몇 초).
  - 창이 안 뜨면 최대 1분까지는 정상적으로 기다리는 중입니다. 그 이상
    아무 반응이 없다면 아래 "문제 해결"을 확인하세요.
- **종료:** 바탕화면 `Stop BLIP` 아이콘을 더블클릭하면 두 서버가 모두
  종료됩니다. (Chrome 창을 그냥 닫기만 하면 서버는 백그라운드에 계속
  떠 있으니, 완전히 끄려면 꼭 `Stop BLIP`을 눌러주세요.)

## 문제 해결

- **아무리 기다려도 Chrome이 안 열림:** 저장소 최상위의 `logs/` 폴더를
  확인하세요.
  - `pip-install.log`, `npm-install.log` — 패키지 설치 단계 오류
  - `backend.err.log`, `frontend.err.log` — 서버 실행 중 오류
  - `launcher-error.log` — 런처 스크립트 자체의 오류
- **Windows에서 "publisher를 확인할 수 없습니다" 같은 SmartScreen 경고가
  뜸:** `.vbs`/`.ps1` 파일이 서명되지 않아서 나오는 정상적인 경고입니다.
  "추가 정보" → "실행"을 눌러 진행하면 됩니다.
- **포트 충돌 (8000/5173이 이미 사용 중):** `Stop-BLIP.vbs`를 한 번 실행해
  기존 프로세스를 정리한 뒤 다시 `Launch-BLIP.vbs`를 실행하세요.

## 파일 구성

| 파일 | 용도 |
|------|------|
| `Create-Desktop-Shortcut.vbs` | 최초 1회 실행 — 바탕화면에 `BLIP`/`Stop BLIP` 바로가기 생성 |
| `Launch-BLIP.vbs` | 바로가기의 실제 대상 — `start.ps1`을 창 없이(hidden) 실행 |
| `Stop-BLIP.vbs` | 바로가기의 실제 대상 — `stop.ps1`을 창 없이(hidden) 실행 |
| `start.ps1` | 백엔드/프론트엔드 셋업+기동, 준비 대기, Chrome 실행 |
| `stop.ps1` | 8000/5173 포트를 점유한 프로세스 종료 |

`run.sh`/`run.bat`(저장소 최상위)와의 차이: `run.*`는 개발자가 터미널에서
직접 로그를 보며 쓰는 용도이고, 이 `desktop/` 폴더는 콘솔을 아예 띄우지 않고
더블클릭 한 번으로 끝내는 일반 사용자용입니다.

독립 실행형 `.exe` 설치 프로그램(Tauri/Electron)으로 패키징하는 방안은
저장소 최상위 `README.md`의 "Packaging as a standalone desktop app
(.exe)" 섹션에 설계 검토를 정리해 두었습니다.
