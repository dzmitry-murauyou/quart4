#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Рисует таблицу «что происходит по тактам» (по данным модели tools/sim.py).

Блоки:
  1) MOV M[4], R0  — команда из адреса 00, такты T0…T5;
  2) JZ $3         — адрес 01, Z = 0 (перехода нет);
  3) JZ $0         — адрес 05, Z = 1 (переход есть);
  4) сводка по всему циклу программы.

Запуск:  python3 tools/make_timing_table.py [выходной.png]
Результат по умолчанию: docs/img/timing_table.png
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sim import CPU, disasm          # циклическая модель процессора

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs/img/timing_table.png")

F = "/usr/share/fonts/truetype/dejavu/"
F_REG = F + "DejaVuSans.ttf"
F_BOLD = F + "DejaVuSans-Bold.ttf"
F_MONO = F + "DejaVuSansMono.ttf"

BLACK = (0, 0, 0)
GREY = (120, 120, 120)

ROW_H = 40
HDR_H = 44
TITLE_H = 42
TICKS = 6                      # тактов на команду: T0…T5
MARGIN = 24
GAP = 36

COLS = [                       # (заголовок, ширина)
    ("Такт", 74),
    ("ША  adr_out", 128),
    ("IR  ir_out", 128),
    ("ШД  data_out", 148),
    ("Z", 52),
    ("Управляющие сигналы", 344),
    ("Что происходит", 560),
]

SIG = {                        # имена сигналов в схеме -> подпись в таблице
    'ir_ld': 'ir_ld',
    'ip_cnt': 'ip_cnt (IP+1)',
    'ip_ld_jmp': 'ip_jump',
    'ar_ld': 'ar_ld',
    'sha_ar': 'sel_sha (ША←AR)',
    'ram_en': 'ram_en',
    'dr_ld': 'dr_ld',
    'dr_out': 'dr_out',
    'ron_wr': 'ron_wr',
    'fr_ld': 'fr_ld',
}


def font(path, size):
    return ImageFont.truetype(path, size)


def fit(draw, text, path, size, width, pad=12):
    f = font(path, size)
    while draw.textlength(text, font=f) > width - pad and size > 8:
        size -= 1
        f = font(path, size)
    return f


def hexb(v, n):
    return format(v, "0%dX" % n)


# ------------------------------------------------------------------ данные модели
def collect():
    """Прогон модели: 6 команд по 6 тактов = полный цикл программы."""
    cpu = CPU()
    ticks = [cpu.step() for _ in range(TICKS * 6)]
    cmd = []                    # (адрес команды, слово, такты)
    for k in range(0, len(ticks), TICKS):
        blk = ticks[k:k + TICKS]
        # слово команды появляется в IR на такте T2 (защёлкнуто в конце T1)
        word = blk[2]['IR'] if len(blk) > 2 else blk[0]['IR']
        cmd.append((blk[0]['IP'], word, blk))      # адрес команды = IP в такте T0
    return ticks, cmd


def action(cmd_word, t, st):
    """Текст «что происходит» для конкретного такта."""
    mov = ((cmd_word >> 8) & 1) == 0
    adr = cmd_word & 0x3F
    rsel = (cmd_word >> 6) & 3
    if t == 0:
        return "ША ← IP; ROM принимает адрес команды"
    if t == 1:
        return "IR ← ROM[IP]; IP ← IP + 1"
    if mov:
        if t == 2:
            return "AR ← IR[5..0] — прямой адрес операнда"
        if t == 3:
            return "ША ← AR; RAM принимает адрес ячейки M[%X]" % adr
        if t == 4:
            return "данные RAM[%X] на ШД; DR ← ШД" % adr
        return "DR → ШД; R%d ← ШД; FR.Z ← (DR = 0)" % rsel
    if t == 2:
        return "декодирование: mov = ~IR[8] = 0"
    if t == 3:
        if st['Z']:
            return "Z = 1 → IP ← IR[5..0] = %X (переход)" % adr
        return "Z = 0 → перехода нет, IP остаётся IP+1"
    return "— (JZ эти такты не использует)"


