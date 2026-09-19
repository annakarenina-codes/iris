import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "iris-backend"))
from pipeline.article_extractor import extract_article_text

urls = {
    "S15": "https://newsinfo.inquirer.net/2300646/padilla-why-not-extend-presidential-immunity-from-suit-to-vp-duterte",
    "S16": "https://www.inquirer.net/483460/live-updates-sara-duterte-impeachment-trial-aug-5-2026/",
    "S17": "https://www.philstar.com/headlines/2016/07/12/1602113/verdict-philippines-wins-arbitration-case-vs-china/amp/",
    "S18": "https://www.gmanetwork.com/news/topstories/regions/994769/american-marine-biologist-shooting-negros/story/",
    "S19": "https://mb.com.ph/2026/07/14/special-task-group-probes-fatal-shooting-of-american-marine-scientist",
    "S20": "https://www.philstar.com/other-sections/forex-stocks/2026/09/09/2555147/162513",
    "S21": "https://www.philstar.com/headlines/2026/08/07/2547564/padilla-vp-secret-funds-used-vs-reds",
}
results = {}
for sid, url in urls.items():
    result = extract_article_text(url)
    results[sid] = {"checked_utc": datetime.now(timezone.utc).isoformat(), "url": url, "result": result}
    (HERE / "retest-20260912/additional-references.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(sid, result.get("status"), result.get("word_count"), flush=True)
