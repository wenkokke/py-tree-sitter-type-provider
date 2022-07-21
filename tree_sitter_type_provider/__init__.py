from abc import abstractmethod
from collections.abc import Callable
from tree_sitter_type_provider.node_types import (
    NodeType as NodeType,
    Point as Point,
    Node as Node,
    NodeChild as NodeChild,
    ERROR as ERROR,
)

import tree_sitter as ts
import typing
import types


class TreeSitterTypeProvider(types.ModuleType):
    @staticmethod
    def _tspoint_to_point(tspoint: tuple[int, int]) -> Point:
        return Point(row=tspoint[0], column=tspoint[1])

    def _node_has_children(self, node: typing.Union[Node, NodeType, ts.Node]) -> bool:
        if isinstance(node, ts.Node):
            node_type = self._node_types_by_type.get(node.type, None)
        else:
            node_type = self._node_types_by_type.get(node.type_name, None)
        return node_type is not None and node_type.children is not None

    def _node_class(self, node: typing.Union[Node, NodeType, ts.Node]) -> type[Node]:
        if isinstance(node, ts.Node):
            return self._node_dataclasses_by_type[node.type]
        else:
            return self._node_dataclasses_by_type[node.type_name]

    def from_tree_sitter(self, tsnode: ts.Node, encoding: str = "utf-8") -> NodeChild:
        """
        Convert a tree-sitter Node to an instance of a generated dataclass.
        """
        if tsnode.is_named:
            # Convert children
            text: str = tsnode.text.decode(encoding)
            start_position: Point = self._tspoint_to_point(tsnode.start_point)
            end_position: Point = self._tspoint_to_point(tsnode.end_point)
            fields: dict[str, NodeChild] = {}
            tsfield_hashes: set[int] = set()
            children: list[NodeChild] = []
            node_type: typing.Optional[NodeType] = self._node_types_by_type.get(
                tsnode.type, None
            )
            if node_type:
                for field_name in node_type.fields.keys():
                    tsfield = tsnode.child_by_field_name(field_name)
                    if tsfield.is_named:
                        tsfield_hashes.add(hash((tsfield.start_byte, tsfield.end_byte)))
                        fields[field_name] = self.from_tree_sitter(tsfield, encoding)
            for tschild in tsnode.children:
                if tschild.is_named:
                    if tschild.__hash__ not in tsfield_hashes:
                        child_value = self.from_tree_sitter(tschild, encoding)
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
                kwargs: dict[
                    str, typing.Union[str, Point, NodeChild, list[NodeChild]]
                ] = {}
                kwargs["type_name"] = tsnode.type
                kwargs["text"] = text
                kwargs["start_position"] = start_position
                kwargs["end_position"] = end_position
                if self._node_has_children(tsnode):
                    kwargs["children"] = children
                kwargs |= fields
                return self._node_class(tsnode)(**kwargs)  # type: ignore
        raise ValueError(ts.Node)

    def __init__(
        self,
        module_name: str,
        node_types: list[NodeType],
        *,
        as_class_name: typing.Optional[Callable[[str], str]] = None,
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

        # Dictionary of abstract classes
        self._node_bases_by_type: dict[str, list[type[Node]]] = {}
        for node_type in self._node_types_by_type.values():
            if node_type.abstract:
                cls = node_type.as_class(as_class_name=as_class_name)
                setattr(self, as_class_name(node_type.type_name), cls)
                for subtype in node_type.subtypes:
                    if subtype.named:
                        if subtype.type_name not in self._node_bases_by_type:
                            self._node_bases_by_type[subtype.type_name] = []
                        self._node_bases_by_type[subtype.type_name].append(cls)

        # Dictionary of dataclasses
        self._node_dataclasses_by_type: dict[str, type[Node]] = {}
        self._node_dataclasses_by_type["ERROR"] = ERROR
        for node_type in self._node_types_by_type.values():
            if node_type.type_name in self._node_bases_by_type:
                bases = tuple(self._node_bases_by_type[node_type.type_name])
            else:
                bases = (Node,)
            cls = node_type.as_class(
                bases=bases,
                as_class_name=as_class_name,
                **dataclass_kwargs,
            )
            self._node_dataclasses_by_type[node_type.type_name] = cls
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
                if not node_type.abstract:
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
                kwargs: dict[str, typing.Union[str, NodeChild, Result, list[Result]]] = {}
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
            **kwargs: dict[str, typing.Union[Result, NodeChild]],
        ) -> Result:
            """
            Transform any node type.
            """

        def NodeTransformer_exec_body(ns):
            ns["__module__"] = module_name
            for node_type in self._node_types_by_type.values():
                if not node_type.abstract:
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
