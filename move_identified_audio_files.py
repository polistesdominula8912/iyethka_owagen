#!/usr/bin/env python3

from pathlib import Path
import csv
import shutil

CORPUS_DIR = Path(r"C:\Users\jay\mfa_data\my_corpus")
PREDICTIONS_FILE = CORPUS_DIR / "speaker_predictions.tsv"
TRANSCRIPT_EXT = ".txt"

UNKNOWN_FOLDER = "TR"

moved_audio = 0
moved_transcripts = 0
already_done = 0
missing_source = 0
errors = 0

with open(PREDICTIONS_FILE, "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:

        action = row["action"].strip().upper()

        if action != "AUTO":
            continue

        speaker = row["predicted_speaker"].strip()
        audio_name = row["file"].strip()

        if not speaker:
            continue

        destination_folder = CORPUS_DIR / speaker
        destination_folder.mkdir(exist_ok=True)

        stem = Path(audio_name).stem

        # Find current location of audio
        matches = list(CORPUS_DIR.rglob(audio_name))

        if not matches:
            print(f"[SKIP] Not found: {audio_name}")
            missing_source += 1
            continue

        audio_path = matches[0]

        # Already in correct folder?
        if audio_path.parent.name == speaker:
            already_done += 1
            continue

        destination_audio = destination_folder / audio_path.name

        try:
            shutil.move(str(audio_path), str(destination_audio))
            moved_audio += 1

            print(
                f"[AUDIO] {audio_path.parent.name}"
                f" -> {speaker} : {audio_name}"
            )

        except Exception as e:
            print(f"[ERROR] {audio_name}: {e}")
            errors += 1
            continue

        # Move transcript if present
        transcript_name = stem + TRANSCRIPT_EXT

        transcript_matches = list(
            CORPUS_DIR.rglob(transcript_name)
        )

        if transcript_matches:

            transcript_path = transcript_matches[0]

            if transcript_path.parent.name != speaker:

                try:
                    shutil.move(
                        str(transcript_path),
                        str(destination_folder / transcript_path.name)
                    )
                    moved_transcripts += 1

                except Exception as e:
                    print(
                        f"[ERROR] transcript {transcript_name}: {e}"
                    )
                    errors += 1

print("\n===== SUMMARY =====")
print(f"Audio moved:       {moved_audio}")
print(f"Transcripts moved: {moved_transcripts}")
print(f"Already correct:   {already_done}")
print(f"Missing source:    {missing_source}")
print(f"Errors:            {errors}")
