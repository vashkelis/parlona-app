"""Word-level alignment for diarization segments.

This module provides post-processing to align diarization segments with
actual Whisper word timestamps, eliminating false starts caused by
background noise, breaths, or other non-speech audio.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger("stt.alignment")


class Word(BaseModel):
    """A single recognized word with timestamps."""
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    text: str = Field(description="Recognized word text")
    probability: Optional[float] = Field(default=None, description="Word probability/confidence")
    channel: Optional[int] = Field(default=None, description="Audio channel (for stereo mode)")


class DiarizationSegment(BaseModel):
    """A speaker segment from diarization (before alignment)."""
    start: float = Field(description="Start time in seconds")
    end: float = Field(description="End time in seconds")
    speaker: str = Field(description="Speaker label")
    channel: Optional[int] = Field(default=None, description="Audio channel (for stereo mode)")


class CleanedSegment(BaseModel):
    """A speaker segment aligned with actual word timestamps."""
    speaker: str = Field(description="Speaker label")
    start: float = Field(description="Aligned start time in seconds")
    end: float = Field(description="Aligned end time in seconds")
    text: str = Field(description="Concatenated text from words in this segment")
    channel: Optional[int] = Field(default=None, description="Audio channel (for stereo mode)")
    confidence: Optional[float] = Field(default=None, description="Average confidence of words")
    words: List[Word] = Field(default_factory=list, description="Individual words in this segment")
    
    def total_word_duration(self) -> float:
        """Compute the total duration of actual words (excluding silence)."""
        return sum(w.end - w.start for w in self.words)


@dataclass
class AlignmentConfig:
    """Configuration for alignment algorithm."""
    overlap_eps: float = 0.2  # Tolerance for word/segment overlap detection
    pad_left: float = 0.2     # Padding before first word
    pad_right: float = 0.2    # Padding after last word
    min_word_duration: float = 0.2  # Min total word duration to keep segment
    min_segment_duration: float = 0.1  # Min cleaned segment duration
    gap_threshold: float = 1.0  # Min gap duration to split segments
    merge_threshold: float = 2.5  # Max gap duration to merge segments


def align_diarization_with_words(
    words: List[Word],
    diar_segments: List[DiarizationSegment],
    config: Optional[AlignmentConfig] = None,
) -> List[CleanedSegment]:
    """Align diarization segments with Whisper word timestamps.
    
    For each diarization segment, finds overlapping words and adjusts
    the segment boundaries to match actual speech, discarding segments
    with no recognized words. Also splits segments where there are gaps
    in speech (indicating another speaker is talking).
    
    Args:
        words: List of recognized words with timestamps
        diar_segments: List of diarization segments (raw from diarization)
        config: Alignment configuration; uses defaults if None
        
    Returns:
        List of cleaned segments aligned to word timestamps
        
    Example:
        >>> words = [
        ...     Word(start=6.5, end=6.8, text="hello"),
        ...     Word(start=6.9, end=7.2, text="world"),
        ... ]
        >>> diar = [DiarizationSegment(start=2.0, end=8.0, speaker="agent")]
        >>> cleaned = align_diarization_with_words(words, diar)
        >>> cleaned[0].start  # Will be ~6.3 (6.5 - 0.2 padding)
        6.3
    """
    if config is None:
        config = AlignmentConfig()
    
    cleaned_segments: List[CleanedSegment] = []
    
    for diar_seg in diar_segments:
        # Find words that overlap with this diarization segment
        # CRITICAL: For stereo mode, only match words from the same channel
        overlapping_words = _find_overlapping_words(
            words=words,
            seg_start=diar_seg.start,
            seg_end=diar_seg.end,
            seg_channel=diar_seg.channel,
            overlap_eps=config.overlap_eps,
        )
        
        if not overlapping_words:
            logger.debug(
                "Discarding diarization segment [%.2f-%.2f] %s: no words found (likely noise)",
                diar_seg.start,
                diar_seg.end,
                diar_seg.speaker,
            )
            continue
        
        # Split into continuous speech segments based on gaps
        speech_segments = _split_on_gaps(overlapping_words, config, diar_seg)
        
        # Add all speech segments to our collection
        cleaned_segments.extend(speech_segments)
        
        for speech_seg in speech_segments:
            logger.debug(
                "Aligned segment: %s [%.2f-%.2f] → [%.2f-%.2f] (%d words, %.2fs speech)",
                diar_seg.speaker,
                diar_seg.start,
                diar_seg.end,
                speech_seg.start,
                speech_seg.end,
                len(speech_seg.words),
                sum(w.end - w.start for w in speech_seg.words),
            )
    
    # Deduplicate words across all segments to prevent overlaps
    if cleaned_segments:
        logger.debug(f"Calling deduplication on {len(cleaned_segments)} segments")
        cleaned_segments = _deduplicate_segments(cleaned_segments, config)
        logger.debug(f"Deduplication result: {len(cleaned_segments)} segments")
    
    # Merge consecutive segments from the same speaker
    if cleaned_segments:
        logger.debug(f"Calling merging on {len(cleaned_segments)} segments")
        cleaned_segments = _merge_consecutive_segments(cleaned_segments, config)
        logger.debug(f"Merging result: {len(cleaned_segments)} segments")
    
    return cleaned_segments


def _find_overlapping_words(
    words: List[Word],
    seg_start: float,
    seg_end: float,
    seg_channel: Optional[int],
    overlap_eps: float,
) -> List[Word]:
    """Find words that overlap with a time segment.
    
    A word is considered overlapping if it is not completely outside
    the segment (with epsilon tolerance for boundary effects).
    
    For stereo mode, only words from the same channel are considered.
    
    Args:
        words: List of all words
        seg_start: Segment start time
        seg_end: Segment end time
        seg_channel: Channel number (None for mono, int for stereo)
        overlap_eps: Tolerance for overlap detection
        
    Returns:
        List of overlapping words in chronological order
    """
    overlapping = []
    for w in words:
        # CRITICAL: For stereo mode, only match words from the same channel
        if seg_channel is not None and w.channel is not None:
            if w.channel != seg_channel:
                continue  # Skip words from different channels
        
        # Word overlaps if it's not completely before or after the segment
        # Allow small epsilon for floating-point and boundary effects
        word_ends_before = w.end < seg_start - overlap_eps
        word_starts_after = w.start > seg_end + overlap_eps
        
        if not (word_ends_before or word_starts_after):
            overlapping.append(w)
    
    return overlapping


def _split_on_gaps(
    words: List[Word], 
    config: AlignmentConfig, 
    diar_seg: DiarizationSegment
) -> List[CleanedSegment]:
    """Split overlapping words into continuous speech segments based on gaps.
    
    Identifies gaps in speech where another speaker might be talking and splits
    the words into separate segments.
    
    Args:
        words: List of overlapping words (sorted by start time)
        config: Alignment configuration
        diar_seg: Original diarization segment
        
    Returns:
        List of CleanedSegment objects representing continuous speech
    """
    if not words:
        return []
    
    # Sort words by start time to ensure proper ordering
    sorted_words = sorted(words, key=lambda w: w.start)
    
    segments: List[CleanedSegment] = []
    current_segment_words: List[Word] = [sorted_words[0]]
    
    # Process each subsequent word
    for i in range(1, len(sorted_words)):
        prev_word = sorted_words[i-1]
        curr_word = sorted_words[i]
        
        # Calculate gap between previous word end and current word start
        gap = curr_word.start - prev_word.end
        
        # If gap is significant, split into a new segment
        if gap > config.gap_threshold:
            # Finalize current segment
            text = " ".join(w.text for w in current_segment_words).strip()
            confidences = [w.probability for w in current_segment_words if w.probability is not None]
            avg_confidence = sum(confidences) / len(confidences) if confidences else None
            
            # Calculate padded boundaries
            first_word = current_segment_words[0]
            last_word = current_segment_words[-1]
            padded_start = max(0.0, first_word.start - config.pad_left)
            padded_end = last_word.end + config.pad_right
            
            segment = CleanedSegment(
                speaker=diar_seg.speaker,
                start=padded_start,
                end=padded_end,
                text=text,
                channel=diar_seg.channel,
                confidence=avg_confidence,
                words=current_segment_words,
            )
            segments.append(segment)
            
            # Start new segment with current word
            current_segment_words = [curr_word]
        else:
            # Continue current segment
            current_segment_words.append(curr_word)
    
    # Don't forget the last segment
    if current_segment_words:
        text = " ".join(w.text for w in current_segment_words).strip()
        confidences = [w.probability for w in current_segment_words if w.probability is not None]
        avg_confidence = sum(confidences) / len(confidences) if confidences else None
        
        # Calculate padded boundaries
        first_word = current_segment_words[0]
        last_word = current_segment_words[-1]
        padded_start = max(0.0, first_word.start - config.pad_left)
        padded_end = last_word.end + config.pad_right
        
        segment = CleanedSegment(
            speaker=diar_seg.speaker,
            start=padded_start,
            end=padded_end,
            text=text,
            channel=diar_seg.channel,
            confidence=avg_confidence,
            words=current_segment_words,
        )
        segments.append(segment)
    
    return segments


def _deduplicate_segments(
    segments: List[CleanedSegment],
    config: AlignmentConfig
) -> List[CleanedSegment]:
    """Deduplicate words across segments by removing overlapping words.
    
    When diarization segments overlap, the same words can appear in multiple
    cleaned segments. This function removes duplicates by keeping words
    in earlier segments and removing them from later ones.
    
    Args:
        segments: List of cleaned segments (sorted by start time)
        config: Alignment configuration
        
    Returns:
        List of deduplicated segments
    """
    # Even with a single segment, we still need to apply filtering
    if not segments:
        return segments
    
    # Sort segments by start time to process in order
    sorted_segments = sorted(segments, key=lambda s: s.start)
    
    # Keep track of words we've already seen by their exact timestamps and channel
    # Include channel to avoid deduplicating across different audio channels
    seen_words: List[tuple[float, float, str, Optional[int]]] = []  # (start, end, text, channel) tuples
    
    deduplicated_segments: List[CleanedSegment] = []
    
    for segment in sorted_segments:
        # Filter out words that have already been seen
        unique_words = []
        for word in segment.words:
            # Check if this exact word (same start, end, text, and channel) has been seen
            word_signature = (word.start, word.end, word.text, word.channel)
            is_duplicate = word_signature in seen_words
            
            if not is_duplicate:
                unique_words.append(word)
                seen_words.append(word_signature)
        
        # Only keep segments that still have words after deduplication
        if unique_words:
            # Recalculate segment text and confidence with unique words
            text = " ".join(w.text for w in unique_words).strip()
            confidences = [w.probability for w in unique_words if w.probability is not None]
            avg_confidence = sum(confidences) / len(confidences) if confidences else None
            
            # Recalculate boundaries if needed
            if len(unique_words) != len(segment.words):
                first_word = unique_words[0]
                last_word = unique_words[-1]
                padded_start = max(0.0, first_word.start - config.pad_left)
                padded_end = last_word.end + config.pad_right
                
                deduplicated_segment = CleanedSegment(
                    speaker=segment.speaker,
                    start=padded_start,
                    end=padded_end,
                    text=text,
                    channel=segment.channel,
                    confidence=avg_confidence,
                    words=unique_words,
                )
            else:
                # No words were removed, keep original segment
                deduplicated_segment = segment
                
            # Apply final filtering based on word duration and segment duration
            total_word_dur = sum(w.end - w.start for w in unique_words)
            segment_duration = deduplicated_segment.end - deduplicated_segment.start
            
            logger.debug(
                "Segment %s [%.2f-%.2f]: word_dur=%.3fs, seg_dur=%.3fs, min_word=%.3fs, min_seg=%.3fs", 
                deduplicated_segment.speaker,
                deduplicated_segment.start,
                deduplicated_segment.end,
                total_word_dur,
                segment_duration,
                config.min_word_duration,
                config.min_segment_duration
            )
            
            if total_word_dur >= config.min_word_duration and segment_duration >= config.min_segment_duration:
                deduplicated_segments.append(deduplicated_segment)
            else:
                logger.debug(
                    "Discarding segment %s [%.2f-%.2f]: word_dur=%.3fs < %.3fs or seg_dur=%.3fs < %.3fs", 
                    deduplicated_segment.speaker,
                    deduplicated_segment.start,
                    deduplicated_segment.end,
                    total_word_dur, config.min_word_duration,
                    segment_duration, config.min_segment_duration
                )
        else:
            logger.debug(f"Segment {segment.speaker} has no unique words after deduplication")
    
    logger.debug(f"Deduplication returning {len(deduplicated_segments)} segments")
    return deduplicated_segments


def _merge_consecutive_segments(
    segments: List[CleanedSegment],
    config: AlignmentConfig
) -> List[CleanedSegment]:
    """Merge consecutive segments from the same speaker when there's no significant gap.
    
    When the same speaker has multiple consecutive segments with little or no gap
    between them (including overlapping segments), merge them into a single segment.
    Segments are merged if the gap between them is less than or equal to merge_threshold.
    Negative gaps (overlapping segments) are always merged.
    
    Args:
        segments: List of cleaned segments (sorted by start time)
        config: Alignment configuration
        
    Returns:
        List of merged segments
    """
    if len(segments) <= 1:
        return segments
    
    # Sort segments by start time to process in order
    sorted_segments = sorted(segments, key=lambda s: s.start)
    
    logger.debug(f"Starting merge process with {len(sorted_segments)} segments")
    for i, seg in enumerate(sorted_segments):
        logger.debug(f"Segment {i}: {seg.speaker} [{seg.start:.2f}-{seg.end:.2f}] channel={seg.channel}")
    
    merged_segments: List[CleanedSegment] = []
    current_segment = sorted_segments[0]
    
    # Process each subsequent segment
    for next_segment in sorted_segments[1:]:
        # Check if we can merge: same speaker and channel, and small gap
        if (current_segment.speaker == next_segment.speaker and 
            current_segment.channel == next_segment.channel):
            
            # Calculate gap between current segment end and next segment start
            gap = next_segment.start - current_segment.end
            
            # If segments overlap or have a small gap, merge the segments
            # Overlapping segments have negative gaps
            if gap <= config.merge_threshold:
                # Merge the segments
                merged_words = current_segment.words + next_segment.words
                merged_text = f"{current_segment.text} {next_segment.text}".strip()
                
                # Recalculate confidence as weighted average
                current_word_dur = sum(w.end - w.start for w in current_segment.words)
                next_word_dur = sum(w.end - w.start for w in next_segment.words)
                total_word_dur = current_word_dur + next_word_dur
                
                if total_word_dur > 0:
                    # Weighted average by word duration
                    current_weight = current_word_dur / total_word_dur
                    next_weight = next_word_dur / total_word_dur
                    
                    if current_segment.confidence is not None and next_segment.confidence is not None:
                        merged_confidence = (
                            current_weight * current_segment.confidence + 
                            next_weight * next_segment.confidence
                        )
                    elif current_segment.confidence is not None:
                        merged_confidence = current_segment.confidence
                    elif next_segment.confidence is not None:
                        merged_confidence = next_segment.confidence
                    else:
                        merged_confidence = None
                else:
                    # Simple average if no word durations
                    if current_segment.confidence is not None and next_segment.confidence is not None:
                        merged_confidence = (current_segment.confidence + next_segment.confidence) / 2
                    elif current_segment.confidence is not None:
                        merged_confidence = current_segment.confidence
                    elif next_segment.confidence is not None:
                        merged_confidence = next_segment.confidence
                    else:
                        merged_confidence = None
                
                # Calculate new boundaries
                first_word = merged_words[0]
                last_word = merged_words[-1]
                merged_start = max(0.0, first_word.start - config.pad_left)
                merged_end = last_word.end + config.pad_right
                
                # Create merged segment
                current_segment = CleanedSegment(
                    speaker=current_segment.speaker,
                    start=merged_start,
                    end=merged_end,
                    text=merged_text,
                    channel=current_segment.channel,
                    confidence=merged_confidence,
                    words=merged_words,
                )
                
                logger.debug(
                    "Merged segments: %s [%.2f-%.2f] + [%.2f-%.2f] (gap=%.3fs, threshold=%.3fs)",
                    current_segment.speaker,
                    current_segment.start,
                    current_segment.end,
                    next_segment.start,
                    next_segment.end,
                    gap,
                    config.merge_threshold
                )
                continue  # Continue to check if we can merge with the next segment
            else:
                logger.debug(
                    "Not merging segments: %s [%.2f-%.2f] + [%.2f-%.2f] (gap=%.3fs > threshold=%.3fs)",
                    current_segment.speaker,
                    current_segment.start,
                    current_segment.end,
                    next_segment.start,
                    next_segment.end,
                    gap,
                    config.merge_threshold
                )
        else:
            logger.debug(
                "Not merging segments: different speaker/channel %s/%s vs %s/%s",
                current_segment.speaker,
                current_segment.channel,
                next_segment.speaker,
                next_segment.channel
            )
        
        # Can't merge, so add current segment to results and move to next
        merged_segments.append(current_segment)
        current_segment = next_segment
    
    # Don't forget the last segment
    merged_segments.append(current_segment)
    
    logger.debug(f"Merging returning {len(merged_segments)} segments")
    return merged_segments
