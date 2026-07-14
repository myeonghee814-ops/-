# 무료 호스팅으로 배포하기 (Vercel + Render)

로컬에서 아직 못 돌리는 상태에서 브라우저로 바로 UI를 확인하고 싶을 때
쓰는 가이드입니다. 프론트엔드는 Vercel, 백엔드는 Render 무료 플랜에
배포합니다.

**중요:** 저는 두 서비스 모두 로그인할 계정이 없어서 배포 버튼을 대신
눌러드릴 수 없습니다. 대신 저장소를 "몇 번 클릭이면 배포되는" 상태로
준비해뒀고, 아래는 정확한 클릭 순서입니다.

이건 `docker-compose.prod.yml`(Postgres + 마이그레이션 + gunicorn, 진짜
프로덕션용)을 대체하는 게 아니라, 그 옆에 추가된 "빠르게 테스트용"
경로입니다. 현재 기능(검색/AI 분석/비교/엑셀 내보내기)은 DB를 전혀 안
쓰기 때문에, 이 배포 경로는 마이그레이션 없이 SQLite 그대로 씁니다.

## 배포 순서 (반드시 이 순서로)

백엔드 URL을 프론트엔드가 알아야 하고, 프론트엔드 URL을 백엔드
CORS 설정이 알아야 해서, 아래 순서를 지켜야 합니다.

### 1. 백엔드를 Render에 배포

1. https://dashboard.render.com 접속 (계정 없으면 GitHub로 가입, 무료)
2. **New** → **Blueprint** 클릭
3. 이 GitHub 저장소(`myeonghee814-ops/-`) 선택 → 브랜치는
   `claude/blip-project-skeleton-azhge3` (또는 머지된 이후라면 `main`)
4. Render가 저장소 루트의 `render.yaml`을 자동으로 읽어서 서비스 구성을
   보여줍니다. `OPENAI_API_KEY`는 비워두면 물어봅니다 — AI 분석 기능을
   쓸 계획이면 여기서 입력하세요 (없어도 검색 기능은 정상 동작합니다).
5. **Apply** 클릭 → 첫 빌드는 몇 분 걸립니다.
6. 빌드가 끝나면 서비스 화면 상단에 URL이 보입니다. 예:
   `https://blip-backend-xxxx.onrender.com` — **이 URL을 복사해두세요.**
7. `https://블립백엔드URL/api/v1/health`로 접속해서
   `{"status":"ok",...}`가 나오면 정상입니다.

**참고:** 무료 플랜은 15분 동안 요청이 없으면 서버가 잠들고, 다음 요청이
오면 다시 깨어나는 데 30~50초 정도 걸립니다. 배포 직후나 오랜만에
접속했을 때 첫 검색이 느리거나 타임아웃처럼 보이면 잠깐 기다렸다가
다시 시도해보세요 — 고장난 게 아닙니다.

### 2. 프론트엔드를 Vercel에 배포

1. https://vercel.com 접속 (계정 없으면 GitHub로 가입, 무료)
2. **Add New** → **Project** 클릭
3. 같은 GitHub 저장소 선택 → **Import**
4. **Root Directory**를 `frontend`로 설정 (Vercel이 Vite 프로젝트로
   자동 인식합니다 — Build Command/Output Directory는 안 건드려도 됨)
5. **Environment Variables**에 아래 2개 추가 (1단계에서 복사한 Render
   URL 사용, 끝에 `/api/v1`, `/api` 꼭 붙이기):
   ```
   VITE_API_BASE_URL = https://블립백엔드URL/api/v1
   VITE_API_ROOT_URL = https://블립백엔드URL/api
   ```
6. **Deploy** 클릭 → 1~2분이면 끝납니다.
7. 완료되면 `https://프로젝트이름.vercel.app` 같은 URL이 나옵니다 —
   **이게 사용자에게 드릴 공개 URL입니다.**

### 3. Render로 돌아가서 CORS 허용 도메인 설정

1. Render 대시보드 → `blip-backend` 서비스 → **Environment** 탭
2. `CORS_ORIGINS` 값을 2단계에서 받은 Vercel URL로 교체:
   ```
   CORS_ORIGINS = https://프로젝트이름.vercel.app
   ```
3. 저장하면 자동으로 재배포됩니다 (1~2분).

이 단계를 건너뛰면 프론트엔드는 뜨지만 검색을 누르는 순간 브라우저
콘솔에 CORS 에러가 뜨고 아무 결과도 안 나옵니다.

## 확인

1. Vercel URL 접속
2. 키워드로 검색 → 결과 테이블이 뜨는지 확인 (Render가 잠들어 있었다면
   첫 요청은 느릴 수 있음)
3. `OPENAI_API_KEY`를 입력했다면 "Analyze Results" 버튼도 눌러서 AI
   분석까지 확인
4. 논문 상세 페이지, Compare 페이지도 클릭해서 확인

## 배포 후 코드를 다시 수정했다면

`main`(또는 배포에 연결한 브랜치)에 푸시하면 Vercel과 Render 둘 다
자동으로 다시 빌드/배포합니다 — 별도로 뭔가 누를 필요 없습니다.

## 이 배포 경로의 한계

- **DB 영속성 없음**: SQLite가 Render 컨테이너 안에만 있고, 재배포되면
  초기화됩니다. 지금 기능은 애초에 DB를 안 쓰니 문제 없지만, 나중에
  "검색 결과 저장" 기능이 들어가면 이 경로는 안 맞습니다 — 그때는
  `docker-compose.prod.yml` 경로(Postgres 포함)나 Render의 유료
  Postgres 애드온이 필요합니다.
- **무료 플랜 콜드 스타트**: 위에 설명한 30~50초 지연.
- **인증 없음**: 지금 프로젝트에 로그인 기능 자체가 없으므로, 이 URL을
  아는 사람은 누구나 접속해서 씁니다. `OPENAI_API_KEY`를 넣었다면 그
  키로 나가는 OpenAI 요청 비용도 발생할 수 있다는 점 참고하세요.
