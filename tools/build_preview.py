#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成済み迷路JSON（tools/generate_mazes.py の出力）を index.html に流し込んだ
プレビューページ tmp/preview.html を作る。本番の index.html は変更しない。

使い方:
  python3 tools/generate_mazes.py --out tmp/mazes_available.json
  python3 tools/build_preview.py tmp/mazes_available.json
  python3 -m http.server 8642   # → http://localhost:8642/tmp/preview.html

プレビューには左下に迷路ジャンプ用の <select> が付く（?m=番号 でも指定可）。
MAZES の置換ロジックは将来の本番埋め込みでもそのまま使える。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def mazes_to_js(mazes):
    out = ['const MAZES = [ // ← tools/build_preview.py が生成JSONから自動埋め込み']
    for m in mazes:
        labels = ','.join("{img:'%s',word:'%s'}" % (l['img'], l['word'])
                          for l in m['labels'])
        out.append('  { // わな%d %s' % (m['score'], m['chain']))
        out.append('    board:BOARD_%s,' % m['board'])
        out.append('    labels:[%s],' % labels)
        out.append('    solution:[%s],' % ','.join(map(str, m['solution'])))
        out.append('  },')
    out.append('];')
    return '\n'.join(out)


def replace_mazes(html, mazes):
    start = html.index('const MAZES = [')
    end = html.index('\n];', start) + len('\n];')
    return html[:start] + mazes_to_js(mazes) + html[end:]


def preview_bar(mazes):
    opts = ''.join(
        '<option value="%d">%d [%s] わな%d %s</option>'
        % (i, i + 1, m['board'], m['score'], m['chain'])
        for i, m in enumerate(mazes))
    return '''
<div style="position:fixed;left:8px;bottom:8px;z-index:9999;background:rgba(255,255,255,.85);
  border-radius:8px;padding:6px 8px;font:12px/1.4 sans-serif;box-shadow:0 1px 6px rgba(0,0,0,.25);">
  ⚠️プレビュー版 <select id="pvsel" style="max-width:min(64vw,420px);font-size:12px;">%s</select>
</div>
<script>
(function(){
  const s = document.getElementById('pvsel');
  const orig = loadMaze;
  loadMaze = function(k){ orig(k); s.value = k; };   // つぎのめいろ等と選択を同期
  s.addEventListener('change', ()=>loadMaze(+s.value));
  const q = new URLSearchParams(location.search).get('m');
  if(q !== null) loadMaze(Math.max(0, Math.min(MAZES.length-1, (+q||1)-1)));
  s.value = mz;
})();
</script>
''' % opts


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else 'tmp/mazes_available.json'
    data = json.load(open(os.path.join(ROOT, src) if not os.path.isabs(src) else src,
                          encoding='utf-8'))
    mazes = data['mazes']
    html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
    html = replace_mazes(html, mazes)
    # tmp/ 配下から img/ 等の相対パスが解決できるように
    html = html.replace('<head>', '<head><base href="../">', 1)
    html = html.replace('</body>', preview_bar(mazes) + '</body>', 1)
    out = os.path.join(ROOT, 'tmp', 'preview.html')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print('出力: tmp/preview.html（%d問 / 元データ: %s）' % (len(mazes), src))


if __name__ == '__main__':
    main()
