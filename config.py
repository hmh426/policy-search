import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = BASE_DIR / "보험상품_PDF"
CHROMA_DIR = DATA_DIR / "chroma_db"
BM25_INDEX_PATH = DATA_DIR / "bm25_index.pkl"
PROCESSED_HASHES_PATH = DATA_DIR / "processed_hashes.json"

for d in [PDF_DIR, CHROMA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# 한국어 특화 SBERT 모델 (KorNLI/KorSTS fine-tuned)
EMBED_MODEL = "snunlp/KR-SBERT-V40K-klueNLI-augSTS"
LLM_MODEL = "claude-sonnet-4-6"

CHUNK_SIZE = 600       # characters
CHUNK_OVERLAP = 100    # characters
VECTOR_TOP_K = 20      # 벡터 검색 후보 수
BM25_TOP_K = 20        # BM25 검색 후보 수
FINAL_TOP_K = 5        # 최종 반환 결과 수
RRF_K = 60             # Reciprocal Rank Fusion 상수
