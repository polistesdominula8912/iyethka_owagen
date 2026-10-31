import json
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

import pygame

# ----------------------------------------------------
# CONFIG
# ----------------------------------------------------

CORPUS_FILE = "corpus_items.txt"
AUDIO_DIR = Path(r"C:\Users\jay\mfa_data\my_corpus\downloads\original_mp3")

pygame.mixer.init()

last_saved = None
last_status = None

# ----------------------------------------------------
# DATA LOADING
# ----------------------------------------------------


def load_entries():

    entries = {}
    all_lines = []

    with open(CORPUS_FILE, encoding="utf-8") as f:

        for line_num, line in enumerate(f):

            line = line.strip()

            if not line:
                continue

            try:
                obj = json.loads(line)
            except Exception:
                continue

            all_lines.append(obj)

            if obj.get("form_type") != "lemma":
                continue

            lemma = obj.get("lemma", "")

            if "oo" not in lemma.lower():
                continue

            if obj.get("aa_review_status"):
                continue

            eid = obj["entry_id"]

            if eid not in entries:
                entries[eid] = {
                    "entry": obj,
                    "audio_files": [],
                }

            filename = obj.get("audio_filename")

            if filename:
                entries[eid]["audio_files"].append(filename)

    return entries, all_lines


entries, corpus = load_entries()

entry_list = list(entries.values())
current_index = 0


# ----------------------------------------------------
# SAVE
# ----------------------------------------------------


def save_corpus():

    with open(CORPUS_FILE, "w", encoding="utf-8") as f:

        for item in corpus:
            f.write(
                json.dumps(
                    item,
                    ensure_ascii=False
                )
                + "\n"
            )

def get_current_values():

    return {
        "lemma":
            lemma_entry.get(),
        "pron":
            pron_entry.get(),
        "definition":
            definition_text.get(
                "1.0",
                tk.END
            ).strip()
    }

# ----------------------------------------------------
# LOOKUP
# ----------------------------------------------------


def update_entry(
        entry_id,
        status,
        lemma,
        pron
):

    for obj in corpus:

        if obj.get("entry_id") != entry_id:
            continue

        obj["lemma"] = lemma
        obj["mfa_pronunciation"] = pron

        obj["aa_review_status"] = status

    save_corpus()

def save_decision(status):

    global last_saved
    global last_status

    entry = entry_list[current_index]["entry"]

    vals = get_current_values()

    update_entry(
        entry["entry_id"],
        status,
        vals["lemma"],
        vals["pron"]
    )

    last_saved = vals
    last_status = status

    next_entry()

def save_and_break(event):

    save_manual()

    return "break"

# ----------------------------------------------------
# AUDIO
# ----------------------------------------------------


def play_file(filepath):

    try:

        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.wait(100)

    except Exception as e:
        print(e)


def play_all():

    entry = entry_list[current_index]

    def worker():

        for fn in entry["audio_files"]:

            path = AUDIO_DIR / fn

            if path.exists():
                play_file(str(path))

    threading.Thread(
        target=worker,
        daemon=True
    ).start()


def play_selected(index):

    entry = entry_list[current_index]

    if index >= len(entry["audio_files"]):
        return

    path = AUDIO_DIR / entry["audio_files"][index]

    if not path.exists():
        return

    threading.Thread(
        target=lambda: play_file(str(path)),
        daemon=True
    ).start()


# ----------------------------------------------------
# UI
# ----------------------------------------------------


root = tk.Tk()
root.title("AA Review")
root.geometry("900x650")

tk.Label(root, text="Lemma").pack()

lemma_entry = tk.Entry(
    root,
    font=("Arial", 20)
)
lemma_entry.pack(fill="x", padx=10)

tk.Label(root, text="Pronunciation").pack()

pron_entry = tk.Entry(
    root,
    font=("Courier", 14),
    width=120
)

pron_entry.pack(fill="x", padx=10)

tk.Label(root, text="Definition").pack()

definition_text = tk.Text(
    root,
    height=4,
    wrap="word"
)
definition_text.pack(
    fill="x",
    padx=10,
    pady=10
)
progress_var = tk.StringVar()



progress_label = tk.Label(
    root,
    textvariable=progress_var
)
progress_label.pack()

audio_frame = tk.Frame(root)
audio_frame.pack(pady=10)

play_all_btn = tk.Button(
    audio_frame,
    text="▶ Play All",
    command=play_all,
    width=15
)

play_all_btn.pack()


recording_frame = tk.Frame(root)
recording_frame.pack(pady=10)

button_frame = tk.Frame(root)
button_frame.pack(pady=20)

separator = tk.Frame(
    root,
    height=2,
    bg="grey"
)
separator.pack(fill="x", pady=10)

tk.Label(
    root,
    text="Previous Entry",
    font=("Arial", 14, "bold")
).pack()

prev_lemma = tk.Entry(root)
prev_lemma.pack(fill="x", padx=10)

prev_pron = tk.Entry(root)
prev_pron.pack(fill="x", padx=10)

prev_status_var = tk.StringVar()

tk.Label(
    root,
    textvariable=prev_status_var
).pack()

special_frame = tk.Frame(root)
special_frame.pack(pady=10)

# ----------------------------------------------------
# SPECIAL CHARACTERS
# ----------------------------------------------------

chars = [
    "â",
    "î",
    "û",
    "ê",
    "ô",
    "ṯẖ",
    "'"
]

