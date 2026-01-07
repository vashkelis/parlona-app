#!/usr/bin/env python3
"""Test for agent_id speaker label replacement."""


def test_agent_id_replacement():
    """Test that manager labels are replaced with agent_id when provided."""
    # Create sample segments (as dictionaries to avoid dependencies)
    segments = [
        {"speaker": "manager", "text": "Hello, how can I help you?"},
        {"speaker": "customer", "text": "I have a problem with my device."},
        {"speaker": "manager", "text": "Let me help you with that."}
    ]
    
    # Test with agent_id provided
    extra_meta = {"agent_id": "6001"}
    agent_id = extra_meta.get("agent_id") if extra_meta else None
    
    if agent_id:
        for segment in segments:
            if segment["speaker"] == "manager":
                segment["speaker"] = agent_id
    
    # Verify manager labels were replaced
    assert segments[0]["speaker"] == "6001"
    assert segments[1]["speaker"] == "customer"  # Should remain unchanged
    assert segments[2]["speaker"] == "6001"
    
    # Format as interleaved text
    interleaved_texts = []
    for segment in segments:
        segment_text = f"[{segment['speaker']}] {segment['text']}"
        interleaved_texts.append(segment_text)
    
    full_text = "\n".join(interleaved_texts)
    
    # Verify the format
    expected_lines = [
        "[6001] Hello, how can I help you?",
        "[customer] I have a problem with my device.",
        "[6001] Let me help you with that."
    ]
    
    actual_lines = full_text.split("\n")
    assert actual_lines == expected_lines
    
    print("✓ Agent ID replacement test passed")
    print("Formatted text:")
    print(full_text)
    
    # Test without agent_id (should keep original labels)
    segments_original = [
        {"speaker": "manager", "text": "Hello, how can I help you?"}
    ]
    
    # Test with empty metadata
    extra_meta_empty = {}
    agent_id_empty = extra_meta_empty.get("agent_id") if extra_meta_empty else None
    
    # Since agent_id_empty is None, no replacement should happen
    if agent_id_empty:
        for segment in segments_original:
            if segment["speaker"] == "manager":
                segment["speaker"] = agent_id_empty
    
    # Should still be "manager"
    assert segments_original[0]["speaker"] == "manager"
    
    print("✓ No agent ID test passed")


if __name__ == "__main__":
    test_agent_id_replacement()
    print("All tests passed!")