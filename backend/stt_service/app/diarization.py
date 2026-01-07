from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple

import soundfile as sf

logger = logging.getLogger("stt.diarization")


@dataclass
class AudioInfo:
    path: str
    channels: int
    sample_rate: int
    duration: float
    subtype: str | None = None


def analyze_audio(path: str) -> AudioInfo:
    with sf.SoundFile(path) as audio:
        frames = len(audio)
        sample_rate = audio.samplerate
        duration = frames / sample_rate if sample_rate else 0.0
        return AudioInfo(
            path=path,
            channels=audio.channels,
            sample_rate=sample_rate,
            duration=duration,
            subtype=audio.subtype,
        )


def split_stereo_to_mono(path: str) -> Tuple[Dict[int, str], Iterable[str]]:
    data, sample_rate = sf.read(path)
    if data.ndim == 1 or data.shape[1] < 2:
        logger.warning("Input audio %s is not stereo; skipping channel split", path)
        return {}, []

    channel_files: Dict[int, str] = {}
    temp_files: list[str] = []

    for channel in range(data.shape[1]):
        mono_data = data[:, channel]
        temp_file = tempfile.NamedTemporaryFile(suffix=f"_ch{channel}.wav", delete=False)
        sf.write(temp_file.name, mono_data, sample_rate)
        temp_file.close()
        channel_files[channel] = temp_file.name
        temp_files.append(temp_file.name)
        logger.debug("Wrote mono channel %s to %s", channel, temp_file.name)

    return channel_files, temp_files


def resolve_speaker_labels(mapping: Dict[int, str], channels: Iterable[int]) -> Dict[int, str]:
    resolved = {}
    for channel in channels:
        resolved[channel] = mapping.get(channel, f"speaker_{channel}")
    return resolved


def cleanup_temp_files(paths: Iterable[str]) -> None:
    for path in paths:
        try:
            Path(path).unlink(missing_ok=True)
        except OSError as exc:  # pragma: no cover - best effort cleanup
            logger.debug("Failed to remove temp file %s: %s", path, exc)
