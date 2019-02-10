import numpy as np
from numpy.fft import rfft as fourier_transform, rfftfreq
from pyPiper import Node, Pipeline

import threading

import audio_tools


from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as graph

#QtGui.QApplication.setGraphicsSystem('raster')
app = QtGui.QApplication([])
#mw = QtGui.QMainWindow()
#mw.resize(800,800)

window = graph.GraphicsWindow(title="Audio")
window.resize(1000,600)
window.setWindowTitle("Audio")

# Enable antialiasing for prettier plots
graph.setConfigOptions(antialias=True)



class AudioGenerator(Node):
    def setup(self, audio_input, samples, window):
        self._samples = samples
        self._input_device = audio_input
        self._plot = window.addPlot(title=self.name)
        self._curve = self._plot.plot(pen="y")
    
    def run(self, data):
        samples = np.array(
            self._input_device.get_samples(self._samples)
        )
        self._curve.setData(samples)
        self.emit(samples)


class FastFourierTransform(Node):
    def setup(self, samples, sample_delta):
        self._fourier_frequencies = rfftfreq(
            samples,
            d=sample_delta,
        )
        self._plot = window.addPlot(title=self.name)
        self._curve = self._plot.plot(pen="y")
        self._plot.setRange(yRange=(0, 10**11))

    def run(self, data):
        transform = np.absolute(fourier_transform(data))
        self._curve.setData(transform[1:])
        self.emit(
            (
                self._fourier_frequencies,
                transform,
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
    AudioGenerator("mic", audio_input=audio_input, samples=samples, window=window)
    | FastFourierTransform("fft", samples=samples, sample_delta=audio_input.sample_delta)
    | OctaveSubsampler("oct", start_octave=4, samples_per_octave=60, num_octaves=8)
    | Void("void")
)

audio_pipeline = threading.Thread(
    target=pipeline.run,
    daemon=True,
)
audio_pipeline.start()

QtGui.QApplication.instance().exec_()

