# Exchange RAG + 로컬 LoRA — GenAI 수업 Final Project 구현

## 제출용 핵심 산출물

**`exchange_rag_local.ipynb`** — 임베딩 검색(retrieval) + 로컬에서 LoRA로 파인튜닝한
`Qwen2.5-1.5B-Instruct` 생성(generation)으로 구성된 추천 시스템. **API 키 없이 끝까지
실행 가능** (Google Colab GPU 런타임 필요).

다른 파일들은 이 메인 노트북을 위한 준비/배경 자료다.

## 전체 실행 순서

1. (1회만, API 키 있는 환경에서) `generate_training_data.ipynb` 실행
   → Claude API로 teacher 라벨 32개를 생성해 `train_data.jsonl`에 저장.
   리포 루트에 `ANTHROPIC_API_KEY`를 채운 `.env`가 필요함 (`.env.example` 참고).
   **이미 생성해서 커밋해두면 이후로는 다시 돌릴 필요 없음.**
2. Google Colab에 `genai_course_project/` 전체(특히 `common.py`, `train_data.jsonl`,
   `exchange_rag_local.ipynb`, `requirements-local.txt`)를 업로드.
3. 런타임을 GPU(T4 이상)로 설정 후 `exchange_rag_local.ipynb`를 처음부터 끝까지 실행.
   - 첫 셀에서 `requirements-local.txt`를 설치 (torch/transformers/peft/bitsandbytes 포함)
   - zero-shot → LoRA 파인튜닝 → 파인튜닝 후 평가 → top-k ablation → 시각화 순으로 진행

노트북 코드를 고치고 싶으면 `.ipynb`를 직접 손으로 편집하지 말고 `build_local_notebook.py` /
`build_training_data_notebook.py` / `build_notebook.py`를 고친 뒤 `python build_*.py`로
다시 생성할 것 (diff가 깨끗하게 유지됨).

## 폴더 구성

- `common.py` — 데이터 로드, 임베딩 검색, ground truth, 평가지표, 규칙기반 베이스라인 등
  두 노트북이 공유하는 코드
- `generate_training_data.ipynb` — Claude(teacher)로 학습 데이터(`train_data.jsonl`) 1회 생성
  (제출용 메인 노트북 아님, API 키 필요)
- `exchange_rag_local.ipynb` — **메인 제출 노트북**, API 키 불필요, GPU 필요
- `exchange_rag.ipynb` — 1차 시도(Claude API로 직접 생성, RAG vs 풀컨텍스트 비교). 참고용으로 남겨둠
- `requirements.txt` / `requirements-local.txt` — 후자는 GPU 학습용 추가 패키지 포함
- `figs/` — 노트북 실행 후 생성되는 결과 그래프 (보고서에 삽입)

## 보고서 작성 시 참고

`exchange_rag_local.ipynb` 마지막 셀의 `summary`(rule_based/zero_shot/fine_tuned 3-way
Precision@5·Recall@5·JSON 준수율·hallucination 비율)와 `ablation_rows`를 Experiments and
Results 섹션에 그대로 인용하면 된다. 명시하면 좋은 한계점:

- 전공제한(`전공제한` 필드)은 자유 텍스트로 allow-list/deny-list 표현이 혼재돼 있어
  ground truth 기준에서 제외함
- 학습 데이터(32개)는 Claude로 1회 distillation한 합성 데이터이며, teacher 모델 자체의
  편향/오류가 그대로 학생 모델에 전이될 수 있음
