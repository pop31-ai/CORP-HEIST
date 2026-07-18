"""
pdfkit_phi - zero-dependency PDF engine for CORP HEIST micro-magazines.

Writes valid PDF 1.4 by hand. No external packages: no reportlab, no fpdf,
no PIL. All visuals are vector graphics drawn with golden-section math.

Coordinate system: PDF origin is bottom-left, y grows up. We keep that
convention but expose helpers so page code can think top-down when needed.

Public surface:
    PHI, PAGE_W, PAGE_H            - constants (A4 portrait, points)
    Doc()                         - a multi-page document
        .page()  -> Canvas        - start a new page, returns its canvas
        .save(path)               - flush to a .pdf file
    Canvas                        - the per-page drawing surface
        colours, rects, lines, polylines, circles, text, gradients-by-bands
"""

import math
import os
import zlib

try:
    from ttf_reader import TTF
except Exception:                       # pragma: no cover
    TTF = None

PHI = 1.618033988749895
INV_PHI = 1.0 / PHI
TAU = math.pi * 2.0

# A4 portrait in PostScript points (1/72 inch)
PAGE_W = 595.28
PAGE_H = 841.89

# --- standard 14 PDF fonts we rely on (no embedding needed) ---
_FONTS = {
    "H":  "Helvetica",
    "HB": "Helvetica-Bold",
    "HO": "Helvetica-Oblique",
    "C":  "Courier",
    "CB": "Courier-Bold",
    "T":  "Times-Roman",
    "TB": "Times-Bold",
    "TI": "Times-Italic",
}


_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

# Embedded (Cyrillic-capable) fonts. Loaded lazily; keyed by our tag.
# Tags "U" (unicode regular) and "UB" (unicode bold) map to these files.
_EMBED_FILES = {
    "U":  "heist-sans.ttf",
    "UB": "heist-sans-bold.ttf",
}


class EmbeddedFont:
    """A TrueType font embedded as CIDFontType2 with Identity-H encoding.

    Text is written as 2-byte glyph ids. A ToUnicode CMap is emitted so the
    PDF stays copy/searchable. Widths come from hmtx via ttf_reader.
    """

    def __init__(self, tag, path):
        self.tag = tag
        self.ttf = TTF.from_file(path)
        self.font_bytes = self.ttf.data
        self.psname = "HeistSans-" + tag
        self.upm = self.ttf.units_per_em

    def encode(self, s):
        """Return the hex string of 2-byte GIDs for a PDF <..> string."""
        out = []
        for ch in s:
            gid = self.ttf.gid(ord(ch))
            out.append("%04X" % gid)
        return "".join(out)

    def width(self, s, size):
        return self.ttf.text_width(s, size)

    def used_gids(self, s, store):
        for ch in s:
            g = self.ttf.gid(ord(ch))
            store[g] = ord(ch)

    def w_array(self):
        """PDF /W array: per-glyph advance in 1000-em units."""
        scale = 1000.0 / self.upm
        parts = []
        run = []
        start = 0
        adv = self.ttf.advances
        n = len(adv)
        # simple form: [0 [w0 w1 w2 ...]]
        widths = " ".join("%d" % round(a * scale) for a in adv)
        return "[0 [%s]]" % widths, n

    def descriptor_flags(self):
        return 4  # symbolic-ish; fine for embedded subset


def is_unicode_font(tag):
    return tag in _EMBED_FILES


def _build_tounicode(gid_to_cp):
    """Emit a ToUnicode CMap stream body mapping glyph ids to codepoints."""
    entries = sorted(gid_to_cp.items())
    lines = []
    for gid, cp in entries:
        lines.append("<%04X> <%04X>" % (gid, cp))
    # bfchar blocks max 100 each
    chunks = [lines[i:i + 100] for i in range(0, len(lines), 100)] or [[]]
    body = ["/CIDInit /ProcSet findresource begin",
            "12 dict begin", "begincmap",
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) "
            "/Supplement 0 >> def",
            "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def",
            "1 begincodespacerange", "<0000> <FFFF>", "endcodespacerange"]
    for ch in chunks:
        if not ch:
            continue
        body.append("%d beginbfchar" % len(ch))
        body.extend(ch)
        body.append("endbfchar")
    body += ["endcmap", "CMapName currentdict /CMap defineresource pop",
             "end", "end"]
    cmap = "\n".join(body)
    raw = cmap.encode("latin-1", "replace")
    return ("<< /Length %d >>\nstream\n" % len(raw)).encode("latin-1") + \
           raw + b"\nendstream"


