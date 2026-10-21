# Engine notes

Technical reference for Élan Plus (SLPS-02759) as far as the translation needed it: the disc, the
archives, the script bytecode, the text engine and font, the graphics and movies, and how the patch
changes them. Offsets are hexadecimal; "entry NNNN" means entry NNNN (decimal) of `GAME/OUTPUT.BIN`.

## Contents

- [Disc](#disc)
- [Archives](#archives)
- [Script bytecode](#script-bytecode)
- [Font and the pair encoding](#font-and-the-pair-encoding)
- [Interface strings in the code](#interface-strings-in-the-code)
- [Pointer-indexed files: mail and conversations](#pointer-indexed-files-mail-and-conversations)
- [Graphics](#graphics)
- [Movies](#movies)
- [Talk help overlay (R2)](#talk-help-overlay-r2)
- [Staff roll](#staff-roll)
- [Extras](#extras)
- [Game state, partners and endings](#game-state-partners-and-endings)
- [Testing notes](#testing-notes)
- [Tools](#tools)

## Disc

- Single track, MODE2/2352, 247,288 sectors. Extracting with dumpsxiso and rebuilding with mkpsxiso
  gives a byte-identical image.
- `SLPS_027.59` (the EXE): loads at `0x80010000`, entry point `0x8001CAB4`.
- Overlays `GAME/GAME.BIN`, `GAME/TITLE.BIN` and `GAME/SIKEN.BIN` load at `0x80070000`.
  `FONT.BIN` (text engine and font) loads at `0x801B0000`.
- The game finds its files by name (`\GAME\*.XA;1` and so on). The patched disc keeps every file at
  its original LBA; the rebuilt `OUTPUT.BIN` is appended at the end of the disc and its ISO directory
  record and the PVD volume size are patched. The game reads the new location (verified). This is why
  the patched image is about 45 MB larger.
- Some loaders (for example the prologue overlay) read `OUTPUT.BIN` entries at their original LBAs.
  As a safety net, the build also writes every changed entry that still fits its original allocation
  back into the old `OUTPUT.BIN` extent, sector by sector, keeping each sector's subheader
  (`mirror_old_output` in `build_patch.py`).
- Every rewritten sector gets fresh EDC/ECC (`cdsector.py`).

## Archives

`GAME/ELANPLUS.BIN` and `GAME/OUTPUT.BIN` share one format:

- Header: a list of `u32 start_sector, u32 count` pairs (relative to the archive), terminated by zero.
- Entries are sector-aligned.
- The repacker keeps every entry's original allocation as a minimum size.

What is where in `OUTPUT.BIN`, as far as the translation is concerned:

| Entries | Contents |
|---|---|
| ~0111-0681 | event scripts (story scenes) |
| 0834-0843 | mail: replies 0834-0841, developers' test mail 0842, monthly exam notices 0843 |
| 0864-0868 | staff roll text (TIMs) |
| 0921-0929 | overlays with pointer-indexed SJIS strings (0922-0929: each candidate's conversation-ending lines) |
| 0930-0977 | free-roam conversations |
| 0514, 0519, 0538, 0847, 0870, 0986, 0988, 0995, 0997 | UI texture atlases (see [Graphics](#graphics)) |

Entries around 0102 that start with 16 zero bytes followed by `46 04 ...` are SPU ADPCM sound
samples, not images.

## Script bytecode

Event scripts (entries ~0111-0681) are bytecode run by an interpreter in the EXE at `0x8001754C`
(jump table at `0x80010304`, opcodes `0x01`-`0x38`; the script pointer is at `ctx+24`).

### Opcode lengths (bytes, including the opcode)

| Opcodes | Length | Notes |
|---|---|---|
| 01-06 | 3 | |
| 07-0C | 2 | |
| 0D-12 | 1 | |
| 13, 14 | 3 | |
| 15 | 2 | wait |
| 16 | variable | text |
| 17 | 1 | wait for text |
| 18, 19 | 2 | |
| 1A | 2 | |
| 1B-1E | 1 | |
| 1F | 3 | goto |
| 20 | variable | menu (choice) |
| 21, 22 | 2 | |
| 23, 24 | 3 | `23 <u16>` sets a flag (see [endings](#game-state-partners-and-endings)) |
| 25, 26 | 5 | conditional goto; `25` = "player is female" |
| 27-2D | 2 | |
| 2E | 4 | |
| 2F | 3 | |
| 30 | 1 | |
| 31, 32 | 2 | |
| 33-36 | 1 | |
| 37 | 2 | |
| 38 | 4 | if-goto |

### Text and choices

- Text: `16 <2-byte characters> (81 84 | 81 90) <1 byte>`. The text is scanned 2 bytes at a time.
- Menu `0x20`: always 2 options, each `{u16 off, text, 00}`; target = field + 2 + off.

### Jumps

All jumps are relative, so the rebuilt scripts must have every jump relocated when the text changes
length:

| Op | Target |
|---|---|
| `1F` | op + 3 + s16 |
| `38` | op + s16 (s16 at +2) |
| `25`, `26` | op + 5 + s16 (s16 at +3) |
| `20` options | field + 2 + off |

All 554 `0x25`/`0x26` jumps in the original land on instruction starts. `elanscript.parse` records
every jump target and `insert_script.rebuild_event` relocates them; after rebuilding, each scene is
re-parsed and every jump (`1F`, `38`, the `20` options, `25`, `26`) is checked to point at the same
instruction index as in the original. (Before the `25`/`26` jumps were relocated, playing as a woman
could freeze at choice menus.)

### Inline markup

The text uses full-width characters as markup: `＊name＊` name plate, `＠ddd＿ddd` voice clip,
`￥` line break, `＝` page break, `；` player name, `｝` pause-like control code, `｛n` effect,
`＜n` speed, `－　...　－` caption. See [TRANSLATING.md](TRANSLATING.md#markup-codes) for the rules.

The empty name-plate box shown briefly after picking a choice is original behaviour (checked on the
Japanese disc).

## Font and the pair encoding

- `FONT.BIN` at `0x36FA` holds JIS X 0208 level 1 (3,489 glyphs) packed in JIS order, 22 bytes per
  glyph: 11 rows of u16, MSB first, 12 px wide used. A glyph's slot is its rank among the defined JIS
  codes.
- English is written as **two 6-px letters per glyph** (the "pair" encoding, `pairfont.py`, with the
  6x11 letter shapes in `enfont.py`). The letter pairs the script needs are assigned to kanji slots,
  using slots the game never uses first. The table of pairs is written to `out/pairs.json`.
- The renderer also draws the previous slot's bottom row above each glyph. Kanji slots have rows 0
  and 10 cleared and letter pairs are drawn one row higher (rows 0-9), so nothing leaks into the
  neighbouring glyph (this was the "stray dots and bars" fixed in v0.4).
- The dialogue box shows 33 characters per line; a wide 33rd letter can touch the frame, so the
  validator enforces 32. Three lines per box.
- The player's name is stored as full-width characters: each letter takes a full Japanese cell,
  which is why typed names have gaps and `；` counts as 8 letters of width (4 cells).

## Interface strings in the code

- Interface strings are Shift-JIS in `GAME.BIN`, `SIKEN.BIN`, `TITLE.BIN` and the EXE. They are
  written in place, within the original byte length (`code_text.py`; the `"max"` field of a `code`
  row).
- Weekday, week, day and rank labels are one-glyph strings (`GAME_BIN` `0x758`..., `0x10C8`...,
  `0x14BC`..., `TITLE_BIN` `0x2C4`...) translated as 2-byte rows.
- The age counter on the Partner Selection panel is a 2-byte string in `SIKEN.BIN` at `0x1B9C`
  ("yo").
- Overlays 0921-0929 (loaded at `0x80160000` / `0x80190000`) contain SJIS strings reached through
  pointers. They are patched in place as `code` files with `"module": "OUTPUT:NNNN"`
  (`translation/code/OUTPUT_092x.json`).
- The SJIS copy of the prologue captions in 0921 is not what is shown on screen; the captions are
  burned into the movie (see [Movies](#movies)).

## Pointer-indexed files: mail and conversations

### Layout

Mail (0834-0843) and conversation (0930-0977) files share one layout:

- a u32 header;
- NUL-terminated messages, each padded to a 4-byte boundary;
- a table of RAM pointers (base `0x80160000`) to the message starts.

`GAME.BIN` holds each table's RAM address: the lists are at `0x39C5C` (0930-0977) and
`0x326EC` / `0x32714` (0834-0843). `indexed.py` rebuilds the messages, keeps each table at its
original offset when the English fits, and otherwise moves it and rewrites the address in `GAME.BIN`.
`build_patch.py` verifies every table after each build. (Before this, talking to a candidate or
reading the day-to-day mail froze the game.)

### Mail (0834-0843)

- Records are split by `00 00 00 00` (shown as `{00}{00}` between messages in the JSON).
- The 32 ALPHA DATABASE hint entries repeat in every mail file, with identical English.
- 0843 holds the monthly exam notices; its last row ends in binary data that is re-appended from
  the original (`tail_len`).
- 0842 (the developers' test mail) is a one-message pointer-indexed file whose table is not listed
  in `GAME.BIN`. Its text must stay short enough to keep the table at offset `0x20`.

### Conversations (0930-0977)

- A full-width markup language: `＊speaker＊`, `￥`, `＋％option％：label`, `＃label`, `＝：goto`, `｝`.
  It is label-based, with no byte offsets, so the text can change length freely.
- The bytes after the last `＃ｅ＞{00}` of each file are a stale table of RAM pointers
  (`0x8016xxxx`; only about a quarter of them land on block starts, even in the original). The
  engine doesn't use it; the build copies it verbatim (`"trailer": true`).
- 0975's header value `0x10` looks like a TIM magic number, so a naive classifier mistakes it for an
  image; it is a conversation file like the others.

## Graphics

UI text drawn as images was redrawn in English. Labels are rendered with TrueType fonts (bundled in
`fonts/`): **Inter SemiBold 11**, with **Carlito Bold** as the narrow fallback, centred at natural
size. (An earlier 5x10 pixel font stretched to the box height looked rough.)

### Atlases

| Where | Contents | Tool |
|---|---|---|
| 0514 @ `0x17AB4`, 0847 @ `0x220` | 4bpp UI atlas: location labels, name tags, stats, "Send" tag | `labels.py` |
| 0514 @ `0x1F4D4` (VRAM x=768 words, y=256; 246 rows) | facility menu atlas: Rest, Load, Save, Rapport, Leave, Send Mail, Exam Info, Talk, Start Training, Cancel, Solo, Joint, "for Help", Candidates, Exam Results, Weekly Results, Results, Mood, Show, Okay, Shift; the Talk help word cells | `labels.py`, `help_labels.py` (see [Talk help overlay](#talk-help-overlay-r2)) |
| 0538 @ 0, 0519 @ `0x8234` | options/prompt atlas: "Choose a destination", mail prompts, Yes/No, Extras, Interviews, Partner Select, Quit | `tim_labels.py` |
| 0997 (8bpp) | name-entry screen | `tim_labels.py` |
| 0995 (8bpp) | gender and confirmation prompts | `tim_labels.py` |
| 0870 | banners: Group Meeting / Total / Rank / Exam | `tim_labels.py` |
| 0988, 0986, `GAME/ELANPLUS.BIN` | Extras screens | `extras_labels.py` (see [Extras](#extras)) |
| 0864-0868 | staff roll | `credits_labels.py` (see [Staff roll](#staff-roll)) |

`tim_labels.py` is palette-aware and handles 4bpp and 8bpp TIMs, with an optional restore of the
grid background.

### Palettes

Read from the game's sprite data:

- 0538/0519 prompts use 0538 CLUT row 13 (1 = white ... 15 = navy).
- Title-menu EXTRAS / INTERVIEWS use row 10 (visible windows u192-231 and u120-207).
- The Partner Select banner is 0538's pixels drawn with 0870's CLUT row 13.
- In 0514, the room banner uses row 13, the map list row 6, and the name tags row 11 (male and
  female tags use different ramps on that row).
- `tim_labels.Tim(data, off, pal)` / `set_pal()` pick the row per job.
- The 0870 banners are drawn with a grey CLUT over the bar, where thin 1-px text vanishes.
  `tim_labels.draw_ttf()` renders them as bold oblique TrueType with a 1-px palette-15 outline, a
  palette-13 drop shadow and a vertical gradient (indices 11, 1..8).
- Location labels use a vertical ramp over the original glyph's brightest indices. Carlito is
  rendered hinted 1-bit so that i-dots stay separate.

### Composite sprites

Several on-screen prompts are made of two sprites, as in the Japanese, so the English has to be
split the same way:

- The meeting prompt "Who will you talk to?" = the mail prompt's x0-23 ("Who") + 0538 x136-212
  ("will you talk to?").
- Partner Selection "Partner? Choose one." = 0538 x89-137 + the destination prompt's tail x161-247.
  The map shows the head x121-160 ("Where?") + the same tail. In 0538/0519, "Partner" must stay left
  of x=127 (the "Talk to them?" sprite starts at x=128).
- Training buttons: the Solo/Joint cell is 31 px wide and the shared cell shows about 80 px, so the
  shared cell reads "Training" and the buttons read "Solo Training" / "Joint Training". The headers
  are "Solo Training" = Solo x0-23 + x48-59 (kept blank) + Training, and "Joint Training" = x24-59 +
  Training.
- The results panel draws the "Weekly Results" and "Candidates" sprites under "Exam Results"; their
  top rows peek out above it, so those rows must stay empty. Weekly Results text starts at row 87.

### Sprite windows

The game's sprite windows don't always match the old glyph extents. Measured examples:

- In the 0514 menu atlas, sprite rectangles are taller than the glyphs: keep text 2 rows clear of
  neighbouring labels (Candidates/Stage end at row 89; Weekly Results is drawn in rows 85-96 with
  84-97 cleared).
- In the 0514 label atlas (rows 56-70), the Flight Rm window ends at x111 and High-G Rm starts at x112.
- HELP next to the R2 icon shows only rows ~48-55 (hand-drawn 5x6 capitals).

### Left as they are

- "POINTS", stacked as POI/NTS in the results tables, is the original game's own English art (0870).
- The day-change card's "Wednes day" and "Time to the Final test" are also original English art.

## Movies

All movies are in `MOVIE/` as MDEC `.STR` files with interleaved XA audio. `OP.STR` and `ED.STR`
contain no Japanese text. The changed movies are re-encoded in place with jPSXdec, so they keep
their size and their audio and timing; `movies.py` runs the whole process (index, decode the frames
needed, redraw, `-replaceframes`) and writes `work/text/movie/`, which `build_patch.py` copies onto
the disc.

jPSXdec is built from [m35/jpsxdec](https://github.com/m35/jpsxdec) with its bundled Ant script and
the `-Werror` flag removed. It indexes the file and re-encodes only the changed macroblocks:
`-x <file>.idx -i 0 -replaceframes replace.xml`.

### Prologue (`PR.STR`)

- 320x240, 1,327 frames, 10 sectors per frame, 7 burned-in captions.
- `str_captions.py`, per caption: finds the Japanese glyph pixels against a clean plate taken 6
  frames before the fade-in, restores them from the plate, draws the English lines (DejaVu Sans
  Condensed 12 px, soft shadow, slight blur to help the encoder) at the original line positions,
  and writes a jPSXdec partial-replace XML limited to the caption band.
- The scene's fade level is measured per frame around each caption and applied to both the restored
  background patch and the English text. Every line of a caption starts at one left edge.

### Exam title cards (`TEST01.STR`-`TEST09.STR`)

- The monthly exam title card is not a texture: each exam has a 240-frame movie (`TEST09` = the
  final exam). The card cross-fades in at about frame 197 and holds to frame 239.
- `exam_cards.py` rebuilds the card (the Japanese erased from the 96x32 repeating brick background,
  the English drawn) and then writes `frame + t * (new card - old card)` for each card frame.
- "MONTHLY EXAM" labels are 14-px bold oblique (N-T kerned); the exam titles sit on a common baseline.
- `TEST09` is different: the card assembles from flying "WARNING" tiles from about frame 193, and
  the Japanese title is drawn above the tiles. `tiles9()` treats the card as static under the tiles,
  matches card pixels per tile and paints out leftover white title pixels.

## Talk help overlay (R2)

- On the Talk screen, **holding** R2 (the "R2 HELP" icon above the mood panel) shows labels with
  leader lines that explain the panel. It is shown only while R2 is held, and only on this screen:
  the room, map, facility, bed menu and mail screens have no R2 help.
- The labels are a sprite list in `GAME/GAME.BIN` at `0x2F974` (RAM `0x8009F974`; `GAME.BIN` and
  `SIKEN.BIN` are loaded at `0x80070000`, so RAM = `0x80070000` + file offset). Layout as in the
  staff-roll table: a u32 count (51), then 12-byte sprites `u8 u, u8 v, u8 x, u8 y | u16 clut,
  u16 tpage | u16 w, u16 h`. The one-sprite list just before it (`0x2F964`) is the "HELP" label.
- Drawing routine `0x80014360(x, y, list, prim buffer, OT slot)`, called from `0x800795E0` while the
  flag at `*(0x801C9DE0) + 2` is set. It reads the count from the list, so a list can be made
  shorter. It builds textured quads: tpage bit `0x4000` mirrors a sprite horizontally (the closing
  parentheses are the opening one mirrored), bit `0x8000` vertically; clut bit `0x8000` turns on
  semi-transparency. `u + w` is stored in a byte, so it must stay below 256. The leader lines are
  separate line primitives (not in the list).
- Sprites 0-46 were text in the 0514 menu atlas (tpage `0x3C` = VRAM 768,256; CLUT `0x3EBC` =
  VRAM 960,250, a grey ramp: 1 near-black ... 14 near-white, glyphs white with a dark outline on a
  transparent ground). They were word and single-kana fragments, several of them shared with the
  mood panel and menus (気分, 普通, 表示, 変化, 好感度, 育成結果, 段階内), which is why redrawing those
  cells in English gave mixed lines such as "Rapport レベル (6 Stag)". Sprites 47-50 are the four
  coloured arcs of the mood legend (CLUT `0x3C7C`).
- The fragments used only by this overlay are the block u48-127 v112-175 of the menu atlas
  (ゲージ 振 切ると / レベル 哀しい / 赤 怒 緑 青 黄 / 楽 が によ ６ （ ８ り); no other sprite list in the
  code modules or `OUTPUT.BIN` points there. u0-47 v165-206 is empty in the original atlas.
- `help_labels.py` (run after `labels.py`) clears that block and draws 16 English word cells there
  and in the empty area (Carlito Bold 11, hinted, white with a 1-px dark outline; words used on
  several lines share a cell), then writes a new 37-sprite list: the English lines word by word,
  the original ▲/▼ sprites, the four arcs. The colour kanji on the arcs are dropped (the arcs show
  the colours) and the legend uses the panel's own mood words (Normal, Anger, Sad, Happy). The list
  goes to `work/text/tables/GAME_BIN_help.json`; `build_patch.py` applies it to `GAME.BIN` after the
  pointer-table step.
- Leader lines on screen: y36 x64-215 (under line 1), y60 x48-216 (between "Rapport gauge" and its
  note), y104 x24-243 (under "Mood gauge"), y209 x128-255 (under "Mood level"), and a vertical line
  at x≈257. Text is kept above or below them and left of the diagonals to the panel.

## Staff roll

- The staff roll is **not** in `ED.STR` (that holds only the ending CG). Its text is five 4bpp
  248x240 TIMs, `OUTPUT.BIN` entries **0864-0868** (VRAM x 320-576, y 256), all resident for the
  whole roll.
- The layout is a sprite table in `GAME/SIKEN.BIN` at `0x2F864` (RAM `0x8009F864`): 39 pages of
  12-byte sprites (`u, v, x, y, clut, tpage, w, h`).
- `credits_labels.py` redraws every block (Inter Medium 13), repacks them over the five TIMs and
  rewrites `u/v/x/w/tpage` of 143 sprites. The new table goes to
  `work/text/tables/SIKEN_BIN_credits.json`; `build_patch.py` applies it after the code strings.
- Where the original splits a line over two sprites side by side, the whole English line goes in
  the first sprite.

## Extras

- Entry 0988 (8bpp, VRAM 320,0): the Interviews/Gallery list (name panels, headers, help bar).
- Entry 0986 (8bpp, VRAM 448,0): a character's interview page (name plates, the 4 questions, light
  and dark copies).
- The Gallery page help is in `GAME/ELANPLUS.BIN` (frame TIM at `0x27800` and a copy at `0xBD32C`,
  right strip at `0xBB80C`). `extras_labels.py` writes a same-size `work/text/elanplus/ELANPLUS.BIN`,
  which `build_patch.py` copies onto the disc.
- Extras appear on the title menu only when the clear data has unlock flags (RAM
  `0x800527A0`..`A5`).

## Game state, partners and endings

### RAM

- Week: `0x800510BD`. Day counter: u16 at `0x800510D0` (`(week - 1) * 7 + 1` = Monday).
- Exam list: `0x800510F8` (ends with `09` for the final exam).
- 9 character records at `0x80051120`, `0x50` bytes each. Records 1-8 are Eiji, Yoh, Kairi, Amane,
  Natsuno, Tomoe, Riko, Kaname. Fields: `+0x02` rank history (one byte per month), `+0x0E` total
  points, `+0x24` stats, `+0x44` rapport (s16), `+0x49` mood index (Hate ... Love).

### Partners and endings

- The final exam is in week 24, on Saturday. Qualification goes by total points (`+0x0E`), not stats.
- A candidate accepts you as partner when their record has rapport `+0x44` >= 48 and mood `+0x49`
  >= 2 (check in `SIKEN.BIN` code at `0x80091538`). The accept variant comes from the rank byte `+0x02`.
- Staff endings: flags at RAM `0x8005106C`. Flag 39 leads to scene 0161 (Narusawa; `0x80051070`
  bit 7); flags 40/41/42 lead to 0163 Sakaki, 0162 Rei and 0164 Sarai (`0x80051071` bits 0/1/2).
  They are set by op `23 <u16>` in events 0394, 0423, 0433 and 0398.

## Testing notes

- **Boot fresh to test a new build.** A save state made on one build carries that build's textures,
  font and `GAME.BIN` text in RAM/VRAM, and caches the `OUTPUT.BIN` entry layout. On a newer disc it
  can show wrong letter pairs, old graphics, or crash when the layout changed.
- From a fresh boot: on the title, wait about 1,500 frames, then pressing START repeatedly reaches
  the gender select.
- `vram_paint.py` copies the redrawn textures into a save state's VRAM (changed rows only), for
  screenshots of graphics changes without replaying.
- `vramfind.py` finds the disc file behind a VRAM rectangle from a save state; `timzoom.py` renders a
  zoomed TIM crop with pixel rulers.
- `headless.py` is a minimal headless libretro front end (with the PCSX-ReARMed core) for automated
  screenshots of patched builds. Buttons include L2/R2/L3/R3 (libretro ids 12-15); the Talk help
  needs R2 held while the screenshot is taken.
- `xdelta3` with a 1 GB source window can be killed for memory inside `build_patch.py`; run it on
  its own and verify by applying the patch (`-d`) and comparing with `cmp`.

## Tools

| Tool | Purpose |
|---|---|
| `build_patch.py` | Build the patched disc and the xdelta from the translation JSON. |
| `extract_script.py` | Extract all translatable text from `OUTPUT.BIN` into per-entry JSON. |
| `elanscript.py` | Script bytecode parser. |
| `insert_script.py` | Rebuild `OUTPUT.BIN` entries from the JSON and repack the archive (round trip is byte-identical). |
| `indexed.py` | Rebuild the pointer-indexed mail and conversation files. |
| `code_text.py` | Interface strings in the code modules, written in place. |
| `relocate.py` | Replace one file inside a raw Mode 2 `.bin` without moving any other file. |
| `cdsector.py` | Mode 2 raw-sector helpers: user data, EDC/ECC. |
| `pairfont.py`, `enfont.py` | The two-letters-per-glyph encoding and the 6x11 letter font. |
| `jptext.py` | Strip the Japanese from the JSON for the repository, and fill it back in from a disc. |
| `validate.py`, `check_en.py` | Check rows against the original's markup and the box limits; check the English-only files (CI). |
| `rewrap.py`, `fix_raw.py`, `show.py`, `setrows.py` | Text helpers: re-wrap lines, restore dropped `{XX}` tokens, print a file's rows, apply a mapping of translations. |
| `labels.py`, `tim_labels.py`, `help_labels.py`, `extras_labels.py`, `credits_labels.py`, `timtool.py`, `fontpath.py` | Redrawn graphics and TIM handling. |
| `movies.py`, `str_captions.py`, `exam_cards.py` | Movie re-encoding. |
| `headless.py`, `vram_paint.py`, `vramfind.py`, `timzoom.py`, `mipsdis.py` | Testing and reverse-engineering helpers (`mipsdis.py`: a minimal R3000A disassembler and PS-X EXE loader). |
