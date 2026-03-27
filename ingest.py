"""
PDF 수집 파이프라인
- PDF 파싱 (pymupdf)
- 보험 약관 특화 청킹 (조항 단위 우선, 슬라이딩 윈도우 폴백)
- 임베딩 생성 및 ChromaDB 저장
- BM25 인덱스 구축
- 처리된 파일 해시로 중복 인덱싱 방지
- 대용량 PDF 지원 (2,000+ 페이지, 배치 임베딩, 진행률 표시)
"""
import re
import json
import pickle
import hashlib
from pathlib import Path
from typing import Callable

import fitz  # pymupdf
import numpy as np
from rank_bm25 import BM25Okapi

from config import (
    PDF_DIR, CHROMA_DIR, BM25_INDEX_PATH, PROCESSED_HASHES_PATH,
    CHUNK_SIZE, CHUNK_OVERLAP
)
from models import get_embed_model, tokenize_ko

# 보험 약관 조항 패턴 (제1조, 제1항, 제1관, [별표1] 등)
ARTICLE_PATTERN = re.compile(
    r'(?:^|\n)\s*(?:제\s*\d+\s*(?:조|항|관)|【.+?】|\[별표\s*\d+\]|\d+\.\s)',
    re.MULTILINE
)

# 의미 없는 페이지 필터 (목차, 빈 페이지 등)
MIN_PAGE_CHARS = 30
# 너무 짧은 청크 필터
MIN_CHUNK_CHARS = 40


def _file_hash(path: Path) -> str:
    """파일 해시 (대용량은 앞뒤 + 크기로 빠르게 계산)"""
    size = path.stat().st_size
    h = hashlib.md5()
    h.update(str(size).encode())
    data = path.read_bytes()
    h.update(data[:8192])
    if size > 16384:
        h.update(data[-8192:])
    return h.hexdigest()


def _load_processed_hashes() -> dict:
    if PROCESSED_HASHES_PATH.exists():
        return json.loads(PROCESSED_HASHES_PATH.read_text(encoding="utf-8"))
    return {}


def _save_processed_hashes(hashes: dict):
    PROCESSED_HASHES_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_HASHES_PATH.write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _clean_text(text: str) -> str:
    """텍스트 정리 - PDF 추출 시 깨지는 레이아웃 복원"""
    # 1) "\n \n" 패턴 → 공백 (PDF 표/세로 레이아웃에서 단어가 끊기는 패턴)
    text = re.sub(r'\n \n', ' ', text)
    # 2) 짧은 줄(10자 이하)이 연속되면 한 줄로 병합
    lines = text.split('\n')
    merged = []
    buf = ""
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buf:
                merged.append(buf)
                buf = ""
            merged.append("")
            continue
        # 짧은 줄은 이전 줄에 이어붙이기
        if len(stripped) <= 10 and buf and not re.match(r'^(?:제\s*\d|【|\[|□|■|○|●|\d+\.)', stripped):
            buf += " " + stripped
        else:
            if buf:
                merged.append(buf)
            buf = stripped
    if buf:
        merged.append(buf)
    text = '\n'.join(merged)
    # 3) 연속 공백 정리
    text = re.sub(r'[ \t]+', ' ', text)
    # 4) 연속 빈 줄 정리 (3줄 이상 → 1줄)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def chunk_by_article(text: str) -> list[str] | None:
    """보험 약관 조항 번호 기준으로 분할"""
    splits = list(ARTICLE_PATTERN.finditer(text))
    if len(splits) < 2:
        return None

    chunks = []
    for i, match in enumerate(splits):
        start = match.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        chunk = text[start:end].strip()

        # 너무 긴 조항은 슬라이딩 윈도우로 재분할
        if len(chunk) > CHUNK_SIZE * 2:
            sub_chunks = sliding_window_chunks(chunk)
            chunks.extend(sub_chunks)
        elif len(chunk) >= MIN_CHUNK_CHARS:
            chunks.append(chunk)

    return chunks if chunks else None


def sliding_window_chunks(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP) -> list[str]:
    """슬라이딩 윈도우 청킹 (폴백)"""
    chunks = []
    start = 0
    while start < len(text):
        chunk = text[start:start + size].strip()
        if len(chunk) >= MIN_CHUNK_CHARS:
            chunks.append(chunk)
        start += size - overlap
    return chunks


