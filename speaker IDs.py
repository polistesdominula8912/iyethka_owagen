from pathlib import Path
from collections import Counter
import re

CORPUS_DIR = Path(r"C:\Users\jay\mfa_data\my_corpus")

IGNORE_SUFFIXES = {
    "edit",
    "edited",
    "truncated",
    "trimmed",
    "fixed",
}

speaker_counts = Counter()
examples = {}

for path in CORPUS_DIR.iterdir():

    if not path.is_file():
        continue

    parts = path.stem.split("_")

    # Remove trailing modifiers
    while parts and parts[-1].lower() in IGNORE_SUFFIXES:
        parts.pop()

    if len(parts) < 4:
        continue

    first = parts[0]

    # Skip ELAN-style IDs
    if "." in first:
        continue

    # Skip simple numeric-prefixed files
    if not re.fullmatch(r"\d{2,}", first):
        continue

    # Last field should be recording number
    if not parts[-1].isdigit():
        continue

    speaker = parts[-2]

    speaker_counts[speaker] += 1

    if speaker not in examples:
        examples[speaker] = path.name


output_file = Path(r"C:\Users\jay\mfa_data") / "detected_speaker_codes.txt"

with open(output_file, "w", encoding="utf-8") as f:
    f.write("Speaker Code\tCount\n")
    f.write("=" * 30 + "\n")

    for speaker, count in sorted(speaker_counts.items()):
        f.write(
            f"{speaker}\t{count}\t{examples[speaker]}\n"
        )

    f.write("\n")
    f.write(f"Total unique speaker codes: {len(speaker_counts)}\n")
    f.write(f"Total files matched: {sum(speaker_counts.values())}\n")

print(f"Found {len(speaker_counts)} unique speaker codes.")
print(f"Wrote report to: {output_file}")
