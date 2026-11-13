# -*- coding: utf-8 -*-
"""Цикловая модель АСК: ША = 6, ШД = 4, MOV M->R (прямая), JZ (непосредственная).

Слово команды 9 бит: КОП[8] | R[7..6] | ADR[5..0].
Команды: КОП = 0 -> MOV, КОП = 1 -> JZ.
"""

ROM = {
    0x00: 0b0_00_000100,  # MOV M[4], R0   R0=9  Z=0
    0x01: 0b1_00_000011,  # JZ  $3         Z=0 -> перехода нет
    0x02: 0b0_01_000101,  # MOV M[5], R1   R1=6  Z=0
    0x03: 0b0_10_000110,  # MOV M[6], R2   R2=F  Z=0
    0x04: 0b0_11_000111,  # MOV M[7], R3   R3=0  Z=1
    0x05: 0b1_00_000000,  # JZ  $0         Z=1 -> переход на 00
}
# Незанятые ячейки = 000 -> формально MOV M[0], R0, но программа зациклена
# (JZ $0 при Z=1), поэтому IP за пределы адреса 05 не выходит.
ROM = {a: ROM.get(a, 0x000) for a in range(64)}

RAM = {a: 0 for a in range(64)}
RAM[4] = 0x9
RAM[5] = 0x6
RAM[6] = 0xF
RAM[7] = 0x0

IP_MASK = 0x3F     # ША = 6 бит
DR_MASK = 0x0F     # ШД = 4 бита


class CPU:
    """Модель машины: 6 тактов (T0…T5), обе памяти — синхронные (задержка 1 такт).

    Память на Stratix II читается по фронту: адрес, поданный в такте T,
    даёт данные в такте T+1. Поэтому адрес операнда выставляется на ША
    в такте T3, а данные RAM читаются в DR в такте T4.
    """

    TICKS = 6

    def __init__(s):
        s.IP = 0; s.IR = 0; s.AR = 0; s.DR = 0; s.Z = 0; s.T = 0
        s.rom_q = 0; s.ram_q = 0          # выходные регистры памяти
        s.RON = [0] * 4; s.trace = []

    # ---- комбинационная логика (как в схеме uu.bdf) ----
    def op(s):     return (s.IR >> 8) & 1        # КОП = IR[8]
    def is_mov(s): return s.op() == 0
    def is_jz(s):  return s.op() == 1
    def jump(s):   return s.op() == 1 and s.Z == 1
    def sel_sha(s): return s.T == 3 and s.is_mov()
    def sha(s):    return s.AR if s.sel_sha() else s.IP
    def adr(s):    return s.IR & IP_MASK             # IR[5..0]
    def rsel(s):   return (s.IR >> 6) & 0x3          # IR[7..6]

    def bus(s):
        """Кто в этом такте выставляет данные на ШД."""
        if s.T == 4 and s.is_mov():
            return s.ram_q, 'RAM'                    # данные RAM (адрес подан в T3)
        if s.T == 5 and s.is_mov():
            return s.DR, 'DR'
        return None, '-'

    def ROM_out(s):
        return s.rom_q                               # слово, прочитанное по адресу T-1

    def step(s):
        sha = s.sha(); bus, src = s.bus(); rom = s.rom_q
        st = dict(T=s.T, IP=s.IP, IR=s.IR, AR=s.AR, DR=s.DR, Z=s.Z,
                  sha=sha, rom=rom, bus=bus, src=src, RON=list(s.RON))
        ctl = dict(ir_ld=(s.T == 1), ip_cnt=(s.T == 1),
                   ip_ld_jmp=(s.T == 3 and s.jump()),
                   ar_ld=(s.T == 2 and s.is_mov()), sha_ar=s.sel_sha(),
                   ram_en=(s.T == 4 and s.is_mov()),
                   dr_ld=(s.T == 4 and s.is_mov()),
                   dr_out=(s.T == 5 and s.is_mov()),
                   ron_wr=(s.T == 5 and s.is_mov()),
                   fr_ld=(s.T == 5 and s.is_mov()))
        st['ctl'] = ctl
        s.trace.append(st)
        # ---- регистры (по фронту) ----
        if s.T == 1:
            s.IR = s.rom_q; s.IP = (s.IP + 1) & IP_MASK
        elif s.T == 2 and s.is_mov():
            s.AR = s.adr()
        elif s.T == 3 and s.jump():
            s.IP = s.adr()
        elif s.T == 4 and s.is_mov():
            s.DR = s.ram_q & DR_MASK
        elif s.T == 5 and s.is_mov():
            s.RON[s.rsel()] = s.DR
            s.Z = 1 if s.DR == 0 else 0
        # ---- память защёлкивает адрес с ША по каждому фронту ----
        s.rom_q = ROM[sha]
        s.ram_q = RAM[sha] & DR_MASK
        s.T = (s.T + 1) % s.TICKS
        return st


def disasm(w):
    adr = w & IP_MASK; r = (w >> 6) & 3
    if ((w >> 8) & 1) == 0:
        return 'MOV M[%X], R%d' % (adr, r)
    return 'JZ  $%X' % adr


if __name__ == '__main__':
    cpu = CPU(); log = []
    for i in range(6 * 6 * 3):        # три полных обхода программы
        st = cpu.step()
        c = st['ctl']
        act = [k for k, v in c.items() if v]
        log.append('T%d IP=%02X IR=%03X(%s) AR=%02X DR=%X Z=%d bus=%s SHA=%02X | %s' % (
            st['T'], st['IP'], st['IR'], disasm(st['IR']), st['AR'], st['DR'], st['Z'],
            '-' if st['bus'] is None else '%X' % st['bus'], st['sha'], ','.join(act)))
        if i % 6 == 5 and i < 6 * 6:
            print('\n'.join(log[-6:])); print('-' * 100)
    print('\nФлаг Z по командам (DR ← ШД в T4, флаг пишется в FR в такте T5 команды MOV):')
    rows = []
    for k in range(0, len(cpu.trace), 6):
        blk = cpu.trace[k:k + 6]
        if len(blk) < 6:
            break
        word = blk[2]['IR']
        if disasm(word).startswith('MOV'):
            rows.append('%02X %-12s операнд DR=%X -> Z=%d'
                        % (blk[0]['IP'], disasm(word), blk[5]['DR'],
                           0 if blk[5]['DR'] else 1))
        else:
            rows.append('%02X %-12s (флаг не меняется) Z=%d'
                        % (blk[0]['IP'], disasm(word), blk[3]['Z']))
        if len(rows) == 6:
            break
    print('\n'.join(rows))
    print('\nИтог: RON =', [format(x, 'X') for x in cpu.RON])
    print('\nТрасса выборки (адреса в порядке выполнения):')
    seen = []
    for st in cpu.trace:
        if st['ctl']['ir_ld']:
            seen.append((st['IP'], st['rom']))
    print(', '.join('%X:%s' % (a, disasm(w)) for a, w in seen[:14]))
