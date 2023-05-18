from pathlib import Path
from typing import Any, List

import pytest
from pytest_golden.plugin import GoldenTestFixture

import tree_sitter_type_provider
from tests import class_signatures, function_signatures, pyver


@pytest.mark.golden_test(f"data/golden/api/*.{pyver()}.yml")  # type: ignore[misc]
def test_talon(golden: GoldenTestFixture) -> None:
    class_prefix = golden["input"]["class_prefix"]
    module_name = f"tree_sitter_{ golden['input']['name'] }"

    def as_class_name(node_type_name: str) -> str:
        buffer: List[str] = [class_prefix]
        for part in node_type_name.split("_"):
            buffer.append(part.capitalize())
        return "".join(buffer)

    node_types_json = Path(__file__).parent / str(golden["input"]["file"])
    node_types = tree_sitter_type_provider.NodeType.schema().loads(
        node_types_json.read_text(), many=True
    )

    module = tree_sitter_type_provider.TreeSitterTypeProvider(
        module_name,
        node_types,
        as_class_name=as_class_name,
        extra=golden["input"]["extra"],
    )

    globals().update(module.__dict__)

    output: List[str] = []
    output.extend(function_signatures(module.__class__))
    output.extend(function_signatures(module))
    output.extend(class_signatures(module.__class__))
    output.extend(class_signatures(module))

    assert "\n".join(output) == golden.out["output"]
