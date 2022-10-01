# Type Providers for Tree Sitter

[![GitHub Workflow Status](https://github.com/wenkokke/py-tree-sitter-type-provider/actions/workflows/build.yml/badge.svg)](https://github.com/wenkokke/py-tree-sitter-talon/actions/workflows/build.yml) ![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/wenkokke/py-tree-sitter-type-provider) ![PyPI](https://img.shields.io/pypi/v/tree-sitter-type-provider)

Create a type AST from any `node-types.json` file, as well as a generic visitor class and a transformer class, and a function to convert to the AST from the `tree_sitter.Node` type.

For example, the following code defines a module named `tree_sitter_javascript` from `tree-sitter-javascript/src/nodes.json`:

```python
import pathlib
import tree_sitter_type_provider as tstp

node_types_json = pathlib.Path("tree-sitter-javascript/src/node-types.json")
node_types = tstp.NodeType.schema().loads(node_types_json.read_text(), many=True)

def as_class_name(node_type_name: str) -> str:
    class_name_parts: typing.List[str] = ["Js"]
    for part in node_type_name.split("_"):
        class_name_parts.append(part.capitalize())
    return "".join(class_name_parts)

sys.modules[__name__] = tstp.TreeSitterTypeProvider(
    "tree_sitter_javascript",
    node_types,
    error_as_node=True,          # Include ERROR as a node in the AST
    as_class_name=as_class_name, # How to convert node types to Python class names
    extra=["comment"],           # Nodes which are marked as 'extra' in the grammar
)
```

The module contains a number of dataclasses which represent the AST nodes:

```python
import tree_sitter as ts
import tree_sitter_type_provider as tstp
import typing

@dataclass
class JsArray(tstp.Node):
    text: str
    type_name: str
    start_position: tstp.Point
    end_position: tstp.Point
    children: typing.List[typing.Union[JsExpression, JsSpreadElement]]

@dataclass
class JsDeclaration(tstp.Node):
    text: str
    type_name: str
    start_position: tstp.Point
    end_position: tstp.Point

@dataclass
class JsWhileStatement(tstp.Node):
    text: str
    type_name: str
    start_position: tstp.Point
    end_position: tstp.Point
    body: JsStatement
    condition: JsParenthesizedExpression

...
```

As well as a function to convert to the AST:

```python
def from_tree_sitter(self, tsvalue: typing.Union[ts.Tree, ts.Node, ts.TreeCursor], *, encoding: str = 'utf-8') -> tstp.Node
```
