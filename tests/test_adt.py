from dataclasses import dataclass

import pytest

from adt import ADT


class MyADT(ADT):
    A = 1

    @dataclass
    class C:
        x: str

    def is_a(self):
        return self is MyADT.A

    def is_c(self):
        return isinstance(self, MyADT.C)


def test_mixins() -> None:
    with pytest.raises(TypeError):

        class InvalidAdt(int, ADT):
            A = 1


def test_match():
    def process(m: MyADT) -> str:
        match m:
            case MyADT.A:
                return "A"
            case MyADT.C(x):
                return f"C('{x}')"

    assert process(MyADT.A) == "A"
    assert process(MyADT.C("1")) == "C('1')"


def test_constructor() -> None:
    assert MyADT(1) is MyADT.A
    assert MyADT(MyADT.C(1)) == MyADT.C(1)

    @dataclass
    class Unrelated:
        x: int

    with pytest.raises(ValueError):
        MyADT(Unrelated(1))


def test_isinstance():
    assert isinstance(MyADT.A, MyADT)
    assert isinstance(MyADT.C(1), MyADT)

    @dataclass
    class Unrelated:
        x: int

    assert not isinstance(Unrelated(1), MyADT)
