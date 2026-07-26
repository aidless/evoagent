import json
import os
from pathlib import Path

candidate = json.loads(Path(os.environ["EVO_CANDIDATE"]).read_text(encoding="utf-8"))
value = json.loads(os.environ["EVO_INPUT"])
expected = json.loads(os.environ["EVO_EXPECTED"])
if candidate.get("trim_whitespace"):
    value = value.strip()
if candidate.get("normalize_case"):
    value = value.lower()
print(json.dumps({"passed": value == expected, "output": value}))
