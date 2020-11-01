import collections

import graphviz

from audioviz import computations


def name(node: computations.Computation) -> str:
    return str(id(node))


def make_graph(computation: computations.Computation) -> None:
    digraph = graphviz.Digraph(name="Computations", graph_attr={"splines": "ortho",})

    todo = collections.deque([computation])

    while todo:
        node = todo.pop()
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
    sample_count = computations.Constant(200)
    sample_delta = computations.Constant(0.02)
    comp = computations.Multiply(
        computations.AWeightingVector(
            computations.FastFourierTransformFrequencies(sample_count, sample_delta)
        ),
        computations.FastFourierTransform(
            computations.Multiply(
                computations.HammingWindow(sample_count),
                computations.AudioSource(None, sample_count),
            ),
            sample_delta,
        ),
    )
    make_graph(comp)
