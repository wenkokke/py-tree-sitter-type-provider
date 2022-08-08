import collections.abc
import dataclasses
import typing

from .node_types import Branch, Node, NodeTypeName, Point


@dataclasses.dataclass
class ParseError(Exception, Branch):
    children: list[Node]

    def __post_init__(self, **kwargs) -> None:
        raise self

    @staticmethod
    def point_to_str(point: Point) -> str:
        return f"line {point.line}, column {point.column}"

    def range(self) -> str:
        if self.start_position.line == self.end_position.line:
            return f"on line {self.start_position.line} between column {self.start_position.column} and {self.end_position.column}"
        else:
            return f" between {self.point_to_str(self.start_position)} and {self.point_to_str(self.end_position)}"

    def annotated_region(self, contents: str) -> str:
        def annotated_lines(
            lines: typing.Sequence[str],
        ) -> collections.abc.Iterator[str]:
            for l, line in enumerate(lines):
                yield line
                is_first_line = l == 0
                is_last_line = l == len(lines) - 1
                start = self.start_position.column if is_first_line else 0
                end = self.end_position.column if is_last_line else len(line)
                annotation: list[str] = []
                for c, _ in enumerate(line):
                    if c <= start or end < c:
                        annotation.append(" ")
                    else:
                        annotation.append("^")
                yield "".join(annotation)

        lines = contents.splitlines()
        lines = lines[self.start_position.line : self.end_position.line + 1]
        return "\n".join(annotated_lines(lines))

    def message(self, *, contents: str, filename: typing.Optional[str] = None) -> str:
        return "".join(
            (
                f"Parse error ",
                f"in {filename} " if filename else "",
                f"{self.range()}:\n",
                f"{self.annotated_region(contents)}\n",
            )
        )
