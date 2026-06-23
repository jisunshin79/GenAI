"""Generates exchange_rag_local.ipynb. Run once with `python build_local_notebook.py`.

This is the MAIN submission notebook. It does not call any external LLM API —
the generation step is a small open-source model fine-tuned locally with LoRA
on teacher-distilled labels (see generate_training_data.ipynb / train_data.jsonl).
"""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []


def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))


def code(text):
    cells.append(nbf.v4.new_code_cell(text))


md("""# 로컬 LoRA 파인튜닝으로 교환학교 추천하기 (제출용 메인 노트북)

이 노트북에서 하는 일은: 학교 정보를 검색(retrieval)해서 후보를 추리고, 그 후보를 가지고
작은 오픈소스 모델(`Qwen2.5-1.5B-Instruct`)이 추천을 만들어내는 것이다. Claude 같은
유료 API는 안 쓰고, Colab의 무료 GPU에서 모델을 직접 학습시킨다.

학습에 쓰는 예시 데이터는 미리 Claude한테 한 번 만들어달라고 해서 `train_data.jsonl`에
저장해뒀다 (`generate_training_data.ipynb` 참고). 이 노트북은 그 파일만 있으면 API 키 없이
끝까지 돌아간다.

비교하는 3가지 방법:
1. 규칙 기반 필터 — AI 없이 조건만 보고 거르기
2. 파인튜닝 전 모델 — 그냥 물어보기 (zero-shot)
3. 파인튜닝 후 모델 — 32개 예시로 한 번 더 학습시킨 버전 (LoRA)

평가 기준: 추천 5개 중 몇 개가 맞았는지(Precision@5/Recall@5), JSON 형식을 잘 지키는지,
존재하지 않는 학교를 추천하는 비율(hallucination), 그리고 검색 후보 수를 바꿔보는 실험.

**GPU 필요**: Colab 런타임을 GPU(T4 이상)로 설정하고 실행할 것.""")

md("""## 0. Colab 환경 설정 (로컬 Jupyter면 자동으로 건너뜀)
`public/data.json`과 `genai_course_project/`를 묶은 zip 파일(`project_for_colab.zip`)을
업로드하면 된다.""")

code("""\
import sys, os, zipfile

IN_COLAB = "google.colab" in sys.modules

if IN_COLAB:
    from google.colab import files

    print("project_for_colab.zip (public/ + genai_course_project/ 포함)을 업로드하세요.")
    uploaded = files.upload()
    zip_name = next(iter(uploaded))
    with zipfile.ZipFile(zip_name) as zf:
        zf.extractall("/content/Exchange-Univ-Map")
    os.chdir("/content/Exchange-Univ-Map/genai_course_project")

print("cwd:", os.getcwd())
""")

code("""\
!pip -q install -r requirements-local.txt
""")

code("""\
import json
import random
from pathlib import Path

import torch
import matplotlib.pyplot as plt
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model

import common as c

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"device: {DEVICE}")

universities = c.load_universities()
embedder, doc_embeddings = c.build_index(universities)
print(f"loaded {len(universities)} universities")
""")

md("""## 1. 학습 데이터 불러오기
`generate_training_data.ipynb`가 미리 만들어둔 예시들을 불러온다. 평가에 쓰는 8개 질문
(`common.TEST_PERSONAS`)은 이 학습 데이터와 겹치지 않게 따로 분리돼 있다.""")

code("""\
train_path = Path("train_data.jsonl")
assert train_path.exists(), "train_data.jsonl이 없습니다. generate_training_data.ipynb를 먼저 실행하세요."

train_records = [json.loads(line) for line in train_path.read_text(encoding="utf-8").splitlines() if line.strip()]
print(f"loaded {len(train_records)} training records")
print(train_records[0]["query"])
""")

md("## 2. 베이스 모델 불러오기")

code("""\
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"

quant_config = None
if DEVICE == "cuda":
    quant_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
    )

tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    quantization_config=quant_config,
    torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
    device_map="auto" if DEVICE == "cuda" else None,
)
if DEVICE != "cuda":
    model = model.to(DEVICE)
print("model loaded")
""")

md("""## 3. 추천을 만드는 함수들
질문 + 검색된 학교 후보를 모델에 넣고 JSON 답을 받아온다. 형식이 깨지면 한 번 더
"JSON만 답해줘"라고 강조해서 재시도한다.""")

