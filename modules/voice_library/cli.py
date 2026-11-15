"""List the voice library, or check it against the TTS engine.

    python -m modules.voice_library.cli                    # every voice
    python -m modules.voice_library.cli --language vi      # Vietnamese voices only
    python -m modules.voice_library.cli --check            # needs internet + `pip install edge-tts`
    python -m modules.voice_library.cli --make-previews    # one sample per voice into assets/voice_previews/
                                                           # (needs internet + edge-tts; then commit them)
"""
from __future__ import annotations

import argparse

from modules.voice_library.library import LANGUAGES, VoiceLibrary, load_library


def format_table(lib: VoiceLibrary, language: str | None = None) -> str:
    voices = lib.list(language=language)
    if not voices:
        return "(no voices)"
    head = f"{'id':<16}{'name':<13}{'lang':<5}{'locale':<8}{'gender':<8}{'wpm':<14}engine voice"
    lines = [head, "-" * len(head)]
    for v in voices:
        wpm = f"{v.base_wpm:.0f}" + ("" if v.wpm_is_measured else " (assumed)")
        star = "*" if lib.default(v.language) == v else " "
        lines.append(f"{v.voice_id:<16}{v.name:<13}{v.language:<5}{v.locale:<8}{v.gender:<8}{wpm:<14}{v.engine_voice}{star}")
    lines.append("\n* = default voice of its language")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--language", choices=sorted(LANGUAGES), default=None)
    ap.add_argument("--check", action="store_true", help="verify every voice exists on the TTS engine (online)")
    ap.add_argument("--make-previews", action="store_true",
                    help="create the bundled sample of every voice that has none (online)")
    ap.add_argument("--force", action="store_true", help="with --make-previews: recreate existing samples")
    args = ap.parse_args(argv)
    lib = load_library()
    print(format_table(lib, args.language))
    if args.make_previews:
        from modules.providers.edge_tts_provider import BUNDLED_DIR, TTSUnavailable, has_bundled, make_bundled_previews
        try:
            made = make_bundled_previews(lib, force=args.force)
        except TTSUnavailable as exc:
            print(f"\nno previews made: {exc}")
            return 2
        print(f"\nwrote {len(made)} sample(s) to {BUNDLED_DIR}; "
              f"voices with a bundled sample: {sum(has_bundled(v) for v in lib)}/{len(lib)}. Commit the folder.")
    if not args.check:
        return 0
    from modules.providers.edge_tts_provider import TTSUnavailable, verify_library
    try:
        result = verify_library(lib)
    except TTSUnavailable as exc:
        print(f"\ncheck not possible: {exc}")
        return 2
    print(f"\nchecked {len(result.ok)} voices on the engine; missing: {result.missing or 'none'}")
    return 1 if result.missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
