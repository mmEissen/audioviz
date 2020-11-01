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

    return digraph.source