def _esc(s):
    """Escape a string for a PDF literal ()-string."""
    return (s.replace("\\", "\\\\")
             .replace("(", "\\(")
             .replace(")", "\\)")
             .replace("\r", " ")
             .replace("\n", " "))


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


class Canvas:
    """One PDF page. Accumulates a content stream of drawing operators."""

    def __init__(self, w=PAGE_W, h=PAGE_H, doc=None):
        self.w = w
        self.h = h
        self._ops = []
        self._doc = doc

    # -- low level ------------------------------------------------------
    def raw(self, s):
        self._ops.append(s)

    def _col(self, rgb):
        r, g, b = rgb
        return "%.4f %.4f %.4f" % (r / 255.0, g / 255.0, b / 255.0)

    def stream(self):
        return "\n".join(self._ops)

    # -- state ----------------------------------------------------------
    def save_state(self):
        self.raw("q")

    def restore_state(self):
        self.raw("Q")

    def set_fill(self, rgb):
        self.raw("%s rg" % self._col(rgb))

    def set_stroke(self, rgb):
        self.raw("%s RG" % self._col(rgb))

    def set_line_width(self, w):
        self.raw("%.3f w" % w)

    def set_dash(self, on, off):
        self.raw("[%.2f %.2f] 0 d" % (on, off))

    def clear_dash(self):
        self.raw("[] 0 d")

    def set_alpha_gs(self, doc, alpha):
        """Register + apply a transparency graphics state via the doc."""
        name = doc.ext_gstate(alpha)
        self.raw("/%s gs" % name)

    # -- rectangles / fills --------------------------------------------
    def rect(self, x, y, w, h, fill=None, stroke=None, lw=1.0):
        if fill is not None:
            self.set_fill(fill)
        if stroke is not None:
            self.set_stroke(stroke)
            self.set_line_width(lw)
        self.raw("%.2f %.2f %.2f %.2f re" % (x, y, w, h))
        if fill is not None and stroke is not None:
            self.raw("B")
        elif fill is not None:
            self.raw("f")
        elif stroke is not None:
            self.raw("S")

    def fill_page(self, rgb):
        self.rect(0, 0, self.w, self.h, fill=rgb)

    def vgrad(self, x, y, w, h, top_rgb, bot_rgb, bands=64):
        """Vertical gradient approximated by horizontal bands (y from bottom)."""
        for i in range(bands):
            t = i / (bands - 1.0)
            col = (lerp(bot_rgb[0], top_rgb[0], t),
                   lerp(bot_rgb[1], top_rgb[1], t),
                   lerp(bot_rgb[2], top_rgb[2], t))
            by = y + h * (i / bands)
            bh = h / bands + 0.6
            self.rect(x, by, w, bh, fill=col)

    # -- lines ----------------------------------------------------------
    def line(self, x1, y1, x2, y2, rgb=(0, 0, 0), lw=1.0):
        self.set_stroke(rgb)
        self.set_line_width(lw)
        self.raw("%.2f %.2f m %.2f %.2f l S" % (x1, y1, x2, y2))

    def polyline(self, pts, rgb=(0, 0, 0), lw=1.0, close=False, fill=None):
        if not pts:
            return
        if fill is not None:
            self.set_fill(fill)
        self.set_stroke(rgb)
        self.set_line_width(lw)
        self.raw("%.2f %.2f m" % (pts[0][0], pts[0][1]))
        for x, y in pts[1:]:
            self.raw("%.2f %.2f l" % (x, y))
        if close:
            self.raw("h")
        if fill is not None and close:
            self.raw("B")
        else:
            self.raw("S")

    # -- circles (bezier approximation) ---------------------------------
    def circle(self, cx, cy, r, fill=None, stroke=None, lw=1.0):
        k = 0.5522847498 * r
        self.raw("%.2f %.2f m" % (cx + r, cy))
        self.raw("%.2f %.2f %.2f %.2f %.2f %.2f c" %
                 (cx + r, cy + k, cx + k, cy + r, cx, cy + r))
        self.raw("%.2f %.2f %.2f %.2f %.2f %.2f c" %
                 (cx - k, cy + r, cx - r, cy + k, cx - r, cy))
        self.raw("%.2f %.2f %.2f %.2f %.2f %.2f c" %
                 (cx - r, cy - k, cx - k, cy - r, cx, cy - r))
        self.raw("%.2f %.2f %.2f %.2f %.2f %.2f c" %
                 (cx + k, cy - r, cx + r, cy - k, cx + r, cy))
        if fill is not None:
            self.set_fill(fill)
        if stroke is not None:
            self.set_stroke(stroke)
            self.set_line_width(lw)
        if fill is not None and stroke is not None:
            self.raw("B")
        elif fill is not None:
            self.raw("f")
        elif stroke is not None:
            self.raw("S")

    def ring(self, cx, cy, r, rgb, lw=1.5):
        self.circle(cx, cy, r, stroke=rgb, lw=lw)

    # -- polygons (regular / star) --------------------------------------
    def regular_poly(self, cx, cy, r, n, rot=0.0, fill=None, stroke=None, lw=1.0):
        pts = []
        for i in range(n):
            a = rot + TAU * i / n
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        self.polyline(pts, rgb=stroke or (0, 0, 0), lw=lw, close=True, fill=fill)

    def star(self, cx, cy, r_out, r_in, points=5, rot=math.pi / 2, fill=None,
             stroke=None, lw=1.0):
        pts = []
        for i in range(points * 2):
            a = rot + math.pi * i / points
            rr = r_out if i % 2 == 0 else r_in
            pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        self.polyline(pts, rgb=stroke or (0, 0, 0), lw=lw, close=True, fill=fill)

    # -- text -----------------------------------------------------------
    def text(self, x, y, s, size=10, font="H", rgb=(0, 0, 0), char_space=None):
        self.set_fill(rgb)
        emb = None
        if is_unicode_font(font) and self._doc is not None:
            emb = self._doc.embedded(font)
        self.raw("BT")
        if char_space is not None:
            self.raw("%.2f Tc" % char_space)
        self.raw("/%s %.2f Tf" % (font, size))
        self.raw("1 0 0 1 %.2f %.2f Tm" % (x, y))
        if emb is not None:
            emb.used_gids(s, self._doc._glyph_use.setdefault(font, {}))
            self.raw("<%s> Tj" % emb.encode(s))
        else:
            self.raw("(%s) Tj" % _esc(s))
        if char_space is not None:
            self.raw("0 Tc")
        self.raw("ET")

    def text_center(self, cx, y, s, size=10, font="H", rgb=(0, 0, 0),
                    char_space=0.0):
        w = text_width(s, size, font, char_space)
        self.text(cx - w / 2.0, y, s, size, font, rgb, char_space or None)

    def text_right(self, x, y, s, size=10, font="H", rgb=(0, 0, 0)):
        w = text_width(s, size, font)
        self.text(x - w, y, s, size, font, rgb)

    def paragraph(self, x, y, s, size=10, font="H", rgb=(0, 0, 0),
                  width=300, leading=None):
        """Word-wrap a paragraph. Returns the y after the last line."""
        leading = leading or size * PHI * 0.75
        words = s.split()
        line = ""
        cy = y
        for wd in words:
            trial = (line + " " + wd).strip()
            if text_width(trial, size, font) > width and line:
                self.text(x, cy, line, size, font, rgb)
                cy -= leading
                line = wd
            else:
                line = trial
        if line:
            self.text(x, cy, line, size, font, rgb)
            cy -= leading
        return cy


