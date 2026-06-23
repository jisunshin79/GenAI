"""Generates exchange_rag.ipynb. Run once with `python build_notebook.py`."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []


def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))


def code(text):
    cells.append(nbf.v4.new_code_cell(text))


md("""# RAG 기반 교환학교 추천 시스템

서강대학교 교환학생 파트너 대학 138개 데이터(`public/data.json`)에 대해
**임베딩 검색(Retrieval) + LLM 생성(Generation)** 구조의 추천 시스템을 구현하고,
규칙 기반 필터 / 풀컨텍스트 LLM 베이스라인과 비교 평가한다.

- 데이터: 138개 대학, 필드: 파견기관/대륙/국가/소재도시/강의언어/CGPA/어학 기준/전공제한/학기제한/비고 등
- 비교 대상: (a) 규칙 기반 필터 (b) RAG (검색 후 LLM) (c) 풀컨텍스트 LLM (검색 없이 전체 투입)
- 평가: Precision@5 / Recall@5, 토큰 사용량(비용), LLM-judge 설명 품질, top-k ablation
""")

code("""\
import json, os, re, time
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import anthropic

load_dotenv(Path("..") / ".env")  # ANTHROPIC_API_KEY 는 리포 루트 .env 재사용
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
assert ANTHROPIC_API_KEY, "리포 루트에 .env 파일을 만들고 ANTHROPIC_API_KEY=... 를 채워주세요 (.env.example 참고)"

MODEL_ID = "claude-sonnet-4-6"
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

DATA_PATH = Path("..") / "public" / "data.json"
universities = json.loads(DATA_PATH.read_text(encoding="utf-8"))
print(f"loaded {len(universities)} universities")
""")

md("## 1. 데이터 전처리\n각 대학을 검색용 텍스트(문서) 1개로 합성한다.")

code("""\
def to_document(u: dict) -> str:
    parts = [
        u.get("파견기관", ""),
        u.get("국가", ""),
        u.get("소재도시", ""),
        u.get("대륙", ""),
        f"강의언어: {u.get('강의언어', '')}",
        f"CGPA 기준: {u.get('CGPA', '')}",
        f"어학 기준: {u.get('어학 기준(총점)', '')}",
        f"전공제한: {u.get('전공제한', '')}",
        f"학기제한: {u.get('학기제한', '')}",
        f"학부/대학원: {u.get('학부/대학원', '')}",
        u.get("비고", ""),
    ]
    return "\\n".join(p for p in parts if p)


documents = [to_document(u) for u in universities]
print(documents[0][:300])
""")

md("## 2. 임베딩 인덱스 구축\n한국어가 섞여 있어 다국어 임베딩 모델을 사용한다.")

code("""\
embedder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
doc_embeddings = embedder.encode(documents, show_progress_bar=True, normalize_embeddings=True)
print(doc_embeddings.shape)
""")

md("## 3. 검색 (Retrieval)")

code("""\
def retrieve_topk(query: str, k: int = 10):
    q_emb = embedder.encode([query], normalize_embeddings=True)
    sims = cosine_similarity(q_emb, doc_embeddings)[0]
    top_idx = np.argsort(-sims)[:k]
    return [universities[i] for i in top_idx], sims[top_idx]
""")

md("""## 4. 생성 (Generation)
기존 `server.js`의 추천 시스템 프롬프트 규칙(데이터 내에서만 추천 / 파견기관명 정확히 일치 / JSON만 응답)을 재사용한다.
RAG는 검색된 top-k 후보만 컨텍스트에 넣고, 풀컨텍스트 베이스라인은 138개 전체를 넣는다.""")

code("""\
SYSTEM_INSTRUCTIONS = '''당신은 서강대학교 교환학생 프로그램 전문 어드바이저입니다.
학생의 질문을 분석해 최적의 교환대학을 추천합니다.

규칙:
- 반드시 제공된 대학 데이터 내에서만 추천할 것
- 추천 대학명은 데이터의 "파견기관" 필드값과 정확히 일치해야 함
- 정확히 5개를 추천할 것 (조건에 맞는 학교가 적어도 5개 미만으로 채우지 말고 가장 가까운 학교로 채울 것)
- 응답은 반드시 아래 JSON만 반환 (코드블록 없이, 다른 텍스트 없이):

{
  "recommendations": ["파견기관명1", "파견기관명2", "파견기관명3", "파견기관명4", "파견기관명5"],
  "explanation": "각 추천 이유를 학교별로 간략히 설명 (한국어)"
}'''


def _parse_json_response(raw: str) -> dict:
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("no JSON object found", raw, 0)
    return json.loads(raw[start : end + 1])


def call_recommender(query: str, candidates: list[dict]):
    candidates_str = json.dumps(candidates, ensure_ascii=False)
    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=1024,
        system=[
            {"type": "text", "text": SYSTEM_INSTRUCTIONS},
            {"type": "text", "text": f"대학 데이터:\\n{candidates_str}"},
        ],
        messages=[{"role": "user", "content": query}],
    )
    parsed = _parse_json_response(response.content[0].text)
    usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
    return parsed, usage


