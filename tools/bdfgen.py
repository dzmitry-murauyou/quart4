# -*- coding: utf-8 -*-
"""Мини-генератор схем Quartus (.bdf/.bsf).

Связи выполняются именами цепей (в Quartus отрезки с одинаковым именем —
одна и та же цепь), поэтому от каждого вывода рисуется короткий отрезок
и рядом ставится имя цепи.
"""
import re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

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
    def __init__(self, title=''):
        self.items = []
        self.nets = {}   # имя цепи -> [(inst.port, ...)]
        self.title = title

    # --- служебное ---------------------------------------------------
    def _label(self, net, x0, y0, x1, y1):
        self.items.append(['text', '"%s"' % net,
                           ['rect', str(x0), str(y0), str(x1), str(y1)],
                           ['font', '"Arial"']])

    def _wire(self, pts, bus=False):
        n = ['connector'] + [['pt', str(x), str(y)] for x, y in pts]
        if bus:
            n.append(['bus'])
        self.items.append(n)

    def _stub(self, inst_name, net, pt, direction, bus=None):
        """Отрезок от вывода + подпись (имя цепи)."""
        x, y = pt
        bus = ('[' in net) if bus is None else bus
        L = max(56, 9 * len(net) + 12)
        if direction == 'left':
            self._wire([(x, y), (x - L, y)], bus)
            self._label(net, x - L + 6, y - 13, x - L + 6 + 8 * len(net), y)
        elif direction == 'right':
            self._wire([(x, y), (x + L, y)], bus)
            self._label(net, x + 4, y - 13, x + 4 + 8 * len(net), y)
        elif direction == 'down':
            self._wire([(x, y), (x, y + L)], bus)
            self._wire([(x, y + L), (x + L, y + L)], bus)
            self._label(net, x + 6, y + L - 13, x + 6 + 8 * len(net), y + L)
        elif direction == 'up':
            self._wire([(x, y), (x, y - L)], bus)
            self._wire([(x, y - L), (x + L, y - L)], bus)
            self._label(net, x + 6, y - L - 13, x + 6 + 8 * len(net), y - L)
        else:
            raise ValueError(direction)
        self.nets.setdefault(net, []).append((inst_name, direction))

    # --- элементы ----------------------------------------------------
    def pin(self, name, kind, net, x, y):
        """Вывод (input/output/bidir) с подписью цепи net."""
        net = norm(net)
        n = clone(load_pin(kind))
        r = first(n, 'rect')
        w = int(r[3]) - int(r[1])
        h = int(r[4]) - int(r[2])
        r[1:] = [str(x), str(y), str(x + w), str(y + h)]
        # имя вывода (+ ширина рамки текста под длину имени)
        for t in children(n, 'text'):
            v = t[1].strip('"')
            if v not in ('INPUT', 'OUTPUT', 'BIDIR', 'VCC'):
                t[1] = '"%s"' % name
                tr = first(t, 'rect')
                if tr is not None:
                    w = 8 * len(name) + 10
                    tr[3] = str(int(tr[1]) + w)
        pt = first(n, 'pt')
        px, py = int(pt[1]), int(pt[2])
        self.items.append(n)
        conn = (x + px, y + py)
        d = 'right' if kind == 'input' else 'left'
        self._stub(name, net, conn, d)
        return conn

    def inst(self, tmpl, iname, x, y, conns, bus=None):
        """Разместить символ; conns: {имя вывода: имя цепи}."""
        conns = {norm(k): norm(v) for k, v in conns.items()}
        self.items.append(tmpl.instance(x, y, iname))
        bus = bus or set()
        for p in tmpl.ports:
            ax, ay = x + p['pt'][0], y + p['pt'][1]
            net = conns.get(norm(p['name']))
            if net is None:
                continue
            if p['pt'][0] == 0:
                d = 'left'
            elif p['pt'][0] == tmpl.w:
                d = 'right'
            elif p['pt'][1] == tmpl.h:
                d = 'down'
            else:
                d = 'up'
            self._stub('%s.%s' % (iname, p['name']), net, (ax, ay), d)

    def note(self, text, x, y, size=10):
        self.items.append(['text', '"%s"' % text.replace('"', ''),
                           ['rect', str(x), str(y), str(x + 8 * len(text)), str(y + 18)],
                           ['font', '"Arial"', ['font_size', str(size)]]])

    def save(self, path, header=HDR_GRAPHIC):
        body = '\n'.join(dump(n) for n in self.items)
        (ROOT / path).write_text(header + '\n' + body + '\n', encoding='utf-8')

    # --- проверка ----------------------------------------------------
    def check(self):
        bad = []
        for net, users in self.nets.items():
            if not users:
                bad.append(net)
        return bad
