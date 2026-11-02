# -*- coding: utf-8 -*-
"""Ортогональная трассировка соединений для генератора схем Quartus.

Правила, которые соблюдает трассировщик (соответствуют поведению Block Editor):
  * провода разных цепей не могут идти по одной линии (наложение = КЗ);
  * конец провода не может попадать на чужой провод (T-соединение = КЗ);
  * излом провода не может попадать на чужой провод;
  * пересечения «крест-накрест» (без излома и без конца) соединения не дают.
"""
import heapq

G = 8                      # шаг сетки, совпадает с шагом схемы

DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]


class RouteError(Exception):
    pass


class Router:
    def __init__(self, xmin=-400, ymin=-400, xmax=4000, ymax=4000):
        self.bounds = (xmin, ymin, xmax, ymax)
        self.pins = {}       # точка -> имя цепи
        self.rows = {}       # y -> [[x1, x2, net, bus], ...]
        self.cols = {}       # x -> [[y1, y2, net, bus], ...]
        self.verts = {}      # точка -> net
        self.segs = []       # (pt1, pt2, net, bus)
        self.hidden = set()  # отрезки, выводимые отдельно (с подписью цепи)
        self.blocked = set()  # точки внутри корпусов символов
        self.soft = set()     # точки рядом с корпусами (штраф, но пройти можно)
        self.rects = []

    # ---------------------------------------------------------- препятствия
    def block_rect(self, x1, y1, x2, y2, pad=0, soft=12):
        self.rects.append((x1, y1, x2, y2, pad))
        for x in range(_floor(x1 - soft), _ceil(x2 + soft) + 1, G):
            for y in range(_floor(y1 - soft), _ceil(y2 + soft) + 1, G):
                if x1 - pad < x < x2 + pad and y1 - pad < y < y2 + pad:
                    self.blocked.add((x, y))
                elif x1 - soft <= x <= x2 + soft and y1 - soft <= y <= y2 + soft:
                    self.soft.add((x, y))
        for p in self.blocked:
            self.soft.discard(p)

    def add_pin(self, pt, net):
        self.pins[pt] = net

    # ---------------------------------------------------------- отрезки
    def add_segment(self, a, b, net, bus=False):
        if a == b:
            return
        for p in (a, b):
            if p[0] % G or p[1] % G:
                raise RouteError('точка %s вне сетки %d (цепь %s)' % (p, G, net))
        if a[1] == b[1]:
            x1, x2 = sorted((a[0], b[0]))
            self.rows.setdefault(a[1], []).append([x1, x2, net, bus])
        else:
            y1, y2 = sorted((a[1], b[1]))
            self.cols.setdefault(a[0], []).append([y1, y2, net, bus])
        self.segs.append((a, b, net, bus))
        for p in (a, b):
            self.verts.setdefault(p, net)

    # ---------------------------------------------------------- снимок состояния
    def snapshot(self):
        return (dict((k, list(v)) for k, v in self.rows.items()),
                dict((k, list(v)) for k, v in self.cols.items()),
                list(self.segs), dict(self.verts), set(self.hidden))

    def restore(self, snap):
        rows, cols, segs, verts, hidden = snap
        self.rows = dict((k, list(v)) for k, v in rows.items())
        self.cols = dict((k, list(v)) for k, v in cols.items())
        self.segs = list(segs)
        self.verts = dict(verts)
        self.hidden = set(hidden)

    # ---------------------------------------------------------- проверки
    def _hard(self, p, net):
        if p in self.blocked:
            return True
        owner = self.pins.get(p)
        return owner is not None and owner != net

    def _sensitive(self, p, net):
        """Точка лежит на чужом проводе / чужой вершине (сквозь можно, излом нельзя)."""
        for s in self.rows.get(p[1], []):
            if s[2] != net and s[0] <= p[0] <= s[1]:
                return True
        for s in self.cols.get(p[0], []):
            if s[2] != net and s[0] <= p[1] <= s[1]:
                return True
        return False

    def _edge_ok(self, p, q, net):
        if p[1] == q[1]:
            a, b = sorted((p[0], q[0]))
            for s in self.rows.get(p[1], []):
                if s[2] != net and not (b < s[0] or a > s[1]):
                    return False
        else:
            a, b = sorted((p[1], q[1]))
            for s in self.cols.get(p[0], []):
                if s[2] != net and not (b < s[0] or a > s[1]):
                    return False
        return True

    def _near_foreign(self, p, net):
        """Штраф за близость к чужим проводам (чтобы линии не липли друг к другу)."""
        for dy in (-G, 0, G):
            for s in self.rows.get(p[1] + dy, []):
                if s[2] != net and s[0] - G <= p[0] <= s[1] + G:
                    return True
        for dx in (-G, 0, G):
            for s in self.cols.get(p[0] + dx, []):
                if s[2] != net and s[0] - G <= p[1] <= s[1] + G:
                    return True
        return False

    # ---------------------------------------------------------- A*
    def path(self, net, start, goals, margin=320, turn_cost=6, near_cost=2):
        goals = set(goals)
        if start in goals:
            return [start]
        x0, y0, x1, y1 = self.bounds
        xs = [start[0]] + [g[0] for g in goals]
        ys = [start[1]] + [g[1] for g in goals]
        x0 = max(x0, min(xs) - margin); x1 = min(x1, max(xs) + margin)
        y0 = max(y0, min(ys) - margin); y1 = min(y1, max(ys) + margin)

        def h(p):
            return min(abs(p[0] - g[0]) + abs(p[1] - g[1]) for g in goals)

        start_state = (start[0], start[1], -1, 0)
        openq = [(h(start) * 1.1, 0, start_state)]
        best = {start_state: 0}
        prev = {}
        goal_state = None
        while openq:
            f, g, st = heapq.heappop(openq)
            x, y, d, forced = st
            p = (x, y)
            if p in goals and p != start:
                goal_state = st
                break
            if best.get(st, 1 << 30) < g:
                continue
            for nd, (dx, dy) in enumerate(DIRS):
                if forced and nd != d:
                    continue
                np_ = (x + dx * G, y + dy * G)
                if not (x0 <= np_[0] <= x1 and y0 <= np_[1] <= y1):
                    continue
                if self._hard(np_, net):
                    continue
                if not self._edge_ok(p, np_, net):
                    continue
                sens = self._sensitive(np_, net)
                if self._sensitive(p, net) and nd != d:
                    # излом на чужом проводе запрещён
                    continue
                turn = (d != -1 and nd != d)
                cost = G + (turn_cost * G if turn else 0)
                if self._near_foreign(np_, net):
                    cost += near_cost * G
                if np_ in self.soft:
                    cost += 2 * G
                nst = (np_[0], np_[1], nd, 1 if (sens and nd == d) else 0)
                ng = g + cost
                if ng < best.get(nst, 1 << 30):
                    best[nst] = ng
                    prev[nst] = st
                    heapq.heappush(openq, (ng + h(np_) * 1.1, ng, nst))
        if goal_state is None:
            raise RouteError('не удалось развести цепь %s' % net)
        path = []
        st = goal_state
        while st is not None:
            path.append((st[0], st[1]))
            st = prev.get(st)
        return path[::-1]

    @staticmethod
    def _runs(path):
        """Ломаная -> максимальные прямые отрезки."""
        if len(path) < 2:
            return []
        runs = []
        start, d0 = path[0], None
        for i in range(1, len(path)):
            d = (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1])
            if d0 is not None and d != d0:
                runs.append((start, path[i - 1]))
                start = path[i - 1]
            d0 = d
        runs.append((start, path[-1]))
        return runs

    # ---------------------------------------------------------- разводка цепи
    def route(self, net, points, bus=False):
        points = list(dict.fromkeys(points))
        if len(points) == 1:
            return
        connected = [points[0]]
        rest = points[1:]
        while rest:
            # ближайшая нагрузка к уже разведённой части
            best = min(rest, key=lambda p: min(abs(p[0] - c[0]) + abs(p[1] - c[1])
                                               for c in connected))
            path = self.path(net, best, connected)
            for a, b in self._runs(path):
                if not self._edge_ok(a, b, net):
                    raise RouteError('КЗ при разводке %s: %s-%s' % (net, a, b))
                self.add_segment(a, b, net, bus)
            connected.extend(path)
            rest.remove(best)

    # ---------------------------------------------------------- поиск точки ответвления
    def free_spot_on(self, net, length=96):
        """Свободный участок провода цепи net (для подключения ответвления)."""
        for (a, b, n, bus) in sorted(self.segs, key=lambda s: -(
                abs(s[0][0] - s[1][0]) + abs(s[0][1] - s[1][1]))):
            if n != net:
                continue
            if a[1] == b[1] and abs(a[0] - b[0]) >= length:
                lo, hi = sorted((a[0], b[0]))
                for x in range(lo + G, hi - G + 1, G):
                    up, dn = (x, a[1] - G), (x, a[1] + G)
                    if not self._hard(up, net) and not self._sensitive(up, net):
                        return (x, a[1]), 'up'
                    if not self._hard(dn, net) and not self._sensitive(dn, net):
                        return (x, a[1]), 'down'
            if a[0] == b[0] and abs(a[1] - b[1]) >= length:
                lo, hi = sorted((a[1], b[1]))
                for y in range(lo + G, hi - G + 1, G):
                    lf, rt = (a[0] - G, y), (a[0] + G, y)
                    if not self._hard(lf, net) and not self._sensitive(lf, net):
                        return (a[0], y), 'left'
                    if not self._hard(rt, net) and not self._sensitive(rt, net):
                        return (a[0], y), 'right'
        return None, None

    # ---------------------------------------------------------- вывод в BDF
    def bdf_items(self):
        items = []
        for (a, b, net, bus) in self.segs:
            if (a, b) in self.hidden:
                continue
            items.append(['connector', ['pt', str(a[0]), str(a[1])],
                          ['pt', str(b[0]), str(b[1])]] + ([['bus']] if bus else []))
        return items

    def junctions(self):
        """Точки, где сходятся три и более проводников (для отрисовки, не для BDF)."""
        cnt = {}
        for (a, b, net, bus) in self.segs:
            for p in (a, b):
                cnt[p] = cnt.get(p, 0) + 1
        res = {p for p, c in cnt.items() if c >= 3}
        for p, c in cnt.items():
            if c >= 3:
                continue
            net = self.verts[p]
            for s in self.rows.get(p[1], []):
                if s[2] == net and s[0] < p[0] < s[1]:
                    res.add(p)
                    break
            else:
                for s in self.cols.get(p[0], []):
                    if s[2] == net and s[0] < p[1] < s[1]:
                        res.add(p)
                        break
        return res


def _floor(v):
    return (int(v) // G) * G


def _ceil(v):
    return -((-int(v)) // G) * G
