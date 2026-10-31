#!/usr/bin/env python3

from pathlib import Path
import shutil
import re

CORPUS_DIR = Path(r"C:\Users\jay\mfa_data\my_corpus")

IGNORE_SUFFIXES = {
    "edit",
    "edited",
    "truncated",
    "trimmed",
    "fixed",
}

MULTI_DIGIT_ID = re.compile(r"^\d{2,}$")

moved = 0

for path in CORPUS_DIR.iterdir():

    if not path.is_file():
        continue

    parts = path.stem.split("_")

    # Remove filename modifiers
    while parts and parts[-1].lower() in IGNORE_SUFFIXES:
        parts.pop()

    if len(parts) < 4:
        continue

    first_field = parts[0]

    # Leave files like:
    # 3.2.5.1.1_xyz...
    if "." in first_field:
        continue

    # Only process filenames beginning with a multi-digit integer
    if not MULTI_DIGIT_ID.fullmatch(first_field):
        continue

    # Last field should be recording number/timestamp
    if not parts[-1].isdigit():
        continue

    speaker = parts[-2].strip()

    if speaker == "":
        speaker = "UNKNOWN"

    speaker_dir = CORPUS_DIR / speaker
    speaker_dir.mkdir(exist_ok=True)

    destination = speaker_dir / path.name

    if destination.exists():
        print(f"Skipping (exists): {path.name}")
        continue

    shutil.move(str(path), str(destination))

    print(f"{path.name} -> {speaker}/")
    moved += 1

print(f"\nMoved {moved} files.")
