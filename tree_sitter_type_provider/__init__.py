import collections.abc
import types
import typing

import tree_sitter

from tree_sitter_type_provider.node_types import Branch as Branch
from tree_sitter_type_provider.node_types import Leaf as Leaf
from tree_sitter_type_provider.node_types import Node as Node
from tree_sitter_type_provider.node_types import NodeArgsType as NodeArgsType
from tree_sitter_type_provider.node_types import NodeFieldName as NodeFieldName
from tree_sitter_type_provider.node_types import NodeType as NodeType
from tree_sitter_type_provider.node_types import NodeTypeError as NodeTypeError
from tree_sitter_type_provider.node_types import NodeTypeName as NodeTypeName
from tree_sitter_type_provider.node_types import Point as Point


class TreeSitterTypeProvider(types.ModuleType):
    @staticmethod
    def _tspoint_to_point(tspoint: tuple[int, int]) -> Point:
        return Point(row=tspoint[0], column=tspoint[1])

    def _node_type_name(
        self,
        node: typing.Union[NodeTypeName, Node, NodeType, tree_sitter.Node],
    ) -> str:
        if isinstance(node, tree_sitter.Node):
            return node.type
        elif isinstance(node, Node):
            return node.type_name
        elif isinstance(node, NodeType):
            return node.type_name
        elif isinstance(node, str):
            return node
        else:
            raise NodeTypeError(
                f"Cannot get node type name for object of type {type(node)}", node
            )

    def _node_type(
        self,
        node: typing.Union[NodeTypeName, Node, NodeType, tree_sitter.Node],
    ) -> NodeType:
        node_type_name = self._node_type_name(node)
        node_type = self._node_types_by_type.get(node_type_name, None)
        if node_type is None:
            raise NodeTypeError(f"Could not find node type {node_type_name}")
        return node_type

    def _node_has_children(
        self,
        node: typing.Union[NodeTypeName, Node, NodeType, tree_sitter.Node],
    ) -> bool:
        node_type = self._node_type(node)
        # NOTE: Any node with content can have extra nodes,
        #       even if the node only has fields and no children.
        return node_type.has_content

    def _node_class(
        self, node: typing.Union[Node, NodeType, tree_sitter.Node]
    ) -> type[Node]:
        node_type_name = self._node_type_name(node)
        cls = self._node_classes_by_type.get(node_type_name, None)
        if cls is None:
            raise NodeTypeError(f"Could not find node type {node_type_name}")
        return cls

    def _node_hash(self, tsnode: tree_sitter.Node) -> int:
        return hash((tsnode.start_byte, tsnode.end_byte))

    def from_tree_sitter(
        self,
        tsvalue: typing.Union[
            tree_sitter.Tree, tree_sitter.Node, tree_sitter.TreeCursor
        ],
        *,
        encoding: str = "utf-8",
    ) -> Node:
        if isinstance(tsvalue, tree_sitter.Tree):
            tsvalue = tsvalue.root_node
        if isinstance(tsvalue, tree_sitter.Node):
            tsvalue = tsvalue.walk()
        return self._from_tree_cursor(tsvalue, encoding=encoding)

    def _from_tree_cursor(
        self,
        tscursor: tree_sitter.TreeCursor,
        *,
        encoding: str = "utf-8",
    ) -> Node:
        if tscursor.node.is_named:
            # Convert basic information
            text: str = tscursor.node.text.decode(encoding)
            type_name: str = tscursor.node.type
            start_position: Point = self._tspoint_to_point(tscursor.node.start_point)
            end_position: Point = self._tspoint_to_point(tscursor.node.end_point)

            # Convert children
            fields: dict[str, Node] = {}
            children: list[Node] = []

            def convert_child(tscursor: tree_sitter.TreeCursor):
                field_name = tscursor.current_field_name()
                child = self._from_tree_cursor(tscursor, encoding=encoding)
                if field_name is None:
                    children.append(child)
                else:
                    fields[field_name] = child

            if tscursor.goto_first_child():
                if tscursor.node.is_named:
                    convert_child(tscursor)
                while tscursor.goto_next_sibling():
                    if tscursor.node.is_named:
                        convert_child(tscursor)
                assert tscursor.goto_parent()

            # Create node instance
            kwargs: dict[str, typing.Union[str, Point, Node, list[Node]]] = {}
            kwargs["type_name"] = type_name
            kwargs["text"] = text
            kwargs["start_position"] = start_position
            kwargs["end_position"] = end_position
            if self._node_has_children(tscursor.node):
                kwargs["children"] = children
            kwargs |= fields

            # Return the node with its field name
            return self._node_class(tscursor.node)(**kwargs)  # type: ignore
        else:
            raise TypeError(tscursor.node.type)

    def __init__(
        self,
        module_name: str,
        node_types: typing.Sequence[NodeType],
        *,
        error_as_node: bool = False,
        extra: typing.Sequence[NodeTypeName] = (),
        as_class_name: typing.Optional[collections.abc.Callable[[str], str]] = None,
        mixins: typing.Sequence[type] = (),
        dataclass_kwargs: dict[str, typing.Any] = {},
    ):
        super().__init__(name=module_name)

        if as_class_name is None:

            def snake_to_pascal(node_type_name: str) -> str:
                return "".join(map(str.capitalize, node_type_name.split("_")))

            as_class_name = snake_to_pascal

        # Dictionary of named node types
        self._node_types_by_type: dict[str, NodeType] = {}
        for node_type in node_types:
            if node_type.named:
                self._node_types_by_type[node_type.type_name] = node_type

        # Create a node type for ERROR
        if error_as_node:
            self._node_types_by_type["ERROR"] = NodeType(
                type_name="ERROR",
                named=True,
                children=NodeArgsType(
                    multiple=True,
                    required=True,
                    types=list(node_types),
                ),
            )

        # Create the list of extra node types
        extra_node_types = list(self._node_type(type_name) for type_name in extra)
        if error_as_node and "ERROR" not in extra:
            extra_node_types.append(self._node_type("ERROR"))
        self._extra: typing.Sequence = tuple(extra_node_types)

        # Dictionary of abstract classes
        self._node_bases_by_type: dict[str, list[type[Node]]] = {}
        for node_type in self._node_types_by_type.values():
            if node_type.is_abstract:
                abscls = node_type.as_type(
                    as_class_name=as_class_name,
                    base=Node,
                    mixins=mixins,
                    extra=self._extra,
                )
                abscls_name = as_class_name(node_type.type_name)
                setattr(self, abscls_name, abscls)
                for subtype in node_type.subtypes:
                    if subtype.named:
                        if subtype.type_name not in self._node_bases_by_type:
                            self._node_bases_by_type[subtype.type_name] = []
                        self._node_bases_by_type[subtype.type_name].append(abscls)

        # Dictionary of dataclasses
        self._node_classes_by_type: dict[str, type[Node]] = {}
        for node_type in self._node_types_by_type.values():
            bases = self._node_bases_by_type.get(node_type.type_name, ())
            cls = node_type.as_type(
                mixins=tuple((*bases, *mixins)),
                as_class_name=as_class_name,
                extra=self._extra,
                **dataclass_kwargs,
            )
            self._node_classes_by_type[node_type.type_name] = cls
            setattr(self, as_class_name(node_type.type_name), cls)
