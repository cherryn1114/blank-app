# lib/parser.py
import re
from rapidfuzz import process, fuzz
import json
from pathlib import Path

LIB = None
ALL_KEYS = None

def load_lib(path: str) -> dict:
    global LIB, ALL_KEYS
    if LIB is None:
        LIB = json.loads(Path(path).read_text(encoding="utf-8"))
        ALL_KEYS = list(LIB.keys()) + [a for v in LIB.values() for a in v.get("aliases", [])]
    return LIB

def find_term(q: str) -> tuple[str, dict]:
    match, score, _ = process.extractOne(q, ALL_KEYS, scorer=fuzz.token_set_ratio)
    # 표준 키
    if match in LIB:
        return match, LIB[match]
    # alias 역매핑
    for k, v in LIB.items():
        if match in v.get("aliases", []):
            return k, v
    return "", {}

TOKEN_RE = re.compile(r"""
    \*\s*(.*?)\s*\*\s*(\d+)\s*(?:회|times|x)   |   # * ... * n회
    \[(.*?)\]\s*(\d+)\s*(?:회|times|x)         |   # [ ... ] n회
    (k|p)(\d+)                                 |   # k3, p2
    (k2tog|p2tog|ssk|ssp|yo|m1L|m1R|k|p)       |   # 단일 토큰
    [,;]                                       |   # 구분자
    (\d+)
""", re.VERBOSE | re.IGNORECASE)

def expand_sequence(s: str) -> list[str]:
    s = s.replace("×", "x")
    tokens = []
    idx = 0
    while idx < len(s):
        m = TOKEN_RE.search(s, idx)
        if not m:
            rest = s[idx:].strip()
            if rest:
                for part in re.split(r"\s+", rest):
                    if part:
                        tokens.append(part.strip(",;"))
            break
        start, end = m.span()
        pre = s[idx:start].strip(" ,;")
        if pre:
            for part in re.split(r"\s+", pre):
                if part:
                    tokens.append(part.strip(",;"))
        g = m.groups()
        if g[0] and g[1]:
            inner, n = g[0], int(g[1])
            tokens.extend(expand_sequence(inner) * n)
        elif g[2] and g[3]:
            inner, n = g[2], int(g[3])
            tokens.extend(expand_sequence(inner) * n)
        elif g[4] and g[5]:
            base, num = g[4].lower(), int(g[5])
            tokens.extend([base] * num)
        elif g[6]:
            tokens.append(g[6].lower())
        idx = end
    tokens = [t.strip().strip(",;") for t in tokens if t.strip() and t.strip() not in [",",";"]]
    return tokens

def stitch_delta(tok: str, lib: dict) -> int:
    key = tok.lower()
    if key in ("k","p"):
        return 0
    lib_key = key.upper() if key.startswith("m1") else key
    if lib_key in lib:
        return lib[lib_key].get("delta", 0)
    mapping = {"yo":1, "m1l":1, "m1r":1, "k2tog":-1, "p2tog":-1, "ssk":-1, "ssp":-1}
    return mapping.get(key, 0)

def compute_counts(tokens: list[str], start_sts: int, lib: dict) -> list[tuple[int,str,int,int]]:
    cur = start_sts
    out = []
    step = 1
    for t in tokens:
        d = stitch_delta(t, lib)
        cur += d
        out.append((step, t, cur, d))
        step += 1
    return out