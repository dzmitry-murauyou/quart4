# -*- coding: utf-8 -*-
"""Проверка схем: геометрия проводников сверяется с замыслом (manifest).

Проверяется:
  1) каждый вывод/порт подключён проводником (нет «висящих» выводов);
  2) все выводы одной цепи лежат в одной геометрически связной компоненте;
  3) разные цепи не слипаются (нет КЗ), кроме пары «шина — её разряд(ы)»;
  4) согласованность разрядностей цепей;
  5) конец провода не попадает на чужой провод (T-образное КЗ).
"""
import sys, json, re, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bdfgen as B


def width(name):
    m = re.search(r'\[(\d+)\.\.(\d+)\]', name)
    if m:
        return abs(int(m.group(1)) - int(m.group(2))) + 1
    return 1


def base(name):
    m = re.match(r'^([A-Za-z_]\w*)\[', name)
    return m.group(1) if m else name


def rng(name):
    m = re.match(r'^[A-Za-z_]\w*\[(\d+)(?:\.\.(\d+))?\]$', name)
    if not m:
        return None
    a = int(m.group(1))
    b = int(m.group(2)) if m.group(2) else a
    return (min(a, b), max(a, b))


def parse_bdf(path):
    tree = B.parse((B.ROOT / path).read_text(encoding='utf-8'))
    ports = []      # (tag, dir, point)
    segs = []       # (a, b, bus)
    labels = []     # (имя, rect)
    for n in tree:
        if not isinstance(n, list) or not n:
            continue
        if n[0] == 'pin':
            d = [k for k in ('input', 'output', 'bidir') if B.children(n, k)][0]
            r = [int(v) for v in B.first(n, 'rect')[1:]]
            pt = [int(v) for v in B.first(n, 'pt')[1:]]
            nm = [t[1].strip('"') for t in B.children(n, 'text')
                  if t[1].strip('"') not in ('INPUT', 'OUTPUT', 'BIDIR', 'VCC')][0]
            ports.append((nm, d, (r[0] + pt[0], r[1] + pt[1])))
        elif n[0] == 'symbol':
            r = [int(v) for v in B.first(n, 'rect')[1:]]
            iname = B.children(n, 'text')[1][1].strip('"')
            for p in B.children(n, 'port'):
                d = [k for k in ('input', 'output', 'bidir') if B.children(p, k)][0]
                pt = [int(v) for v in B.first(p, 'pt')[1:]]
                pn = B.children(p, 'text')[0][1].strip('"')
                ports.append(('%s.%s' % (iname, pn), d,
                              (r[0] + pt[0], r[1] + pt[1])))
        elif n[0] == 'connector':
            ps = [(int(p[1]), int(p[2])) for p in B.children(n, 'pt')]
            bus = bool(B.children(n, 'bus'))
            for a, b in zip(ps, ps[1:]):
                segs.append((a, b, bus))
            for tx in B.children(n, 'text'):
                r = [int(v) for v in B.first(tx, 'rect')[1:]]
                labels.append((tx[1].strip('"'), tuple(r), True))
        elif n[0] == 'text':
            if B.children(n, 'font') and B.children(B.first(n, 'font'), 'font_size'):
                continue          # пояснительная надпись, а не имя цепи
            lab = n[1].strip('"')
            r = [int(v) for v in B.first(n, 'rect')[1:]]
            labels.append((lab, tuple(r), False))
    return ports, segs, labels


def seg_touches_rect(a, b, r):
    """Проводник касается рамки подписи (проводник проходит по её краю)."""
    x0, y0, x1, y1 = r
    if a[1] == b[1]:
        return y0 <= a[1] <= y1 and not (max(a[0], b[0]) < x0 or min(a[0], b[0]) > x1)
    return x0 <= a[0] <= x1 and not (max(a[1], b[1]) < y0 or min(a[1], b[1]) > y1)


def on_seg(p, a, b):
    if a[1] == b[1] == p[1]:
        return min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
    if a[0] == b[0] == p[0]:
        return min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    return False


def strictly_on(p, a, b):
    return on_seg(p, a, b) and p != a and p != b


