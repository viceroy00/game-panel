# 🎮 Game Panel — 비공개 게임 서버 관리 시스템

지인 전용 Docker 게임 서버 관리. Discord 인증 + TOTP 2FA + 범용 파일 관리 + Discord 채널 알림.

## 주요 기능

- 🔐 Discord OAuth2 지인 인증 (서버 멤버만 가입 가능)
- 🎟️ 초대 코드 (디스코드 안 쓰는 지인용)
- 🔑 자체 계정 + TOTP 2FA + 긴급 복구 코드 8개
- 🎮 Docker 컨테이너 제어 (시작/정지/재시작/로그)
- 📁 범용 웹 파일 탐색기 (게임 무관 — 모드/설정 직접 관리)
- 👥 RBAC 서버별 권한
- ❤️ 헬스체크 → 다운 알림 → 7일 자동 삭제
- 💬 Discord 채널 알림 (서버 상태, 게임 신청, 신규 가입)
- 📧 SMTP 메일 알림 (Discord 알림과 병행)
- 📱 PWA 모바일
- 🪟 Windows Docker Desktop 호환

## 접근 제어 구조

```
지인 → 관리자의 디스코드 서버 가입
        ↓
Game Panel에서 "Discord로 로그인"
        ↓
서버 멤버 확인 → 자동 계정 생성 → 2FA 설정 강제
        ↓
디스코드 안 쓰는 사람 → 초대 코드로 가입
```

## 파일 관리 (모드/설정)

게임별 모드 관리를 추상화하는 대신, **범용 웹 파일 탐색기**를 제공합니다.

```
서버 제어 → [파일 관리] 버튼
  └─ /data/
      ├── mods/          ← 드래그앤드롭으로 .jar 업로드
      ├── config/        ← 클릭하면 웹 에디터로 편집
      ├── world/         ← 월드 백업 다운로드
      └── server.properties  ← 인라인 편집
```

게임이 뭐든 상관없이 컨테이너 내부 파일을 윈도우 탐색기처럼 관리합니다.
새 게임이 추가돼도 패널 코드 변경 없음.

## Discord 채널 알림

지정한 Discord 채널에 실시간 Embed 메시지를 자동 전송합니다.

| 이벤트 | 색상 | 채널 |
|--------|------|------|
| 🔴 서버 다운 감지 | 빨강 | notify |
| 🟢 서버 시작/복구 | 초록 | notify |
| 🟠 삭제 예고 (5일째) | 주황 | notify |
| ⛔ 자동 삭제 완료 | 진빨강 | notify |
| 🔵 게임 서버 신청 | 파랑 | request |
| 🟣 신규 사용자 가입 | 보라 | notify |

## 빠른 시작

```powershell
git clone https://your-git-server.example.com/yourname/game-panel.git
cd game-panel
copy .env.example .env   # 설정 편집
docker compose up -d
```

초기 관리자 계정은 `.env`의 `ADMIN_USERNAME` / `ADMIN_PASSWORD`로 자동 생성됩니다.
첫 로그인 시 TOTP 2FA 설정이 강제됩니다.

## 게임 서버 등록 조건

패널에 게임 서버가 표시되려면 **두 가지 조건을 모두** 충족해야 합니다:

| 조건 | 설명 |
|------|------|
| `--label game-panel.managed=true` | 패널 관리 대상 라벨 |
| `--network game-servers` | 게임 서버 전용 네트워크 |

이 이중 검증으로 패널 인프라 컨테이너(backend, nginx, DB)는 절대 게임 서버 목록에 노출되지 않습니다.

### 게임 서버 띄우기 예시

