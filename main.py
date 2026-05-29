import argparse
import difflib
import re
import subprocess
import tempfile
import time
from pathlib import Path
import os
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
OUTPUT_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
ALPHA_RE = re.compile(r"[A-Za-zÄÖÜäöüß]")


def extract_last_sentence(text: str) -> str:
    chunks = [text.strip()] if text else []
    if not chunks:
        return ""
    return chunks[-1]


def is_usable_correction(original: str, corrected: str) -> bool:
    if not corrected:
        return False
    if corrected == original:
        return False
    if not ALPHA_RE.search(corrected):
        return False

    original_len = len(original.strip())
    corrected_len = len(corrected.strip())
    if original_len == 0:
        return False
    ratio = corrected_len / original_len
    if ratio < 0.5 or ratio > 2.0:
        return False

    punct_count = sum(1 for ch in corrected if not ch.isalnum() and not ch.isspace())
    if corrected_len > 0 and (punct_count / corrected_len) > 0.4:
        return False
    return True


def normalize_model_output(text: str) -> str:
    cleaned = clean_buffer_text(text)
    if not cleaned:
        return ""
    parts = [p.strip() for p in OUTPUT_SENTENCE_SPLIT_RE.split(cleaned) if p.strip()]
    if not parts:
        return cleaned
    return parts[0]


def correct_sentence(tokenizer, model, sentence: str) -> str:
    if not sentence:
        return ""
    prompt = f"Rechtschreibung: {sentence}"
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True)
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max(32, len(sentence.split()) * 4),
            num_beams=8,
            length_penalty=1.0,
            no_repeat_ngram_size=3,
            repetition_penalty=1.5,
            early_stopping=True,
        )
    corrected = normalize_model_output(
        tokenizer.decode(output_ids[0], skip_special_tokens=True)
    )
    return corrected if is_usable_correction(sentence, corrected) else sentence


def append_to_espanso(
    typo: str,
    correction: str,
    espanso_path: str = "~/.config/espanso/match/packages/typos/config.yml",
) -> None:
    """
    Bereinigt das Typo-Korrektur-Paar und fügt es im korrekten YAML-Format
    am Ende der Espanso-Datei hinzu, ausgenommen reine Groß-/Kleinschreibungs-Änderungen.
    """
    # Whitespace und eventuelle Rest-Klammern entfernen
    clean_typo = typo.strip().replace("[-", "").replace("-]", "")
    clean_corr = correction.strip().replace("{+", "").replace("+}", "")

    # Sicherheits-Check 1: Nur hinzufügen, wenn es sich um echte Wörter handelt
    if not re.search(r"\w", clean_typo) or not re.search(r"\w", clean_corr):
        return

    # AUSNAHME-REGEL: Reine Groß-/Kleinschreibungs-Änderungen ignorieren
    # Wenn sich die Wörter nach dem Kleinmachen (lower) gleichen, fliegen sie raus!
    if clean_typo.lower() == clean_corr.lower():
        return

    full_path = os.path.expanduser(espanso_path)

    # Verzeichnis erstellen, falls es noch nicht existiert
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    # Sicherheits-Check 2: Duplikate in der Datei verhindern
    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            if (
                f'trigger: "{clean_typo}"' in content
                or f"trigger: '{clean_typo}'" in content
            ):
                return  # Bereits vorhanden, wir überspringen das Duplikat

    # Das neue YAML-Match-Paket vorbereiten
    new_match = f'\n  - trigger: "{clean_typo}"\n    replace: "{clean_corr}"\n'

    # Ans Ende der Datei appenden
    with open(full_path, "a", encoding="utf-8") as f:
        f.write(new_match)


def clean_buffer_text(text: str) -> str:
    return text.strip()


