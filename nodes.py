import numpy as np
from numpy.fft import rfft as fourier_transform, rfftfreq
from pyPiper import Node, Pipeline


import audio_tools


class AudioGenerator(Node):
    def setup(self, audio_input, samples):
        self._samples = samples
        self._input_device = audio_input
    
    def run(self, data):
        self.emit(
            np.array(
                self._input_device.get_samples(self._samples)
            )
        )


class FastFourierTransform(Node):
    def setup(self, samples, sample_delta):
        self._fourier_frequencies = rfftfreq(
            samples,
            d=sample_delta,
        )

    def run(self, data):
        self.emit(
            (
                self._fourier_frequencies,
                np.absolute(fourier_transform(data)),
            )
        )


class OctaveSubsampler(Node):
    def setup(self, start_octave, samples_per_octave, num_octaves):
        self._sample_points = np.exp2(
            (
                np.arange(samples_per_octave * num_octaves)
                + samples_per_octave * start_octave
            )
            / samples_per_octave
        )
    
    def run(self, data):
        frequencies, values = data
        self.emit(
            (
                self._sample_points,
                np.interp(
                    self._sample_points,
                    frequencies,
                    values,
                ),
            )
        )


class Void(Node):
    def run(self, data):
        pass

audio_input = audio_tools.AudioInput()
audio_input.start()

samples = audio_input.seconds_to_samples(0.05)

pipeline = Pipeline(
    AudioGenerator("mic", audio_input=audio_input, samples=samples)
    | FastFourierTransform("fft", samples=samples, sample_delta=audio_input.sample_delta)
    | OctaveSubsampler("oct", start_octave=4, samples_per_octave=60, num_octaves=8)
    | Void("void")
)
pipeline.run()

