from audioviz.computations import Benchmarker
import typing as t
import sys
import os

from airpixel import client as air_client
import click

from audioviz import audio_tools, computations


BEAMS = 36
LED_PER_BEAM = 8

VISUALIZE = bool(os.environ.get("VISUALIZE", False))

SAMPLE_RATE = 22050

PORT = 50000

VOLUME_MIN_THRESHOLD = 0
VOLUME_FALLOFF = 1.1
VOLUME_DEBUG = 0

FADE_FALLOFF = 32

FIRST_OCTAVE = 8
NUM_OCTAVES = 6

WINDOW_SIZE_SEC = 0.05


def make_computation(ip_address: str, port: int):
    mon_client = air_client.MonitorClient("monitoring_uds")

    audio_input = audio_tools.AudioInput(sample_rate=SAMPLE_RATE)
    audio_input.start()

    sample_count = computations.Constant(
        audio_input.seconds_to_samples(WINDOW_SIZE_SEC)
    )
    sample_delta = computations.Constant(audio_input.sample_delta)
    lowest_note = computations.Constant(6.02236781303)
    highest_note = computations.Constant(11.0313565963)
    beam_count = computations.Constant(36)
    half_beam_count = computations.Constant(18)
    leds_per_beam = computations.Constant(8)

    fft_frequencies = computations.FastFourierTransformFrequencies(
        sample_count, sample_delta
    )

    return computations.Star(
        computations.Roll(
            computations.Mirror(
                computations.VolumeNormalizer(
                    computations.Resample(
                        computations.Log2(fft_frequencies),
                        computations.Multiply(
                            computations.AWeightingVector(fft_frequencies),
                            computations.FastFourierTransform(
                                computations.Multiply(
                                    computations.AudioSource(audio_input, sample_count),
                                    computations.HammingWindow(sample_count),
                                ),
                                sample_delta,
                            ),
                        ),
                        computations.Linspace(
                            lowest_note, highest_note, half_beam_count
                        ),
                    ),
                )
            ),
            computations.Constant(16),
        ),
        leds_per_beam,
        beam_count,
        ip_address,
        port,
    )


@click.command()
@click.argument("ip_address", required=True)
@click.argument("port", required=True, type=int)
@click.option("--graph", is_flag=True)
@click.option("--benchmark", is_flag=True)
def main(ip_address:str, port: int, graph: bool, benchmark: bool) -> None:
    comp = make_computation(ip_address, port)

    if graph or benchmark:
        from audioviz import computation_graph
        print(computation_graph.make_graph(comp, benchmark))
        return

    while True:
        comp.value()
        comp.clean()


if __name__ == "__main__":
    main()
