#!/usr/bin/env python3
"""trust-probe-01 的 LLM proposer（evoagent propose() 的子进程入口）。

契约（core.py:130 propose）：
- 读环境变量 EVO_INCUMBENT / EVO_FAILURES / EVO_ROUND；
- stdout 只输出一个 JSON list，每个元素是一个候选 dict；
- 任何日志走 stderr；LLM 失败/超时/解析失败一律输出 []，绝不编造候选。

真实性边界：**预测内容（predicted_fix / predicted_regression / rationale）必须由
Magpie LLM 真实产出**。edit_id / kind / target_files 是分类元数据，由本脚本按轮次
确定性分配，以保证 6 类 kind 覆盖均衡、可复算（见 PREREG.md 与 README.md）。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

GATEWAY = os.environ.get("MAGPIE_URL", "http://127.0.0.1:3425/v1/chat/completions")
MODEL = os.environ.get("MAGPIE_MODEL", "workbuddy/deepseek-v4.1-flash")
TIMEOUT = float(os.environ.get("MAGPIE_TIMEOUT", "60"))
TEMPERATURE = 0.7
MAX_TOKENS = 2400

KINDS = ("tool", "prompt", "middleware", "memory", "workflow", "subagent")
SWITCHES = ("trim_whitespace", "collapse_spaces", "strip_punct",
            "normalize_case", "dedupe_words", "reverse_words")

SWITCH_DOC = (
    "trim_whitespace: 去掉字符串首尾空白\n"
    "collapse_spaces: 把连续空白合并成单个空格\n"
    "strip_punct: 去掉标点符号\n"
    "normalize_case: 全部转小写\n"
    "dedupe_words: 去掉相邻重复单词\n"
    "reverse_words: 反转单词顺序（危险操作，可能破坏已经正确的用例）"
)


def _log(message: str) -> None:
    print(f"[proposer] {message}", file=sys.stderr, flush=True)


def _emit(proposals: list) -> None:
    print(json.dumps(proposals, ensure_ascii=False))
    sys.exit(0)


def _load_case_ids() -> list[str]:
    cases = json.loads(Path("benchmark.json").read_text(encoding="utf-8-sig"))["cases"]
    return [str(c["id"]) for c in cases]


def _call_llm(system: str, user: str) -> str:
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
    }).encode("utf-8")
    req = urllib.request.Request(
        GATEWAY, data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"]


def _extract_json(text: str):
    """剥掉可能的 markdown fence，返回解析后的 list。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0]
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start < 0 or end <= start:
        raise ValueError("no JSON array in LLM output")
    return json.loads(cleaned[start:end + 1])


def _build_prompt(incumbent: dict, failures: list[str], case_ids: list[str],
                  round_no: int) -> tuple[str, str]:
    system = (
        "你是一个 agent harness 的修改器。你只输出严格的 JSON，不输出解释文字。"
    )
    user = f"""这是第 {round_no + 1} / 12 轮 harness 演化。

评估器会把下面 6 个布尔开关按固定顺序作用到每条用例的输入字符串上，
再与 expected 比较，相同才算通过：
{SWITCH_DOC}

12 条用例的 id：{json.dumps(case_ids)}
当前 incumbent（全部开关状态）：{json.dumps(incumbent, ensure_ascii=False)}
当前失败的用例 id：{json.dumps(failures)}

你的任务：提出 3 个不同的候选修改。每个候选选择一组开关状态，并且**必须自声明预测**：
这次改动预计会修好哪些用例（predicted_fix）、可能弄坏哪些用例（predicted_regression）。
这是预测，不是要你算到全对；请按你对开关语义的判断如实给出，允许出错。

严格要求：
1. 输出一个 JSON 数组，恰好 3 个元素，本轮 3 个候选的开关组合要互不相同，
   也不要与之前轮次完全一致（用第 {round_no + 1} 轮做区分）。
2. 每个元素形如：
   {{"trim_whitespace": false, "collapse_spaces": true, "strip_punct": false,
     "normalize_case": false, "dedupe_words": false, "reverse_words": false,
     "edits": [
       {{"predicted_fix": ["c09"], "predicted_regression": ["c05"], "rationale": "..."}},
       {{"predicted_fix": ["c10"], "predicted_regression": ["c07"], "rationale": "..."}}
     ]}}
   6 个开关键必须全部出现且值为布尔；edits 恰好 2 笔。
   第 1 个候选请只用 1 个开关（保守尝试），第 2、3 个候选可以用 2 个以上。
3. **回归预测不能偷懒**：大多数开关在修好某些用例的同时会弄坏当前已通过的
   用例。当前通过的用例是 c01..c08，你必须在每笔 edit 的 predicted_regression
   里至少写 1 个你认为有风险的 c01..c08 里的 id；全部留空数组会让你这次修改
   对回归盲区失去可检查性。
4. predicted_fix / predicted_regression 里的 id 只能取自上面 12 个 id，
   每笔至少有一个非空；rationale 用一句中文说明。
5. 不要输出 JSON 之外的任何文字。"""
    return system, user


