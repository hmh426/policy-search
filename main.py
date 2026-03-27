"""
보험 약관 검색 & Q&A - Streamlit 웹 앱
실행: streamlit run main.py
"""
import json
import re
import time
from pathlib import Path

import streamlit as st

from config import PDF_DIR, DATA_DIR, ANTHROPIC_API_KEY

# ── 페이지 설정 ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="보험 약관 검색 & Q&A",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* 다크모드 - 약간 밝게 조정 */
.stApp {
    background-color: #3C3C3C !important;
    color: #c0c0c0 !important;
}
/* 메인 콘텐츠 좌우 여백 축소 */
.stMainBlockContainer {
    max-width: 100% !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
/* 사이드바 배경색 */
section[data-testid="stSidebar"] {
    background-color: #2B2B2B !important;  
}
/* 사이드바 글자 크기 */
section[data-testid="stSidebar"] {
    font-size: 0.92em !important;
}
/* 전체 텍스트 명도 낮춤 (버튼 제외) */
.stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp label {
    color: #c0c0c0 !important;
}
/* caption 글자 밝기 */
.stApp [data-testid="stCaptionContainer"] {
    color: #aaaaaa !important;
}
.stApp [data-testid="stCaptionContainer"] * {
    color: #aaaaaa !important;
}
.result-card {
    background: #ffffff;
    border-left: 4px solid #1f77b4;
    padding: 12px 16px;
    margin: 8px 0;
    border-radius: 4px;
}
.source-badge {
    background: #AAAAAA;           /* 출처 배지 배경색 */
    color: #252525;                /* 출처 배지 글자색 */
    padding: 3px 7px;
    border-radius: 4px;
    font-size: 0.85em;
    font-weight: 600;
}
.score-badge {
    background: #e8f5e9;
    color: #2e7d32;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: 700;
}
/* 사이드바 요소 간격 축소 */
section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
    margin-bottom: -1rem !important;
}
/* 파일 업로더 - 기본 텍스트/버튼 모두 숨김 */
[data-testid="stFileUploaderDropzone"] span,
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] button {
    display: none !important;
}
/* 드롭존 스타일 */
[data-testid="stFileUploaderDropzone"] {
    border: 1px dashed #666 !important;
    border-radius: 8px !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    height: 42px !important;
    min-height: 42px !important;
    cursor: pointer !important;
    background-color: #2f2f2f !important;  /* 드롭존 배경색 */
}
/* 멀티셀렉트 배경색 */
[data-testid="stMultiSelect"] > div > div {
    background-color: #2f2f2f !important;  /* 셀렉트 배경색 */
}
/* 멀티셀렉트 선택된 태그 색상 */
[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    background-color: #4c6a7c !important;  /* 태그 배경색 */
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span {
    color: #e0e0e0 !important;             /* 태그 글자색 */
}
[data-testid="stFileUploaderDropzone"]::before {
    content: "📂 업로드" !important;
    font-size: 0.9rem !important;
    color: #c0c0c0 !important;
    padding-top: 8px !important;
    text-align: center !important;
    display: block !important;
}
/* Choose options 한글화 */
[data-testid="stMultiSelect"] [data-testid="stMarkdownContainer"] {
    font-size: 0;
}
/* Deploy 버튼만 숨김 */
[data-testid="stToolbar"] [data-testid="stToolbarActions"] button:last-child {
    display: none !important;
}
/* 파일 업로더 글자색 */
[data-testid="stFileUploader"] label,
[data-testid="stFileUploader"] span,
[data-testid="stFileUploader"] p,
[data-testid="stFileUploader"] small {
    color: #a0a0a0 !important;            /* 업로더 글자색 */
}
/* 드롭다운(select) 화살표 색상 */
[data-testid="stMultiSelect"] svg,
[data-testid="stSelectbox"] svg {
    fill: #888888 !important;              /* 화살표 색상 */
}
/* expander 화살표/글자 색상 */
[data-testid="stExpander"] summary * {
    color: #c0c0c0 !important;             /* 접힘 화살표+헤더 색상 */
    fill: #c0c0c0 !important;
}
/* expander 전체 글자색 + 크기 */
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] span,
[data-testid="stExpander"] [data-testid="stMarkdownContainer"] li {
    color: #cccccc !important;             /* expander 글자색 */
    font-size: 1.1rem !important;
}
/* 키워드 탭 줄바꿈 (가로 스크롤 방지) */
[data-testid="stTabs"] > div:first-child,
[data-testid="stTabs"] > div:first-child > div,
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    flex-wrap: wrap !important;
    overflow: hidden !important;
    gap: 0 !important;
}
[data-testid="stTabs"] [data-baseweb="tab-list"] button {
    flex-shrink: 0 !important;
    margin-right: 8px !important;
    color: #d0d0d0 !important;
}
/* 탭 오른쪽 그라데이션 제거 */
[data-testid="stTabs"] [data-baseweb="tab-list"]::after {
    display: none !important;
}
/* 탭 메뉴 글자색 */
[data-testid="stTabs"] [data-baseweb="tab-list"] button p {
    color: #d0d0d0 !important;
}
/* 좁은 화면에서 컬럼 세로 쌓임 방지 */
[data-testid="stColumns"] {
    flex-wrap: nowrap !important;
}
[data-testid="stColumn"] {
    min-width: 0 !important;
}
/* 검색바: 결과 수/검색 버튼은 고정폭, 검색창만 유동 */
[data-testid="stColumns"]:first-of-type [data-testid="stColumn"]:nth-child(2) {
    flex: 0 0 80px !important;
    min-width: 80px !important;
}
[data-testid="stColumns"]:first-of-type [data-testid="stColumn"]:nth-child(3) {
    flex: 0 0 90px !important;
    min-width: 90px !important;
}
/* 탭 높이 제한 스크롤 제거 */
[data-testid="stTabs"] > div:first-child {
    max-height: none !important;
}
/* primary 버튼 (검색, 인덱싱 시작 등) */
.stButton button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background-color: #4c6a7c !important;  /* 버튼 배경색 */
    border-color: #4c6a7c !important;      /* 버튼 테두리색 */
}
/* 버튼 글자색 - Streamlit이 <p>로 감싸므로 여기서 지정 */
.stButton button[kind="primary"] p,
button[data-testid="stBaseButton-primary"] p {
    color: #EEEEEE !important;             /* 버튼 글자색 */
}
/* 버튼 마우스 올렸을 때 */
.stButton button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
    background-color: #5c7e90 !important;  /* hover 배경색 */
    border-color: #5c7e90 !important;
}
</style>
""", unsafe_allow_html=True)


# ── 리소스 캐시 (앱 재실행 간 모델 유지) ────────────────────────────
@st.cache_resource(show_spinner="임베딩 모델 로딩 중... (최초 1회)")
def _load_models():
    from models import get_embed_model, get_kiwi
    get_embed_model()
    get_kiwi()
    return True


def _models_ready() -> bool:
    try:
        _load_models()
        return True
    except Exception as e:
        st.error(f"모델 로딩 실패: {e}")
        return False


# ── 세션 상태 초기화 ─────────────────────────────────────────────────
def _init_state():
    defaults = {
        "chat_history": [],
        "search_results": [],
        "search_query": "",
        "selected_files": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── 사이드바 ─────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown('<p style="font-size:1.2rem; color:#c8c8c8; margin:0 0 4px 0;">📋 보험 약관 검색</p><hr style="margin:4px 0 8px 0; border-color:#444;">', unsafe_allow_html=True)

        # 인덱싱된 문서 목록 (상품별 그룹)
        indexed = _get_indexed_files()
        if indexed:
            file_names = [f["filename"] for f in indexed]

            # 파일명에서 상품명 추출 ('_' 앞부분)
            products = {}
            for fname in file_names:
                product = fname.rsplit("_", 1)[0] if "_" in fname else fname
                products.setdefault(product, []).append(fname)

            if len(products) > 1:
                # 상품이 여러 개면 상품 단위 선택
                product_names = ["전체"] + list(products.keys())
                selected_product = st.selectbox(
                    f"보험 상품 ({len(products)}개)",
                    options=product_names,
                )
                if selected_product == "전체":
                    st.session_state.selected_files = []
                else:
                    st.session_state.selected_files = products[selected_product]
                    st.caption(f"  {len(products[selected_product])}개 문서 선택됨")
            else:
                # 상품 1개면 개별 파일 선택
                selected = st.multiselect(
                    f"검색 범위 ({len(indexed)}개 문서)",
                    options=file_names,
                    default=st.session_state.selected_files,
                )
                st.session_state.selected_files = selected

        # API 키 상태
        if ANTHROPIC_API_KEY:
            st.caption("Claude API 연결됨")
        else:
            st.caption("⚠ API 키 없음 (.env 설정)")


@st.cache_data(ttl=10)
def _get_indexed_files():
    from ingest import get_indexed_files
    return get_indexed_files()


def _run_ingest(force: bool = False):
    from ingest import ingest_pdfs

    log_container = st.empty()
    logs = []

    def log(msg: str):
        logs.append(msg)
        log_container.markdown("\n\n".join(f"- {m}" for m in logs[-10:]))

    with st.spinner("인덱싱 중..."):
        result = ingest_pdfs(force=force, log=log)

    log_container.empty()

    if result["status"] == "no_pdfs":
        st.warning("PDF 파일이 없습니다. 사이드바에서 파일을 업로드하세요.")
    elif result["added"] > 0:
        st.success(f"완료! {result['added']}개 청크 추가, {result['skipped']}개 파일 건너뜀")
        st.cache_data.clear()
    else:
        st.info(f"모든 파일이 이미 인덱싱되어 있습니다. ({result['skipped']}개 건너뜀)")


def _delete_file(filename: str):
    from ingest import delete_pdf_index
    if delete_pdf_index(filename):
        st.success(f"삭제 완료: {filename}")
        st.cache_data.clear()


# ── 자주 검색하는 키워드 (카테고리별) ─────────────────────────────────
KEYWORD_CATEGORIES = {
    "💰 보험금": [
        "보험금 청구", "보험금 지급", "보험금 부지급", "청구 서류",
        "보험금 청구 기한", "보험금 산정", "보험금 감액", "지연이자",
    ],
    "🏥 진단·수술·입원": [
        "암 진단금", "수술비", "입원비", "통원비", "입원일당",
        "진단비", "항암치료비", "요양병원", "재해입원", "질병입원",
    ],
    "⚠️ 면책·감액": [
        "면책사유", "면책기간", "감액기간", "고지의무",
        "계약 전 알릴 의무", "통지의무", "기왕증", "음주운전 면책",
    ],
    "🔄 갱신·보험료": [
        "갱신", "갱신형 보험료", "보험료 납입면제", "보장개시일",
        "보험료 인상", "납입기간", "납입최고", "보험료 자동대출납입",
    ],
    "📋 해지·환급": [
        "해지환급금", "계약해지", "청약철회", "만기환급금",
        "품질보증해지", "무사고 환급", "실효", "부활",
    ],
    "🏦 실손·자기부담": [
        "실손보험", "자기부담금", "중복보험", "비례보상",
        "실손 보장범위", "비급여", "도수치료", "MRI 보장",
    ],
    "📑 특약·보장": [
        "특약", "보장범위", "3대 기본계약", "사망보험금",
        "후유장해", "질병코드", "재해분류표", "질병 분류표",
    ],
    "⚙️ 계약 관리": [
        "보험계약대출", "수익자 변경", "피보험자", "보험나이",
        "약관교부의무", "설명의무", "배서", "계약변경",
    ],
    "⚖️ 민원·분쟁": [
        "손해사정", "분쟁조정", "약관 해석", "보험사기",
        "민원 제기", "금감원 분쟁", "소송",
    ],
    "🚗 자동차보험": [
        "과실비율", "대물배상", "대인배상", "자기차량손해",
        "무보험차상해", "렌트비", "교통사고 합의금",
    ],
}

# 사용자 키워드 저장 경로
USER_KEYWORDS_PATH = DATA_DIR / "user_keywords.json"


def _load_user_keywords() -> list[str]:
    if USER_KEYWORDS_PATH.exists():
        return json.loads(USER_KEYWORDS_PATH.read_text(encoding="utf-8"))
    return []


def _save_user_keywords(keywords: list[str]):
    USER_KEYWORDS_PATH.write_text(
        json.dumps(keywords, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _highlight_text(text: str, query: str) -> str:
    """검색어를 노란 배경으로 하이라이트"""
    import html
    text = html.escape(text)
    # 검색어를 형태소 단위로 분리하여 각각 하이라이트
    from models import get_kiwi
    kiwi = get_kiwi()
    morphs = kiwi.tokenize(query)
    noun_tags = {"NNG", "NNP", "SL", "SH"}
    keywords = [t.form for t in morphs if t.tag in noun_tags and len(t.form) >= 2]
    # 원본 검색어에서 공백으로 분리한 2글자 이상 단어도 추가
    for word in query.split():
        if len(word) >= 2 and word not in keywords:
            keywords.append(word)
    # 긴 키워드부터 매칭 (부분 겹침 방지)
    keywords.sort(key=len, reverse=True)
    for kw in keywords:
        escaped_kw = html.escape(kw)
        pattern = re.compile(re.escape(escaped_kw), re.IGNORECASE)
        text = pattern.sub(
            f'<mark style="background:rgba(255,215,0,0.10);color:inherit;padding:1px 2px;border-radius:2px">{escaped_kw}</mark>',
            text,
        )
    return text


# ── 검색 탭 ─────────────────────────────────────────────────────────
def render_search_tab():
    st.subheader("문서 검색")

    # ── 검색 입력 ────────────────────────────────────────────────
    col1, col2, col3 = st.columns([6, 1, 1])
    query = col1.text_input(
        "검색어",
        placeholder="예: 암 진단금 지급 조건, 면책 기간, 보험료 납입 면제...",
        label_visibility="collapsed",
    )
    top_k = col2.selectbox("결과 수", [3, 5, 10, 20], index=1, label_visibility="collapsed")
    search_btn = col3.button("검색", type="primary", use_container_width=True)

    # ── 자주 찾는 키워드 (카테고리 탭) ────────────────────────────
    cat_names = list(KEYWORD_CATEGORIES.keys())
    user_kws = _load_user_keywords()
    tab_labels = cat_names + ["⭐ 내 키워드"]
    kw_tabs = st.tabs(tab_labels)

    def _pill_changed(key):
        """키워드 클릭 시 콜백 - 선택값을 검색 대기열에 저장"""
        val = st.session_state.get(key)
        if val:
            st.session_state["_do_search"] = val
            # 다른 탭의 pills 선택 해제
            all_keys = [f"pills_{c}" for c in cat_names] + ["pills_user"]
            for k in all_keys:
                if k != key and k in st.session_state:
                    st.session_state[k] = None

    # 카테고리별 키워드 (pills로 컴팩트하게)
    for idx, cat_name in enumerate(cat_names):
        with kw_tabs[idx]:
            st.pills("kw", KEYWORD_CATEGORIES[cat_name],
                     selection_mode="single", label_visibility="collapsed",
                     key=f"pills_{cat_name}",
                     on_change=_pill_changed, args=(f"pills_{cat_name}",))

    # 내 키워드 탭 (추가/검색/삭제 통합)
    with kw_tabs[-1]:
        edit_mode = st.session_state.get("_kw_edit", False)

        if edit_mode:
            # 편집 모드: 추가 + X 삭제
            ac1, ac2, ac3 = st.columns([3, 1, 1])
            new_kw = ac1.text_input("새 키워드", placeholder="키워드 입력", label_visibility="collapsed")
            if ac2.button("➕ 추가", use_container_width=True):
                if new_kw.strip() and new_kw.strip() not in user_kws:
                    user_kws.append(new_kw.strip())
                    _save_user_keywords(user_kws)
                    st.rerun()
            if ac3.button("✅ 완료", use_container_width=True):
                st.session_state["_kw_edit"] = False
                st.rerun()
            if user_kws:
                kept = st.multiselect(
                    "키워드 관리",
                    options=user_kws,
                    default=user_kws,
                    label_visibility="collapsed",
                    key="user_kw_manage",
                )
                if set(kept) != set(user_kws):
                    _save_user_keywords(kept)
                    st.rerun()
        else:
            # 일반 모드: pills + 편집 버튼 한 줄
            if user_kws:
                kw_col1, kw_col2 = st.columns([6, 1])
                kw_col1.pills("ukw", user_kws,
                              selection_mode="single", label_visibility="collapsed",
                              key="pills_user",
                              on_change=_pill_changed, args=("pills_user",))
                if kw_col2.button("✏️", use_container_width=True, help="키워드 추가/삭제"):
                    st.session_state["_kw_edit"] = True
                    st.rerun()
            else:
                if st.button("➕ 키워드 추가"):
                    st.session_state["_kw_edit"] = True
                    st.rerun()

    # ── 검색 실행 (버튼 또는 키워드 클릭) ────────────────────────
    pill_query = st.session_state.pop("_do_search", None)
    final_query = pill_query or query
    should_search = pill_query or (search_btn and query.strip())

    if should_search and final_query.strip():
        if not _models_ready():
            return

        from search import search as do_search

        with st.spinner("검색 중..."):
            results = do_search(
                final_query.strip(),
                top_k=int(top_k),
                filename_filter=st.session_state.selected_files or None,
            )

        st.session_state.search_results = results
        st.session_state.search_query = final_query

    # ── 결과 표시 ────────────────────────────────────────────────
    results = st.session_state.search_results
    if not results:
        if st.session_state.search_query:
            st.info("검색 결과가 없습니다.")
        return

    res_col1, res_col2 = st.columns([3, 2])
    res_col1.markdown(f"**{len(results)}개 결과** — '{st.session_state.search_query}'")
    tog1, tog2 = res_col2.columns(2)
    highlight_on = tog1.toggle("강조", value=True)
    expand_all = tog2.toggle("펼치기", value=True)

    # 1등 점수 기준 백분율로 변환 (1등 = 100%)
    max_score = results[0].score if results else 1.0

    for i, r in enumerate(results, 1):
        with st.container():
            pct = r.score / max_score * 100
            st.markdown(
                f'<span class="source-badge">📄 {r.filename}</span> '
                f'<span style="color:#666"> {r.page}페이지</span> '
                f'<span class="score-badge" style="float:right">{pct:.0f}%</span>',
                unsafe_allow_html=True,
            )
            text = r.text or "(텍스트 없음)"
            with st.expander(f"#{i} {text[:60]}...", expanded=expand_all):
                if highlight_on and st.session_state.search_query:
                    display_text = _highlight_text(text, st.session_state.search_query)
                    st.markdown(display_text, unsafe_allow_html=True)
                else:
                    st.markdown(text)


# ── Q&A 탭 ──────────────────────────────────────────────────────────
def render_qa_tab():
    st.subheader("약관 Q&A")

    if not ANTHROPIC_API_KEY:
        st.warning("Claude API 키가 없어 Q&A를 사용할 수 없습니다.\n\n`.env` 파일에 `ANTHROPIC_API_KEY=sk-ant-...`를 추가하세요.")
        return

    # 대화 이력 표시
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("📌 참고 출처"):
                    for s in msg["sources"]:
                        st.caption(f"• {s['filename']} {s['page']}페이지")

    # 입력
    if prompt := st.chat_input("약관에 대해 질문해보세요... (예: 이 보험에서 자살은 보험금이 나오나요?)"):
        if not _models_ready():
            return

        from qa import answer_stream, search as do_search
        from search import search as do_search_plain

        # 사용자 메시지 추가
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 스트리밍 응답
        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""

            for token in answer_stream(
                prompt,
                chat_history=st.session_state.chat_history[:-1],
                filename_filter=st.session_state.selected_files or None,
            ):
                full_response += token
                placeholder.markdown(full_response + "▌")

            placeholder.markdown(full_response)

        # 출처 검색 (별도로 표시용)
        sources = []
        try:
            from search import search as _s
            res = _s(
                prompt,
                top_k=5,
                filename_filter=st.session_state.selected_files or None,
            )
            seen = set()
            for r in res:
                key = (r.filename, r.page)
                if key not in seen:
                    seen.add(key)
                    sources.append({"filename": r.filename, "page": r.page})
        except Exception:
            pass

        if sources:
            with st.expander("📌 참고 출처"):
                for s in sources:
                    st.caption(f"• {s['filename']} {s['page']}페이지")

        st.session_state.chat_history.append({
            "role": "assistant",
            "content": full_response,
            "sources": sources,
        })

    # 대화 초기화
    if st.session_state.chat_history:
        if st.button("대화 초기화", use_container_width=False):
            st.session_state.chat_history = []
            st.rerun()


# ── 문서 관리 탭 ─────────────────────────────────────────────────────
def render_manage_tab():
    st.subheader("문서 관리")

    # 인덱싱 컨트롤
    col_idx1, col_idx2, col_idx3 = st.columns(3)
    if col_idx1.button("인덱싱 시작", type="primary", use_container_width=True):
        _run_ingest(force=False)
    if col_idx2.button("강제 재인덱싱", use_container_width=True):
        _run_ingest(force=True)
    with col_idx3:
        uploaded = st.file_uploader(
            "PDF 업로드",
            type="pdf",
            accept_multiple_files=True,
            label_visibility="collapsed",
        )
        if uploaded:
            saved = []
            for f in uploaded:
                dest = PDF_DIR / f.name
                dest.write_bytes(f.read())
                saved.append(f.name)
            if saved:
                st.success(f"{len(saved)}개 저장됨")
                st.cache_data.clear()

    st.divider()

    # 파일 목록
    pdf_files = sorted(PDF_DIR.glob("*.pdf"))
    indexed = {f["filename"]: f["chunks"] for f in _get_indexed_files()}

    if not pdf_files:
        st.info(f"PDF 파일 없음. 사이드바에서 업로드하거나 아래 경로에 직접 넣으세요:\n\n`{PDF_DIR}`")
        return

    # 상품별 그룹핑
    products = {}
    for pdf in pdf_files:
        product = pdf.name.rsplit("_", 1)[0] if "_" in pdf.name else pdf.stem
        products.setdefault(product, []).append(pdf)

    st.markdown(f'<p style="color:#b0b0b0;">{len(products)}개 상품 · {len(pdf_files)}개 파일</p>', unsafe_allow_html=True)

    for product_name, files in products.items():
        # 상품 그룹별 총 청크 수
        total_chunks = sum(indexed.get(f.name, 0) for f in files)
        group_status = f"✅ {total_chunks:,}청크" if total_chunks else "⬜ 미인덱싱"

        with st.expander(f"📦 {product_name}  ({len(files)}개 파일 · {group_status})", expanded=False):
            for pdf in files:
                doc_type = pdf.name.rsplit("_", 1)[-1].replace(".pdf", "") if "_" in pdf.name else pdf.name
                size_kb = pdf.stat().st_size / 1024
                chunks = indexed.get(pdf.name, 0)
                status = f"✅ {chunks:,}청크" if chunks else "⬜ 미인덱싱"

                col1, col2, col3 = st.columns([8, 1, 1])
                col1.markdown(
                    f'<p style="color:#d0d0d0; margin:0;">📄 {doc_type}'
                    f'<span style="color:#b0b0b0; font-size:0.85em; margin-left:12px;">{size_kb:.0f} KB · {status}</span></p>',
                    unsafe_allow_html=True,
                )
                col2.download_button("⬇", data=pdf.read_bytes(), file_name=pdf.name, mime="application/pdf", key=f"dl_{pdf.name}", help="다운로드")
                if col3.button("✕", key=f"rm_{pdf.name}", help="삭제"):
                    st.session_state[f"_confirm_del_{pdf.name}"] = True

                # 삭제 확인
                if st.session_state.get(f"_confirm_del_{pdf.name}"):
                    st.warning(f"**{pdf.name}** 삭제하시겠습니까?")
                    _, c1, c2 = st.columns([6, 1, 1])
                    if c1.button("삭제 확인", key=f"yes_{pdf.name}", type="primary"):
                        from send2trash import send2trash
                        send2trash(str(pdf))
                        _delete_file(pdf.name)
                        st.session_state.pop(f"_confirm_del_{pdf.name}", None)
                        st.rerun()
                    if c2.button("취소", key=f"no_{pdf.name}"):
                        st.session_state.pop(f"_confirm_del_{pdf.name}", None)
                        st.rerun()


# ── 사용방법 탭 ───────────────────────────────────────────────────────
def render_search_guide_tab():
    st.subheader("검색방법")

    st.markdown("""
