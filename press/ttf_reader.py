"""
ttf_reader - minimal TrueType parser for PDF embedding (zero deps, stdlib only).

Reads just what a CIDFontType2 needs:
  - units per em (head)
  - cmap (format 4 and/or 12) -> unicode -> glyph id
  - hmtx -> advance widths per glyph
  - bbox + ascent/descent for FontDescriptor
Used at PDF build time; no fontTools required in this module.
"""

import struct


class TTF:
    def __init__(self, data):
        self.data = data
        self.tables = {}
        self.units_per_em = 1000
        self.num_glyphs = 0
        self.cmap = {}          # unicode codepoint -> gid
        self.advances = []      # gid -> advance width (font units)
        self.bbox = (0, 0, 1000, 1000)
        self.ascent = 800
        self.descent = -200
        self._parse()

    @classmethod
    def from_file(cls, path):
        with open(path, "rb") as f:
            return cls(f.read())

    # ------------------------------------------------------------------
    def _u16(self, o): return struct.unpack(">H", self.data[o:o+2])[0]
    def _s16(self, o): return struct.unpack(">h", self.data[o:o+2])[0]
    def _u32(self, o): return struct.unpack(">I", self.data[o:o+4])[0]

    def _parse(self):
        d = self.data
        # offset table
        num_tables = self._u16(4)
        p = 12
        for _ in range(num_tables):
            tag = d[p:p+4].decode("latin-1")
            offset = self._u32(p + 8)
            length = self._u32(p + 12)
            self.tables[tag] = (offset, length)
            p += 16
        self._parse_head()
        self._parse_maxp()
        self._parse_hhea_hmtx()
        self._parse_cmap()
        self._parse_os2()

    def _parse_head(self):
        o, _ = self.tables["head"]
        self.units_per_em = self._u16(o + 18)
        xmin = self._s16(o + 36); ymin = self._s16(o + 38)
        xmax = self._s16(o + 40); ymax = self._s16(o + 42)
        self.bbox = (xmin, ymin, xmax, ymax)
        self.index_to_loc = self._s16(o + 50)

    def _parse_maxp(self):
        o, _ = self.tables["maxp"]
        self.num_glyphs = self._u16(o + 4)

    def _parse_hhea_hmtx(self):
        oh, _ = self.tables["hhea"]
        self.ascent = self._s16(oh + 4)
        self.descent = self._s16(oh + 6)
        num_hm = self._u16(oh + 34)
        om, _ = self.tables["hmtx"]
        adv = []
        last = 0
        for i in range(self.num_glyphs):
            if i < num_hm:
                last = self._u16(om + i * 4)
            adv.append(last)
        self.advances = adv

    def _parse_os2(self):
        if "OS/2" in self.tables:
            o, _ = self.tables["OS/2"]
            try:
                self.ascent = self._s16(o + 68) or self.ascent   # sTypoAscender
                self.descent = self._s16(o + 70) or self.descent
            except Exception:
                pass

    def _parse_cmap(self):
        o, _ = self.tables["cmap"]
        n = self._u16(o + 2)
        best = None
        best_fmt = -1
        for i in range(n):
            pid = self._u16(o + 4 + i * 8)
            eid = self._u16(o + 6 + i * 8)
            off = self._u32(o + 8 + i * 8)
            sub = o + off
            fmt = self._u16(sub)
            # prefer unicode BMP/full: (3,1) fmt4, (3,10)/(0,x) fmt12
            score = fmt
            if (pid, eid) in ((3, 1), (0, 3), (3, 10), (0, 4)):
                if fmt in (4, 12) and fmt > best_fmt:
                    best = sub
                    best_fmt = fmt
        if best is None:
            # fallback: first subtable
            off = self._u32(o + 8)
            best = o + off
            best_fmt = self._u16(best)
        if best_fmt == 4:
            self._cmap4(best)
        elif best_fmt == 12:
            self._cmap12(best)
        else:
            self._cmap4(best)

    def _cmap4(self, o):
        segx2 = self._u16(o + 6)
        segc = segx2 // 2
        end_o = o + 14
        start_o = end_o + segx2 + 2
        delta_o = start_o + segx2
        range_o = delta_o + segx2
        for s in range(segc):
            end = self._u16(end_o + s * 2)
            start = self._u16(start_o + s * 2)
            delta = self._u16(delta_o + s * 2)
            r_off = self._u16(range_o + s * 2)
            for cp in range(start, end + 1):
                if cp == 0xFFFF:
                    continue
                if r_off == 0:
                    gid = (cp + delta) & 0xFFFF
                else:
                    gi = range_o + s * 2 + r_off + (cp - start) * 2
                    if gi + 1 >= len(self.data):
                        continue
                    gid = self._u16(gi)
                    if gid != 0:
                        gid = (gid + delta) & 0xFFFF
                if gid != 0:
                    self.cmap[cp] = gid

    def _cmap12(self, o):
        ngroups = self._u32(o + 12)
        p = o + 16
        for _ in range(ngroups):
            sc = self._u32(p); ec = self._u32(p + 4); sg = self._u32(p + 8)
            for cp in range(sc, ec + 1):
                self.cmap[cp] = sg + (cp - sc)
            p += 12

    # ------------------------------------------------------------------
    def gid(self, cp):
        return self.cmap.get(cp, 0)

    def advance(self, gid):
        if 0 <= gid < len(self.advances):
            return self.advances[gid]
        return self.advances[0] if self.advances else self.units_per_em

    def scaled_advance(self, cp, size):
        g = self.gid(cp)
        return self.advance(g) / self.units_per_em * size

    def text_width(self, s, size):
        w = 0.0
        for ch in s:
            w += self.scaled_advance(ord(ch), size)
        return w


if __name__ == "__main__":
    import os
    for name in ("heist-sans.ttf", "heist-sans-bold.ttf"):
        p = os.path.join(os.path.dirname(__file__), "fonts", name)
        f = TTF.from_file(p)
        print(name, "upm", f.units_per_em, "glyphs", f.num_glyphs,
              "cmap", len(f.cmap), "bbox", f.bbox)
        print("  width 'Привет' 12pt =", round(f.text_width("\u041f\u0440\u0438\u0432\u0435\u0442", 12), 2))
        print("  gid А =", f.gid(0x0410), " gid A =", f.gid(0x41))
