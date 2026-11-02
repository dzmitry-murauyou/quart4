# -*- coding: utf-8 -*-
"""Мини-генератор схем Quartus (.bdf/.bsf) с настоящей разводкой проводниками."""
import re, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

import router as R
from router import RouteError

SLICE = re.compile(r'^([A-Za-z_]\w*)\[(\d+)(?:\.\.(\d+))?\]$')

def norm(name):
    """a[7:0] -> a[7..0] (нотация шин Quartus)."""
    return re.sub(r'\[(\d+):(\d+)\]', r'[\1..\2]', str(name))

HDR_GRAPHIC = '''/*
Copyright (C) 1991-2009 Altera Corporation
Your use of Altera Corporation's design tools, logic functions 
and other software and tools, and its AMPP partner logic 
functions, and any output files from any of the foregoing 
(including device programming or simulation files), and any 
associated documentation or information are expressly subject 
to the terms and conditions of the Altera Program License 
Subscription Agreement, Altera MegaCore Function License 
Agreement, or other applicable license agreement, including, 
without limitation, that your use is for the sole purpose of 
programming logic devices manufactured by Altera and sold by 
Altera or its authorized distributors.  Please refer to the 
applicable agreement for further details.
*/
//#pragma file_not_in_maxplusii_format
(header "graphic" (version "1.3"))'''

HDR_SYMBOL = '''/*
Copyright (C) 1991-2009 Altera Corporation
Your use of Altera Corporation's design tools, logic functions 
and other software and tools, and any AMPP partner logic 
functions, and any output files from any of the foregoing 
(including device programming or simulation files), and any 
associated documentation or information are expressly subject 
to the terms and conditions of the Altera Program License 
Subscription Agreement, Altera MegaCore Function License 
Agreement, or any other applicable license agreement, including, 
without limitation, that your use is for the sole purpose of 
programming logic devices manufactured by Altera and sold by 
Altera or its authorized distributors.  Please refer to the 
applicable agreement for further details.
*/
(header "symbol" (version "1.1"))'''

# ---------------------------------------------------------------- sexpr
TOK = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')

def parse(text):
    stack = [[]]
    for t in TOK.findall(text):
        if t == '(':
            stack.append([])
        elif t == ')':
            top = stack.pop()
            stack[-1].append(top)
        else:
            stack[-1].append(t)
    return stack[0]

def atom(x):
    return not isinstance(x, list)

MULTI = ('symbol', 'pin', 'port', 'connector', 'drawing')

def render(n):
    if atom(n):
        return n
    return '(' + ' '.join(render(c) for c in n) + ')'

def inline(n):
    return n[0] not in MULTI

def dump(n, ind=0):
    tab = '\t' * ind
    if atom(n):
        return tab + n
    if inline(n):
        return tab + render(n)
    out = tab + '(' + n[0]
    for c in n[1:]:
        out += '\n' + dump(c, ind + 1)
    return out + ')'

def children(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]

def first(node, name):
    r = children(node, name)
    return r[0] if r else None

# ---------------------------------------------------------------- шаблоны
class Symbol:
    """Шаблон символа (из .bsf или из готового .bdf)."""
    def __init__(self, node):
        self.node = node
        r = [int(v) for v in first(node, 'rect')[1:]]
        self.w, self.h = r[2] - r[0], r[3] - r[1]
        self.ports = []
        for p in children(node, 'port'):
            d = 'input'
            for k in ('input', 'output', 'bidir'):
                if children(p, k):
                    d = k
            pt = first(p, 'pt')
            texts = [t[1].strip('"') for t in children(p, 'text')]
            name = texts[0] if texts else ''
            self.ports.append({'name': name, 'dir': d,
                               'pt': (int(pt[1]), int(pt[2])),
                               'node': p})

    def pin(self, name):
        for p in self.ports:
            if p['name'] == name:
                return p
        raise KeyError(name)

    def instance(self, x, y, iname, rename=None):
        """Текст экземпляра, размещённого в точке (x, y) — левый верхний угол."""
        n = clone(self.node)
        r = first(n, 'rect')
        r[1:] = [str(x), str(y), str(x + self.w), str(y + self.h)]
        # второе текстовое поле символа — имя экземпляра
        texts = children(n, 'text')
        if len(texts) > 1:
            texts[1][1] = '"%s"' % iname
        # при необходимости переименовать выводы (например, ширина шины)
        if rename:
            for p in children(n, 'port'):
                for t in children(p, 'text'):
                    if t[1].strip('"') in rename:
                        t[1] = '"%s"' % rename[t[1].strip('"')]
        return n


