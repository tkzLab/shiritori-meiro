#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""しりとり迷路の自動生成器（オフライン）。

「事前に大量生成して検証済みデータとして埋め込む」ハイブリッド方式の生成側。
盤面プリセット(A/B)上で START→GOAL のルートを引き、語彙からしりとり連鎖を
割り当て、残りマスにダミー（分岐点には同じ先頭文字の"わな"を優先）を置き、
DFS で「しりとりとして有効な START→GOAL 単純パスがちょうど1本」であることを
機械検証したものだけを採用する。わなの数をスコアにして良問を選抜する。

使い方:
  python3 tools/generate_mazes.py                     # いまある絵だけで生成
  python3 tools/generate_mazes.py --with-planned      # 作成予定の絵も含めて生成
  python3 tools/generate_mazes.py --count-a 30 --count-b 20 --seed 1 --out tmp/mazes.json

出力 JSON の mazes[] は index.html の MAZES と同じ形
（board は 'A'/'B' の文字列。埋め込み時に BOARD_A/BOARD_B 参照へ置換する）。
score/chain はレビュー用のメタ情報。
"""
import argparse
import json
import os
import random
import sys

# ---------------------------------------------------------------- 語彙
# slug は img/nodes/<slug>.png のファイル名と一致させること
WORDS_AVAILABLE = {
    # セット1
    'niwatori': 'にわとり', 'ryu': 'りゅう', 'randoseru': 'らんどせる',
    'pasta': 'ぱすた', 'ringo': 'りんご', 'gorira': 'ごりら', 'rappa': 'らっぱ',
    'risu': 'りす', 'suika': 'すいか', 'karasu': 'からす', 'tamago': 'たまご',
    # セット2
    'daikon': 'だいこん', 'iruka': 'いるか', 'inoshishi': 'いのしし',
    'kitsune': 'きつね', 'fune': 'ふね', 'hebi': 'へび', 'kuma': 'くま',
    'zou': 'ぞう', 'kasa': 'かさ', 'saikoro': 'さいころ',
    'kutsushita': 'くつした', 'tokei': 'とけい', 'momo': 'もも', 'ki': 'き',
    'tako': 'たこ', 'koma': 'こま', 'sushi': 'すし', 'chou': 'ちょう',
    'milk': 'みるく', 'cheese': 'ちーず', 'fuusen': 'ふうせん', 'pan': 'ぱん',
    'hoshi': 'ほし', 'koala': 'こあら', 'sakura': 'さくら', 'sai': 'さい',
    'tulip': 'ちゅーりっぷ', 'kagami': 'かがみ', 'kemushi': 'けむし',
    'megane': 'めがね',
    # セット3（2026-07-05 追加。まり→ますく に変更）
    'neko': 'ねこ', 'shika': 'しか', 'ushi': 'うし', 'masuku': 'ますく',
    'mogura': 'もぐら', 'roketto': 'ろけっと', 'biidama': 'びーだま',
    'wani': 'わに', 'uchiwa': 'うちわ',
}
# 作成予定（イラスト待ち）。絵ができたら slug を合わせて img/nodes/ に置き、上へ移す
WORDS_PLANNED = {}

# ---------------------------------------------------------------- 盤面
# index.html の BOARD_A / BOARD_B と一致させること（edges/start/goal）
BOARDS = {
    'A': dict(
        n=11, start=0, goal=10,
        edges=[[0, 1], [1, 2], [2, 3], [4, 5], [5, 6], [7, 8], [8, 9], [9, 10],
               [0, 4], [1, 5], [2, 5], [3, 6], [4, 7], [5, 9], [3, 10]],
        path_len=(5, 6),   # 正解ルートのマス数（手作り1〜3と同じ規模）
    ),
    'B': dict(
        n=16, start=0, goal=15,
        edges=[[0, 1], [0, 4], [1, 2], [1, 5], [2, 3], [2, 6], [3, 7],
               [5, 6], [5, 9], [6, 7], [6, 10], [7, 11],
               [4, 8], [8, 9], [8, 12], [9, 10], [9, 13], [10, 11], [10, 14],
               [11, 15], [12, 13], [13, 14], [14, 15]],
        path_len=(8, 9),
    ),
}

# ------------------------------------------------- しりとり判定（index.html と同一ロジック）
SMALL = 'ゃゅょぁぃぅぇぉっ'


def last_kana(w):
    c = w[-1]
    if c in SMALL:
        c = w[-2]
    if c == 'ー':
        c = w[-2]
    return c


def first_kana(w):
    return w[0]


def shiritori_ok(prev, nxt):
    return last_kana(prev) == first_kana(nxt)


# ---------------------------------------------------------------- グラフ道具
def adjacency(board):
    adj = [[] for _ in range(board['n'])]
    for a, b in board['edges']:
        adj[a].append(b)
        adj[b].append(a)
    return adj


def all_simple_paths(board):
    """START→GOAL の単純パスを path_len の範囲で全列挙"""
    adj = adjacency(board)
    lo, hi = board['path_len']
    res = []

    def dfs(node, visited, path):
        if node == board['goal']:
            if lo <= len(path) <= hi:
                res.append(tuple(path))
            return
        if len(path) >= hi:
            return
        for nx in adj[node]:
            if nx not in visited:
                visited.add(nx)
                path.append(nx)
                dfs(nx, visited, path)
                path.pop()
                visited.remove(nx)

    dfs(board['start'], {board['start']}, [board['start']])
    return res


def valid_paths(adj, start, goal, words_at, limit=3):
    """しりとりとして有効な START→GOAL 単純パスを limit 本まで列挙"""
    res = []

    def dfs(node, visited, path):
        if len(res) >= limit:
            return
        if node == goal:
            res.append(tuple(path))
            return
        for nx in adj[node]:
            if nx in visited:
                continue
            if shiritori_ok(words_at[node], words_at[nx]):
                visited.add(nx)
                path.append(nx)
                dfs(nx, visited, path)
                path.pop()
                visited.remove(nx)

    dfs(start, {start}, [start])
    return res


def sample_chains(words, length, rng, cap=3000):
    """指定長のしりとり連鎖（語の重複なし）を cap 本までランダム順に列挙。
    「ん」終わりの語は連鎖に入れない（教育上、正解ルートで「ん」を踏ませない）"""
    usable = [w for w in words if last_kana(w) != 'ん']
    succ = {w: [x for x in usable if x != w and shiritori_ok(w, x)] for w in usable}
    res = []

    def dfs(acc, used):
        if len(res) >= cap:
            return
        if len(acc) == length:
            res.append(tuple(acc))
            return
        nxts = [x for x in succ[acc[-1]] if x not in used]
        rng.shuffle(nxts)
        for x in nxts:
            used.add(x)
            acc.append(x)
            dfs(acc, used)
            acc.pop()
            used.discard(x)

    order = usable[:]
    rng.shuffle(order)
    for w in order:
        dfs([w], {w})
    return res


# ---------------------------------------------------------------- 生成本体
def trap_pairs(adj, route, chain, words_at):
    """わな = 正解ルート上のマス s から出る「しりとりは正しいのに不正解」の一歩。
    (s, p) のペア数を返す"""
    on_route = set(route)
    cnt = 0
    for i in range(len(route) - 1):
        k = last_kana(chain[i])
        for p in adj[route[i]]:
            if p not in on_route and first_kana(words_at[p]) == k:
                cnt += 1
    return cnt


def try_fill(board, route, chain, vocab, rng, attempts=25):
    """ダミーを配置して検証。合格した中で最もわなが多い配置を返す（無ければ None）"""
    adj = adjacency(board)
    non_route = [p for p in range(board['n']) if p not in route]
    avail = [w for w in vocab if w not in chain]
    # わなを置けるマス: ルート上のマス s_i に隣接する非ルートマス（必要な先頭文字つき）
    opps = []
    for i in range(len(route) - 1):
        k = last_kana(chain[i])
        for p in adj[route[i]]:
            if p not in route:
                opps.append((p, k))
    best = None
    for t in range(attempts):
        prob = 1.0 if t < attempts // 2 else 0.6  # 後半はわなを間引いて逃げ道を作る
        assign = {}
        used = set(chain)
        rng.shuffle(opps)
        for p, k in opps:
            if p in assign or rng.random() > prob:
                continue
            cands = [w for w in avail if w not in used and first_kana(w) == k]
            if cands:
                w = rng.choice(cands)
                assign[p] = w
                used.add(w)
        rest = [w for w in avail if w not in used]
        rng.shuffle(rest)
        for p in non_route:
            if p not in assign:
                assign[p] = rest.pop()
        words_at = {p: chain[i] for i, p in enumerate(route)}
        words_at.update(assign)
        paths = valid_paths(adj, board['start'], board['goal'], words_at, limit=2)
        if len(paths) == 1 and paths[0] == tuple(route):  # 解が一意＝正解ルートのみ
            score = trap_pairs(adj, route, chain, words_at)
            if best is None or score > best[0]:
                best = (score, dict(words_at))
    return best


def generate_for_board(key, vocab, target, rng, chains_per_route=40):
    board = BOARDS[key]
    routes = all_simple_paths(board)
    rng.shuffle(routes)
    chains_by_len = {}
    for ln in range(board['path_len'][0], board['path_len'][1] + 1):
        chains_by_len[ln] = sample_chains(vocab, ln, rng)

    candidates = []  # (score, route, chain, words_at)
    seen_chains = set()
    for route in routes:
        chains = chains_by_len.get(len(route), [])
        picked = chains[:] if len(chains) <= chains_per_route else rng.sample(chains, chains_per_route)
        for chain in picked:
            if chain in seen_chains:
                continue
            got = try_fill(board, route, chain, vocab, rng)
            if got:
                seen_chains.add(chain)
                candidates.append((got[0], route, chain, got[1]))
        if len(candidates) >= target * 6:
            break

    # 選抜: スコア順に、まずルート重複なしで取り、足りなければ重複を許す
    candidates.sort(key=lambda c: (-c[0], rng.random()))
    selected = []
    for max_route_use in (1, 2, 3, 4, 6, 999):
        route_use = {}
        for s in selected:
            route_use[s[1]] = route_use.get(s[1], 0) + 1
        for c in candidates:
            if len(selected) >= target:
                break
            if any(c[2] == s[2] for s in selected):
                continue
            if route_use.get(c[1], 0) >= max_route_use:
                continue
            selected.append(c)
            route_use[c[1]] = route_use.get(c[1], 0) + 1
        if len(selected) >= target:
            break
    stats = dict(routes=len(routes),
                 chains={ln: len(cs) for ln, cs in chains_by_len.items()},
                 candidates=len(candidates))
    return selected, stats


# ---------------------------------------------------------------- 自己テスト
# 手作りの4問（index.html の MAZES と同内容）を検証器に通し、
# Python 側のしりとり判定・一意性判定が本物と一致していることを担保する
HANDMADE = [
    ('A', ['にわとり', 'りゅう', 'らんどせる', 'ぱすた', 'りんご', 'ごりら',
           'らっぱ', 'りす', 'すいか', 'からす', 'たまご'], [0, 4, 5, 6, 3, 10]),
    ('A', ['いるか', 'かさ', 'さい', 'ぞう', 'かがみ', 'こま', 'すし', 'みるく',
           'くつした', 'たこ', 'こあら'], [0, 4, 7, 8, 9, 10]),
    ('A', ['とけい', 'へび', 'ぱん', 'もも', 'いるか', 'かさ', 'さくら',
           'かがみ', 'ほし', 'さい', 'いのしし'], [0, 4, 5, 9, 10]),
    ('B', ['にわとり', 'りす', 'さくら', 'らっぱ', 'だいこん', 'すいか', 'かさ',
           'ぱすた', 'ぱん', 'ふうせん', 'きつね', 'たまご', 'めがね', 'へび',
           'くま', 'ごりら'], [0, 1, 5, 6, 2, 3, 7, 11, 15]),
]


def selftest():
    for i, (key, words, sol) in enumerate(HANDMADE):
        board = BOARDS[key]
        adj = adjacency(board)
        words_at = dict(enumerate(words))
        paths = valid_paths(adj, board['start'], board['goal'], words_at, limit=3)
        assert len(paths) == 1 and paths[0] == tuple(sol), \
            f'selftest NG: もんだい{i + 1} paths={paths}'
    print(f'selftest OK: 手作り{len(HANDMADE)}問すべて「解が一意＝正解ルート」を確認')


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--with-planned', action='store_true',
                    help='作成予定の絵（WORDS_PLANNED）も語彙に含める')
    ap.add_argument('--count-a', type=int, default=30)
    ap.add_argument('--count-b', type=int, default=20)
    ap.add_argument('--seed', type=int, default=20260705)
    ap.add_argument('--out', default='tmp/mazes_generated.json')
    args = ap.parse_args()

    selftest()

    slug_by_word = {}
    vocab_map = dict(WORDS_AVAILABLE)
    if args.with_planned:
        vocab_map.update(WORDS_PLANNED)
    for slug, word in vocab_map.items():
        slug_by_word[word] = slug
    vocab = list(vocab_map.values())

    # 絵の実在チェック（planned はまだ無くてよいが、状況を表示する）
    img_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'img', 'nodes')
    missing = [s for s in vocab_map if not os.path.exists(os.path.join(img_dir, s + '.png'))]
    if missing:
        print(f'注意: 絵が未作成の slug: {" ".join(sorted(missing))}'
              f'（埋め込み前に img/nodes/ へ追加が必要）')

    rng = random.Random(args.seed)
    mazes = []
    for key, target in (('A', args.count_a), ('B', args.count_b)):
        selected, stats = generate_for_board(key, vocab, target, rng)
        print(f'\n盤面{key}: ルート{stats["routes"]}本 / 連鎖 ' +
              ' '.join(f'長さ{ln}:{n}本' for ln, n in sorted(stats['chains'].items())) +
              f' / 合格候補{stats["candidates"]}問 → 採用{len(selected)}問')
        for score, route, chain, words_at in selected:
            labels = [{'img': slug_by_word[words_at[p]], 'word': words_at[p]}
                      for p in range(BOARDS[key]['n'])]
            mazes.append({'board': key, 'labels': labels, 'solution': list(route),
                          'score': score, 'chain': '→'.join(chain)})

    out_path = args.out
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({'seed': args.seed, 'with_planned': args.with_planned,
                   'mazes': mazes}, f, ensure_ascii=False, indent=1)

    print(f'\n出力: {out_path}（{len(mazes)}問）')
    for i, m in enumerate(mazes):
        print(f'  {i + 1:2d}. [{m["board"]}] わな{m["score"]} '
              f'{"-".join(map(str, m["solution"]))}  {m["chain"]}')
    if not mazes:
        sys.exit(1)


if __name__ == '__main__':
    main()