code("""\
def build_messages(query: str, candidates: list[dict]) -> list[dict]:
    candidates_str = json.dumps(candidates, ensure_ascii=False)
    return [
        {"role": "system", "content": c.SYSTEM_INSTRUCTIONS + f"\\n\\n대학 데이터:\\n{candidates_str}"},
        {"role": "user", "content": query},
    ]


@torch.no_grad()
def generate(model, query: str, candidates: list[dict], max_new_tokens: int = 400) -> str:
    messages = build_messages(query, candidates)
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output_ids = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
    )
    new_tokens = output_ids[0][inputs["input_ids"].shape[1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True)


def generate_and_parse(model, query: str, candidates: list[dict]) -> dict:
    raw = generate(model, query, candidates)
    try:
        return c.parse_json_response(raw), True
    except Exception:
        pass
    # 1회 재시도: 포맷을 더 강하게 강조
    retry_query = query + "\\n\\n(반드시 JSON 객체만 응답하세요. 다른 텍스트를 추가하지 마세요.)"
    raw_retry = generate(model, retry_query, candidates)
    try:
        return c.parse_json_response(raw_retry), True
    except Exception:
        return {"recommendations": [], "explanation": ""}, False
""")

md("""## 4. 평가 함수 (세 방법 비교에 공통으로 사용)

**평가 기준에서 주의할 점**: "정답"을 정할 때 지역(`region`)과 학위과정(`degree`)만 보고
정한다 (전공이나 CGPA처럼 질문에 들어간 세부 조건은 정답 판단에 안 들어간다). 그래서 모델이
전공·CGPA까지 고려해서 그럴듯하게 추천해도, 이 기준에서는 "틀렸다"고 나올 수 있다 — 즉
zero_shot/fine_tuned의 recall이 낮게 나오는 게 모델이 못해서가 아니라 평가 기준이 거칠어서일
수도 있다는 점을 감안하고 결과를 봐야 한다.""")

code("""\
def evaluate_method(name: str, recommend_fn, k: int = 10):
    rows = []
    for p in c.TEST_PERSONAS:
        gt = c.ground_truth_set(p, universities)
        result = recommend_fn(p, k)
        precision, recall = c.precision_recall_at_5(result["recommendations"], gt)
        rows.append({
            "persona": p["id"],
            "method": name,
            "precision": precision,
            "recall": recall,
            "valid_json": result.get("valid_json", True),
            "hallucination": c.is_hallucinated(result["recommendations"], universities),
            "hallucinated_names": c.hallucinated_names(result["recommendations"], universities),
        })
    return rows


def rule_based_fn(persona, k):
    return c.rule_based_recommend(persona["region"], persona["degree"], universities)


def make_local_model_fn(model):
    def fn(persona, k):
        candidates = c.retrieve_topk(persona["query"], embedder, doc_embeddings, universities, k=k)
        parsed, valid = generate_and_parse(model, persona["query"], candidates)
        parsed["valid_json"] = valid
        return parsed
    return fn
""")

md("## 5. Zero-shot 평가 (파인튜닝하기 전 모델)")

code("""\
zero_shot_rows = evaluate_method("zero_shot", make_local_model_fn(model), k=10)
zero_shot_rows
""")

md("""## 6. LoRA로 파인튜닝하기
질문 부분에는 loss를 안 걸고(label=-100), 모델이 답해야 할 JSON 부분에만 loss를 걸어서
학습시킨다.""")

code("""\
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    task_type="CAUSAL_LM",
)
peft_model = get_peft_model(model, lora_config)
peft_model.print_trainable_parameters()
""")

code("""\
class RecommendationDataset(torch.utils.data.Dataset):
    def __init__(self, records, tokenizer, max_length: int = 1024):
        self.examples = []
        for r in records:
            messages = build_messages(r["query"], r["candidates"])
            prompt_text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            target_text = json.dumps(r["target"], ensure_ascii=False)
            full_text = prompt_text + target_text + tokenizer.eos_token

            prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
            full_ids = tokenizer(full_text, add_special_tokens=False)["input_ids"][:max_length]

            labels = [-100] * min(len(prompt_ids), len(full_ids)) + full_ids[len(prompt_ids):]
            labels = labels[: len(full_ids)]
            self.examples.append({"input_ids": full_ids, "labels": labels})

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        return self.examples[idx]


def collate_fn(batch):
    max_len = max(len(ex["input_ids"]) for ex in batch)
    pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id
    input_ids, labels, attention_mask = [], [], []
    for ex in batch:
        pad_len = max_len - len(ex["input_ids"])
        input_ids.append(ex["input_ids"] + [pad_id] * pad_len)
        labels.append(ex["labels"] + [-100] * pad_len)
        attention_mask.append([1] * len(ex["input_ids"]) + [0] * pad_len)
    return {
        "input_ids": torch.tensor(input_ids),
        "labels": torch.tensor(labels),
        "attention_mask": torch.tensor(attention_mask),
    }


train_dataset = RecommendationDataset(train_records, tokenizer)
print(f"train examples: {len(train_dataset)}")
""")

