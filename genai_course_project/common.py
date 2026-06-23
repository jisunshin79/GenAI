"""Shared data/retrieval/evaluation utilities for both notebooks.

generate_training_data.ipynb uses this to build (query, candidates) pairs and
send them to the teacher (Claude). exchange_rag_local.ipynb uses the same
retrieval + evaluation code so the local student model is compared on
identical ground rules.
"""
import json
import re
import statistics as stats
from pathlib import Path

import numpy as np

DATA_PATH = Path(__file__).parent.parent / "public" / "data.json"
EMBEDDER_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

SYSTEM_INSTRUCTIONS = """당신은 서강대학교 교환학생 프로그램 전문 어드바이저입니다.
학생의 질문을 분석해 최적의 교환대학을 추천합니다.

규칙:
- 반드시 제공된 대학 데이터 내에서만 추천할 것
- 추천 대학명은 데이터의 "파견기관" 필드값과 정확히 일치해야 함
- 정확히 5개를 추천할 것 (조건에 맞는 학교가 5개 미만이면 가장 가까운 학교로 채울 것)
- 응답은 반드시 아래 JSON만 반환 (코드블록 없이, 다른 텍스트 없이):

{
  "recommendations": ["파견기관명1", "파견기관명2", "파견기관명3", "파견기관명4", "파견기관명5"],
  "explanation": "각 추천 이유를 학교별로 간략히 설명 (한국어)"
}"""

# 평가용 고정 테스트셋. 학습 데이터 생성 시 이 8개와 동일한 질의는 사용하지 않는다 (train/test 분리).
TEST_PERSONAS = [
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


def load_universities() -> list[dict]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


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
    return "\n".join(p for p in parts if p)


def build_index(universities: list[dict]):
    """Loads the multilingual embedder and encodes all university documents."""
    from sentence_transformers import SentenceTransformer

    embedder = SentenceTransformer(EMBEDDER_MODEL_NAME)
    documents = [to_document(u) for u in universities]
    doc_embeddings = embedder.encode(documents, show_progress_bar=True, normalize_embeddings=True)
    return embedder, doc_embeddings


def retrieve_topk(query: str, embedder, doc_embeddings, universities: list[dict], k: int = 10):
    from sklearn.metrics.pairwise import cosine_similarity

    q_emb = embedder.encode([query], normalize_embeddings=True)
    sims = cosine_similarity(q_emb, doc_embeddings)[0]
    top_idx = np.argsort(-sims)[:k]
    return [universities[i] for i in top_idx]


def ground_truth_set(persona: dict, universities: list[dict]) -> set[str]:
    return {
        u["파견기관"] for u in universities
        if u["대륙"] == persona["region"]
        and (persona["degree"] == "학부" or u.get("학부/대학원") == "학부/대학원")
    }


def precision_recall_at_5(recommended: list[str], gt: set[str]):
    top5 = recommended[:5]
    hits = len(set(top5) & gt)
    precision = hits / len(top5) if top5 else 0.0
    recall = hits / len(gt) if gt else 0.0
    return precision, recall


def _slots_count(u: dict) -> int:
    """파견인원(학기당) is free text (e.g. '1\\n\\n*독일어권...'), so just take the
    first number found, defaulting to 0."""
    match = re.search(r"\d+", str(u.get("파견인원(학기당)") or ""))
    return int(match.group()) if match else 0


def rule_based_recommend(region: str, degree: str, universities: list[dict], top_n: int = 5) -> dict:
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


def parse_json_response(raw: str) -> dict:
    """Extracts and parses the {...} object from a model response, tolerating
    code fences and any leading/trailing prose the model adds despite
    instructions to return JSON only. Raises on malformed input."""
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("no JSON object found", raw, 0)
    return json.loads(raw[start : end + 1])


def is_hallucinated(recommendations: list[str], universities: list[dict]) -> float:
    """Fraction of recommended names that do not exist anywhere in the dataset."""
    valid_names = {u["파견기관"] for u in universities}
    if not recommendations:
        return 0.0
    bad = sum(1 for name in recommendations if name not in valid_names)
    return bad / len(recommendations)


def hallucinated_names(recommendations: list[str], universities: list[dict]) -> list[str]:
    """The subset of recommended names that do not exist anywhere in the dataset
    (정성 분석용 — is_hallucinated()는 비율만 주지만 이건 실제로 어떤 이름이 지어졌는지 보여준다)."""
    valid_names = {u["파견기관"] for u in universities}
    return [name for name in recommendations if name not in valid_names]


def mean(values) -> float:
    values = list(values)
    return stats.mean(values) if values else 0.0


# 멀티턴 확장 데모용: 질의에 지역/학위 정보가 빠져 있으면 1회만 추가로 물어보기 위한
# 단순 키워드 기반 슬롯 추출. (정량 평가에는 쓰지 않음)
REGION_KEYWORDS = {
    "Asia": ["아시아"],
    "Europe": ["유럽"],
    "North America": ["북미"],
    "Oceania": ["오세아니아"],
    "Latin America": ["남미", "라틴"],
}
DEGREE_KEYWORDS = {
    "학부": ["학부생", "학부"],
    "대학원": ["대학원생", "대학원"],
}
FOLLOWUP_QUESTIONS = {
    "region": "어느 지역의 학교를 찾으시나요? (예: 아시아, 유럽, 북미, 오세아니아, 남미)",
    "degree": "학부생이신가요, 대학원생이신가요?",
}


def detect_region(query: str) -> str | None:
    for region, keywords in REGION_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            return region
    return None


def detect_degree(query: str) -> str | None:
    for degree, keywords in DEGREE_KEYWORDS.items():
        if any(kw in query for kw in keywords):
            return degree
    return None


def missing_slots(query: str) -> list[str]:
    """질의에서 지역/학위 정보를 찾지 못하면 해당 슬롯 이름을 반환한다."""
    missing = []
    if detect_region(query) is None:
        missing.append("region")
    if detect_degree(query) is None:
        missing.append("degree")
    return missing
