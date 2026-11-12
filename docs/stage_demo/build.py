"""Inline the extracted JSON into page.src.html -> one self-contained page. Usage: python build.py data.json out.html"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "page.src.html"), encoding="utf-8").read()
data = open(sys.argv[1], encoding="utf-8").read().replace("</", "<\/")
open(sys.argv[2], "w", encoding="utf-8").write(src.replace("__DATA__", data))
