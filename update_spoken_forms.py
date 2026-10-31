import json

# ==========================================================
# CONFIG
# ==========================================================

INPUT_FILE = "corpus_items_corrected.txt"
OUTPUT_FILE = "corpus_items_spoken_fixed.txt"

# Add or remove vowels here as needed.
VOWELS = [
    ("a", "aa"),
    ("â", "ââ"),
    ("e", "ee"),
    ("ê", "êê"),
    ("i", "ii"),
    ("î", "îî"),
    ("o", "oo"),
    ("ô", "ôô"),
    ("u", "uu"),
    ("û", "ûû"),
]


# ==========================================================
# TRANSFORMATIONS
# ==========================================================

def apply_glottal(text):
    for short_vowel, long_vowel in VOWELS:
        text = text.replace(
            long_vowel,
            f"{short_vowel}'{short_vowel}"
        )
    return text


def apply_long(text):
    for short_vowel, long_vowel in VOWELS:
        text = text.replace(
            f"{short_vowel}'{short_vowel}",
            long_vowel
        )
    return text


def apply_short(text):
    for short_vowel, long_vowel in VOWELS:
        text = text.replace(
            f"{short_vowel}'{short_vowel}",
            short_vowel
        )
        text = text.replace(
            long_vowel,
            short_vowel
        )
    return text


def apply_status(text, status):
    if not isinstance(text, str):
        return text

    if status == "glottal":
        return apply_glottal(text)

    if status == "long":
        return apply_long(text)

    if status == "short":
        return apply_short(text)

    return text


# ==========================================================
# MAIN
# ==========================================================

updated = 0

with open(INPUT_FILE, encoding="utf-8") as fin, \
     open(OUTPUT_FILE, "w", encoding="utf-8") as fout:

    for line in fin:
        obj = json.loads(line)

        status = obj.get("aa_review_status")

        # Skip manual edits and anything unreviewed
        if status not in {"glottal", "long", "short"}:
            fout.write(
                json.dumps(obj, ensure_ascii=False) + "\n"
            )
            continue

        old_spoken = obj.get("spoken_form", "")
        old_norm = obj.get("normalized_form", "")

        obj["spoken_form"] = apply_status(
            old_spoken,
            status
        )

        obj["normalized_form"] = apply_status(
            old_norm,
            status
        )

        if (
            obj["spoken_form"] != old_spoken
            or obj["normalized_form"] != old_norm
        ):
            updated += 1

        fout.write(
            json.dumps(obj, ensure_ascii=False) + "\n"
        )

print(f"Updated {updated} entries")
print(f"Saved to {OUTPUT_FILE}")
