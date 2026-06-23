"""Generates generate_training_data.ipynb. Run once with `python build_training_data_notebook.py`."""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []


def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))


def code(text):
    cells.append(nbf.v4.new_code_cell(text))


md("""# 학습 데이터 생성 (Teacher 라벨링)

이 노트북은 **제출용 메인 노트북이 아니다**. Claude API(teacher)를 사용해 합성 학생 질의에 대한
정답 추천+설명을 1회 생성하고 `train_data.jsonl`로 저장하는 용도다. 이 출력 파일만 있으면
`exchange_rag_local.ipynb`(로컬 LoRA 파인튜닝 + 평가, 메인 제출 노트북)는 API 키 없이 재현 가능하다.

평가용 8개 테스트 페르소나(`common.TEST_PERSONAS`)와 겹치지 않는 별도의 학습 질의를 코드로
생성해서 train/test를 분리한다.""")

code("""\
import json, os, time
from pathlib import Path

from dotenv import load_dotenv
import anthropic

import common as c

load_dotenv(Path("..") / ".env")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
assert ANTHROPIC_API_KEY, "리포 루트에 .env 파일을 만들고 ANTHROPIC_API_KEY=... 를 채워주세요"

MODEL_ID = "claude-sonnet-4-6"
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

universities = c.load_universities()
embedder, doc_embeddings = c.build_index(universities)
print(f"loaded {len(universities)} universities, embeddings shape={doc_embeddings.shape}")
""")

md("## 1. 학습용 페르소나 질의 생성 (템플릿 기반, API 불필요)")

code("""\
REGIONS = ["Europe", "North America", "Asia", "Oceania"]
DEGREES = ["학부", "대학원"]
MAJORS = [
    "경영학", "컴퓨터공학", "심리학", "정치외교학", "전자공학", "경제학",
    "영문학", "사회학", "기계공학", "화학공학", "교육학", "커뮤니케이션학",
]
REGION_KR = {"Europe": "유럽", "North America": "북미", "Asia": "아시아", "Oceania": "오세아니아"}

QUERY_TEMPLATES = [
    "{region_kr}에서 {major}을 전공하고 싶은 {degree} 학생입니다. 영어 강의가 가능한 학교를 추천해주세요.",
    "{degree} 과정이고 {major}에 관심이 많습니다. {region_kr} 지역 교환학교 중 추천할 곳이 있나요?",
    "{region_kr} 교환학교를 알아보고 있는 {degree}생입니다. {major} 관련 수업을 들을 수 있는 학교 위주로 알려주세요.",
]


def build_train_personas():
    personas = []
    pid = 0
    for region in REGIONS:
        for degree in DEGREES:
            for i, major in enumerate(MAJORS):
                template = QUERY_TEMPLATES[i % len(QUERY_TEMPLATES)]
                query = template.format(region_kr=REGION_KR[region], major=major, degree=degree)
                personas.append({"id": pid, "region": region, "degree": degree, "major": major, "query": query})
                pid += 1
    return personas


train_personas = build_train_personas()
print(f"generated {len(train_personas)} training personas")

# train/test 질의 중복 방지 확인
test_queries = {p["query"] for p in c.TEST_PERSONAS}
train_personas = [p for p in train_personas if p["query"] not in test_queries]
print(f"after de-dup against test set: {len(train_personas)}")
""")

md("""## 2. 학습 세트 크기 줄이기
4 지역 × 2 학위 × 12 전공 = 96개는 API 호출이 많아지므로, 지역·학위 조합별로 전공을 4개씩만 샘플링해
~32개로 줄인다 (Colab LoRA 학습에는 이 정도로 충분하고 시간도 절약됨). 전체 96개는
`train_personas_full`에 따로 남겨서, **데이터 규모가 파인튜닝 효과에 영향을 주는지**를 보는
별도 실험(섹션 5)에 쓴다.""")

code("""\
import random

random.seed(42)
SAMPLED_MAJORS_PER_GROUP = 4

train_personas_full = train_personas  # 96개 (de-dup 후), 데이터 규모 실험용

sampled = []
for region in REGIONS:
    for degree in DEGREES:
        group = [p for p in train_personas_full if p["region"] == region and p["degree"] == degree]
        sampled.extend(random.sample(group, min(SAMPLED_MAJORS_PER_GROUP, len(group))))

train_personas = sampled
print(f"small training set size: {len(train_personas)}")
print(f"full training set size: {len(train_personas_full)}")
""")

md("## 3. 각 질의에 대해 검색(top-k) 후 Claude로 teacher 라벨 생성")

code("""\
def call_teacher(query: str, candidates: list[dict]) -> dict:
    candidates_str = json.dumps(candidates, ensure_ascii=False)
    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=1024,
        system=[
            {"type": "text", "text": c.SYSTEM_INSTRUCTIONS},
            {"type": "text", "text": f"대학 데이터:\\n{candidates_str}"},
        ],
        messages=[{"role": "user", "content": query}],
    )
    return c.parse_json_response(response.content[0].text)


TOP_K = 10


def generate_records(personas: list[dict]) -> list[dict]:
    records = []
    for p in personas:
        candidates = c.retrieve_topk(p["query"], embedder, doc_embeddings, universities, k=TOP_K)
        try:
            target = call_teacher(p["query"], candidates)
        except Exception as e:
            print(f"skip persona {p['id']} due to error: {e}")
            continue
        records.append({
            "query": p["query"],
            "candidates": candidates,
            "target": target,
        })
        time.sleep(1)
    return records


records = generate_records(train_personas)
print(f"collected {len(records)} training records (small set)")
""")

md("## 4. `train_data.jsonl` 로 저장 (32개, 메인 노트북 기본 학습셋)")

code("""\
out_path = Path("train_data.jsonl")
with out_path.open("w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\\n")

print(f"wrote {len(records)} records to {out_path}")
print(json.dumps(records[0], ensure_ascii=False, indent=2)[:800])
""")

md("""## 5. 데이터 규모 실험용 학습셋 생성 (~96개)
`exchange_rag_local.ipynb`의 "데이터 규모 확장 실험" 섹션에서, 학습 데이터를 32개 → ~96개로
늘렸을 때 LoRA 파인튜닝 효과(precision/recall, hallucination rate)가 실제로 좋아지는지 검증한다.
API 호출이 더 많이 들어가므로(약 90회) 시간이 좀 더 걸린다.""")

code("""\
records_large = generate_records(train_personas_full)
print(f"collected {len(records_large)} training records (large set)")

out_path_large = Path("train_data_large.jsonl")
with out_path_large.open("w", encoding="utf-8") as f:
    for r in records_large:
        f.write(json.dumps(r, ensure_ascii=False) + "\\n")

print(f"wrote {len(records_large)} records to {out_path_large}")
""")

nb["cells"] = cells
out_path = "generate_training_data.ipynb"
nbf.write(nb, out_path)
print(f"wrote {out_path}")
