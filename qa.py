"""
RAG 기반 보험 약관 Q&A
- 하이브리드 검색으로 관련 약관 청크 검색
- Claude API로 약관 해석 및 답변 생성
- 스트리밍 응답 지원
- 대화 이력 유지
"""
from typing import Generator

import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL, FINAL_TOP_K
from search import search, SearchResult

SYSTEM_PROMPT = """당신은 보험 약관 전문 해설사입니다. 제공된 약관 문서를 바탕으로 정확하고 이해하기 쉽게 질문에 답변합니다.

답변 원칙:
1. 반드시 제공된 약관 내용에 근거하여 답변하세요.
2. 관련 내용을 찾을 수 없으면 솔직하게 "해당 내용을 제공된 약관에서 찾을 수 없습니다"라고 말하세요.
3. 어려운 보험 용어는 괄호 안에 쉬운 말로 풀어 설명하세요. 예: "피보험자(보험에 가입된 사람)"
4. 답변 마지막에 참고한 출처(파일명, 페이지)를 반드시 명시하세요.
5. 여러 약관을 비교하는 질문은 표 형식으로 정리해서 답변하세요.
6. 답변은 친절하고 명확하게, 한국어로 작성하세요."""


def _build_context(results: list[SearchResult]) -> str:
    parts = []
    for r in results:
        parts.append(f"[출처: {r.filename} {r.page}페이지]\n{r.text}")
    return "\n\n" + ("─" * 40) + "\n\n".join(parts)


def answer_stream(
    query: str,
    chat_history: list[dict] | None = None,
    filename_filter: list[str] | None = None,
    top_k: int = FINAL_TOP_K,
) -> Generator[str, None, None]:
    """
    스트리밍 Q&A. 토큰 단위로 yield.

    Args:
        query: 사용자 질문
        chat_history: [{"role": "user"|"assistant", "content": "..."}]
        filename_filter: 특정 파일만 검색
        top_k: 참조할 청크 수

    Yields:
        텍스트 토큰 (마지막에 sources 딕셔너리 yield)
    """
    if not ANTHROPIC_API_KEY:
        yield "⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요."
        return

    # 관련 약관 검색
    results = search(query, top_k=top_k, filename_filter=filename_filter)

    if not results:
        yield "인덱싱된 문서에서 관련 내용을 찾을 수 없습니다. PDF를 먼저 인덱싱해주세요."
        return

    context = _build_context(results)

    # 메시지 구성
    messages = []
    if chat_history:
        for h in chat_history[-6:]:  # 최근 3턴
            messages.append({"role": h["role"], "content": h["content"]})

    messages.append({
        "role": "user",
        "content": f"다음 보험 약관 내용을 참고하여 질문에 답변해주세요.\n\n[참고 약관]\n{context}\n\n[질문]\n{query}",
    })

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    with client.messages.stream(
        model=LLM_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


def answer(
    query: str,
    chat_history: list[dict] | None = None,
    filename_filter: list[str] | None = None,
    top_k: int = FINAL_TOP_K,
) -> dict:
    """
    동기 Q&A (전체 응답을 한 번에 반환).

    Returns:
        {"answer": str, "sources": [{"filename": str, "page": int}]}
    """
    if not ANTHROPIC_API_KEY:
        return {"answer": "⚠️ ANTHROPIC_API_KEY가 설정되지 않았습니다.", "sources": []}

    results = search(query, top_k=top_k, filename_filter=filename_filter)

    if not results:
        return {
            "answer": "인덱싱된 문서에서 관련 내용을 찾을 수 없습니다.",
            "sources": [],
        }

    context = _build_context(results)
    messages = []
    if chat_history:
        for h in chat_history[-6:]:
            messages.append({"role": h["role"], "content": h["content"]})

    messages.append({
        "role": "user",
        "content": f"다음 보험 약관 내용을 참고하여 질문에 답변해주세요.\n\n[참고 약관]\n{context}\n\n[질문]\n{query}",
    })

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    # 중복 제거된 출처 목록
    sources = []
    seen = set()
    for r in results:
        key = (r.filename, r.page)
        if key not in seen:
            seen.add(key)
            sources.append({"filename": r.filename, "page": r.page})

    return {
        "answer": response.content[0].text,
        "sources": sources,
    }
