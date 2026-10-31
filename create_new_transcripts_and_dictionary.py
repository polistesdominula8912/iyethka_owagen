#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate MFA transcripts and dictionary from a JSONL corpus.

Input:
    corpus_items_spoken_fixed.txt

Output:
    transcripts/
        *.txt
    mfa_dictionary.txt
"""

import json
from pathlib import Path
from collections import defaultdict

INPUT_FILE = "corpus_items_spoken_fixed.txt"
TRANSCRIPT_DIR = Path("transcripts")
DICTIONARY_FILE = "mfa_dictionary.txt"

TRANSCRIPT_DIR.mkdir(exist_ok=True)

# word -> set(pronunciations)
dictionary_entries = defaultdict(set)

num_transcripts = 0

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, start=1):
        line = line.strip()

        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            print(f"Skipping invalid JSON on line {line_num}")
            continue

        audio_filename = record.get("audio_filename", "").strip()
        normalized_form = record.get("normalized_form", "").strip()
        pronunciation = record.get("mfa_pronunciation", "").strip()

        if not audio_filename or not normalized_form:
            continue

        # --------------------------------------------------
        # Transcript creation
        # --------------------------------------------------
        transcript_name = Path(audio_filename).stem + ".txt"
        transcript_path = TRANSCRIPT_DIR / transcript_name

        with open(transcript_path, "w", encoding="utf-8") as out:
            out.write(normalized_form + "\n")

        num_transcripts += 1

        # --------------------------------------------------
        # MFA dictionary entry
        # --------------------------------------------------
        if pronunciation:
            dictionary_entries[normalized_form].add(pronunciation)

# ------------------------------------------------------
# Write MFA dictionary
# ------------------------------------------------------
with open(DICTIONARY_FILE, "w", encoding="utf-8") as out:
    for word in sorted(dictionary_entries):
        for pron in sorted(dictionary_entries[word]):
            out.write(f"{word}\t{pron}\n")

print(f"Created {num_transcripts} transcript files.")
print(f"Created dictionary: {DICTIONARY_FILE}")
print(
    f"Dictionary contains "
    f"{sum(len(v) for v in dictionary_entries.values())} entries."
)
