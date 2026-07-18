"""
make_subset.py - build compact subset TTFs (Latin + Cyrillic + digits + punct)
from system Arial, so the PDF engine can embed them with zero runtime deps.

Run once locally (needs fontTools). Produces:
    fonts/heist-sans.ttf        (regular)
    fonts/heist-sans-bold.ttf   (bold)
The generated files are committed and loaded by pdfkit_phi at build time.
"""

import os
from fontTools import subset

HERE = os.path.dirname(__file__)
FONTS = os.path.join(HERE, "fonts")

# characters we ever print: ASCII printable + Cyrillic (upper+lower+yo) + dashes
CHARS = set()
for cp in range(0x20, 0x7F):          # basic latin
    CHARS.add(chr(cp))
for cp in range(0x0410, 0x0450):      # Cyrillic А-я
    CHARS.add(chr(cp))
CHARS.add("\u0401")                    # Ё
CHARS.add("\u0451")                    # ё
CHARS.add("\u2014")                    # em dash
CHARS.add("\u2013")                    # en dash
CHARS.add("\u2018"); CHARS.add("\u2019")
CHARS.add("\u201C"); CHARS.add("\u201D")
CHARS.add("\u00AB"); CHARS.add("\u00BB")   # << >>
CHARS.add("\u2116")                    # No
CHARS.add("\u2192")                    # arrow
CHARS.add("\u00B7")                    # middle dot
CHARS.add("\u2605")                    # star
UNICODES = sorted(ord(c) for c in CHARS)

SOURCES = [
    ("C:\\Windows\\Fonts\\arial.ttf",   "heist-sans.ttf"),
    ("C:\\Windows\\Fonts\\arialbd.ttf", "heist-sans-bold.ttf"),
]


def build():
    os.makedirs(FONTS, exist_ok=True)
    for src, dst in SOURCES:
        if not os.path.exists(src):
            print("  [skip] missing", src)
            continue
        opts = subset.Options()
        opts.glyph_names = False
        opts.recalc_bounds = True
        opts.notdef_outline = True
        opts.desubroutinize = True
        opts.drop_tables += ["FFTM", "GPOS", "GSUB", "GDEF", "DSIG"]
        opts.name_IDs = []
        opts.legacy_kern = False
        font = subset.load_font(src, opts)
        subsetter = subset.Subsetter(options=opts)
        subsetter.populate(unicodes=UNICODES)
        subsetter.subset(font)
        out = os.path.join(FONTS, dst)
        subset.save_font(font, out, opts)
        print("  [OK] %-24s %6d bytes  (%d chars)"
              % (dst, os.path.getsize(out), len(UNICODES)))


if __name__ == "__main__":
    build()
    print("Gotovo. Shrifty v", FONTS)
