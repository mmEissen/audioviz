from audioviz.computations import computation
import collections

import graphviz

from audioviz import computations


def name(node: computations.Computation) -> str:
    return str(id(node))


def make_graph(computation: computations.Computation) -> None:
    digraph = graphviz.Digraph(name="Computations", graph_attr={"splines": "ortho",})

    todo = collections.deque([computation])
    visited = set()

    while todo:
        node = todo.pop()
        if name(node) in visited:
            continue
        visited.add(name(node))
        fillcolor = "white" if node.is_constant() else "yellow"
        digraph.node(
            name(node),
            label=str(node),
            shape="rectangle",
            fillcolor=fillcolor,
            style="filled",
        )

        for child in node.inputs():
            todo.append(child)
            digraph.edge(name(child), name(node))

    print(digraph.source)


if __name__ == "__main__":
    resample_notes = computations.Constant(
        None
    )  # np.linspace(lowest note, highest note number of beams / 2)
    sample_count = computations.Constant(200)
    sample_delta = computations.Constant(0.02)
    fft_frequencies = computations.FastFourierTransformFrequencies(
        sample_count, sample_delta
    )

    comp = computations.Roll(
        computations.Mirror(
            computations.Resample(
                computations.Log2(fft_frequencies),
                computations.Multiply(
                    computations.AWeightingVector(fft_frequencies),
                    computations.FastFourierTransform(
                        computations.Multiply(
                            computations.HammingWindow(sample_count),
                            computations.AudioSource(None, sample_count),
                        ),
                        sample_delta,
                    ),
                ),
                resample_notes,
            ),
            computations.Constant(True),
        ),
        computations.Constant(16),
    )
    make_graph(comp)