def build_clean_diff(original: str, corrected: str) -> str:
    orig_clean = clean_buffer_text(original)
    corr_clean = clean_buffer_text(corrected)

    orig_words = re.findall(r"\w+|\s+|[^\w\s]", orig_clean)
    corr_words = re.findall(r"\w+|\s+|[^\w\s]", corr_clean)

    matcher = difflib.SequenceMatcher(None, orig_words, corr_words)
    result = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        # Berechne den aktuellen Einzug (Länge der letzten Zeile im result)
        current_output = "".join(result)
        if "\n" in current_output:
            current_indent = len(current_output.split("\n")[-1])
        else:
            current_indent = len(current_output)

        indent_spaces = " " * current_indent

        if tag == "equal":
            result.append("".join(orig_words[i1:i2]))
        elif tag == "delete":
            del_text = "".join(orig_words[i1:i2])
            result.append(f"\n{indent_spaces}[[-{del_text}-]]\n{indent_spaces}")
        elif tag == "insert":
            ins_text = "".join(corr_words[j1:j2])
            result.append(f"\n{indent_spaces}{{+{ins_text}+}}\n{indent_spaces}")
        elif tag == "replace":
            del_text = "".join(orig_words[i1:i2])
            ins_text = "".join(corr_words[j1:j2])

            # --- NEU: HIER ERFOLGT DER ESPANSO AUTOMATION CALL ---
            # Wir übergeben das gefundene Fehler-Wort und die Korrektur
            append_to_espanso(del_text, ins_text)
            # -----------------------------------------------------

            result.append(
                f"\n{indent_spaces}[[-{del_text}-]]\n{indent_spaces}{{+{ins_text}+}}\n{indent_spaces}"
            )

    return "".join(result)


def open_diff_in_kitty(original: str, corrected: str) -> None:
    if original == corrected:
        return

    diff_text = build_clean_diff(original, corrected)
    with tempfile.NamedTemporaryFile(
        "w", delete=False, suffix="_diff.txt"
    ) as diff_file:
        diff_file.write(diff_text)
        diff_path = diff_file.name

    kitty_cmd = [
        "kitty",
        "@",
        "launch",
        "--type=os-window",
        "nvim",
        "-c",
        "setlocal filetype=diff",
        diff_path,
    ]
    try:
        subprocess.run(kitty_cmd, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        subprocess.run(["nvim", "-c", "setlocal filetype=diff", diff_path], check=False)


def should_process_file(file_path: str, watch_dir: Path) -> bool:
    try:
        resolved = Path(file_path).resolve()
    except FileNotFoundError:
        return False
    return str(resolved).startswith(str(watch_dir.resolve())) and resolved.is_file()


class BufferDaemon:
    def __init__(
        self, watch_dir: str, model_name: str, idle_seconds: float, debug: bool
    ) -> None:
        self.watch_dir = Path(watch_dir)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.model.eval()
        self.last_processed: dict[str, str] = {}
        self.last_mtime: dict[str, float] = {}
        self.idle_seconds = idle_seconds
        self.debug = debug

    def _handle_file(self, file_path: str) -> bool:
        if not should_process_file(file_path, self.watch_dir):
            return False

        text = Path(file_path).read_text(encoding="utf-8", errors="ignore")
        text = clean_buffer_text(text)
        sentence = extract_last_sentence(text)
        if not sentence:
            return False

        if self.last_processed.get(file_path) == sentence:
            return False

        corrected = correct_sentence(self.tokenizer, self.model, sentence)
        if self.debug:
            print(f"[debug] input: {sentence}")
            print(f"[debug] output: {corrected}")
        self.last_processed[file_path] = sentence
        open_diff_in_kitty(sentence, corrected)
        return True

    def scan_once(self, now: float | None = None) -> int:
        processed = 0
        now = time.time() if now is None else now
        for path in sorted(self.watch_dir.glob("doc-*")):
            if not path.is_file():
                continue
            mtime = path.stat().st_mtime
            known_mtime = self.last_mtime.get(str(path))
            if known_mtime is None or mtime > known_mtime:
                self.last_mtime[str(path)] = mtime
                continue
            if (now - mtime) < self.idle_seconds:
                continue
            if self._handle_file(str(path)):
                processed += 1
        return processed


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch-dir", default="/tmp/nvim-anywhere")
    parser.add_argument("--scan-interval", type=float, default=0.4)
    parser.add_argument("--idle-seconds", type=float, default=1.2)
    parser.add_argument(
        "--model",
        default="oliverguhr/spelling-correction-german-base",
    )
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def run_daemon(
    watch_dir: str,
    model_name: str,
    scan_interval: float,
    idle_seconds: float,
    debug: bool,
) -> None:
    daemon = BufferDaemon(
        watch_dir=watch_dir,
        model_name=model_name,
        idle_seconds=idle_seconds,
        debug=debug,
    )
    print(f"Daemon aktiv, überwacht: {watch_dir}")
    while True:
        daemon.scan_once()
        time.sleep(scan_interval)


def main() -> None:
    args = parse_args()
    run_daemon(
        watch_dir=args.watch_dir,
        model_name=args.model,
        scan_interval=args.scan_interval,
        idle_seconds=args.idle_seconds,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
