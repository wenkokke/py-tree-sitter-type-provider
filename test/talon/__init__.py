from pathlib import Path
from tree_sitter_type_provider import TreeSitterTypeProvider
from tree_sitter_type_provider.node_types import *

import sys


class TreeSitterTalonModule(TreeSitterTypeProvider):
    def __init__(self):
        node_types_path = Path(__file__).parent / "node-types.json"
        node_types = NodeType.schema().loads(node_types_path.read_text(), many=True)
        super().__init__(module_name="talon", node_types=node_types)


sys.modules[__name__] = TreeSitterTalonModule()
