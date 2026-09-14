"""Multilingual layer (TDD 4.3, TECHNICAL_SETUP 8.9).

Reads: raw user text / audio
Writes: nothing (pure helpers used by the router and the voice endpoint)
Tech: Unicode-script language detection; AI4Bharat IndicTrans2 (translation) and Indic wav2vec (ASR)
through ``transformers``, loaded lazily and only when ``settings.indic_translation_enabled``.

When the models are disabled or fail to load, text passes through unchanged with status
``"unavailable"``; the router's Hindi/Hinglish cue parsing still works offline.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Literal

from config.settings import settings

logger = logging.getLogger(__name__)

TranslationStatus = Literal["not_needed", "translated", "unavailable"]

# (first code point, last code point) -> ISO 639-1 code
_SCRIPTS: list[tuple[int, int, str]] = [
    (0x0900, 0x097F, "hi"),  # Devanagari
    (0x0980, 0x09FF, "bn"),  # Bengali
    (0x0A00, 0x0A7F, "pa"),  # Gurmukhi
    (0x0A80, 0x0AFF, "gu"),  # Gujarati
    (0x0B00, 0x0B7F, "or"),  # Odia
    (0x0B80, 0x0BFF, "ta"),  # Tamil
    (0x0C00, 0x0C7F, "te"),  # Telugu
    (0x0C80, 0x0CFF, "kn"),  # Kannada
    (0x0D00, 0x0D7F, "ml"),  # Malayalam
]

# IndicTrans2 FLORES-style language tags
_FLORES = {
    "en": "eng_Latn", "hi": "hin_Deva", "bn": "ben_Beng", "pa": "pan_Guru", "gu": "guj_Gujr",
    "or": "ory_Orya", "ta": "tam_Taml", "te": "tel_Telu", "kn": "kan_Knda", "ml": "mal_Mlym",
}


class LanguageLayerUnavailable(RuntimeError):
    """Raised when a speech/translation model is disabled or cannot be loaded."""


def detect_language(text: str) -> str:
    """Language code from the dominant Indic script in ``text``; Latin/unknown -> ``"en"``."""
    counts: dict[str, int] = {}
    for ch in text or "":
        cp = ord(ch)
        for lo, hi, code in _SCRIPTS:
            if lo <= cp <= hi:
                counts[code] = counts.get(code, 0) + 1
                break
    return max(counts, key=counts.get) if counts else "en"


@lru_cache(maxsize=2)
def _load_translator(model_name: str) -> tuple[Any, Any]:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
    return tokenizer, model


def _translate(text: str, src: str, tgt: str) -> str:
    model_name = settings.indic_translation_model
    if src == "en":  # the configured model is indic->en; the en->indic checkpoint follows the AI4Bharat naming
        model_name = model_name.replace("indic-en", "en-indic")
    tokenizer, model = _load_translator(model_name)
    try:
        from IndicTransToolkit import IndicProcessor  # optional pre/post-processing helper

        proc = IndicProcessor(inference=True)
        batch = proc.preprocess_batch([text], src_lang=_FLORES[src], tgt_lang=_FLORES[tgt])
    except ImportError:
        proc, batch = None, [f"{_FLORES[src]} {_FLORES[tgt]} {text}"]
    inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True)
    output = model.generate(**inputs, max_length=256, num_beams=4)
    decoded = tokenizer.batch_decode(output, skip_special_tokens=True)
    if proc is not None:
        decoded = proc.postprocess_batch(decoded, lang=_FLORES[tgt])
    return decoded[0].strip()


def to_english(text: str, lang: str) -> tuple[str, TranslationStatus]:
    if lang == "en":
        return text, "not_needed"
    if not settings.indic_translation_enabled or lang not in _FLORES:
        return text, "unavailable"
    try:
        return _translate(text, lang, "en"), "translated"
    except Exception as exc:  # model missing, no torch, download blocked, ...
        logger.warning("IndicTrans2 %s->en unavailable: %s", lang, exc)
        return text, "unavailable"


def from_english(text: str, lang: str) -> str:
    if lang == "en" or not settings.indic_translation_enabled or lang not in _FLORES:
        return text
    try:
        return _translate(text, "en", lang)
    except Exception as exc:
        logger.warning("IndicTrans2 en->%s unavailable: %s", lang, exc)
        return text


@lru_cache(maxsize=1)
def _load_asr() -> Any:
    from transformers import pipeline

    return pipeline("automatic-speech-recognition", model=settings.indic_asr_model)


def transcribe(audio_bytes: bytes) -> str:
    """Speech to text with the configured Indic ASR model (requires ffmpeg for decoding)."""
    if not settings.indic_translation_enabled:
        raise LanguageLayerUnavailable("Voice input is disabled (set INDIC_TRANSLATION_ENABLED=true and install the Indic ASR model).")
    try:
        result = _load_asr()(audio_bytes)
    except Exception as exc:
        raise LanguageLayerUnavailable(f"Indic ASR model unavailable: {exc}") from exc
    text = (result or {}).get("text", "").strip()
    if not text:
        raise LanguageLayerUnavailable("ASR produced no transcript.")
    return text
