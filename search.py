"""
하이브리드 검색 엔진
- 벡터 검색 (ChromaDB + sentence-transformers)
- BM25 키워드 검색 (rank-bm25 + 한국어 형태소 분석)
- Reciprocal Rank Fusion으로 결과 통합
"""
import pickle
from dataclasses import dataclass

import numpy as np

from config import (
    CHROMA_DIR, BM25_INDEX_PATH,
    VECTOR_TOP_K, BM25_TOP_K, FINAL_TOP_K, RRF_K
)
from models import get_embed_model, get_kiwi, tokenize_ko


@dataclass
class SearchResult:
    text: str
    filename: str
    page: int
    score: float


def _load_bm25_data() -> dict | None:
    if not BM25_INDEX_PATH.exists():
        return None
    with open(BM25_INDEX_PATH, "rb") as f:
        return pickle.load(f)


def _rrf_fusion(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """Reciprocal Rank Fusion - 여러 순위 목록을 점수로 통합"""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def search(
    query: str,
    top_k: int = FINAL_TOP_K,
    filename_filter: list[str] | None = None,
) -> list[SearchResult]:
    """
    하이브리드 검색 (BM25 + 벡터) with RRF 융합

    Args:
        query: 검색 쿼리
        top_k: 반환할 결과 수
        filename_filter: 특정 파일만 검색할 경우 파일명 목록
    """
    import chromadb

    id_to_content: dict[str, dict] = {}
    vec_ranking: list[str] = []
    bm25_ranking: list[str] = []
    vec_distances: dict[str, float] = {}   # 벡터 거리 (관련도 필터용)
    bm25_scores: dict[str, float] = {}     # BM25 점수 (관련도 필터용)

    # ── 벡터 검색 ──────────────────────────────────────────────────
    try:
        embed_model = get_embed_model()
        q_embed = embed_model.encode([query])[0].tolist()

        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        collection = client.get_or_create_collection("insurance_docs")

        total_count = collection.count()
        if total_count == 0:
            return []

        n_results = min(VECTOR_TOP_K, total_count)
        where_clause = None
        if filename_filter:
            if len(filename_filter) == 1:
                where_clause = {"filename": filename_filter[0]}
            else:
                where_clause = {"filename": {"$in": filename_filter}}

        query_kwargs = dict(
            query_embeddings=[q_embed],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        if where_clause:
            query_kwargs["where"] = where_clause

        vec_res = collection.query(**query_kwargs)

        for doc_id, doc, meta, dist in zip(
            vec_res["ids"][0], vec_res["documents"][0], vec_res["metadatas"][0],
            vec_res["distances"][0],
        ):
            if not meta or not isinstance(meta, dict):
                continue
            id_to_content[doc_id] = {"text": doc, "metadata": meta}
            vec_ranking.append(doc_id)
            vec_distances[doc_id] = dist

    except Exception as e:
        pass  # 벡터 검색 실패 시 BM25만 사용

    # ── BM25 검색 ─────────────────────────────────────────────────
    bm25_data = _load_bm25_data()
    if bm25_data:
        q_tokens = tokenize_ko(query)
        if q_tokens:
            scores = bm25_data["bm25"].get_scores(q_tokens)
            top_indices = np.argsort(scores)[::-1][:BM25_TOP_K]

            # BM25 최소 점수 기준 (평균의 일정 비율 이상만)
            nonzero_scores = scores[scores > 0]
            bm25_min = float(np.mean(nonzero_scores) * 0.5) if len(nonzero_scores) > 0 else 0.0

            for idx in top_indices:
                if scores[idx] < bm25_min:
                    continue  # BM25 점수 미달 = 유의미한 키워드 매칭 없음
                doc_id = bm25_data["ids"][idx]
                meta = bm25_data["metadatas"][idx]

                if not meta or not isinstance(meta, dict):
                    continue

                # 파일 필터 적용
                if filename_filter and meta.get("filename") not in filename_filter:
                    continue

                bm25_ranking.append(doc_id)
                bm25_scores[doc_id] = float(scores[idx])
                if doc_id not in id_to_content:
                    id_to_content[doc_id] = {
                        "text": bm25_data["documents"][idx],
                        "metadata": meta,
                    }

    if not id_to_content:
        return []

    # ── RRF 융합 ──────────────────────────────────────────────────
    fused_scores = _rrf_fusion([vec_ranking, bm25_ranking])
    top_ids = sorted(fused_scores, key=lambda x: fused_scores[x], reverse=True)[:top_k]

    # ── 관련도 필터링 ─────────────────────────────────────────────
    MAX_VEC_DISTANCE = 0.3  # 코사인 거리 기준 (0=동일, 2=정반대)

    # 검색어에서 명사만 추출 (의미 있는 키워드)
    kiwi = get_kiwi()
    q_morphs = kiwi.tokenize(query)
    meaningful_tags = {"NNG", "NNP", "SL", "SH"}  # 일반명사, 고유명사, 외래어
    query_nouns = [t.form for t in q_morphs if t.tag in meaningful_tags
                   and (len(t.form) >= 2 or t.tag in meaningful_tags)]

    results = []
    for doc_id in top_ids:
        if doc_id not in id_to_content:
            continue

        content = id_to_content[doc_id]
        meta = content.get("metadata")
        text = content.get("text")
        if not meta or not isinstance(meta, dict) or not text:
            continue

        # 벡터 거리 체크
        dist = vec_distances.get(doc_id, 2.0)
        has_strong_vec = dist <= MAX_VEC_DISTANCE

        # 명사 매칭 체크: 검색어의 명사 중 하나라도 결과 텍스트에 포함되는지
        has_noun_match = any(noun in text for noun in query_nouns) if query_nouns else False

        # 벡터 유사도 높거나, 명사가 실제로 포함된 경우만 통과
        if not has_strong_vec and not has_noun_match:
            continue

        results.append(
            SearchResult(
                text=text,
                filename=meta.get("filename", ""),
                page=meta.get("page", 0),
                score=fused_scores[doc_id],
            )
        )

    return results