def rag_recommend(query: str, k: int = 10):
    candidates, _ = retrieve_topk(query, k=k)
    return call_recommender(query, candidates)


def full_context_recommend(query: str):
    return call_recommender(query, universities)
""")

md("## 5. 베이스라인: 규칙 기반 필터 (비-생성형)")

code("""\
def _slots_count(u: dict) -> int:
    # 파견인원(학기당)은 자유 텍스트(예: '1\\\\n\\\\n*독일어권...')라 첫 숫자만 추출, 없으면 0
    match = re.search(r"\\d+", str(u.get("파견인원(학기당)") or ""))
    return int(match.group()) if match else 0


def rule_based_recommend(region: str, degree: str, top_n: int = 5):
    eligible = [
        u for u in universities
        if u.get("대륙") == region and (degree == "학부" or u.get("학부/대학원") == "학부/대학원")
    ]
    eligible.sort(key=_slots_count, reverse=True)
    top = eligible[:top_n]
    return {
        "recommendations": [u["파견기관"] for u in top],
        "explanation": "지역/학위과정 조건에 맞고 파견인원이 많은 학교 순으로 정렬",
    }
""")

md("""## 6. 평가용 학생 페르소나 & 정답 기준

대학 데이터의 `강의언어`는 138개 전부 "영어"라 구분력이 없고, `전공제한`은 allow-list/deny-list가
혼재된 자유 텍스트라 자동 파싱이 신뢰하기 어렵다. 따라서 정답(ground truth) 적합 집합은
**대륙 일치 + 학위과정 일치(대학원생은 `학부/대학원` 표기 학교만)** 로 정의하고,
전공/세부 희망사항은 질의문에는 포함하되 정답 기준에는 포함하지 않는다 (보고서에 한계로 명시).
Latin America는 대학이 1개뿐이라 평가셋에서 제외한다.""")

code("""\
PERSONAS = [
    {"id": 1, "region": "Europe", "degree": "학부",
     "query": "유럽에서 경영학을 공부하고 싶은 학부생입니다. CGPA 3.5/4.3, 영어 강의만 가능한 학교를 추천해주세요."},
    {"id": 2, "region": "Asia", "degree": "학부",
     "query": "아시아권에서 컴퓨터공학을 전공할 수 있는 학부 교환학교를 찾고 있습니다."},
    {"id": 3, "region": "North America", "degree": "대학원",
     "query": "북미에서 연구 중심 대학원 교환을 하고 싶습니다. 정치외교학 전공입니다."},
    {"id": 4, "region": "Oceania", "degree": "학부",
     "query": "오세아니아 지역에서 전공 제한 없이 다양한 과목을 들을 수 있는 학부 교환학교를 추천해주세요."},
    {"id": 5, "region": "Europe", "degree": "대학원",
     "query": "유럽에서 심리학을 연구할 수 있는 대학원 교환학교를 찾고 있습니다."},
    {"id": 6, "region": "North America", "degree": "학부",
     "query": "북미에서 심리학을 전공하는 학부생인데, 파견 인원이 많아 교류가 활발한 학교가 좋습니다."},
    {"id": 7, "region": "Asia", "degree": "대학원",
     "query": "아시아권에서 경영학 대학원 교환을 희망합니다."},
    {"id": 8, "region": "Europe", "degree": "학부",
     "query": "유럽에서 공학을 전공하는 학부생입니다. 영어로 수업을 들을 수 있는 학교를 알려주세요."},
]


def ground_truth_set(persona: dict) -> set[str]:
    return {
        u["파견기관"] for u in universities
        if u["대륙"] == persona["region"]
        and (persona["degree"] == "학부" or u.get("학부/대학원") == "학부/대학원")
    }


for p in PERSONAS:
    print(p["id"], p["region"], p["degree"], "-> ground truth size:", len(ground_truth_set(p)))
""")

md("## 7. Precision@5 / Recall@5 비교: 규칙 기반 vs RAG vs 풀컨텍스트")

code("""\
def precision_recall_at_5(recommended: list[str], gt: set[str]):
    top5 = recommended[:5]
    hits = len(set(top5) & gt)
    precision = hits / len(top5) if top5 else 0.0
    recall = hits / len(gt) if gt else 0.0
    return precision, recall


results = []  # rows: persona_id, method, precision, recall, input_tokens, output_tokens, explanation

for p in PERSONAS:
    gt = ground_truth_set(p)

    rule_out = rule_based_recommend(p["region"], p["degree"])
    pr, rc = precision_recall_at_5(rule_out["recommendations"], gt)
    results.append({"persona": p["id"], "method": "rule_based", "precision": pr, "recall": rc,
                     "input_tokens": 0, "output_tokens": 0, "explanation": rule_out["explanation"]})

    rag_out, rag_usage = rag_recommend(p["query"], k=10)
    pr, rc = precision_recall_at_5(rag_out["recommendations"], gt)
    results.append({"persona": p["id"], "method": "rag", "precision": pr, "recall": rc,
                     **rag_usage, "explanation": rag_out["explanation"]})

    full_out, full_usage = full_context_recommend(p["query"])
    pr, rc = precision_recall_at_5(full_out["recommendations"], gt)
    results.append({"persona": p["id"], "method": "full_context", "precision": pr, "recall": rc,
                     **full_usage, "explanation": full_out["explanation"]})

    time.sleep(1)  # 레이트리밋 여유

