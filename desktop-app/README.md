# BLIP 독립 실행형 앱 (.exe) — Tauri 스캐폴드

`desktop/`(vbs 기반 조용한 실행기)의 다음 단계입니다. 여기 있는 것들로
`tauri build`를 실행하면 진짜 Windows 설치 프로그램(.msi 또는 .exe)이
만들어지고, 설치하면 시작메뉴/바탕화면 바로가기도 Tauri가 알아서
만들어줍니다 — `desktop/*.vbs`의 바로가기 수동 생성이 필요 없어집니다.

## 검증 상태 (중요 — 읽어주세요)

이 스캐폴드는 리눅스 샌드박스에서 작업하며 만들었기 때문에, **실제
Windows `.exe`를 빌드/설치/실행해서 테스트한 적이 없습니다.** 대신
가능한 범위에서 최대한 검증했습니다:

- **PyInstaller로 백엔드를 얼린 실행파일**은 실제로 빌드해서 실행까지
  확인했습니다 — `/api/v1/health`, SPA 라우팅 폴백(`/paper/123` →
  `index.html`), `/assets/*.js` 정적 파일, `/api/search`가 캐치올
  라우트에 안 가려지는 것까지 전부 정상 동작을 확인했습니다. (리눅스
  바이너리라 Windows에서 그대로 못 쓰지만, `pyinstaller.spec`의 hidden
  imports와 `main.py`의 프론트엔드 서빙 로직 자체는 검증됐습니다.)
- **Rust 코드(`src/main.rs`)의 API 사용법**(`app.path().resolve(...,
  BaseDirectory::Resource)`, sidecar의 `.env()` 빌더, `tauri.conf.json`의
  `externalBin`/`resources`/capabilities 문법)은 전부 실제 크레이트
  소스코드(`tauri` 2.11.5, `tauri-plugin-shell` 2.3.5)를 직접 열어서
  메서드 시그니처를 대조 확인했습니다. 추측이 아닙니다.
- **`cargo check`는 끝까지 통과하지 못했습니다** — 이 샌드박스에서
  `libwebkit2gtk-4.1-dev` 등 리눅스 GTK 개발 라이브러리를 apt로 설치하려
  했으나 미러 접근이 막혀 있었습니다. 이건 Windows 빌드와는 무관합니다
  (Windows는 GTK가 아니라 WebView2를 씀). 대신 의존성 트리 해석과 제
  코드가 포함된 크레이트 그래프 컴파일은 GTK 바인딩 단계 직전까지
  전부 성공하는 것을 확인했습니다.

**즉: 배관(플러밍)은 실제로 맞다는 확신이 높지만, Windows에서 첫
`tauri build`는 뭔가 한 번은 삐끗할 가능성이 있습니다.** (아이콘 누락,
버전 사소한 API 변경 등) 아래 순서대로 진행하면서 에러가 나면 그
지점부터 같이 고치면 됩니다.

## 사전 준비 (Windows 빌드 머신)

