#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成済み迷路JSON（tools/generate_mazes.py の出力）を本番 index.html の
MAZES に埋め込む。置換ロジックは build_preview.py と共有。

使い方:
  python3 tools/generate_mazes.py --out tmp/mazes_final.json
  python3 tools/embed_mazes.py tmp/mazes_final.json
  python3 tools/build_preview.py tmp/mazes_final.json   # プレビューも同じデータで更新
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_preview import ROOT, replace_mazes


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'tmp/mazes_final.json'
    path = src if os.path.isabs(src) else os.path.join(ROOT, src)
    data = json.load(open(path, encoding='utf-8'))
    idx = os.path.join(ROOT, 'index.html')
    html = open(idx, encoding='utf-8').read()
    html = replace_mazes(html, data['mazes'])
    with open(idx, 'w', encoding='utf-8') as f:
        f.write(html)
    a = sum(1 for m in data['mazes'] if m['board'] == 'A')
    print('index.html に埋め込み: %d問（かんたんA:%d / むずかしいB:%d / 元データ: %s）'
          % (len(data['mazes']), a, len(data['mazes']) - a, src))


if __name__ == '__main__':
    main()