# --- Helvetica/Courier/Times metrics (AFM widths, per 1000 units) ------
# Compact tables good enough for justified magazine columns.
_HELV = {
    ' ': 278, '!': 278, '"': 355, '#': 556, '$': 556, '%': 889, '&': 667,
    "'": 191, '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333,
    '.': 278, '/': 278, '0': 556, '1': 556, '2': 556, '3': 556, '4': 556,
    '5': 556, '6': 556, '7': 556, '8': 556, '9': 556, ':': 278, ';': 278,
    '<': 584, '=': 584, '>': 584, '?': 556, '@': 1015, 'A': 667, 'B': 667,
    'C': 722, 'D': 722, 'E': 667, 'F': 611, 'G': 778, 'H': 722, 'I': 278,
    'J': 500, 'K': 667, 'L': 556, 'M': 833, 'N': 722, 'O': 778, 'P': 667,
    'Q': 778, 'R': 722, 'S': 667, 'T': 611, 'U': 722, 'V': 667, 'W': 944,
    'X': 667, 'Y': 667, 'Z': 611, '[': 278, '\\': 278, ']': 278, '^': 469,
    '_': 556, '`': 333, 'a': 556, 'b': 556, 'c': 500, 'd': 556, 'e': 556,
    'f': 278, 'g': 556, 'h': 556, 'i': 222, 'j': 222, 'k': 500, 'l': 222,
    'm': 833, 'n': 556, 'o': 556, 'p': 556, 'q': 556, 'r': 333, 's': 500,
    't': 278, 'u': 556, 'v': 500, 'w': 722, 'x': 500, 'y': 500, 'z': 500,
    '{': 334, '|': 260, '}': 334, '~': 584,
}
_HELV_BOLD = dict(_HELV)
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    _HELV_BOLD[_c] = int(_HELV[_c] * 1.04) + 6
for _c in "abcdefghijklmnopqrstuvwxyz":
    _HELV_BOLD[_c] = _HELV[_c] + 28