def extract_chunks_from_pdf(pdf_path: Path, log: Callable = print) -> list[dict]:
    """PDF에서 청크 추출 (대용량 지원)"""
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    all_chunks = []

    log_interval = max(total_pages // 10, 1)  # 10% 단위로 진행률

    for page_num in range(total_pages):
        if page_num % log_interval == 0 and total_pages > 100:
            pct = page_num * 100 // total_pages
            log(f"    페이지 처리 중: {page_num}/{total_pages} ({pct}%)")

        page = doc[page_num]
        text = _clean_text(page.get_text())

        if len(text) < MIN_PAGE_CHARS:
            continue

        # 조항 기반 청킹 시도, 실패 시 슬라이딩 윈도우
        chunks = chunk_by_article(text) or sliding_window_chunks(text)

        for i, chunk in enumerate(chunks):
            chunk_id = hashlib.md5(
                f"{pdf_path.name}_{page_num}_{i}".encode()
            ).hexdigest()
            all_chunks.append({
                "id": chunk_id,
                "text": chunk,
                "filename": pdf_path.name,
                "page": page_num + 1,
                "chunk_idx": i,
            })

    doc.close()
    return all_chunks


def _rebuild_bm25(collection, log: Callable = print):
    """ChromaDB 전체 문서로 BM25 인덱스 재구축"""
    log("BM25 인덱스 재구축 중...")
    all_docs = collection.get(include=["documents", "metadatas"])
    if not all_docs["ids"]:
        return

    total = len(all_docs["documents"])
    log(f"  형태소 분석 중: {total:,}개 청크")

    tokenized = []
    for i, doc in enumerate(all_docs["documents"]):
        tokenized.append(tokenize_ko(doc))
        if (i + 1) % 2000 == 0:
            log(f"  형태소 분석: {i + 1:,}/{total:,}")

    bm25 = BM25Okapi(tokenized)

    bm25_data = {
        "bm25": bm25,
        "ids": all_docs["ids"],
        "documents": all_docs["documents"],
        "metadatas": all_docs["metadatas"],
    }
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(bm25_data, f)
    log(f"BM25 인덱스 완료: {total:,}개 청크")


def ingest_pdfs(
    pdf_paths: list[Path] = None,
    force: bool = False,
    log: Callable = print,
) -> dict:
    """
    메인 수집 파이프라인.

    Args:
        pdf_paths: 처리할 PDF 경로 목록. None이면 PDF 폴더 전체 스캔.
        force: True이면 이미 처리된 파일도 재인덱싱.
        log: 진행 상황 콜백 (print 또는 Streamlit용 함수).

    Returns:
        {"status": "ok"|"no_pdfs"|"no_text", "added": int, "skipped": int}
    """
    import chromadb

    if pdf_paths is None:
        pdf_paths = sorted(PDF_DIR.glob("*.pdf"))

    if not pdf_paths:
        return {"status": "no_pdfs", "added": 0, "skipped": 0}

    processed_hashes = _load_processed_hashes()
    embed_model = get_embed_model()

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection("insurance_docs")

    added_total = 0
    skipped_total = 0

    for pdf_path in pdf_paths:
        fhash = _file_hash(pdf_path)

        if not force and processed_hashes.get(pdf_path.name) == fhash:
            log(f"  건너뜀 (이미 처리됨): {pdf_path.name}")
            skipped_total += 1
            continue

        log(f"  파싱 중: {pdf_path.name}")
        chunks = extract_chunks_from_pdf(pdf_path, log=log)

        if not chunks:
            log(f"  텍스트 없음 (스캔 PDF?): {pdf_path.name}")
            skipped_total += 1
            continue

        log(f"  청크 수: {len(chunks):,}개")

        # 기존 데이터 삭제 후 재삽입
        existing = collection.get(where={"filename": pdf_path.name})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])

        # 배치 임베딩 (대용량 대응: 1000개씩 분할)
        embed_batch = 256
        all_embeddings = []
        texts = [c["text"] for c in chunks]

        for i in range(0, len(texts), embed_batch):
            batch_texts = texts[i:i + embed_batch]
            pct = min(100, (i + embed_batch) * 100 // len(texts))
            log(f"  임베딩 생성 중: {pct}%")
            emb = embed_model.encode(batch_texts, batch_size=64, show_progress_bar=False)
            all_embeddings.append(emb)

        embeddings = np.vstack(all_embeddings).tolist()

        # ChromaDB 저장 (배치)
        db_batch = 500
        for i in range(0, len(chunks), db_batch):
            batch = chunks[i:i + db_batch]
            collection.upsert(
                ids=[c["id"] for c in batch],
                embeddings=embeddings[i:i + db_batch],
                documents=[c["text"] for c in batch],
                metadatas=[
                    {
                        "filename": c["filename"],
                        "page": c["page"],
                        "chunk_idx": c["chunk_idx"],
                    }
                    for c in batch
                ],
            )

        processed_hashes[pdf_path.name] = fhash
        added_total += len(chunks)
        log(f"  완료: {pdf_path.name} ({len(chunks):,}개 청크)")

    _save_processed_hashes(processed_hashes)

    if added_total > 0:
        _rebuild_bm25(collection, log=log)

    return {"status": "ok", "added": added_total, "skipped": skipped_total}


def delete_pdf_index(filename: str) -> bool:
    """특정 파일 인덱스 삭제"""
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection("insurance_docs")

    existing = collection.get(where={"filename": filename})
    if not existing["ids"]:
        return False

    collection.delete(ids=existing["ids"])

    # 해시 목록에서도 제거
    hashes = _load_processed_hashes()
    hashes.pop(filename, None)
    _save_processed_hashes(hashes)

    # BM25 재구축
    _rebuild_bm25(collection)
    return True


def get_indexed_files() -> list[dict]:
    """인덱싱된 파일 목록 반환"""
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        collection = client.get_or_create_collection("insurance_docs")
        all_metas = collection.get(include=["metadatas"])["metadatas"]
    except Exception:
        return []

    file_counts: dict[str, int] = {}
    for meta in all_metas:
        fname = meta.get("filename", "unknown")
        file_counts[fname] = file_counts.get(fname, 0) + 1

    return [{"filename": k, "chunks": v} for k, v in sorted(file_counts.items())]
