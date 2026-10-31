"""
Resumable MFA Corpus Builder
============================

Input:
    stoney_output/corpus_items.csv

Output:

    mfa_corpus/
        downloads/
            original_mp3/
            wav/

        transcripts/

        metadata/

Features
--------

✓ Resume after interruption
✓ Safe Ctrl+C handling
✓ Automatic checkpoints
✓ Progress estimates
✓ Download statistics
✓ WAV conversion
✓ MFA transcript creation

To safely pause at any time:

    CTRL+C

Progress will be saved automatically.
"""

from pathlib import Path
import json
import signal
import time
from datetime import timedelta
import statistics
import threading

import pandas as pd
import requests

from pydub import AudioSegment
from pydub.utils import which
if which("ffmpeg") is None:
    raise RuntimeError(
        "FFmpeg not found."
    )

# ============================================================================
# EXECUTION MODES
# ============================================================================

TEST_MODE = False

# Number of recordings to process during a test run.
TEST_LIMIT = 25

# Enable audit before downloading.
RUN_AUDIT = True

# Seconds to wait for user input.
CONTINUE_TIMEOUT = 20

# ============================================================================
# CONFIG
# ============================================================================

INPUT_CSV = "stoney_output/corpus_items.csv"

CORPUS_ROOT = Path("mfa_corpus")

MP3_DIR = CORPUS_ROOT / "downloads" / "original_mp3"

WAV_DIR = CORPUS_ROOT / "downloads" / "wav"

LAB_DIR = CORPUS_ROOT / "transcripts"

META_DIR = CORPUS_ROOT / "metadata"

STATE_FILE = META_DIR / "download_state.json"

FAILURES_FILE = META_DIR / "failures.csv"

MANIFEST_FILE = META_DIR / "corpus_manifest.csv"

# Audio format for MFA

TARGET_SAMPLE_RATE = 16000

TARGET_CHANNELS = 1

# Save progress every N completed items

CHECKPOINT_INTERVAL = 50

# Print progress every N completed items

STATUS_INTERVAL = 25

REQUEST_TIMEOUT = 120

# ============================================================================

for p in [
    MP3_DIR,
    WAV_DIR,
    LAB_DIR,
    META_DIR,
]:
    p.mkdir(
        parents=True,
        exist_ok=True
    )

# ============================================================================
# LOAD DATA
# ============================================================================

df = pd.read_csv(INPUT_CSV)

df = df[
    df["audio_url"].notna()
]

if TEST_MODE:

    print()
    print("=" * 80)
    print("TEST MODE ENABLED")
    print("=" * 80)

    print(
        f"Limiting run to first "
        f"{TEST_LIMIT} recordings."
    )

    df = df.head(TEST_LIMIT)

TOTAL_RECORDINGS = len(df)

# ============================================================================
# LOAD STATE
# ============================================================================

if STATE_FILE.exists():

    with open(
        STATE_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        state = json.load(f)

else:

    state = {
        "completed": [],
        "downloaded_bytes": 0
    }

completed = set(
    state.get(
        "completed",
        []
    )
)

downloaded_bytes = (
    state.get(
        "downloaded_bytes",
        0
    )
)

# ============================================================================
# CTRL+C
# ============================================================================

shutdown_requested = False


def handle_interrupt(
    signum,
    frame
):
    global shutdown_requested

    shutdown_requested = True

    print()
    print("=" * 60)
    print("PAUSE REQUEST RECEIVED")
    print("Saving progress...")
    print("=" * 60)


signal.signal(
    signal.SIGINT,
    handle_interrupt
)

# ============================================================================
# STATE SAVE
# ============================================================================


def save_state():

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "completed":
                    sorted(
                        completed
                    ),
                "downloaded_bytes":
                    downloaded_bytes
            },
            f,
            indent=2
        )

# ============================================================================
# SIZE AUDIT
# ============================================================================

