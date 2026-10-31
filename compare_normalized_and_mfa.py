import json
import os
import re
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import pygame

# ============================================================
# CONFIGURATION
# ============================================================

JSONL_FILE = r"C:\Users\jay\mfa_data\corpus_items_spoken_fixed.txt"

AUDIO_DIR = r"C:\Users\jay\mfa_data\my_corpus\downloads\original_mp3"

SPECIAL_CHARS = "â,î,û,ṯẖ".split(",")

# ============================================================
# OPTIONAL FILTERS / FLAGS
# Add new checks here later.
# Return True if an entry should be shown.
# ============================================================


def should_show_entry(entry):
    reconstructed = mfa_to_normalized(
        entry.get("mfa_pronunciation", "")
    )

    normalized = entry.get("normalized_form", "").strip()

    # Current flag
    if reconstructed != normalized:
        return True

    # --------------------------------------------------------
    # FUTURE EXAMPLES
    # --------------------------------------------------------

    # if entry.get("aa_review_status") == "manual":
    #     return True

    # if "â" in entry.get("spoken_form", ""):
    #     return True

    # if "'" in entry.get("mfa_pronunciation", ""):
    #     return True

    # if entry.get("form_type") != "lemma":
    #     return True

    return False


# ============================================================
# AUDIO
# ============================================================

try:
    import pygame

    pygame.mixer.init()
    AUDIO_ENABLED = True

except Exception:
    AUDIO_ENABLED = False
    print("pygame not available; audio disabled")


# ============================================================
# MFA RECONSTRUCTION
# ============================================================

VOWELS = set(
    list("aeiou")
    + ["â", "î", "û"]
)


def is_vowel(token):
    return token in VOWELS


def mfa_to_normalized(mfa):
    """
    Convert MFA pronunciation back to orthography.

    Rules:
    - single spaces removed
    - triple spaces become word spaces
    - apostrophe only retained between identical vowels
    """

    if not mfa:
        return ""

    words = [w.strip() for w in re.split(r"\s{3,}", mfa.strip())]

    converted_words = []

    for word in words:
        tokens = word.split()

        result = ""
        i = 0

        while i < len(tokens):
            tok = tokens[i]

            if tok == "'":
                prev_tok = tokens[i - 1] if i > 0 else ""
                next_tok = tokens[i + 1] if i + 1 < len(tokens) else ""

                if (
                    prev_tok == next_tok
                    and is_vowel(prev_tok)
                ):
                    result += "'"

                i += 1
                continue

            result += tok
            i += 1

        converted_words.append(result)

    return " ".join(converted_words).strip()


# ============================================================
# LOAD DATA
# ============================================================

entries = []

with open(JSONL_FILE, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f):
        line = line.strip()

        if not line:
            continue

        try:
            obj = json.loads(line)

            obj["_line_num"] = line_num

            if should_show_entry(obj):
                entries.append(obj)

        except Exception as e:
            print(f"Bad JSON on line {line_num + 1}: {e}")

if not entries:
    print("No flagged entries found.")
    raise SystemExit

# ============================================================
# LOAD COMPLETE FILE FOR SAVING
# ============================================================

all_lines = []

with open(JSONL_FILE, "r", encoding="utf-8") as f:
    for line in f:
        all_lines.append(json.loads(line))

backup_created = False


def ensure_backup():
    global backup_created

    if backup_created:
        return

    backup_path = JSONL_FILE + ".bak"

    if not os.path.exists(backup_path):
        shutil.copy2(JSONL_FILE, backup_path)
        print(f"Created backup: {backup_path}")

    backup_created = True


# ============================================================
# GUI
# ============================================================

root = tk.Tk()
root.title("MFA Mismatch Editor")
root.geometry("1200x850")

current_index = 0
current_field = None


def insert_special(char):
    widget = root.focus_get()

    if isinstance(widget, tk.Entry):
        widget.insert(tk.INSERT, char)


def play_audio():
    if not AUDIO_ENABLED:
        return

    try:
        pygame.mixer.music.stop()

        filename = entries[current_index].get("audio_filename", "")

        path = os.path.join(AUDIO_DIR, filename)

        if os.path.exists(path):
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()

    except Exception as e:
        print("Audio error:", e)


def save_current():
    entry = entries[current_index]

    entry["lemma"] = lemma_var.get()
    entry["spoken_form"] = spoken_var.get()
    entry["normalized_form"] = normalized_var.get()
    entry["mfa_pronunciation"] = mfa_var.get()

    original_index = entry["_line_num"]

    all_lines[original_index]["lemma"] = entry["lemma"]
    all_lines[original_index]["spoken_form"] = entry["spoken_form"]
    all_lines[original_index]["normalized_form"] = entry["normalized_form"]
    all_lines[original_index]["mfa_pronunciation"] = entry["mfa_pronunciation"]

    ensure_backup()

    with open(JSONL_FILE, "w", encoding="utf-8") as f:
        for obj in all_lines:
            f.write(
                json.dumps(obj, ensure_ascii=False)
                + "\n"
            )


