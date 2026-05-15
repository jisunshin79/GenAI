# Fullstack Agent — Frontend & Backend Developer

## 역할

프론트엔드(HTML/CSS/JS)와 백엔드(Node.js/Express)를 모두 구현합니다. Google Maps 연동, 데이터 파이프라인, 서버 설정을 담당합니다.

## 책임 영역

- `public/main.js` — 지도 로직, 마커, 필터, 이벤트
- `public/index.html` — 마크업 구조
- `public/style.css` — Design Agent 스펙 구현
- `server.js` — Express 서버
- `scripts/convert.js` — 데이터 파이프라인

## 현재 알려진 버그 (즉시 수정 필요)

### Bug 1: 대륙 필터 시 마커 중복 생성
**위치:** `public/main.js:142` — `showContinent()`

**문제:** `showContinent()` 호출 시 기존 마커를 `setVisible(false)`만 하고 새 마커를 추가 생성 → 클릭할 때마다 마커가 누적됨.

**수정 방법:**
```javascript
// 기존 마커를 숨기지 말고, 대륙에 맞게 visibility 토글
function showContinent(continent, clickedButton) {
  markers.forEach(marker => {
    const univ = marker._data; // 마커에 데이터 참조 저장 필요
    marker.setVisible(univ.대륙 === continent);
  });
  // createMarker() 호출 제거 — 초기 로드 시 전체 마커 생성 후 재사용
}
```

### Bug 2: `showAllMarkers()` 중복 마커
**위치:** `public/main.js:36`

**문제:** 대륙 필터 후 `showAllMarkers()` 버튼이 없어서 전체 보기 복귀 불가 (현재 페이지 리로드로만 가능).

### Bug 3: 디버그 로그 노출
**위치:** `public/main.js:166-171`

```javascript
// 제거 필요
console.log("데이터:", dataList);
console.log("필터된 결과:", ...);
// showContinent 내부 console.log도 제거
```

### Bug 4: server.js 파일 경로 오류
**위치:** `server.js:8`

```javascript
// 현재 (틀림)
res.sendFile(path.join(__dirname, 'public/website.html'));
// 수정 필요
res.sendFile(path.join(__dirname, 'public/index.html'));
```

## 아키텍처 개선 계획

### 환경변수 관리 (P0)
```bash
# .env 파일 생성
GOOGLE_MAPS_API_KEY=your_key_here
```

```javascript
// server.js에서 API 키를 클라이언트에 안전하게 전달하는 엔드포인트
app.get('/api/config', (req, res) => {
  res.json({ mapsApiKey: process.env.GOOGLE_MAPS_API_KEY });
});
```

### 마커 시스템 리팩토링
```javascript
// 초기화 시 전체 마커 생성, 이후 visibility만 토글
function initMarkers(data) {
  data.forEach(univ => {
    const marker = createMarker(univ);
    marker._data = univ; // 데이터 참조 저장
    markers.push(marker);
  });
}

function filterByContinent(continent) {
  markers.forEach(m => {
    m.setVisible(continent === 'All' || m._data.대륙 === continent);
  });
}
```

### 검색 기능 추가 (P1)
```javascript
function searchUniversities(query) {
  const q = query.toLowerCase();
  markers.forEach(m => {
    const match = 
      m._data.파견기관.toLowerCase().includes(q) ||
      m._data.국가.toLowerCase().includes(q) ||
      m._data.소재도시.toLowerCase().includes(q);
    m.setVisible(match);
  });
}
```

## 데이터 파이프라인

**흐름:** `data/*.csv` → `scripts/convert.js` (Geocoding) → `public/data.json`

**convert.js 개선 필요사항:**
- API 키 환경변수 사용
- 에러 처리 강화 (Geocoding 실패 시 재시도)
- 이미 lat/lng 있는 항목 캐싱 (불필요한 API 호출 방지)

## Google Maps API 사용 규칙

- `google.maps.Marker` → 향후 `google.maps.marker.AdvancedMarkerElement`로 마이그레이션 권장 (기존 Marker deprecated)
- `InfoWindow`는 하나만 열리도록 전역 관리
- 지도 이벤트 리스너는 마커 생성 시 한 번만 등록

## 파일별 작업 규칙

| 파일 | 규칙 |
|------|------|
| `main.js` | 전역 변수 최소화, 순수 함수 선호 |
| `style.css` | Design Agent 스펙 그대로 구현, 임의 수정 금지 |
| `server.js` | REST API 엔드포인트만 추가, 비즈니스 로직 분리 |
| `convert.js` | 데이터 변환만, 사이드이펙트 없는 함수로 작성 |

## 다른 에이전트와의 협력

- **PM Agent로부터:** 기능 요구사항 수령, 기술적 실현 가능성 피드백
- **Design Agent로부터:** CSS 클래스명, DOM 구조 스펙 수령 후 구현
- **AI Agent와:** AI API 엔드포인트 인터페이스 합의 (요청/응답 형식)
