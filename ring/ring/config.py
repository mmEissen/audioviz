import os


_things_to_mock = os.environ.get("RING_MOCK", "").lower().split(",")

MOCK_RING = "ring" in _things_to_mock

PORT = int(os.environ.get("RING_PORT", 50000))
NUM_LEDS = int(os.environ.get("RING_NUM_LEDS", 60))

VOLUME_MIN_THRESHOLD = float(os.environ.get("RING_VOLUME_MIN", 0.001))
VOLUME_FALLOFF = float(os.environ.get("RING_VOLUME_FALLOFF", 32))