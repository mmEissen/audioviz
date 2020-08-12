import config

import typing as t
import time
import sys
import os

import audio_tools
import threading
from airpixel import client as air_client
from pyPiper import Pipeline

import nodes


BEAMS = 36
LED_PER_BEAM = 8

VISUALIZE = bool(os.environ.get("VISUALIZE", False))

SAMPLE_RATE = 176400

PORT = 50000

VOLUME_MIN_THRESHOLD = 0
VOLUME_FALLOFF = 1.1
VOLUME_DEBUG = 0

FADE_FALLOFF = 32

FIRST_OCTAVE = 5
NUM_OCTAVES = 8

WINDOW_SIZE_SEC = 0.1


def main() -> None:
    ip_address, port = sys.argv[1:3]

    mon_client = air_client.MonitorClient("monitoring_uds")

    audio_input = audio_tools.AudioInput(sample_rate=SAMPLE_RATE)
    audio_input.start()

    samples = audio_input.seconds_to_samples(WINDOW_SIZE_SEC)
    fft_node = nodes.FastFourierTransform(
        "fft", samples=samples, sample_delta=audio_input.sample_delta, monitor_client=mon_client
    )

    pipeline = Pipeline(
        nodes.AudioGenerator(
            "mic", audio_input=audio_input, samples=samples, monitor_client=mon_client
        )
        | fft_node
        | nodes.AWeighting(
            "a-weighting", frequencies=fft_node.fourier_frequencies, monitor_client=mon_client
        )
        | nodes.OctaveSubsampler(
            "sampled",
            start_octave=FIRST_OCTAVE,
            samples_per_octave=BEAMS / NUM_OCTAVES,
            num_octaves=NUM_OCTAVES,
            frequencies=fft_node.fourier_frequencies,
            monitor_client=mon_client,
        )
        | nodes.Gaussian("smoothed", sigma=0.5, monitor_client=mon_client)
        # | nodes.FoldingNode("folded", samples_per_octave=BEAMS, monitor_client=mon_client)
        # | nodes.SumMatrixVertical("sum", monitor_client=mon_client)
        # | nodes.MaxMatrixVertical("max", monitor_client=mon_client)
        | nodes.Normalizer(
            "normalized",
            min_threshold=VOLUME_MIN_THRESHOLD,
            falloff=VOLUME_FALLOFF,
            monitor_client=mon_client,
        )
        | nodes.Square("square", monitor_client=mon_client)
        | nodes.Logarithm("log", i_0=0.03, monitor_client=mon_client)
        # | nodes.Fade("fade", falloff=FADE_FALLOFF, monitor_client=mon_client)
        # | nodes.Shift("clip", minimum=0.14)
        | nodes.Star(
            "ring",
            ip_address=ip_address,
            port=port,
            led_per_beam=LED_PER_BEAM,
            beams=BEAMS,
            octaves=NUM_OCTAVES,
        )
    )

    if config.VISUALIZE:
        audio_pipeline = threading.Thread(target=pipeline.run, daemon=True)
        audio_pipeline.start()
        app.exec_()
    else:
        pipeline.run()


if __name__ == "__main__":
    main()
