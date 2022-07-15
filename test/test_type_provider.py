import itertools
from pathlib import Path
from typing import Generator, List
from tree_sitter_type_provider import TreeSitterTypeProvider
from tree_sitter_type_provider.node_types import *
import pytest
import inspect


def function_signatures(object: object) -> Generator[str, None, None]:
    for name, fun in inspect.getmembers(object, inspect.isfunction):
        if not name.startswith("_"):
            yield f"{name}{inspect.signature(fun)}"


def class_signatures(object: object) -> Generator[str, None, None]:
    for name, cls in inspect.getmembers(object, inspect.isclass):
        if not name.startswith("_"):
            yield f"{name}{inspect.signature(cls)}"
            for sig in function_signatures(cls):
                yield f"  {sig}"


@pytest.mark.golden_test("golden/*.yml")
def test_talon(golden):
    node_types_json = Path(__file__).parent / f"node-types/{ golden['input'] }.json"
    node_types = NodeType.schema().loads(node_types_json.read_text(), many=True)
    talon = TreeSitterTypeProvider("talon", node_types)

    output: List[str] = []
    output.extend(function_signatures(talon.__class__))
    output.extend(function_signatures(talon))
    output.extend(class_signatures(talon.__class__))
    output.extend(class_signatures(talon))

    assert "\n".join(output) == golden.out["output"]
