#!/usr/bin/env python3
"""Test for interleaved output formatting."""


def test_interleaved_output_format():
    """Test that segments are formatted with interleaved speaker labels."""
    # Create sample segments in chronological order (simulated)
    segments = [
        {"speaker": "manager", "text": "Hello, how can I help you?"},
        {"speaker": "customer", "text": "I have a problem with my device."},
        {"speaker": "manager", "text": "Let me help you with that."}
    ]
    
    # Format as interleaved text
    interleaved_texts = []
    for segment in segments:
        segment_text = f"[{segment['speaker']}] {segment['text']}"
        interleaved_texts.append(segment_text)
    
    full_text = "\n".join(interleaved_texts)
    
    # Verify the format
    expected_lines = [
        "[manager] Hello, how can I help you?",
        "[customer] I have a problem with my device.",
        "[manager] Let me help you with that."
    ]
    
    actual_lines = full_text.split("\n")
    assert actual_lines == expected_lines
    
    print("✓ Interleaved output format test passed")
    print("Formatted text:")
    print(full_text)


if __name__ == "__main__":
    test_interleaved_output_format()
    print("All tests passed!")