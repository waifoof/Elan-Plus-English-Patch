"""Redraw the staff roll (ending credits) in English.

  python3 credits_labels.py [arc_dir] [out_bin_dir] [preview_dir] [siken_in] [table_json]

Defaults (relative to the repository): arc_dir work/arc/OUTPUT, out_bin_dir work/text/bin,
preview_dir (none), siken_in work/disc/GAME/SIKEN.BIN, table_json work/text/tables/SIKEN_BIN_credits.json

Where the staff roll comes from (see docs/ENGINE_NOTES.md, "Staff roll"):
  * The text is five 4bpp 248x240 TIMs, OUTPUT.BIN entries 0864-0868 (VRAM x 320/384/448/512/576,
    y 256, CLUT 768,496: index 0 transparent, 1 white, 2-14 greys = anti-aliasing). Each TIM holds
    the Japanese credit lines as blocks of 16-px rows.
  * The layout is a table in GAME/SIKEN.BIN at 0x2F864 (RAM 0x8009F864): 39 credit "pages", each a
    u32 count followed by count x 12-byte sprites:  u8 u, u8 v, u8 x, u8 y | u16 clut, u16 tpage |
    u16 w, u16 h.  tpage 21..25 = TIM 0864..0868. Most pages exist twice (clut 0xFC30 / 0x7C30,
    the fade and the hold version, same geometry). The scrolling pages (tpage 24/25) use y as an
    offset inside the scrolling strip.
English names are much wider than the kanji (many name sprites are only 64 px wide), so this
tool re-packs every referenced block in its TIM with the English drawn in it, and rewrites the
u, v, x and w of every sprite in the table (y, h, clut, tpage and the sprite count are unchanged;
each block is re-centred on the screen centre of its original glyphs). Two pages draw one line
from two sprites side by side; there the whole English line goes in the first sprite and the
other one points at a blank 8x16 area.

Outputs: out_bin_dir/0864..0868.bin (same size as the originals) and table_json:
  {"module": "GAME/SIKEN.BIN", "patches": [{"off": int, "orig": hex, "new": hex}]}
The build must apply those byte patches to GAME/SIKEN.BIN (after the code_text strings);
patch_siken(data) below does it and checks the original bytes.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from fontpath import FONTS
import json, os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timtool

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARC = os.path.join(_ROOT, 'work', 'arc', 'OUTPUT')
OUT = os.path.join(_ROOT, 'work', 'text', 'bin')
SIKEN = os.path.join(_ROOT, 'work', 'disc', 'GAME', 'SIKEN.BIN')
TABLE_JSON = os.path.join(_ROOT, 'work', 'text', 'tables', 'SIKEN_BIN_credits.json')
TABLE_OFF = 0x2F864
TPAGE_TIM = {21: 864, 22: 865, 23: 866, 24: 867, 25: 868}
FONT = FONTS + '/opentype/inter/Inter-Medium.otf'
SIZE = 13              # cap height ~9.5 px, like the original "Presented by"
BASE = 12              # baseline row inside a 16-row line slot (kanji sit on rows 1-13)
SS = 4                 # supersampling
MIN_SQUEEZE = 0.84     # narrowest horizontal squeeze before the font size is reduced
# grey level (0-31) of CLUT indices 1..14
LEVELS = [31, 28, 27, 25, 24, 22, 20, 19, 16, 14, 13, 11, 10, 8]

# ------------------------------------------------------------------ the credit blocks
# (tim, u, v, w, h): (Japanese lines, English lines[, options])
# options: 'keep' = original pixels (already English), 'blank' = second half of a split line,
#          'anchor': 'l' keeps the block's left edge (or puts it at 'lx'), 'cx': screen centre,
#          'maxw': widest line in px.
BLOCKS = {
    # 0864: cast, character design, game design & direction, planning & scenario
    (864, 8, 0, 48, 16): (['キャスト'], ['Cast']),
    (864, 0, 16, 64, 96): (['エイジ', 'ヨウ', 'カイリ', 'アマネ', 'ナツノ', 'トモエ'],
                           ['Eiji', 'Yoh', 'Kairi', 'Amane', 'Natsuno', 'Tomoe'], {'cx': 46}),
    (864, 64, 16, 88, 96): (['関 智一', '石田 彰', '千葉 進歩', '高山 みなみ', '黒崎 彩子', '川澄 綾子'],
                            ['Tomokazu Seki', 'Akira Ishida', 'Susumu Chiba', 'Minami Takayama',
                             'Ayako Kurosaki', 'Ayako Kawasumi'], {'anchor': 'l', 'lx': 79}),   # clear of Eiji's portrait
    (864, 0, 112, 64, 96): (['リコ', 'カナメ', 'ナルサワ', 'サカキ', 'レイ', 'サライ'],
                            ['Riko', 'Kaname', 'Narusawa', 'Sakaki', 'Rei', 'Sarai'], {'cx': 176}),
    (864, 64, 112, 88, 96): (['金月 真美', '半場 友恵', '三木 眞一郎', '伊藤 美紀', '岩田 光央', '保志 総一朗'],
                             ['Mami Kanetsuki', 'Tomoe Hanba', 'Shinichiro Miki', 'Miki Ito',
                              'Mitsuo Iwata', 'Soichiro Hoshi'], {'anchor': 'l', 'lx': 214}),
    (864, 0, 208, 128, 32): (['キャラクターデザイン', 'イラストレーション'], ['Character Design', 'Illustration']),
    (864, 168, 16, 64, 16): (['奈月 らん'], ['Ran Natsuki']),
    (864, 128, 208, 112, 16): (['ゲームデザイン ・'], ['Game Design & Direction'], {'cx': 160}),
    (864, 152, 192, 80, 16): (['ディレクション'], [''], {'blank': True}),
    (864, 160, 32, 80, 16): (['後藤 吉明'], ['Yoshiaki Goto']),
    (864, 56, 0, 112, 16): (['（企画室アロワナ）'], ['(Arowana Planning Office)']),
    (864, 128, 224, 112, 16): (['企画 ・ シナリオ'], ['Planning & Scenario']),
    (864, 160, 48, 80, 64): (['中沢 淳子', '柴田 亜紀子', '岡本 真弓', '東郷 裕美'],
                             ['Junko Nakazawa', 'Akiko Shibata', 'Mayumi Okamoto', 'Hiromi Togo']),
    # 0865: game production, programming, graphics, scenario assistance, mechanics, 3D, visual, sound
    (865, 64, 16, 72, 16): (['ゲーム制作'], ['Game Production']),
    (865, 0, 48, 144, 16): (['デジタルウェア株式会社'], ['Digitalware Inc.']),
    (865, 0, 0, 112, 16): (['ゲームプログラム'], ['Programming']),
    (865, 0, 16, 64, 32): (['大滝 恵二', '関口 博史'], ['Keiji Otaki', 'Hiroshi Sekiguchi']),
    (865, 0, 64, 112, 16): (['ゲームグラフィック'], ['Graphics']),
    (865, 16, 80, 80, 32): (['市川 晶章', '宮脇 達也'], ['Masaaki Ichikawa', 'Tatsuya Miyawaki']),
    (865, 16, 112, 80, 32): (['東郷 裕美', '奥富 舞巳'], ['Hiromi Togo', 'Maimi Okutomi']),
    (865, 16, 144, 80, 48): (['シナリオ協力', '山田 理子', '志村 美穂'],
                             ['Scenario Assistance', 'Riko Yamada', 'Miho Shimura']),
    (865, 0, 192, 112, 16): (['メカニックデザイン'], ['Mechanical Design']),
    (865, 24, 208, 64, 16): (['村田 護郎'], ['Goro Murata']),
    (865, 0, 224, 144, 16): (['（スタジオ・カムシャフト）'], ['(Studio Camshaft)']),
    (865, 128, 0, 80, 16): (['3Dモデリング'], ['3D Modeling']),
    (865, 152, 16, 64, 16): (['倉田 泰志'], ['Yasushi Kurata']),
    (865, 112, 32, 112, 16): (['ビジュアルデザイン'], ['Visual Design'], {'cx': 231}),
    (865, 152, 48, 64, 16): (['永田 毅'], ['Takeshi Nagata']),
    (865, 112, 64, 120, 16): (['（ソニー・ミュージック'], ['(Sony Music Communications)'], {'cx': 228, 'maxw': 164}),
    (865, 96, 80, 128, 16): (['コミュニケーションズ）'], [''], {'blank': True}),
    (865, 152, 96, 32, 16): (['作曲'], ['Music']),
    (865, 128, 112, 80, 16): (['神尾 憲一'], ['Kenichi Kamio']),
    (865, 112, 128, 112, 32): (['サウンドデザイン', '西川 博司'], ['Sound Design', 'Hiroshi Nishikawa']),
    (865, 104, 160, 128, 32): (['サウンドアシスタント', '保坂 求美'], ['Sound Assistant', 'Motomi Hosaka']),
    (865, 112, 192, 80, 16): (['サウンド制作'], ['Sound Production']),
    (865, 88, 208, 136, 16): (['ライトリンクミュージック'], ['Light Link Music Ltd.'], {'cx': 160}),
    (865, 144, 224, 56, 16): (['有限会社'], [''], {'blank': True}),
    # 0866: CG movie, voice casting, publicity
    (866, 112, 96, 112, 16): (['CGムービー制作'], ['CG Movie Production']),
    (866, 88, 112, 160, 48): (['株式会社ディジメーション', 'プロジェクトウズ', 'クロックワイズ'],
                              ['Digimation Inc.', 'Project Uzu', 'Clockwise']),
    (866, 0, 160, 80, 16): (['CGムービー'], ['CG Movie'], {'cx': 232}),   # CG Movie headings centred over role + names
    (866, 80, 160, 96, 16): (['プロデューサー'], ['Producer'], {'cx': 232}),
    (866, 16, 0, 80, 16): (['梶田 浩司'], ['Koji Kajita'], {'cx': 232}),
    (866, 0, 16, 104, 32): (['CGムービー監督', '滝川 和男'], ['CG Movie Director', 'Kazuo Takigawa'], {'cx': 232}),
    (866, 0, 176, 80, 16): (['CGムービー'], ['CG Movie'], {'cx': 232}),
    (866, 80, 176, 112, 16): (['アートディレクター'], ['Art Director'], {'cx': 232}),
    (866, 24, 48, 64, 16): (['副島 恵文'], ['Yoshifumi Soejima'], {'cx': 232}),
    (866, 0, 192, 80, 16): (['CGムービー'], ['CG Movie'], {'cx': 80}),
    (866, 80, 192, 88, 16): (['3Dデザイナー'], ['3D Designers'], {'cx': 80}),
    (866, 24, 64, 64, 32): (['栗原 一', '三浦 康一'], ['Hajime Kurihara', 'Koichi Miura'], {'cx': 80}),
    (866, 0, 208, 88, 16): (['4Dデザイナー'], ['4D Designer'], {'cx': 80}),
    (866, 24, 96, 64, 16): (['大嶋 慎介'], ['Shinsuke Oshima'], {'cx': 80}),
    (866, 88, 208, 136, 16): (['グラフィックデザイナー'], ['Graphic Designers'], {'cx': 80}),
    (866, 24, 112, 64, 32): (['坂上 幸子', '青木 洋'], ['Sachiko Sakagami', 'Hiroshi Aoki'], {'cx': 80}),
    (866, 112, 0, 112, 48): (['声優コーディネイト', '松岡 超', '（大沢事務所）'],
                             ['Voice Casting', 'Cho Matsuoka', '(Ohsawa Office)']),
    (866, 136, 48, 64, 48): (['広報', '三浦 紀子', '本田 明美'], ['Publicity', 'Noriko Miura', 'Akemi Honda']),
    # 0867: cooperating companies (scrolling)
    (867, 48, 0, 96, 16): (['開発制作協力'], ['Development Support']),
    (867, 48, 16, 96, 16): (['企画室アロワナ'], ['Arowana Planning Office']),
    (867, 24, 32, 144, 16): (['デジタルウェア株式会社'], ['Digitalware Inc.']),
    (867, 32, 48, 128, 16): (['有限会社ミントハウス'], ['Mint House Ltd.']),
    (867, 32, 64, 128, 16): (['スタジオ・カムシャフト'], ['Studio Camshaft']),
    (867, 16, 80, 160, 16): (['株式会社ディジメーション'], ['Digimation Inc.']),
    (867, 48, 96, 96, 16): (['音楽制作協力'], ['Music Production Support']),
    (867, 0, 112, 192, 16): (['有限会社ライトリンクミュージック'], ['Light Link Music Ltd.']),
    (867, 56, 128, 80, 16): (['大沢事務所'], ['Ohsawa Office']),
    (867, 48, 144, 96, 16): (['広報宣伝協力'], ['Promotion Support']),
    (867, 0, 160, 168, 16): (['株式会社ソニー・ミュージック'], ['Sony Music Communications Inc.'], {'cx': 160}),
    (867, 0, 176, 120, 16): (['コミュニケーションズ'], [''], {'blank': True}),
    (867, 0, 208, 208, 16): (['有限会社グランパパプロダクション'], ['Granpapa Production Ltd.']),
    # 0868: special thanks, producer, presented by
    (868, 0, 0, 120, 16): (['スペシャルサンクス'], ['Special Thanks']),
    (868, 24, 112, 80, 64): (['坂井 恭子', '大館 典子', '山田 輝広', '水谷 哲也'],
                             ['Kyoko Sakai', 'Noriko Odate', 'Teruhiro Yamada', 'Tetsuya Mizutani']),
    (868, 24, 176, 80, 16): (['内村 恵'], ['Megumi Uchimura']),
    (868, 0, 224, 136, 16): (['（ビギナーズレーベル）'], ['(Beginners Label)']),
    (868, 120, 0, 112, 16): (['ビスコスタッフ一同'], ['All VISCO Staff']),
    (868, 136, 16, 72, 16): (['and You.'], ['and You.'], {'keep': True}),
    (868, 128, 32, 96, 16): (['プロデューサー'], ['Producer']),
    (868, 136, 48, 80, 16): (['中沢 淳子'], ['Junko Nakazawa']),
    (868, 120, 64, 112, 32): (['Presented by', 'VISCO'], ['Presented by', 'VISCO'], {'keep': True}),
}
# Lines in the TIMs that no table sprite shows (left over from Élan): logged only, not drawn.
UNUSED = [
    (867, '株式会社ムービック', 'Movic Co., Ltd.'),
    (868, '前田 愛 ちゃん', 'Ai Maeda'), (868, '前田 亜季 ちゃん', 'Aki Maeda'),
    (868, '豊田 久代', 'Hisayo Toyoda'), (868, '工藤 長', 'Osamu Kudo'),
    (868, '岩橋 崇', 'Takashi Iwahashi'), (868, '近沢 晋治', 'Shinji Chikazawa'),
    (868, '（ソニー・ミュージック / コミュニケーションズ）', '(Sony Music Communications)'),
]


# ------------------------------------------------------------------ TIM helpers
def load_tim(arc, n):
    d = bytearray(open(os.path.join(arc, f'{n:04d}.bin'), 'rb').read())
    t = timtool.parse(d, 0)
    raw = np.frombuffer(bytes(d[t['pix']:t['pix'] + t['w'] * t['h'] // 2]), np.uint8).reshape(t['h'], t['w'] // 2)
    px = np.zeros((t['h'], t['w']), np.uint8)
    px[:, 0::2] = raw & 15
    px[:, 1::2] = raw >> 4
    return d, t, px


def store_tim(d, t, px):
    raw = (px[:, 0::2] | (px[:, 1::2] << 4)).astype(np.uint8)
    d[t['pix']:t['pix'] + raw.size] = raw.tobytes()
    return d


# ------------------------------------------------------------------ text rendering
def text_width(text, size, sq):
    return ImageFont.truetype(FONT, size * SS).getlength(text) * sq / SS


def fit(text, maxw):
    """-> (size, squeeze) so the line is at most maxw px wide."""
    for size in (SIZE, 12.5, 12, 11.5, 11):
        w = text_width(text, size, 1.0)
        if w <= maxw:
            return size, 1.0
        if w * MIN_SQUEEZE <= maxw:
            return size, maxw / w
    return 11, maxw / text_width(text, 11, 1.0)


def render_line(text, size, sq):
    """-> uint8 array (16, w) of CLUT indices."""
    font = ImageFont.truetype(FONT, size * SS)
    W = int(font.getlength(text)) + 4 * SS
    img = Image.new('L', (W, 16 * SS), 0)
    ImageDraw.Draw(img).text((2 * SS, BASE * SS), text, font=font, fill=255, anchor='ls')
    w = max(1, int(round(W * sq / SS)))
    a = np.asarray(img.resize((w * SS, 16 * SS), Image.LANCZOS), np.float32)
    a = a.reshape(16, SS, w, SS).mean((1, 3)) / 255.0
    a = np.clip(a * 1.15, 0, 1)            # slightly brighter stems, like the white kanji strokes
    out = np.zeros(a.shape, np.uint8)
    lv = np.array(LEVELS, np.float32)
    on = a >= 0.22
    g = a * 31
    idx = np.abs(g[..., None] - lv[None, None, :]).argmin(-1) + 1
    out[on] = idx[on]
    cols = np.where(out.any(0))[0]
    return out[:, cols.min():cols.max() + 1] if cols.size else out[:, :0]


# ------------------------------------------------------------------ layout table
def read_table(siken):
    pages, o = [], TABLE_OFF
    while True:
        n, = struct.unpack_from('<I', siken, o)
        if not 0 < n <= 12:
            break
        ents = []
        for k in range(n):
            eo = o + 4 + 12 * k
            a, b, c = struct.unpack_from('<III', siken, eo)
            ents.append(dict(off=eo, u=a & 255, v=(a >> 8) & 255, x=(a >> 16) & 255, y=a >> 24,
                             clut=b & 0xFFFF, tp=b >> 16, w=c & 0xFFFF, h=c >> 16))
        pages.append(ents)
        o += 4 + 12 * n
    return pages


def glyph_box(px, u, v, w, h):
    sub = px[v:v + h, u:u + w]
    cols = np.where(sub.any(0))[0]
    return (int(cols.min()), int(cols.max())) if cols.size else (0, w - 1)


def build_blocks(px_by_tim):
    """Render every block: -> {key: pixel array (h, w_new)}, {key: left/centre info}"""
    pix, info = {}, {}
    for key, spec in BLOCKS.items():
        tim, u, v, w, h = key
        jp, en = spec[0], spec[1]
        opt = spec[2] if len(spec) > 2 else {}
        src = px_by_tim[tim]
        g0, g1 = glyph_box(src, u, v, w, h)
        info[key] = dict(g0=g0, g1=g1, opt=opt)
        if opt.get('keep'):
            pix[key] = src[v:v + h, u:u + w].copy()
            continue
        if opt.get('blank'):
            pix[key] = None
            continue
        assert len(en) == h // 16, key
        maxw = opt.get('maxw', 236)
        lines = [render_line(t, *fit(t, maxw)) if t else np.zeros((16, 0), np.uint8) for t in en]
        bw = max(8, max(l.shape[1] for l in lines) + 2)
        bw = (bw + 3) & ~3
        blk = np.zeros((h, bw), np.uint8)
        for i, l in enumerate(lines):
            if opt.get('anchor') == 'l':
                x0 = 1
            else:
                x0 = (bw - l.shape[1]) // 2
            blk[16 * i:16 * i + 16, x0:x0 + l.shape[1]] = l
        pix[key] = blk
    return pix, info


def pack(items, bins, W=248, H=240):
    """Shelf packer over several TIMs. items {key: (w, h)}; a block goes into its own TIM (key[0])
    when it fits, else into another one. -> {key: (tim, u, v)}"""
    shelves = {b: [] for b in bins}               # [y, h, used_x]
    top = {b: 0 for b in bins}
    pos = {}
    for k in sorted(items, key=lambda k: (-items[k][1], -items[k][0])):
        w, h = items[k]
        order = [k[0]] + [b for b in bins if b != k[0]]
        for b in order:
            best = None
            for s in shelves[b]:
                if s[1] >= h and s[2] + w <= W and (best is None or s[1] < best[1]):
                    best = s
            if best is None and top[b] + h <= H:
                best = [top[b], h, 0]
                shelves[b].append(best)
                top[b] += h
            if best is not None:
                pos[k] = (b, best[2], best[0])
                best[2] += w
                break
        else:
            raise SystemExit(f'block {k} does not fit in any TIM')
    return pos


def main(arc=ARC, out=OUT, preview=None, siken_path=SIKEN, table_json=TABLE_JSON):
    siken = bytearray(open(siken_path, 'rb').read())
    pages = read_table(siken)
    tims = {n: load_tim(arc, n) for n in TPAGE_TIM.values()}
    px_by_tim = {n: t[2] for n, t in tims.items()}
    # every referenced block must be described
    used = {(TPAGE_TIM[e['tp']], e['u'], e['v'], e['w'], e['h']) for p in pages for e in p if e['tp'] in TPAGE_TIM}
    missing = used - set(BLOCKS)
    assert not missing, missing
    pix, info = build_blocks(px_by_tim)
    items = {k: (p.shape[1], p.shape[0]) for k, p in pix.items() if p is not None}
    for n in tims:
        items[(n, 'blank')] = (8, 16)
    pos = pack(items, list(tims))
    canvas = {n: np.zeros_like(px_by_tim[n]) for n in tims}
    for k, (b, pu, pv) in pos.items():
        if k[1] != 'blank':
            p = pix[k]
            canvas[b][pv:pv + p.shape[0], pu:pu + p.shape[1]] = p
    os.makedirs(out, exist_ok=True)
    for n in tims:
        d, t, _ = tims[n]
        store_tim(d, t, canvas[n])
        open(os.path.join(out, f'{n:04d}.bin'), 'wb').write(d)
        mine = [k for k, q in pos.items() if q[0] == n]
        moved = [k for k in mine if k[0] != n]
        print(f'{n:04d}: {len(mine)} blocks ({len(moved)} moved in from other TIMs), '
              f'rows used {max(pos[k][2] + items[k][1] for k in mine)}/240')
    TIM_TPAGE = {n: tp for tp, n in TPAGE_TIM.items()}
    # rewrite the table
    patches = []
    shots = []
    for pi, page in enumerate(pages):
        layout = []
        for e in page:
            if e['tp'] not in TPAGE_TIM:
                continue
            n = TPAGE_TIM[e['tp']]
            key = (n, e['u'], e['v'], e['w'], e['h'])
            inf = info[key]
            if pix[key] is None:                       # second half of a split line
                b, nu, nv = pos[(n, 'blank')]
                nw, nx, nh = 8, e['x'], 16
            else:
                b, nu, nv = pos[key]
                nw = pix[key].shape[1]
                nh = e['h']
                opt = inf['opt']
                if opt.get('keep'):
                    nx = e['x']
                elif opt.get('anchor') == 'l':
                    nx = opt['lx'] - 1 if 'lx' in opt else e['x'] + inf['g0'] - 1
                else:
                    cx = opt.get('cx', e['x'] + (inf['g0'] + inf['g1'] + 1) / 2)
                    nx = int(round(cx - nw / 2))
                nx = max(0, min(nx, 320 - nw, 255))
            tp = TIM_TPAGE[b]
            a = nu | nv << 8 | nx << 16 | e['y'] << 24
            c = nw | nh << 16
            new = struct.pack('<III', a, e['clut'] | tp << 16, c)
            old = bytes(siken[e['off']:e['off'] + 12])
            if new != old:
                patches.append({'off': e['off'], 'orig': old.hex(), 'new': new.hex()})
            layout.append((b, nu, nv, nw, nh, nx, e['y']))
        if layout and page[0]['clut'] != 0xFC30:
            shots.append((pi, layout))
    os.makedirs(os.path.dirname(table_json), exist_ok=True)
    json.dump({'module': 'GAME/SIKEN.BIN', 'note': 'staff roll layout table, see tools/credits_labels.py',
               'patches': patches}, open(table_json, 'w'), indent=1)
    print(f'{len(patches)} table sprites changed -> {table_json}')
    if preview:
        os.makedirs(preview, exist_ok=True)
        sheet = Image.new('RGB', (4 * 320, ((len(shots) + 3) // 4) * 240), (0, 0, 0))
        lut = np.array([[0, 0, 0]] + [[l * 255 // 31] * 3 for l in LEVELS] + [[8, 8, 8]], np.uint8)
        for i, (pi, layout) in enumerate(shots):
            scr = np.zeros((240 + 256, 320, 3), np.uint8)
            scr[:] = (16, 16, 48)
            for n, u, v, w, h, x, y in layout:
                blk = canvas[n][v:v + h, u:u + w]
                if y + h > scr.shape[0]:
                    continue
                reg = scr[y:y + h, x:x + w]
                m = blk[:, :reg.shape[1]] > 0
                reg[m] = lut[blk[:, :reg.shape[1]][m]]
            im = Image.fromarray(scr[:240])
            ImageDraw.Draw(im).text((2, 2), f'page {pi}', fill=(255, 255, 0))
            sheet.paste(im, ((i % 4) * 320, (i // 4) * 240))
        sheet.save(os.path.join(preview, 'credits_pages.png'))
        for n in tims:
            Image.fromarray(lut[canvas[n]]).resize((496, 480), Image.NEAREST).save(os.path.join(preview, f'tim{n}.png'))


def patch_siken(data, table_json=TABLE_JSON):
    """Apply the layout-table patches to GAME/SIKEN.BIN (bytes -> bytes, same size)."""
    d = bytearray(data)
    for p in json.load(open(table_json))['patches']:
        o, old, new = p['off'], bytes.fromhex(p['orig']), bytes.fromhex(p['new'])
        assert d[o:o + len(old)] == old, f'SIKEN.BIN @{o:X}: unexpected bytes'
        d[o:o + len(new)] = new
    return bytes(d)


if __name__ == '__main__':
    defaults = [ARC, OUT, None, SIKEN, TABLE_JSON]
    args = sys.argv[1:] + defaults[len(sys.argv) - 1:]
    main(*[None if x in ('', '-') else x for x in args[:5]])
