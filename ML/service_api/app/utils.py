import re
from typing import Optional, Tuple

_WS = re.compile(r"\s+")

def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = s.strip()
    s = _WS.sub("", s)
    # 괄호, 특수문자 일부 제거(너무 공격적으로 하지 않음)
    s = re.sub(r"[()（）\[\]{}.,\-·]", "", s)
    return s

def extract_region_tokens(address: str) -> Tuple[Optional[str], Optional[str]]:
    """
    아주 단순한 휴리스틱:
    - '...구', '...동' 키워드를 address에서 찾아서 sgg/emd 추정
    실패하면 None 반환.
    """
    if not address:
        return None, None

    # 공백 단위로 토큰화(원문 유지)
    toks = re.split(r"\s+", address.strip())
    sgg = None
    emd = None
    for t in toks:
        if t.endswith("구") and sgg is None:
            sgg = t
        if (t.endswith("동") or t.endswith("읍") or t.endswith("면")) and emd is None:
            emd = t

    return sgg, emd
