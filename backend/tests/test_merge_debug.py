#!/usr/bin/env python3
"""Debug test for the specific merging issue."""

import logging
from backend.stt_service.app.alignment import (
    Word, 
    DiarizationSegment, 
    CleanedSegment,
    AlignmentConfig,
    _merge_consecutive_segments
)

# Set up logging to see the debug messages
logging.basicConfig(level=logging.DEBUG)


def test_merge_issue():
    """Test the specific case from the user's log."""
    # Create the segments as they appear in the log
    segment1 = CleanedSegment(
        speaker="customer",
        start=48.82,
        end=51.76,
        text="Так, нажимаю. Держу.",
        channel=1,
        confidence=0.9698866340849134,
        words=[
            Word(start=49.02, end=49.48, text="Так,", probability=0.9254106879234314, channel=1),
            Word(start=49.9, end=50.32, text="нажимаю.", probability=0.991982638835907, channel=1),
            Word(start=51.06, end=51.56, text="Держу.", probability=0.992266575495402, channel=1),
        ]
    )
    
    segment2 = CleanedSegment(
        speaker="customer",
        start=53.78,
        end=57.7,
        text="Готово. Да, теперь индикатор горит синим.",
        channel=1,
        confidence=0.9576696150865492,
        words=[
            Word(start=53.98, end=54.64, text="Готово.", probability=0.9669235199689865, channel=1),
            Word(start=55.62, end=55.9, text="Да,", probability=0.9538224339485168, channel=1),
            Word(start=56.42, end=56.42, text="теперь", probability=0.9947412014007568, channel=1),
            Word(start=56.42, end=56.92, text="индикатор", probability=0.9815021455287933, channel=1),
            Word(start=56.92, end=57.2, text="горит", probability=0.9936557412147522, channel=1),
            Word(start=57.2, end=57.5, text="синим.", probability=0.8421722253163656, channel=1),
        ]
    )
    
    segments = [segment1, segment2]
    config = AlignmentConfig(merge_threshold=2.5)  # New default
    
    print(f"Segment 1: {segment1.speaker} [{segment1.start:.2f}-{segment1.end:.2f}] channel={segment1.channel}")
    print(f"Segment 2: {segment2.speaker} [{segment2.start:.2f}-{segment2.end:.2f}] channel={segment2.channel}")
    print(f"Gap: {segment2.start - segment1.end:.2f} seconds")
    print(f"Merge threshold: {config.merge_threshold} seconds")
    
    # Test with new default threshold
    result = _merge_consecutive_segments(segments, config)
    print(f"Result with threshold {config.merge_threshold}: {len(result)} segments")
    
    if len(result) == 1:
        merged = result[0]
        print(f"Merged segment: {merged.speaker} [{merged.start:.2f}-{merged.end:.2f}]")
        print(f"Text: {merged.text}")
        print(f"Words: {[w.text for w in merged.words]}")
    
    # Test with even higher threshold
    config_high = AlignmentConfig(merge_threshold=3.0)
    result_high = _merge_consecutive_segments(segments, config_high)
    print(f"Result with threshold {config_high.merge_threshold}: {len(result_high)} segments")
    
    if len(result_high) == 1:
        merged = result_high[0]
        print(f"Merged segment: {merged.speaker} [{merged.start:.2f}-{merged.end:.2f}]")
        print(f"Text: {merged.text}")
        print(f"Words: {[w.text for w in merged.words]}")


if __name__ == "__main__":
    test_merge_issue()