code("""\
from transformers import Trainer, TrainingArguments

training_args = TrainingArguments(
    output_dir="lora_checkpoints",
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    logging_steps=5,
    save_strategy="no",
    report_to="none",
    fp16=(DEVICE == "cuda"),
)

trainer = Trainer(
    model=peft_model,
    args=training_args,
    train_dataset=train_dataset,
    data_collator=collate_fn,
)
trainer.train()
""")

md("## 7. 파인튜닝한 모델 평가")

code("""\
peft_model.eval()
fine_tuned_rows = evaluate_method("fine_tuned", make_local_model_fn(peft_model), k=10)
fine_tuned_rows
""")

md("## 8. 규칙 기반 평가 + 세 방법 비교 요약")

code("""\
rule_rows = evaluate_method("rule_based", rule_based_fn, k=10)

all_rows = rule_rows + zero_shot_rows + fine_tuned_rows


def summarize(method: str):
    rows = [r for r in all_rows if r["method"] == method]
    return {
        "precision@5": c.mean(r["precision"] for r in rows),
        "recall@5": c.mean(r["recall"] for r in rows),
        "json_validity": c.mean(1.0 if r["valid_json"] else 0.0 for r in rows),
        "hallucination_rate": c.mean(r["hallucination"] for r in rows),
    }


summary = {m: summarize(m) for m in ["rule_based", "zero_shot", "fine_tuned"]}
summary
""")

md("""## 8.5 가짜 학교 이름 직접 확인해보기
hallucination_rate는 "몇 퍼센트가 가짜였다"는 숫자만 알려준다. 실제로 어떤 이름이 나왔는지
보면 — 오타 수준의 변형인지, 아예 다른 진짜 대학 이름을 가져다 쓴 건지 알 수 있고, 이걸 보면
모델이 "검색된 후보를 무시하고 사전학습 때 봤던 그럴듯한 대학 이름을 그냥 떠올린 것"인지
판단하는 데 도움이 된다.""")

code("""\
for method in ["zero_shot", "fine_tuned"]:
    rows = [r for r in all_rows if r["method"] == method and r["hallucinated_names"]]
    print(f"--- {method}: {len(rows)}/{len(c.TEST_PERSONAS)} personas with hallucinated names ---")
    for r in rows:
        print(f"  persona {r['persona']}: {r['hallucinated_names']}")
""")

md("""## 9. 검색 후보 수(top-k)를 바꿔보면 어떻게 될까
지금까지는 검색 후보를 10개로 고정했는데, 5개/10개/20개로 바꿔보면서 파인튜닝된 모델의
정확도와 hallucination이 어떻게 달라지는지 본다.""")

code("""\
ablation_rows = []
for k in [5, 10, 20]:
    rows = evaluate_method(f"fine_tuned_k{k}", make_local_model_fn(peft_model), k=k)
    ablation_rows.append({
        "k": k,
        "precision@5": c.mean(r["precision"] for r in rows),
        "recall@5": c.mean(r["recall"] for r in rows),
        "hallucination_rate": c.mean(r["hallucination"] for r in rows),
    })

ablation_rows
""")

md("## 10. 그래프로 보기")

code("""\
Path("figs").mkdir(exist_ok=True)
methods = ["rule_based", "zero_shot", "fine_tuned"]

fig, ax = plt.subplots(1, 2, figsize=(10, 4))
ax[0].bar(methods, [summary[m]["precision@5"] for m in methods])
ax[0].set_title("Precision@5")
ax[1].bar(methods, [summary[m]["recall@5"] for m in methods])
ax[1].set_title("Recall@5")
plt.tight_layout()
plt.savefig("figs/precision_recall_local.png", dpi=150)
plt.show()

fig, ax = plt.subplots(1, 2, figsize=(10, 4))
ax[0].bar(methods, [summary[m]["json_validity"] for m in methods])
ax[0].set_title("JSON Validity Rate")
ax[1].bar(methods, [summary[m]["hallucination_rate"] for m in methods])
ax[1].set_title("Hallucination Rate")
plt.tight_layout()
plt.savefig("figs/validity_hallucination.png", dpi=150)
plt.show()

fig, ax = plt.subplots(figsize=(5, 4))
ks = [row["k"] for row in ablation_rows]
ax.plot(ks, [row["precision@5"] for row in ablation_rows], marker="o", label="precision@5")
ax.plot(ks, [row["recall@5"] for row in ablation_rows], marker="o", label="recall@5")
ax.set_xlabel("top-k retrieved candidates")
ax.legend()
plt.tight_layout()
plt.savefig("figs/ablation_topk_local.png", dpi=150)
plt.show()

fig, ax = plt.subplots(figsize=(5, 4))
ax.plot(ks, [row["hallucination_rate"] for row in ablation_rows], marker="o", color="firebrick")
ax.set_xlabel("top-k retrieved candidates")
ax.set_ylabel("hallucination rate")
plt.tight_layout()
plt.savefig("figs/ablation_topk_hallucination.png", dpi=150)
plt.show()
""")

