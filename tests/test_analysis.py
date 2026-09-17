from savescope.core.analysis import BinaryAnalysisEngine

def test_entropy_and_block_identification():
    # Pure zero data
    zeros = b"\x00" * 256
    assert BinaryAnalysisEngine.calculate_shannon_entropy(zeros) == 0.0

    # Plain text
    text = b"This is plain text binary readable save data header!" * 4
    text_entropy = BinaryAnalysisEngine.calculate_shannon_entropy(text)
    assert 2.0 < text_entropy < 5.0

    # Simulated random/compressed bytes
    import os
    random_bytes = os.urandom(2048)
    rand_entropy = BinaryAnalysisEngine.calculate_shannon_entropy(random_bytes)
    assert rand_entropy > 7.2

    blocks = BinaryAnalysisEngine.identify_blocks(zeros + text + random_bytes, chunk_size=64)
    assert any(b["type"] == "ZERO_PADDING" for b in blocks)
    assert any(b["type"] == "ASCII_TEXT" for b in blocks)
    assert any(b["type"] == "COMPRESSED_OR_ENCRYPTED" for b in blocks)
