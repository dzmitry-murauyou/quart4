#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Рисует таблицы кода программы в стиле отчёта (как в методичке):
  1) Адрес ROM | Символьно | BIN (10 бит) | HEX
  2) побитовое поле команды: КОП(2) | ADR(6) | R(2)

Запуск:  python3 tools/make_code_table.py [выходной.png]
Результат по умолчанию: docs/img/code_table.png
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs/img/code_table.png")

F = "/usr/share/fonts/truetype/dejavu/"
F_REG = F + "DejaVuSans.ttf"
F_BOLD = F + "DejaVuSans-Bold.ttf"
F_MONO = F + "DejaVuSansMono.ttf"

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

# --- программа: (адрес, мнемоника, КОП(2 бита), ADR(6 бит), R(2 бита)) -----------------
PROGRAM = [
    ("00", "Mov ($4), R0", 0b01, 0b000100, 0b00),
    ("01", "JZ $3", 0b10, 0b000011, 0b00),
    ("02", "Mov ($5), R1", 0b01, 0b000101, 0b01),
    ("03", "Mov ($6), R2", 0b01, 0b000110, 0b10),
    ("04", "Mov ($7), R3", 0b01, 0b000111, 0b11),
    ("05", "JZ $0", 0b10, 0b000000, 0b00),
]

ROW_H = 40          # высота строки данных
HDR_H = 44          # высота строки заголовка
MARGIN = 24         # поля картинки
GAP = 44            # промежуток между таблицами


def word(kop, adr, r):
    return (kop << 8) | (adr << 2) | r


def bits(value, n):
    return format(value, "0%db" % n)


def fit(draw, text, font, width, pad=10):
    """Уменьшает шрифт, если текст не влезает в ячейку."""
    size = font.size
    while draw.textlength(text, font=font) > width - pad and size > 8:
        size -= 1
        fname = F_MONO if "Mono" in font.path else (F_BOLD if "Bold" in font.path else F_REG)
        font = ImageFont.truetype(fname, size)
    return font


class Table:
    """Простая таблица с объединёнными ячейками заголовка."""

    def __init__(self, cols, rows_i, rows_h, hdr_height, row_height):
        self.cols = cols                # список ширин колонок
        self.pad_x = 10
        self.rows_i = rows_i            # [(col, span, text, font_kind)]
        self.rows_h = rows_h            # [[(text, font_kind), ...], ...]
        self.hdr_height = hdr_height
        self.row_height = row_height

    @property
    def width(self):
        return sum(self.cols)

    @property
    def height(self):
        return self.hdr_height + self.row_height * len(self.rows_h)

    def draw(self, draw, x0, y0):
        cols = self.cols
        xs = [x0]
        for w in cols:
            xs.append(xs[-1] + w)
        # горизонтальные линии
        ys = [y0, y0 + self.hdr_height]
        for _ in self.rows_h:
            ys.append(ys[-1] + self.row_height)
        for y in ys:
            draw.line([(x0, y), (x0 + self.width, y)], fill=BLACK, width=2)
        # вертикальные линии сетки заголовка (с учётом объединений)
        for x in xs:
            draw.line([(x, y0), (x, ys[1])], fill=BLACK, width=2)
        # затираем внутренние границы объединённых ячеек заголовка
        cx = x0
        for col, span, text, kind in self.rows_i:
            x1 = xs[col]
            x2 = xs[col + span]
            if span > 1:
                for x in xs[col + 1:col + span]:
                    draw.line([(x, y0 + 1), (x, ys[1] - 1)], fill=WHITE, width=2)
            font = ImageFont.truetype(BOLD if kind == "b" else (MONO if kind == "m" else REG), 16)
            font = fit(draw, text, font, x2 - x1)
            tw = draw.textlength(text, font=font)
            asc, desc = font.getmetrics()
            draw.text(((x1 + x2 - tw) / 2, y0 + (self.hdr_height - asc - desc) / 2),
                      text, font=font, fill=BLACK)
        # вертикальные линии строк данных
        for x in xs:
            draw.line([(x, ys[1]), (x, ys[-1])], fill=BLACK, width=2)
        for i, row in enumerate(self.rows_h):
            y = ys[1 + i]
            for j, (text, kind) in enumerate(row):
                x1, x2 = xs[j], xs[j + 1]
                font = ImageFont.truetype(BOLD if kind == "b" else (MONO if kind == "m" else REG), 16)
                font = fit(draw, text, font, x2 - x1)
                tw = draw.textlength(text, font=font)
                asc, desc = font.getmetrics()
                draw.text(((x1 + x2 - tw) / 2, y + (self.row_height - asc - desc) / 2),
                          text, font=font, fill=BLACK)


REG = F_REG
BOLD = F_BOLD
MONO = F_MONO


def main():
    # ---------- таблица 1: адрес / символьно / BIN / HEX ----------
    t1 = Table(
        cols=[150, 330, 260, 120],
        rows_i=[(0, 1, "Адрес ROM", "b"), (1, 1, "Символьно", "b"),
                (2, 1, "BIN (10 бит)", "b"), (3, 1, "HEX", "b")],
        rows_h=[],
        hdr_height=HDR_H,
        row_height=ROW_H,
    )
    for addr, mnem, kop, adr, r in PROGRAM:
        code = word(kop, adr, r)
        t1.rows_h.append([(addr, "m"), (mnem, "r"),
                          (bits(code, 10), "m"), ("%03X" % code, "m")])

    # ---------- таблица 2: побитовое поле ----------
    bit_w = 40
    t2 = Table(
        cols=[150] + [bit_w] * 10,
        rows_i=[(0, 1, "Адрес ROM", "b"), (1, 2, "КОП (2 бита)", "b"),
                (3, 6, "ADR (6 бит)", "b"), (9, 2, "R (2 бита)", "b")],
        rows_h=[],
        hdr_height=HDR_H,
        row_height=ROW_H,
    )
    for addr, mnem, kop, adr, r in PROGRAM:
        row = [(addr, "m")]
        row += [(b, "m") for b in bits(kop, 2)]
        row += [(b, "m") for b in bits(adr, 6)]
        row += [(b, "m") for b in bits(r, 2)]
        t2.rows_h.append(row)

    W = max(t1.width, t2.width) + 2 * MARGIN
    H = MARGIN + t1.height + GAP + t2.height + MARGIN
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    t1.draw(d, (W - t1.width) // 2, MARGIN)
    t2.draw(d, (W - t2.width) // 2, MARGIN + t1.height + GAP)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT)
    print("сохранено: %s (%dx%d)" % (os.path.relpath(OUT, ROOT), W, H))
    for addr, mnem, kop, adr, r in PROGRAM:
        code = word(kop, adr, r)
        print("  %s  %-14s %s  %03X" % (addr, mnem, bits(code, 10), code))


if __name__ == "__main__":
    main()