def estimate_download_size(
    session,
    dataframe,
    sample_size=100
):

    print()
    print("=" * 80)
    print("AUDITING DOWNLOAD SIZE")
    print("=" * 80)

    sample = dataframe.sample(
        min(sample_size, len(dataframe)),
        random_state=42
    )

    sizes = []

    for _, row in sample.iterrows():

        try:

            url = row["audio_url"]

            response = session.head(
                url,
                timeout=30,
                allow_redirects=True,
            )

            size = int(
                response.headers.get(
                    "Content-Length",
                    0
                )
            )

            if size > 0:
                sizes.append(size)

        except Exception:
            pass

    if not sizes:

        print(
            "Could not estimate size."
        )
        return None

    avg_size = statistics.mean(
        sizes
    )

    estimate = (
        avg_size
        * len(dataframe)
    )

    print(
        f"Sampled files: "
        f"{len(sizes)}"
    )

    print(
        f"Average size: "
        f"{human_bytes(avg_size)}"
    )

    print(
        f"Estimated total download: "
        f"{human_bytes(estimate)}"
    )

    estimated_wav_size = estimate * 0.6

    print(
        f"Estimated WAV size: "
        f"{human_bytes(estimated_wav_size)}"
    )

    print(
        f"Estimated total storage: "
        f"{human_bytes(
            estimate +
            estimated_wav_size
        )}"
    )

    return estimate

# ============================================================================
# UTILS
# ============================================================================


def human_bytes(num):

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB"
    ]

    size = float(num)

    for unit in units:

        if size < 1024:
            return f"{size:.1f} {unit}"

        size /= 1024

    return f"{size:.1f} PB"


def format_duration(seconds):

    return str(
        timedelta(
            seconds=int(seconds)
        )
    )

user_choice = None

def get_user_input():

    global user_choice

    try:

        user_choice = input(
            "\nContinue? "
            "(Y/n) "
        )

    except EOFError:
        user_choice = None


# ============================================================================
# START
# ============================================================================

print()
print("=" * 80)
print("STONEY MFA CORPUS BUILDER")
print("=" * 80)

print(
    f"Total recordings to process: "
    f"{TOTAL_RECORDINGS:,}"
)

print(
    f"Already completed: "
    f"{len(completed):,}"
)

print()
print(
    "To safely pause at any time:"
)
print(
    "    Press CTRL+C"
)
print(
    "Progress will be saved automatically."
)
print()

session = requests.Session()

if RUN_AUDIT:

    estimated_size = (
        estimate_download_size(
            session,
            df
        )
    )

    print()

    print(
        "Press Ctrl+C at any time "
        "to pause safely."
    )

    print()

    thread = threading.Thread(
        target=get_user_input
    )

    thread.daemon = True

    thread.start()

    print(
        f"Waiting "
        f"{CONTINUE_TIMEOUT} seconds..."
    )

    thread.join(
        CONTINUE_TIMEOUT
    )

    if (
        user_choice is not None
        and user_choice.lower().strip()
        in ["n", "no"]
    ):

        print()

        print(
            "Download cancelled."
        )

        raise SystemExit()

    print()

    print(
        "Proceeding with download."
    )

start_time = time.time()

if MANIFEST_FILE.exists():

    manifest_rows = pd.read_csv(
        MANIFEST_FILE
    ).to_dict(
        orient="records"
    )

else:

    manifest_rows = []

existing_manifest_files = {
    row["wav_file"]
    for row in manifest_rows
}

if FAILURES_FILE.exists():
    failure_rows = pd.read_csv(
        FAILURES_FILE
    ).to_dict(
        orient="records"
    )
else:
    failure_rows = []

newly_completed = 0

existing_size = sum(
    p.stat().st_size
    for p in MP3_DIR.glob("*.mp3")
)

downloaded_bytes = max(
    downloaded_bytes,
    existing_size
)

starting_completed = len(completed)

# ============================================================================
# PROCESS
# ============================================================================

