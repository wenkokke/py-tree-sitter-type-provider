from collections.abc import Generator
from pathlib import Path
from tree_sitter_type_provider import TreeSitterTypeProvider, NodeType
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
    name = golden["input"]["name"]
    class_prefix = golden["input"]["class_prefix"]
    module_name = f"tree_sitter_{ name }"

    def as_class_name(node_type_name: str) -> str:
        buffer: list[str] = [class_prefix]
        for part in node_type_name.split("_"):
            buffer.append(part.capitalize())
        return "".join(buffer)

    node_types_json = Path(__file__).parent / f"node-types/{ name }.json"
    node_types = NodeType.schema().loads(node_types_json.read_text(), many=True)

    module = TreeSitterTypeProvider(
        module_name, node_types, as_class_name=as_class_name
    )

    output: list[str] = []
    output.extend(function_signatures(module.__class__))
    output.extend(function_signatures(module))
    output.extend(class_signatures(module.__class__))
    output.extend(class_signatures(module))

    assert "\n".join(output) == golden.out["output"]
