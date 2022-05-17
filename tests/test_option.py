from dataclasses import dataclass
from typing import TypeVar

from adt import ADT


T = TypeVar("T")


class Option(ADT[T]):
    NONE = None

    @dataclass
    class Some:
        val: T

    def is_some(self) -> bool:
        return self is not Option.NONE

    def unwrap(self) -> T:
        if self is Option.NONE:
            raise RuntimeError("Value not present")
        return self.val

    def __iter__(self):
        return iter([] if self is Option.NONE else [self.val])


def test_iteration():
    assert list(Option[int].NONE) == []
    assert list(Option[int].Some(1)) == [1]
