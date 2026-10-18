"""Render in temporary storage and synchronize the existing course mirrors."""
from pathlib import Path
import argparse
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["student-notes.md", "student-notes.qmd", "w04-fund-contract.qmd",
           "w05-venture-contract.qmd", "w04-preparation.qmd",
           "w05-preparation.qmd", "exercises.qmd", "pevc-handout.css"]
PAGES = ["index.html", "student-notes.html", "w04-fund-contract.html",
         "w05-venture-contract.html", "w04-preparation.html",
         "w05-preparation.html", "exercises.html"]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--math-cache", type=Path)
    parser.add_argument("--sync-parent", action="store_true")
    args = parser.parse_args()
    base = ROOT.parent
    if args.sync_parent and not (base / "W04-W05-PEVC合同理论-学生讲义.md").is_file():
        parser.error("Parent course mirror is missing")
    if args.math_cache:
        for name in ("katex.min.js", "katex.min.css"):
            if not (args.math_cache / name).is_file():
                parser.error(f"Missing math-cache asset: {name}")
    with tempfile.TemporaryDirectory(prefix="pevc-render-") as tmp:
        stage = Path(tmp)
        for name in SOURCES:
            shutil.copy2(ROOT / name, stage / name)
        config = (ROOT / "_quarto.yml").read_text()
        if args.math_cache:
            shutil.copytree(args.math_cache, stage / "katex")
            config = config.replace("    html-math-method: katex",
                "    html-math-method:\n      method: katex\n      url: katex/")
        (stage / "_quarto.yml").write_text(config)
        subprocess.run(["quarto", "render"], cwd=stage, check=True)
        for name in PAGES:
            if name != "index.html":
                rendered = (stage / "docs" / name).read_text()
                cleaned = "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
                (ROOT / "docs" / name).write_text(cleaned)
    shutil.copy2(ROOT / "docs/w05-venture-contract.html", ROOT / "w05-venture-contract.html")
    if args.sync_parent:
        for name in SOURCES:
            shutil.copy2(ROOT / name, base / "html-src" / name)
        shutil.copy2(ROOT / "student-notes.md", base / "W04-W05-PEVC合同理论-学生讲义.md")
        for folder in (base / "docs", base / "docs/html-src"):
            for name in PAGES:
                shutil.copy2(ROOT / "docs" / name, folder / name)
        if (base / "docs/html-src/student-notes.md").is_file():
            shutil.copy2(ROOT / "student-notes.md", base / "docs/html-src/student-notes.md")
    print("Rendered six pages; independent index retained; mirrors:", args.sync_parent)

if __name__ == "__main__":
    main()