md("""## 11. 멀티턴 데모: 정보가 부족하면 한 번 더 물어보기
질문에 지역이나 학위과정 정보가 빠져 있으면, 추천하기 전에 **딱 한 번만** 더 물어보는
가장 단순한 버전을 시연한다. 위에서 측정한 정확도·hallucination 숫자에는 영향을 주지 않는
별도의 데모이고, "이 추천 시스템을 대화형으로 확장할 수 있다"는 걸 보여주기 위한 것이다.""")

code("""\
incomplete_query = "컴퓨터공학을 전공할 수 있는 교환학교를 추천해주세요."
missing = c.missing_slots(incomplete_query)
print("학생:", incomplete_query)
print("missing slots:", missing)

full_query = incomplete_query
if missing:
    followup = c.FOLLOWUP_QUESTIONS[missing[0]]
    print("어드바이저:", followup)

    user_answer = "아시아권이고 학부생입니다."  # 데모용 가상 답변 (실제로는 사용자 입력)
    print("학생:", user_answer)
    full_query = incomplete_query + " " + user_answer

print("still missing:", c.missing_slots(full_query))

candidates = c.retrieve_topk(full_query, embedder, doc_embeddings, universities, k=10)
followup_result, followup_valid = generate_and_parse(peft_model, full_query, candidates)
followup_result
""")

md("""## 12. 학습 데이터를 늘리면 더 좋아질까? (시도했지만 끝내지 못함)
3번~9번 결과를 보면 zero_shot이랑 fine_tuned가 거의 똑같았다. 제일 의심되는 이유는 학습
데이터가 겨우 32개뿐이라는 것이다. 그래서 똑같은 방식으로 학습 데이터만 ~90개로 늘려서
다시 파인튜닝해보고 32개짜리랑 비교해보려고 했다 (`generate_training_data.ipynb`에서
`train_data_large.jsonl`을 만들어야 함).

실제로 시도해봤지만, Colab GPU(T4, 15GB)에서 첫 번째 모델을 학습시킨 뒤라 메모리가
부족해서 두 번째 학습이 끝까지 돌지 않았다(`OutOfMemoryError`). 모델을 지우고 메모리를
비우는 코드를 넣어도 GPU 메모리 단편화 때문에 완전히 해결되지는 않았다. 시간 관계상 이
실험은 여기서 멈추고, **"데이터를 늘리면 실제로 좋아지는지"는 다음에 풀어야 할 질문으로
남긴다** (보고서 Conclusion 참고).""")

md("""## 결론 (요약용)
`summary`, `ablation_rows` 값을 보고서의 Experiments and Results에 그대로 인용한다.

- **rule_based가 zero_shot/fine_tuned보다 정확도(precision/recall)가 훨씬 높다.** 다만
  "정답"을 지역+학위과정만 보고 정해서 전공/CGPA 같은 세부 조건은 평가에 반영되지 않는다는
  한계가 있다 — 생성형 모델의 recall이 낮게 나온 것도 이 평가 기준이 거칠어서일 수 있다.
- **zero_shot과 fine_tuned(32개) 결과가 거의 똑같다** — 32개 정도의 데이터로는 LoRA
  파인튜닝이 별 효과를 못 냈다는 뜻이다. 학습 데이터를 더 늘리면 달라지는지는 시도했지만
  끝내지 못했다(섹션 12 참고).
- **hallucination_rate가 약 19%다.** 섹션 8.5에서 실제로 어떤 가짜 이름이 나왔는지 볼 수
  있다 — 모델이 검색된 후보를 무시하고, 사전학습 때 봤던 그럴듯한 대학 이름을 그대로
  가져다 쓰는 경향이 있다는 정성적 증거다.

종합하면, **답이 명확한 자격조건(지역/학위) 매칭에는 규칙 기반 필터링이 더 안전하고
정확하지만, 전공·CGPA·선호도처럼 자유롭게 표현되는 조건을 이해하고 설명을 만드는 데는
여전히 생성형 방식이 필요하다.** 다만 hallucination 위험을 줄이려면 검색 후보를 더 좁혀
주거나(섹션 9 참고), 추천을 후보 목록 안으로 강제하는 장치가 추가로 필요하다는 게 이
실험의 핵심 결론이다.""")

nb["cells"] = cells
out_path = "exchange_rag_local.ipynb"
nbf.write(nb, out_path)
print(f"wrote {out_path}")
