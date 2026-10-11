"""
Génère la page web du dashboard (index.html, publiée avec GitHub Pages)
à partir des données produites par pipeline.py.

Lancer après le pipeline :  python src/build_site.py
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "data" / "processed" / "dashboard_data.json").read_text(encoding="utf-8"))
template = (ROOT / "site" / "template.html").read_text(encoding="utf-8")

page = template.replace("__DATA__", json.dumps(data, ensure_ascii=False))
(ROOT / "index.html").write_text(page, encoding="utf-8")
print("Page générée :", ROOT / "index.html")
