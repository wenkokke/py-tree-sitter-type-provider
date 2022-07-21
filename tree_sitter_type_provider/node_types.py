from collections.abc import Callable
from dataclasses import dataclass, field, make_dataclass
from dataclasses_json import DataClassJsonMixin, config, dataclass_json
from functools import reduce

import typing


@dataclass
class Point:
    row: int
    column: int


@dataclass
class Node(DataClassJsonMixin):
    text: str
    type_name: str = field(metadata=config(field_name="type"))
    start_position: Point
    end_position: Point


NodeChild = typing.Union[list[Node], Node, None]


@dataclass_json
@dataclass
class ERROR(Node):
    children: list[NodeChild] = field(default_factory=list)


@dataclass_json
@dataclass
class SimpleNodeType:
    type_name: str = field(metadata=config(field_name="type"))
    named: bool

    def as_typehint(self, *, as_class_name: Callable[[str], str]) -> type[Node]:
        if self.named:
            return typing.cast(type, as_class_name(self.type_name))
        raise ValueError(self)

    @staticmethod
    def many_as_typehint(
        simple_node_types: list["SimpleNodeType"],
        *,
        as_class_name: Callable[[str], str],
    ) -> type[Node]:
        Ts: list[type] = []
        for simple_node_type in simple_node_types:
            if simple_node_type.named:
                Ts.append(simple_node_type.as_typehint(as_class_name=as_class_name))

        if len(Ts) == 0:
            raise ValueError(simple_node_types)

        if len(Ts) == 1:
            return Ts[0]

        return reduce(lambda R, T: typing.cast(type, typing.Union[R, T]), Ts)


@dataclass_json
@dataclass
class NodeArgsType:
    multiple: bool
    required: bool
    types: list[SimpleNodeType]

    @property
    def named(self) -> bool:
        return any(type.named for type in self.types)

    def as_typehint(
        self,
        *,
        as_class_name: Callable[[str], str],
    ) -> type[NodeChild]:
        T = SimpleNodeType.many_as_typehint(self.types, as_class_name=as_class_name)
        if T is not None:
            if self.multiple:
                return list[T]  # type: ignore
            else:
                if self.required:
                    return T
                else:
                    return typing.Optional[T]  # type: ignore
        else:
            raise ValueError(self)


@dataclass_json
@dataclass
class NodeType(SimpleNodeType):
    fields: dict[str, NodeArgsType] = field(default_factory=dict)
    children: typing.Union[NodeArgsType, None] = None
    subtypes: list[SimpleNodeType] = field(default_factory=list)

    def __post_init__(self, **kwargs):
        assert not (
            self.abstract and self.has_content
        ), "Nodes can have either fields and children or subtypes, but not both."

    @property
    def abstract(self) -> bool:
        return len(self.subtypes) > 0

    @property
    def has_content(self) -> bool:
        return len(self.fields) > 0 or self.children is not None

    def as_class(
        self,
        *,
        bases: tuple[type[Node], ...] = (Node,),
        as_class_name: Callable[[str], str],
        **kwargs,
    ) -> type[Node]:
        if self.named:
            cls_name = as_class_name(self.type_name)
            if self.abstract:
                return type(cls_name, (Node,), {})
            else:
                fields: dict[str, type[NodeChild]] = {}
                for field_name, field in self.fields.items():
                    if field.named:
                        field_type = field.as_typehint(as_class_name=as_class_name)
                        if field_type is not None:
                            fields[field_name] = field_type
                if self.children is not None:
                    children_type = self.children.as_typehint(
                        as_class_name=as_class_name
                    )
                    if children_type is not None:
                        fields["children"] = children_type
                return make_dataclass(
                    cls_name=cls_name, fields=fields.items(), bases=bases, **kwargs
                )
        else:
            raise ValueError(self)
