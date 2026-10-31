from collections import Counter
from pathlib import Path

# Input dictionary
dictionary_path = r"C:\Users\jay\mfa_data\my_dictionary.txt"

# Output counts file
output_path = r"C:\Users\jay\mfa_data\phone_counts.tsv"

phone_counts = Counter()
total_entries = 0
bad_lines = 0

with open(dictionary_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, start=1):
        line = line.strip()

        if not line:
            continue

        try:
            # Split only on the first tab
            entry, pronunciation = line.split("\t", 1)
        except ValueError:
            bad_lines += 1
            print(f"Warning: line {line_num} does not contain a tab")
            continue

        phones = pronunciation.split()

        phone_counts.update(phones)
        total_entries += 1

# Write results sorted by frequency (highest first)
with open(output_path, "w", encoding="utf-8") as out:
    out.write("PHONE\tCOUNT\n")

    for phone, count in phone_counts.most_common():
        out.write(f"{phone}\t{count}\n")

print(f"Processed {total_entries:,} entries")
print(f"Found {len(phone_counts):,} unique phones")
print(f"Skipped {bad_lines:,} malformed lines")
print(f"Output written to: {output_path}")
