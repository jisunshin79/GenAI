require('dotenv').config();
const express = require('express');
const path = require('path');
const fs = require('fs');
const Anthropic = require('@anthropic-ai/sdk');

const app = express();
app.use(express.static('public'));
app.use(express.json());

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// Load university data once at startup (used as cached prompt context)
const universityData = JSON.parse(
  fs.readFileSync(path.join(__dirname, 'public/data.json'), 'utf-8')
);
const universityDataStr = JSON.stringify(universityData);

app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public/index.html'));
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
          text: `서강대학교 파트너 대학 데이터:\n${universityDataStr}`,
          cache_control: { type: 'ephemeral' }
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