def load_entry(idx):
    global current_index

    current_index = idx

    entry = entries[idx]

    lemma_var.set(entry.get("lemma", ""))
    spoken_var.set(entry.get("spoken_form", ""))
    normalized_var.set(entry.get("normalized_form", ""))
    mfa_var.set(entry.get("mfa_pronunciation", ""))

    reconstruction_var.set(
        mfa_to_normalized(
            entry.get("mfa_pronunciation", "")
        )
    )

    status_var.set(
        f"{idx + 1} / {len(entries)}"
    )

    remaining_var.set(
        f"Remaining: {len(entries) - idx - 1}"
    )

    info_var.set(
        f"form_type={entry.get('form_type','')} | "
        f"speaker={entry.get('speaker_type','')} | "
        f"audio={entry.get('audio_filename','')}"
    )

    play_audio()


def next_entry():
    save_current()

    if current_index < len(entries) - 1:
        load_entry(current_index + 1)
    else:
        messagebox.showinfo(
            "Finished",
            "No more flagged entries."
        )


def previous_entry():
    save_current()

    if current_index > 0:
        load_entry(current_index - 1)


def replay_audio():
    play_audio()


# ============================================================
# WIDGETS
# ============================================================

top_frame = ttk.Frame(root)
top_frame.pack(fill="x", padx=10, pady=5)

status_var = tk.StringVar()
remaining_var = tk.StringVar()

ttk.Label(
    top_frame,
    textvariable=status_var,
    font=("Segoe UI", 12, "bold")
).pack(side="left", padx=10)

ttk.Label(
    top_frame,
    textvariable=remaining_var
).pack(side="left", padx=10)

info_var = tk.StringVar()

ttk.Label(
    root,
    textvariable=info_var
).pack(fill="x", padx=10, pady=5)

# ------------------------------------------------------------

chars_frame = ttk.LabelFrame(
    root,
    text="Special Characters"
)

chars_frame.pack(fill="x", padx=10, pady=5)

for c in SPECIAL_CHARS:
    ttk.Button(
        chars_frame,
        text=c,
        width=5,
        command=lambda ch=c: insert_special(ch)
    ).pack(side="left", padx=2, pady=4)

# ------------------------------------------------------------

fields_frame = ttk.Frame(root)
fields_frame.pack(fill="both", expand=True, padx=10)

lemma_var = tk.StringVar()
spoken_var = tk.StringVar()
normalized_var = tk.StringVar()
mfa_var = tk.StringVar()
reconstruction_var = tk.StringVar()

FIELD_WIDTH = 120

ttk.Label(
    fields_frame,
    text="Lemma"
).pack(anchor="w")

lemma_entry = ttk.Entry(
    fields_frame,
    textvariable=lemma_var,
    width=FIELD_WIDTH
)
lemma_entry.pack(fill="x", pady=2)

ttk.Label(
    fields_frame,
    text="Spoken Form"
).pack(anchor="w")

spoken_entry = ttk.Entry(
    fields_frame,
    textvariable=spoken_var,
    width=FIELD_WIDTH
)
spoken_entry.pack(fill="x", pady=2)

ttk.Label(
    fields_frame,
    text="Normalized Form"
).pack(anchor="w")

normalized_entry = ttk.Entry(
    fields_frame,
    textvariable=normalized_var,
    width=FIELD_WIDTH
)
normalized_entry.pack(fill="x", pady=2)

ttk.Label(
    fields_frame,
    text="MFA Pronunciation"
).pack(anchor="w")

mfa_entry = ttk.Entry(
    fields_frame,
    textvariable=mfa_var,
    width=FIELD_WIDTH
)
mfa_entry.pack(fill="x", pady=2)

ttk.Label(
    fields_frame,
    text="Reconstructed MFA Form"
).pack(anchor="w", pady=(10, 0))

recon_label = ttk.Label(
    fields_frame,
    textvariable=reconstruction_var,
    foreground="blue"
)
recon_label.pack(anchor="w")

# ------------------------------------------------------------

nav_frame = ttk.Frame(root)
nav_frame.pack(fill="x", pady=10)

ttk.Button(
    nav_frame,
    text="◀ Previous",
    command=previous_entry
).pack(side="left", padx=5)

ttk.Button(
    nav_frame,
    text="Replay Audio",
    command=replay_audio
).pack(side="left", padx=5)

ttk.Button(
    nav_frame,
    text="Save + Next ▶",
    command=next_entry
).pack(side="right", padx=5)

# ============================================================
# KEYBOARD SHORTCUTS
# ============================================================

root.bind("<Return>", lambda e: next_entry())

root.bind("<Control-s>", lambda e: save_current())

root.bind("<Left>", lambda e: previous_entry())

root.bind("<Right>", lambda e: next_entry())

# ============================================================
# START
# ============================================================

load_entry(0)

root.mainloop()