---
이 도구의 핵심은 **수천 페이지의 약관에서 원하는 내용을 빠르게 찾는 것**입니다.

---
#### 검색 방식 이해하기
- 검색은 **키워드 매칭 + 의미 유사도** 두 가지를 결합한 하이브리드 방식입니다.
- 입력한 검색어가 정확히 포함된 문서뿐 아니라, 의미가 비슷한 내용도 함께 찾아줍니다.
- 결과 옆 **퍼센트(%)** 는 1위 대비 상대적 관련도입니다 (1위 = 100%).

---
#### 효과적인 검색 방법
- 구체적으로 검색할수록 정확한 결과가 나옵니다.
  - ❌ `보험금` → 결과가 너무 많고 광범위
  - ✅ `암 진단금 지급 조건` → 원하는 조항을 정확히 찾음
  - ✅ `입원 보험금 청구 서류` → 필요한 서류 목록을 바로 확인
- **2글자 이상 단어**로 검색하세요. 1글자(예: "암")는 단독 검색보다 조합 검색이 정확합니다.
  - ❌ `암` → 단독 검색 시 노이즈 가능
  - ✅ `암 진단`, `암 보험금`, `암 면책기간` → 정확한 결과
- 자연스러운 문장으로 검색해도 됩니다.
  - ✅ `수술비는 얼마나 나오나요`
  - ✅ `보험료 납입 면제 조건이 뭐야`

