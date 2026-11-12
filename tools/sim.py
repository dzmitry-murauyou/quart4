# -*- coding: utf-8 -*-
"""Цикловая модель АСК: ША = 6, ШД = 4, MOV M->R (прямая), JZ (непосредственная).

Слово команды 10 бит: КОП[9..8] | ADR[7..2] | R[1..0].
"""

ROM = {
    0x00: 0b01_000100_00,  # MOV M[4], R0   R0=9  Z=0
    0x01: 0b10_000011_00,  # JZ  $3         Z=0 -> перехода нет
    0x02: 0b01_000101_01,  # MOV M[5], R1   R1=6  Z=0
    0x03: 0b01_000110_10,  # MOV M[6], R2   R2=F  Z=0
    0x04: 0b01_000111_11,  # MOV M[7], R3   R3=0  Z=1
    0x05: 0b10_000000_00,  # JZ  $0         Z=1 -> переход на 00
}
ROM = {a: ROM.get(a, 0x000) for a in range(64)}

RAM = {a: 0 for a in range(64)}
RAM[4] = 0x9
RAM[5] = 0x6
RAM[6] = 0xF
RAM[7] = 0x0

IP_MASK = 0x3F     # ША = 6 бит
DR_MASK = 0x0F     # ШД = 4 бита


class CPU:
    def __init__(s):
        s.IP = 0; s.IR = 0; s.AR = 0; s.DR = 0; s.Z = 0; s.T = 0
        s.RON = [0] * 4; s.trace = []

    # ---- комбинационная логика (как в схеме uu.bdf) ----
    def is_mov(s): return ((s.IR >> 9) & 1) == 0 and ((s.IR >> 8) & 1) == 1
    def is_jz(s):  return ((s.IR >> 9) & 1) == 1 and ((s.IR >> 8) & 1) == 0
    def is_jmp(s): return ((s.IR >> 9) & 1) == 1 and ((s.IR >> 8) & 1) == 1
    def jump(s):   return ((s.IR >> 9) & 1) == 1 and (((s.IR >> 8) & 1) == 1 or s.Z == 1)
    def sel_sha(s): return s.T == 3 and s.is_mov()
    def sha(s):    return s.AR if s.sel_sha() else s.IP
    def adr(s):    return (s.IR >> 2) & IP_MASK      # IR[7..2]
    def rsel(s):   return s.IR & 0x3                 # IR[1..0]

    def bus(s):
        if s.T == 3 and s.is_mov():
            return RAM[s.AR], 'RAM'
        if s.T == 4 and s.is_mov():
            return s.DR, 'DR'
        return None, '-'

    def ROM_out(s):
        return ROM[s.sha()]

    def step(s):
        sha = s.sha(); bus, src = s.bus(); rom = s.ROM_out()
        st = dict(T=s.T, IP=s.IP, IR=s.IR, AR=s.AR, DR=s.DR, Z=s.Z,
                  sha=sha, rom=rom, bus=bus, src=src, RON=list(s.RON))
        ctl = dict(ir_ld=s.T == 1, ip_cnt=s.T == 1,
                   ip_ld_jmp=(s.T == 3 and s.jump()),
                   ar_ld=(s.T == 2 and s.is_mov()), sha_ar=s.sel_sha(),
                   ram_en=s.sel_sha(), dr_ld=(s.T == 3 and s.is_mov()),
                   dr_out=(s.T == 4 and s.is_mov()),
                   ron_wr=(s.T == 4 and s.is_mov()),
                   fr_ld=(s.T == 4 and s.is_mov()))
        st['ctl'] = ctl
        s.trace.append(st)
        # ---- регистры (по фронту) ----
        if s.T == 1:
            s.IR = rom; s.IP = (s.IP + 1) & IP_MASK
        elif s.T == 3 and s.jump():
            s.IP = s.adr()
        if s.T == 2 and s.is_mov():
            s.AR = s.adr()
        if s.T == 3 and s.is_mov():
            s.DR = bus & DR_MASK
        if s.T == 4 and s.is_mov():
            s.RON[s.rsel()] = bus & DR_MASK
            s.Z = 1 if s.DR == 0 else 0
        s.T = (s.T + 1) & 7
        return st


def disasm(w):
    kop = (w >> 8) & 3; adr = (w >> 2) & IP_MASK; r = w & 3
    if kop == 0b01: return 'MOV M[%X], R%d' % (adr, r)
    if kop == 0b10: return 'JZ  $%X' % adr
    if kop == 0b11: return 'JMP $%X' % adr
    return 'NOP'


if __name__ == '__main__':
    cpu = CPU(); log = []
    for i in range(8 * 8 * 3):        # три полных обхода программы
        st = cpu.step()
        c = st['ctl']
        act = [k for k, v in c.items() if v]
        log.append('T%d IP=%02X IR=%03X(%s) AR=%02X DR=%X Z=%d bus=%s SHA=%02X | %s' % (
            st['T'], st['IP'], st['IR'], disasm(st['IR']), st['AR'], st['DR'], st['Z'],
            '-' if st['bus'] is None else '%X' % st['bus'], st['sha'], ','.join(act)))
        if i % 8 == 7 and i < 8 * 8:
            print('\n'.join(log[-8:])); print('-' * 100)
    print('\nИтог: RON =', [format(x, 'X') for x in cpu.RON])
    print('\nТрасса выборки (адреса в порядке выполнения):')
    seen = []
    for st in cpu.trace:
        if st['ctl']['ir_ld']:
            seen.append((st['IP'], st['rom']))
    print(', '.join('%X:%s' % (a, disasm(w)) for a, w in seen[:14]))
