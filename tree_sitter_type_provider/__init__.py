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
        # NOTE: Extra node types cannot have content.
        # NOTE: Any node with content can have extra nodes,
        #       even if the node only has fields and no children.
        return not node_type.is_extra(extra=self._extra) and node_type.has_content

    def _node_class(
        self, node: typing.Union[Node, NodeType, tree_sitter.Node]
    ) -> type[Node]:
        return self._node_classes_by_type[self._node_type_name(node)]

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
            node_type = self._node_type(tsnode)
            tsfield_hashes: set[int] = set()

            if not node_type.is_extra(extra=self._extra):
                # Get all named fields from the tsnode
                for field_name in node_type.fields.keys():
                    tsfield = tsnode.child_by_field_name(field_name)
                    if tsfield.is_named:
                        tsfield_hashes.add(self._node_hash(tsfield))
                        field = self.from_tree_sitter(tsfield, encoding=encoding)
                        fields[field_name] = field

                # Get all children and extra nodes from the tsnode
                for tschild in tsnode.children:
                    if tschild.is_named:
                        if tschild.__hash__ not in tsfield_hashes:
                            child_value = self.from_tree_sitter(
                                tschild, encoding=encoding
                            )
                            if not isinstance(child_value, str):
                                children.append(child_value)

            # Create node instance
            if tsnode.type == "ERROR":
                return ERROR(
                    text=text,
                    type_name="ERROR",
                    start_position=start_position,
                    end_position=end_position,
                    children=children,
                )
            else:
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
        node_types: list[NodeType],
        *,
        extra: typing.Sequence[NodeTypeName] = (),
        as_class_name: typing.Optional[Callable[[str], str]] = None,
        mixins: typing.Sequence[type] = (),
        dataclass_kwargs: dict[str, typing.Any] = {},
    ):
        super().__init__(name=module_name)

        self.NodeTypeName = NodeTypeName
        self.NodeFieldName = NodeFieldName
        self.AsClassName = AsClassName
        self.NodeTypeError = NodeTypeError
        self.Point = Point
        self.Node = Node
        self.Leaf = Leaf
        self.Extra = Extra
        self.Branch = Branch
        self.ERROR = ERROR
        self.SimpleNodeType = SimpleNodeType
        self.NodeArgsType = NodeArgsType
        self.NodeType = NodeType

        if as_class_name is None:

            def snake_to_pascal(node_type_name: str) -> str:
                return "".join(map(str.capitalize, node_type_name.split("_")))

            as_class_name = snake_to_pascal

        # Dictionary of named node types
        self._node_types_by_type: dict[str, NodeType] = {}
        for node_type in node_types:
            if node_type.named:
                self._node_types_by_type[node_type.type_name] = node_type

        self._extra: typing.Sequence = tuple(
            self._node_type(type_name) for type_name in extra
        )

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
        self._node_classes_by_type["ERROR"] = ERROR
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

        # Create NodeVisitor class
        def visit(self, node: Node) -> None:
            if isinstance(node, Node):
                cls_name = node.__class__.__name__.split(".")[-1]
                visit_node_type = getattr(self, f"visit_{cls_name}")
                visit_node_type(node)

        def generic_visit(self, node: Node) -> None:
            for field_name in node.__dataclass_fields__.keys():
                field_value = getattr(node, field_name)
                if isinstance(field_value, list):
                    for item in field_value:
                        self.visit(item)
                if isinstance(field_value, Node):
                    self.visit(field_value)

        def NodeVisitor_exec_body(ns):
            ns["__module__"] = module_name
            for node_type in self._node_types_by_type.values():
                if not node_type.is_abstract:
                    ns[f"visit_{as_class_name(node_type.type_name)}"] = generic_visit
            ns["visit_ERROR"] = generic_visit
            ns["visit"] = visit
            ns["generic_visit"] = generic_visit
            return ns

        self.NodeVisitor: type = types.new_class(
            name="NodeVisitor",
            bases=(object,),
            kwds={},
            exec_body=NodeVisitor_exec_body,
        )

        # Create NodeTransformer class
        Result = typing.TypeVar("Result")

        self.Result = Result

        def transform(self, node: Node) -> Result:
            if isinstance(node, Node):
                cls_name = node.__class__.__name__.split(".")[-1]
                func: Callable[..., Result] = getattr(self, f"transform_{cls_name}")
                kwargs: dict[str, typing.Union[str, Node, Result, list[Result]]] = {}
                for field_name in node.__dataclass_fields__.keys():
                    field_value = getattr(node, field_name)
                    if isinstance(field_value, Node):
                        kwargs[field_name] = self.transform(field_value)
                        kwargs[f"{field_name}_hist"] = field_value
                    elif isinstance(field_value, list):
                        field_value_results: list[Result] = []
                        for field_value_item in field_value:
                            if isinstance(field_value_item, Node):
                                field_value_results.append(
                                    self.transform(field_value_item)
                                )
                        kwargs[field_name] = field_value_results
                        kwargs[f"{field_name}_hist"] = field_value
                    else:
                        kwargs[field_name] = field_value
                return func(**kwargs)
            else:
                return ValueError(node)

        def generic_transform(
            self,
            *,
            text: str,
            type_name: str,
            start_position: Point,
            end_position: Point,
            **kwargs: dict[str, typing.Union[Result, Node]],
        ) -> Result:
            """
            Transform any node type.
            """

        def NodeTransformer_exec_body(ns):
            ns["__module__"] = module_name
            for node_type in self._node_types_by_type.values():
                if not node_type.is_abstract:
                    # TODO: generate function with more accurate type signature
                    ns[
                        f"transform_{as_class_name(node_type.type_name)}"
                    ] = abstractmethod(generic_transform)
            ns["transform_ERROR"] = abstractmethod(generic_transform)
            ns["transform"] = transform
            return ns

        self.NodeTransformer = types.new_class(
            name="NodeTransformer",
            bases=(typing.Generic[Result],),
            kwds={},
            exec_body=NodeTransformer_exec_body,
        )
