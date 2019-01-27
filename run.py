import typing as t
import time
import sys
import os

import audio_tools
import config
import effects
from airpixel import client as air_client

if config.MOCK_RING:
    from airpixel import qt5_client


def client_and_wait():
    print(__file__)
    client = air_client.AirClient(config.PORT, config.PORT + 1, config.NUM_LEDS)

    return client, watch_threads


def watch_threads(loop_threads):
    try:
        print("Press Ctrl-C to stop")
        while True:
            time.sleep(0.1)
            if not all(thread.is_alive() for thread in loop_threads):
                print("A thread crashed! Quitting.")
                break
    except (KeyboardInterrupt, SystemExit):
        print("Quitting gracefully...")
    finally:
        for thread in loop_threads:
            thread.stop()
        return 0


def main() -> None:
    client, wait = client_and_wait()

    audio_input = audio_tools.AudioInput()
    audio_input.start()

    volume_normalizer = effects.ContiniuousVolumeNormalizer(
        config.VOLUME_MIN_THRESHOLD,
        config.VOLUME_FALLOFF,
        config.VOLUME_DEBUG,
    )
    render_func = effects.FadingCircularEffect(
        audio_input,
        client,
        volume_normalizer,
        window_size=config.WINDOW_SIZE_SEC,
        first_octave=config.FIRST_OCTAVE,
        number_octaves=config.NUMBER_OCTAVES,
        falloff=config.FADE_FALLOFF,
        color_rotation_period=config.COLOR_RATATION_PERIOD,
    )

    loop = air_client.RenderLoop(client, render_func)
    loop.start()

    return_code = wait([loop, audio_input])

    sys.exit(return_code)


if __name__ == "__main__":
    main()
