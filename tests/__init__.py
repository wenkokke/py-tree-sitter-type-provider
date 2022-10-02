import inspect
import re
import sys
import typing


def pyver() -> str:
    return f"py{sys.version_info.major}{sys.version_info.minor}"


def short(sig: inspect.Signature) -> str:
    out = str(sig)
    out = re.sub(r"ForwardRef\('([^']+)'\)", r"\1", out)
    out = out.replace("tree_sitter_type_provider.node_types.", "")
    out = out.replace("abc.Talon", "Talon")
    out = re.sub(r"'Talon([^']+)'", r"Talon\1", out)
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


def node_dict_simplify(node_dict: typing.Dict[str, typing.Any]) -> None:
    if len(node_dict) > 4:
        del node_dict["text"]

    del node_dict["start_position"]
    del node_dict["end_position"]

    for key in node_dict.keys():
        if isinstance(node_dict[key], dict):
            node_dict_simplify(node_dict[key])
        if isinstance(node_dict[key], list):
            for val in node_dict[key]:
                if isinstance(val, dict):
                    node_dict_simplify(val)
