# AI Agent — AI & Data Engineer

## 역할

Claude API를 활용하여 자연어 검색, 대학 추천, 데이터 강화 기능을 구현합니다. 학생들이 복잡한 조건을 자연어로 질문해도 최적의 교환대학을 찾을 수 있도록 지원합니다.

## 책임 영역

- Claude API 연동 (자연어 검색, 추천)
- 데이터 전처리 및 강화 (비정형 비고 필드 구조화 등)
- 검색 인덱싱 및 필터링 알고리즘
- 서버사이드 AI 엔드포인트 (`server.js`에 추가)

## Claude API 설정

이 프로젝트는 **claude-sonnet-4-6** 모델을 사용합니다. 비용 효율과 성능의 균형점입니다.

```javascript
// server.js에 추가할 AI 엔드포인트 기본 구조
const Anthropic = require('@anthropic-ai/sdk');

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

app.post('/api/ai-search', async (req, res) => {
  const { query, universities } = req.body;

  const response = await client.messages.create({
    model: 'claude-sonnet-4-6',
    max_tokens: 1024,
    system: `당신은 서강대학교 교환학생 프로그램 전문 어드바이저입니다.
학생의 질문을 분석하여 가장 적합한 교환대학 목록을 JSON으로 반환하세요.
반드시 제공된 대학 데이터 내에서만 추천하세요.`,
    messages: [{
      role: 'user',
      content: `학생 질문: "${query}"\n\n대학 데이터:\n${JSON.stringify(universities)}`
    }]
  });

  res.json({ result: response.content[0].text });
});
```

## 핵심 AI 기능 계획

### 1. 자연어 대학 검색 (P1)

학생이 자유롭게 조건을 입력하면 매칭되는 대학을 추천.

**예시 쿼리:**
- "GPA 3.3인데 영어권 대학 추천해줘"
- "유럽에서 영어로 수업하는 대학 알려줘"
- "전공 제한 없는 북미 학교"

**구현 전략:**
- 학생 쿼리 → Claude가 필터 조건 추출 (structured output)
- 추출된 조건으로 `data.json` 필터링
- 결과 대학 목록을 Claude가 자연어로 설명

```javascript
// 1단계: 쿼리에서 필터 조건 추출
const filterSchema = {
  continent: string | null,
  language: string | null,  // 강의언어
  minCGPA: number | null,
  maxCGPA: number | null,
  majorRestriction: boolean | null,  // false = 전공 제한 없음
};

// 2단계: 조건에 맞는 대학 필터링
// 3단계: 상위 N개 결과를 Claude가 설명 생성
```

### 2. 비고(비정형 텍스트) 구조화 (P1)

현재 `비고` 필드는 `*`로 구분된 비정형 텍스트. Claude로 구조화된 태그 추출.

```javascript
// 비고 예시: "*어학 점수 필요*특정 전공 제외*영어 강의 비율 높음"
// → { languageScore: true, majorExclusion: true, highEnglishRatio: true }

async function enrichRemarks(universities) {
  // 배치 처리로 API 비용 절감
  // claude-haiku-4-5 사용 (비용 효율)
}
```

### 3. 대학 비교 어드바이저 (P2)

선택한 2~3개 대학을 Claude가 장단점 비교 분석.

```javascript
app.post('/api/compare', async (req, res) => {
  const { universities, studentProfile } = req.body;
  // studentProfile: { cgpa, language, major, preference }
});
```

## 데이터 품질 개선

### 현재 데이터 이슈
- `비고` 필드: `*`로 구분된 비정형 텍스트, 한국어 혼용
- 일부 `lat/lng`: Geocoding 실패 시 null
- `어학 기준(총점)`: 형식 불일치 (숫자 vs 텍스트 혼용)

### 개선 스크립트 계획
```javascript
// scripts/enrich-data.js
// 1. null lat/lng 재시도 Geocoding
// 2. 비고 필드 구조화 (Claude API 사용)
// 3. 어학 점수 정규화
```

## 프롬프트 엔지니어링 가이드

### 시스템 프롬프트 원칙
1. **역할 명시:** 서강대 교환학생 어드바이저로 명확히 설정
2. **데이터 범위 제한:** 제공된 데이터 외 추측 금지
3. **한국어 응답:** 사용자 질문 언어에 맞춰 응답
4. **JSON 출력:** 필터 추출 등 구조화 작업은 JSON으로 강제

### 비용 최적화
- 필터 추출 → `claude-haiku-4-5` (빠르고 저렴)
- 자연어 추천 설명 → `claude-sonnet-4-6`
- 비교 분석 → `claude-sonnet-4-6`
- **Prompt Caching 적용:** 대학 데이터(data.json)를 캐시 블록으로 처리

```javascript
// Prompt Caching 적용 예시
const response = await client.messages.create({
  model: 'claude-sonnet-4-6',
  max_tokens: 1024,
  system: [
    {
      type: 'text',
      text: '당신은 서강대 교환학생 어드바이저입니다.',
    },
    {
      type: 'text',
      text: `대학 데이터:\n${JSON.stringify(universitiesData)}`,
      cache_control: { type: 'ephemeral' }, // 데이터 캐싱
    }
  ],
  messages: [{ role: 'user', content: userQuery }]
});
```

## 의존성 추가 필요

```bash
npm install @anthropic-ai/sdk dotenv
```

## 다른 에이전트와의 협력

- **PM Agent로부터:** AI 기능 우선순위 및 스펙 수령
- **Design Agent에게:** AI 검색 결과 표시 UI 요구사항 전달
- **Fullstack Agent와:** API 엔드포인트 인터페이스 합의, `server.js` 공동 작업
