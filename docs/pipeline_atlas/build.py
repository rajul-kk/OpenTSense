"""Inline data.json into page.src.html -> atlas.html (a single self-contained page). Usage: python build.py data.json atlas.html"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "page.src.html"), encoding="utf-8").read()
data = open(sys.argv[1], encoding="utf-8").read().replace("</", "<\/")
open(sys.argv[2], "w", encoding="utf-8").write(src.replace("__DATA__", data))
