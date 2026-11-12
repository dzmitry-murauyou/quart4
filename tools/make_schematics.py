# -*- coding: utf-8 -*-
"""Сборка схем проекта: rom.bdf, ram.bdf, ron.bdf, uu.bdf, laba4.bdf + символы.

Все соединения выполняются настоящими проводниками (элемент connector),
прокладываемыми автоматически (tools/router.py). Имена цепей остаются только
на ответвлениях от шин (ir[5..2], dr[3] и т.п.), где иначе разрядность
не указать.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bdfgen as B

ROOT = B.ROOT
PRIM = 'uu.bdf'          # файл-источник шаблонов примитивов (перезаписывается позже)
SRC_PRIM = 'laba4.bdf'   # примитивы берём из файла, который не перезаписываем первым


def P(name):
    return B.load_prim(name, SRC_PRIM if _has(SRC_PRIM, name) else PRIM)


def _has(fn, name):
    txt = (ROOT / fn).read_text(encoding='utf-8')
    return ('text "%s"' % name) in txt


# ------------------------------------------------------------ выводы
def inp(s, name, net, cx, cy):
    """Входной вывод: точка подключения (cx, cy)."""
    return s.pin(name, 'input', net, cx - 168, cy - 8)


def outp(s, name, net, cx, cy):
    return s.pin(name, 'output', net, cx, cy - 8)


def bidir(s, name, net, cx, cy):
    return s.pin(name, 'bidir', net, cx, cy - 8)


# ------------------------------------------------------------ .bsf символы
def write_bsf(fname, title, ports):
    """ports: [(имя, направление)] — входы слева, выходы/bidir справа."""
    left = [p for p in ports if p[1] == 'input']
    right = [p for p in ports if p[1] != 'input']
    W = 240
    H = max(len(left), len(right)) * 24 + 40
    items = []
    items.append(['rect', '0', '0', str(W), str(H)])
    items.append(['text', '"%s"' % title,
                  ['rect', '60', '2', str(60 + 9 * len(title)), '18'],
                  ['font', '"Arial"', ['font_size', '10']]])
    items.append(['text', '"inst"', ['rect', '8', str(H - 20), '30', str(H - 8)],
                  ['font', '"Arial"']])
    for i, (name, d) in enumerate(left):
        name = B.norm(name)
        y = 32 + i * 24
        w = 9 * len(name)
        items.append(['port', ['pt', '0', str(y)], ['input'],
                      ['text', '"%s"' % name, ['rect', '0', '0', str(w), '14'],
                       ['font', '"Arial"', ['font_size', '8']]],
                      ['text', '"%s"' % name, ['rect', '22', str(y - 13), str(22 + w), str(y)],
                       ['font', '"Arial"', ['font_size', '8']]],
                      ['line', ['pt', '0', str(y)], ['pt', '16', str(y)],
                       ['line_width', '3' if '[' in name else '1']]])
    for i, (name, d) in enumerate(right):
        name = B.norm(name)
        y = 32 + i * 24
        w = 9 * len(name)
        items.append(['port', ['pt', str(W), str(y)], [d],
                      ['text', '"%s"' % name, ['rect', '0', '0', str(w), '14'],
                       ['font', '"Arial"', ['font_size', '8']]],
                      ['text', '"%s"' % name, ['rect', str(W - 22 - w), str(y - 13), str(W - 22), str(y)],
                       ['font', '"Arial"', ['font_size', '8']]],
                      ['line', ['pt', str(W), str(y)], ['pt', str(W - 16), str(y)],
                       ['line_width', '3' if '[' in name else '1']]])
    draw = ['drawing',
            ['line', ['pt', '16', '16'], ['pt', '16', str(H - 16)], ['line_width', '1']],
            ['line', ['pt', '16', str(H - 16)], ['pt', str(W - 16), str(H - 16)], ['line_width', '1']],
            ['line', ['pt', str(W - 16), str(H - 16)], ['pt', str(W - 16), '16'], ['line_width', '1']],
            ['line', ['pt', str(W - 16), '16'], ['pt', '16', '16'], ['line_width', '1']]]
    items.append(draw)
    body = B.dump(['symbol'] + items)
    (ROOT / fname).write_text(B.HDR_SYMBOL + '\n' + body + '\n', encoding='utf-8')


# ------------------------------------------------------------ rom.bdf
def make_rom():
    s = B.Sch()
    rom = B.load_bsf('lpm_rom0.bsf')
    inp(s, 'address[5:0]', 'address[5:0]', 360, 160)
    inp(s, 'clock', 'clk', 360, 392)
    outp(s, 'q[9:0]', 'rom_q[9:0]', 1000, 168)
    s.inst(rom, 'inst', 600, 128,
           {'address[5:0]': 'address[5:0]', 'clock': 'clk', 'q[9:0]': 'rom_q[9:0]'})
    s.note('ROM: 64 x 10, init file rom.mif', 200, 40)
    s.connect().save('rom.bdf')


# ------------------------------------------------------------ ram.bdf
def make_ram():
    s = B.Sch()
    ram = B.load_bsf('lpm_ram_dq0.bsf')
    buf = B.load_bsf('lpm_bustri0.bsf')
    inp(s, 'address[5:0]', 'address[5:0]', 360, 224)
    inp(s, 'data_in[3:0]', 'ram_d[3:0]', 360, 176)
    inp(s, 'wren', 'ram_wr', 360, 488)
    inp(s, 'enable', 'ram_en', 360, 648)
    inp(s, 'clock', 'clk', 360, 768)
    outp(s, 'data_out[3:0]', 'data_out[3:0]', 1064, 584)
    s.inst(ram, 'inst', 600, 160,
           {'address[5:0]': 'address[5:0]', 'data[3:0]': 'ram_d[3:0]',
            'wren': 'ram_wr', 'clock': 'clk', 'q[3:0]': 'ram_q[3:0]'})
    s.inst(buf, 'inst1', 880, 560,
           {'enabledt': 'ram_en', 'data[3:0]': 'ram_q[3:0]',
            'tridata[3:0]': 'data_out[3:0]'})
    s.note('RAM: 64 x 4, init file ram.mif', 200, 40)
    s.connect().save('ram.bdf')


# ------------------------------------------------------------ ron.bdf
def make_ron():
    s = B.Sch()
    dff = B.load_bsf('lpm_dff2.bsf')       # 6 бит
    dec = B.load_bsf('lpm_decode0.bsf')    # 2 -> 4
    mux = B.load_bsf('lpm_mux0.bsf')       # 4:1, 6 бит
    buf = B.load_bsf('lpm_bustri0.bsf')
    inp(s, 'clk', 'clk', 360, 104)
    inp(s, 'data_input[3:0]', 'ron_d[3:0]', 360, 248)
    inp(s, 'address[1:0]', 'ron_a[1:0]', 360, 408)
    inp(s, 'write', 'write', 360, 808)
    inp(s, 'read', 'read', 360, 1008)
    outp(s, 'data_output[3:0]', 'data_output[3:0]', 1360, 624)
    s.inst(dec, 'dec', 400, 760,
           {'data[1..0]': 'ron_a[1:0]', 'enable': 'write',
            'eq0': 'we0', 'eq1': 'we1', 'eq2': 'we2', 'eq3': 'we3'})
    for i in range(4):
        s.inst(dff, 'r%d' % i, 640, 96 + i * 160,
               {'data[3..0]': 'ron_d[3:0]', 'clock': 'clk', 'enable': 'we%d' % i,
                'q[3..0]': 'r%d[3..0]' % i})
    s.inst(mux, 'mux', 960, 224,
           {'data0x[3..0]': 'r0[3..0]', 'data1x[3..0]': 'r1[3..0]',
            'data2x[3..0]': 'r2[3..0]', 'data3x[3..0]': 'r3[3..0]',
            'sel[1..0]': 'ron_a[1..0]', 'result[3..0]': 'ron_mux[3..0]'})
    s.inst(buf, 'buf', 1180, 600,
           {'enabledt': 'read', 'data[3..0]': 'ron_mux[3..0]',
            'tridata[3..0]': 'data_output[3..0]'})
    s.note('RON: registers R0..R3, 4 bit each', 200, 40)
    s.connect().save('ron.bdf')


# ------------------------------------------------------------ uu.bdf
def make_uu():
    s = B.Sch()
    cnt = B.load_bsf('lpm_counter0.bsf')   # 3 бита, счётчик тактов
    dec = B.load_bsf('lpm_decode1.bsf')    # 3 -> 8
    ir_b = B.load_bsf('lpm_dff0.bsf')      # 10 бит (IR)
    reg6 = B.load_bsf('lpm_dff1.bsf')      # 6 бит (AR, IP)
    dr_b = B.load_bsf('lpm_dff2.bsf')      # 4 бита (DR, РОН)
    fr_b = B.load_bsf('lpm_dff3.bsf')      # 1 бит
    add = B.load_bsf('lpm_add_sub0.bsf')   # 6 бит
    one = B.load_bsf('lpm_constant0.bsf')  # 6 бит, значение 1
    mux = B.load_bsf('lpm_mux1.bsf')       # 2:1, 6 бит
    buf = B.load_bsf('lpm_bustri0.bsf')    # 4 бита
    notg, andg, org, gnd = P('NOT'), P('AND2'), P('OR2'), P('GND')

    # ---- выводы блока
    inp(s, 'clk', 'clk', 360, 72)
    inp(s, 'rom_data[9:0]', 'rom_data[9:0]', 360, 296)
    bidir(s, 'data_io[3:0]', 'data_io[3:0]', 1900, 664)
    outp(s, 'address[5:0]', 'address[5:0]', 1900, 488)
    outp(s, 'ir_out[9:0]', 'ir[9:0]', 1900, 328)
    outp(s, 'T_out[2:0]', 'T[2:0]', 1900, 104)
    outp(s, 'flag_out', 'z', 1900, 248)
    outp(s, 'ron_addr[1:0]', 'ir[1..0]', 1900, 1136)
    outp(s, 'ron_wr', 'mov_t4', 1900, 1264)
    outp(s, 'ron_rd', 'gnd_net', 1900, 1392)
    outp(s, 'ram_en', 'mov_t3', 1900, 1520)
    outp(s, 'ram_wr', 'gnd_net', 1900, 1648)

    # ---- регистры и счётчик тактов
    s.inst(cnt, 'T_cnt', 456, 64, {'clock': 'clk', 'q[2:0]': 'T[2:0]'})
    s.inst(dec, 'T_dec', 760, 32,
           {'data[2..0]': 'T[2:0]', 'eq1': 't1', 'eq2': 't2', 'eq3': 't3',
            'eq4': 't4'})
    s.inst(ir_b, 'IR_reg', 456, 272,
           {'data[9..0]': 'rom_data[9:0]', 'clock': 'clk', 'enable': 't1',
            'q[9..0]': 'ir[9..0]'})
    s.inst(reg6, 'AR_reg', 456, 456,
           {'data[5..0]': 'ir[7..2]', 'clock': 'clk', 'enable': 'mov_t2',
            'q[5..0]': 'ar[5:0]'})
    s.inst(dr_b, 'DR_reg', 456, 640,
           {'data[3..0]': 'data_io[3:0]', 'clock': 'clk', 'enable': 'mov_t3',
            'q[3..0]': 'dr[3:0]'})
    s.inst(reg6, 'IP_reg', 456, 820,
           {'data[5..0]': 'ip_next[5:0]', 'clock': 'clk', 'enable': 'ip_en',
            'q[5..0]': 'ip[5:0]'})
    s.inst(add, 'IP_inc', 456, 1000,
           {'dataa[5..0]': 'ip[5:0]', 'datab[5..0]': 'one[5:0]',
            'result[5..0]': 'ip_plus1[5:0]'})
    s.inst(one, 'const1', 240, 1000, {'result[5..0]': 'one[5:0]'})
    s.inst(mux, 'IP_mux', 940, 820,
           {'data0x[5..0]': 'ip_plus1[5:0]', 'data1x[5..0]': 'ir[7..2]',
            'sel': 'ip_jump', 'result[5..0]': 'ip_next[5:0]'})
    s.inst(mux, 'SHA_mux', 940, 440,
           {'data0x[5..0]': 'ip[5:0]', 'data1x[5..0]': 'ar[5:0]',
            'sel': 'mov_t3', 'result[5..0]': 'address[5:0]'})
    s.inst(buf, 'DR_buf', 1240, 640,
           {'enabledt': 'mov_t4', 'data[3..0]': 'dr[3:0]',
            'tridata[3..0]': 'data_io[3:0]'})
    s.inst(fr_b, 'FR', 1260, 200,
           {'data': 'z_d', 'clock': 'clk', 'enable': 'mov_t4', 'q': 'z'})

    # ---- управляющая логика (КОП = IR[9..8])
    s.inst(notg, 'n_ir9', 456, 1400, {'IN': 'ir[9]', 'OUT': 'n_ir9'})
    s.inst(andg, 'is_mov', 560, 1400, {'IN1': 'ir[8]', 'IN2': 'n_ir9', 'OUT': 'is_mov'})
    s.inst(org, 'jcond', 700, 1400, {'IN1': 'ir[8]', 'IN2': 'z', 'OUT': 'jcond'})
    s.inst(andg, 'jump', 840, 1400, {'IN1': 'ir[9]', 'IN2': 'jcond', 'OUT': 'jump'})
    s.inst(andg, 'mov_t2', 980, 1400, {'IN1': 't2', 'IN2': 'is_mov', 'OUT': 'mov_t2'})
    s.inst(andg, 'mov_t3', 1120, 1400, {'IN1': 't3', 'IN2': 'is_mov', 'OUT': 'mov_t3'})
    s.inst(andg, 'mov_t4', 1260, 1400, {'IN1': 't4', 'IN2': 'is_mov', 'OUT': 'mov_t4'})
    s.inst(andg, 'ip_jmp', 1400, 1400, {'IN1': 't3', 'IN2': 'jump', 'OUT': 'ip_jump'})
    s.inst(org, 'ip_en', 1540, 1400, {'IN1': 't1', 'IN2': 'ip_jump', 'OUT': 'ip_en'})
    # флаг нуля: z_d = ~(dr[3] | dr[2] | dr[1] | dr[0])
    s.inst(org, 'o1', 560, 1620, {'IN1': 'dr[0]', 'IN2': 'dr[1]', 'OUT': 'o1'})
    s.inst(org, 'o2', 700, 1620, {'IN1': 'dr[2]', 'IN2': 'dr[3]', 'OUT': 'o2'})
    s.inst(org, 'o3', 840, 1620, {'IN1': 'o1', 'IN2': 'o2', 'OUT': 'o3'})
    s.inst(notg, 'nz', 980, 1620, {'IN': 'o3', 'OUT': 'z_d'})
    # константа 0 для неиспользуемых в данном варианте управляющих сигналов
    s.inst(gnd, 'gnd0', 1400, 1620, {'1': 'gnd_net'})

    s.note('CONTROL UNIT: IP, IR, AR, DR, FR, state counter T0..T7', 200, 20)
    s.connect().save('uu.bdf')


# ------------------------------------------------------------ laba4.bdf (верхний уровень)
def make_top():
    s = B.Sch()
    uu = B.load_bsf('uu.bsf')
    rom = B.load_bsf('rom.bsf')
    ram = B.load_bsf('ram.bsf')
    ron = B.load_bsf('ron.bsf')

    inp(s, 'clk', 'clk', 200, 272)
    out = [('adr_out[5:0]', 'address[5:0]', 296),
           ('rom_data_out[9:0]', 'rom_data[9:0]', 376),
           ('ir_out[9:0]', 'ir[9:0]', 456),
           ('T_out[2:0]', 'T[2:0]', 536),
           ('flag_out', 'z', 616),
           ('ron_addr_out[1:0]', 'ron_addr[1:0]', 696),
           ('ron_wr_out', 'ron_wr', 776),
           ('ron_rd_out', 'ron_rd', 856),
           ('ram_en_out', 'ram_en', 936),
           ('ram_wr_out', 'ram_wr', 1016),
           ('data_out[3:0]', 'data_io[3:0]', 1096)]
    for pname, net, y in out:
        outp(s, pname, net, 1600, y)

    s.inst(uu, 'inst5', 400, 240,
           {'clk': 'clk', 'rom_data[9..0]': 'rom_data[9:0]',
            'address[5..0]': 'address[5:0]', 'ron_addr[1..0]': 'ron_addr[1:0]',
            'ron_wr': 'ron_wr', 'ron_rd': 'ron_rd',
            'ram_en': 'ram_en', 'ram_wr': 'ram_wr', 'ir_out[9..0]': 'ir[9:0]',
            'T_out[2..0]': 'T[2:0]', 'flag_out': 'z', 'data_io[3..0]': 'data_io[3:0]'})
    s.inst(rom, 'inst4', 1000, 200,
           {'address[5:0]': 'address[5:0]', 'clock': 'clk', 'q[9:0]': 'rom_data[9:0]'})
    s.inst(ram, 'inst2', 1000, 500,
           {'address[5:0]': 'address[5:0]', 'data_in[3:0]': 'data_io[3:0]',
            'wren': 'ram_wr', 'enable': 'ram_en', 'clock': 'clk',
            'data_out[3:0]': 'data_io[3:0]'})
    s.inst(ron, 'inst3', 1000, 800,
           {'clk': 'clk', 'data_input[3:0]': 'data_io[3:0]',
            'address[1:0]': 'ron_addr[1:0]', 'write': 'ron_wr',
            'read': 'ron_rd', 'data_output[3:0]': 'data_io[3:0]'})
    s.note('CPU: address bus 6, data bus 4 (ROM 64x10, RAM 64x4, RON 4x4)', 200, 40)
    s.connect().save('laba4.bdf')


if __name__ == '__main__':
    write_bsf('rom.bsf', 'rom', [('address[5:0]', 'input'), ('clock', 'input'),
                                 ('q[9:0]', 'output')])
    write_bsf('ram.bsf', 'ram', [('address[5:0]', 'input'), ('data_in[3:0]', 'input'),
                                 ('wren', 'input'), ('enable', 'input'), ('clock', 'input'),
                                 ('data_out[3:0]', 'output')])
    write_bsf('ron.bsf', 'ron', [('clk', 'input'), ('data_input[3:0]', 'input'),
                                 ('address[1:0]', 'input'), ('write', 'input'),
                                 ('read', 'input'), ('data_output[3:0]', 'output')])
    write_bsf('uu.bsf', 'uu', [('clk', 'input'), ('rom_data[9:0]', 'input'),
                               ('data_io[3:0]', 'bidir'),
                               ('address[5:0]', 'output'), ('ir_out[9:0]', 'output'),
                               ('T_out[2:0]', 'output'), ('flag_out', 'output'),
                               ('ron_addr[1:0]', 'output'), ('ron_wr', 'output'),
                               ('ron_rd', 'output'), ('ram_en', 'output'),
                               ('ram_wr', 'output')])
    for fn in (make_rom, make_ram, make_ron, make_uu, make_top):
        print('--', fn.__name__)
        fn()
    print('схемы собраны')