---
#### 실전 검색 예시

| 이런 걸 알고 싶을 때 | 이렇게 검색하세요 |
|---|---|
| **보험금 청구/지급** | |
| 보험금 청구할 때 뭐 필요해? | `보험금 청구 서류` |
| 보험금 언제까지 줘야 해? | `보험금 지급 기한` |
| 보험금 늦게 주면 이자 붙어? | `지연이자` 또는 `보험금 지급 지연` |
| 보험금을 대리인이 받을 수 있어? | `지정대리청구인` |
| **진단/수술/입원** | |
| 암 걸리면 얼마 받아? | `암 진단금 지급` |
| 수술비 보장 범위가 어떻게 돼? | `수술 보험금 지급 기준` |
| 입원비 최대 며칠까지 나와? | `입원 보험금 한도` |
| 통원 치료도 보장돼? | `통원 의료비` 또는 `외래 보장` |
| 어떤 질병이 중대한 질병이야? | `중대한 질병` 또는 `특정 질병` |
| **면책/감액** | |
| 보험금 안 주는 경우가 뭐야? | `면책 사유` 또는 `보험금 부지급` |
| 가입 초기에 보험금 깎이나? | `감액 기간` 또는 `감액 지급` |
| 자살하면 보험금 나와? | `자살 면책` 또는 `자살 보험금` |
| 음주운전 사고도 보장돼? | `음주 면책` 또는 `음주운전 보장` |
| 전쟁이나 자연재해는? | `전쟁 면책` 또는 `천재지변` |
| **계약/가입** | |
| 기존 병력 있으면 가입 가능해? | `고지의무 위반` 또는 `계약전 알릴의무` |
| 보험 계약 취소할 수 있어? | `청약 철회` 또는 `품질보증해지` |
| 보험 나이는 어떻게 계산해? | `보험 나이` 또는 `계약 나이` |
| 수익자를 바꿀 수 있어? | `수익자 변경` |
| **보험료/갱신** | |
| 보험료 안 내면 어떻게 돼? | `보험료 납입 유예` 또는 `실효 해지` |
| 갱신할 때 보험료 얼마나 올라? | `갱신 보험료 인상` |
| 보험료 납입 면제 조건이 뭐야? | `보험료 납입 면제` |
| 보험료 자동이체 변경하려면? | `보험료 납입 방법` |
| **해지/환급** | |
| 해지하면 환급금 얼마야? | `해약환급금 계산` |
| 중도 해지하면 손해가 커? | `해약환급금` 또는 `중도 해지` |
| 보험 부활시킬 수 있어? | `효력 회복` 또는 `계약 부활` |
| **실손/자기부담** | |
| 실손보험 자기부담금이 얼마야? | `실손 자기부담` |
| 비급여 항목도 보장돼? | `비급여 보장` 또는 `실손 비급여` |
| 도수치료도 실손에서 돼? | `도수치료` 또는 `비급여 물리치료` |
| **특약/보장** | |
| 어떤 특약이 있어? | `특약 종류` 또는 `특별약관` |
| 특약 중도에 추가할 수 있어? | `특약 추가` 또는 `특약 변경` |
| **민원/분쟁** | |
| 보험사가 보험금 안 주면? | `분쟁 조정` 또는 `이의 제기` |
| 민원 어디에 넣어야 해? | `민원 접수` 또는 `금융감독원` |

