import numpy as np
from numpy.fft import rfft as fourier_transform, rfftfreq
from pyPiper import Node, Pipeline

import threading

import audio_tools

import a_weighting_table

from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as graph



class PlottableNode(Node):
    def setup(self, window):
        if window is None:
            self.plot = self._no_plot
            return
        self.setup_plot(window)

    def setup_plot(self, window):
        window.nextRow()
        self._plot = window.addPlot(title=self.name)
        self._curve = self._plot.plot(pen="y")

    def _no_plot(self, data):
        pass

    def plot(self, data):
        if isinstance(data, tuple):
            self._curve.setData(*data)
        else:
            self._curve.setData(data)

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
        self._fourier_frequencies = rfftfreq(
            samples,
            d=sample_delta,
        )
    
    def setup_plot(self, window):
        super().setup_plot(window)
        self._plot.setLogMode(x=True, y=False)
        self._plot.setRange(yRange=(0, 2e11))

    def run(self, data):
        self.emit(
            (
                self._fourier_frequencies,
                np.absolute(fourier_transform(data)),
            )
        )


class OctaveSubsampler(PlottableNode):
    def setup(self, start_octave, samples_per_octave, num_octaves, window=None):
        super().setup(window)
        self._sample_points = np.exp2(
            (
                np.arange(samples_per_octave * num_octaves)
                + samples_per_octave * start_octave
            )
            / samples_per_octave
        )
    
    def setup_plot(self, window):
        super().setup_plot(window)
        self._plot.setLogMode(x=True, y=False)
        self._plot.setRange(yRange=(0, 2e22))
    
    def run(self, data):
        frequencies, values = data
        self.emit(
            (
                self._sample_points,
                np.interp(
                    self._sample_points,
                    frequencies,
                    values,
                    left=0,
                    right=0,
                ) ** 2,
            )
        )


class AWeighting(PlottableNode):
    def setup(self, window=None):
        super().setup(window)

    def setup_plot(self, window):
        super().setup_plot(window)
        self._plot.setLogMode(x=True, y=False)
        self._plot.setRange(yRange=(0, 1e22))

    def run(self, data):
        frequencies, values = data
        weights = np.interp(
            frequencies,
            a_weighting_table.frequencies,
            a_weighting_table.weights,
        )
        self.emit(
            (
                frequencies,
                values * weights,
            )
        )


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


audio_input = audio_tools.AudioInput()
audio_input.start()

samples = audio_input.seconds_to_samples(0.03)

pipeline = Pipeline(
    AudioGenerator("mic", audio_input=audio_input, samples=samples, window=window)
    | FastFourierTransform("fft", samples=samples, sample_delta=audio_input.sample_delta, window=window)
    | OctaveSubsampler("oct", start_octave=6, samples_per_octave=60, num_octaves=7, window=window)
    | AWeighting("a-weighting", window=window)
    | Void("void")
)

audio_pipeline = threading.Thread(
    target=pipeline.run,
    daemon=True,
)
audio_pipeline.start()

QtGui.QApplication.instance().exec_()

