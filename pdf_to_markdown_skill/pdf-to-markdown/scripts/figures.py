#!/usr/bin/env python3
"""Find figures by their captions and save each as an image for embedding.

usage: figures.py INPUT.pdf WORKDIR [--dpi 200] [--max-kb 1500]

A figure is anchored on its caption: a text block starting "Fig. N", "Figure N"
or "FIG. N". The figure is the graphics (vector paths, raster images) and the
small text inside them (axis labels, legends) directly above the caption, within
the caption's column, up to the nearest line of running prose. The region is
rendered whole, so composite figures (vector art + embedded heatmaps) stay intact.
Decorative graphics without a caption (logos, badges, icons) are ignored.

Writes WORKDIR/figures/figN.png (JPEG figN.jpg if the PNG exceeds --max-kb) and
WORKDIR/figures/check_figN.png: a low-resolution view of the surroundings with the
crop drawn as a red box, for checking that nothing is cut off or included by
mistake. Prints one line per figure. In the page Markdown, place a figure with
    ![Fig. N](figure:figN)
and assemble.py embeds the image itself, so the output is one self-contained file.
"""
import sys, os, re, argparse, statistics
import pymupdf

# a caption is "Fig. 3." / "FIG. 3:" / "Figure 3 |" -- the number must be followed by a separator,
# so body text such as "Figure 1(a), computed for ..." is not taken for a caption
CAP = re.compile(r'\s*(?:Fig\.|Figure|FIG\.)\s*(\d+)\s*[.:|\u2014\u2013]')
BARE_NUM = re.compile(r'[-\u2013\u2014\s]*\d{1,4}[-\u2013\u2014\s]*')