- [Rust](https://www.rust-lang.org/tools/install) (`rustup`)
- [Node.js 20+](https://nodejs.org/)
- [Python 3.11+](https://www.python.org/downloads/)
- [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
  (Tauri의 Rust MSVC 툴체인에 필요)
- [WebView2 런타임](https://developer.microsoft.com/microsoft-edge/webview2/) —
  Windows 11과 최신 Windows 10에는 이미 있음. 없으면 Tauri가 설치 시
  자동으로 부트스트래퍼를 받아옴 (`tauri.conf.json`에 별도 설정 없이
  기본 동작)
- Tauri CLI: `npm install -g @tauri-apps/cli`

## 빌드 순서

### 1. 프론트엔드 빌드 → `frontend_dist/`로 복사

```powershell
cd frontend
npm install
npm run build
cd ..
Copy-Item -Recurse -Force frontend\dist desktop-app\frontend_dist
```

`desktop-app/frontend_dist`는 `tauri.conf.json`의 `bundle.resources`가
가리키는 고정 경로입니다 (`.gitignore`에 이미 제외되어 있음, 매 빌드마다
새로 생성).

### 2. 백엔드를 sidecar 실행파일로 freeze

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pyinstaller pyinstaller-hooks-contrib
pyinstaller pyinstaller.spec --distpath dist --workpath build --noconfirm
cd ..
```

결과물은 `backend\dist\blip-backend.exe` (단일 파일)입니다. Tauri는
sidecar 파일명에 타겟 트리플이 붙어있길 요구하므로, 트리플을 확인하고
그 이름으로 복사합니다:

```powershell
rustc -Vv | Select-String "host"
# 보통: host: x86_64-pc-windows-msvc

Copy-Item backend\dist\blip-backend.exe `
  desktop-app\src-tauri\binaries\blip-backend-x86_64-pc-windows-msvc.exe
```

**만약 `ModuleNotFoundError`가 뜨면:** `blip-backend.exe`를 콘솔에서
직접 실행해 보면(`.\backend\dist\blip-backend.exe`) 어떤 모듈이
빠졌는지 바로 보입니다. `backend/pyinstaller.spec`의 `hiddenimports`
리스트에 추가하고 다시 freeze하세요. 흔한 원인은 SQLAlchemy
방언이나 pydantic의 선택적 의존성입니다.

### 3. 아이콘 생성 (최초 1회)

```powershell
tauri icon path\to\1024x1024-icon.png --output desktop-app\src-tauri\icons
```

실제 아이콘 아트워크가 없다면 우선 아무 정사각형 PNG로 생성해서 빌드가
되는지만 먼저 확인해도 됩니다 — 나중에 다시 교체 가능합니다.

### 4. Tauri 앱 빌드

```powershell
cd desktop-app\src-tauri
cargo tauri build
```

(`cargo tauri`가 안 되면 `npm install -g @tauri-apps/cli` 후
`tauri build`로 실행)

성공하면 `desktop-app\src-tauri\target\release\bundle\` 아래에
`msi\BLIP_0.1.0_x64_en-US.msi`와 `nsis\BLIP_0.1.0_x64-setup.exe`가
생깁니다. 이 설치 파일 하나를 배포하면 일반 사용자는 그냥 설치하고
시작메뉴/바탕화면 아이콘을 누르면 됩니다 — Python이나 Node.js가 컴퓨터에
설치되어 있을 필요도 없습니다 (전부 안에 얼려서 들어있음).

### 개발 중 빠르게 확인하고 싶다면

```powershell
cd desktop-app\src-tauri
cargo tauri dev
```

`[backend] ...` 접두사로 백엔드 stdout/stderr가 터미널에 그대로
찍힙니다 (`src/main.rs` 참고) — sidecar가 왜 안 뜨는지 디버깅할 때 여기부터
보세요.

## 파일 구성

| 경로 | 역할 |
|---|---|
| `src-tauri/Cargo.toml` | Rust 의존성 (`tauri`, `tauri-plugin-shell`, `ureq`) |
| `src-tauri/tauri.conf.json` | 앱 메타데이터, 창 설정, sidecar(`externalBin`)와 번들 리소스(`resources`) 선언 |
| `src-tauri/capabilities/default.json` | sidecar 실행을 허용하는 권한 선언 (`shell:allow-execute`) |
| `src-tauri/src/main.rs` | sidecar 실행 → `frontend_dist` 경로를 env var로 전달 → 헬스체크 대기 → 스플래시에서 실제 앱으로 이동 |
| `src-tauri/binaries/` | freeze한 `blip-backend-<triple>.exe`를 넣는 자리 (직접 생성 필요, git에는 없음) |
| `src-tauri/icons/` | 앱 아이콘 (직접 생성 필요, git에는 없음) |
| `splash/index.html` | 백엔드가 뜨는 동안 보여주는 로딩 화면 |
| `frontend_dist/` | 빌드된 프론트엔드가 복사되는 자리 (직접 생성 필요, git에는 없음) |

## 이 스캐폴드가 하지 않는 것 (알려진 한계)

- **DB 마이그레이션 미포함**: 현재 기능(검색/AI 분석/비교/엑셀 내보내기)은
  DB를 전혀 안 씁니다. 나중에 "검색 결과 저장" 기능이 들어가면
  (`README.md` 로드맵 참고) `backend/alembic/`을 리소스로 함께 묶고
  sidecar 시작 시 `alembic upgrade head`를 먼저 실행하도록 손봐야 합니다.
- **자동 업데이트 없음**: Tauri의 업데이터 플러그인은 아직 설정 안 함.
  버전이 오르면 새 설치 파일을 다시 배포/설치해야 합니다.
- **콘솔 창이 sidecar에 여전히 붙어있음** (`pyinstaller.spec`의
  `console=True`): 디버깅 편의를 위해 켜뒀습니다. 완성도를 높이려면
  `console=False`로 바꾸고 로그를 파일로 리다이렉트하는 방식으로 옮기는
  게 좋습니다 (`desktop/start.ps1`이 이미 하는 방식과 동일).
