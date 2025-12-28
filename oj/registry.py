from __future__ import annotations

from oj.atcoder import atcoder_oj
from oj.base import OjAdapter, OjNames
from oj.codeforces import codeforces_oj


_OJS: dict[str, OjAdapter] = {
    OjNames.atcoder: atcoder_oj,
    OjNames.codeforces: codeforces_oj,
}


def get_oj(name: str) -> OjAdapter:
    if name not in _OJS:
        raise KeyError(f"unknown oj: {name}")
    return _OJS[name]