for _, row in df.iterrows():

    if shutdown_requested:
        break

    audio_url = str(
        row["audio_url"]
    )

    filename = str(
        row["audio_filename"]
    )

    if filename in completed:
        continue

    stem = Path(
        filename
    ).stem

    mp3_path = (
        MP3_DIR / filename
    )

    wav_path = (
        WAV_DIR /
        f"{stem}.wav"
    )

    lab_path = (
        LAB_DIR /
        f"{stem}.lab"
    )

    try:

        # ==========================================================
        # DOWNLOAD MP3
        # ==========================================================

        file_size = 0

        if not mp3_path.exists():

            response = session.get(
                audio_url,
                timeout=REQUEST_TIMEOUT,
                stream=True
            )

            response.raise_for_status()

            with open(
                mp3_path,
                "wb"
            ) as f:

                for chunk in response.iter_content(
                    chunk_size=65536
                ):

                    if chunk:

                        f.write(chunk)

                        file_size += len(
                            chunk
                        )

            downloaded_bytes += (
                file_size
            )

        else:

            file_size = (
                mp3_path.stat()
                .st_size
            )

        # ==========================================================
        # WAV CONVERSION
        # ==========================================================

        if not wav_path.exists():

            audio = AudioSegment.from_file(
                mp3_path
            )

            audio = (
                audio
                .set_channels(
                    TARGET_CHANNELS
                )
                .set_frame_rate(
                    TARGET_SAMPLE_RATE
                )
            )

            audio.export(
                wav_path,
                format="wav"
            )

        # ==========================================================
        # TRANSCRIPT
        # ==========================================================

        if not lab_path.exists():

            transcription = (
                str(
                    row[
                        "normalized_form"
                    ]
                )
                .strip()
            )

            with open(
                lab_path,
                "w",
                encoding="utf-8"
            ) as f:

                f.write(
                    transcription
                )

        if str(wav_path) not in existing_manifest_files:

            manifest_rows.append({
                "entry_id":
                    row["entry_id"],
                "lemma":
                    row["lemma"],
                "spoken_form":
                    row["spoken_form"],
                "normalized_form":
                    row["normalized_form"],
                "speaker_type":
                    row.get(
                        "speaker_type",
                        "unknown"
                    ),
                "wav_file":
                    str(wav_path),
                "lab_file":
                    str(lab_path),
            })

            existing_manifest_files.add(
                str(wav_path)
            )

        completed.add(
            filename
        )

        newly_completed += 1

        # ==========================================================
        # STATUS OUTPUT
        # ==========================================================

        if (
            newly_completed %
            STATUS_INTERVAL
            == 0
        ):

            elapsed = (
                time.time()
                - start_time
            )

            completed_count = len(completed)

            processed_this_run = (
                completed_count
                - starting_completed
            )

            rate = (
                processed_this_run / elapsed
                if elapsed > 0
                else 0
            )
            
            remaining = max(
                0,
                TOTAL_RECORDINGS - completed_count
            )

            eta_seconds = (
                remaining / rate
                if rate > 0
                else 0
            )

            avg_file_size = (
                downloaded_bytes
                / completed_count
                if completed_count > 0
                else 0
            )

            projected_final_size = (
                avg_file_size
                * TOTAL_RECORDINGS
            )

            projected_wav_size = (
                projected_final_size * 0.6
            )

            projected_total_storage = (
                projected_final_size
                + projected_wav_size
            )
            
            print(
                f"Estimated final size: "
                f"{human_bytes(projected_final_size)}"
            )

            print(
                f"Estimated WAV size: "
                f"{human_bytes(projected_wav_size)}"
            )

            print(
                f"Estimated total storage: "
                f"{human_bytes(projected_total_storage)}"
            )
            print(
                f"Completed: {completed_count:,}/{TOTAL_RECORDINGS:,}"
            )

            print(
                f"Rate: {rate:.2f} files/sec"
            )

            print(
                f"ETA: {format_duration(eta_seconds)}"
            )

        if newly_completed % CHECKPOINT_INTERVAL == 0:
            save_state()

            pd.DataFrame(manifest_rows).to_csv(
                MANIFEST_FILE,
                index=False
            )

    except Exception as e:
        failure_rows.append({
            "filename": filename,
            "audio_url": audio_url,
            "error": str(e)
        })
        
save_state()

pd.DataFrame(manifest_rows).to_csv(
    MANIFEST_FILE,
    index=False
)

if failure_rows:
    pd.DataFrame(failure_rows).to_csv(
        FAILURES_FILE,
        index=False
    )
elif FAILURES_FILE.exists():
    FAILURES_FILE.unlink()

print("Finished.")
