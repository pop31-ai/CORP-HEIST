"""
magazine.py - CORP HEIST micro-magazine layout on top of pdfkit_phi.

Provides a Magazine wrapper that lays out a cover + article pages with the
golden-section grid, corporate-gold masthead, drop caps, pull quotes and a
running footer. Charts come from phi_charts, data from phi_data.
"""

import math
from pdfkit_phi import (Doc, PAGE_W, PAGE_H, PHI, INV_PHI, text_width, TAU)
import phi_charts as G

MARGIN = PAGE_W * (1 - INV_PHI) * 0.5   # golden outer margin ~ 50pt
COL_GAP = 16
CONTENT_W = PAGE_W - MARGIN * 2
COL_W = (CONTENT_W - COL_GAP) / 2.0
TOP = PAGE_H - MARGIN
BOTTOM = MARGIN


class Magazine:
    def __init__(self, issue_no, title, subtitle, tagline, date_str,
                 accent=G.GOLD):
        self.doc = Doc(title="CORP HEIST - %s" % title, author="PHI PRESS")
        G.bind_doc(self.doc)
        self.issue_no = issue_no
        self.title = title
        self.subtitle = subtitle
        self.tagline = tagline
        self.date_str = date_str
        self.accent = accent
        self._pageno = 0

    # ------------------------------------------------------------------
    def _footer(self, c):
        y = MARGIN * 0.55
        c.line(MARGIN, y + 10, PAGE_W - MARGIN, y + 10, rgb=G.GREY_DK, lw=0.5)
        c.text(MARGIN, y, "CORP HEIST  /  PHI PRESS", size=7,
               font="UB", rgb=G.GREY, char_space=1.0)
        c.text_center(PAGE_W / 2, y,
                      "SROCHNY VYPUSK #%02d" % self.issue_no, size=7,
                      font="U", rgb=G.GREY, char_space=2.0)
        c.text_right(PAGE_W - MARGIN, y, "str. %d" % self._pageno,
                     size=7, font="CB", rgb=self.accent)

    def _bg(self, c):
        c.fill_page(G.INK)
        # faint golden rectangle motif in a corner
        G.golden_rects(c, PAGE_W - 210, PAGE_H - 210, 190, 190,
                       depth=7, col=self.accent, alpha=0.06)
        G.phi_spiral(c, MARGIN + 30, MARGIN + 40, turns=3.0, scale=1.4,
                     col=self.accent, lw=0.5, alpha=0.05)

    def _new_page(self):
        self._pageno += 1
        c = self.doc.page()
        self._bg(c)
        return c

    # ------------------------------------------------------------------
    def cover(self, headline, deck, hero_draw=None, flashes=None):
        c = self._new_page()
        # masthead band
        band_h = 92
        c.vgrad(0, PAGE_H - band_h, PAGE_W, band_h,
                (34, 28, 10), G.INK, bands=48)
        c.line(0, PAGE_H - band_h, PAGE_W, PAGE_H - band_h,
               rgb=self.accent, lw=1.2)
        c.text(MARGIN, PAGE_H - 46, "CORP HEIST", size=30, font="UB",
               rgb=self.accent, char_space=3)
        c.text(MARGIN, PAGE_H - 66, self.tagline, size=8, font="U",
               rgb=G.GREY, char_space=2)
        c.text_right(PAGE_W - MARGIN, PAGE_H - 40,
                     "VYPUSK #%02d" % self.issue_no, size=12, font="CB",
                     rgb=G.WHITE)
        c.text_right(PAGE_W - MARGIN, PAGE_H - 58, self.date_str,
                     size=8, font="C", rgb=G.GREY)

        # SROCHNO stripe
        y = PAGE_H - band_h - 26
        c.rect(MARGIN, y, 78, 16, fill=G.RED)
        c.text(MARGIN + 6, y + 4, "SROCHNO", size=9, font="UB", rgb=G.WHITE,
               char_space=1)
        c.text(MARGIN + 88, y + 4, self.subtitle, size=9, font="UB",
               rgb=self.accent, char_space=1)

        # headline (big, golden)
        hy = y - 30
        for i, ln in enumerate(self._wrap(headline, 30, "UB")):
            c.text(MARGIN, hy - i * 34, ln, size=30, font="UB",
                   rgb=G.GOLD_LT)
        hy -= 34 * len(self._wrap(headline, 30, "UB")) + 6
        c.paragraph(MARGIN, hy, deck, size=11, font="U", rgb=G.WHITE,
                    width=CONTENT_W, leading=15)

        # hero infographic zone (golden-section slot)
        hero_h = (hy - 40) * INV_PHI
        hero_y = 40 + MARGIN
        if hero_draw:
            hero_draw(c, MARGIN, hero_y, CONTENT_W, hero_h)

        # flash bullets down the side
        if flashes:
            fy = hero_y + hero_h - 6
            # placed by caller usually; keep simple here
        self._footer(c)
        return c

    # ------------------------------------------------------------------
    def article(self, kicker, headline, body_paras, charts=None,
                pull_quote=None, boxout=None):
        """A two-column article page. charts: list of draw callables placed
        in the right rail slots. Returns the canvas."""
        c = self._new_page()
        # header
        c.rect(MARGIN, TOP - 4, 20, 4, fill=self.accent)
        c.text(MARGIN, TOP - 20, kicker, size=9, font="UB", rgb=self.accent,
               char_space=2)
        hlines = self._wrap(headline, 34, "UB")
        hy = TOP - 40
        for i, ln in enumerate(hlines):
            c.text(MARGIN, hy - i * 24, ln, size=21, font="UB", rgb=G.GOLD_LT)
        hy -= 24 * len(hlines) + 10
        c.line(MARGIN, hy + 6, PAGE_W - MARGIN, hy + 6, rgb=G.GREY_DK, lw=0.6)

        # columns
        col_x = [MARGIN, MARGIN + COL_W + COL_GAP]
        col_top = hy - 6
        col_bottom = BOTTOM + 26
        # reserve right column bottom for charts if provided
        chart_reserve = 0
        if charts:
            chart_reserve = sum(ch[1] + 12 for ch in charts)

        cur_col = 0
        cy = col_top
        first = True
        for para in body_paras:
            avail_bottom = col_bottom + (chart_reserve if cur_col == 1 else 0)
            if first:
                cy = self._drop_cap(c, col_x[cur_col], cy, para)
                first = False
            else:
                cy = c.paragraph(col_x[cur_col], cy, para, size=9.5,
                                 font="U", rgb=G.PARCH, width=COL_W,
                                 leading=13)
            cy -= 6
            if cy < avail_bottom:
                cur_col += 1
                if cur_col > 1:
                    break
                cy = col_top

        # pull quote spanning gutter in col 0 if room
        if pull_quote and cur_col == 0 and cy > col_bottom + 60:
            self._pull_quote(c, col_x[0], cy - 4, COL_W, pull_quote)

        # right rail charts
        if charts:
            chy = col_bottom
            for draw, ch_h in charts:
                draw(c, col_x[1], chy, COL_W, ch_h)
                chy += ch_h + 12

        # boxout at very bottom of col 0
        if boxout:
            self._boxout(c, col_x[0], col_bottom, COL_W, boxout)

        self._footer(c)
        return c

    # ---- helpers ------------------------------------------------------
    def _wrap(self, s, max_chars, font):
        words = s.split()
        lines, line = [], ""
        for w in words:
            if len(line) + len(w) + 1 > max_chars and line:
                lines.append(line)
                line = w
            else:
                line = (line + " " + w).strip()
        if line:
            lines.append(line)
        return lines

    def _drop_cap(self, c, x, y, para):
        if not para:
            return y
        cap = para[0]
        rest = para[1:].lstrip()
        cap_size = 40
        c.text(x, y - cap_size * 0.72, cap, size=cap_size, font="UB",
               rgb=self.accent)
        cap_w = text_width(cap, cap_size, "UB") + 6
        # first N lines flow beside the cap (narrower), then full width
        words = rest.split()
        narrow_w = COL_W - cap_w
        cy = y
        lines_beside = 3
        beside_out = []
        buf = ""
        consumed = 0            # index into words
        i = 0
        while i < len(words):
            w = words[i]
            trial = (buf + " " + w).strip()
            if text_width(trial, 9.5, "U") > narrow_w and buf:
                beside_out.append(buf)
                buf = ""
                if len(beside_out) >= lines_beside:
                    break
            else:
                buf = trial
                i += 1
                consumed = i
        if len(beside_out) < lines_beside and buf:
            beside_out.append(buf)
            buf = ""
            consumed = i
        for j, ln in enumerate(beside_out):
            c.text(x + cap_w, cy - j * 13, ln, size=9.5, font="U",
                   rgb=G.PARCH)
        cy -= 13 * len(beside_out)
        remaining = ((buf + " ") if buf else "") + " ".join(words[consumed:])
        remaining = remaining.strip()
        if remaining:
            cy = c.paragraph(x, cy, remaining, size=9.5, font="U",
                             rgb=G.PARCH, width=COL_W, leading=13)
        return cy

    def _pull_quote(self, c, x, y, w, quote):
        c.line(x, y, x, y - 40, rgb=self.accent, lw=2)
        c.paragraph(x + 10, y - 6, quote, size=13, font="U",
                    rgb=G.GOLD_LT, width=w - 14, leading=16)

    def _boxout(self, c, x, y, w, box):
        title, lines = box
        h = 16 + len(lines) * 12 + 14
        G.panel(c, x, y, w, h, fill=G.PANEL2, border=self.accent, lw=0.8)
        c.text(x + 8, y + h - 16, title, size=9, font="UB", rgb=self.accent,
               char_space=1)
        for i, ln in enumerate(lines):
            c.circle(x + 12, y + h - 30 - i * 12 + 3, 1.4, fill=self.accent)
            c.text(x + 20, y + h - 30 - i * 12, ln, size=8, font="U",
                   rgb=G.PARCH)

    def infographic_page(self, kicker, headline, tiles, intro=None):
        """A data page: a title block + a grid of chart tiles.
        tiles: list of (draw_callable, rows_span) where rows_span in {1,2}
        laid out on a 2-column golden grid. Returns the canvas."""
        c = self._new_page()
        c.rect(MARGIN, TOP - 4, 20, 4, fill=self.accent)
        c.text(MARGIN, TOP - 20, kicker, size=9, font="UB", rgb=self.accent,
               char_space=2)
        hlines = self._wrap(headline, 34, "UB")
        hy = TOP - 40
        for i, ln in enumerate(hlines):
            c.text(MARGIN, hy - i * 24, ln, size=21, font="UB", rgb=G.GOLD_LT)
        hy -= 24 * len(hlines) + 8
        if intro:
            hy = c.paragraph(MARGIN, hy, intro, size=10, font="U",
                             rgb=G.WHITE, width=CONTENT_W, leading=14)
            hy -= 6
        c.line(MARGIN, hy + 4, PAGE_W - MARGIN, hy + 4, rgb=G.GREY_DK, lw=0.6)

        grid_top = hy - 4
        grid_bottom = BOTTOM + 26
        grid_h = grid_top - grid_bottom
        # 3 rows on golden ratio; tiles fill left-to-right, top-to-bottom
        cols_x = [MARGIN, MARGIN + COL_W + COL_GAP]
        row_h = (grid_h - 2 * 14) / 3.0
        slot = 0          # 0..5 (3 rows * 2 cols)
        for draw, span in tiles:
            row = slot // 2
            col = slot % 2
            if col == 1 and span == 2:
                slot += 1
                row = slot // 2
                col = 0
            x = cols_x[col]
            top_y = grid_top - row * (row_h + 14)
            if span == 2:
                w = CONTENT_W
                h = row_h
                draw(c, x, top_y - h, w, h)
                slot += 2
            else:
                w = COL_W
                h = row_h
                draw(c, x, top_y - h, w, h)
                slot += 1
            if slot >= 6:
                break
        self._footer(c)
        return c

    def back_cover(self, lines, glossary=None):
        c = self._new_page()
        c.vgrad(0, 0, PAGE_W, PAGE_H, (18, 15, 6), G.INK, bands=60)
        G.phi_spiral(c, PAGE_W / 2, PAGE_H / 2, turns=4.2, scale=2.2,
                     col=self.accent, lw=0.8, alpha=0.5)
        c.text_center(PAGE_W / 2, PAGE_H - 120, "CORP HEIST", size=34,
                      font="UB", rgb=self.accent, char_space=4)
        c.text_center(PAGE_W / 2, PAGE_H - 150, self.tagline, size=10,
                      font="U", rgb=G.GREY, char_space=2)
        cy = PAGE_H - 210
        for ln in lines:
            c.text_center(PAGE_W / 2, cy, ln, size=12, font="U", rgb=G.WHITE)
            cy -= 22
        if glossary:
            gy = cy - 20
            G.section_title(c, MARGIN, gy, "\u0413\u041b\u041e\u0421\u0421\u0410\u0420\u0418\u0419 PHI", size=12)
            gy -= 22
            for term, desc in glossary:
                c.text(MARGIN, gy, term, size=9, font="UB", rgb=self.accent)
                c.paragraph(MARGIN + 90, gy, desc, size=9, font="U",
                            rgb=G.PARCH, width=CONTENT_W - 90, leading=12)
                gy -= 26
        self._footer(c)
        return c

    def save(self, path):
        return self.doc.save(path)
