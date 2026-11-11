from __future__ import annotations

import json
import os
import re
from pathlib import Path

# 开关按这个固定顺序作用；顺序本身是 bench 契约的一部分，proposer 会看到它。
SWITCH_ORDER = (
    "trim_whitespace",
    "collapse_spaces",
    "strip_punct",
    "normalize_case",
    "dedupe_words",
    "reverse_words",
)


def apply(text: str, cfg: dict) -> str:
    """确定性地按 SWITCH_ORDER 把 6 个开关作用到字符串上。"""
    s = text
    if cfg.get("trim_whitespace"):
        s = s.strip()
    if cfg.get("collapse_spaces"):
        s = re.sub(r"\s+", " ", s)
    if cfg.get("strip_punct"):
        s = re.sub(r"[^\w\s]", "", s)
    if cfg.get("normalize_case"):
        s = s.lower()
    if cfg.get("dedupe_words"):
        out: list[str] = []
        for word in s.split(" "):
            if not out or out[-1] != word:
                out.append(word)
        s = " ".join(out)
    if cfg.get("reverse_words"):
        s = " ".join(reversed(s.split(" ")))
    return s


def main() -> None:
    """evoagent evaluate() 的子进程入口：stdin 走环境变量，stdout 只出一行 JSON。"""
    cfg = json.loads(Path(os.environ["EVO_CANDIDATE"]).read_text(encoding="utf-8-sig"))
    text = json.loads(os.environ["EVO_INPUT"])
    expected = json.loads(os.environ["EVO_EXPECTED"])
    output = apply(text, cfg)
    print(json.dumps({"passed": output == expected, "output": output}, ensure_ascii=False))


if __name__ == "__main__":
    main()
