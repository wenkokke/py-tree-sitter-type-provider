from abc import ABC, abstractmethod
from dataclasses import dataclass, field, make_dataclass
from functools import reduce
from types import NoneType
from dataclasses_json import DataClassJsonMixin, dataclass_json
from typing import (
    Callable,
    Dict,
    Optional,
    Sequence,
    Type,
    Union,
    cast,
)


@dataclass
class Node(DataClassJsonMixin):
    text: str
    type: str


@dataclass_json
@dataclass
class SimpleNodeType:
    type: str
    named: bool

    def as_typehint(self, as_cls_name: Callable[[str], str]) -> Type[Node]:
        if self.named:
            return cast(Type, as_cls_name(self.type))
        raise ValueError(self)

    @staticmethod
    def many_as_typehint(
        simple_node_types: list["SimpleNodeType"],
        as_cls_name: Callable[[str], str],
    ) -> Type[Node]:
        Ts: list[Type] = []
        for simple_node_type in simple_node_types:
            T = simple_node_type.as_typehint(as_cls_name=as_cls_name)
            if T is not None:
                Ts.append(T)

        if len(Ts) == 0:
            raise ValueError(simple_node_types)

        if len(Ts) == 1:
            return Ts[0]

        return reduce(lambda R, T: cast(Type, Union[R, T]), Ts)


NodeChild = Union[Sequence[Node], Node, Optional[Node]]


@dataclass_json
@dataclass
class NodeArgsType:
    multiple: bool
    required: bool
    types: list[SimpleNodeType]

    def as_typehint(
        self,
        as_cls_name: Callable[[str], str],
    ) -> Type[NodeChild]:
        T = SimpleNodeType.many_as_typehint(self.types, as_cls_name=as_cls_name)
        if T is not None:
            if self.multiple:
                return list[T]  # type: ignore
            else:
                if self.required:
                    return T
                else:
                    return Optional[T]  # type: ignore
        else:
            raise ValueError(self)


@dataclass_json
@dataclass
class NodeType(SimpleNodeType):
    fields: dict[str, NodeArgsType] = field(default_factory=dict)
    children: Optional[NodeArgsType] = None

    def is_terminal(self) -> bool:
        return len(self.fields) == 0 and self.children is None

    def as_dataclass(self, as_cls_name: Callable[[str], str], **kwargs) -> Type[Node]:
        if self.named:
            cls_name = as_cls_name(self.type)
            fields: Dict[str, Type[NodeChild]] = {}
            for field_name, field in self.fields.items():
                field_type = field.as_typehint(as_cls_name=as_cls_name)
                if field_type is not None:
                    fields[field_name] = field_type
            if self.children is not None:
                children_type = self.children.as_typehint(as_cls_name=as_cls_name)
                if children_type is not None:
                    fields["children"] = children_type
            return make_dataclass(
                cls_name=cls_name, fields=fields.items(), bases=(Node,), **kwargs
            )
        else:
            raise ValueError(self)
