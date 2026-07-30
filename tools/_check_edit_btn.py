# -*- coding: utf-8 -*-
import re
import urllib.request
from pathlib import Path

html = urllib.request.urlopen("http://194.226.187.101/dealer", timeout=30).read().decode("utf-8", "replace")
m = re.search(r"<script>(.*)</script>\s*</body>", html, re.S)
script = m.group(1)
Path("_dealer_script.js").write_text(script, encoding="utf-8")
print("chars", len(script))
print("editRender", "async function editRender" in script)
print("setupEditMarkup calls", script.count("setupEditMarkup"))
idx = html.find('id="dealerEditBtn"')
print("btn snippet:", html[idx : idx + 100])
# Find if button disabled logic exists
print("dealerEditBtn disabled assign", "dealerEditBtn" in script and "disabled" in script[script.find("dealerEditBtn") - 50 : script.find("dealerEditBtn") + 80] if "dealerEditBtn" in script else "no js ref")
# button never referenced in JS for disable - check
for line in script.splitlines():
    if "dealerEditBtn" in line or ("EditBtn" in line):
        print("LINE", line.strip())
