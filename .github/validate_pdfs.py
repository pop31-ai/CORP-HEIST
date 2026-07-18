#!/usr/bin/env python3
"""CI gate: validate that every PHI PRESS PDF is well-formed.

Checks each issue (01..10) plus the combined almanac for:
  - %PDF-1.4 header and %%EOF trailer
  - /Root and startxref present
  - two embedded CIDFontType2 fonts (Cyrillic) via /Subtype /Type0
Exits non-zero on the first failure so CI fails loudly.
"""
import os
import sys

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "press", "out")
ISSUES = [
    "vypusk_01_phi_rynok.pdf", "vypusk_02_sektora.pdf", "vypusk_03_shorty.pdf",
    "vypusk_04_centrobank.pdf", "vypusk_05_magnaty.pdf", "vypusk_06_magnat_goda.pdf",
    "vypusk_07_derivativy.pdf", "vypusk_08_boty.pdf", "vypusk_09_gildii.pdf",
    "vypusk_10_market_meiking.pdf", "almanac_full.pdf",
]


def check(path):
    if not os.path.exists(path):
        return "missing file"
    b = open(path, "rb").read()
    if len(b) < 2000:
        return "too small (%d bytes)" % len(b)
    if b[:8] != b"%PDF-1.4":
        return "bad header %r" % b[:8]
    if b"%%EOF" not in b:
        return "no %%EOF trailer"
    if b"/Root" not in b:
        return "no /Root"
    if b"startxref" not in b:
        return "no startxref"
    cid = b.count(b"/Subtype /Type0")
    if cid < 2:
        return "expected 2 CID fonts, found %d" % cid
    return None


def main():
    failures = 0
    for name in ISSUES:
        path = os.path.join(OUT, name)
        err = check(path)
        size = os.path.getsize(path) if os.path.exists(path) else 0
        if err:
            print("  [FAIL] %-32s %s" % (name, err))
            failures += 1
        else:
            print("  [OK]   %-32s %7d bytes" % (name, size))
    if failures:
        print("PDF validation FAILED: %d file(s) bad" % failures)
        sys.exit(1)
    print("PDF validation OK: %d files" % len(ISSUES))


if __name__ == "__main__":
    main()
