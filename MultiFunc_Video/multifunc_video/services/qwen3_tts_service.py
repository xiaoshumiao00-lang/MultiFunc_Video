# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Qwen3-TTS service wrapper.

Provides a thin async wrapper around the ``qwen_tts`` package so that it can be
used uniformly by TTSService. The model is kept loaded as a singleton so that
batch generation (e.g. per-segment teaching video synthesis) does not pay the
model loading cost for every segment.
"""

import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import soundfile as sf
import torch
from loguru import logger


class Qwen3TTSService:
    """Async-friendly wrapper for local Qwen3-TTS inference."""

    _model_instance: Optional[object] = None
    _model_path: Optional[str] = None
    _model_type: Optional[str] = None
    _speakers: Optional[List[str]] = None

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        ref_audio_path: Optional[str] = None,
        prompt_text: Optional[str] = None,
        speaker: Optional[str] = None,
        language: str = "Auto",
        speed: float = 1.0,
    ):
        self.model_path = model_path
        self.device = device
        self.ref_audio_path = ref_audio_path
        self.prompt_text = prompt_text or ""
        self.speaker = speaker
        self.language = language
        self.speed = speed

    # ------------------------------------------------------------------
    # Model lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load the Qwen3-TTS model into memory (singleton)."""
        if (
            Qwen3TTSService._model_instance is not None
            and Qwen3TTSService._model_path == self.model_path
        ):
            logger.info("Qwen3-TTS model already loaded, reusing singleton")
            return

        logger.info(f"Loading Qwen3-TTS model from {self.model_path}")

        try:
            from qwen_tts import Qwen3TTSModel
        except ImportError as e:
            raise ImportError(
                "qwen_tts package is not installed. "
                "Please install it first, e.g. 'pip install qwen-tts'."
            ) from e

        if not os.path.isdir(self.model_path):
            raise FileNotFoundError(f"Qwen3-TTS model path does not exist: {self.model_path}")

        dtype = torch.bfloat16 if self.device == "cuda" and torch.cuda.is_available() else torch.float32
        Qwen3TTSService._model_instance = Qwen3TTSModel.from_pretrained(
            self.model_path,
            device_map=self.device,
            dtype=dtype,
        )
        Qwen3TTSService._model_path = self.model_path
        Qwen3TTSService._model_type = getattr(
            Qwen3TTSService._model_instance.model, "tts_model_type", "unknown"
        )
        try:
            Qwen3TTSService._speakers = Qwen3TTSService._model_instance.get_supported_speakers()
        except Exception:
            Qwen3TTSService._speakers = []

        logger.info(
            f"Qwen3-TTS model loaded (type={Qwen3TTSService._model_type}, "
            f"speakers={len(Qwen3TTSService._speakers or [])})"
        )

    @classmethod
    def unload(cls) -> None:
        """Unload the model and release GPU memory."""
        if cls._model_instance is not None:
            logger.info("Unloading Qwen3-TTS model to release memory")
            del cls._model_instance
            cls._model_instance = None
            cls._model_path = None
            cls._model_type = None
            cls._speakers = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def is_loaded(self) -> bool:
        return Qwen3TTSService._model_instance is not None

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def synthesize(
        self,
        text: str,
        output_path: str,
        ref_audio_path: Optional[str] = None,
        prompt_text: Optional[str] = None,
        speaker: Optional[str] = None,
        language: Optional[str] = None,
        speed: Optional[float] = None,
        **kwargs,
    ) -> str:
        """
        Synthesize text to speech and save to ``output_path``.

        Returns the path to the generated audio file.
        """
        if Qwen3TTSService._model_instance is None:
            self.load()

        model = Qwen3TTSService._model_instance
        model_type = Qwen3TTSService._model_type

        # Resolve parameters
        effective_ref_audio = ref_audio_path or self.ref_audio_path
        effective_prompt_text = prompt_text if prompt_text is not None else self.prompt_text
        effective_speaker = speaker or self.speaker
        effective_language = language or self.language
        effective_speed = speed if speed is not None else self.speed

        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)

        # Route to the correct generation method based on model type
        if model_type == "custom_voice":
            effective_speaker = effective_speaker or (self._speakers[0] if self._speakers else "Auto")
            logger.info(f"Qwen3-TTS CustomVoice using speaker: {effective_speaker}, speed={effective_speed}")
            wavs, sr = model.generate_custom_voice(
                text=text,
                speaker=effective_speaker,
                language=effective_language,
                speed=effective_speed,
                **kwargs,
            )

        elif model_type == "base":
            if not effective_ref_audio or not os.path.isfile(effective_ref_audio):
                raise ValueError(
                    "Qwen3-TTS Base model requires a reference audio for voice cloning. "
                    "Please provide ref_audio_path."
                )
            logger.info(
                f"Qwen3-TTS Base voice clone: ref={effective_ref_audio}, "
                f"speed={effective_speed}, language={effective_language}"
            )
            wavs, sr = model.generate_voice_clone(
                text=text,
                ref_audio=effective_ref_audio,
                ref_text=effective_prompt_text or None,
                language=effective_language,
                speed=effective_speed,
                **kwargs,
            )

        elif model_type == "voice_design":
            instruct = kwargs.get("instruct", "")
            logger.info(f"Qwen3-TTS VoiceDesign: speed={effective_speed}")
            wavs, sr = model.generate_voice_design(
                text=text,
                instruct=instruct,
                language=effective_language,
                speed=effective_speed,
                **kwargs,
            )

        else:
            raise ValueError(f"Unsupported Qwen3-TTS model type: {model_type}")

        # Save audio
        audio_data = wavs[0].astype(np.float32)
        sf.write(output_path, audio_data, sr)

        duration = len(audio_data) / sr
        logger.info(f"Qwen3-TTS generated audio: {output_path}, duration={duration:.2f}s")
        return output_path

    def synthesize_with_timestamps(
        self,
        text: str,
        output_path: str,
        **kwargs,
    ) -> Dict:
        """Synthesize and return path, duration, and rough word timestamps."""
        audio_path = self.synthesize(text=text, output_path=output_path, **kwargs)
        info = sf.info(audio_path)
        duration = info.duration
        words = self._estimate_word_timestamps(text, duration)
        return {
            "audio_path": audio_path,
            "duration": duration,
            "sample_rate": info.samplerate,
            "words": words,
            "text": text,
        }

    @classmethod
    def _estimate_word_timestamps(cls, text: str, duration: float) -> List[Dict]:
        """Generate coarse word-level timestamps for subtitle alignment."""
        sentences = [s.strip() for s in re.split(r"[。！？，、；：\"\"''（）]", text) if s.strip()]
        if not sentences:
            sentences = [text]
        total_chars = sum(len(s) for s in sentences)
        if total_chars == 0:
            return []

        words = []
        current_time = 0.0
        for sentence in sentences:
            char_duration = duration / total_chars
            start = current_time
            end = start + len(sentence) * char_duration
            words.append({
                "word": sentence,
                "start": round(start, 2),
                "end": round(end, 2),
                "start_time": start,
                "end_time": end,
            })
            current_time = end
        return words

    @classmethod
    def list_speakers(cls) -> List[str]:
        return cls._speakers or []


# ----------------------------------------------------------------------
# Convenience helpers for TTSService
# ----------------------------------------------------------------------

def get_qwen3_tts_service(config: Dict) -> Qwen3TTSService:
    """Build a Qwen3TTSService from a config dict."""
    return Qwen3TTSService(
        model_path=config.get("model_path", ""),
        device=config.get("device", "cuda"),
        ref_audio_path=config.get("default_ref_audio") or None,
        prompt_text=config.get("default_prompt_text", ""),
        speaker=config.get("speaker") or None,
        language=config.get("language", "Auto"),
        speed=config.get("speed", 1.0),
    )
