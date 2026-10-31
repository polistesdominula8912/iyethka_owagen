# pip install speechbrain torchaudio torch numpy soundfile

#!/usr/bin/env python3

from pathlib import Path
from multiprocessing import Pool, cpu_count
from speechbrain.inference.speaker import EncoderClassifier
import torchaudio
import torch
import numpy as np
import pickle
import random
import csv
import soundfile as sf


# =====================================================
# CONFIG
# =====================================================

mfa_dir = Path(r"C:\Users\jay\mfa_data")
CORPUS_DIR = mfa_dir / "my_corpus"

UNKNOWN_FOLDER = "TR"

K = 40

AUTO_SCORE = 0.85
AUTO_MARGIN = 0.10

REVIEW_SCORE = 0.70
REVIEW_MARGIN = 0.05

CACHE_DIR = CORPUS_DIR / "_speaker_cache"

CENTROID_FILE = CACHE_DIR / "speaker_centroids.pkl"
UNKNOWN_EMBED_FILE = CACHE_DIR / "unknown_embeddings.pkl"

CACHE_DIR.mkdir(exist_ok=True)

AUDIO_EXTENSIONS = {
    ".wav",
    ".flac",
    ".mp3",
    ".m4a",
    ".ogg"
}

# =====================================================
# AUDIO HELPERS
# =====================================================

def find_audio_files(folder):
    files = []

    for ext in AUDIO_EXTENSIONS:
        files.extend(folder.glob(f"*{ext}"))

    return sorted(files)

# =====================================================
# EMBEDDING HELPERS
# =====================================================

_classifier = None


def init_worker():

    global _classifier

    device = "cuda:0" if torch.cuda.is_available() else "cpu"

    _classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        run_opts={"device": device}
    )

    print("Using device:", device)

    _classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        run_opts={"device": device}
    )

    print("Model loaded")


def generate_embedding(path):
    try:

        audio, sr = sf.read(path)

        signal = torch.tensor(audio, dtype=torch.float32)

        if signal.ndim == 1:
            signal = signal.unsqueeze(0)
        else:
            signal = signal.T

        emb = _classifier.encode_batch(signal)
        emb = emb.squeeze().detach().cpu().numpy()

        return (path, emb, None)

    except Exception as e:
        print(f"\nFAILED: {path}")
        print(f"ERROR: {e}\n")

        return (path, None, str(e))

def parallel_embed(filelist):
    print("Running sequentially")

    global _classifier

    if _classifier is None:
        init_worker()

    results = []

    for f in filelist:
        results.append(generate_embedding(str(f)))

    return results


# =====================================================
# CENTROIDS
# =====================================================

def build_known_embeddings():
    cache_file = CACHE_DIR / "known_embeddings.pkl"

    if cache_file.exists():
        print("Loading cached known embeddings...")
        with open(cache_file, "rb") as f:
            return pickle.load(f)

    known = []

    for speaker_dir in CORPUS_DIR.iterdir():

        if not speaker_dir.is_dir():
            continue

        if speaker_dir.name == UNKNOWN_FOLDER:
            continue

        if speaker_dir.name.startswith("_"):
            continue

        files = find_audio_files(speaker_dir)

        if not files:
            continue

        print(
            f"{speaker_dir.name}: "
            f"{len(files)} samples"
        )

        for path, emb, err in parallel_embed(files):

            if emb is None:
                continue

            known.append(
                {
                    "speaker": speaker_dir.name,
                    "embedding": emb
                }
            )

    with open(cache_file, "wb") as f:
        pickle.dump(known, f)

    return known

# =====================================================
# UNKNOWN EMBEDDINGS
# =====================================================

def build_unknown_embeddings():

    if UNKNOWN_EMBED_FILE.exists():

        print(
            "Loading cached unknown embeddings..."
        )

        with open(
            UNKNOWN_EMBED_FILE,
            "rb"
        ) as f:

            return pickle.load(f)

    unknown_dir = (
        CORPUS_DIR /
        UNKNOWN_FOLDER
    )

    files = find_audio_files(
        unknown_dir
    )

    print(
        f"Embedding "
        f"{len(files)} "
        f"unknown files..."
    )

    embeddings = {}

    for path, emb, err in (
        parallel_embed(files)
    ):

        if emb is None:

            print(
                f"Failed: "
                f"{Path(path).name}"
            )

            continue

        embeddings[
            Path(path).name
        ] = emb

    with open(
        UNKNOWN_EMBED_FILE,
        "wb"
    ) as f:

        pickle.dump(
            embeddings,
            f
        )

    return embeddings

# =====================================================
# SCORING
# =====================================================

def cosine(a, b):

    return float(
        np.dot(a, b)
        /
        (
            np.linalg.norm(a)
            *
            np.linalg.norm(b)
        )
    )


from collections import defaultdict


def classify_knn(
    known_embeddings,
    unknown_embeddings
):

    rows = []

    for filename, emb in unknown_embeddings.items():

        scores = []

        for sample in known_embeddings:

            score = cosine(
                emb,
                sample["embedding"]
            )

            scores.append(
                (
                    sample["speaker"],
                    score
                )
            )

        scores.sort(
            key=lambda x: x[1],
            reverse=True
        )

        top_k = scores[:K]

        vote_totals = defaultdict(float)

        for speaker, score in top_k:
            vote_totals[speaker] += score

        ranked = sorted(
            vote_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )

        best_speaker, best_vote = ranked[0]

        if len(ranked) > 1:
            second_speaker, second_vote = ranked[1]
        else:
            second_speaker = ""
            second_vote = 0.0

        ratio = best_vote / max(second_vote, 0.01)

        if ratio >= 3:
            action = "AUTO"

        elif ratio >= 1.5:
            action = "REVIEW"

        else:
            action = "KEEP_UNKNOWN"

        rows.append([
            filename,
            best_speaker,
            round(best_vote, 4),
            second_speaker,
            round(second_vote, 4),
            round(ratio, 4),
            action
        ])

    return rows

# =====================================================
# REPORT
# =====================================================

def write_report(rows):

    outfile = (
        CORPUS_DIR /
        "speaker_predictions.tsv"
    )

    with open(
        outfile,
        "w",
        newline="",
        encoding="utf-8"
    ) as f:

        writer = csv.writer(
            f,
            delimiter="\t"
        )

        writer.writerow([
            "file",
            "predicted_speaker",
            "best_score",
            "second_speaker",
            "second_score",
            "ratio",
            "action"
        ])

        writer.writerows(rows)

    print(
        f"\nWritten:\n{outfile}"
    )

# =====================================================
# MAIN
# =====================================================

def main():

    print(
        "CUDA:",
        torch.cuda.is_available()
    )

    if torch.cuda.is_available():

        print(
            torch.cuda.get_device_name(0)
        )

    known_embeddings = build_known_embeddings()

    print(
        f"\nLoaded "
        f"{len(known_embeddings)} known samples"
    )
    
    unknown_embeddings = build_unknown_embeddings()

    rows = classify_knn(
        known_embeddings,
        unknown_embeddings
    )

    write_report(rows)

if __name__ == "__main__":
    main()
