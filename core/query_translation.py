"""Optional offline Persian sentence translation, never a movie-title lookup."""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "models/translation/nllb-200-distilled-600M-ct2-int8"


def translation_python():
    root = Path(os.getenv("CINESCENE_STORAGE_ROOT", ROOT / "models")) / "translation-runtime"
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def translate_local(model_path, text, truncate=False):
    import ctranslate2
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(str(Path(model_path) / "tokenizer.json"))
    # NLLB's language prefix is explicit; do not reuse the tokenizer's default English template.
    tokens = tokenizer.encode(text, add_special_tokens=False).tokens
    if len(tokens) > 480:
        if not truncate:
            raise ValueError("Translation input exceeds the supported sentence length.")
        tokens = tokens[:480]
    source = ["pes_Arab", *tokens, "</s>"]
    model = ctranslate2.Translator(str(model_path), device="cpu", compute_type="int8",
                                 inter_threads=1, intra_threads=2)
    result = model.translate_batch([source], target_prefix=[["eng_Latn"]], beam_size=2,
                                   max_decoding_length=320, max_input_length=512)[0]
    output = result.hypotheses[0]
    if output and output[0] == "eng_Latn":
        output = output[1:]
    ids = [tokenizer.token_to_id(token) for token in output]
    translated = tokenizer.decode([value for value in ids if value is not None], skip_special_tokens=True).strip()
    if not translated or not re.search(r"[A-Za-z]", translated):
        raise ValueError("Translation did not produce an English sentence.")
    return translated


class OfflineQueryTranslator:
    def __init__(self):
        self.model_path = Path(os.getenv("CINESCENE_TRANSLATION_MODEL", MODEL))
        self.executable = translation_python()
        self.enabled = os.getenv("CINESCENE_QUERY_TRANSLATION", "1") == "1"
        self.timeout = max(30, min(300, float(os.getenv("CINESCENE_TRANSLATION_TIMEOUT_SEC", "150"))))

    @property
    def available(self):
        return self.enabled and self.executable.is_file() and all((self.model_path / name).is_file() for name in
                                                                ("model.bin", "config.json", "tokenizer.json"))

    @lru_cache(maxsize=32)
    def translate(self, text):
        if not self.available:
            return None
        from core.model_worker import run_worker
        return run_worker({"kind": "translate", "model": str(self.model_path), "text": text},
                          executable=self.executable, timeout=self.timeout, required_mb=850)

    @lru_cache(maxsize=128)
    def translate_evidence(self, text):
        if not self.available:
            return None
        from core.model_worker import run_worker
        # This is only a bounded verification window. Original scene dialogue
        # remains complete and unchanged in storage and in the search response.
        return run_worker({"kind": "translate", "model": str(self.model_path), "text": text, "truncate": True},
                          executable=self.executable, timeout=self.timeout, required_mb=850)

    def status(self):
        return {"available": self.available, "provider": "offline-nllb-600m-int8",
                "license": "CC-BY-NC-4.0", "external_query_requests": False,
                "scene_verification_translation": self.available, "timeout_seconds": self.timeout}
