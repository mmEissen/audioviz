import os


_things_to_mock = os.environ.get("RING_MOCK", "").lower().split(",")
MOCK_AUDIO = "audio" in _things_to_mock
MOCK_RING = "ring" in _things_to_mock
PROFILING_ENABLED = True
