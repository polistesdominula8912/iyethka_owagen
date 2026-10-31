"""
===============================================================================
Stoney Dictionary Scraper for MFA / MFL Training
===============================================================================

Purpose
-------
Extract:
    * dictionary entries
    * audio recordings
    * transcriptions

for speech technology work.

Core Principle
--------------
One audio recording = one corpus item

Outputs
-------
entries.json
    Dictionary metadata and provenance.

corpus_items.csv
    One row per transcription/audio pair.

corpus_items.jsonl
    Same information in JSONL format.

download_manifest.csv
    Audio download list.

mfa_dictionary.txt
    Automatically generated pronunciation dictionary.

scrape_summary.json
    Counts and diagnostics.

-------------------------------------------------------------------------------
ORTHOGRAPHY NOTES
-------------------------------------------------------------------------------

The Stoney writing system is largely phonetic.

Explicit glottal stops are represented by apostrophe:

    a'a

and will generate:

    a ' a

Many older dictionary entries contain adjacent vowels without an apostrophe:

    aa

Historically these often imply:

    a ʔ a

However because orthographic conventions are evolving and contrastive vowel
length is emerging, this scraper preserves the source orthography by default.

Therefore:

    aa

becomes:

    a a

NOT

    a ' a

Unless AUTO_INSERT_PREDICTABLE_GLOTTALS is enabled.

-------------------------------------------------------------------------------
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

import unicodedata

# =============================================================================
# CONFIGURATION
# =============================================================================

SEARCH_URL = "https://dictionary.stoneynakoda.org/index.php/Search"

OUTPUT_DIR = Path("stoney_output")

# Alternate apostrophe characters that may occur in source data.
# All will be normalized to GLOTTAL_SYMBOL.

APOSTROPHE_VARIANTS = [
    "’",  # curly apostrophe
    "ʻ",  # okina-like
    "ʼ",  # modifier apostrophe
]

# -----------------------------------------------------------------------------
# CASE NORMALIZATION
# -----------------------------------------------------------------------------

# Capitalization is not meaningful for MFA training.
# All words will be converted to lowercase before
# dictionary generation and pronunciation generation.

NORMALIZE_CASE = True

# -----------------------------------------------------------------------------
# TEST MODE
# -----------------------------------------------------------------------------

TEST_MODE = False

# Restrict search terms during testing.
TEST_SEARCH_TERMS = [
    "m",
    "M",
]

# Maximum pages per term while testing.
MAX_PAGES_PER_TERM = None

# Number of corpus items printed at end.
PRINT_SAMPLE_ITEMS = 5

# -----------------------------------------------------------------------------
# FULL ALPHABET SEARCH TERMS
# -----------------------------------------------------------------------------

FULL_SEARCH_TERMS = [
    "a",
    "â",
    "b",
    "ch",
    "d",
    "e",
    "g",
    "h",
    "i",
    "î",
    "j",
    "k",
    "m",
    "n",
    "o",
    "p",
    "r",
    "rh",
    "s",
    "t",
    "th",
    "ṯẖ",
    "u",
    "û",
    "w",
    "y",
    "z",
]

# -----------------------------------------------------------------------------
# REQUESTS
# -----------------------------------------------------------------------------

PAGE_SIZE = 5

REQUEST_TIMEOUT = 60

REQUEST_DELAY_SECONDS = 0.25

# -----------------------------------------------------------------------------
# ORTHOGRAPHY / MFA CONFIGURATION
# -----------------------------------------------------------------------------

GENERATE_MFA_DICTIONARY = True

GLOTTAL_SYMBOL = "'"

PRESERVE_EXPLICIT_GLOTTALS = True

AUTO_INSERT_PREDICTABLE_GLOTTALS = True

VOWELS = {
    "a",
    "â",
    "e",
    "i",
    "î",
    "o",
    "u",
    "û",
}

MULTIGRAPHS = [
    "ch",
    "th",
    "rh",
    "ṯẖ",
]

REMOVE_CHARACTERS = [
    ",",
    ".",
    ";",
    ":",
    "?",
    "!",
    "(",
    ")",
    "[",
    "]",
]

# -----------------------------------------------------------------------------
# OUTPUT FILENAMES
# -----------------------------------------------------------------------------

ENTRIES_JSON = "entries.json"

CORPUS_CSV = "corpus_items.csv"

CORPUS_JSONL = "corpus_items.jsonl"

MANIFEST_CSV = "download_manifest.csv"

MFA_DICTIONARY = "mfa_dictionary.txt"

SUMMARY_JSON = "scrape_summary.json"

PROBLEM_ENTRIES_JSON = "problem_entries.json"

# =============================================================================
# HELPERS
# =============================================================================

def clean_text(text: str) -> str:

    if not text:
        return ""

    text = unicodedata.normalize(
        "NFC",
        text
    )

    for apostrophe in APOSTROPHE_VARIANTS:
        text = text.replace(
            apostrophe,
            GLOTTAL_SYMBOL
        )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()

def card_hash(html: str) -> str:
    return hashlib.sha256(
        html.encode("utf-8")
    ).hexdigest()


def extract_entry_id(card) -> str:
    disclaimer = card.select_one(".disclaimer")

    if disclaimer:
        onclick = disclaimer.get("onclick", "")

        match = re.search(
            r'openModal\(".*?",\s*"(\d+)"\)',
            onclick,
        )

        if match:
            return match.group(1)

    return ""


def extract_audio_url(audio_tag) -> str:
    if not audio_tag:
        return ""

    return clean_text(
        audio_tag.get("src", "")
    )

# =============================================================================
# TOKENIZER
# =============================================================================


def tokenize_word(word: str):
    """
    Convert orthography to MFA tokens.

    Examples

    a'a
        -> a ' a

    aa
        -> a a

    chagha
        -> ch a g h a
    """
    word = clean_text(word)
    
    if NORMALIZE_CASE:
        word = word.lower()
        
    word = word.strip()

    for c in REMOVE_CHARACTERS:
        word = word.replace(c, "")

    ordered_multigraphs = sorted(
        MULTIGRAPHS,
        key=len,
        reverse=True,
    )

    tokens = []

    i = 0

    while i < len(word):

        if (
            PRESERVE_EXPLICIT_GLOTTALS
            and word[i] == GLOTTAL_SYMBOL
        ):
            tokens.append(GLOTTAL_SYMBOL)
            i += 1
            continue

        matched = False

        for mg in ordered_multigraphs:

            if word[i:].startswith(mg):
                tokens.append(mg)
                i += len(mg)
                matched = True
                break

        if matched:
            continue

        tokens.append(word[i])
        i += 1

    if AUTO_INSERT_PREDICTABLE_GLOTTALS:

        expanded = []

        for idx, token in enumerate(tokens):

            expanded.append(token)

            if idx == len(tokens) - 1:
                continue

            next_token = tokens[idx + 1]

            if (
                token in VOWELS
                and next_token in VOWELS
            ):
                expanded.append(GLOTTAL_SYMBOL)

        tokens = expanded

    return tokens


def pronunciation_for_word(word: str) -> str:

    if NORMALIZE_CASE:
        word = word.lower()

    return " ".join(
        tokenize_word(word)
    )


# =============================================================================
# INITIALIZE
# =============================================================================

OUTPUT_DIR.mkdir(exist_ok=True)

session = requests.Session()

entries = []

corpus_items = []

search_terms = (
    TEST_SEARCH_TERMS
    if TEST_MODE
    else FULL_SEARCH_TERMS
)

seen_entries = set()

problem_entries = []

# =============================================================================
# SCRAPE
# =============================================================================

search_stats = {}

for term in search_terms:

    term_entry_count = 0
    term_entry_ids = set()

    print(f"\nSearching '{term}'")

    page_counter = 0
    offset = 0

    while True:

        response = session.post(
            SEARCH_URL,
            data={
                "lang": "L",
                "word": term,
                "token": "7",
                "page": str(offset),
            },
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        cards = soup.select("div.content")

        if not cards:
            break

        for card in cards:
            
            raw_html = str(card)

            entry_id = extract_entry_id(card)

            html_sha256 = card_hash(raw_html)

            entry_key = (
                entry_id
                if entry_id
                else html_sha256
            )

            if entry_key in seen_entries:
                continue

            seen_entries.add(entry_key)

            # -----------------------------------------------------------------
            # LEMMA
            # -----------------------------------------------------------------

            lemma = ""

            entry_span = card.select_one(".Entry")

            if entry_span:

                for candidate in entry_span.select(".wordclickL"):

                    text = clean_text(
                        candidate.get_text()
                    )

                    if text:
                        lemma = text
                        break

            if not lemma:

                print(
                    f"WARNING: Missing lemma "
                    f"(entry_id={entry_id})"
                )

                problem_entries.append({
                    "entry_id": entry_id,
                    "reason": "missing_lemma",
                    "html_hash": html_sha256,
                })

                continue

            # -----------------------------------------------------------------
            # POS
            # -----------------------------------------------------------------

            pos_tag = card.select_one(
                ".Entry__PartOfSpeech"
            )

            pos = (
                clean_text(pos_tag.get_text())
                if pos_tag
                else ""
            )

            # -----------------------------------------------------------------
            # DEFINITIONS
            # -----------------------------------------------------------------

            definitions = []

            for definition in card.select(
                ".Definition__Definition"
            ):
                text = clean_text(
                    definition.get_text(
                        " ",
                        strip=True,
                    )
                )

                if text:
                    definitions.append(text)

            # -----------------------------------------------------------------
            # VARIANTS
            # -----------------------------------------------------------------

            variants = []

            for ref in card.select(
                ".References .wordclickL"
            ):

                variant = clean_text(
                    ref.get_text()
                )

                if (
                    variant
                    and variant != lemma
                ):
                    variants.append(variant)

            variants = sorted(
                set(variants)
            )

            # -----------------------------------------------------------------
            # ENTRY RECORD
            # -----------------------------------------------------------------

            entry = {
                "entry_id": entry_id,
                "lemma": lemma,
                "part_of_speech": pos,
                "definitions": definitions,
                "variants": variants,
                "html_hash": html_sha256,
            }

            entries.append(entry)

            term_entry_count += 1

            if entry_id:
                term_entry_ids.add(entry_id)

            # -----------------------------------------------------------------
            # LEMMA AUDIO
            # -----------------------------------------------------------------

            for audio_container in card.select(
                ".Entry__AudioFemale, .Entry__AudioMale"
            ):

                classes = audio_container.get(
                    "class",
                    []
                )

                if "Entry__AudioFemale" in classes:
                    speaker_type = "female"

                elif "Entry__AudioMale" in classes:
                    speaker_type = "male"

                else:
                    speaker_type = "unknown"

                audio = audio_container.select_one(
                    "audio[src]"
                )

                if not audio:
                    continue

                audio_url = extract_audio_url(audio)

                if not audio_url:
                    continue

                corpus_items.append({
                    "entry_id": entry_id,
                    "lemma": lemma,

                    "spoken_form": lemma,

                    "normalized_form":
                        clean_text(lemma).lower()
                        if NORMALIZE_CASE
                        else lemma,

                    "mfa_pronunciation":
                        pronunciation_for_word(lemma),

                    "form_type": "lemma",

                    "translation": "",

                    "part_of_speech": pos,

                    "definitions":
                        " ; ".join(definitions),

                    "speaker_type":
                        speaker_type,

                    "audio_url": audio_url,

                    "audio_filename":
                        audio_url.split("/")[-1],

                    "html_hash": html_sha256,
                })

            # -----------------------------------------------------------------
            # INFLECTED FORMS
            # -----------------------------------------------------------------

            for infl in card.select(
                ".InflectedForm"
            ):

                word_form_tag = infl.select_one(
                    ".InflectedForm__WordForm"
                )

                if not word_form_tag:
                    continue

                spoken_form = clean_text(
                    word_form_tag.get_text()
                )

                if not spoken_form:
                    continue

                form_type_tag = infl.select_one(
                    ".InflectedForm__FormType"
                )

                form_type = (
                    clean_text(
                        form_type_tag.get_text()
                    )
                    if form_type_tag
                    else "inflected"
                )

                translation_tag = infl.select_one(
                    ".InflectedForm__Translation"
                )

                translation = (
                    clean_text(
                        translation_tag.get_text()
                    )
                    if translation_tag
                    else ""
                )

                audio_tag = infl.select_one(
                    "audio[src]"
                )

                audio_url = extract_audio_url(
                    audio_tag
                )

                if not audio_url:
                    continue

                corpus_items.append({
                    "entry_id": entry_id,
                    "lemma": lemma,
                    "spoken_form": spoken_form,
                    "normalized_form":
                        clean_text(spoken_form).lower()
                        if NORMALIZE_CASE
                        else spoken_form,
                    "mfa_pronunciation":
                        pronunciation_for_word(
                            spoken_form
                        ),
                    "form_type": form_type,
                    "translation": translation,
                    "part_of_speech": pos,
                    "definitions":
                        " ; ".join(definitions),
                    "speaker_type": "unknown",
                    "audio_url": audio_url,
                    "audio_filename":
                        audio_url.split("/")[-1]
                        if audio_url else "",
                    "html_hash": html_sha256,
                })

        page_counter += 1

        if (
            TEST_MODE
            and MAX_PAGES_PER_TERM is not None
            and page_counter >= MAX_PAGES_PER_TERM
        ):
            break

        next_link = soup.select_one(
            'a[rel="next"]'
        )

        if not next_link:
            break

        offset += PAGE_SIZE

        time.sleep(
            REQUEST_DELAY_SECONDS
        )

    print(
        f"Finished '{term}': "
        f"{term_entry_count} cards, "
        f"{len(term_entry_ids)} unique entries"
    )
    
    search_stats[term] = {
        "cards": term_entry_count,
        "unique_entries": len(term_entry_ids),
    }

# =============================================================================
# SAVE ENTRIES
# =============================================================================

with open(
    OUTPUT_DIR / ENTRIES_JSON,
    "w",
    encoding="utf-8",
) as f:
    json.dump(
        entries,
        f,
        ensure_ascii=False,
        indent=2,
    )

# =============================================================================
# SAVE CORPUS CSV
# =============================================================================

corpus_df = pd.DataFrame(
    corpus_items
)

corpus_df.to_csv(
    OUTPUT_DIR / CORPUS_CSV,
    index=False,
)

# =============================================================================
# SAVE JSONL
# =============================================================================

with open(
    OUTPUT_DIR / CORPUS_JSONL,
    "w",
    encoding="utf-8",
) as f:

    for row in corpus_items:

        f.write(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            + "\n"
        )

# =============================================================================
# DOWNLOAD MANIFEST
# =============================================================================

manifest_columns = [
    "audio_filename",
    "audio_url",
    "spoken_form",
    "lemma",
    "entry_id",
]

corpus_df[
    manifest_columns
].to_csv(
    OUTPUT_DIR / MANIFEST_CSV,
    index=False,
)

# =============================================================================
# MFA DICTIONARY
# =============================================================================

if GENERATE_MFA_DICTIONARY:

    unique_words = {}

    for row in corpus_items:

        word = row["normalized_form"]

        if not word:
            continue

        if word not in unique_words:
            unique_words[word] = True

    lines = []

    for word in sorted(unique_words):

        pronunciation = (
            pronunciation_for_word(word)
        )

        lines.append(
            f"{word}\t{pronunciation}"
        )

    with open(
        OUTPUT_DIR / MFA_DICTIONARY,
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            "\n".join(lines)
        )
        
# =============================================================================
# PROBLEM ENTRIES
# =============================================================================

with open(
    OUTPUT_DIR / PROBLEM_ENTRIES_JSON,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        problem_entries,
        f,
        ensure_ascii=False,
        indent=2,
    )

# =============================================================================
# SUMMARY
# =============================================================================

summary = {

    "scraped_at":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "entries":
        len(entries),

    "problem_entries":
        len(problem_entries),

    "corpus_items":
        len(corpus_items),

    "unique_words":
        len({
            (
                x["normalized_form"]
                if NORMALIZE_CASE
                else x["spoken_form"]
            )
            for x in corpus_items
            if x["spoken_form"]
        }),

    "recordings_with_audio":
        len([
            x
            for x in corpus_items
            if x["audio_url"]
        ]),

    "female_recordings":
        len([
            x
            for x in corpus_items
            if x.get(
                "speaker_type"
            ) == "female"
        ]),

    "male_recordings":
        len([
            x
            for x in corpus_items
            if x.get(
                "speaker_type"
            ) == "male"
        ]),

    "unknown_speaker_recordings":
        len([
            x
            for x in corpus_items
            if x.get(
                "speaker_type"
            ) == "unknown"
        ]),
}

with open(
    OUTPUT_DIR / SUMMARY_JSON,
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        summary,
        f,
        indent=2,
    )

# =============================================================================
# FINISHED
# =============================================================================

print()
print("=" * 80)
print("SCRAPE COMPLETE")
print("=" * 80)

print()
print(json.dumps(
    corpus_items[:PRINT_SAMPLE_ITEMS],
    ensure_ascii=False,
    indent=2,
))

print()
print(json.dumps(
    summary,
    indent=2,
))

print("\nENTRY COUNTS BY SEARCH TERM")
print("=" * 40)

for term, stats in search_stats.items():
    print(
        f"{term:>4} : "
        f"{stats['unique_entries']:>5} entries"
    )