```powershell
# 네트워크 생성 (최초 1회)
docker network create game-servers

# Minecraft 서버
docker run -d \
  --name minecraft-survival \
  --network game-servers \
  --label game-panel.managed=true \
  -e EULA=TRUE \
  -e DISABLE_GUI=true \
  -p 25565:25565 \
  itzg/minecraft-server:java21

# Valheim 서버
docker run -d \
  --name valheim-server \
  --network game-servers \
  --label game-panel.managed=true \
  -p 2456-2458:2456-2458/udp \
  lloesche/valheim-server

# docker-compose로 띄우는 경우
# labels:
#   - "game-panel.managed=true"
# networks:
#   - game-servers
```

라벨이나 네트워크 중 하나라도 빠지면 패널에서 보이지 않습니다.

## Discord 봇 설정

1. https://discord.com/developers/applications → 새 앱 생성
2. OAuth2 → Redirect URI: `https://game.example.com/api/auth/discord/callback`
3. Bot → 토큰 복사
4. 봇을 비공개 서버에 초대 (Server Members Intent 활성화)
5. .env에 Client ID, Secret, Bot Token, Guild ID 입력
6. 알림 채널 ID: Discord 설정 → 고급 → 개발자 모드 → 채널 우클릭 → "채널 ID 복사"

## 환경 변수 (.env)

### 앱 기본

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `APP_NAME` | `Game Panel` | 앱 표시 이름 |
| `APP_URL` | `https://game.example.com` | 외부 접근 URL (OAuth 콜백 등에 사용) |
| `DEBUG` | `false` | 디버그 모드 |

### JWT 인증

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `JWT_SECRET` | — | **필수.** 64자 이상 랜덤 문자열 |
| `JWT_ALGORITHM` | `HS256` | JWT 서명 알고리즘 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | 액세스 토큰 만료 (분) |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | 리프레시 토큰 만료 (일) |

### 데이터베이스

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/game_panel.db` | SQLAlchemy 비동기 DB URL |

### SMTP 메일 알림

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `SMTP_HOST` | `mail.example.com` | SMTP 서버 |
| `SMTP_PORT` | `587` | SMTP 포트 (STARTTLS) |
| `SMTP_USER` | — | SMTP 인증 계정 |
| `SMTP_PASS` | — | SMTP 인증 비밀번호 |
| `SMTP_FROM` | — | 발신 이메일 주소 |
| `ADMIN_EMAIL` | — | 관리자 알림 수신 이메일 |

### 초기 관리자

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `ADMIN_USERNAME` | `admin` | 초기 관리자 ID (첫 실행 시 자동 생성) |
| `ADMIN_PASSWORD` | — | **필수.** 초기 관리자 비밀번호 |

### Docker

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DOCKER_SOCKET` | `/var/run/docker.sock` | Docker 소켓 경로 |
| `GAME_NETWORK` | `game-servers` | 게임 서버용 Docker 네트워크 |

### 헬스체크

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `HEALTHCHECK_INTERVAL_MINUTES` | `5` | 헬스체크 주기 (분) |
| `AUTO_DELETE_DAYS` | `7` | 다운 상태 서버 자동 삭제까지 일수 |
| `HEALTHCHECK_NOTIFY` | `true` | 헬스체크 알림 활성화 |

### Discord OAuth2

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DISCORD_CLIENT_ID` | — | Discord 앱 Client ID |
| `DISCORD_CLIENT_SECRET` | — | Discord 앱 Client Secret |
| `DISCORD_REDIRECT_URI` | `{APP_URL}/api/auth/discord/callback` | OAuth2 콜백 URI |
| `DISCORD_GUILD_ID` | — | 비공개 디스코드 서버 ID |
| `DISCORD_BOT_TOKEN` | — | 서버 멤버 확인용 봇 토큰 |
| `DISCORD_ENABLED` | `true` | Discord 로그인 활성화 |

### Discord 채널 알림

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DISCORD_NOTIFY_CHANNEL_ID` | — | 서버 상태 알림 채널 ID |
| `DISCORD_REQUEST_CHANNEL_ID` | — | 게임 신청 알림 채널 ID (비워두면 notify 채널 사용) |
| `DISCORD_NOTIFY_ENABLED` | `true` | Discord 채널 알림 활성화 |

