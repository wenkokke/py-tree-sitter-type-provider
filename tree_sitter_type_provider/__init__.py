from abc import ABC, abstractmethod
from dataclasses import dataclass
from types import ModuleType
from dataclasses_json import dataclass_json
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
from .node_types import *
import tree_sitter as ts


class TreeSitterTypeProvider(ModuleType):
    @dataclass_json
    @dataclass
    class ERROR(Node):
        children: list[NodeChild] = field(default_factory=list)

    @staticmethod
    def _tspoint_to_point(tspoint: Tuple[int, int]) -> Point:
        return Point(row=tspoint[0], column=tspoint[1])

    @staticmethod
    def _snake_to_pascal(text: str) -> str:
        return "".join(chunk.capitalize() for chunk in text.split("_"))

    def _node_has_children(self, node: Union[Node, NodeType, ts.Node]) -> bool:
        node_type = self._node_types_by_type.get(node.type, None)
        return node_type is not None and node_type.children is not None

    def _node_class(self, node: Union[Node, NodeType, ts.Node]) -> Type[Node]:
        return self._node_dataclasses_by_type[node.type]

    def from_tree_sitter(self, tsnode: ts.Node) -> NodeChild:
        """
        Convert a tree-sitter Node to an instance of a generated dataclass.
        """
        if tsnode.is_named:
            # Convert children
            text: str = tsnode.text.decode("utf-8")
            start_position: Point = self._tspoint_to_point(tsnode.start_position)
            end_position: Point = self._tspoint_to_point(tsnode.end_position)
            fields: Dict[str, NodeChild] = {}
            children: List[NodeChild] = []
            for i in range(0, tsnode.named_child_count):
                tschild: Optional[ts.Node] = tsnode.named_child(i)
                if tschild is not None:
                    field_name: Optional[str] = tschild.field_name_for_child(i)
                    if field_name is not None:
                        fields[field_name] = self.from_tree_sitter(tschild)
                    else:
                        child_value = self.from_tree_sitter(tschild)
                        if not isinstance(child_value, str):
                            children.append(child_value)
            # Create node instance
            if tsnode.is_error:
                return self.ERROR(
                    text=text,
                    type="ERROR",
                    start_position=start_position,
                    end_position=end_position,
                    children=children,
                )
            else:
                kwargs: Dict[str, Union[str, Point, NodeChild, List[NodeChild]]] = {}
                kwargs["type"] = tsnode.type
                kwargs["text"] = text
                kwargs["start_position"] = start_position
                kwargs["end_position"] = end_position
                if self._has_children(tsnode):
                    kwargs["children"] = children
                kwargs |= fields
                return self._node_class(tsnode)(**kwargs)  # type: ignore
        raise ValueError(ts.Node)

    def __init__(
        self,
        module_name: str,
        node_types: list[NodeType],
        as_class_name: Optional[Callable[[str], str]] = None,
        dataclass_kwargs: Dict[str, Any] = {},
    ):
        super().__init__(name=module_name)

        # Set default value for as_class_name
        if as_class_name is None:
            as_class_name = self._snake_to_pascal

        # Dictionary of named node types
        self._node_types_by_type: Dict[str, NodeType] = {}
        for node_type in node_types:
            if node_type.named:
                self._node_types_by_type[node_type.type] = node_type

        # Dictionary of abstract classes
        self._node_bases_by_type: Dict[str, List[Type[Node]]] = {}
        for node_type in self._node_types_by_type.values():
            if node_type.abstract:
                cls = node_type.as_class(as_class_name)
                setattr(self, as_class_name(node_type.type), cls)
                for subtype in node_type.subtypes:
                    if subtype.named:
                        if subtype.type not in self._node_bases_by_type:
                            self._node_bases_by_type[subtype.type] = []
                        self._node_bases_by_type[subtype.type].append(cls)

        # Dictionary of dataclasses
        self._node_dataclasses_by_type: Dict[str, Type[Node]] = {}
        self._node_dataclasses_by_type["ERROR"] = self.ERROR
        for node_type in self._node_types_by_type.values():
            if node_type.type in self._node_bases_by_type:
                bases = tuple(self._node_bases_by_type[node_type.type])
            else:
                bases = (Node,)
            cls = node_type.as_class(
                as_class_name,
                bases=bases,
                **dataclass_kwargs,
            )
            self._node_dataclasses_by_type[node_type.type] = cls
            setattr(self, as_class_name(node_type.type), cls)

        # Create NodeVisitor class
        def visit(self, node: Node) -> None:
            if isinstance(node, Node):
                cls_name = node.__class__.__name__.split(".")[-1]
                visit_node_type = getattr(self, f"visit_{cls_name}")
                visit_node_type(node)

        def generic_visit(self, node: Node) -> None:
            for field_value in node.__dataclass_fields__.values():
                if isinstance(field_value, list):
                    for item in field_value:
                        self.visit(item)
                if isinstance(field_value, Node):
                    self.visit(field_value)

        self.NodeVisitor: Type = type(
            "NodeVisitor",
            (object,),
            {
                "visit": visit,
                "generic_visit": generic_visit,
                "visit_ERROR": generic_visit,
            }
            | {
                f"visit_{as_class_name(node_type.type)}": generic_visit
                for node_type in self._node_types_by_type.values()
                if not node_type.abstract
            },
        )

        # Create NodeTransformer class
        Result = TypeVar("Result")

        self.Result = Result

        def transform(self, node: Node) -> Result:
            if isinstance(node, Node):
                cls_name = node.__class__.__name__.split(".")[-1]
                func: Callable[..., Result] = getattr(self, f"transform_{cls_name}")
                kwargs: Dict[str, str | NodeChild | Result | List[Result]] = {}
                for field_name, field_value in node.__dataclass_fields__.items():
                    if isinstance(field_value, str):
                        kwargs[field_name] = field_value
                    elif isinstance(field_value, Node):
                        kwargs[field_name] = self.transform(node)
                        kwargs[f"{field_name}_hist"] = field_value
                    elif isinstance(field_value, list):
                        field_value_results: List[Result] = []
                        for field_value_item in field_value:
                            if isinstance(field_value_item, Node):
                                field_value_results.append(
                                    self.transform(field_value_item)
                                )
                        kwargs[field_name] = field_value_results
                        kwargs[f"{field_name}_hist"] = field_value
                    else:
                        raise ValueError({field_name: field_value})
                return func(**kwargs)
            else:
                return ValueError(node)

        def generic_transform(
            self,
            *,
            text: str,
            type: str,
            children: List[Result] = [],
            **kwargs: Dict[str, Result | NodeChild],
        ) -> Result:
            """
            Transform any node type.
            """

        self.NodeTransformer = type(
            "NodeTransformer",
            (ABC,),
            {
                "transform": transform,
                "transform_ERROR": abstractmethod(generic_transform),
            }
            | {
                f"transform_{as_class_name(node_type.type)}": abstractmethod(
                    generic_transform
                )
                for node_type in self._node_types_by_type.values()
                if not node_type.abstract
            },
        )
