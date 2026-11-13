# -*- coding: utf-8 -*-
"""Генерация файлов временных диаграмм (.vwf) для функционального моделирования.

Формат повторяет то, что пишет сам Quartus II 9.1 (см. исходный lab4.vwf проекта):

  * шина описывается ДВУМЯ видами строк:
        SIGNAL("adr_out")     SIGNAL_TYPE = BUS;        WIDTH = 6; LSB_INDEX = 0;
        SIGNAL("adr_out[5]")  SIGNAL_TYPE = SINGLE_BIT; PARENT = "adr_out";
  * список переходов (TRANSITION_LIST) есть у КАЖДОГО разряда, а у строки-шины
    его НЕТ.

Если сделать иначе (имя шины с диапазоном `adr_out[5..0]` и список переходов
только у неё, без списков у разрядов), quartus_sim.exe падает с
`Fatal Error ... VDB_VALUE_BUS::is_homogenous (db_vdb)` — база значений шины
собирается из разрядов без данных и получается «неоднородной».

`lab4.vwf`      — шины + разряды (как в Quartus);
`lab4_bits.vwf` — только отдельные разряды, без строк-шин (страховка: в этом
                  файле шинных значений нет вообще, багу не на чем сработать).
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

HDR = '''/*
Copyright (C) 1991-2009 Altera Corporation
Your use of Altera Corporation's design tools, logic functions 
and other software and tools, and its AMPP partner logic 
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

HEADER
{
\tVERSION = 1;
\tTIME_UNIT = ns;
\tDATA_OFFSET = 0.0;
\tDATA_DURATION = %(dur)s;
\tSIMULATION_TIME = 0.0;
\tGRID_PHASE = 0.0;
\tGRID_PERIOD = 100.0;
\tGRID_DUTY_CYCLE = 50;
}
'''

CLK_HALF = 100.0     # полпериода синхросигнала, нс
CLK_NUM = 64         # число периодов синхронизации (один такт = 1 период)

# (имя вывода верхнего уровня, разрядность, направление)
SIGNALS = [
    ('clk', 1, 'INPUT'),
    ('adr_out[5..0]', 6, 'OUTPUT'),
    ('data_out[3..0]', 4, 'OUTPUT'),
    ('ir_out[8..0]', 9, 'OUTPUT'),
    ('T_out[2..0]', 3, 'OUTPUT'),
    ('flag_out', 1, 'OUTPUT'),
    ('rom_data_out[8..0]', 9, 'OUTPUT'),
    ('ram_en_out', 1, 'OUTPUT'),
    ('ram_wr_out', 1, 'OUTPUT'),
    ('ron_wr_out', 1, 'OUTPUT'),
    ('ron_rd_out', 1, 'OUTPUT'),
    ('ron_addr_out[1..0]', 2, 'OUTPUT'),
]

SIG = ('SIGNAL("%(name)s")\n{\n\tVALUE_TYPE = NINE_LEVEL_BIT;\n'
       '\tSIGNAL_TYPE = %(type)s;\n\tWIDTH = %(w)d;\n\tLSB_INDEX = %(lsb)d;\n'
       '\tDIRECTION = %(dir)s;\n\tPARENT = "%(parent)s";\n}\n')

CLK_LIST = ('TRANSITION_LIST("clk")\n{\n\tNODE\n\t{\n\t\tREPEAT = %d;\n'
            '\t\tLEVEL 0 FOR %.1f;\n\t\tLEVEL 1 FOR %.1f;\n\t}\n}\n')

X_LIST = ('TRANSITION_LIST("%s")\n{\n\tNODE\n\t{\n\t\tREPEAT = 1;\n'
          '\t\tLEVEL X FOR %.1f;\n\t}\n}\n')


def parse(name):
    """'adr_out[5..0]' -> ('adr_out', [5, 4, 3, 2, 1, 0])"""
    if '[' not in name:
        return name, []
    base, rng = name.split('[')
    msb, lsb = rng.rstrip(']').split('..')
    return base, list(range(int(msb), int(lsb) - 1, -1))


def build(bits_only=False):
    dur = CLK_HALF * 2 * CLK_NUM
    decls, lists = [], []
    for name, w, d in SIGNALS:
        base, bits = parse(name)
        if w == 1:
            decls.append(SIG % dict(name=name, type='SINGLE_BIT', w=1, lsb=-1,
                                    dir=d, parent=''))
            lists.append(CLK_LIST % (CLK_NUM, CLK_HALF, CLK_HALF) if name == 'clk'
                         else X_LIST % (name, dur))
            continue
        if not bits_only:                        # строка-шина без списка переходов
            decls.append(SIG % dict(name=base, type='BUS', w=w, lsb=0,
                                    dir=d, parent=''))
        for i in bits:                           # разряды: свой PARENT и свой список
            decls.append(SIG % dict(name='%s[%d]' % (base, i), type='SINGLE_BIT',
                                    w=1, lsb=-1, dir=d,
                                    parent='' if bits_only else base))
            lists.append(X_LIST % ('%s[%d]' % (base, i), dur))
    return (HDR % {'dur': '%.1f' % dur}) + '\n' + '\n'.join(decls) + '\n' + '\n'.join(lists), dur


def main():
    text, dur = build(False)
    (ROOT / 'lab4.vwf').write_text(text, encoding='utf-8')
    print('lab4.vwf: %.0f нс, %d тактов (шины + разряды)' % (dur, CLK_NUM))
    text, dur = build(True)
    (ROOT / 'lab4_bits.vwf').write_text(text, encoding='utf-8')
    print('lab4_bits.vwf: %.0f нс, только разряды (страховка от бага VDB)' % dur)


if __name__ == '__main__':
    main()