def text_columns(lines, W):
    """Text columns [(x0, x1)] from prose lines (same method as prepare.py)."""
    long = [r for r, t, _ in lines if len(t) >= 35]
    if not long: return [(0.0, W)]
    # column starts: left edges shared by many prose lines (centred titles, affiliations and
    # indented first lines do not reach the count)
    xs = sorted(b.x0 for b in long)
    need = max(3, 0.06 * len(long))
    merged = []                          # greedy left to right: a start supported by enough lines
    for x in xs:                         # beginning within 16 pt of it (covers indented first lines)
        if merged and x - merged[-1] < 20: continue
        if sum(x <= v <= x + 16 for v in xs) >= need: merged.append(x)
    if not merged: return [(min(b.x0 for b in long), max(b.x1 for b in long))]
    cols = []
    for x in merged:
        x1s = sorted(b.x1 for b in long if x - 4 <= b.x0 <= x + 20)
        cols.append((float(x), x1s[len(x1s) // 2]))
    return cols


def ink_bbox(page, reg):
    """Shrink reg to the non-white pixels inside it (form XObjects often declare a bounding
    box far larger than what they draw)."""
    pix = page.get_pixmap(dpi=72, clip=reg, colorspace=pymupdf.csGRAY)
    w, h, s = pix.width, pix.height, pix.samples
    rows = [y for y in range(h) if min(s[y * w:(y + 1) * w]) < 245]
    colsx = [x for x in range(w) if min(s[x::w][:h]) < 245]
    if not rows or not colsx: return reg
    sx, sy = reg.width / w, reg.height / h
    return pymupdf.Rect(reg.x0 + colsx[0] * sx, reg.y0 + rows[0] * sy,
                        reg.x0 + (colsx[-1] + 1) * sx, reg.y0 + (rows[-1] + 1) * sy)
ap = argparse.ArgumentParser()
ap.add_argument('pdf'); ap.add_argument('work')
ap.add_argument('--dpi', type=int, default=200)
ap.add_argument('--max-kb', type=int, default=1500)
a = ap.parse_args()
out = os.path.join(a.work, 'figures'); os.makedirs(out, exist_ok=True)
doc = pymupdf.open(a.pdf)
chk = pymupdf.open(a.pdf)   # separate copy: check boxes must never leak into figure renders
found = []

for pno, page in enumerate(doc, 1):
    d = page.get_text('dict')
    lines = []                                   # (bbox, text, size)
    for b in d['blocks']:
        for l in b.get('lines', []):
            t = ''.join(s['text'] for s in l['spans']).strip()
            if t:
                lines.append((pymupdf.Rect(l['bbox']), t, max(s['size'] for s in l['spans'])))
    if not lines: continue
    W, H = page.rect.width, page.rect.height
    # running heads and page numbers are never part of a figure
    lines = [(r, t, sz) for r, t, sz in lines
             if not ((r.y1 < 0.08 * H or r.y0 > 0.92 * H) and (BARE_NUM.fullmatch(t) or sz < 9))]
    cols = text_columns(lines, W)
    body = statistics.mode(round(sz * 2) / 2 for _, t, sz in lines if len(t) > 30) if any(len(t) > 30 for _, t, _ in lines) else 10
    caps = [(pymupdf.Rect(b[:4]), CAP.match(b[4]).group(1)) for b in page.get_text('blocks') if CAP.match(b[4])]
    graphics = [pymupdf.Rect(dr['rect']) for dr in page.get_drawings()]
    for img in page.get_images(full=True):
        graphics += list(page.get_image_rects(img[0]))
    for cap, num in caps:
        colw = cap.width
        xl, xr = cap.x0 - 12, cap.x1 + 12
        inx = lambda r: r.x1 > xl and r.x0 < xr and (min(r.x1, xr) - max(r.x0, xl)) > 0.5 * min(r.width, colw) - 1
        # top limit: lowest line of running prose above the caption in this column
        prose = [r.y1 for r, t, sz in lines if r.y1 <= cap.y0 + 1 and inx(r) and len(t) >= 35
                 and r.width >= 0.7 * colw and abs(sz - body) <= 1.0 and not CAP.match(t)]
        # prose that is itself inside the figure would sit below graphics; take the lowest prose line
        # that has graphics below it
        top = 0
        for y in sorted(prose, reverse=True):
            if any(g.y0 >= y - 1 and g.y1 <= cap.y0 + 2 and inx(g) for g in graphics):
                top = y; break
        items = [g for g in graphics if g.y0 >= top - 1 and g.y1 <= cap.y0 + 2 and inx(g) and g.width * g.height > 0]
        items += [r for r, t, sz in lines if r.y0 >= top - 1 and r.y1 <= cap.y0 + 1 and inx(r) and not CAP.match(t)]
        if not any(g for g in graphics if g in items):
            print(f'fig{num} p{pno}: caption found but no graphics above it -> place by hand or skip'); continue
        reg = pymupdf.Rect(items[0])
        for r in items[1:]: reg |= r
        # keep the crop inside the caption's column(s), extended halfway into each gutter
        inside = [c for c in cols if c[1] > cap.x0 and c[0] < cap.x1]
        if inside:
            k0, k1 = cols.index(inside[0]), cols.index(inside[-1])
            lo = (cols[k0 - 1][1] + cols[k0][0]) / 2 if k0 > 0 else 0
            hi = (cols[k1][1] + cols[k1 + 1][0]) / 2 if k1 + 1 < len(cols) else W
            reg &= pymupdf.Rect(lo, 0, hi, H)
        reg = (ink_bbox(page, reg & page.rect) + (-3, -3, 3, 3)) & page.rect
        pix = page.get_pixmap(dpi=a.dpi, clip=reg)
        data, ext = pix.tobytes('png'), 'png'
        if len(data) > a.max_kb * 1024:
            data, ext = pix.tobytes('jpeg', jpg_quality=90), 'jpg'
        for e in ('png', 'jpg'):                 # no stale file of the other type
            if os.path.exists(f'{out}/fig{num}.{e}'): os.remove(f'{out}/fig{num}.{e}')
        open(f'{out}/fig{num}.{ext}', 'wb').write(data)
        # crop check: surroundings at low resolution with the crop outlined
        ctx = (reg + (-25, -25, 25, 25)) & page.rect
        cp = chk[pno - 1]
        shape = cp.new_shape(); shape.draw_rect(reg); shape.finish(color=(1, 0, 0), width=1.2)
        shape.commit()
        cp.get_pixmap(dpi=90, clip=ctx).save(f'{out}/check_fig{num}.png')
        found.append(num)
        print(f'fig{num} p{pno}: {pix.width}x{pix.height} {ext} {len(data)//1024} KB -> figure:fig{num} | check {out}/check_fig{num}.png')

print(f'{len(found)} figures in {out}' + ('' if found else ' (none: no captions starting "Fig." / "Figure" found)'))
