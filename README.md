# Typo Daemon

An asynchronous, local background daemon that monitors `nvim-anywhere` buffers, detects typos, corrects them using Hugging Face language models, and automatically appends the corrected typos to your **espanso** configuration for future real-time text expansion.

Whenever you leave insert-mode, the daemon isolates your last changes, computes the diff, and spins up a dedicated `kitty` window running `nvim -d` (or a granular split buffer) to visualize the changes.

---

## Features

* **Real-time File Watching:** Actively tracks active `doc-*` files inside `/tmp/nvim-anywhere`.
* **Smart Idle Detection:** Waits for a configurable idle timeout before analyzing text, preventing interruptions while typing.
* **Language Agnostic Architecture:** Currently ships with a German spelling correction model, but can easily be configured to load models for English, French, Spanish, or any other language available on Hugging Face.
* **Automated Espanso Sync:** Once a typo is fixed and accepted, the daemon automatically appends the `trigger -> replace` pair to your `espanso` config file so the mistake is corrected in real-time across your entire OS next time.

---

## Requirements

### 1. System Dependencies

* **Linux** environment
* **`kitty`** (Terminal emulator used to spawn the diff window)
* **`nvim`** (Neovim)

### 2. Python Packages

```bash
pip install torch transformers pytest

```

### 3. Neovim Configuration (Required)

To make full use of the live diffing and block-highlighting inside Neovim, make sure your lazyvim/neovim environment is configured with the following plugins:

* **`granular-diff-buffer`**
* **`folke/todo-comments.nvim`**
-> config in nvim/lua/plugins/*

---

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt 

```

1. Start the Daemon:

```bash
python3 main.py 

```

To see options:

```bash
python3 main.py -h

```

---

## CLI Options & Model Customization

By default, the script runs the German model `oliverguhr/spelling-correction-german-base`. However, you can swap it out for **any language model** via the `--model` flag.

### Key Flags

* `--model`: The Hugging Face repo ID. Swap out the German base for English, Dutch, etc.
* `--espanso-path`: Target YAML configuration file where automated text triggers are appended.

---

## Automated Espanso Integration

The daemon seamlessly closes the loop between manual writing corrections and global automation. When a typo is registered:

1. It compares your input against the model output.
2. It extracts the raw typo and its exact fix.
3. It appends a clean match block directly into your espanso package config:

```yaml
  - trigger: "jetze"
    replace: "jetzt"

```

*Note: Make sure your `--espanso-path` points to a valid file inside your active espanso setup directory.*

---

## Testing

The test suite ensures the text extraction logic, sentence delimiters, and diffing algorithms work perfectly without regression.

Run tests quietly via `pytest`:

```bash
python3 -m pytest -q test_main.py

```