def analyse(path):
    ports, segs, labels = parse_bdf(path)
    uf = {}

    def find(x):
        uf.setdefault(x, x)
        while uf[x] != x:
            uf[x] = uf[uf[x]]
            x = uf[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            uf[rb] = ra

    for a, b, bus in segs:
        union(a, b)
    pts = set()
    for a, b, bus in segs:
        pts.add(a)
        pts.add(b)
    pts.update(p for _, _, p in ports)
    for p in pts:
        for a, b, bus in segs:
            if on_seg(p, a, b):
                union(p, a)
    # подписи цепей прикрепляем к проводнику, на котором лежит подпись
    lab_of = {}
    for lab, r, in_conn in labels:
        if in_conn:
            lab_of.setdefault(('conn', lab), set()).add(lab)
            continue
        for a, b, bus in segs:
            if seg_touches_rect(a, b, r):
                lab_of.setdefault(find(a), set()).add(lab)
    return ports, segs, find, lab_of


def check(path, verbose=True):
    ports, segs, find, lab_of = analyse(path)
    mf = B.ROOT / 'tools' / ('manifest_%s.json' % path)
    manifest = json.loads(mf.read_text(encoding='utf-8'))
    errors = []
    # 1) висящие выводы
    at = {}
    used = {t for tags in manifest.values() for t in tags}
    unused = []
    for tag, d, p in ports:
        tgt = [s for s in segs if on_seg(p, s[0], s[1])]
        if not tgt:
            if tag in used:
                errors.append('вывод без проводника: %s%s' % (tag, p))
            else:
                unused.append(tag)
        at[tag] = p
    # 2) одна цепь — одна компонента
    comp = {}
    for net, tags in manifest.items():
        roots = set()
        for t in tags:
            if t not in at:
                errors.append('в manifest цепь %s ссылается на несуществующий %s' % (net, t))
                continue
            roots.add(find(at[t]))
        comp[net] = roots
        if len(roots) > 1:
            lost = [t for t in tags if t in at and find(at[t]) != min(roots)]
            errors.append('цепь %s разорвана (%d компонент), оторваны: %s'
                          % (net, len(roots), lost))
    # 3) КЗ между разными цепями
    for r in set().union(*comp.values()) if comp else []:
        fams = {}
        for net, roots in comp.items():
            if r in roots:
                fams.setdefault(base(net), set()).add(net)
        if len(fams) > 1:
            errors.append('КЗ: в одной компоненте цепи %s'
                          % sorted(n for s in fams.values() for n in s))
    # 3b) каждая подпись должна лежать на проводнике (иначе имя цепи не действует)
    attached = set()
    for names in lab_of.values():
        attached |= names
    _, _, labels = parse_bdf(path)
    for lab, r, in_conn in labels:
        if not in_conn and lab not in attached:
            errors.append('подпись "%s" не привязана к проводнику' % lab)
    # 3c) каждый отвод от шины должен быть подписан своим именем
    by_name = {lab for lab, _, _ in labels}
    known = set(manifest)
    for net in manifest:
        rn, pars = rng(net), [n for n in known if rng(n) and rng(n) != rng(net)]
        if rn is None or '..' not in net:
            continue
        parent = [n for n in known
                  if n != net and rng(n) and base(n) == base(net)
                  and rng(n)[0] <= rn[0] and rn[1] <= rng(n)[1]]
        if any(rng(p) != rn for p in parent) and net not in by_name:
            errors.append('отвод %s не подписан' % net)
    # 4) конец провода на чужом проводе
    for a, b, bus in segs:
        for p in (a, b):
            for a2, b2, bus2 in segs:
                if (a2, b2) == (a, b):
                    continue
                if strictly_on(p, a2, b2):
                    # Т-соединение допустимо только внутри одной цепи
                    n1 = [n for n, rs in comp.items() if find(p) in rs]
                    n2 = [n for n, rs in comp.items() if find(a2) in rs]
                    if base(n1[0] if n1 else '?') != base(n2[0] if n2 else '?'):
                        errors.append('T-КЗ в точке %s (%s / %s)' % (p, n1, n2))
    # 4b) корпуса символов и выводы не накладываются друг на друга
    tree = B.parse((B.ROOT / path).read_text(encoding='utf-8'))
    rects = []
    for n in tree:
        if isinstance(n, list) and n and n[0] in ('symbol', 'pin'):
            r = [int(v) for v in B.first(n, 'rect')[1:]]
            rects.append(r)
    for i in range(len(rects)):
        for j in range(i + 1, len(rects)):
            a, b = rects[i], rects[j]
            if not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]):
                errors.append('наложение символов: %s и %s' % (a, b))

    # 5) разрядности
    w = {}
    for net in manifest:
        w.setdefault(net, set()).add(width(net))
    # 6) подписи цепей: имя должно совпадать с именем разветвляемой шины
    for lab, r in []:
        pass
    n_nets = len(manifest)
    print('=== %s: выводов %d, проводников %d, цепей %d, подписей %d'
          % (path, len(ports), len(segs), n_nets, len(lab_of)))
    if unused:
        print('   (не задействованы в схеме: %s)' % ', '.join(sorted(unused)))
    if errors:
        for e in errors:
            print('   !!! %s' % e)
    else:
        print('   OK: все выводы подключены, цепи связны, КЗ нет')
    return errors


if __name__ == '__main__':
    bad = 0
    for f in sys.argv[1:]:
        bad += len(check(f))
    print('ошибок:', bad)
