# Exchange Univ Map — Project Guide

## 프로젝트 개요

서강대학교 교환학생 파트너 대학(전 세계)을 Google Maps API로 시각화하는 인터랙티브 웹앱.

- **목적:** 학생들이 교환학교 위치·정보를 지도에서 빠르게 탐색
- **데이터:** CSV(서강대 파견기관 자료) → Geocoding → `public/data.json`
- **배포:** Express.js 정적 서버, `localhost:3000`

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Frontend | HTML, CSS, Vanilla JavaScript |
| Backend | Node.js, Express.js |
| Map | Google Maps JavaScript API |
| Data Pipeline | csv-parser, node-fetch (Geocoding) |

## 디렉토리 구조

```
Exchange-Univ-Map/
├── public/
│   ├── index.html      # 메인 페이지 (Google Maps 로드)
│   ├── main.js         # 지도 초기화, 마커, 필터 로직
│   ├── style.css       # 전체 스타일
│   └── data.json       # Geocoded 대학 데이터 (빌드 산출물)
├── scripts/
│   └── convert.js      # CSV → JSON 변환 + Geocoding
├── data/
│   └── *.csv           # 원본 파견기관 데이터
├── server.js           # Express 서버
└── .claude/
    └── agents/         # 에이전트별 역할 정의
```

## 핵심 데이터 필드 (data.json)

```
파견기관, 대륙, 국가, 소재도시, 강의언어, CGPA,
어학 기준(총점), 파견인원(학기당), 학부/대학원,
전공제한, 학기제한, 비고, lat, lng
```

## 현재 기능

- 대륙 필터 버튼 (Asia / North America / Europe / Oceania / Latin America)
- 마커 hover → 요약 팝업 (대학명, 도시, 비고 2개)
- 마커 click → 상세 팝업 (전체 필드)
- 반응형 레이아웃

## 에이전트 구조

이 프로젝트는 4개 전문 에이전트가 협력하여 개발합니다.

| 에이전트 | 역할 파일 | 담당 영역 |
|---------|----------|----------|
| PM Agent | `.claude/agents/pm-agent.md` | 로드맵, 우선순위, 스펙 작성 |
| Design Agent | `.claude/agents/design-agent.md` | UI/UX, CSS, 인터랙션 디자인 |
| Fullstack Agent | `.claude/agents/fullstack-agent.md` | HTML/JS/CSS 구현, 백엔드, 데이터 파이프라인 |
| AI Agent | `.claude/agents/ai-agent.md` | AI 기능, NLP 검색, 데이터 강화 |

## API 키 관리

- Google Maps API 키: `public/index.html`의 `ENTER YOUR API KEY`
- Geocoding API 키: `scripts/convert.js`의 `apiKey` 변수
- **절대 API 키를 커밋하지 마세요** — `.gitignore`에 `.env` 추가 권장

## 개발 명령어

```bash
# 서버 실행
node server.js

# CSV → JSON 변환 (API 키 설정 후)
node scripts/convert.js
```
