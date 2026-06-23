require('dotenv').config();
const express = require('express');
const path = require('path');
const fs = require('fs');
const Anthropic = require('@anthropic-ai/sdk');

const app = express();
app.use(express.static('public', { index: false }));
app.use(express.json());

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// Load university data once at startup
const universityData = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'public/data.json'), 'utf-8')
);

// genai_course_project/common.py의 to_document()와 동일한 필드 구성.
// 전체 데이터셋을 매번 Claude에 통째로 넘기는 대신, 질의와 겹치는 키워드가
// 많은 학교만 top-k로 추려서 보낸다 (논문 노트북에서 검증한 RAG 검색 방식).
function toDocument(u) {
  return [
    u['파견기관'], u['국가'], u['소재도시'], u['대륙'],
    `강의언어: ${u['강의언어'] || ''}`,
    `CGPA 기준: ${u['CGPA'] || ''}`,
    `어학 기준: ${u['어학 기준(총점)'] || ''}`,
    `전공제한: ${u['전공제한'] || ''}`,
    `학기제한: ${u['학기제한'] || ''}`,
    `학부/대학원: ${u['학부/대학원'] || ''}`,
    u['비고'] || '',
  ].filter(Boolean).join('\n');
}

const universityDocs = universityData.map(toDocument);

const STOPWORDS = new Set(['만점', '없음', '전체', '상관없음', '미입력', '추가', '요청', '학생', '프로필']);

function retrieveTopK(query, k = 15) {
  const tokens = query
    .replace(/[.,!?~()/:-]/g, ' ')
    .split(/\s+/)
    .filter(t => t.length >= 2 && !STOPWORDS.has(t));

  const scored = universityData.map((u, i) => ({
    u,
    score: tokens.reduce((acc, t) => acc + (universityDocs[i].includes(t) ? 1 : 0), 0),
  }));
  scored.sort((a, b) => b.score - a.score);

  const hits = scored.filter(s => s.score > 0);
  return (hits.length > 0 ? hits : scored).slice(0, k).map(s => s.u);
}

app.get('/', (req, res) => {
  const html = fs.readFileSync(path.join(__dirname, 'public/index.html'), 'utf-8');
  const injected = html.replace('ENTER YOUR API KEY', process.env.GOOGLE_MAPS_API_KEY || '');
  res.send(injected);
});

// POST /api/recommend
// Body: { query?: string, profile?: { cgpa, cgpaScale, region, language, toefl, ielts, major, notes } }
// Response: { recommendations: string[], explanation: string }
app.post('/api/recommend', async (req, res) => {
  const { query, profile } = req.body;

  let userMessage = query || '';
  if (profile) {
    userMessage = `학생 프로필:
- GPA: ${profile.cgpa} / ${profile.cgpaScale}만점
- 희망 지역: ${profile.region || '전체'}
- 강의언어: ${profile.language || '상관없음'}
- TOEFL(iBT): ${profile.toefl || '없음'}
- IELTS: ${profile.ielts || '없음'}
- 전공: ${profile.major || '미입력'}
- 추가 요청: ${profile.notes || '없음'}
이 조건에 맞는 교환대학을 추천해주세요.`;
  }

  if (!userMessage.trim()) {
    return res.status(400).json({ error: '질문 또는 프로필을 입력해주세요.' });
  }

  const candidates = retrieveTopK(userMessage, 15);

  try {
    const response = await client.messages.create({
      model: 'claude-sonnet-4-6',
      max_tokens: 2048,
      system: [
        {
          type: 'text',
          text: `당신은 서강대학교 교환학생 프로그램 전문 어드바이저입니다.
학생의 질문 또는 프로필을 분석해 최적의 교환대학을 추천합니다.

규칙:
- 반드시 제공된 대학 데이터 내에서만 추천할 것
- 추천 대학명은 데이터의 "파견기관" 필드값과 정확히 일치해야 함
- 최대 5개까지 추천
- 응답은 반드시 아래 JSON만 반환 (코드블록 없이, 다른 텍스트 없이):

{
  "recommendations": ["파견기관명1", "파견기관명2"],
  "explanation": "각 추천 이유를 학교별로 간략히 설명 (한국어, 친근한 말투)"
}`
        },
        {
          type: 'text',
          text: `서강대학교 파트너 대학 데이터 (질의와 관련성 높은 상위 ${candidates.length}개만 전달됨):\n${JSON.stringify(candidates)}`
        }
      ],
      messages: [{ role: 'user', content: userMessage }]
    });

    const raw = response.content[0].text.trim()
      .replace(/^```json\n?/, '').replace(/^```\n?/, '').replace(/\n?```$/, '');
    const parsed = JSON.parse(raw);
    res.json(parsed);
  } catch (err) {
    console.error('AI recommend error:', err.message);
    res.status(500).json({ error: 'AI 추천 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.' });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 서버 실행 중: http://localhost:${PORT}`);
});
