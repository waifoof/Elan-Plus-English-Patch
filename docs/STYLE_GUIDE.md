# Style guide

The rules, names and terms the translation follows. If you propose a change, keep to these so the
script stays consistent. For the editing workflow and the full list of markup codes, see
[TRANSLATING.md](TRANSLATING.md).

## Contents

- [Part 1: Story scenes and interface text](#part-1-story-scenes-and-interface-text)
- [Part 2: Free-roam conversations](#part-2-free-roam-conversations)
- [Voice and style](#voice-and-style)
- [Cast](#cast)
- [Glossary: speaker names](#glossary-speaker-names)
- [Glossary: names, places and terms](#glossary-names-places-and-terms)
- [Canonical terms](#canonical-terms)
- [Fixed wording, punctuation and spelling](#fixed-wording-punctuation-and-spelling)

## Part 1: Story scenes and interface text

Fill `"en"` for every row; never change `"jp"`, `"id"`, `"end"` or `"choice"`. A story row looks like:

    ＊カナメ＊＠００２＿００８<line 1>￥<line 2>￥<line 3>

and its English keeps the same markup in the same order:

    ＊Kaname＊＠００２＿００８<line 1>￥<line 2>￥<line 3>

| Markup | Meaning | Rule |
|---|---|---|
| `＊Name＊` | name plate (empty `＊＊` = narration) | keep the full-width `＊ ＊`; put the English name from the glossary inside (`＊Kaname＊`); keep `＊＊` empty if it was empty |
| `＠ddd＿ddd` | voice clip id | copy **exactly**, full-width digits included |
| `￥` | line break inside a box | at most 2 per page (3 lines per box) |
| `；` | **the player's name** (the game inserts what the player typed) | keep the same number of `；` and write the sentence around it, e.g. `The Day ； and Amane Depart`; counts as 8 letters of line width |
| `｝` | engine control code inside dialogue (a pause) | keep the **same number**, at the same point in the sentence; it takes no width |
| `｛n` `＜n` | text-effect codes (e.g. `｛１`...`｛０` on/off, `＜５` speed) | copy exactly, same order; no width |
| `＝` | page break inside one row (next box), usually followed by the next voice code | keep the **same number** of `＝`, in the same places; each page has its own 3-line limit |
| `－　...　－` | centred caption / heading | keep `－　` and `　－` (full-width dash + full-width space) around the English |
| `　` (full-width space) | indentation in captions | keep it where the Japanese has it at the start of a caption line |

**Order matters.** Copy the markup in exactly the order it appears in the Japanese. Some scenes put
the voice code *before* the name plate (`＠２１０＿０１２＊Narusawa＊...`), others after
(`＊Narusawa＊＠００２＿００８...`). Mid-row pages look like `...first page.＝＠２１０＿０１４Second page...`.

The sequence of engine codes (voice `＠ddd＿ddd`, `；`, `｝`, `｛n`, `＜n`, `＝`) must be identical in
the English and the Japanese: same values, same order. Put each code at the matching point of the
English sentence. Full-width digits right after a voice code are ordinary text: write them as ASCII
(`＠１０９＿０１３10 minutes.`).

### Hard limits (enforced by the validator)

- **32 characters per line** (text between `￥` breaks, not counting the name plate and voice code).
  Measured in-game: a wide 33rd letter can touch the box frame.
- **3 lines per box.** If the English doesn't fit, condense; never split one row across two.
- **Choice rows** (`"choice": true`): one line, **max 24 characters**, no `￥`.
- **Name plates:** max 8 characters inside `＊ ＊` (see the glossary).
- **Allowed characters:** plain ASCII letters, digits, space and
  `` . , ! ? ' " - : ; ( ) / & % + = * ~ # < > _ [ ] $ ^ ``.
  No curly quotes, no `…` (write `...`), no em dash (write `--` or rephrase), no accented letters,
  no Japanese.

## Part 2: Free-roam conversations

The `mk` files (0930-0977) hold the conversations you have with candidates in the training
facilities. Each row is one **block** (it ends with `｝`). Translate each block as a whole, keeping
every code exactly.

    ＊；＊＋％opt1％：Ａ％opt2％：Ｂ＋％opt3％：Ｃ％opt4％：Ｄ ...  ＃Ａ＊Amane＊reply...＝：Ｉ＃Ｂ...  ｝

| Code | Meaning | Rule |
|---|---|---|
| `＊；＊` | the PLAYER is speaking (choices follow) | copy exactly, never translate |
| `＊Name＊` | speaker tag | English short name from the glossary |
| `＋％text％：Ｘ％text％：Ｙ` | one pair of player choices; each option jumps to label `Ｘ` / `Ｙ` | translate only the option text; keep `＋ ％ ％：Ｘ` exactly; one line, max **28** characters |
| `＃Ｘ` | label (start of the reply to an option) | copy exactly; text may follow immediately (`＃ＩYou're...`) |
| `＝：Ｘ` / `：ｅ` | jump to label `Ｘ` / jump to the end | copy exactly |
| `＝` followed by text | new page | keep the same pages |
| `￥` | line break | max 3 lines per page, 32 characters per line |
| `｝` | end of block | copy |
| `；` | the player's name (inside text) | keep; counts as 8 characters |

Labels are single **full-width** letters (`Ａ`-`Ｚ`, `ｅ`). Never write full-width letters in the
English text, only ASCII.

The four choice pairs in a block are alternatives the game picks between. Translate all of them,
keeping the same tone pattern (agree / disagree / unsure / emphatic and so on). Player choices should
sound like natural replies, and the reply that follows must make sense after the choice: if a reply
reacts to laughter ("Don't laugh!", "You look amused"), the choice before it should read as a light
laugh ("Ha,", "Heh,").

These are casual one-on-one chats. Keep each candidate's personality (see the cast table): Amane is
cheerful and boyish; Kaname is formal and quaint and calls the player "Cousin"; Yoh is a rough, flirty
guy.

## Voice and style

- Natural, idiomatic English that sounds like people talking. Not literal, not stiff.
- Keep each character's personality consistent (formal/casual, gruff/gentle). Read the whole scene
  before translating a line of it.
- Drop honorifics (-san, -kun, -chan); express politeness or familiarity through wording instead.
  Keep a title if it is a rank or role ("Doctor", "Captain"). No Mr./Ms./Mrs.
- Given names as in the glossary. Don't invent nicknames.
- Interjections: translate the feeling ("Huh?", "Whoa!", "Hmm..."), don't transliterate ("Eh?" is
  fine, "Ara?" is not).
- Stuttering and ellipses: `...` is fine; keep it light.
- Sound effects in narration: a short English description or onomatopoeia.
- Keep the intensity of `!` and `?` roughly as in the original.
- Lines that repeat (meeting speeches, ending speeches, the ALPHA DATABASE entries) read the same
  everywhere.
- Male and female player versions of a scene or block should match apart from what actually differs.
  In female-player variants nobody addresses the player as "man", "guy" or "dude" (an interjection
  like "Man, I'm beat" is fine).

## Cast

Pronouns must match.

| Character | Gender | Notes |
|---|---|---|
| Kaname | female | calls the player "Cousin" (従兄殿 / 従姉殿) |
| Natsuno | female | Haruka's older sister; Yoh calls her "Nat" (the Japanese uses a nickname) |
| Riko | female | |
| Tomoe | female | |
| Sakaki (Yuri) | female | staff |
| Haruka | female | Natsuno's younger sister; calls her "Sis" |
| Yoh | **male** | rough and flirtatious; he/him |
| Amane | male | cheerful, boyish |
| Eiji | male | |
| Kairi | male | says "Yes", not "Yeah" |
| Rei | male | staff |
| Sarai | male | staff |
| Narusawa (Kazuya) | male | director |

## Glossary: speaker names

Name plates and in dialogue.

| Japanese | English | Notes |
|---|---|---|
| カナメ | Kaname | |
| ナルサワ | Narusawa | family name |
| リコ | Riko | |
| ナツノ | Natsuno | "Natsu" in the results tables, where the full name doesn't fit |
| アマネ | Amane | |
| ヨウ | Yoh | spelled "Yoh" so it never reads as "you" |
| エイジ | Eiji | |
| サカキ | Sakaki | family name |
| トモエ | Tomoe | |
| カイリ | Kairi | |
| レイ | Rei | |
| サライ | Sarai | |
| ハルカ | Haruka | |
| 少年 | Boy | |
| 整備士 | Mechanic | |
| 医師 | Doctor | |
| 放送 | PA | public-address announcement |
| 技術者 | Engineer | |
| 研究者Ａ / 研究者Ｂ | Lab A / Lab B | the plate is narrow; dialogue can say "researcher" |
| 上層部 | Command | the higher-ups |
| 二人 | Both | |
| 三人 | All 3 | |
| ？？？ / ？？？？ | ??? / ???? | |

## Glossary: names, places and terms

| Japanese | English |
|---|---|
| ナルサワ・カズヤ | Kazuya Narusawa |
| サカキ・ユリ | Yuri Sakaki |
| ステーション・アルファ / アルファ | Station Alpha / Alpha |
| エラン | Elan (the planet) |
| プロジェクト・エラン | Project Elan |
| ソピア | Sophia (the colony; "on Sophia") |
| ゲート | the Gate (the wormhole gate) |
| 親密度 / 好感度 / ストレス値 | Closeness / Affection (UI button: Rapport) / Stress |
| 気分 / 嬉しい / 哀しい / 怒り | Mood / Happy / Sad / Angry |
| 普通 (mood) | Normal (not "Okay") |
| 体力 筋力 知力 技術力 操縦力 直感力 判断力 根性 | Stamina, Strength, Intellect, Tech, Piloting, Sense, Judgment, Grit (UI: Stam Str Int Tech Pilot Sense Judge Grit) |
| 月末試験 / 最終試験 | monthly exam / **final exam** (not "final test") |
| 共同トレーニング / 通常 | joint training / solo training (UI buttons: Solo / Joint) |
| ワーカー | Worker (exo-suit) |
| αDATA BASE NO:nn | ALPHA DATABASE No.nn (identical text in every mail file) |

Full names are written given name first (Kazuya Narusawa); name plates use the short form.
『』 quotes become "double quotes". ・・・ becomes "...". Hearts (◆) in mail become `~` or are dropped.

Mail files: 0834 Amane, 0835 Eiji, 0836 Kairi, 0837 Kaname, 0838 Natsuno, 0839 Riko, 0840 Tomoe,
0841 Yoh; 0842 is the developers' test mail and 0843 the monthly exam notices.

## Canonical terms

Facility and place names are proper nouns: capitalise them in dialogue too.

| Japanese | English (always) | Do not use |
|---|---|---|
| 航行演習場 | Flight Training Room (map label: Flight Rm) | Navigation Training Area/Hall, navigation range, nav sim |
| 航行演習 (the training) | flight training | navigation training |
| 共有フロア | Common Floor | Common Area, lounge, common floor |
| 環境調整区 | Environmental Section | Environmental Control (Area), Environmental Zone |
| 資料室 | Archives | archive room, reference room, records room, Archive Room |
| 管理センター / 管理者センター | Control Center | Admin Center, Supervisor Center |
| 加重力室 | High-G Room | G-chamber, gravity room, high-G room |
| 筋力鍛練場 | Weight Room | gym (the gym is the Indoor Gym) |
| 運動場 / 室内運動場 | Indoor Gym (casual: "the gym") | track, field |
| 整備室 / 医務室 / モニタールーム | Maintenance Room / Medical Room / Monitor Room | lowercase forms, maintenance bay |
| 格納庫 | Hangar | hangar |
| 食堂 | Cafeteria | cafeteria |
| 通信センター / 通信室 | Comm Center / Comm Room | comm room for the center |
| 管理者 | supervisor(s) | administrators, admin, staff, management, people in charge |
| 管理委員会 | Management Committee | |
| 適格者 | qualify / the qualified (those chosen for the mission) | "chosen as a candidate" |
| 体力 / 技術力 / 直感力 | Stamina / Tech / Sense (as stat names; "intuition" is fine as an ordinary word) | physical training, Technical, Technology |
| 根性 / 判断力 | Grit / Judgment | |
| Exams (in prose) | Rescue, EVA, Sample Analysis, Worker Assembly, Geological Survey, Wildlife Capture, SL Gate Navigation, SL Atmospheric Entry, final exam | Creature Capture, Bio Catch (small menu slots may keep their short forms) |

Training named after a stat is capitalised: Stamina / Strength / Intellect / Tech / Piloting /
Sense / Judgment / Grit training.

## Fixed wording, punctuation and spelling

- Departure captions: `－　One Month Later　－` and `－　； and <Name> Depart　－` (use "Leave" only if
  "Depart" doesn't fit).
- Always `...`, never `..`, `....` or `.....`.
- Questions end with `?` (or `?!` when emphatic), never `!!`. Plain statements don't end with `!?`
  just because the Japanese has ！？; tag questions are often suggestions or statements.
- Choices end with normal punctuation (`.`, `?`, `!`) like lines of dialogue, unless the length limit
  forbids it.
- Double quotes, never single quotes, for quoted words.
- "okay", not "OK". "Geez", not "Jeez". "mail", not "email". "halfhearted", "minicomputer" (one word).
- Stutters are lowercase after the hyphen ("B-but", "Wh-what"), except names, "Cousin" and "I".
