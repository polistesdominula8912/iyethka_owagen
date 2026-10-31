#!/usr/bin/env python3

from pathlib import Path

import unicodedata

MULTIGRAPHS = [
    "aa",
    "ââ",
    "ee",
    "ch",
    "rh",
    "th",
    "ṯẖ",
    "ûû"
]

REMOVE_CHARS = "-‑‘’/"

VALID_PHONES = {
    "a","aa","â","ââ","b","ch","d","e","ee","g","h",
    "i","î","j","k","m","n","o","ô","p","r","rh",
    "s","t","th","ṯẖ","u","û","ûû","w","y","z","'"
}

VOWELS = {
    "a", "aa",
    "â", "ââ",
    "e", "ee",
    "i", "î",
    "o", "ô",
    "u",
    "û", "ûû"
}


def expected_phone_count(graphemes):
    count = len(graphemes)

    for a, b in zip(graphemes, graphemes[1:]):
        if a in VOWELS and b in VOWELS:
            count += 1

    return count


def normalize_word(word):
    """
    NFC normalization and removal of false graphemes.
    """
    word = unicodedata.normalize("NFC", word)

    for ch in REMOVE_CHARS:
        word = word.replace(ch, "")

    return word


def tokenize_word(word):
    """
    Convert orthographic word into grapheme sequence.
    """

    word = normalize_word(word)

    tokens = []
    i = 0

    while i < len(word):

        matched = False

        for g in MULTIGRAPHS:
            if word.startswith(g, i):
                tokens.append(g)
                i += len(g)
                matched = True
                break

        if matched:
            continue

        # Single-character grapheme
        tokens.append(word[i])
        i += 1

    return tokens


def split_entry(spelling, phones):
    """
    Split a phrase pronunciation into word pronunciations.
    Assumes orthography is essentially phonemic.
    """
    words = spelling.split()

    phone_index = 0
    output = []

    for word in words:
        graphemes = tokenize_word(word)
        n = expected_phone_count(graphemes)

        if phone_index + n > len(phones):
            raise ValueError(
                f"Not enough phones for '{spelling}'"
            )

        word_phones = phones[phone_index:phone_index + n]
        phone_index += n

        output.append((word, word_phones))

    if phone_index != len(phones):
        raise ValueError(
            f"Unused phones in '{spelling}'\n"
            f"  phones={phones}"
        )

    return output


def process_dictionary(infile, outfile):
    entries = {}

    with open(infile, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            if not line:
                continue

            parts = line.split()

            # Find the beginning of the pronunciation by matching
            # against the grapheme inventory.
            #
            # We assume pronunciation tokens are all single graphemes.
            #

            # Simple heuristic:
            # first token sequence that reconstructs the spelling.
            #
            # Dictionary format:
            #
            # WORD... PHONE PHONE PHONE

            found = False

            for split_pos in range(1, len(parts)):
                spelling = " ".join(parts[:split_pos])
                phones = parts[split_pos:]

                try:
                    split_words = split_entry(spelling, phones)

                    reconstructed = []
                    for word, wordphones in split_words:
                        reconstructed.extend(wordphones)

                    if reconstructed == phones:
                        found = True

                        for word, wordphones in split_words:
                            pron = " ".join(wordphones)

                            if word not in entries:
                                entries[word] = pron

                        break

                except ValueError:
                    pass

            if not found:
                print(
                    f"Could not parse line {line_num}: {line}"
                )

    with open(outfile, "w", encoding="utf-8") as f:
        for word in sorted(entries):
            f.write(f"{word}\t{entries[word]}\n")


if __name__ == "__main__":
    process_dictionary(
        "my_dictionary.txt",
        "split_dictionary.txt"
    )

    print("Done.")
