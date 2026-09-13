#!/usr/bin/env python3
"""Inline css/js/corpus into one self-contained file (dist/mentor.html).
Single source of truth stays in the separate files."""
import json, pathlib, re
d = pathlib.Path(__file__).parent
html = (d / "index.html").read_text()
css = (d / "styles.css").read_text()
match = (d / "match.js").read_text()
app = (d / "app.js").read_text()
corpus = json.loads((d / "corpus.json").read_text())

html = html.replace('<link rel="stylesheet" href="styles.css">', "<style>\n" + css + "\n</style>")
html = html.replace('<link rel="manifest" href="manifest.webmanifest">', "")
html = html.replace('<script src="match.js"></script>\n<script src="app.js"></script>',
    "<script>window.SV_CORPUS=" + json.dumps(corpus, ensure_ascii=False) + ";</script>\n"
    "<script>" + match + "</script>\n<script>" + app + "</script>")
html = re.sub(r'<script>\nif \("serviceWorker".*?</script>', "", html, flags=re.S)
(d / "dist").mkdir(exist_ok=True)
(d / "dist" / "mentor.html").write_text(html)
print("dist/mentor.html", len((d / "dist" / "mentor.html").read_text()), "bytes")

# Artifact target: the host supplies <!doctype>, <head> and <body>, so strip ours.
body = re.search(r"<body[^>]*>(.*)</body>", html, flags=re.S).group(1)
head = re.search(r"<head>(.*)</head>", html, flags=re.S).group(1)
keep = "\n".join(l for l in head.splitlines()
                 if "<title" in l or "<style" in l or "fonts.g" in l or l.strip() == "</style>"
                 or (l and not l.lstrip().startswith("<meta")))
style = re.search(r"<style>.*?</style>", head, flags=re.S).group(0)
fonts = "\n".join(l for l in head.splitlines() if "fonts.g" in l)
title = re.search(r"<title>.*?</title>", head, flags=re.S).group(0)
(d / "dist" / "artifact.html").write_text(fonts + "\n" + title + "\n" + style + "\n" + body)
print("dist/artifact.html", len((d / "dist" / "artifact.html").read_text()), "bytes")
