from __future__ import annotations

import logging
import os
import numpy as np
from typing import Any, Dict, Iterable, List, Optional, Tuple
import soundfile as sf
from faster_whisper import WhisperModel

from backend.stt_service.app.config import STTServiceSettings
from backend.stt_service.app.diarization import (
    analyze_audio,
    cleanup_temp_files,
    resolve_speaker_labels,
    split_stereo_to_mono,
)
from backend.stt_service.app.stt_engine.base import (
    BaseSTTEngine,
    TranscriptionResult,
    TranscriptionSegment,
    Word,
)
from backend.stt_service.app.alignment import (
    AlignmentConfig,
    CleanedSegment,
    DiarizationSegment,
    align_diarization_with_words,
    Word as AlignmentWord,
)

logger = logging.getLogger("stt.faster_whisper")


class FasterWhisperEngine(BaseSTTEngine):
    name = "faster_whisper"

    def __init__(self, settings: STTServiceSettings) -> None:
        self.settings = settings
        compute_type = settings.resolved_compute_type
        
        # Get Whisper model caching configuration
        whisper_model_dir = settings.whisper_model_dir
        whisper_local_only = settings.whisper_local_only
        
        # Log configuration for debugging
        logger.info(
            "Whisper model config: name='%s' device=%s compute_type=%s model_dir='%s' local_only=%s hf_hub_offline=%s",
            settings.stt_model_name,
            settings.resolved_device,
            compute_type,
            whisper_model_dir,
            whisper_local_only,
            os.getenv("HF_HUB_OFFLINE", "0"),
        )
        
        self.model = WhisperModel(
            settings.stt_model_name,
            device=settings.resolved_device,
            compute_type=compute_type,
            download_root=whisper_model_dir,
            local_files_only=whisper_local_only,
        )

    def transcribe(
        self,
        job_id: str,
        audio_path: str,
        diarization_mode: str = "none",
        extra_meta: dict | None = None,
        **kwargs: Any,
    ) -> TranscriptionResult:
        if diarization_mode == "stereo_channels":
            return self._transcribe_stereo(job_id, audio_path, extra_meta)
        return self._transcribe_standard(job_id, audio_path, extra_meta)

    def _transcribe_standard(self, job_id: str, audio_path: str, extra_meta: dict | None = None) -> TranscriptionResult:
        segments, info = self._run_transcription(audio_path)
        
        # Apply word-level alignment even in non-diarized mode
        # This still cleans up timestamps based on actual word recognition
        if segments and any(seg.words for seg in segments):
            segments = self._apply_word_alignment(segments, job_id)
        
        # Sort segments by start time
        segments.sort(key=lambda seg: seg.start)
        
        # Customize speaker labels if agent_id is provided
        agent_id = extra_meta.get("agent_id") if extra_meta else None
        if agent_id:
            for segment in segments:
                if segment.speaker == "manager":
                    segment.speaker = agent_id
        
        # Build the full text with interleaved speaker labels
        interleaved_texts = []
        for segment in segments:
            segment_text = f"[{segment.speaker}] {segment.text}"
            interleaved_texts.append(segment_text)
        
        text = "\n".join(interleaved_texts)
        metadata = self._build_metadata(info)
        metadata["diarization_mode"] = "none"
        return TranscriptionResult(
            job_id=job_id,
            text=text,
            segments=segments,
            language=info.get("language"),
            metadata=metadata,
        )

    def _detect_speech_start(self, audio_path: str, sample_rate: int = 16000, frame_duration_ms: int = 30) -> float:
        """Detect the start of speech in an audio file using WebRTC VAD.
        
        Note: This method is deprecated in favor of word-level alignment.
        Kept for backward compatibility but requires webrtcvad package.
        """
        try:
            import webrtcvad
            import resampy
        except ImportError:
            logger.warning("webrtcvad or resampy not available; speech detection disabled")
            return 0.0
            
        try:
            # Read audio file
            audio, sr = sf.read(audio_path)
            if len(audio) == 0:
                return 0.0
                
            # Convert to mono if needed
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
                
            if sr != sample_rate:
                # Resample if needed (WebRTC VAD requires 8kHz, 16kHz, 32kHz, or 48kHz)
                audio = resampy.resample(audio, sr, sample_rate)
                sr = sample_rate
                
            # Convert to 16-bit PCM
            if audio.dtype != np.int16:
                audio = (audio * 32767).astype(np.int16)
            
            # Initialize VAD with most aggressive filtering
            vad = webrtcvad.Vad(3)
            frame_size = int(sr * frame_duration_ms / 1000)
            
            # Look for the first frame with speech
            for i in range(0, len(audio) - frame_size + 1, frame_size):
                frame = audio[i:i + frame_size].tobytes()
                if vad.is_speech(frame, sr):
                    # Convert frame index to seconds, subtract 500ms to be safe
                    return max(0, (i / sr) - 0.5)
                    
            return 0.0
            
        except Exception as e:
            logger.warning(f"Error in speech detection: {e}")
            return 0.0

    def _apply_word_alignment(self, segments: List[TranscriptionSegment], job_id: str) -> List[TranscriptionSegment]:
        """Apply word-level alignment to clean up diarization timestamps.
        
        This method uses word timestamps from Whisper to adjust segment boundaries,
        eliminating false starts caused by background noise.
        
        Args:
            segments: Raw transcription segments with word timestamps
            job_id: Job ID for logging
            
        Returns:
            Cleaned segments with adjusted timestamps
        """
        # Extract all words from all segments WITH CHANNEL INFORMATION
        all_words: List[AlignmentWord] = []
        for seg in segments:
            for word in seg.words:
                all_words.append(AlignmentWord(
                    start=word.start,
                    end=word.end,
                    text=word.text,
                    probability=word.probability,
                    channel=word.channel,  # Preserve channel info
                ))
        
        # Create diarization segments from the original segments
        diar_segments: List[DiarizationSegment] = []
        for seg in segments:
            diar_segments.append(DiarizationSegment(
                start=seg.start,
                end=seg.end,
                speaker=seg.speaker or "speaker_unknown",
                channel=seg.channel,
            ))
        
        # Get alignment configuration from settings
        config = AlignmentConfig(
            overlap_eps=self.settings.alignment_overlap_eps,
            pad_left=self.settings.alignment_pad_left,
            pad_right=self.settings.alignment_pad_right,
            min_word_duration=self.settings.alignment_min_word_duration,
            min_segment_duration=self.settings.alignment_min_segment_duration,
            gap_threshold=self.settings.alignment_gap_threshold,
            merge_threshold=self.settings.alignment_merge_threshold,
        )
        
        # Apply alignment
        cleaned_segments = align_diarization_with_words(
            words=all_words,
            diar_segments=diar_segments,
            config=config,
        )
        
        logger.info(
            "Job %s: alignment cleaned %d segments → %d segments",
            job_id,
            len(segments),
            len(cleaned_segments),
        )
        
        # Convert cleaned segments back to TranscriptionSegment
        result_segments: List[TranscriptionSegment] = []
        for cleaned in cleaned_segments:
            # Convert words back to Word objects
            words = [Word(
                start=w.start,
                end=w.end,
                text=w.text,
                probability=w.probability,
                channel=w.channel,  # Preserve channel info
            ) for w in cleaned.words]
            
            result_segments.append(TranscriptionSegment(
                start=cleaned.start,
                end=cleaned.end,
                text=cleaned.text,
                speaker=cleaned.speaker,
                channel=cleaned.channel,
                confidence=cleaned.confidence,
                words=words,
            ))
        
        return result_segments

    def _transcribe_stereo(self, job_id: str, audio_path: str, extra_meta: dict | None = None) -> TranscriptionResult:
        audio_info = analyze_audio(audio_path)
        if audio_info.channels < 2:
            logger.warning(
                "Job %s audio %s has %s channel(s); falling back to non-diarized mode",
                job_id,
                audio_path,
                audio_info.channels,
            )
            return self._transcribe_standard(job_id, audio_path, extra_meta)

        # Split stereo audio into mono channels
        channel_files, temp_files = split_stereo_to_mono(audio_path)
        
        all_segments: List[TranscriptionSegment] = []
        metadata = {
            "diarization_mode": "stereo_channels",
            "channels": {},
            "audio": {
                "channels": audio_info.channels,
                "sample_rate": audio_info.sample_rate,
                "duration": audio_info.duration,
            },
        }
        
        detected_languages = []  # Move this outside the try block
        mapping = resolve_speaker_labels(self.settings.speaker_mapping, channel_files.keys())

        try:
            for channel, mono_path in channel_files.items():
                speaker_label = mapping.get(channel, f"speaker_{channel}")
                logger.info(
                    "Job %s: transcribing channel %s (%s) from %s",
                    job_id,
                    channel,
                    speaker_label,
                    mono_path,
                )
                
                # Transcribe this channel with word timestamps
                channel_segments, info = self._run_transcription(mono_path, speaker=speaker_label, channel=channel)
                
                # Extract language directly from info object (this is the reliable way)
                channel_language = getattr(info, 'language', None)
                if channel_language:
                    detected_languages.append(channel_language)
                    logger.debug("Job %s: Channel %s detected language: %s", job_id, channel, channel_language)
                
                # Build channel metadata and ensure language is included
                channel_metadata = self._build_metadata(info)
                logger.debug("Job %s: Built channel %s metadata: %s", job_id, channel, channel_metadata)
                
                # Explicitly ensure language is in the metadata
                if channel_language and "language" not in channel_metadata:
                    channel_metadata["language"] = channel_language
                    logger.debug("Job %s: Added language to channel %s metadata", job_id, channel)
                
                # Store the complete channel metadata
                metadata["channels"][channel] = channel_metadata
                logger.debug("Job %s: Assigned channel %s metadata: %s", job_id, channel, metadata["channels"][channel])
                
                # Add speaker to the existing metadata (don't overwrite it)
                metadata["channels"][channel]["speaker"] = speaker_label
                logger.debug("Job %s: Final channel %s metadata: %s", job_id, channel, metadata["channels"][channel])
                
                all_segments.extend(channel_segments)

            # Apply alignment to clean up timestamps based on word-level data
            all_segments = self._apply_word_alignment(all_segments, job_id)
            
            # Sort all segments by their start time
            all_segments.sort(key=lambda seg: seg.start)
            
            # Customize speaker labels if agent_id is provided
            agent_id = extra_meta.get("agent_id") if extra_meta else None
            if agent_id:
                for segment in all_segments:
                    if segment.speaker == "manager":
                        segment.speaker = agent_id
            
            # Build the full text with interleaved speaker labels
            # Instead of grouping by speaker, we interleave segments chronologically
            interleaved_texts = []
            for segment in all_segments:
                segment_text = f"[{segment.speaker}] {segment.text}"
                interleaved_texts.append(segment_text)
            
            full_text = "\n".join(interleaved_texts)

            # Get primary language from the first channel with content
            primary_language = None
            logger.debug("Job %s: Checking channel metadata for language", job_id)
            for channel, channel_meta in metadata["channels"].items():
                logger.debug("Job %s: Channel %s metadata: %s", job_id, channel, channel_meta)
                if "language" in channel_meta and channel_meta["language"] is not None:
                    primary_language = channel_meta["language"]
                    logger.debug("Job %s: Found language '%s' in channel %s", job_id, primary_language, channel)
                    break
            
            # Fallback: if no language found in metadata, use detected languages
            if primary_language is None and detected_languages:
                primary_language = detected_languages[0]  # Use the first detected language
                logger.debug("Job %s: Using fallback language from detected languages: %s", job_id, primary_language)
            
            logger.info("Job %s: Primary language detected as: %s", job_id, primary_language)
            return TranscriptionResult(
                job_id=job_id,
                text=full_text,
                segments=all_segments,
                language=primary_language,
                metadata=metadata,
            )

        finally:
            cleanup_temp_files(temp_files)

    def _run_transcription(
        self,
        audio_path: str,
        speaker: str | None = None,
        channel: int | None = None,
    ) -> Tuple[List[TranscriptionSegment], Dict[str, Any]]:
        generator, info = self.model.transcribe(
            audio_path,
            beam_size=self.settings.beam_size,
            temperature=self.settings.temperature,
            vad_filter=self.settings.vad_filter,
            vad_parameters={"min_silence_duration_ms": self.settings.vad_min_silence_ms},
            language=self.settings.language,
            task=self.settings.task,
            initial_prompt=self.settings.initial_prompt,
            word_timestamps=True,  # Enable word-level timestamps
        )
        
        # Log language detection info
        if hasattr(info, 'language'):
            logger.debug("_run_transcription: Detected language: %s (probability: %s)", 
                        info.language, getattr(info, 'language_probability', 'unknown'))
        
        segments: List[TranscriptionSegment] = []
        for seg in generator:
            text = seg.text.strip()
            if not text:
                continue
            
            # Extract word-level timestamps
            words = []
            if hasattr(seg, 'words') and seg.words:
                for w in seg.words:
                    words.append(Word(
                        start=float(w.start),
                        end=float(w.end),
                        text=w.word.strip(),
                        probability=getattr(w, 'probability', None),
                        channel=channel,  # Pass channel info to words
                    ))
            
            segment = TranscriptionSegment(
                start=float(seg.start),
                end=float(seg.end),
                text=text,
                speaker=speaker,
                channel=channel,
                confidence=self._confidence(seg),
                words=words,
            )
            segments.append(segment)
        
        return segments, info

    @staticmethod
    def _confidence(segment: Any) -> float | None:
        no_speech = getattr(segment, "no_speech_prob", None)
        if no_speech is None:
            return None
        return max(0.0, min(1.0, 1.0 - no_speech))

    @staticmethod
    def _build_metadata(info: Any | None) -> Dict[str, Any]:
        if not info:
            return {}
        metadata: Dict[str, Any] = {}
        logger.debug("Building metadata from info object: %s", info)
        logger.debug("Info object attributes: %s", dir(info) if hasattr(info, '__dict__') else 'No __dict__')
        logger.debug("Info object type: %s", type(info))
        
        # Extract language information more robustly
        for attr in ("language", "language_probability", "duration", "duration_after_vad"):
            value = getattr(info, attr, None)
            logger.debug("Attribute %s: %s (type: %s)", attr, value, type(value))
            if value is not None:
                metadata[attr] = value
        
        # Additional check for language in case it's stored differently
        if "language" not in metadata and hasattr(info, 'language'):
            metadata["language"] = info.language
            
        logger.debug("Built metadata: %s", metadata)
        return metadata
