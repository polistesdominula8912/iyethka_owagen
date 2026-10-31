#!/usr/bin/env python3

from pathlib import Path
import unicodedata

CORPUS_DIR = Path(r"C:\Users\jay\mfa_data\my_corpus")

REMOVE_CHARS = "-‑‘’/"


def normalize_text(text):
    # Normalize Unicode
    text = unicodedata.normalize("NFC", text)

    # Remove unwanted characters
    for ch in REMOVE_CHARS:
        text = text.replace(ch, "")

    return text


for txt_file in CORPUS_DIR.glob("*.txt"):
    try:
        original = txt_file.read_text(
            encoding="utf-8",
            errors="replace"
        )

        normalized = normalize_text(original)

        if normalized != original:
            txt_file.write_text(
                normalized,
                encoding="utf-8"
            )
            print(f"Modified {txt_file.name}: {original}")
        else:
            continue

    except Exception as e:
        print(f"ERROR: {txt_file.name}: {e}")

print("Done.")
