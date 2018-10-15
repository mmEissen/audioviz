import typing as t
import sys
import os

import audio_tools
import config
import ring_client
import profiler
from effects import CircularFourierEffect

if config.MOCK_RING or config.MOCK_AUDIO:
    from PyQt5.QtWidgets import QApplication
    import qt5_client


def qtmock_client_and_wait():
    application = QApplication(sys.argv)
    client = qt5_client.Qt5RingClient(config.NUM_LEDS)
    return client, application.exec_


def client_and_wait():
    print(__file__)
    client = ring_client.RingClient(config.PORT, config.NUM_LEDS)

    def wait() -> int:
        input()
        return 0

    return client, wait


def main() -> None:
    if config.MOCK_RING:
        client, wait = qtmock_client_and_wait()
    else:
        client, wait = client_and_wait()

    if config.MOCK_AUDIO:
        audio_input: audio_tools.AbstractAudioInput = qt5_client.MockSinInput()
    else:
        audio_input = audio_tools.AudioInput()

    profiling_thread = profiler.ProfilingTread()
    profiler.Profiler.enabled = config.PROFILING_ENABLED
    if config.PROFILING_ENABLED:
        profiling_thread.start()

    render_func = CircularFourierEffect(audio_input, client)

    loop = ring_client.RenderLoop(client, render_func)
    loop.start()

    return_code = wait()

    loop.stop()
    profiling_thread.stop()
    sys.exit(return_code)


if __name__ == "__main__":
    main()
