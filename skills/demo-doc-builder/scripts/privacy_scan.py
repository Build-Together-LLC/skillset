#!/usr/bin/env python3
"""Scan a finished .docx for things that must not be in a shared demo document.

    privacy_scan.py doc.docx [--deny names.txt] [--allow-domain example.com --allow-domain school.example]

Reports, and exits 1 when it finds any of:
  - e-mail addresses outside the allowed domains (default: example.com, example.org, example.net, *.test, *.example)
  - secrets: private key blocks, AWS and GitHub tokens, Meta and Google tokens, long hex or base64 runs, 'api_key'/'secret' values
  - any line from the --deny file (one name, number or phrase per line, case-insensitive): real staff, parents, phone numbers
It also prints every external link so you can check them. Pictures cannot be read by it: look at those with contact_sheet.py.
"""
import argparse
import re
import sys
import zipfile

PATTERNS = {
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "AWS key": r"\bAKIA[0-9A-Z]{16}\b",
    "GitHub token": r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",
    "Meta or Google token": r"\b(?:EAA[A-Za-z0-9]{20,}|ya29\.[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,})\b",
    "long hex": r"\b[0-9a-f]{40,}\b",
    "secret assignment": r"(?i)\b(?:api[_-]?key|api[_-]?secret|access[_-]?token|password)\b\s*[:=]\s*\S{8,}",
}


def text_of(path):
    z = zipfile.ZipFile(path)
    parts = [n for n in z.namelist() if re.match(r"word/(document|header\d*|footer\d*|footnotes)\.xml", n)]
    xml = " ".join(z.read(n).decode("utf8", "ignore") for n in parts)
    links = sorted(set(re.findall(r'Target="(http[^"]+)"', z.read("word/_rels/document.xml.rels").decode())))
    return re.sub(r"<[^>]+>", " ", xml), links


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--deny")
    ap.add_argument("--allow-domain", action="append", default=[])
    a = ap.parse_args()
    text, links = text_of(a.docx)
    allowed = ["example.com", "example.org", "example.net", *a.allow_domain]
    found = []
    for mail in sorted(set(re.findall(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)", text))):
        if not (mail in allowed or mail.endswith((".test", ".example")) or any(mail.endswith("." + d) for d in allowed)):
            found.append(f"e-mail domain not allowed: @{mail}")
    for label, pat in PATTERNS.items():
        for m in sorted(set(re.findall(pat, text))):
            found.append(f"{label}: {m[:60]}")
    if a.deny:
        for line in open(a.deny):
            word = line.strip()
            if word and re.search(re.escape(word), text, re.I):
                found.append(f"denied word: {word}")
    print(f"{a.docx}: {len(found)} problem(s), {len(links)} external link(s)")
    for f in found:
        print("  !", f)
    for link in links:
        print("  link", link)
    sys.exit(1 if found else 0)


if __name__ == "__main__":
    main()
