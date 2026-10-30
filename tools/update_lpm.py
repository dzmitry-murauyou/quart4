# -*- coding: utf-8 -*-
"""Приведение LPM-блоков к разрядностям варианта: ШД=6, ША=4, команда=8."""
import re, sys, pathlib

def sub_once(s, old, new, path, cnt=1):
    n = s.count(old)
    if n != cnt:
        raise SystemExit('%s: ожидалось %d вхождений %r, найдено %d' % (path, cnt, old, n))
    return s.replace(old, new)

def edit(path, pairs):
    p = pathlib.Path(path); s = p.read_text(encoding='utf-8', errors='replace')
    for old, new, cnt in pairs:
        s = sub_once(s, old, new, path, cnt)
    p.write_text(s, encoding='utf-8')

# ---------------- .v ----------------
edit('lpm_rom0.v', [
    ('input\t[5:0]  address;', 'input\t[3:0]  address;', 1),
    ('output\t[8:0]  q;', 'output\t[7:0]  q;', 1),
    ('wire [8:0] sub_wire0;', 'wire [7:0] sub_wire0;', 1),
    ('wire [8:0] q = sub_wire0[8:0];', 'wire [7:0] q = sub_wire0[7:0];', 1),
    ('.data_a ({9{1\'b1}})', '.data_a ({8{1\'b1}})', 1),
    ('numwords_a = 64', 'numwords_a = 16', 1),
    ('widthad_a = 6', 'widthad_a = 4', 1),
    ('width_a = 9', 'width_a = 8', 1),
])
edit('lpm_ram_dq0.v', [
    ('input\t[5:0]  address;', 'input\t[3:0]  address;', 1),
    ('input\t[8:0]  data;', 'input\t[5:0]  data;', 1),
    ('output\t[8:0]  q;', 'output\t[5:0]  q;', 1),
    ('wire [8:0] sub_wire0;', 'wire [5:0] sub_wire0;', 1),
    ('wire [8:0] q = sub_wire0[8:0];', 'wire [5:0] q = sub_wire0[5:0];', 1),
    ('numwords_a = 64', 'numwords_a = 16', 1),
    ('widthad_a = 6', 'widthad_a = 4', 1),
    ('width_a = 9', 'width_a = 6', 1),
])
edit('lpm_dff0.v', [
    ('input\t[8:0]  data;', 'input\t[7:0]  data;', 1),
    ('output\t[8:0]  q;', 'output\t[7:0]  q;', 1),
    ('wire [8:0] sub_wire0;', 'wire [7:0] sub_wire0;', 1),
    ('wire [8:0] q = sub_wire0[8:0];', 'wire [7:0] q = sub_wire0[7:0];', 1),
    ('lpm_width = 9', 'lpm_width = 8', 1),
])
edit('lpm_dff1.v', [
    ('input\t[5:0]  data;', 'input\t[3:0]  data;', 1),
    ('output\t[5:0]  q;', 'output\t[3:0]  q;', 1),
    ('wire [5:0] sub_wire0;', 'wire [3:0] sub_wire0;', 1),
    ('wire [5:0] q = sub_wire0[5:0];', 'wire [3:0] q = sub_wire0[3:0];', 1),
    ('lpm_width = 6', 'lpm_width = 4', 1),
])
edit('lpm_mux0.v', [
    ('input\t[8:0]  data0x;', 'input\t[5:0]  data0x;', 1),
    ('input\t[8:0]  data1x;', 'input\t[5:0]  data1x;', 1),
    ('input\t[8:0]  data2x;', 'input\t[5:0]  data2x;', 1),
    ('input\t[8:0]  data3x;', 'input\t[5:0]  data3x;', 1),
    ('output\t[8:0]  result;', 'output\t[5:0]  result;', 1),
    ('lpm_width = 9', 'lpm_width = 6', 1),
])
edit('lpm_mux1.v', [
    ('input\t[5:0]  data0x;', 'input\t[3:0]  data0x;', 1),
    ('input\t[5:0]  data1x;', 'input\t[3:0]  data1x;', 1),
    ('output\t[5:0]  result;', 'output\t[3:0]  result;', 1),
    ('lpm_width = 6', 'lpm_width = 4', 1),
])
edit('lpm_bustri0.v', [
    ('input\t[8:0]  data;', 'input\t[5:0]  data;', 1),
    ('inout\t[8:0]  tridata;', 'inout\t[5:0]  tridata;', 1),
    ('lpm_width = 9', 'lpm_width = 6', 1),
])
edit('lpm_add_sub0.v', [
    ('input\t[5:0]  dataa;', 'input\t[3:0]  dataa;', 1),
    ('input\t[5:0]  datab;', 'input\t[3:0]  datab;', 1),
    ('output\t[5:0]  result;', 'output\t[3:0]  result;', 1),
    ('lpm_width = 6', 'lpm_width = 4', 1),
])
edit('lpm_constant0.v', [
    ('output\t[5:0]  result;', 'output\t[3:0]  result;', 1),
    ('lpm_width = 6', 'lpm_width = 4', 1),
])
print('OK: .v обновлены')
