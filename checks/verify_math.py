"""Parse every formula in the rendered pages using the project's KaTeX runtime."""
from collections import Counter
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
import argparse
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]


class Formulas(HTMLParser):
    def __init__(self, page):
        super().__init__()
        self.page = page
        self.depth = 0
        self.parts = []
        self.items = []

    def handle_starttag(self, tag, attrs):
        if self.depth:
            self.depth += 1
        elif tag == "span" and "math" in dict(attrs).get("class", "").split():
            self.depth = 1
            self.parts = []
            self.display = "display" in dict(attrs).get("class", "").split()

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1
            if not self.depth:
                raw = "".join(self.parts).strip()
                if raw[:2] in (r"\(", r"\["):
                    raw = raw[2:-2]
                self.items.append({"page": self.page, "tex": raw,
                                   "display": self.display})

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--katex", required=True, type=Path)
    args = parser.parse_args()
    items, hashes = [], {}
    for path in sorted((ROOT / "docs").glob("*.html")):
        if path.name not in ("index.html", "student-notes.html", "exercises.html",
                             "w04-fund-contract.html", "w05-venture-contract.html",
                             "w04-preparation.html", "w05-preparation.html"):
            continue
        parsed = Formulas(path.name)
        parsed.feed(path.read_text())
        items.extend(parsed.items)
        hashes[path.name] = sha256(path.read_bytes()).hexdigest()
    script = """
const katex = require(process.argv[1]);
const items = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const errors = [];
for (const item of items) {
  try { katex.renderToString(item.tex, {throwOnError: true,
    strict: 'ignore', trust: false, displayMode: item.display}); }
  catch (error) { errors.push({...item, error: String(error)}); }
}
process.stdout.write(JSON.stringify(errors));
"""
    result = subprocess.run(["node", "-e", script, str(args.katex.resolve())],
                            input=json.dumps(items), text=True, capture_output=True, check=True)
    errors = json.loads(result.stdout)
    counts = Counter(item["page"] for item in items)
    report = {"method": "Offline KaTeX syntax check; visual checks recorded separately",
              "total": len(items),
              "pages": [{"page": name, "formulas": counts[name]} for name in hashes],
              "errors": errors, "checked_at": datetime.now().astimezone().isoformat(),
              "html_sha256": hashes}
    (ROOT / "checks/math-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"formulas": len(items), "errors": len(errors)}))
    assert not errors, errors


if __name__ == "__main__":
    main()
