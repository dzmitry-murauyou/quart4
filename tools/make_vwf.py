# -*- coding: utf-8 -*-
"""Генерация файла временных диаграмм (.vwf) для функционального моделирования."""
import math, pathlib

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
	VERSION = 1;
	TIME_UNIT = ns;
	DATA_OFFSET = 0.0;
	DATA_DURATION = %(dur)s;
	SIMULATION_TIME = 0.0;
	GRID_PHASE = 0.0;
	GRID_PERIOD = 100.0;
	GRID_DUTY_CYCLE = 50;
}
'''

CLK_HALF = 100.0     # полпериода синхросигнала, нс
CLK_NUM = 64         # число периодов синхронизации

SIGNALS = [
    ('clk', 1, 'INPUT'),
    ('adr_out[3..0]', 4, 'OUTPUT'),
    ('data_out[5..0]', 6, 'OUTPUT'),
    ('ir_out[7..0]', 8, 'OUTPUT'),
    ('T_out[2..0]', 3, 'OUTPUT'),
    ('flag_out', 1, 'OUTPUT'),
    ('rom_data_out[7..0]', 8, 'OUTPUT'),
    ('ram_en_out', 1, 'OUTPUT'),
    ('ram_wr_out', 1, 'OUTPUT'),
    ('ron_wr_out', 1, 'OUTPUT'),
    ('ron_rd_out', 1, 'OUTPUT'),
    ('ron_addr_out[1..0]', 2, 'OUTPUT'),
]


def sig_block(name, width, direction):
    bus = width > 1
    short = name.split('[')[0]
    w = width
    return ('SIGNAL("%s")\n{\n\tVALUE_TYPE = NINE_LEVEL_BIT;\n\tSIGNAL_TYPE = %s;\n'
            '\tWIDTH = %d;\n\tLSB_INDEX = %d;\n\tDIRECTION = %s;\n\tPARENT = "%s";\n}\n') % (
        name, 'BUS' if bus else 'SINGLE_BIT', w, 0 if bus else -1, direction,
        '' if bus else '')


def sig_bits(name, width, direction):
    out = []
    if width == 1:
        return out
    short = name.split('[')[0]
    for i in range(width - 1, -1, -1):
        out.append(('SIGNAL("%s[%d]")\n{\n\tVALUE_TYPE = NINE_LEVEL_BIT;\n'
                    '\tSIGNAL_TYPE = SINGLE_BIT;\n\tWIDTH = 1;\n\tLSB_INDEX = -1;\n'
                    '\tDIRECTION = %s;\n\tPARENT = "%s";\n}\n') % (short, i, direction, short))
    return out


def main():
    dur = CLK_HALF * 2 * CLK_NUM
    text = HDR % {'dur': '%.1f' % dur}
    for name, w, d in SIGNALS:
        text += '\n' + sig_block(name, w, d)
        for b in sig_bits(name, w, d):
            text += '\n' + b
    # стимулы
    for name, w, d in SIGNALS:
        short = name.split('[')[0]
        if name == 'clk':
            text += ('\nTRANSITION_LIST("clk")\n{\n\tNODE\n\t{\n\t\tREPEAT = %d;\n'
                     '\t\tLEVEL 0 FOR %.1f;\n\t\tLEVEL 1 FOR %.1f;\n\t}\n}\n') % (
                CLK_NUM, CLK_HALF, CLK_HALF)
            continue
        entries = [(name)] + [('%s[%d]' % (short, i)) for i in range(w - 1, -1, -1)] if w > 1 else [name]
        for e in entries:
            text += ('\nTRANSITION_LIST("%s")\n{\n\tNODE\n\t{\n\t\tREPEAT = 1;\n'
                     '\t\tLEVEL X FOR %.1f;\n\t}\n}\n') % (e, dur)
    (ROOT / 'lab4.vwf').write_text(text, encoding='utf-8')
    print('lab4.vwf: %.0f нс, %d периодов clk' % (dur, CLK_NUM))


if __name__ == '__main__':
    main()
