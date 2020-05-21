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


def main() -> None:
    ip_address, port = sys.argv[1:3]

    if config.VISUALIZE:
        app = QtGui.QApplication([])
        window = graph.GraphicsWindow(title="Audio")
        window.resize(1800, 600)
        window.setWindowTitle("Audio")
    else:
        window = None

    audio_input = audio_tools.AudioInput(sample_rate=config.SAMPLE_RATE)
    audio_input.start()

    samples = audio_input.seconds_to_samples(config.WINDOW_SIZE_SEC)
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
            start_octave=config.FIRST_OCTAVE,
            samples_per_octave=config.NUM_LEDS,
            num_octaves=config.NUM_OCTAVES,
            frequencies=fft_node.fourier_frequencies,
            window=None,
        )
        | nodes.Gaussian("smoothed", sigma=1.2, window=None)
        | nodes.FoldingNode("folded", num_octaves=config.NUM_OCTAVES, window=None)
        | nodes.SumMatrixVertical("sum", window=None)
        # | nodes.MaxMatrixVertical("max", window=window)
        | nodes.Normalizer(
            "normalized",
            min_threshold=config.VOLUME_MIN_THRESHOLD,
            falloff=config.VOLUME_FALLOFF,
            window=window,
        )
        | nodes.Square("square", window=None)
        | nodes.Logarithm("log", summand=0.3, window=None)
        # | nodes.Fade("fade", falloff=config.FADE_FALLOFF, window=window)
        | nodes.Shift("clip", minimum=0.14)
        | nodes.Ring(
            "ring",
            ip_address=ip_address,
            port=port,
            color_rotation_period=config.COLOR_RATATION_PERIOD,
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
