import time
import typing as t

import click

from audioviz import audio_tools, computations, star


CALIBRATION_SAMPLES = 100
CALIBRATION_FACTOR = 1.5


def make_computation():
    audio_input = audio_tools.AudioInput(sample_rate=star.SAMPLE_RATE)
    audio_input.start()
    sample_count = computations.Constant(
        audio_input.seconds_to_samples(star.WINDOW_SIZE_SEC)
    )
    return computations.Maximum(computations.AudioSource(audio_input, sample_count))


def get_value(computation):
    value = computation.volatile_value()
    time.sleep(2 * star.WINDOW_SIZE_SEC)
    return value


@click.command()
def main() -> None:
    comp = make_computation()

    max_value = max(get_value(comp) for _ in range(CALIBRATION_SAMPLES))

    with open(star.CALIBRATION_FILE, "w") as calibration_file:
        calibration_file.write(str(max_value * CALIBRATION_FACTOR))


if __name__ == "__main__":
    main()