def rows_for(block):
    out = []
    for st in block:
        ctl = [SIG[k] for k, v in st['ctl'].items() if v]
        out.append([
            "T%d" % st['T'],
            "0x" + hexb(st['sha'], 2),
            "0x" + hexb(st['IR'], 3),
            "ZZZZ" if st['bus'] is None else "0x%X" % st['bus'],
            str(st['Z']),
            ", ".join(ctl) if ctl else "—",
            action(st['IR'], st['T'], st),
        ])
    return out


def cpu_after(st):
    """Флаг Z после такта: записывается в конце T4 команды MOV."""
    return 1 if st['DR'] == 0 else 0


def summary(cmd):
    rows = []
    for adr, word, blk in cmd:
        mov = ((word >> 8) & 1) == 0
        if mov:
            rows.append(["0x" + hexb(adr, 2), disasm(word),
                         "0x%02X" % blk[3]['sha'],
                         "0x%X" % blk[4]['bus'],
                         "R%d ← 0x%X" % ((word >> 6) & 3, blk[5]['bus']),
                         "Z = %d" % (0 if blk[5]['DR'] else 1)])
        else:
            jump = blk[3]['ctl']['ip_ld_jmp']
            rows.append(["0x" + hexb(adr, 2), disasm(word), "—", "—",
                         "IP ← 0x%02X" % blk[4]['IP'] if jump else "перехода нет",
                         "Z = %d" % blk[3]['Z']])
    return rows


SUMMARY_COLS = [("Адрес", 90), ("Команда", 200), ("T3: ША (адрес RAM)", 190),
                ("T4: ШД (данные)", 170), ("Запись в РОН", 190),
                ("Флаг после", 150)]


# ------------------------------------------------------------------ рисование
def draw_table(d, x, y, title, cols, rows):
    """Рисует заголовок блока и таблицу; возвращает y после таблицы."""
    f_title = font(F_BOLD, 20)
    d.text((x, y), title, font=f_title, fill=BLACK)
    y += TITLE_H
    # шапка
    cx = x
    f_hdr = font(F_BOLD, 15)
    for name, w in cols:
        d.rectangle([cx, y, cx + w, y + HDR_H], outline=BLACK, width=1)
        f = fit(d, name, F_BOLD, 15, w)
        d.text((cx + 8, y + 13), name, font=f, fill=BLACK)
        cx += w
    y += HDR_H
    for row in rows:
        cx = x
        for (name, w), val in zip(cols, row):
            d.rectangle([cx, y, cx + w, y + ROW_H], outline=BLACK, width=1)
            mono = val.startswith("0x") or val in ("ZZZZ", "—") or val.startswith("T")
            path = F_MONO if mono else F_REG
            f = fit(d, val, path, 15, w)
            d.text((cx + 8, y + 12), val, font=f, fill=BLACK)
            cx += w
        y += ROW_H
    return y


def main():
    ticks, cmd = collect()
    W = MARGIN * 2 + sum(w for _, w in COLS)
    blocks = []
    for adr, word, blk in cmd[:2] + cmd[5:]:
        kind = "MOV M → R, прямая адресация" if ((word >> 8) & 1) == 0 else \
               "JZ, непосредственная адресация"
        blocks.append(("Команда 0x%02X — %s (%s)" % (adr, disasm(word), kind),
                       COLS, rows_for(blk)))
    blocks.append(("Весь цикл программы (6 команд × 6 тактов)", SUMMARY_COLS,
                   summary(cmd)))

    H = MARGIN * 2 + sum(TITLE_H + HDR_H + ROW_H * len(r) + GAP
                         for _, _, r in blocks)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    y = MARGIN
    for title, cols, rows in blocks:
        y = draw_table(d, MARGIN, y, title, cols, rows) + GAP
    img.save(OUT)
    print("%s: %dx%d" % (OUT, W, H))


if __name__ == "__main__":
    main()
