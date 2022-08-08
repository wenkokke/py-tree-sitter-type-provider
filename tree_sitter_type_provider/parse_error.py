import collections.abc
import dataclasses
import typing

from .node_types import Branch, Node, Point


@dataclasses.dataclass
class ParseError(Exception, Branch):
    children: list[Node]
    contents: typing.Optional[str] = None
    filename: typing.Optional[str] = None

    @staticmethod
    def _point_to_str(point: Point) -> str:
        return f"line {point.line}, column {point.column}"

    def _range(self) -> str:
        if self.start_position.line == self.end_position.line:
            return f"on line {self.start_position.line} between column {self.start_position.column} and {self.end_position.column}"
        else:
            return f" between {self._point_to_str(self.start_position)} and {self._point_to_str(self.end_position)}"

    def _annotated_region(self) -> str:
        if self.contents:

            def _annotated_lines(
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
                        if c < start or end < c:
                            annotation.append(" ")
                        else:
                            annotation.append("^")
                    yield "".join(annotation)

            lines = self.contents.splitlines()
            lines = lines[self.start_position.line : self.end_position.line + 1]
            return "\n".join(_annotated_lines(lines))
        else:
            return self.text

    def __str__(self) -> str:
        return "".join(
            (
                f"Parse error ",
                f"in {self.filename} " if self.filename else "",
                f"{self._range()}:\n",
                f"{self._annotated_region()}\n",
            )
        )