def insert_char(c):

    widget = root.focus_get()

    if hasattr(widget, "insert"):
        widget.insert(
            "insert",
            c
        )

for ch in chars:

    tk.Button(
        special_frame,
        text=ch,
        width=3,
        command=lambda c=ch:
            insert_char(c)
    ).pack(
        side="left",
        padx=2
    )

# ----------------------------------------------------
# NAVIGATION
# ----------------------------------------------------


def load_current():

    global current_index

    if current_index >= len(entry_list):

        messagebox.showinfo(
            "Done",
            "Review complete!"
        )

        root.destroy()
        return

    entry = entry_list[current_index]["entry"]

    lemma_entry.delete(0, tk.END)
    lemma_entry.insert(
        0,
        entry.get("lemma", "")
    )

    pron_entry.delete(0, tk.END)
    pron_entry.insert(
        0,
        entry.get("mfa_pronunciation", "")
    )

    definition_text.delete("1.0", tk.END)
    definition_text.insert(
        "1.0",
        entry.get("definitions", "")
    )

    if last_saved:

        prev_lemma.delete(0, tk.END)
        prev_lemma.insert(
            0,
            last_saved["lemma"]
        )

        prev_pron.delete(0, tk.END)
        prev_pron.insert(
            0,
            last_saved["pron"]
        )

        prev_status_var.set(
            f"Status: {last_status}"
        )

    progress_var.set(
        f"{current_index+1} / {len(entry_list)}"
    )

    for widget in recording_frame.winfo_children():
        widget.destroy()

    files = entry_list[current_index]["audio_files"]

    for i, file in enumerate(files):

        b = tk.Button(
            recording_frame,
            text=f"Play #{i+1}",
            command=lambda n=i: play_selected(n)
        )

        b.pack(
            side="left",
            padx=4
        )

    root.after(500, play_all)

    lemma_entry.selection_range(0, tk.END)
    root.focus_force()


def next_entry():

    global current_index
    current_index += 1
    load_current()


# ----------------------------------------------------
# DECISIONS
# ----------------------------------------------------


def choose_glottal():

    lemma = lemma_entry.get()

    lemma = (
        lemma
        .replace("oo", "o'o")
        .replace("ee", "e'e")
    )

    lemma_entry.delete(0, tk.END)
    lemma_entry.insert(0, lemma)

    save_decision("glottal")


def choose_long():

    pron = pron_entry.get()

    pron = (
        pron
        .replace("o ' o", "oo")
        .replace("e ' e", "ee")
    )

    pron_entry.delete(0, tk.END)
    pron_entry.insert(0, pron)

    save_decision("long")

def make_short(text):

    text = text.replace("o'o", "o")
    text = text.replace("o ' o", "o")
    text = text.replace("oo", "o")

    text = text.replace("e'e", "e")
    text = text.replace("e ' e", "e")
    text = text.replace("ee", "e")

    return text

def choose_short():

    lemma = make_short(
        lemma_entry.get()
    )

    pron = make_short(
        pron_entry.get()
    )

    lemma_entry.delete(0, tk.END)
    lemma_entry.insert(0, lemma)

    pron_entry.delete(0, tk.END)
    pron_entry.insert(0, pron)

    save_decision("short")


def choose_disputed():
    save_decision("disputed")


def skip():

    next_entry()

def previous_entry():

    global current_index

    if current_index > 0:
        current_index -= 1
        load_current()

def save_manual():

    global last_saved
    global last_status

    entry = entry_list[current_index]["entry"]

    vals = get_current_values()

    update_entry(
        entry["entry_id"],
        "manual",
        vals["lemma"],
        vals["pron"]
    )

    last_saved = vals
    last_status = "manual"

    next_entry()

    root.focus_force()

# ----------------------------------------------------
# BUTTONS
# ----------------------------------------------------

tk.Button(
    button_frame,
    text="G\nGlottal Stop",
    width=18,
    height=3,
    command=choose_glottal
).grid(row=0, column=0, padx=5)

tk.Button(
    button_frame,
    text="L\nLong Vowel",
    width=18,
    height=3,
    command=choose_long
).grid(row=0, column=1, padx=5)

tk.Button(
    button_frame,
    text="Q\nShort Vowel",
    width=18,
    height=3,
    command=choose_short
).grid(row=0, column=2, padx=5)

tk.Button(
    button_frame,
    text="D\nDisputed",
    width=18,
    height=3,
    command=choose_disputed
).grid(row=0, column=3, padx=5)

tk.Button(
    button_frame,
    text="S\nSkip",
    width=18,
    height=3,
    command=skip
).grid(row=0, column=4, padx=5)

tk.Button(
    root,
    text="← Previous",
    command=previous_entry
).pack()

tk.Button(
    root,
    text="Enter\nSave Manual Edit",
    command=save_manual
).pack()

# ----------------------------------------------------
# SHORTCUT KEYS
# ----------------------------------------------------

root.bind_all("g", lambda e: choose_glottal())
root.bind_all("l", lambda e: choose_long())
root.bind_all("q", lambda e: choose_short())
root.bind_all("d", lambda e: choose_disputed())
root.bind_all("s", lambda e: skip())
root.bind_all("r", lambda e: play_all())
lemma_entry.bind("<Return>", lambda e: save_manual())
pron_entry.bind("<Return>", lambda e: save_manual())
definition_text.bind("<Return>", save_and_break)

# ----------------------------------------------------

load_current()

root.mainloop()
