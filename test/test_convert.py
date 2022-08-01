import pathlib
import sys
import typing

import pytest
import tree_sitter as ts

import tree_sitter_type_provider as tstp


def node_dict_simplify(node_dict: dict[str, typing.Any]) -> None:
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


TESTDIR = pathlib.Path(__file__).parent


@pytest.mark.golden_test("golden/convert/*.yml")
def test_talon(golden):
    class_prefix = golden["input"]["class_prefix"]
    module_name = f"tree_sitter_{ golden['input']['name'] }"

    def as_class_name(node_type_name: str) -> str:
        buffer: list[str] = [class_prefix]
        for part in node_type_name.split("_"):
            buffer.append(part.capitalize())
        return "".join(buffer)

    node_types_json = TESTDIR / golden["input"]["node_types"]
    node_types = tstp.NodeType.schema().loads(node_types_json.read_text(), many=True)

    repository_path = str(TESTDIR / golden["input"]["repository_path"])
    library_name = {
        "linux": f"{ module_name }.so",
        "darwin": f"{ module_name }.dylib",
        "win32": f"{ module_name }.dll",
    }[sys.platform]
    library_path = str(TESTDIR / library_name)
    ts.Language.build_library(library_path, [repository_path])

    language = ts.Language(library_path, golden["input"]["name"])
    parser = ts.Parser()
    parser.set_language(language)

    types = tstp.TreeSitterTypeProvider(
        module_name,
        node_types,
        error_as_node=True,
        as_class_name=as_class_name,
        extra=golden["input"]["extra"],
    )

    contents = golden["input"]["contents"]
    tree = parser.parse(bytes(contents, encoding="utf-8"))
    node = types.from_tree_sitter(tree.root_node)
    node_dict = node.to_dict()
    node_dict_simplify(node_dict)

    assert node_dict == golden.out["output"]
