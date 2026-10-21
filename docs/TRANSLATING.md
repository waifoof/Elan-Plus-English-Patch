# Editing the translation

The English lives in `translation/<kind>/*.json`. To keep the game's script out of the repository,
these files contain **only the English**, plus each row's id and some layout fields. To see the
Japanese next to it, let the build read it back from your own disc.

Before you start, set up the build as described in [BUILDING.md](BUILDING.md), and read the
[style guide](STYLE_GUIDE.md).

## Workflow

1. **Prepare** the editable files (dump the disc, unpack the archive, merge in the Japanese):

   ```sh
   python3 build.py --disc "Elan Plus (Japan).bin" prepare
   ```

   This writes `work/text/<kind>/*.json`, where every row has the original `"jp"` next to its `"en"`.

2. **Edit** the `"en"` values in `work/text/<kind>/*.json`. Change nothing else: not `"jp"`, `"id"`,
   or any other field.

3. **Validate** your changes against the Japanese markup and the box limits:

   ```sh
   python3 tools/validate.py work/text/*/*.json
   ```

   Every file should report `0 problems, 0 untranslated rows`.

4. **Export** the English back into the repository:

   ```sh
   python3 build.py export
   ```

   This writes English-only copies of every file in `work/text/` to `translation/`.
   **Export before building**: the full build regenerates `work/text/` from `translation/`, so
   unexported edits are lost.

5. **Build and test** in an emulator:

   ```sh
   python3 build.py --disc "Elan Plus (Japan).bin"
   ```

   Boot the new image fresh. A save state made on an older build keeps that build's text, font and
   file layout in memory, so it can show wrong letters or crash on a new build.

6. **Run the repository check** (this is what CI runs on a pull request; it needs no disc):

   ```sh
   python3 tools/check_en.py --base-ref origin/main
   ```

   It re-checks the limits on the English alone, makes sure no Japanese characters slipped in, and,
   with `--base-ref`, confirms that only the words changed: every markup code, row and field must be
   the same as at that git ref.

## File kinds

| Kind | Folder | What it is | Row id |
|---|---|---|---|
| `event` | `translation/event/` | Story scenes (230 files). Dialogue, narration, captions and the two-option choices (`"choice": true`). | `NNNN:offset` |
| `mk` | `translation/mk/` | Free-roam conversations with the candidates (48 files, 0930-0977). Each row is one whole conversation block with its choices and replies. | `NNNN:bNNN` |
| `rec` | `translation/rec/` | Mail: candidates' mail replies (0834-0841), the developers' test mail (0842) and the monthly exam notices (0843). The ALPHA DATABASE hint entries repeat in every mail file and must read the same in all of them. | `NNNN:rNNN` |
| `code` | `translation/code/` | Interface strings stored in the game code and overlays (menus, tutorial pop-ups, exam screens, conversation goodbye lines). Each is written in place and has a byte budget, `"max"`. | `MODULE:offset` |

**Male/female twins.** Many scenes and conversation blocks exist twice, once for a male and once for
a female player, and usually differ by only a few words. When you change one, make the same change
to its twin. (Also: in female-player variants nobody calls the player "man", "guy" or "dude".)

Rows with `"skip": true` are not translated (unused or non-text data). Fields like `"trailer"` and
`"tail_len"` tell the build to copy binary data from the original; leave them alone.

## Markup codes

The codes are full-width characters, and they must stay exactly as they are, **in the same order** as
in the Japanese (the validator compares the sequence). Only the words around them change.

### Story scenes, interface text and mail

| Code | Meaning |
|---|---|
| `＊Name＊` | Name plate (speaker). Empty `＊＊` = narration; keep it empty. Max 8 letters, from the glossary. |
| `＠ddd＿ddd` | Voice clip id, full-width digits. Copy exactly. Some scenes put it before the name plate, some after. |
| `￥` | Line break inside a box. |
| `＝` | Page break: the next box. Same number, same places. Each page has its own 3-line limit. |
| `；` | The player's name, inserted by the game. Same number; write the sentence around it. Counts as 8 letters. |
| `｝` | Pause / control code. Same number, at the matching point of the sentence. Takes no width. |
| `｛n`, `＜n` | Text effect codes (e.g. `｛１`...`｛０` on/off, `＜５` speed). Copy exactly. No width. |
| `”n` | Expression code in voiced lines stored in the code modules. Copy exactly. |
| `－　...　－` | Centred caption or heading: keep the full-width dash and space on both sides. |
| `　` | Full-width space: keep it where a caption line starts with one. |
| `{XX}` | A raw byte the game needs (two hex digits). Copy exactly. In mail, `{00}{00}` separates messages in one row. |

### Conversations (`mk`)

A block looks like this (shortened):

```
＊；＊＋％Yeah, I guess.％：Ａ％Not really.％：Ｂ ... ＃Ａ＊Amane＊Yeah, I knew it.＝：Ｉ＃Ｂ ... ｝
```

| Code | Meaning |
|---|---|
| `＊；＊` | The player is speaking (the choices follow). Never change it. |
| `＊Name＊` | Speaker tag, max 8 letters. |
| `＋％text％：Ｘ％text％：Ｙ` | A pair of player choices; each jumps to label `Ｘ` / `Ｙ`. Translate only the option text. The game picks one of the four pairs in a block, so translate all of them with the same tone pattern (agree / disagree / unsure / emphatic...). |
| `＃Ｘ` | Label: the start of the reply to an option. Text may follow right away (`＃ＩYou're...`). |
| `＝：Ｘ` | Jump to label `Ｘ`. |
| `：ｅ` | Jump to the end of the conversation. |
| `＝` followed by text | New page. |
| `￥`, `；`, `｝` | As above; `｝` ends the block. |
| `＞{00}` | End marker; the last block of a file must keep its closing `＞{00}`. |
| `{XX}` | Raw bytes; copy exactly. `tools/fix_raw.py <file>` re-inserts ones a translation dropped. |

Labels are single **full-width** letters (`Ａ`-`Ｚ`, `ｅ`). Never write full-width letters in the
English itself: plain ASCII only.

## Limits

The validator enforces all of these:

- **32 characters per line** (the box is about 33 wide, and a wide 33rd letter can touch the frame).
  The name plate, voice code and other codes don't count; `；` counts as 8.
- **3 lines per page.** If the English doesn't fit, condense or use the existing page breaks;
  never add or remove pages.
- **Choices:** one line, max **24** characters in story scenes, max **28** in conversations.
- **Name plates / speaker tags:** max 8 letters.
- **Mail:** a message may not have more lines than the Japanese one, and its lines must fit the
  width of the Japanese message.
- **Interface strings (`code`):** the encoded English must fit the row's `"max"` bytes. Letters are
  stored two per character slot, so a run of letters takes its length rounded up to an even number
  of bytes, and each full-width code takes 2. Roughly: `"max"` letters.
- **Characters:** ASCII letters, digits, space and `` . , ! ? ' " - : ; ( ) / & % + = * ~ # < > _ [ ] $ ^ ``.
  No curly quotes, no `…` (write `...`), no em dash, no accented letters, no Japanese.

`python3 tools/rewrap.py --limit 32 FILE...` lists lines that are too long and, with `--apply`,
moves line breaks to fix the ones that can be fixed that way (words and codes are never changed).
