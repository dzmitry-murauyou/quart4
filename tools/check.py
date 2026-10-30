# -*- coding: utf-8 -*-
"""Проверка сгенерированных схем: извлечение нетлиста по именам цепей."""
import sys, re, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bdfgen as B

def width(name):
    """Разрядность цепи по имени: x[7..0] -> 8, x[3] -> 1, x -> 1."""
    m = re.search(r'\[(\d+)\.\.(\d+)\]', name)
    if m:
        return abs(int(m.group(1)) - int(m.group(2))) + 1
    if re.search(r'\[\d+\]', name):
        return 1
    return 1

def netlist(path):
    txt = (B.ROOT / path).read_text(encoding='utf-8')
    tree = B.parse(txt)
    pins = []      # (tag, dir, point)
    conns = []     # [(p1,p2)]
    labels = []    # (name, rect)
    for n in tree:
        if not isinstance(n, list) or not n:
            continue
        if n[0] == 'pin':
            d = [k for k in ('input', 'output', 'bidir') if B.children(n, k)][0]
            r = [int(v) for v in B.first(n, 'rect')[1:]]
            pt = [int(v) for v in B.first(n, 'pt')[1:]]
            name = [t[1].strip('"') for t in B.children(n, 'text')
                    if t[1].strip('"') not in ('INPUT', 'OUTPUT', 'BIDIR', 'VCC')][0]
            pins.append((name, d, (r[0] + pt[0], r[1] + pt[1])))
        elif n[0] == 'symbol':
            r = [int(v) for v in B.first(n, 'rect')[1:]]
            iname = B.children(n, 'text')[1][1].strip('"')
            for p in B.children(n, 'port'):
                d = [k for k in ('input', 'output', 'bidir') if B.children(p, k)][0]
                pt = [int(v) for v in B.first(p, 'pt')[1:]]
                pname = B.children(p, 'text')[0][1].strip('"')
                pins.append(('%s.%s' % (iname, pname), d, (r[0] + pt[0], r[1] + pt[1])))
        elif n[0] == 'connector':
            ps = [(int(p[1]), int(p[2])) for p in B.children(n, 'pt')]
            conns.append(ps)
        elif n[0] == 'text':
            nm = n[1].strip('"')
            r = [int(v) for v in B.first(n, 'rect')[1:]]
            labels.append((nm, r))
    # union-find по отрезкам и точкам, затем подписи в компоненту
    uf = {}
    def find(a):
        uf.setdefault(a, a)
        while uf[a] != a:
            uf[a] = uf[uf[a]]
            a = uf[a]
        return a
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            uf[rb] = ra
    for ps in conns:
        for a, b in zip(ps, ps[1:]):
            union(a, b)
    # подпись прикрепляем к отрезку, на котором лежит её прямоугольник
    net_of = {}
    for nm, r in labels:
        rx0, ry0, rx1, ry1 = r
        for ps in conns:
            for a, b in zip(ps, ps[1:]):
                (x0, y0), (x1, y1) = a, b
                if y0 == y1 and ry1 == y0 and min(x0, x1) <= rx0 <= max(x0, x1):
                    find(a); net_of.setdefault(find(a), set()).add(nm)
                elif x0 == x1 and rx0 == x0 and min(y0, y1) <= ry1 <= max(y0, y1):
                    find(a); net_of.setdefault(find(a), set()).add(nm)
    net = {}
    for tag, d, pt in pins:
        root = find(pt)
        names = net_of.get(root)
        net[tag] = (sorted(names)[0] if names else None, d)
    return net

def report(path, show=True):
    nl = netlist(path)
    print('=== %s' % path)
    bad = []
    for tag, (nm, d) in nl.items():
        if nm is None:
            bad.append(tag)
        if show:
            print('   %-24s %-7s %s' % (tag, d, nm))
    if bad:
        print('   !!! без имени цепи: %s' % bad)
    # ширины
    w = {}
    for tag, (nm, d) in nl.items():
        if nm:
            w.setdefault(nm, set()).add(width(nm))
    confl = {k: v for k, v in w.items() if len(v) > 1}
    if confl:
        print('   !!! конфликт разрядностей: %s' % confl)
    return nl

if __name__ == '__main__':
    for f in sys.argv[1:]:
        report(f)


def summary(path):
    nl = netlist(path)
    nets = {}
    for tag, (nm, d) in nl.items():
        nets.setdefault(nm, []).append((tag, d))
    print('=== %s: цепей %d' % (path, len(nets)))
    for nm in sorted(nets, key=lambda x: (x is None, str(x))):
        if nm is None:
            continue
        drv = [t for t, d in nets[nm] if d in ('input', 'output')]
        n_in = len([1 for t, d in nets[nm] if d == 'input'])
        n_out = len([1 for t, d in nets[nm] if d == 'output'])
        n_bid = len([1 for t, d in nets[nm] if d == 'bidir'])
        w = width(nm)
        print('   %-18s w=%d  in=%d out=%d bidir=%d' % (nm, w, n_in, n_out, n_bid))