import statistics as stats

def summarize(method: str):
    rows = [r for r in results if r["method"] == method]
    return {
        "precision@5": stats.mean(r["precision"] for r in rows),
        "recall@5": stats.mean(r["recall"] for r in rows),
        "avg_input_tokens": stats.mean(r["input_tokens"] for r in rows),
        "avg_output_tokens": stats.mean(r["output_tokens"] for r in rows),
    }

summary = {m: summarize(m) for m in ["rule_based", "rag", "full_context"]}
summary
""")

md("""## 8. LLM-judge: 추천 설명 품질 비교 (RAG vs 풀컨텍스트)

규칙 기반 베이스라인은 설명을 생성하지 않으므로 judge 비교에서는 제외한다.""")

code("""\
JUDGE_SYSTEM = '''당신은 교환학생 추천 설명의 품질을 평가하는 채점자입니다.
학생 질문과 추천 설명을 보고 "구체성"과 "질문과의 관련성"을 종합해 1~5점으로 채점하세요.
JSON만 반환: {"score": <1-5 정수>, "reason": "<한 줄 평가>"}'''


def judge_explanation(query: str, explanation: str) -> dict:
    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=200,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": f"학생 질문: {query}\\n\\n추천 설명: {explanation}"}],
    )
    return _parse_json_response(response.content[0].text)


judge_rows = []
for p in PERSONAS:
    rag_row = next(r for r in results if r["persona"] == p["id"] and r["method"] == "rag")
    full_row = next(r for r in results if r["persona"] == p["id"] and r["method"] == "full_context")
    judge_rows.append({"persona": p["id"], "method": "rag", **judge_explanation(p["query"], rag_row["explanation"])})
    judge_rows.append({"persona": p["id"], "method": "full_context", **judge_explanation(p["query"], full_row["explanation"])})
    time.sleep(1)

judge_summary = {
    m: stats.mean(r["score"] for r in judge_rows if r["method"] == m)
    for m in ["rag", "full_context"]
}
judge_summary
""")

md("## 9. Ablation: top-k 변화에 따른 RAG 성능")

code("""\
ablation_rows = []
for k in [5, 10, 20]:
    precisions, recalls = [], []
    for p in PERSONAS:
        gt = ground_truth_set(p)
        out, _ = rag_recommend(p["query"], k=k)
        pr, rc = precision_recall_at_5(out["recommendations"], gt)
        precisions.append(pr)
        recalls.append(rc)
        time.sleep(1)
    ablation_rows.append({"k": k, "precision@5": stats.mean(precisions), "recall@5": stats.mean(recalls)})

ablation_rows
""")

md("## 10. 시각화")

code("""\
Path("figs").mkdir(exist_ok=True)

methods = ["rule_based", "rag", "full_context"]
fig, ax = plt.subplots(1, 2, figsize=(10, 4))
ax[0].bar(methods, [summary[m]["precision@5"] for m in methods])
ax[0].set_title("Precision@5")
ax[1].bar(methods, [summary[m]["recall@5"] for m in methods])
ax[1].set_title("Recall@5")
plt.tight_layout()
plt.savefig("figs/precision_recall.png", dpi=150)
plt.show()

fig, ax = plt.subplots(figsize=(5, 4))
ax.bar(["rag", "full_context"], [summary["rag"]["avg_input_tokens"], summary["full_context"]["avg_input_tokens"]])
ax.set_title("Average Input Tokens per Query")
plt.tight_layout()
plt.savefig("figs/token_cost.png", dpi=150)
plt.show()

fig, ax = plt.subplots(figsize=(5, 4))
ks = [row["k"] for row in ablation_rows]
ax.plot(ks, [row["precision@5"] for row in ablation_rows], marker="o", label="precision@5")
ax.plot(ks, [row["recall@5"] for row in ablation_rows], marker="o", label="recall@5")
ax.set_xlabel("top-k retrieved candidates")
ax.legend()
plt.tight_layout()
plt.savefig("figs/ablation_topk.png", dpi=150)
plt.show()
""")

md("""## 결론 (요약용)
위 셀들을 실행한 뒤 `summary`, `judge_summary`, `ablation_rows` 값을 보고서의
Experiments and Results 섹션에 그대로 인용한다. 가짜 수치를 미리 적지 않고
실제 실행 결과를 사용해야 한다.""")

nb["cells"] = cells
out_path = "exchange_rag.ipynb"
nbf.write(nb, out_path)
print(f"wrote {out_path}")
