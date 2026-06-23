#!/usr/bin/env python3
"""progress.json 全部任务 done → exit 0；否则 exit 1。供 /goal 的收敛检测调用。"""

import json
import sys
from pathlib import Path

data = json.loads(Path("progress.json").read_text(encoding="utf-8"))
tasks = data.get("tasks", [])
total = len(tasks)
done = sum(1 for t in tasks if t.get("status") == "done")
pending = [t["id"] for t in tasks if t.get("status") != "done"]

print(f"progress: {done}/{total} done")
if pending:
    print(f"pending: {pending}")
    sys.exit(1)
sys.exit(0)
