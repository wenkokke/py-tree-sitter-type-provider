from abc import abstractmethod
from collections.abc import Callable
from tree_sitter_type_provider.node_types import *

import tree_sitter
import typing
import types


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
        self, tsnode: tree_sitter.Node, *, encoding: str = "utf-8"
    ) -> Node:
        """
        Convert a tree-sitter Node to an instance of a generated dataclass.
        """
        if tsnode.is_named:
            text: str = tsnode.text.decode(encoding)
            start_position: Point = self._tspoint_to_point(tsnode.start_point)
            end_position: Point = self._tspoint_to_point(tsnode.end_point)
            fields: dict[str, Node] = {}
            children: list[Node] = []
            tsfield_hashes: set[int] = set()

            try:
                # Get all named fields from the tsnode
                node_type = self._node_type(tsnode)
                for field_name in node_type.fields.keys():
                    tsfield = tsnode.child_by_field_name(field_name)
                    if tsfield.is_named:
                        tsfield_hashes.add(self._node_hash(tsfield))
                        field = self.from_tree_sitter(tsfield, encoding=encoding)
                        fields[field_name] = field
            except NodeTypeError:
                pass

            # Get all children and extra nodes from the tsnode
            for tschild in tsnode.children:
                if tschild.is_named:
                    if tschild.__hash__ not in tsfield_hashes:
                        child_value = self.from_tree_sitter(tschild, encoding=encoding)
                        if not isinstance(child_value, str):
                            children.append(child_value)

            # Create node instance
            kwargs: dict[str, typing.Union[str, Point, Node, list[Node]]] = {}
            kwargs["type_name"] = tsnode.type
            kwargs["text"] = text
            kwargs["start_position"] = start_position
            kwargs["end_position"] = end_position
            if self._node_has_children(tsnode):
                kwargs["children"] = children
            kwargs |= fields
            return self._node_class(tsnode)(**kwargs)  # type: ignore
        raise ValueError(tree_sitter.Node)

    def __init__(
        self,
        module_name: str,
        node_types: typing.Sequence[NodeType],
        *,
        error_as_node: bool = False,
        extra: typing.Sequence[NodeTypeName] = (),
        as_class_name: typing.Optional[Callable[[str], str]] = None,
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
