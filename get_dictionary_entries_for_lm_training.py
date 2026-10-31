import json
from pathlib import Path

input_file = Path(r"C:\Users\jay\mfa_data\Stoney prep work\corpus_items_spoken_fixed.txt")
output_file = Path(r"C:\Users\jay\mfa_data\all_text.txt")

seen = set()
count = 0

with open(input_file, "r", encoding="utf-8") as infile, \
     open(output_file, "w", encoding="utf-8") as outfile:

    for line_num, line in enumerate(infile, start=1):
        line = line.strip()
        if not line:
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            print(f"Skipping invalid JSON on line {line_num}")
            continue

        spoken_form = record.get("spoken_form", "").strip()

        if not spoken_form:
            continue

        # Keep only unique spoken forms
        if spoken_form not in seen:
            seen.add(spoken_form)
            outfile.write(spoken_form + "\n")
            count += 1

print(f"Wrote {count:,} unique spoken forms to:")
print(output_file)