---
#### 카테고리별 키워드 활용
- 검색창 아래에 10개 카테고리(보험금, 진단·수술·입원, 면책·감액 등)가 있습니다.
- 카테고리를 클릭하면 자주 검색되는 키워드 목록이 나타납니다.
- **키워드를 클릭하면 바로 검색됩니다** — 일일이 타이핑할 필요 없습니다.

---
#### 내 키워드 관리
- ⭐ 내 키워드 탭에서 자주 쓰는 검색어를 등록할 수 있습니다.
- ✏️ 버튼을 눌러 편집 모드로 전환하면 키워드 추가/삭제가 가능합니다.
- 등록된 키워드를 클릭하면 바로 검색됩니다.

---
#### 검색 범위 지정 (좌측 사이드바)
- 상품이 여러 개인 경우, 좌측 사이드바에서 특정 상품만 선택해서 검색 범위를 좁힐 수 있습니다.
- 선택하지 않으면 전체 문서에서 검색합니다.
- 상품별로 자동 그룹핑되어 있어 원하는 상품을 쉽게 찾을 수 있습니다.

---
#### 검색 결과 보기
- 결과는 관련도 높은 순으로 정렬됩니다.
- **모두 펼치기** 토글로 결과 내용을 한눈에 볼 수 있습니다.
- 결과 수는 검색창 오른쪽 드롭다운에서 변경 가능합니다 (3, 5, 10, 20개).
- 관련 없는 결과는 자동으로 필터링되어 표시되지 않습니다.
""")


def render_help_tab():
    st.subheader("사용방법")

    st.markdown("""