def _metrics(font):
    if font in ("HB", "CB", "TB"):
        return _HELV_BOLD
    return _HELV


_ACTIVE_DOC = [None]   # set by Doc so text_width can reach embedded metrics


def text_width(s, size, font="H", char_space=0.0):
    """Approx string width in points. Courier is monospace (600/1000)."""
    if is_unicode_font(font) and _ACTIVE_DOC[0] is not None:
        emb = _ACTIVE_DOC[0].embedded(font)
        if emb is not None:
            return emb.width(s, size) + char_space * max(0, len(s) - 1)
    if font in ("C", "CB"):
        return len(s) * size * 0.6 + char_space * max(0, len(s) - 1)
    m = _metrics(font)
    total = 0
    for ch in s:
        total += m.get(ch, 556)
    return total / 1000.0 * size + char_space * max(0, len(s) - 1)


class Doc:
    """Multi-page PDF document, serialised on save()."""

    def __init__(self, title="CORP HEIST", author="PHI PRESS", compress=True):
        self.pages = []
        self.title = title
        self.author = author
        self.compress = compress
        self._gstates = {}   # alpha -> name
        self._gs_seq = 0
        self._embedded = {}      # tag -> EmbeddedFont
        self._glyph_use = {}     # tag -> {gid: unicode}
        _ACTIVE_DOC[0] = self

    def embedded(self, tag):
        """Lazily load an embedded Cyrillic font by tag ('U' / 'UB')."""
        if TTF is None or tag not in _EMBED_FILES:
            return None
        if tag not in self._embedded:
            path = os.path.join(_FONT_DIR, _EMBED_FILES[tag])
            if not os.path.exists(path):
                return None
            self._embedded[tag] = EmbeddedFont(tag, path)
        return self._embedded.get(tag)

    def page(self):
        c = Canvas(doc=self)
        self.pages.append(c)
        _ACTIVE_DOC[0] = self
        return c

    def ext_gstate(self, alpha):
        alpha = round(clamp(alpha, 0.0, 1.0), 3)
        if alpha not in self._gstates:
            self._gs_seq += 1
            self._gstates[alpha] = "GS%d" % self._gs_seq
        return self._gstates[alpha]

    # -- serialisation --------------------------------------------------
    def _obj(self, buf, offsets, body_bytes):
        offsets.append(len(buf[0]))
        n = len(offsets)
        buf[0] += ("%d 0 obj\n" % n).encode("latin-1") + body_bytes + b"\nendobj\n"
        return n

    def save(self, path):
        buf = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
        offsets = []

        def add(body):
            if isinstance(body, str):
                body = body.encode("latin-1", "replace")
            return self._obj(buf, offsets, body)

        # 1: catalog (fill root/pages refs after we know them)
        # We pre-plan object numbers:
        #   1 catalog, 2 pages, then per page: content + page obj,
        #   then fonts, then gstates, then info.
        n_pages = len(self.pages)

        font_objs = {}
        gs_objs = {}

        # placeholders determined by counting:
        # obj1 = catalog, obj2 = pages tree
        catalog_n = 1
        pages_n = 2
        # content and page objects
        content_ns = []
        page_ns = []
        next_n = 3
        for _ in self.pages:
            content_ns.append(next_n); next_n += 1
            page_ns.append(next_n); next_n += 1
        for key in _FONTS:
            font_objs[key] = next_n; next_n += 1
        # embedded (Cyrillic) fonts: 5 objects each
        emb_objs = {}   # tag -> dict(type0, cid, desc, file, tounicode)
        for tag in sorted(self._embedded):
            emb_objs[tag] = {
                "type0": next_n, "cid": next_n + 1, "desc": next_n + 2,
                "file": next_n + 3, "tou": next_n + 4,
            }
            next_n += 5
        for alpha, name in self._gstates.items():
            gs_objs[name] = next_n; next_n += 1
        info_n = next_n

        # --- write catalog ---
        add("<< /Type /Catalog /Pages %d 0 R >>" % pages_n)

        # --- write pages tree ---
        kids = " ".join("%d 0 R" % p for p in page_ns)
        add("<< /Type /Pages /Count %d /Kids [%s] >>" % (n_pages, kids))

        # --- font resource dict fragment ---
        font_res = " ".join("/%s %d 0 R" % (k, font_objs[k]) for k in _FONTS)
        emb_res = " ".join("/%s %d 0 R" % (tag, emb_objs[tag]["type0"])
                           for tag in emb_objs)
        gs_res = " ".join("/%s %d 0 R" % (name, gs_objs[name])
                          for name in gs_objs)
        all_font_res = font_res + ((" " + emb_res) if emb_res else "")
        res = "/Font << %s >>" % all_font_res
        if gs_res:
            res += " /ExtGState << %s >>" % gs_res

        # --- write content + page objects ---
        for i, c in enumerate(self.pages):
            raw = c.stream().encode("latin-1", "replace")
            if self.compress:
                comp = zlib.compress(raw, 9)
                head = ("<< /Length %d /Filter /FlateDecode >>\nstream\n"
                        % len(comp)).encode("latin-1")
                body = head + comp + b"\nendstream"
            else:
                head = ("<< /Length %d >>\nstream\n" % len(raw)).encode("latin-1")
                body = head + raw + b"\nendstream"
            add(body)
            page_body = ("<< /Type /Page /Parent %d 0 R "
                         "/MediaBox [0 0 %.2f %.2f] "
                         "/Resources << %s >> /Contents %d 0 R >>"
                         % (pages_n, c.w, c.h, res, content_ns[i]))
            add(page_body)

        # --- fonts ---
        for key in _FONTS:
            add("<< /Type /Font /Subtype /Type1 /BaseFont /%s "
                "/Encoding /WinAnsiEncoding >>" % _FONTS[key])

        # --- embedded CID fonts ---
        for tag in sorted(self._embedded):
            emb = self._embedded[tag]
            ids = emb_objs[tag]
            warr, _ = emb.w_array()
            scale = 1000.0 / emb.upm
            xmin, ymin, xmax, ymax = emb.ttf.bbox
            asc = int(emb.ttf.ascent * scale)
            desc = int(emb.ttf.descent * scale)
            bbox = "[%d %d %d %d]" % (int(xmin * scale), int(ymin * scale),
                                      int(xmax * scale), int(ymax * scale))
            # Type0
            add("<< /Type /Font /Subtype /Type0 /BaseFont /%s "
                "/Encoding /Identity-H /DescendantFonts [%d 0 R] "
                "/ToUnicode %d 0 R >>"
                % (emb.psname, ids["cid"], ids["tou"]))
            # CIDFontType2
            add("<< /Type /Font /Subtype /CIDFontType2 /BaseFont /%s "
                "/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) "
                "/Supplement 0 >> /FontDescriptor %d 0 R "
                "/CIDToGIDMap /Identity /W %s >>"
                % (emb.psname, ids["desc"], warr))
            # FontDescriptor
            add("<< /Type /FontDescriptor /FontName /%s /Flags %d "
                "/FontBBox %s /ItalicAngle 0 /Ascent %d /Descent %d "
                "/CapHeight %d /StemV 80 /FontFile2 %d 0 R >>"
                % (emb.psname, emb.descriptor_flags(), bbox, asc, desc,
                   asc, ids["file"]))
            # FontFile2 (the actual TTF bytes, flate compressed)
            fb = emb.font_bytes
            comp = zlib.compress(fb, 9)
            file_body = ("<< /Length %d /Length1 %d /Filter /FlateDecode >>\n"
                         "stream\n" % (len(comp), len(fb))).encode("latin-1")
            file_body += comp + b"\nendstream"
            add(file_body)
            # ToUnicode CMap
            used = self._glyph_use.get(tag, {})
            add(_build_tounicode(used))

        # --- gstates ---
        for alpha, name in self._gstates.items():
            add("<< /Type /ExtGState /ca %.3f /CA %.3f >>" % (alpha, alpha))

        # --- info ---
        add("<< /Title (%s) /Author (%s) /Creator (PHI PRESS - zero-dep) >>"
            % (_esc(self.title), _esc(self.author)))

        # --- xref ---
        pdf = buf[0]
        xref_pos = len(pdf)
        n_obj = len(offsets)
        xref = ["xref", "0 %d" % (n_obj + 1), "0000000000 65535 f "]
        for off in offsets:
            xref.append("%010d 00000 n " % off)
        pdf += ("\n".join(xref) + "\n").encode("latin-1")
        pdf += ("trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\n"
                "startxref\n%d\n%%%%EOF\n"
                % (n_obj + 1, catalog_n, info_n, xref_pos)).encode("latin-1")

        with open(path, "wb") as f:
            f.write(pdf)
        return path


if __name__ == "__main__":
    d = Doc(title="pdfkit self-test")
    c = d.page()
    c.fill_page((10, 11, 22))
    c.vgrad(0, PAGE_H * 0.6, PAGE_W, PAGE_H * 0.4,
            (30, 26, 12), (10, 11, 22))
    c.text_center(PAGE_W / 2, PAGE_H - 120, "PHI PRESS", size=42,
                  font="HB", rgb=(255, 200, 0), char_space=4)
    c.star(PAGE_W / 2, PAGE_H - 200, 40, 40 * INV_PHI, 5,
           fill=(255, 226, 75), stroke=(255, 200, 0))
    c.paragraph(80, PAGE_H - 300,
                "Zero dependency PDF engine. Golden section everywhere. "
                * 6, size=11, font="H", rgb=(220, 220, 220), width=440)
    out = d.save("selftest.pdf")
    print("wrote", out)
