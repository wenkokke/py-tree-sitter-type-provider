# Type Providers for Tree Sitter

![GitHub Workflow Status](https://img.shields.io/github/workflow/status/wenkokke/py-tree-sitter-type-provider/CI) ![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/wenkokke/py-tree-sitter-type-provider)

Create a type AST from any `node-types.json` file, as well as a generic visitor class and a transformer class, and a function to convert to the AST from the `tree_sitter.Node` type.

For example, the following code defines a module named `tree_sitter_javascript` from `tree-sitter-javascript/src/nodes.json`:

```python
from pathlib import Path
import tree_sitter_type_provider as tstp

node_types_json = Path("tree-sitter-javascript/src/node-types.json")
node_types = tstp.NodeType.schema().loads(node_types_json.read_text(), many=True)

def as_class_name(node_type_name: str) -> str:
    class_name_parts: list[str] = ["Js"]
    for part in node_type_name.split("_"):
        class_name_parts.append(part.capitalize())
    return "".join(class_name_parts)


sys.modules[__name__] = tstp.TreeSitterTypeProvider(
    "tree_sitter_javascript", node_types, as_class_name=as_class_name
)
```

The module contains a number of dataclasses which represent the AST nodes:

```python
import tree_sitter as ts
import tree_sitter_type_provider as tstp

@dataclass
class JsArray(tstp.Node):
    text: str
    type_name: str
    start_position: tstp.Point
    end_position: tstp.Point
    children: list[Union[JsExpression, JsSpreadElement]]

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

As well as generic visitor and transformer classes:

```python
Result = TypeVar("Result")

class NodeTransformer:
    transform(self, node: tstp.Node) -> Result
    transform_ERROR(self, *, text: str, type_name: str, start_position: tstp.Point, end_position: tstp.Point, **kwargs: dict[str, Any]) -> Result
    transform_JsArray(self, *, text: str, type_name: str, start_position: tstp.Point, end_position: tstp.Point, **kwargs: dict[str, Any]) -> Result
    # NOTE: no transform_JsDeclaration: it's not a concrete node type, but a superclass for several node types
    transform_JsWhileStatement(self, *, text: str, type_name: str, start_position: tstp.Point, end_position: tstp.Point, **kwargs: dict[str, Any]) -> Result
    ...

class NodeVisitor:
    generic_visit(self, node: tstp.Node) -> None
    visit(self, node: tstp.Node) -> None
    visit_ERROR(self, node: tstp.Node) -> None
    visit_JsArray(self, node: tstp.Node) -> None
    # NOTE: no visit_JsDeclaration: it's not a concrete node type, but a superclass for several node types
    visit_JsWhileStatement(self, node: tstp.Node) -> None
    ...
```

And a function to convert to the AST:

```python
def from_tree_sitter(self, tsnode: ts.Node, encoding: str = 'utf-8') -> tstp.Node
```