### Discord 역할 제한

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DISCORD_ALLOWED_ROLE_IDS` | — | 허용 역할 ID (쉼표 구분, 비워두면 멤버면 누구나 허용) |

역할 제한이 설정되면 로그인, 게임 신청, 서버 제어 **전체**에 적용됩니다.
여러 역할 중 하나라도 보유하면 허용. 관리자는 역할 제한 무시.
역할 ID 확인: Discord 서버 설정 → 역할 → 우클릭 → "역할 ID 복사" (개발자 모드 필요)

### 기타

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `INVITE_CODE_ENABLED` | `true` | 초대 코드 가입 활성화 |
| `MAX_MOD_UPLOAD_SIZE_MB` | `100` | 파일 업로드 최대 크기 (MB) |
| `PANEL_HTTP_PORT` | `8090` | 패널 HTTP 포트 |

## 디렉토리 구조

```
game-panel/
├── backend/app/
│   ├── auth/          # JWT + TOTP 2FA + 복구코드
│   ├── discord/       # Discord OAuth2 + 채널 알림
│   ├── invite/        # 초대 코드 시스템
│   ├── containers/    # Docker 제어 (격리)
│   ├── files/         # 범용 파일 탐색기
│   ├── rbac/          # 권한 관리
│   ├── requests/      # 게임 신청
│   ├── templates/     # 게임 설정 양식 관리
│   ├── mail/          # SMTP 알림
│   ├── scheduler/     # 헬스체크 + 자동 삭제
│   └── config.py      # 환경 변수 관리
├── frontend/src/views/
│   ├── Login.vue       # Discord + ID/PW + 초대코드 + 2FA
│   ├── Dashboard.vue   # 서버 현황 대시보드
│   ├── ServerControl.vue # 서버 제어 + 로그
│   ├── FileManager.vue # 웹 파일 탐색기 (줄번호 에디터)
│   ├── GameRequest.vue # 게임 서버 신청 (양식 다운로드/업로드)
│   ├── AdminUsers.vue  # 사용자 관리
│   ├── AdminPermissions.vue # 권한 관리
│   ├── AdminInvites.vue # 초대 코드 관리
│   ├── AdminRequests.vue # 게임 신청 관리 (다단계 워크플로우)
│   └── AdminTemplates.vue # 게임 설정 양식 관리
├── nginx/nginx.conf    # 리버스 프록시 (HTTP)
├── docker-compose.yml
├── docker-compose.test.yml  # 테스트 환경 (포트 8091)
├── .env.example
└── examples/
    └── minecraft.yml   # Minecraft 서버 예시
