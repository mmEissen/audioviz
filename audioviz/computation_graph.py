from audioviz.computations import computation
import collections

import graphviz

from audioviz import computations


def name(node: computations.Computation) -> str:
    return str(id(node))


def run_n_loops(computation: computations.Computation, n: int=1000):
    for _ in range(n):
        computation.value()
        computation.clean()


def make_graph(computation: computations.Computation, benchmark: bool = False) -> None:
    if benchmark:
        computation.set_benchmark(True)
        run_n_loops(computation)

    digraph = graphviz.Digraph(name="Computations", graph_attr={"splines": "ortho",})

    todo = collections.deque([computation])
    visited = set()

    while todo:
        node = todo.pop()
        if name(node) in visited:
            continue
        visited.add(name(node))
        fillcolor = "white" if node.is_constant() else "yellow"
        if benchmark:
            label = f"{str(node)}\nt={node.benchmark.average() * 1000:.2f}ms"
        else:
            label = str(node)

        digraph.node(
            name(node),
            label=label,
            shape="rectangle",
            fillcolor=fillcolor,
            style="filled",
        )

        for child in node.inputs():
            todo.append(child)
            digraph.edge(name(child), name(node))
    
    computation.set_benchmark(False)

    return digraph.source
