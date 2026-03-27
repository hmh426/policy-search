"""
모델 싱글톤 관리 - 무거운 모델을 한 번만 로드
"""
from config import EMBED_MODEL

_embed_model = None
_kiwi = None


def get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer(EMBED_MODEL)
    return _embed_model


def get_kiwi():
    global _kiwi
    if _kiwi is None:
        from kiwipiepy import Kiwi
        _kiwi = Kiwi()
    return _kiwi


def tokenize_ko(text: str) -> list[str]:
    """BM25용 한국어 형태소 분석 - 명사/동사/형용사 추출"""
    kiwi = get_kiwi()
    tokens = kiwi.tokenize(text)
    # 명사(NN*), 동사(VV), 형용사(VA), 외래어(SL) 추출
    keep_pos = {"NNG", "NNP", "NNB", "NR", "NP", "VV", "VA", "SL", "SH"}
    # 1글자 필터: 일반명사/고유명사(NNG,NNP)와 외래어(SL,SH)는 유지 (암, 골 등)
    # 대명사(NP), 의존명사(NNB), 동사(VV), 형용사(VA) 중 1글자는 노이즈 (이, 것, 할, 한)
    meaningful_1char = {"NNG", "NNP", "SL", "SH"}
    return [t.form for t in tokens if t.tag in keep_pos
            and (len(t.form) >= 2 or t.tag in meaningful_1char)]
