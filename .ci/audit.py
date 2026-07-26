#!/usr/bin/env python3
"""Audit: re-run the full self-evolution test suite and emit a JSON summary."""
from __future__ import annotations
import json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main()->int:
    env=__import__("os").environ.copy();env["PYTHONPATH"]=str(ROOT/"src")
    started=time.monotonic()
    proc=subprocess.run([sys.executable,"-m","unittest","discover","-s",str(ROOT/"tests")],env=env,capture_output=True,text=True)
    duration=time.monotonic()-started
    last=proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    summary={"duration_s":round(duration,2),"returncode":proc.returncode,"last_line":last,"stderr_tail":proc.stderr[-400:]}
    (ROOT/".evo/ci/audit-last.json").parent.mkdir(parents=True,exist_ok=True)
    (ROOT/".evo/ci/audit-last.json").write_text(json.dumps(summary,indent=2)+chr(10),encoding="utf-8")
    print(json.dumps(summary,indent=2))
    return proc.returncode
if __name__=="__main__":sys.exit(main())
