import config

import typing as t
import time
import sys
import os

import audio_tools
import threading
from airpixel import client as air_client
from pyPiper import Pipeline

if config.VISUALIZE:
    import pyqtgraph as graph
    from pyqtgraph.Qt import QtGui, QtCore

import nodes


BEAMS = 36
LED_PER_BEAM = 8

VISUALIZE = False

SAMPLE_RATE = 176400

PORT = 50000

VOLUME_MIN_THRESHOLD = 0
VOLUME_FALLOFF = 1.1
VOLUME_DEBUG = 0

FADE_FALLOFF = 256

FIRST_OCTAVE = 3
NUM_OCTAVES = 12

WINDOW_SIZE_SEC = 0.1


def main() -> None:
    ip_address, port = sys.argv[1:3]

    if VISUALIZE:
        app = QtGui.QApplication([])
        window = graph.GraphicsWindow(title="Audio")
        window.resize(1800, 600)
        window.setWindowTitle("Audio")
    else:
        window = None

    audio_input = audio_tools.AudioInput(sample_rate=SAMPLE_RATE)
    audio_input.start()

    samples = audio_input.seconds_to_samples(WINDOW_SIZE_SEC)
    fft_node = nodes.FastFourierTransform(
        "fft", samples=samples, sample_delta=audio_input.sample_delta, window=None
    )

    pipeline = Pipeline(
        nodes.AudioGenerator(
            "mic", audio_input=audio_input, samples=samples, window=window
        )
        | fft_node
        | nodes.AWeighting(
            "a-weighting", frequencies=fft_node.fourier_frequencies, window=None
        )
        | nodes.OctaveSubsampler(
            "sampled",
            start_octave=FIRST_OCTAVE,
            samples_per_octave=BEAMS,
            num_octaves=NUM_OCTAVES,
            frequencies=fft_node.fourier_frequencies,
            window=None,
        )
        | nodes.Gaussian("smoothed", sigma=1.2, window=None)
        | nodes.FoldingNode("folded", num_octaves=NUM_OCTAVES, window=None)
        | nodes.SumMatrixVertical("sum", window=None)
        # | nodes.MaxMatrixVertical("max", window=window)
        | nodes.Normalizer(
            "normalized",
            min_threshold=VOLUME_MIN_THRESHOLD,
            falloff=VOLUME_FALLOFF,
            window=window,
        )
        | nodes.Square("square", window=None)
        | nodes.Logarithm("log", summand=0.3, window=None)
        # | nodes.Fade("fade", falloff=FADE_FALLOFF, window=window)
        | nodes.Shift("clip", minimum=0.14)
        | nodes.Star(
            "ring",
            ip_address=ip_address,
            port=port,
            led_per_beam=LED_PER_BEAM, beams=BEAMS,
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