---
#### 1. PDF 문서 추가하기

**방법 A) 드래그 업로드**
- 📁 문서 관리 탭에서 드래그로 PDF를 업로드할 수 있습니다.
- 업로드된 파일은 아래 폴더에 자동 저장됩니다.

**방법 B) 폴더에 직접 넣기**
""")
    st.code(str(PDF_DIR), language=None)
    st.markdown("""
**파일명 규칙 (중요!)**
- `상품명_문서종류.pdf` 형식으로 저장하면 상품별 자동 그룹핑됩니다.
- 예시:
  - `(무)하나로 누리는 건강보험_계약자용약관.pdf`
  - `(무)하나로 누리는 건강보험_사업방법서.pdf`
  - `(무)하나로 누리는 건강보험_상품요약서.pdf`
- `_` 앞부분이 같으면 같은 상품으로 묶입니다.

---
#### 2. 인덱싱 (최초 1회)

PDF를 추가한 후 **📁 문서 관리** 탭에서:
- **인덱싱 시작** — 새로 추가된 파일만 인덱싱
- **강제 재인덱싱** — 이미 처리된 파일도 다시 인덱싱

인덱싱이 완료되어야 검색이 가능합니다.

---
#### 3. 검색하기

검색 방법에 대한 자세한 설명은 **❓ 검색방법** 탭을 참고하세요.