def clone(n):
    return [clone(c) for c in n] if isinstance(n, list) else n


def load_bsf(name):
    txt = (ROOT / name).read_text(encoding='utf-8')
    tree = parse(txt)
    sym = [n for n in tree if isinstance(n, list) and n and n[0] == 'symbol'][0]
    return Symbol(sym)


def load_prim(name, src):
    """Первый символ типа name в файле src (.bdf/.bsf)."""
    txt = (ROOT / src).read_text(encoding='utf-8')
    tree = parse(txt)
    for n in tree:
        if isinstance(n, list) and n and n[0] == 'symbol':
            t = children(n, 'text')
            if t and t[0][1].strip('"') == name:
                return Symbol(n)
    raise KeyError('%s not found in %s' % (name, src))


def load_pin(kind):
    """Шаблон вывода (pin) нужного направления из uu.bdf."""
    txt = (ROOT / 'uu.bdf').read_text(encoding='utf-8')
    tree = parse(txt)
    for n in tree:
        if isinstance(n, list) and n and n[0] == 'pin':
            if children(n, kind):
                return n
    raise KeyError(kind)


# ---------------------------------------------------------------- схема


class Sch:
    """Схема с настоящей графической разводкой проводниками."""

    def __init__(self, title=''):
        self.items = []
        self.nets = {}      # имя цепи -> [(tag, точка)]
        self.pins = {}      # точка -> имя цепи
        self.texts = []     # (имя, rect) — подписи цепей
        self.title = title
        self.router = R.Router()

    # --- служебное ---------------------------------------------------
    def _add(self, net, tag, pt):
        if pt[0] % 8 or pt[1] % 8:
            raise RouteError('вывод %s не на сетке 8: %s' % (tag, pt))
        net = norm(net)
        self.nets.setdefault(net, []).append((tag, pt))
        self.pins[pt] = net
        self.router.add_pin(pt, net)

    def _text(self, name, x0, y0, x1, y1):
        self.items.append(['text', '"%s"' % name,
                           ['rect', str(x0), str(y0), str(x1), str(y1)],
                           ['font', '"Arial"']])
        self.texts.append((name, (x0, y0, x1, y1)))

    def _rect_free(self, x0, y0, x1, y1, net):
        """Свободен ли прямоугольник под подпись цепи."""
        r = self.router
        for (ax, ay, bx, by, pad) in r.rects:
            if not (x1 < ax - pad or x0 > bx + pad or y1 < ay - pad or y0 > by + pad):
                return False
        for (nm, (tx0, ty0, tx1, ty1)) in self.texts:
            if not (x1 < tx0 or x0 > tx1 or y1 < ty0 or y0 > ty1):
                return False
        for yy in range(y0 - (y0 % 8), y1 + 1, 8):
            for seg in r.rows.get(yy, []):
                if seg[2] != net and not (x1 < seg[0] or x0 > seg[1]):
                    return False
        for xx in range(x0 - (x0 % 8), x1 + 1, 8):
            for seg in r.cols.get(xx, []):
                if seg[2] != net and not (y1 < seg[0] or y0 > seg[1]):
                    return False
        return True

    # --- элементы ----------------------------------------------------
    def pin(self, name, kind, net, x, y):
        """Вывод схемы (input/output/bidir). Соединение — в точке (x+px, y+py)."""
        x, y = int(x) - int(x) % 8, int(y) - int(y) % 8
        n = clone(load_pin(kind))
        r = first(n, 'rect')
        w, h = int(r[3]) - int(r[1]), int(r[4]) - int(r[2])
        r[1:] = [str(x), str(y), str(x + w), str(y + h)]
        for t in children(n, 'text'):
            v = t[1].strip('"')
            if v not in ('INPUT', 'OUTPUT', 'BIDIR', 'VCC'):
                t[1] = '"%s"' % name
                tr = first(t, 'rect')
                if tr is not None:
                    tr[3] = str(int(tr[1]) + 8 * len(name) + 10)
        pt = first(n, 'pt')
        px, py = int(pt[1]), int(pt[2])
        self.items.append(n)
        self.router.block_rect(x, y, x + w, y + h, soft=8)
        conn = (x + px, y + py)
        self._add(net, name, conn)
        return conn

    def inst(self, tmpl, iname, x, y, conns):
        """Разместить символ; conns: {имя вывода: имя цепи}."""
        conns = {norm(k): norm(v) for k, v in (conns or {}).items()}
        x, y = int(x) - int(x) % 8, int(y) - int(y) % 8
        self.items.append(tmpl.instance(x, y, iname))
        self.router.block_rect(x, y, x + tmpl.w, y + tmpl.h)
        for p in tmpl.ports:
            ax, ay = x + p['pt'][0], y + p['pt'][1]
            net = conns.get(norm(p['name']))
            if net:
                self._add(net, '%s.%s' % (iname, p['name']), (ax, ay))
        return self

    def note(self, text, x, y, size=10):
        text = text.replace('"', '')
        self.items.append(['text', '"%s"' % text,
                           ['rect', str(x), str(y), str(x + 8 * len(text)), str(y + 18)],
                           ['font', '"Arial"', ['font_size', str(size)]]])
        self.router.block_rect(x, y, x + 8 * len(text), y + 18, pad=6, soft=10)

    # --- разводка ----------------------------------------------------
    def _span(self, net):
        pts = [p for _, p in self.nets[net]]
        return (max(p[0] for p in pts) - min(p[0] for p in pts) +
                max(p[1] for p in pts) - min(p[1] for p in pts))

    def connect(self):
        r = self.router
        names = list(self.nets)
        # отвод от шины: ir[5..2] при наличии цепи ir[7..0]
        def rng(n):
            m = SLICE.match(n)
            if not m:
                return None
            a = int(m.group(2))
            b = int(m.group(3)) if m.group(3) else a
            return (min(a, b), max(a, b))
        cut = {}
        for n in names:
            rn = rng(n)
            if rn is None:
                continue
            cand = []
            base = SLICE.match(n).group(1)
            for b in names:
                if b == n or '..' not in b or SLICE.match(b).group(1) != base:
                    continue
                rb = rng(b)
                if rb and rb[0] <= rn[0] and rn[1] <= rb[1] and rb != rn:
                    cand.append((rb[1] - rb[0], b))
            if cand:
                cut[n] = min(cand)[1]
        roots = [n for n in names if n not in cut]
        for n in sorted(roots, key=self._span, reverse=True):
            pts = [p for _, p in self.nets[n]]
            if len(pts) < 2:
                continue
            r.route(n, pts, bus=('..' in n))
        for n in sorted(cut, key=lambda k: -len(self.nets[k])):
            self._tap(n, cut[n])
        for n in roots:
            pts = [p for _, p in self.nets[n]]
            if len(pts) == 1:
                print('   !!! цепь %s имеет только одну точку' % n)
        self.items.extend(r.bdf_items())
        return self

    def _tap(self, net, parent):
        """Ответвление от шины parent: короткий отвод + подпись имени цепи.

        Отвод всегда перпендикулярен шине; подпись ставится над горизонтальным
        участком отвода так, чтобы проводник касался её рамки.
        """
        r = self.router
        pts = [p for _, p in self.nets[net]]
        w = 8 * len(net) + 6
        w8 = (w + 12 + 7) // 8 * 8      # длина «хвоста» отвода, кратная шагу сетки
        cands = []

        def lab_for(c, e):
            if c[0] == e[0]:                    # отвод вертикальный — подпись сбоку
                y0 = min(c[1], e[1]) + 4
                return (c[0] + 6, y0, c[0] + 6 + w, y0 + 13)
            x0 = min(c[0], e[0]) + 4            # отвод горизонтальный — подпись сверху
            return (x0, c[1] - 15, x0 + w, c[1] - 2)

        def consider(c, e, f):
            if r._hard(e, net) or r._sensitive(e, net):
                return
            if not r._edge_ok(c, e, net):
                return
            if f is not None:
                if r._hard(f, net) or r._sensitive(f, net):
                    return
                if not r._edge_ok(e, f, net):
                    return
            lab = lab_for(c, e)
            if not self._rect_free(*lab, net):
                return
            tail = f if f is not None else e
            dist = min(abs(tail[0] - p[0]) + abs(tail[1] - p[1]) for p in pts)
            cands.append((dist, c, e, f, lab))

        for (a, b, n, bus) in list(r.segs):
            if n != parent:
                continue
            if a[1] == b[1]:                       # шина горизонтальна
                lo, hi = sorted((a[0], b[0]))
                for x in range(lo + 8, hi - 8 + 1, 8):
                    c = (x, a[1])
                    for sy in (-16, -24, -32, 16, 24, 32):
                        e = (x, a[1] + sy)
                        for sx in (1, -1):
                            f = (e[0] + sx * w8, e[1])
                            consider(c, e, f)
            else:                                   # шина вертикальна
                lo, hi = sorted((a[1], b[1]))
                for y in range(lo + 8, hi - 8 + 1, 8):
                    c = (a[0], y)
                    for sx in (-((w + 24 + 7) // 8 * 8), (w + 24 + 7) // 8 * 8):
                        e = (a[0] + sx, y)
                        for sy in (24, -24):
                            f = (e[0], e[1] + sy)
                            consider(c, e, f)
        if not cands:
            raise RouteError('нет места для отвода %s от %s' % (net, parent))
        cands.sort(key=lambda x: x[0])
        for dist, c, e, f, lab in cands[:24]:
            snap = r.snapshot()
            multi = '..' in net
            r.add_segment(c, e, net, bus=multi)
            r.hidden.add((c, e))
            r.add_segment(e, f, net)
            try:
                r.route(net, [f] + pts)
            except RouteError:
                r.restore(snap)
                continue
            # имя цепи хранится внутри самого проводника-отвода (как в Quartus)
            self.items.append(['connector',
                               ['text', '"%s"' % net,
                                ['rect', str(lab[0]), str(lab[1]),
                                 str(lab[2]), str(lab[3])],
                                ['font', '"Arial"']],
                               ['pt', str(c[0]), str(c[1])],
                               ['pt', str(e[0]), str(e[1])]] + ([['bus']] if multi else []))
            self.texts.append((net, lab))
            return
        raise RouteError('не удалось развести отвод %s от %s' % (net, parent))

    # --- сохранение --------------------------------------------------
    def manifest(self):
        return {n: sorted(t for t, _ in self.nets[n]) for n in self.nets}

    def save(self, path, header=HDR_GRAPHIC):
        body = '\n'.join(dump(n) for n in self.items)
        (ROOT / path).write_text(header + '\n' + body + '\n', encoding='utf-8')
        mf = ROOT / 'tools' / ('manifest_%s.json' % path)
        mf.write_text(json.dumps(self.manifest(), ensure_ascii=False, indent=1),
                      encoding='utf-8')

    def check(self):
        return [n for n in self.nets if len(self.nets[n]) < 2]
