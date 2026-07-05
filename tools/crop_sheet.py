#!/usr/bin/env python3
"""
一覧シート画像（白背景）から、個々のイラストを切り出すツール。

使い方:
  1) 下の CONFIG を、新しいシート画像に合わせて編集
  2) python3 tools/crop_sheet.py
  3) tmp/contact.png（コンタクトシート）を目視で確認してから使う

仕組み: 行→列の「非白ピクセルの連続帯」を検出。行/列が期待数より
多く割れたときは、最小ギャップの隣接帯から順に結合して数を合わせる
（卵の2個・靴下の左右など、部品が分かれた絵をまとめられる）。
出力は img/nodes/<slug>.png（白の正方形キャンバス中央に配置）。

依存: Pillow(PIL) のみ（numpy不要）。
"""
from PIL import Image, ImageDraw
import os

# ===================== CONFIG =====================
SRC  = "img/sheet3.png"       # 元のシート画像（セット3・2026-07-05）
OUT  = "img/nodes"            # 出力先
ROWS = 3                       # 行数
COLS = 3                       # 各行の個数（全行同じ想定）
PAD  = 6                       # 切り出しの余白(px)
# 左上→右へ、行ごとに並ぶ順の slug（ROWS*COLS 個。ローマ字推奨）
WORDS = [
    "neko",    "shika",  "ushi",     # ねこ・しか・うし
    "masuku",  "mogura", "roketto",  # ますく・もぐら・ろけっと
    "biidama", "wani",   "uchiwa",   # びーだま・わに・うちわ
]
# ==================================================

def content(r,g,b):  # 白背景でなければ中身
    return not (r>=234 and g>=234 and b>=234)

def bands(counts, thresh, bridge, minlen):
    on=[c>thresh for c in counts]; segs=[]; i=0; n=len(on)
    while i<n:
        if on[i]:
            j=i
            while j<n and on[j]: j+=1
            segs.append([i,j-1]); i=j
        else: i+=1
    merged=[]
    for s in segs:
        if merged and s[0]-merged[-1][1] <= bridge: merged[-1][1]=s[1]
        else: merged.append(s[:])
    return [s for s in merged if s[1]-s[0] >= minlen]

def merge_to(band_list, want):
    m=[b[:] for b in band_list]
    while len(m) > want:
        gaps=[(m[k+1][0]-m[k][1],k) for k in range(len(m)-1)]
        _,k=min(gaps); m[k][1]=m[k+1][1]; del m[k+1]
    return m

def main():
    os.makedirs(OUT, exist_ok=True)
    im = Image.open(SRC).convert("RGB"); W,H = im.size; px = im.load()
    STEP=2
    def col_counts(y0,y1):
        c=[0]*W
        for x in range(0,W,STEP):
            n=0
            for y in range(y0,y1,STEP):
                r,g,b=px[x,y]
                if content(r,g,b): n+=1
            c[x]=n
        return c
    rc=[0]*H
    for y in range(0,H,STEP):
        n=0
        for x in range(0,W,STEP):
            r,g,b=px[x,y]
            if content(r,g,b): n+=1
        rc[y]=n
    row_bands = merge_to(bands(rc, thresh=14, bridge=8, minlen=70), ROWS)
    print("row_bands:", row_bands, "count=", len(row_bands))

    cells=[]
    for (y0,y1) in row_bands:
        cb = merge_to(bands(col_counts(y0,y1+1), thresh=6, bridge=18, minlen=25), COLS)
        for (x0,x1) in cb: cells.append((x0,y0,x1,y1))
    print("total cells:", len(cells), "expected", ROWS*COLS)

    def tight(x0,y0,x1,y1):
        mnx,mny,mxx,mxy=x1,y1,x0,y0; f=False
        for y in range(y0,y1+1):
            for x in range(x0,x1+1):
                r,g,b=px[x,y]
                if content(r,g,b):
                    f=True
                    mnx=min(mnx,x); mxx=max(mxx,x); mny=min(mny,y); mxy=max(mxy,y)
        return (mnx,mny,mxx,mxy) if f else None

    names=[]
    for idx,(x0,y0,x1,y1) in enumerate(cells):
        bb=tight(x0,y0,x1,y1)
        if not bb: continue
        mnx,mny,mxx,mxy=bb; w=mxx-mnx+1; h=mxy-mny+1; side=max(w,h)+PAD*2
        crop=im.crop((mnx,mny,mxx+1,mxy+1))
        canvas=Image.new("RGB",(side,side),(255,255,255))
        canvas.paste(crop,((side-w)//2,(side-h)//2))
        name=WORDS[idx] if idx<len(WORDS) else f"item{idx}"
        canvas.save(os.path.join(OUT,name+".png")); names.append(name)
        print(f"saved {name}.png {side}x{side}")

    # コンタクトシート
    os.makedirs("tmp", exist_ok=True)
    cell=150; labelh=20
    sheet=Image.new("RGB",(COLS*cell,ROWS*(cell+labelh)),(235,242,250))
    d=ImageDraw.Draw(sheet)
    for i,n in enumerate(names):
        im2=Image.open(os.path.join(OUT,n+".png")).convert("RGB"); im2.thumbnail((cell-14,cell-14))
        r,c=divmod(i,COLS); x=c*cell; y=r*(cell+labelh)
        sheet.paste(im2,(x+(cell-im2.width)//2,y+(cell-im2.height)//2))
        d.text((x+5,y+cell+3),n,fill=(0,0,0))
    sheet.save("tmp/contact.png")
    print("contact sheet -> tmp/contact.png（目視確認すること）")

if __name__=="__main__":
    main()
