"""Tests for word-level alignment functionality."""
from __future__ import annotations

import pytest
from backend.stt_service.app.alignment import (
    AlignmentConfig,
    CleanedSegment,
    DiarizationSegment,
    Word,
    align_diarization_with_words,
)


class TestWordLevelAlignment:
    """Test suite for word-level alignment."""

    def test_basic_alignment(self):
        """Test basic alignment with words inside diarization segment."""
        words = [
            Word(start=6.5, end=6.8, text="hello"),
            Word(start=6.9, end=7.2, text="world"),
        ]
        diar_segments = [
            DiarizationSegment(start=2.0, end=8.0, speaker="agent"),
        ]
        
        cleaned = align_diarization_with_words(words, diar_segments)
        
        assert len(cleaned) == 1
        assert cleaned[0].speaker == "agent"
        # Start should be first word start minus padding (6.5 - 0.2 = 6.3)
        assert cleaned[0].start == pytest.approx(6.3, abs=0.01)
        # End should be last word end plus padding (7.2 + 0.2 = 7.4)
        assert cleaned[0].end == pytest.approx(7.4, abs=0.01)
        assert cleaned[0].text == "hello world"
        assert len(cleaned[0].words) == 2

    def test_discards_segments_without_words(self):
        """Test that segments with no words are discarded."""
        words = [
            Word(start=10.0, end=10.5, text="test"),
        ]
        diar_segments = [
            DiarizationSegment(start=2.0, end=5.0, speaker="agent"),  # No words
            DiarizationSegment(start=9.5, end=11.0, speaker="client"),  # Has words
        ]
        
        cleaned = align_diarization_with_words(words, diar_segments)
        
        # Only the segment with words should remain
        assert len(cleaned) == 1
        assert cleaned[0].speaker == "client"
        assert "test" in cleaned[0].text

    def test_multiple_segments_with_words(self):
        """Test alignment with multiple speaker segments."""
        words = [
            Word(start=1.0, end=1.5, text="hello"),
            Word(start=1.6, end=2.0, text="there"),
            Word(start=5.0, end=5.3, text="how"),
            Word(start=5.4, end=5.8, text="are"),
            Word(start=5.9, end=6.2, text="you"),
        ]
        diar_segments = [
            DiarizationSegment(start=0.5, end=3.0, speaker="agent"),
            DiarizationSegment(start=4.5, end=7.0, speaker="client"),
        ]
        
        cleaned = align_diarization_with_words(words, diar_segments)
        
        assert len(cleaned) == 2
        assert cleaned[0].speaker == "agent"
        assert cleaned[0].text == "hello there"
        assert cleaned[1].speaker == "client"
        assert cleaned[1].text == "how are you"

    def test_custom_padding(self):
        """Test alignment with custom padding configuration."""
        words = [
            Word(start=5.0, end=5.5, text="test"),
        ]
        diar_segments = [
            DiarizationSegment(start=4.0, end=6.0, speaker="agent"),
        ]
        config = AlignmentConfig(
            pad_left=0.5,
            pad_right=0.3,
        )
        
        cleaned = align_diarization_with_words(words, diar_segments, config)
        
        assert len(cleaned) == 1
        # Start: 5.0 - 0.5 = 4.5
        assert cleaned[0].start == pytest.approx(4.5, abs=0.01)
        # End: 5.5 + 0.3 = 5.8
        assert cleaned[0].end == pytest.approx(5.8, abs=0.01)

    def test_min_word_duration_filter(self):
        """Test filtering segments with insufficient word duration."""
        words = [
            Word(start=5.0, end=5.05, text="uh"),  # Very short word
        ]
        diar_segments = [
            DiarizationSegment(start=4.0, end=8.0, speaker="agent"),
        ]
        config = AlignmentConfig(
            min_word_duration=0.2,  # Require at least 0.2s of actual speech
        )
        
        cleaned = align_diarization_with_words(words, diar_segments, config)
        
        # Segment should be discarded due to insufficient word duration
        assert len(cleaned) == 0

    def test_stereo_channel_preservation(self):
        """Test that channel information is preserved."""
        words = [
            Word(start=1.0, end=1.5, text="left", channel=0),
            Word(start=2.0, end=2.5, text="right", channel=1),
        ]
        diar_segments = [
            DiarizationSegment(start=0.5, end=2.0, speaker="agent", channel=0),
            DiarizationSegment(start=1.5, end=3.0, speaker="client", channel=1),
        ]
        
        cleaned = align_diarization_with_words(words, diar_segments)
        
        assert len(cleaned) == 2
        assert cleaned[0].channel == 0
        assert cleaned[0].speaker == "agent"
        assert cleaned[1].channel == 1
        assert cleaned[1].speaker == "client"

    def test_overlap_epsilon_tolerance(self):
        """Test overlap detection with epsilon tolerance."""
        words = [
            Word(start=5.0, end=5.5, text="test"),
        ]
        # Diarization segment ends just before word starts (within epsilon)
        diar_segments = [
            DiarizationSegment(start=4.0, end=4.85, speaker="agent"),
        ]
        config = AlignmentConfig(
            overlap_eps=0.2,  # Should catch the word (4.85 + 0.2 > 5.0)
        )
        
        cleaned = align_diarization_with_words(words, diar_segments, config)
        
        # Should include the word due to epsilon tolerance
        assert len(cleaned) == 1
        assert "test" in cleaned[0].text

    def test_zero_padding_at_start(self):
        """Test that start timestamp doesn't go below zero."""
        words = [
            Word(start=0.1, end=0.5, text="start"),
        ]
        diar_segments = [
            DiarizationSegment(start=0.0, end=1.0, speaker="agent"),
        ]
        config = AlignmentConfig(
            pad_left=0.5,  # Would normally put start at -0.4
        )
        
        cleaned = align_diarization_with_words(words, diar_segments, config)
        
        assert len(cleaned) == 1
        # Start should be clamped to 0.0
        assert cleaned[0].start == 0.0

    def test_word_probability_preservation(self):
        """Test that word probabilities are preserved and averaged."""
        words = [
            Word(start=1.0, end=1.5, text="hello", probability=0.9),
            Word(start=1.6, end=2.0, text="world", probability=0.8),
        ]
        diar_segments = [
            DiarizationSegment(start=0.5, end=2.5, speaker="agent"),
        ]
        
        cleaned = align_diarization_with_words(words, diar_segments)
        
        assert len(cleaned) == 1
        # Average confidence should be (0.9 + 0.8) / 2 = 0.85
        assert cleaned[0].confidence == pytest.approx(0.85, abs=0.01)
        # Words should be preserved
        assert len(cleaned[0].words) == 2
        assert cleaned[0].words[0].probability == 0.9

    def test_empty_inputs(self):
        """Test handling of empty inputs."""
        # No words
        cleaned = align_diarization_with_words([], [DiarizationSegment(start=0, end=1, speaker="agent")])
        assert len(cleaned) == 0
        
        # No diarization segments
        cleaned = align_diarization_with_words([Word(start=0, end=1, text="test")], [])
        assert len(cleaned) == 0
        
        # Both empty
        cleaned = align_diarization_with_words([], [])
        assert len(cleaned) == 0

    def test_channel_isolation(self):
        """Test that words from different channels are isolated correctly."""
        # Simulate stereo scenario: channel 0 words at 1.0-1.5s, channel 1 words at 1.2-1.8s
        words = [
            Word(start=1.0, end=1.3, text="hello", channel=0),      # Channel 0
            Word(start=1.4, end=1.5, text="world", channel=0),      # Channel 0
            Word(start=1.2, end=1.4, text="goodbye", channel=1),    # Channel 1
            Word(start=1.5, end=1.8, text="everyone", channel=1),   # Channel 1
        ]
        
        # Diarization segments for each channel
        diar_segments = [
            DiarizationSegment(start=0.5, end=2.0, speaker="agent", channel=0),
            DiarizationSegment(start=0.5, end=2.0, speaker="client", channel=1),
        ]
        
        cleaned = align_diarization_with_words(words, diar_segments)
        
        # Should have two separate segments
        assert len(cleaned) == 2
        
        # Find segments by speaker
        agent_segment = next((s for s in cleaned if s.speaker == "agent"), None)
        client_segment = next((s for s in cleaned if s.speaker == "client"), None)
        
        assert agent_segment is not None
        assert client_segment is not None
        
        # Agent segment should only contain channel 0 words
        assert agent_segment.channel == 0
        assert len(agent_segment.words) == 2
        assert all(w.channel == 0 for w in agent_segment.words)
        assert "hello" in agent_segment.text
        assert "world" in agent_segment.text
        
        # Client segment should only contain channel 1 words
        assert client_segment.channel == 1
        assert len(client_segment.words) == 2
        assert all(w.channel == 1 for w in client_segment.words)
        assert "goodbye" in client_segment.text
        assert "everyone" in client_segment.text

    def test_gap_splitting(self):
        """Test that segments are split when there are gaps indicating another speaker."""
        # Simulate a customer speaking with a gap where manager speaks
        # Customer: 18.21-19.05, gap (manager speaks), then 28.05-29.53
        words = [
            Word(start=18.21, end=18.55, text="Hello", channel=1),
            Word(start=18.55, end=19.05, text="customer", channel=1),
            # GAP HERE where manager speaks (19.27-25.39)
            Word(start=28.05, end=28.71, text="Goodbye", channel=1),
            Word(start=28.71, end=29.53, text="customer", channel=1),
        ]
        
        # Original diarization segment covers entire time range
        diar_segments = [
            DiarizationSegment(start=18.01, end=29.73, speaker="customer", channel=1),
        ]
        
        # Use a small gap threshold to trigger splitting
        config = AlignmentConfig(gap_threshold=2.0, pad_left=0.2, pad_right=0.2)  # Split on 2+ second gaps
        
        cleaned = align_diarization_with_words(words, diar_segments, config)
        
        # Should have two separate segments due to the gap
        assert len(cleaned) == 2
        
        # Both segments should belong to the customer
        assert all(s.speaker == "customer" for s in cleaned)
        assert all(s.channel == 1 for s in cleaned)
        
        # First segment should contain first two words
        first_segment = cleaned[0]
        assert len(first_segment.words) == 2
        assert "Hello" in first_segment.text
        assert "customer" in first_segment.text
        # Start should be first word start minus padding (18.21 - 0.2 = 18.01)
        assert first_segment.start == pytest.approx(18.01, abs=0.01)
        
        # Second segment should contain last two words
        second_segment = cleaned[1]
        assert len(second_segment.words) == 2
        assert "Goodbye" in second_segment.text
        assert "customer" in second_segment.text
        # Start should be first word start minus padding (28.05 - 0.2 = 27.85)
        assert second_segment.start == pytest.approx(27.85, abs=0.01)

    def test_deduplication_of_overlapping_segments(self):
        """Test that duplicate words in overlapping segments are removed."""
        # Simulate overlapping diarization segments that would produce EXACT duplicate words
        # These represent the same word appearing in multiple diarization segments
        words = [
            Word(start=30.24, end=30.90, text="Спасибо", channel=0),
            Word(start=31.34, end=31.86, text="мигающий", channel=0),
            Word(start=31.86, end=32.22, text="красный", channel=0),
            Word(start=32.22, end=32.68, text="индикатор", channel=0),
            Word(start=32.68, end=32.82, text="на", channel=0),  # This word will be duplicated
            Word(start=32.82, end=33.08, text="данной", channel=0),
            Word(start=33.08, end=33.42, text="модели", channel=0),
            Word(start=33.42, end=33.70, text="обычно", channel=0),
            Word(start=33.70, end=34.24, text="указывает", channel=0),
            Word(start=34.24, end=34.36, text="неудачную", channel=0),
            Word(start=34.36, end=34.84, text="попытку", channel=0),
            Word(start=34.84, end=35.24, text="подключения", channel=0),
        ]
        
        # Create diarization segments that would cause the SAME word to appear in both
        # by duplicating the word with exact same timestamps in our test setup
        # In real scenarios, this happens when overlapping diarization segments both match the same word
        
        # Overlapping diarization segments that would cause duplicates
        diar_segments = [
            DiarizationSegment(start=30.04, end=33.90, speaker="manager", channel=0),
            DiarizationSegment(start=32.88, end=38.04, speaker="manager", channel=0),
        ]
        
        # Disable merging for this test to isolate deduplication behavior
        config = AlignmentConfig(merge_threshold=-10.0)  # Disable merging even for overlapping segments
        
        cleaned = align_diarization_with_words(words, diar_segments, config)
        
        # Should have 2 segments after deduplication (and no merging due to 0 threshold)
        assert len(cleaned) == 2
        
        # All segments should belong to the manager
        assert all(s.speaker == "manager" for s in cleaned)
        assert all(s.channel == 0 for s in cleaned)
        
        # No word should appear in both segments (deduplication check)
        all_words_in_first = [w.text for w in cleaned[0].words]
        all_words_in_second = [w.text for w in cleaned[1].words]
        
        # Check that there's no overlap in words between segments
        common_words = set(all_words_in_first) & set(all_words_in_second)
        # In this case we expect the deduplication to work correctly
        # The word that appears in both segments should only be in the first one
        
        # Total words should be less than or equal to original count due to deduplication
        total_words = len(all_words_in_first) + len(all_words_in_second)
        assert total_words <= len(words), f"Expected deduplication to reduce words, got {total_words} from {len(words)}"
        
        # Check that we have the expected words distributed between segments
        # First segment should have the early words including the duplicated one
        # Second segment should have the later words without the duplicated one
        assert "Спасибо" in all_words_in_first
        assert "указывает" in all_words_in_first
        assert "подключения" in all_words_in_second

    def test_merge_consecutive_segments(self):
        """Test that consecutive segments from the same speaker are merged."""
        # Simulate consecutive segments from the same speaker with a small gap
        words = [
            Word(start=30.24, end=30.90, text="Спасибо", channel=0),
            Word(start=31.34, end=31.86, text="мигающий", channel=0),
            Word(start=31.86, end=32.22, text="красный", channel=0),
            Word(start=32.22, end=32.68, text="индикатор", channel=0),
            Word(start=32.68, end=32.82, text="на", channel=0),
            Word(start=32.82, end=33.08, text="данной", channel=0),
            Word(start=33.08, end=33.42, text="модели", channel=0),
            Word(start=33.42, end=33.70, text="обычно", channel=0),
            Word(start=33.70, end=34.24, text="указывает", channel=0),
            Word(start=34.24, end=34.36, text="на", channel=0),
            Word(start=34.36, end=34.84, text="неудачную", channel=0),
            Word(start=34.84, end=35.24, text="попытку", channel=0),
            Word(start=35.24, end=35.88, text="подключения", channel=0),
        ]
        
        # Two consecutive segments from the same speaker with a small gap
        diar_segments = [
            DiarizationSegment(start=30.04, end=33.90, speaker="manager", channel=0),
            DiarizationSegment(start=33.50, end=38.04, speaker="manager", channel=0),  # Small gap to previous
        ]
        
        # Use a merge threshold that will trigger merging
        config = AlignmentConfig(merge_threshold=1.0)  # Merge gaps up to 1 second
        
        cleaned = align_diarization_with_words(words, diar_segments, config)
        
        # Should have 1 merged segment instead of 2 separate ones
        assert len(cleaned) == 1
        
        # The merged segment should contain all words
        segment = cleaned[0]
        assert segment.speaker == "manager"
        assert segment.channel == 0
        
        # Check that all words are present
        word_texts = [w.text for w in segment.words]
        assert "Спасибо" in word_texts
        assert "подключения" in word_texts
        
        # Check that the segment boundaries encompass all words
        assert segment.start <= 30.24  # Should start at or before first word
        assert segment.end >= 35.88   # Should end at or after last word

    def test_merge_three_consecutive_segments_with_larger_gaps(self):
        """Test merging three segments with larger gaps that should still be merged with increased threshold."""
        # Simulate the case from the user's log
        words = [
            Word(start=49.02, end=49.48, text="Так,", channel=1),
            Word(start=49.90, end=50.32, text="нажимаю.", channel=1),
            Word(start=51.06, end=51.56, text="Держу.", channel=1),
            Word(start=53.98, end=54.64, text="Готово.", channel=1),
            Word(start=55.62, end=55.90, text="Да,", channel=1),
            Word(start=56.42, end=56.42, text="теперь", channel=1),
            Word(start=56.42, end=56.92, text="индикатор", channel=1),
            Word(start=56.92, end=57.20, text="горит", channel=1),
            Word(start=57.20, end=57.50, text="синим.", channel=1),
        ]
        
        # Three consecutive segments from the same speaker with small gaps
        diar_segments = [
            DiarizationSegment(start=48.82, end=51.76, speaker="customer", channel=1),
            DiarizationSegment(start=53.78, end=54.84, speaker="customer", channel=1),
            DiarizationSegment(start=55.42, end=57.70, speaker="customer", channel=1),
        ]
        
        # Use a merge threshold that will trigger merging of all segments
        config = AlignmentConfig(merge_threshold=2.5)  # Merge gaps up to 2.5 seconds
        
        cleaned = align_diarization_with_words(words, diar_segments, config)
        
        # Should have 1 merged segment instead of 3 separate ones
        assert len(cleaned) == 1
        
        # The merged segment should contain all words
        segment = cleaned[0]
        assert segment.speaker == "customer"
        assert segment.channel == 1
        
        # Check that all words are present
        word_texts = [w.text for w in segment.words]
        assert "Так," in word_texts
        assert "нажимаю." in word_texts
        assert "Держу." in word_texts
        assert "Готово." in word_texts
        assert "Да," in word_texts
        assert "теперь" in word_texts
        assert "индикатор" in word_texts
        assert "горит" in word_texts
        assert "синим." in word_texts
        
        # Check that the segment boundaries encompass all words
        assert segment.start <= 49.02  # Should start at or before first word
        assert segment.end >= 57.50   # Should end at or after last word