def _sanitize(raw: list, case_ids: set[str], round_no: int) -> list[dict]:
    """把 LLM 的预测内容装进 evoagent 候选结构，并过滤掉不合规的声明。"""
    proposals: list[dict] = []
    dropped_candidates = 0
    for j, item in enumerate(raw[:3]):
        if not isinstance(item, dict):
            dropped_candidates += 1
            continue
        candidate: dict = {}
        valid_switches = True
        for key in SWITCHES:
            value = item.get(key)
            if not isinstance(value, bool):
                valid_switches = False
                break
            candidate[key] = value
        if not valid_switches:
            dropped_candidates += 1
            continue
        raw_edits = item.get("edits")
        if not isinstance(raw_edits, list):
            dropped_candidates += 1
            continue
        edits = []
        for k, edit in enumerate(raw_edits[:2]):
            if not isinstance(edit, dict):
                continue
            fix = edit.get("predicted_fix")
            regression = edit.get("predicted_regression")
            if not isinstance(fix, list) or not isinstance(regression, list):
                continue
            fix = [str(t) for t in fix]
            regression = [str(t) for t in regression]
            # 幻觉预测必须拦在账本之外：无效 id 的 edit 直接丢弃，不补造
            if any(t not in case_ids for t in (*fix, *regression)):
                _log(f"round={round_no} candidate={j} edit={k} dropped: unknown task id")
                continue
            if not fix and not regression:
                continue
            kind = KINDS[(round_no * 6 + j * 2 + k) % len(KINDS)]
            edits.append({
                "edit_id": f"r{round_no:02d}c{j}e{k}",
                "kind": kind,
                "target_files": [f"harness/{kind}.yaml"],
                "predicted_fix": fix,
                "predicted_regression": regression,
                "rationale": str(edit.get("rationale", "")),
            })
        if not edits:
            dropped_candidates += 1
            continue
        candidate["change_manifest"] = {"edits": edits}
        proposals.append(candidate)
    if dropped_candidates:
        _log(f"round={round_no} dropped_candidates={dropped_candidates}")
    return proposals


def main() -> None:
    try:
        case_ids = _load_case_ids()
        incumbent = json.loads(os.environ.get("EVO_INCUMBENT", "{}"))
        failures = json.loads(os.environ.get("EVO_FAILURES", "[]"))
        round_no = int(os.environ.get("EVO_ROUND", "0"))
        system, user = _build_prompt(incumbent, failures, case_ids, round_no)
        content = _call_llm(system, user)
        raw = _extract_json(content)
        if not isinstance(raw, list):
            raise ValueError("LLM output is not a JSON array")
        proposals = _sanitize(raw, set(case_ids), round_no)
        _log(f"round={round_no} proposals={len(proposals)} model={MODEL}")
        _emit(proposals)
    except (urllib.error.URLError, TimeoutError, OSError,
            KeyError, ValueError, json.JSONDecodeError) as exc:
        _log(f"FAILED: {type(exc).__name__}: {exc}")
        _emit([])


if __name__ == "__main__":
    main()
