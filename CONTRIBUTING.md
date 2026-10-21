# Contributing

Thanks for helping improve the Élan Plus translation. Bug reports, text fixes and corrections
(especially to the staff-roll names) are all welcome.

The translation was made with AI machine translation and AI-assisted editing (see the README), so
reports of mistranslations, lines that miss the original's meaning or tone, and better wording from
people who read Japanese are especially valuable.

## Reporting a problem

[Open an issue](https://github.com/waifoof/Elan-Plus-English-Patch/issues/new/choose) and pick
**Bug report** (freezes, graphics, overflowing or untranslated text) or **Text fix** (typos,
mistranslations, awkward lines). Please include:

- **a screenshot** of the problem;
- **where in the game** it happened: week and day, location, which scene or conversation, and
  whether you play the male or the female route;
- **the patch version** (e.g. v1.0.1) and your emulator, or real hardware.

If the patch won't apply or the game won't boot, add the checksums of your original `.bin` and
compare them with [CHECKSUMS.md](CHECKSUMS.md) first.

Check [KNOWN_ISSUES.md](KNOWN_ISSUES.md) before reporting: some oddities are the original game's own
artwork or a limit of the engine.

## Proposing text fixes

A pull request is the quickest way to get a fix in. You need your own copy of the game to see the
Japanese and to test.

1. Follow the workflow in [docs/TRANSLATING.md](docs/TRANSLATING.md): `build.py --disc ... prepare`,
   edit `"en"` in `work/text/`, run `tools/validate.py`, then `build.py export` to write the change to
   `translation/*.json`. (A small typo can also be fixed directly in `translation/*.json`.)
2. Change **only the words**. Every markup code (voice ids, page breaks, speaker tags, labels, raw
   `{XX}` bytes) and every field other than `"en"` must stay exactly as it is.
3. Keep **male/female twin rows consistent**: many scenes and conversation blocks exist once for each
   player gender. Make the same change to both.
4. Follow the [style guide](docs/STYLE_GUIDE.md): names, canonical terms, punctuation and the
   characters' voices.
5. Run the same check CI runs, and make sure it passes:

   ```sh
   python3 tools/check_en.py --base-ref origin/main
   ```

6. If you can, build the patch and look at the changed lines in an emulator (boot fresh, not from an
   old save state).

In the pull request, say what you changed, why, and where it appears in the game.

## Never commit game data

This repository must not contain anything from the game. Please don't commit or attach:

- disc images or files from the disc (`.bin`, `.cue`, `.iso`, `.STR`, `OUTPUT.BIN` entries, extracted
  textures...);
- anything from `work/` or `out/`, or a built patch (`.xdelta` files go on the Releases page);
- Japanese script text: the `"jp"` field is filled in from your disc at build time and is removed
  again by `build.py export`; `check_en.py` rejects Japanese characters in the English;
- screenshots of whole scripts or long passages of the Japanese text (a screenshot of the one line
  you're reporting is fine);
- emulator save states or memory cards.

`.gitignore` already excludes the usual files, but please check `git status` before you commit.

## Licence

By contributing you agree that your contribution is released under the [MIT License](LICENSE) of
this repository.
