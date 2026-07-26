from __future__ import annotations

import json
import time
from pathlib import Path


def load_transformers_model(model_path: Path):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    tokenizer = AutoTokenizer.from_pretrained(str(model_path), trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        str(model_path),
        trust_remote_code=True,
        torch_dtype=torch.float32,
        device_map="cpu",
    )
    return tokenizer, model


def generate(tokenizer, model, prompt: str, max_new_tokens: int = 64) -> str:
    import torch

    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id
            if tokenizer.eos_token_id is not None
            else 0,
        )
    return tokenizer.decode(
        output[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True
    )


def runtime_check(model_path: Path) -> dict:
    started = time.monotonic()
    result = {
        "path": str(model_path),
        "available": False,
        "missing_modules": [],
        "loaded": False,
        "generation": None,
    }
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception as exc:
        result["missing_modules"] = ["transformers/torch"]
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["duration_s"] = round(time.monotonic() - started, 2)
        return result
    try:
        tokenizer, model = load_transformers_model(model_path)
        result["loaded"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["duration_s"] = round(time.monotonic() - started, 2)
        return result
    try:
        result["generation"] = generate(tokenizer, model, "Q: 2+2=?\nA:", 8)
        result["available"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["duration_s"] = round(time.monotonic() - started, 2)
    return result


if __name__ == "__main__":
    import sys

    path = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path(
            r"C:\Users\Administrator\.cache\huggingface\hub\models--Qwen--Qwen2.5-1.5B-Instruct\snapshots"
        )
    )
    if path.is_dir() and not path.name.startswith("models--"):
        snapshots = [child for child in path.iterdir() if child.is_dir()]
        if snapshots:
            path = snapshots[0]
    print(json.dumps(runtime_check(path), indent=2, default=str))
