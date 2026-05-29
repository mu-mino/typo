import tempfile
import difflib
from pathlib import Path

import main


def test_extract_last_sentence_with_punctuation():
    text = "Das ist ein Test. Noch ein Satz! Letzter Satz?"
    assert main.extract_last_sentence(text) == "Letzter Satz?"


def test_extract_last_sentence_without_punctuation():
    text = "erste zeile\nzweite zeile"
    assert main.extract_last_sentence(text) == "zweite zeile"


def test_extract_last_sentence_empty_text():
    assert main.extract_last_sentence("   \n") == ""


def test_clean_buffer_text_strips_outer_whitespace():
    assert main.clean_buffer_text("  abc  \n") == "abc"


def test_is_usable_correction_rejects_noise():
    assert (
        main.is_usable_correction("das ist noch ein fehler", ".. ..........") is False
    )


def test_is_usable_correction_accepts_real_text():
    assert (
        main.is_usable_correction("ich habe einn fehler", "ich habe einen fehler.")
        is True
    )


def test_normalize_model_output_uses_first_sentence():
    raw = "Das ist eine fehlerhafte Ausgabe. Das ist eine zweite Ausgabe."
    assert main.normalize_model_output(raw) == "Das ist eine fehlerhafte Ausgabe."


def test_build_clean_diff_strips_noisy_headers():
    diff_text = main.build_clean_diff("eins\nzwei", "eins\ndrei")
    assert "index " not in diff_text
    assert "/tmp/" not in diff_text
    assert "+drei" in diff_text
    assert "-zwei" in diff_text
    assert "@@" in diff_text


def test_correct_sentence_handles_real_problem_case_1():
    class DummyTokenizer:
        def __call__(self, text, return_tensors="pt", truncation=True):
            return {"input_text": text}

        def decode(self, output, skip_special_tokens=True):
            return output

    class DummyModel:
        def generate(self, **kwargs):
            assert kwargs["input_text"].startswith("Rechtschreibung: ")
            return ["Ich bin da anderer Meinungs, als du es bist. Extra Satz."]

    out = main.correct_sentence(
        DummyTokenizer(), DummyModel(), "ich bin da anderer Meinungs als du es bst"
    )
    assert out == "Ich bin da anderer Meinungs, als du es bist."


def test_correct_sentence_handles_real_problem_case_2():
    class DummyTokenizer:
        def __call__(self, text, return_tensors="pt", truncation=True):
            return {"input_text": text}

        def decode(self, output, skip_special_tokens=True):
            return output

    class DummyModel:
        def generate(self, **kwargs):
            return ["Das ist eine fehlerhafte Ausgabe. Das ist eine zweite Ausgabe."]

    out = main.correct_sentence(
        DummyTokenizer(), DummyModel(), "das ist einer fehölerheafgte ausgabe"
    )
    assert out == "Das ist eine fehlerhafte Ausgabe."


def test_correct_sentence_uses_large_enough_generation_budget():
    captured = {}

    class DummyTokenizer:
        def __call__(self, text, return_tensors="pt", truncation=True):
            return {"input_text": text}

        def decode(self, output, skip_special_tokens=True):
            return output

    class DummyModel:
        def generate(self, **kwargs):
            captured.update(kwargs)
            return [
                "Ein fehlerhafter Text zur Uberprufung, ob es richtig funktioniert."
            ]

    main.correct_sentence(
        DummyTokenizer(),
        DummyModel(),
        "ein fehlerhftr tex zur uberprfung ob es ruchtig funktionerrt",
    )
    assert captured["max_new_tokens"] >= 32


def test_scan_once_processes_new_file(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "doc-1"
        file_path.write_text("Das ist ein Satz ohnee Fehler.", encoding="utf-8")

        class DummyTokenizer:
            def __call__(self, text, return_tensors="pt", truncation=True):
                return {"input_text": text}

            def decode(self, output, skip_special_tokens=True):
                return output

        class DummyModel:
            def eval(self):
                return None

            def generate(self, **kwargs):
                text = kwargs["input_text"].replace("Rechtschreibung: ", "")
                return [text.replace("ohnee", "ohne")]

        monkeypatch.setattr(
            main,
            "AutoTokenizer",
            type(
                "T", (), {"from_pretrained": staticmethod(lambda _m: DummyTokenizer())}
            ),
        )
        monkeypatch.setattr(
            main,
            "AutoModelForSeq2SeqLM",
            type("M", (), {"from_pretrained": staticmethod(lambda _m: DummyModel())}),
        )
        captured = []
        monkeypatch.setattr(
            main,
            "open_diff_in_kitty",
            lambda original, corrected: captured.append((original, corrected)),
        )

        daemon = main.BufferDaemon(
            watch_dir=tmp_dir, model_name="ignored-model", idle_seconds=1.2, debug=False
        )
        processed_first = daemon.scan_once(now=file_path.stat().st_mtime)
        processed_second = daemon.scan_once(now=file_path.stat().st_mtime + 2.0)

        assert processed_first == 0
        assert processed_second == 1
        assert captured == [
            ("Das ist ein Satz ohnee Fehler.", "Das ist ein Satz ohne Fehler.")
        ]


def test_debug_prints_input_output(monkeypatch, capsys):
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "doc-1"
        file_path.write_text("ich habe einn fehler", encoding="utf-8")

        class DummyTokenizer:
            def __call__(self, text, return_tensors="pt", truncation=True):
                return {"input_text": text}

            def decode(self, output, skip_special_tokens=True):
                return output

        class DummyModel:
            def eval(self):
                return None

            def generate(self, **kwargs):
                return ["ich habe einen fehler"]

        monkeypatch.setattr(
            main,
            "AutoTokenizer",
            type(
                "T", (), {"from_pretrained": staticmethod(lambda _m: DummyTokenizer())}
            ),
        )
        monkeypatch.setattr(
            main,
            "AutoModelForSeq2SeqLM",
            type("M", (), {"from_pretrained": staticmethod(lambda _m: DummyModel())}),
        )
        monkeypatch.setattr(
            main, "open_diff_in_kitty", lambda _original, _corrected: None
        )

        daemon = main.BufferDaemon(
            watch_dir=tmp_dir, model_name="ignored-model", idle_seconds=1.2, debug=True
        )
        daemon.scan_once(now=file_path.stat().st_mtime)
        daemon.scan_once(now=file_path.stat().st_mtime + 2.0)

        out = capsys.readouterr().out
        assert "[debug] input: ich habe einn fehler" in out
        assert "[debug] output: ich habe einen fehler" in out
