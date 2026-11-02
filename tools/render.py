# -*- coding: utf-8 -*-
"""Быстрая отрисовка .bdf в PNG (для визуальной проверки схем)."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bdfgen as B
from PIL import Image, ImageDraw, ImageFont

FONT = ImageFont.load_default()


def rect_of(node):
    r = B.first(node, 'rect')
    return [int(v) for v in r[1:]] if r else None


def draw_bdf(path, out, scale=1.0):
    tree = B.parse((B.ROOT / path).read_text(encoding='utf-8'))
    items = []
    ends = {}
    minx = miny = 10 ** 9
    maxx = maxy = -10 ** 9
    def upd(x, y):
        nonlocal minx, miny, maxx, maxy
        minx, miny = min(minx, x), min(miny, y)
        maxx, maxy = max(maxx, x), max(maxy, y)

    for n in tree:
        if not isinstance(n, list) or not n:
            continue
        if n[0] == 'rectangle':
            continue
        if n[0] == 'pin':
            r = rect_of(n)
            pt = [int(v) for v in B.first(n, 'pt')[1:]]
            name = [t[1].strip('"') for t in B.children(n, 'text')
                    if t[1].strip('"') not in ('INPUT', 'OUTPUT', 'BIDIR', 'VCC')][0]
            items.append(('rect', (r[0], r[1], r[2], r[3]), '#cfe0f0'))
            items.append(('bigtext', (r[0] + 70, r[1] - 16), name))
            upd(r[0], r[1]); upd(r[2], r[3])
        elif n[0] == 'symbol':
            r = rect_of(n)
            typ = B.children(n, 'text')[0][1].strip('"')
            iname = B.children(n, 'text')[1][1].strip('"')
            items.append(('rect', tuple(r), '#f7f0dc'))
            items.append(('bigtext', (r[0] + 6, r[1] - 18), '%s:%s' % (typ, iname)))
            for p in B.children(n, 'port'):
                pt = [int(v) for v in B.first(p, 'pt')[1:]]
                pname = B.children(p, 'text')[0][1].strip('"')
                items.append(('pintext', (r[0] + pt[0], r[1] + pt[1]), pname))
            upd(r[0], r[1]); upd(r[2], r[3])
        elif n[0] == 'connector':
            ps = [(int(p[1]), int(p[2])) for p in B.children(n, 'pt')]
            bus = bool(B.children(n, 'bus'))
            items.append(('poly', ps, bus))
            for tx in B.children(n, 'text'):
                r = [int(v) for v in B.first(tx, 'rect')[1:]]
                items.append(('label', (r[0], r[3] - 11), tx[1].strip('"')))
            if len(ps) == 2:
                ends[ps[0]] = ends.get(ps[0], 0) + 1
                ends[ps[1]] = ends.get(ps[1], 0) + 1
            for p in ps:
                upd(*p)
        elif n[0] == 'junction':
            pt = [int(v) for v in B.first(n, 'pt')[1:]]
            items.append(('dot', tuple(pt)))
            upd(*pt)
        elif n[0] == 'text':
            nm = n[1].strip('"')
            r = [int(v) for v in B.first(n, 'rect')[1:]]
            items.append(('label', (r[0], r[3] - 12), nm))
            upd(r[0], r[1]); upd(r[2], r[3])

    for p, c in ends.items():
        if c >= 3:
            items.append(('dot', p))
    W = int((maxx - minx + 80) * scale)
    H = int((maxy - miny + 80) * scale)
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)
    ox, oy = 40 - minx * scale, 40 - miny * scale
    def T(x, y):
        return (x * scale + ox, y * scale + oy)
    for it in items:
        if it[0] == 'rect':
            x0, y0, x1, y1 = it[1]
            d.rectangle([T(x0, y0), T(x1, y1)], outline='#888', fill=it[2])
        elif it[0] == 'poly':
            pts = [T(*p) for p in it[1]]
            w = 3 if (len(it) > 2 and it[2]) else 1
            d.line(pts, fill='#1b3f6b' if w > 1 else '#222', width=w)
        elif it[0] == 'dot':
            x, y = T(*it[1])
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill='#1b3f6b')
        elif it[0] == 'label':
            d.text(T(*it[1]), it[2], fill='#06c', font=FONT)
        elif it[0] == 'bigtext':
            d.text(T(*it[1]), it[2], fill='#603', font=FONT)
        elif it[0] == 'pintext':
            d.text(T(*it[1]), it[2], fill='#555', font=FONT)
    img.save(out)
    print('%s -> %s (%dx%d)' % (path, out, W, H))


if __name__ == '__main__':
    for f in sys.argv[1:]:
        out = pathlib.Path(__file__).resolve().parent.parent / 'docs' / 'img' / (f.replace('.bdf', '.png'))
        out.parent.mkdir(parents=True, exist_ok=True)
        draw_bdf(f, str(out), scale=1.0)
