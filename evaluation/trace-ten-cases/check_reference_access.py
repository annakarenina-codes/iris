"""Check existing reference URLs independently, without modifying the pipeline."""
import ast
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "iris-backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)
from pipeline.article_extractor import extract_article_text

tree = ast.parse((HERE / "build_reference_workbook.py").read_text(encoding="utf-8"))
sources = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "sources" for t in n.targets))
out = HERE / "retest-20260912" / "reference-access.json"
results = {}
for sid, data in sources.items():
    result = extract_article_text(data[1])
    results[sid] = {"checked_utc": datetime.now(timezone.utc).isoformat(), "url": data[1], "result": result}
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(sid, result.get("status"), result.get("word_count"), flush=True)
