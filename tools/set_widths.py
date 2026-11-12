# -*- coding: utf-8 -*-
"""Приведение всех мегафункций LPM к новым разрядностям варианта.

Вариант: ША = 6 (64 слова), ШД = 4, слово команды 10 бит
(КОП 2 + ADR 6 + R 2).

Скрипт правит три вида файлов каждой мегафункции:
  *.v      — объявления портов, внутренние wire, параметры (defparam),
             а также информационные комментарии «Retrieval info»;
  *_bb.v   — «чёрный ящик»: только объявления портов;
  *.bsf    — символ для Block Editor: имена портов вида x[7..0].

Разрядности (было -> стало):
  lpm_rom0       64x9   -> 64x10      (address 6, q 10)
  lpm_ram_dq0    64x9   -> 64x4       (address 6, data/q 4)
  lpm_dff0 (IR)  8/9    -> 10
  lpm_dff1 (AR/IP) 4/6  -> 6
  lpm_dff2 (DR/RON) 6/9 -> 4
  lpm_dff3 (FR)   1     -> 1  (без изменений)
  lpm_mux0 (РОН)  6/9   -> 4
  lpm_mux1 (IP/SHA) 4/6 -> 6
  lpm_add_sub0    4/6   -> 6
  lpm_constant0   4/6   -> 6   (значение 1)
  lpm_bustri0     6/9   -> 4
"""
import re, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def apply_pairs(text, pairs, strict=True):
    """Последовательные замены без взаимных наложений (через метки)."""
    tmp = []
    for i, (old, new) in enumerate(pairs):
        key = '\x00%d\x00' % i
        if old not in text:
            if strict:
                raise SystemExit('не найдено: %r' % old)
            continue
        text = text.replace(old, key)
        tmp.append((key, new))
    for key, new in tmp:
        text = text.replace(key, new)
    return text


def set_param(text, name, value):
    """CONSTANT/PRIVATE: NAME NUMERIC "N" -> value."""
    pat = re.compile(r'(%s NUMERIC )"\d+"' % re.escape(name))
    if not pat.search(text):
        return text
    return pat.sub(lambda m: '%s"%s"' % (m.group(1), value), text)


SPEC = {
    'lpm_rom0': dict(
        v=[('[3:0]', '[5:0]'), ('[7:0]', '[9:0]')],
        widths=dict(numwords_a='64', widthad_a='6', width_a='10'),
        bsf=[('address[3..0]', 'address[5..0]'), ('q[7..0]', 'q[9..0]')],
    ),
    'lpm_ram_dq0': dict(
        v=[('[3:0]', '[5:0]'), ('[5:0]', '[3:0]')],
        widths=dict(numwords_a='64', widthad_a='6', width_a='4'),
        bsf=[('address[3..0]', 'address[5..0]'),
             ('data[5..0]', 'data[3..0]'), ('q[5..0]', 'q[3..0]')],
    ),
    'lpm_dff0': dict(
        v=[('[7:0]', '[9:0]')], widths=dict(lpm_width='10'),
        bsf=[('data[7..0]', 'data[9..0]'), ('q[7..0]', 'q[9..0]')],
    ),
    'lpm_dff1': dict(
        v=[('[3:0]', '[5:0]')], widths=dict(lpm_width='6'),
        bsf=[('data[3..0]', 'data[5..0]'), ('q[3..0]', 'q[5..0]')],
    ),
    'lpm_dff2': dict(
        v=[('[5:0]', '[3:0]')], widths=dict(lpm_width='4'),
        bsf=[('data[5..0]', 'data[3..0]'), ('q[5..0]', 'q[3..0]')],
    ),
    'lpm_mux0': dict(
        v=[('[5:0]', '[3:0]'), ('[23:0]', '[15:0]')], widths=dict(lpm_width='4'),
        bsf=[('[5..0]', '[3..0]')],
    ),
    'lpm_mux1': dict(
        v=[('[3:0]', '[5:0]'), ('[7:0]', '[11:0]')], widths=dict(lpm_width='6'),
        bsf=[('[3..0]', '[5..0]')],
    ),
    'lpm_add_sub0': dict(
        v=[('[3:0]', '[5:0]')], widths=dict(lpm_width='6'),
        bsf=[('[3..0]', '[5..0]')],
    ),
    'lpm_constant0': dict(
        v=[('[3:0]', '[5:0]')], widths=dict(lpm_width='6'),
        bsf=[('result[3..0]', 'result[5..0]')],
    ),
    'lpm_bustri0': dict(
        v=[('[5:0]', '[3:0]')], widths=dict(lpm_width='4'),
        # tridata — первой: иначе замена заденет её как подстроку data[5..0]
        bsf=[('tridata[5..0]', 'tridata[3..0]'), ('data[5..0]', 'data[3..0]')],
    ),
}


def patch_v(path, spec, strict=True):
    p = ROOT / path
    t = p.read_text(encoding='utf-8', errors='replace')
    t = apply_pairs(t, spec['v'], strict)
    for name, val in spec['widths'].items():
        t = re.sub(r'(%s = )\d+' % name, lambda m: m.group(1) + val, t)
        t = set_param(t, name.upper(), val)
    p.write_text(t, encoding='utf-8')


def patch_bsf(path, spec):
    p = ROOT / path
    t = p.read_text(encoding='utf-8', errors='replace')
    p.write_text(apply_pairs(t, spec['bsf']), encoding='utf-8')


if __name__ == '__main__':
    for name, spec in SPEC.items():
        patch_v(name + '.v', spec)
        patch_v(name + '_bb.v', spec, strict=False)
        patch_bsf(name + '.bsf', spec)
        print('%-14s OK' % name)
    print('разрядности обновлены: ША = 6, ШД = 4, команда = 10 бит')
