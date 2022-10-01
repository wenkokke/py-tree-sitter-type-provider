import inspect
import pathlib
import re
import typing

import pytest

import tree_sitter_type_provider


def short(sig: inspect.Signature) -> str:
    out = str(sig)
    out = out.replace("tree_sitter_type_provider.node_types.", "")
    out = re.sub(r"ForwardRef\('(\w+)'\)", r"\1", out)
    out = out.replace("typing.", "")
    out = re.sub(r"Optional\[([^\]]+)\]", r"Union[\1, None]", out)
    out = out.replace("NoneType", "None")
    out = out.replace("abc.", "")
    out = out.replace("~Result", "Result")
    return out


def function_signatures(object: object) -> typing.Iterator[str]:
    for name, fun in inspect.getmembers(object, inspect.isfunction):
        if not (name.startswith("_") or name in ["to_dict", "to_json"]):
            try:
                funsig = inspect.signature(fun)
                yield f"{name}{short(funsig)}"
            except ValueError:
                pass


def class_signatures(object: object) -> typing.Iterator[str]:
    for name, cls in inspect.getmembers(object, inspect.isclass):
        if not name.startswith("_"):
            try:
                clssig = inspect.signature(cls)
                yield f"{name}{short(clssig)}"
                for funsigstr in function_signatures(cls):
                    yield f"  {funsigstr}"
            except ValueError:
                pass


@pytest.mark.golden_test("data/golden/api/*.yml")
def test_talon(golden):
    class_prefix = golden["input"]["class_prefix"]
    module_name = f"tree_sitter_{ golden['input']['name'] }"

    def as_class_name(node_type_name: str) -> str:
        buffer: typing.List[str] = [class_prefix]
        for part in node_type_name.split("_"):
            buffer.append(part.capitalize())
        return "".join(buffer)

    node_types_json = pathlib.Path(__file__).parent / golden["input"]["file"]
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

    output: typing.List[str] = []
    output.extend(function_signatures(module.__class__))
    output.extend(function_signatures(module))
    output.extend(class_signatures(module.__class__))
    output.extend(class_signatures(module))

    assert "\n".join(output) == golden.out["output"]
