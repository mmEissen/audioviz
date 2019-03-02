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
        | nodes.Gaussian("smoothed", sigma=1, window=None)
        | nodes.OctaveSubsampler(
            "sampled",
            start_octave=5,
            samples_per_octave=config.NUM_LEDS,
            num_octaves=config.NUM_OCTAVES,
            frequencies=fft_node.fourier_frequencies,
            window=None,
        )
        | nodes.FoldingNode("folded", num_octaves=config.NUM_OCTAVES, window=None)
        | nodes.SumMatrixVertical("sum", window=None)
        | nodes.Square("square", window=None)
        # | MaxMatrixVertical("max", window=window)
        | nodes.NaturalLogarithm("log", window=None)
        | nodes.Normalizer(
            "normalized",
            min_threshold=config.VOLUME_MIN_THRESHOLD,
            falloff=config.VOLUME_FALLOFF,
            window=window,
        )
        | nodes.Fade("fade", falloff=config.FADE_FALLOFF, window=window)
        | nodes.Ring(
            "ring",
            port=config.PORT,
            num_leds=config.NUM_LEDS,
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