```

## 배포

```powershell
git clone https://git.namgun.or.kr/namgun/game-panel.git
cd game-panel
copy .env.example .env        # 환경변수 편집
docker compose build --no-cache frontend-build
docker compose up -d --build
```

> DB 스키마 변경 시 자동 마이그레이션됩니다. `down -v` 불필요, 사용자 데이터 보존.

## 변경 이력

### v0.5.1 — 버그 수정

- Vuetify3 v-file-input 호환 수정 (양식/설정 파일 업로드 실패 버그)

### v0.5.0 — 신청 워크플로우 대규모 개편

- **다단계 신청 워크플로우**: 대기 → 승인 → 생성중 → 생성완료 → 권한부여 → 방화벽 → 온보딩 (7단계)
- **게임 설정 양식 관리**: 관리자가 게임별 엑셀 양식 업로드 → 사용자가 다운로드/수정/첨부 신청
- **사용자 식별 통일**: 닉네임/이메일 수동 입력 제거, 계정 정보(디스코드 닉네임 + 인증 이메일)로 자동 연동
- **단계별 알림**: 각 단계 전환 시 이메일 + Discord 자동 발송
- **관리자 설정 양식 페이지**: 게임별 엑셀 양식 업로드/다운로드/삭제
- **사용자 설정 파일 첨부**: 신청 시 수정한 설정 엑셀 업로드, 관리자가 다운로드 가능
- 승인 다이얼로그에서 접속 IP, 포트, 초기 비밀번호, 설정 파일 경로 입력
- 승인/거절 시 신청자에게 이메일 + Discord 알림 자동 발송
- 권한 부여/변경 시 Discord 채널 + 이메일 알림
- 컨테이너 목록 로딩 속도 개선 (stats 분리 → 목록 즉시 표시 후 리소스 비동기 로딩)
- **파일 편집기 개선**: 줄번호 표시, 현재 줄/칸 표시, Tab 들여쓰기, 다크 테마 코드 에디터
- **자동 DB 마이그레이션**: 앱 시작 시 스키마 버전 체크 → 미적용 변경분 자동 적용 (사용자 데이터 보존)

### v0.4.2 — 버그 수정

- 권한 부여 시 `files` 액션이 유효하지 않다고 거부되는 문제 수정

### v0.4.1 — 버그 수정

- Discord OAuth2 redirect_uri URL 인코딩 누락 수정
- PWA 서비스 워커가 /api/ 경로를 가로채는 문제 수정
- 일반 사용자에게 권한 없는 컨테이너가 보이던 문제 수정
- 권한 부여 다이얼로그 컨테이너 선택형 드롭다운 적용

### v0.4.0 — 이메일 인증 시스템

- 가입 시 이메일 인증 (6자리 코드, 24시간 유효)
- 비밀번호 재설정 (이메일 링크, 1시간 유효)
- 2FA 분실 시 이메일로 복구 (6자리 코드, 15분 유효)
- 전체 가입자 (Discord 포함) 이메일 인증 필수
- 이메일 미인증 시 로그인 후 인증 화면으로 강제 이동
- 이메일 열거 방지 (비밀번호 재설정 시 동일 응답)

### v0.3.0 — Discord 역할 기반 접근 제어

- Discord 역할 기반 접근 제어 (로그인/신청/서버 제어 전체 적용)
  - `DISCORD_ALLOWED_ROLE_IDS`로 허용 역할 지정 (쉼표 구분)
  - 여러 역할 중 하나라도 있으면 허용, 관리자는 제한 무시
  - 매 로그인 시 역할 갱신, DB에 저장
- 게임 신청 API에 로그인 + 역할 체크 필수화
- 게임 서버 등록 조건 문서화 (라벨 + 네트워크 이중 검증)
- Minecraft 예제에 `DISABLE_GUI=true`, `java21` 태그 적용

### v0.2.0 — Discord 채널 알림 + UI 통일

- Discord 채널 알림 시스템 추가 (서버 상태, 게임 신청, 신규 가입)
- 헬스체크에 Discord 알림 통합 (다운/복구/삭제 예고/자동 삭제)
- 수동 서버 시작 시 Discord 알림
- 게임 서버 등록 조건 문서화 (라벨 + 네트워크 이중 검증)
- 전체 UI 테마 통일 (다크 + 블루 계열)
  - 버튼 사이즈/스타일 일관화
  - 카드 테두리, 테이블 헤더, Chip 스타일 통일
  - 복구 코드 페이지 다운로드 버튼 수정
- Nginx SSL 제거 → HTTP 전용 (앞단 리버스 프록시에서 TLS 처리)
- bcrypt 버전 고정 (passlib 호환 문제 해결)
- SQLAlchemy relationship ambiguity 해결 (Permission 모델)

### v0.1.0 — 초기 릴리즈

- Discord OAuth2 + 초대코드 + 자체 계정 인증
- TOTP 2FA + 복구 코드
- Docker 컨테이너 제어
- 범용 웹 파일 탐색기
- RBAC 서버별 권한
- 헬스체크 + 자동 삭제
- SMTP 알림
- 게임 서버 신청
