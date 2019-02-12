import time
import threading

import numpy as np
import pyqtgraph as graph
from numpy.fft import rfft as fourier_transform, rfftfreq
from pyPiper import Node, Pipeline
from pyqtgraph.Qt import QtGui, QtCore
from scipy import ndimage

import a_weighting_table
import audio_tools


class ContiniuousVolumeNormalizer:
    def __init__(self, min_threshold=0, falloff=8) -> None:
        self._min_threshold = min_threshold
        self._falloff = falloff
        self._current_threshold = self._min_threshold
        self._last_call = 0

    def _update_threshold(self, max_sample, timestamp):
        if max_sample >= self._current_threshold:
            self._current_threshold = max_sample
        else:
            target_threshold = max_sample
            factor = 1 / self._falloff ** (timestamp - self._last_call)
            self._current_threshold = self._current_threshold * factor + target_threshold * (
                1 - factor
            )
        self._last_call = timestamp

    def normalize(self, signal, timestamp):
        if self._last_call == 0:
            self._last_call = timestamp
        max_sample = np.max(np.abs(signal))
        self._update_threshold(max_sample, timestamp)
        if self._current_threshold >= self._min_threshold:
            return signal / self._current_threshold
        return signal * 0


class PlottableNode(Node):
    def setup(self, window=None):
        if window is None:
            self.plot = self._no_plot
            return
        self._current_max_y = 0
        self.setup_plot(window)

    def setup_plot(self, window):
        window.nextRow()
        self._plot = window.addPlot(title=self.name)
        self._curve = self._plot.plot(pen="y")

    def _no_plot(self, data):
        pass

    def _fit_plot(self, points):
        self._current_max_y = max(max(points), self._current_max_y)
        self._plot.setRange(yRange=(0, self._current_max_y))

    def plot(self, data):
        if isinstance(data, tuple):
            _, points = data
            self._curve.setData(*data)
        else:
            points = data
            self._curve.setData(data)
        self._fit_plot(points)

    def emit(self, data):
        self.plot(data)
        return super().emit(data)


class AudioGenerator(PlottableNode):
    def setup(self, audio_input, samples, window=None):
        super().setup(window)
        self._samples = samples
        self._input_device = audio_input
    
    def run(self, data):
        samples = np.array(
            self._input_device.get_samples(self._samples)
        )
        self.emit(samples)


class FastFourierTransform(PlottableNode):
    def setup(self, samples, sample_delta, window=None):
        super().setup(window)
        self.sample_delta = sample_delta
        self.fourier_frequencies = rfftfreq(
            samples,
            d=sample_delta,
        )

    def run(self, data):
        self.emit(
            np.absolute(fourier_transform(data) * self.sample_delta)
        )


class OctaveSubsampler(PlottableNode):
    def setup(self, start_octave, samples_per_octave, num_octaves, frequencies, window=None):
        super().setup(window)
        self._sample_points = np.exp2(
            (
                np.arange(samples_per_octave * num_octaves)
                + samples_per_octave * start_octave
            )
            / samples_per_octave
        )
        self.frequencies = frequencies

    def run(self, data):
        self.emit(
            np.interp(
                self._sample_points,
                self.frequencies,
                data,
                left=0,
                right=0,
            )
        )


class AWeighting(PlottableNode):
    def setup(self, frequencies, window=None):
        self.weights = np.interp(
            frequencies,
            a_weighting_table.frequencies,
            a_weighting_table.weights,
        )
        super().setup(window)

    def setup_plot(self, window):
        super().setup_plot(window)
        self._plot.setLogMode(x=True, y=False)

    def run(self, data):
        self.emit(
            data * self.weights,
        )


class Gaussian(PlottableNode):
    def setup(self, sigma, window=None):
        self._sigma = sigma
        super().setup(window)
    
    def setup_plot(self, window):
        super().setup_plot(window)
        self._plot.setLogMode(x=True, y=False)

    def run(self, data):
        self.emit(
            ndimage.gaussian_filter(data, sigma=self._sigma),
        )


class Square(PlottableNode):
    def run(self, data):
        self.emit(
            data ** 2,
        )

class FoldingNode(PlottableNode):
    def setup(self, num_octaves, window=None):
        self._num_octaves = num_octaves
        super().setup(window)

    def setup_plot(self, window):
        window.nextRow()
        self._plot = window.addPlot(title=self.name)
        self._curves = [
            self._plot.plot(pen=(i / self._num_octaves * 255, (1 - i / self._num_octaves) * 255, 255))
            for i in range(self._num_octaves)
        ]
    
    def plot(self, data):
        for sub_data, curve in zip(data, self._curves):
            curve.setData(sub_data)
            self._fit_plot(sub_data)

    def run(self, data):
        wrapped = np.reshape(data, (self._num_octaves, -1))
        self.emit(wrapped)


class SumMatrixVertical(PlottableNode):
    def run(self, data):
        self.emit(
            np.add.reduce(data),
        )


class NaturalLogarithm(PlottableNode):
    def run(self, data):
        self.emit(np.log(data + 1))


class Normalizer(PlottableNode):
    def setup(self, window=None):
        super().setup(window=window)
        self.normalizer = ContiniuousVolumeNormalizer()
    
    def run(self, data):
        self.emit(self.normalizer.normalize(data, time.time()))


class Void(Node):
    def run(self, data):
        pass



#QtGui.QApplication.setGraphicsSystem('raster')
app = QtGui.QApplication([])
#mw = QtGui.QMainWindow()
#mw.resize(800,800)

window = graph.GraphicsWindow(title="Audio")
window.resize(1800,600)
window.setWindowTitle("Audio")

# Enable antialiasing for prettier plots
graph.setConfigOptions(antialias=True)


audio_input = audio_tools.AudioInput(sample_rate=176400)
audio_input.start()

samples = audio_input.seconds_to_samples(0.1)
octaves = 8

fft_node = FastFourierTransform("fft", samples=samples, sample_delta=audio_input.sample_delta, window=None)

pipeline = Pipeline(
    AudioGenerator("mic", audio_input=audio_input, samples=samples, window=window)
    | fft_node
    | AWeighting("a-weighting", frequencies=fft_node.fourier_frequencies, window=None)
    | Square("square", window=None)
    | NaturalLogarithm("log", window=None)
    | Gaussian("smoothed", sigma=1, window=None)
    | OctaveSubsampler("sampled", start_octave=5, samples_per_octave=60, num_octaves=octaves, frequencies=fft_node.fourier_frequencies, window=None)
    | FoldingNode("folded", num_octaves=octaves, window=None)
    | SumMatrixVertical("sum", window=window)
    | Normalizer("normalized", window=window)
    | Void("void")
)

audio_pipeline = threading.Thread(
    target=pipeline.run,
    daemon=True,
)
audio_pipeline.start()

QtGui.QApplication.instance().exec_()