---
#### 4. Q&A (AI 답변)

**💬 Q&A** 탭에서 자연어로 질문하면 AI가 약관 내용을 바탕으로 답변합니다.
- 예: "이 보험에서 자살은 보험금이 나오나요?"
- 예: "암 진단금 지급 조건이 뭐야?"

> `.env` 파일에 `ANTHROPIC_API_KEY=sk-ant-...`를 설정해야 사용 가능합니다.

---
#### 5. 문서 관리

**📁 문서 관리** 탭에서:
- ⬇ — PDF 다운로드
- ✕ — PDF 삭제 (확인 절차 있음, 휴지통으로 이동)
- 상품별로 그룹핑되어 표시됩니다.

---
#### 6. 실행 방법
""")
    st.code("streamlit run main.py", language="bash")
    st.markdown("""
브라우저에서 자동으로 열립니다. (기본 주소: http://localhost:8501)
""")


# ── 메인 ─────────────────────────────────────────────────────────────
def _auto_ingest_if_needed():
    """인덱싱 데이터가 없으면 자동으로 인덱싱 실행"""
    from config import BM25_INDEX_PATH, CHROMA_DIR
    chroma_db_file = CHROMA_DIR / "chroma.sqlite3"
    if not BM25_INDEX_PATH.exists() or not chroma_db_file.exists():
        pdfs = sorted(PDF_DIR.glob("*.pdf"))
        if pdfs:
            with st.spinner("첫 실행 — 문서 인덱싱 중... (1~2분 소요)"):
                from ingest import ingest_pdfs
                ingest_pdfs(log=lambda msg: None)
            st.cache_data.clear()


def main():
    _init_state()
    render_sidebar()
    _auto_ingest_if_needed()

    # ── Q&A 탭은 Claude Console API (유료, 사용량 과금) 가입 필요 ──
    # ── 가입 후 .env 파일에 ANTHROPIC_API_KEY 설정하면 사용 가능 ──
    # ── Q&A 탭을 다시 활성화하려면 아래 3줄의 주석을 해제하세요: ──
    #   1) 탭 목록에 "💬 Q&A" 추가
    #   2) tab_qa 변수 추가
    #   3) with tab_qa: render_qa_tab() 블록 추가
    tab_search, tab_manage, tab_search_guide, tab_help = st.tabs(
        ["🔍 검색", "📁 문서 관리", "❓ 검색방법", "❓ 사용방법"]
    )

    with tab_search:
        render_search_tab()

    # with tab_qa:
    #     render_qa_tab()

    with tab_manage:
        render_manage_tab()

    with tab_search_guide:
        render_search_guide_tab()

    with tab_help:
        render_help_tab()


if __name__ == "__main__":
    main()
