from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional


@dataclass
class Word:
    """A single recognized word with timestamps."""
    start: float
    end: float
    text: str
    probability: Optional[float] = None
    channel: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str
    speaker: Optional[str] = None
    channel: Optional[int] = None
    confidence: Optional[float] = None
    words: List[Word] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Convert words to dicts for serialization
        result['words'] = [w.to_dict() if hasattr(w, 'to_dict') else w for w in self.words]
        return result


@dataclass
class TranscriptionResult:
    job_id: str
    text: str
    segments: List[TranscriptionSegment] = field(default_factory=list)
    language: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def segments_as_dicts(self) -> List[Dict[str, Any]]:
        return [segment.to_dict() for segment in self.segments]


class BaseSTTEngine(ABC):
    name: str = "base"

    @abstractmethod
    def transcribe(
        self,
        job_id: str,
        audio_path: str,
        diarization_mode: Literal["none", "stereo_channels"] = "none",
        extra_meta: dict | None = None,
        **kwargs: Any,
    ) -> TranscriptionResult:
        """Transcribe the supplied audio file."""
        raise NotImplementedError
