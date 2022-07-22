from __future__ import annotations
from collections.abc import Generator
from pathlib import Path
from tree_sitter_type_provider import *
import tree_sitter_type_provider.node_types as nt
import pytest
import inspect
import typing
import re

Context: typing.TypeAlias = typing.Union[None, typing.Mapping[str, typing.Any]]


def short(sig: inspect.Signature) -> str:
    out = str(sig)
    out = out.replace("tree_sitter_type_provider.node_types.", "")
    out = re.sub(r"ForwardRef\('(\w+)'\)", r"\1", out)
    out = out.replace("typing.", "")
    out = out.replace("NoneType", "None")
    out = out.replace("abc.", "")
    out = out.replace("~Result", "Result")
    return out


def function_signatures(
    object: object, ctx: Context = None
) -> Generator[str, None, None]:
    for name, fun in inspect.getmembers(object, inspect.isfunction):
        if not (name.startswith("_") or name in ["to_dict", "to_json"]):
            try:
                funsig = inspect.signature(fun, globals=ctx, eval_str=True)
                yield f"{name}{short(funsig)}"
            except ValueError:
                pass


def class_signatures(object: object, ctx: Context = None) -> Generator[str, None, None]:
    for name, cls in inspect.getmembers(object, inspect.isclass):
        if not name.startswith("_"):
            try:
                clssig = inspect.signature(cls, globals=ctx, eval_str=True)
                yield f"{name}{short(clssig)}"
                for funsigstr in function_signatures(cls, ctx=ctx):
                    yield f"  {funsigstr}"
            except ValueError:
                pass


@pytest.mark.golden_test("golden/*.yml")
def test_talon(golden):
    class_prefix = golden["input"]["class_prefix"]
    module_name = f"tree_sitter_{ golden['input']['name'] }"

    def as_class_name(node_type_name: str) -> str:
        buffer: list[str] = [class_prefix]
        for part in node_type_name.split("_"):
            buffer.append(part.capitalize())
        return "".join(buffer)

    node_types_json = Path(__file__).parent / golden['input']['file']
    node_types = NodeType.schema().loads(node_types_json.read_text(), many=True)

    module = TreeSitterTypeProvider(
        module_name, node_types, error_as_node=True, as_class_name=as_class_name, extra=golden["input"]["extra"]
    )

    ctx: Context = globals() | module.__dict__

    output: list[str] = []
    output.extend(function_signatures(module.__class__, ctx=ctx))
    output.extend(function_signatures(module, ctx=ctx))
    output.extend(class_signatures(module.__class__, ctx=ctx))
    output.extend(class_signatures(module, ctx=ctx))

    assert "\n".join(output) == golden.out["output"]
