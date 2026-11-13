#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка обёрток мегафункций (.v): у каждого выходного порта должен быть драйвер.

Именно такой промах ломал флаг Z: в `lpm_compare0.v` был объявлен выход `aeb`,
но к выходу компонента `lpm_compare` он не был подключён (`assign aeb = ...`
отсутствовал), поэтому на вход данных регистра флагов приходил «висящий» сигнал.

Запуск:  python3 tools/check_lpm.py
"""
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    bad = 0
    files = sorted(glob.glob(os.path.join(ROOT, 'lpm_*.v')))
    for path in files:
        name = os.path.basename(path)
        if name.endswith('_bb.v'):
            continue
        text = open(path, encoding='utf-8').read()
        m = re.search(r'module\s+\w+\s*\((.*?)\);(.*?)endmodule', text, re.S)
        if not m:
            print('   !!! %s: не найден модуль' % name)
            bad += 1
            continue
        body = m.group(2)
        outs = [n.strip()
                for o in re.findall(r'output\s*(?:\[[^\]]*\])?\s*([\w, ]+);', body)
                for n in o.split(',') if n.strip()]
        for o in outs:
            # выход должен быть либо объявлен как wire с присваиванием,
            # либо подключён через assign
            if not re.search(r'(wire[^=;]*\b%s\s*=|assign\s+%s\s*=)' % (o, o), body):
                print('   !!! %s: у выхода %s нет драйвера' % (name, o))
                bad += 1
    print('проверено мегафункций: %d, проблем: %d'
          % (len([f for f in files if not f.endswith('_bb.v')]), bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
