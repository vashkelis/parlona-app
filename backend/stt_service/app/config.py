from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Dict, List, Tuple

from pydantic import Field
from pydantic_settings import BaseSettings


def _cuda_available() -> bool:
    visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES")
    if visible_devices and visible_devices != "-1":
        return True
    try:
        import torch  # type: ignore

        return bool(torch.cuda.is_available())
    except Exception:  # pragma: no cover - torch optional
        return False


class STTServiceSettings(BaseSettings):
    """Configuration for the STT service and engines."""

    stt_engine: str = Field(default="faster_whisper", validation_alias="STT_ENGINE")
    stt_model_name: str = Field(default="small", validation_alias="STT_MODEL_NAME")
    device: str = Field(default="auto", validation_alias="STT_DEVICE")
    compute_type: str = Field(default="float16", validation_alias="STT_COMPUTE_TYPE")
    diarization_mode: str = Field(default="none", validation_alias="STT_DIARIZATION_MODE")
    stereo_speaker_mapping: str = Field(
        default="0:speaker_1,1:speaker_2", 
        validation_alias="STT_STEREO_SPEAKER_MAPPING"
    )
    language: str | None = Field(default=None, validation_alias="STT_LANGUAGE")
    task: str = Field(default="transcribe", validation_alias="STT_TASK")
    beam_size: int = Field(default=5, validation_alias="STT_BEAM_SIZE")
    temperature: float = Field(default=0.0, validation_alias="STT_TEMPERATURE")
    vad_filter: bool = Field(default=True, validation_alias="STT_VAD_FILTER")
    vad_min_silence_ms: int = Field(default=500, validation_alias="STT_VAD_MIN_SILENCE_MS")
    initial_prompt: str | None = Field(default=None, validation_alias="STT_INITIAL_PROMPT")
    audio_path_mappings: str = Field(default="", validation_alias="STT_AUDIO_PATH_MAPPINGS")
    whisper_model_dir: str = Field(default="/models/whisper", validation_alias="WHISPER_MODEL_DIR")
    whisper_local_only: bool = Field(default=False, validation_alias="WHISPER_LOCAL_ONLY")
    
    # Word-level alignment configuration
    alignment_overlap_eps: float = Field(default=0.2, validation_alias="STT_ALIGNMENT_OVERLAP_EPS")
    alignment_pad_left: float = Field(default=0.2, validation_alias="STT_ALIGNMENT_PAD_LEFT")
    alignment_pad_right: float = Field(default=0.2, validation_alias="STT_ALIGNMENT_PAD_RIGHT")
    alignment_min_word_duration: float = Field(default=0.2, validation_alias="STT_ALIGNMENT_MIN_WORD_DURATION")
    alignment_min_segment_duration: float = Field(default=0.1, validation_alias="STT_ALIGNMENT_MIN_SEGMENT_DURATION")
    alignment_gap_threshold: float = Field(default=1.0, validation_alias="STT_ALIGNMENT_GAP_THRESHOLD")
    alignment_merge_threshold: float = Field(default=2.5, validation_alias="STT_ALIGNMENT_MERGE_THRESHOLD")

    class Config:
        env_prefix = ""
        env_file = ".env"
        case_sensitive = False
        protected_namespaces = ("settings_",)
        env_file_encoding = 'utf-8'
        extra = 'ignore'

    @property
    def resolved_device(self) -> str:
        if self.device.lower() in {"auto", ""}:
            return "cuda" if _cuda_available() else "cpu"
        return self.device

    @property
    def resolved_compute_type(self) -> str:
        compute = self.compute_type.lower()
        device = self.resolved_device
        if device == "cpu":
            if compute in {"int8", "int8_float32"}:
                return compute
            # CPUs generally cannot accelerate float16/bfloat16; fall back to int8.
            return "int8"
        return compute

    @property
    def speaker_mapping(self) -> Dict[int, str]:
        mapping = {}
        raw = self.stereo_speaker_mapping.strip()
        if not raw:
            return {0: "speaker_1", 1: "speaker_2"}
        if raw.startswith("{"):
            try:
                parsed = json.loads(raw)
                return {int(k): str(v) for k, v in parsed.items()}
            except json.JSONDecodeError:
                pass
        for pair in raw.split(","):
            if ":" not in pair:
                continue
            idx, label = pair.split(":", 1)
            idx = idx.strip()
            label = label.strip() or "speaker"
            if idx.isdigit():
                mapping[int(idx)] = label
        if not mapping:
            mapping = {0: "speaker_1", 1: "speaker_2"}
        return mapping

    @property
    def path_mappings(self) -> List[Tuple[str, str]]:
        raw = self.audio_path_mappings.strip()
        if not raw:
            return []
        # Allow JSON specification
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                return [(
                    str(item[0]).rstrip("/"),
                    str(item[1]).rstrip("/") or "/",
                ) for item in parsed if len(item) >= 2]
            except json.JSONDecodeError:
                pass
        mappings: List[Tuple[str, str]] = []
        for pair in raw.split(";"):
            if "=" not in pair:
                continue
            host, container = pair.split("=", 1)
            host = host.strip().rstrip("/")
            container = container.strip() or "/"
            if host and container:
                mappings.append((host, container.rstrip("/")))
        return mappings


def get_stt_settings() -> STTServiceSettings:
    return STTServiceSettings()
