# -*- coding: utf-8 -*-
"""Сборка схем проекта: rom.bdf, ram.bdf, ron.bdf, uu.bdf, laba4.bdf + символы."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bdfgen as B

ROOT = B.ROOT
PRIM = 'uu.bdf'          # файл-источник шаблонов примитивов (перезапишется позже)
SRC_PRIM = 'laba4.bdf'   # примитивы берём из файла, который не перезаписываем первым

def P(name):
    return B.load_prim(name, SRC_PRIM if _has(SRC_PRIM, name) else PRIM)

def _has(fn, name):
    txt = (ROOT / fn).read_text(encoding='utf-8')
    return ('text "%s"' % name) in txt

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
                      ['line', ['pt', '0', str(y)], ['pt', '16', str(y)], ['line_width', '3' if '[' in name else '1']]])
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
    s.pin('address[3:0]', 'input', 'address[3:0]', 150, 200)
    s.pin('clock', 'input', 'clk', 150, 400)
    s.pin('q[7:0]', 'output', 'rom_q[7:0]', 1000, 300)
    s.inst(rom, 'inst', 500, 200,
           {'address[3:0]': 'address[3:0]', 'clock': 'clk', 'q[7:0]': 'rom_q[7:0]'})
    s.note('ROM: 16 x 8, init file rom.mif', 150, 60)
    s.save('rom.bdf')


# ------------------------------------------------------------ ram.bdf
def make_ram():
    s = B.Sch()
    ram = B.load_bsf('lpm_ram_dq0.bsf')
    buf = B.load_bsf('lpm_bustri0.bsf')
    s.pin('address[3:0]', 'input', 'address[3:0]', 150, 150)
    s.pin('data_in[5:0]', 'input', 'ram_d[5:0]', 150, 350)
    s.pin('wren', 'input', 'ram_wr', 150, 550)
    s.pin('enable', 'input', 'ram_en', 150, 750)
    s.pin('clock', 'input', 'clk', 150, 950)
    s.pin('data_out[5:0]', 'output', 'data_out[5:0]', 1100, 550)
    s.inst(ram, 'inst', 550, 200,
           {'address[3:0]': 'address[3:0]', 'data[5:0]': 'ram_d[5:0]',
            'wren': 'ram_wr', 'clock': 'clk', 'q[5:0]': 'ram_q[5:0]'})
    s.inst(buf, 'inst1', 750, 550,
           {'enabledt': 'ram_en', 'data[5:0]': 'ram_q[5:0]', 'tridata[5:0]': 'data_out[5:0]'})
    s.note('RAM: 16 x 6, init file ram.mif', 150, 60)
    s.save('ram.bdf')


# ------------------------------------------------------------ ron.bdf
def make_ron():
    s = B.Sch()
    dff = B.load_bsf('lpm_dff2.bsf')       # 6 бит
    dec = B.load_bsf('lpm_decode0.bsf')    # 2 -> 4
    mux = B.load_bsf('lpm_mux0.bsf')       # 4:1, 6 бит
    buf = B.load_bsf('lpm_bustri0.bsf')
    s.pin('clk', 'input', 'clk', 150, 100)
    s.pin('data_input[5:0]', 'input', 'ron_d[5:0]', 150, 300)
    s.pin('address[1:0]', 'input', 'ron_a[1:0]', 150, 500)
    s.pin('write', 'input', 'write', 150, 700)
    s.pin('read', 'input', 'read', 150, 900)
    s.pin('data_output[5:0]', 'output', 'data_output[5:0]', 1500, 500)
    s.inst(dec, 'dec', 550, 650,
           {'data[1..0]': 'ron_a[1:0]', 'enable': 'write',
            'eq0': 'we0', 'eq1': 'we1', 'eq2': 'we2', 'eq3': 'we3'})
    for i in range(4):
        s.inst(dff, 'r%d' % i, 550 + 0, 100 + i * 140,
               {'data[5:0]': 'ron_d[5:0]', 'clock': 'clk', 'enable': 'we%d' % i,
                'q[5:0]': 'r%d[5:0]' % i})
    s.inst(mux, 'mux', 1000, 250,
           {'data0x[5:0]': 'r0[5:0]', 'data1x[5:0]': 'r1[5:0]',
            'data2x[5:0]': 'r2[5:0]', 'data3x[5:0]': 'r3[5:0]',
            'sel[1..0]': 'ron_a[1:0]', 'result[5:0]': 'ron_mux[5:0]'})
    s.inst(buf, 'buf', 1000, 550,
           {'enabledt': 'read', 'data[5:0]': 'ron_mux[5:0]', 'tridata[5:0]': 'data_output[5:0]'})
    s.note('RON: registers R0..R3, 6 bit each', 150, 40)
    s.save('ron.bdf')


# ------------------------------------------------------------ uu.bdf
def make_uu():
    s = B.Sch()
    cnt = B.load_bsf('lpm_counter0.bsf')   # 3 бита, счётчик тактов
    dec = B.load_bsf('lpm_decode1.bsf')    # 3 -> 8
    ir = B.load_bsf('lpm_dff0.bsf')        # 8 бит
    reg4 = B.load_bsf('lpm_dff1.bsf')      # 4 бита
    dr = B.load_bsf('lpm_dff2.bsf')        # 6 бит
    fr = B.load_bsf('lpm_dff3.bsf')        # 1 бит
    add = B.load_bsf('lpm_add_sub0.bsf')   # 4 бита
    one = B.load_bsf('lpm_constant0.bsf')  # 4 бита, значение 1
    mux = B.load_bsf('lpm_mux1.bsf')       # 2:1, 4 бита
    buf = B.load_bsf('lpm_bustri0.bsf')    # 6 бит
    notg, andg, org, gnd = P('NOT'), P('AND2'), P('OR2'), P('GND')

    # ---- выводы блока
    s.pin('clk', 'input', 'clk', 100, 80)
    s.pin('rom_data[7:0]', 'input', 'rom_data[7:0]', 100, 240)
    s.pin('data_io[5:0]', 'bidir', 'data_io[5:0]', 2450, 240)
    s.pin('address[3:0]', 'output', 'address[3:0]', 2450, 420)
    s.pin('ir_out[7:0]', 'output', 'ir[7:0]', 2450, 560)
    s.pin('T_out[2:0]', 'output', 'T[2:0]', 2450, 700)
    s.pin('flag_out', 'output', 'z', 2450, 840)
    s.pin('ron_addr[1:0]', 'output', 'ir[1..0]', 2450, 980)
    s.pin('ron_wr', 'output', 'mov_t4', 2450, 1120)
    s.pin('ron_rd', 'output', 'gnd_net', 2450, 1260)
    s.pin('ram_en', 'output', 'mov_t3', 2450, 1400)
    s.pin('ram_wr', 'output', 'gnd_net', 2450, 1540)

    # ---- регистры и счётчик тактов
    s.inst(cnt, 'T_cnt', 450, 100, {'clock': 'clk', 'q[2:0]': 'T[2:0]'})
    s.inst(dec, 'T_dec', 800, 100,
           {'data[2:0]': 'T[2:0]', 'eq0': 't0', 'eq1': 't1', 'eq2': 't2', 'eq3': 't3',
            'eq4': 't4', 'eq5': 't5', 'eq6': 't6', 'eq7': 't7'})
    s.inst(ir, 'IR_reg', 450, 400,
           {'data[7:0]': 'rom_data[7:0]', 'clock': 'clk', 'enable': 't1', 'q[7:0]': 'ir[7:0]'})
    s.inst(reg4, 'AR_reg', 450, 700,
           {'data[3:0]': 'ir[5..2]', 'clock': 'clk', 'enable': 'mov_t2', 'q[3:0]': 'ar[3:0]'})
    s.inst(dr, 'DR_reg', 450, 950,
           {'data[5:0]': 'data_io[5:0]', 'clock': 'clk', 'enable': 'mov_t3', 'q[5:0]': 'dr[5:0]'})
    s.inst(reg4, 'IP_reg', 900, 700,
           {'data[3:0]': 'ip_next[3:0]', 'clock': 'clk', 'enable': 'ip_en', 'q[3:0]': 'ip[3:0]'})
    s.inst(add, 'IP_inc', 900, 950,
           {'dataa[3:0]': 'ip[3:0]', 'datab[3:0]': 'one[3:0]', 'result[3:0]': 'ip_plus1[3:0]'})
    s.inst(one, 'const1', 600, 1100, {'result[3:0]': 'one[3:0]'})
    s.inst(mux, 'IP_mux', 1350, 900,
           {'data0x[3:0]': 'ip_plus1[3:0]', 'data1x[3:0]': 'ir[5..2]',
            'sel': 'ip_jump', 'result[3:0]': 'ip_next[3:0]'})
    s.inst(mux, 'SHA_mux', 1350, 500,
           {'data0x[3:0]': 'ip[3:0]', 'data1x[3:0]': 'ar[3:0]',
            'sel': 'mov_t3', 'result[3:0]': 'address[3:0]'})
    s.inst(buf, 'DR_buf', 1350, 150,
           {'enabledt': 'mov_t4', 'data[5:0]': 'dr[5:0]', 'tridata[5:0]': 'data_io[5:0]'})
    s.inst(fr, 'FR', 1800, 700,
           {'data': 'z_d', 'clock': 'clk', 'enable': 'mov_t4', 'q': 'z'})

    # ---- управляющая логика
    s.inst(notg, 'n_ir7', 450, 1350, {'IN': 'ir[7]', 'OUT': 'n_ir7'})
    s.inst(andg, 'is_mov', 620, 1350, {'IN1': 'ir[6]', 'IN2': 'n_ir7', 'OUT': 'is_mov'})
    s.inst(org, 'jcond', 800, 1350, {'IN1': 'ir[6]', 'IN2': 'z', 'OUT': 'jcond'})
    s.inst(andg, 'jump', 970, 1350, {'IN1': 'ir[7]', 'IN2': 'jcond', 'OUT': 'jump'})
    s.inst(andg, 'mov_t2', 1140, 1350, {'IN1': 't2', 'IN2': 'is_mov', 'OUT': 'mov_t2'})
    s.inst(andg, 'mov_t3', 1310, 1350, {'IN1': 't3', 'IN2': 'is_mov', 'OUT': 'mov_t3'})
    s.inst(andg, 'mov_t4', 1480, 1350, {'IN1': 't4', 'IN2': 'is_mov', 'OUT': 'mov_t4'})
    s.inst(andg, 'ip_jmp', 1650, 1350, {'IN1': 't3', 'IN2': 'jump', 'OUT': 'ip_jump'})
    s.inst(org, 'ip_en', 1820, 1350, {'IN1': 't1', 'IN2': 'ip_jump', 'OUT': 'ip_en'})
    # флаг нуля: z_d = ~(dr[5]|dr[4]|dr[3]|dr[2]|dr[1]|dr[0])
    s.inst(org, 'o1', 620, 1550, {'IN1': 'dr[0]', 'IN2': 'dr[1]', 'OUT': 'o1'})
    s.inst(org, 'o2', 800, 1550, {'IN1': 'dr[2]', 'IN2': 'dr[3]', 'OUT': 'o2'})
    s.inst(org, 'o3', 970, 1550, {'IN1': 'dr[4]', 'IN2': 'dr[5]', 'OUT': 'o3'})
    s.inst(org, 'o4', 1140, 1550, {'IN1': 'o1', 'IN2': 'o2', 'OUT': 'o4'})
    s.inst(org, 'o5', 1310, 1550, {'IN1': 'o3', 'IN2': 'o4', 'OUT': 'o5'})
    s.inst(notg, 'nz', 1480, 1550, {'IN': 'o5', 'OUT': 'z_d'})
    # константа 0 для резервных сигналов РОН/память
    s.inst(gnd, 'gnd0', 1650, 1550, {'1': 'gnd_net'})

    s.note('CONTROL UNIT: IP, IR, AR, DR, FR, state counter T0..T7', 100, 30)
    s.save('uu.bdf')


# ------------------------------------------------------------ laba4.bdf (верхний уровень)
def make_top():
    s = B.Sch()
    uu = B.load_bsf('uu.bsf')
    rom = B.load_bsf('rom.bsf')
    ram = B.load_bsf('ram.bsf')
    ron = B.load_bsf('ron.bsf')

    s.pin('clk', 'input', 'clk', 120, 200)
    out = [('adr_out[3:0]', 'address[3:0]'), ('data_out[5:0]', 'data_io[5:0]'),
           ('rom_data_out[7:0]', 'rom_data[7:0]'), ('ir_out[7:0]', 'ir[7:0]'),
           ('T_out[2:0]', 'T[2:0]'), ('flag_out', 'z'),
           ('ron_addr_out[1:0]', 'ron_addr[1:0]'), ('ron_wr_out', 'ron_wr'),
           ('ron_rd_out', 'ron_rd'), ('ram_en_out', 'ram_en'), ('ram_wr_out', 'ram_wr')]
    for i, (pname, net) in enumerate(out):
        s.pin(pname, 'output', net, 2200, 120 + i * 140)

    s.inst(uu, 'inst5', 400, 300,
           {'clk': 'clk', 'rom_data[7:0]': 'rom_data[7:0]', 'address[3:0]': 'address[3:0]',
            'ron_addr[1:0]': 'ron_addr[1:0]', 'ron_wr': 'ron_wr', 'ron_rd': 'ron_rd',
            'ram_en': 'ram_en', 'ram_wr': 'ram_wr', 'ir_out[7:0]': 'ir[7:0]',
            'T_out[2:0]': 'T[2:0]', 'flag_out': 'z', 'data_io[5:0]': 'data_io[5:0]'})
    s.inst(rom, 'inst4', 900, 250,
           {'address[3:0]': 'address[3:0]', 'clock': 'clk', 'q[7:0]': 'rom_data[7:0]'})
    s.inst(ram, 'inst2', 900, 550,
           {'address[3:0]': 'address[3:0]', 'data_in[5:0]': 'data_io[5:0]', 'wren': 'ram_wr',
            'enable': 'ram_en', 'clock': 'clk', 'data_out[5:0]': 'data_io[5:0]'})
    s.inst(ron, 'inst3', 900, 950,
           {'clk': 'clk', 'data_input[5:0]': 'data_io[5:0]', 'address[1:0]': 'ron_addr[1:0]',
            'write': 'ron_wr', 'read': 'ron_rd', 'data_output[5:0]': 'data_io[5:0]'})
    s.note('CPU: data bus 6, address bus 4 (ROM 16x8, RAM 16x6, RON 4x6)',
           120, 40)
    s.save('laba4.bdf')


if __name__ == '__main__':
    # порядок важен: laba4.bdf — источник шаблонов примитивов (AND2 и др.)
    write_bsf('rom.bsf', 'rom', [('address[3:0]', 'input'), ('clock', 'input'),
                                 ('q[7:0]', 'output')])
    write_bsf('ram.bsf', 'ram', [('address[3:0]', 'input'), ('data_in[5:0]', 'input'),
                                 ('wren', 'input'), ('enable', 'input'), ('clock', 'input'),
                                 ('data_out[5:0]', 'output')])
    write_bsf('ron.bsf', 'ron', [('clk', 'input'), ('data_input[5:0]', 'input'),
                                 ('address[1:0]', 'input'), ('write', 'input'),
                                 ('read', 'input'), ('data_output[5:0]', 'output')])
    write_bsf('uu.bsf', 'uu', [('clk', 'input'), ('rom_data[7:0]', 'input'),
                               ('data_io[5:0]', 'bidir'),
                               ('address[3:0]', 'output'), ('ir_out[7:0]', 'output'),
                               ('T_out[2:0]', 'output'), ('flag_out', 'output'),
                               ('ron_addr[1:0]', 'output'), ('ron_wr', 'output'),
                               ('ron_rd', 'output'), ('ram_en', 'output'),
                               ('ram_wr', 'output')])
    make_rom()
    make_ram()
    make_ron()
    make_uu()
    make_top()
    print('схемы собраны')
