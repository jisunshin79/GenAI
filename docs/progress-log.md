# Progress Log

개발 진행 과정을 날짜별로 기록합니다.

---

## 2026-05-15

### 프로젝트 초기 설정

**완료:**
- GitHub 레포지토리 생성 (`jisunshin79/GenAI`)
- 4-에이전트 구조 설정 (PM / Design / Fullstack / AI)
- `CLAUDE.md` 프로젝트 문서 작성
- `.claude/agents/` 에이전트별 역할 파일 생성

**버그 수정 (Fullstack Agent):**
- `showContinent()` 마커 중복 생성 → 초기 1회 생성 후 visibility 토글로 변경
- 대륙 필터 후 전체 보기 복귀 불가 → "All" 버튼 추가
- `console.log` 디버그 로그 3개 제거
- `server.js` 파일 경로 오류 (`website.html` → `index.html`)

**PM 결정사항:**
- 생성형 AI 결합 방향 확정
- Phase 1: AI 어드바이저 챗봇 + 맞춤 진단 (Claude API + data.json)
- Phase 2: 서강대 국제처 RAG 어시스턴트

---

### Phase 1 구현 시작: AI 교환학생 어드바이저

**아키텍처 결정:**
- 모델: `claude-sonnet-4-6`
- Prompt Caching 적용: `data.json` (138개 대학, 187KB)을 캐시 블록으로 처리
- 백엔드: `POST /api/recommend` 엔드포인트
- 프론트엔드: 오른쪽 슬라이드인 AI 패널

**UI 구성:**
- 탭 1: 자유 검색 (자연어 입력 + 예시 칩)
- 탭 2: 맞춤 진단 (GPA / 지역 / 언어 / 어학점수 폼)
- 결과: 추천 대학 카드 + 지도 마커 하이라이트 + AI 설명

**기술 스택 추가:**
- `@anthropic-ai/sdk` — Claude API 클라이언트
- `dotenv` — 환경변수 관리

---

**Phase 1 구현 완료:**
- `server.js` — `/api/recommend` 엔드포인트 (Claude Sonnet 4.6, Prompt Caching)
- `public/index.html` — AI 어드바이저 사이드 패널 HTML
- `public/style.css` — AI 패널 전체 스타일 (슬라이드 애니메이션, 카드, 로딩 스피너)
- `public/main.js` — AI 패널 로직 (자유검색 / 맞춤진단 / 결과 하이라이트)
- `docs/progress-log.md`, `ROADMAP.md` 문서화
- `.env.example` 추가
- `@anthropic-ai/sdk`, `dotenv` 패키지 설치

**다음 단계:** Phase 2 — 서강대 국제처 RAG 어시스턴트
