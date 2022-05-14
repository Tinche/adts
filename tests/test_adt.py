from dataclasses import dataclass

import pytest

from adt import ADT


@dataclass
class OuterClass:
    x: int


class MyADT(ADT):
    A = 1
    B = OuterClass

    @dataclass
    class C:
        x: str


def test_mixins() -> None:
    with pytest.raises(TypeError):

        class InvalidAdt(int, ADT):
            A = 1


def test_match():
    def process(m: MyADT) -> str:
        match m:
            case MyADT.A:
                return "A"
            case MyADT.B(x):
                return f"B({x})"
            case MyADT.C(x):
                return f"C('{x}')"

    assert process(MyADT.A) == "A"
    assert process(MyADT.B(1)) == "B(1)"
    assert process(OuterClass(1)) == "B(1)"
    assert process(MyADT.C("1")) == "C('1')"


def test_constructor() -> None:
    assert MyADT(1) is MyADT.A
    assert MyADT(MyADT.B(1)) == OuterClass(1)
    assert MyADT(OuterClass(1)) == OuterClass(1)
    assert MyADT(MyADT.C(1)) == MyADT.C(1)

    @dataclass
    class Unrelated:
        x: int

    with pytest.raises(ValueError):
        MyADT(Unrelated(1))


# def test_access_by_name():
#     assert MyADT["A"] is MyADT.A
#     assert MyADT["B"] is MyADT.B
#     assert MyADT["B"] is OuterClass
#     assert MyADT["C"] is MyADT.C


def test_isinstance():
    assert isinstance(MyADT.A, MyADT)
    assert isinstance(MyADT.B(1), MyADT)

    @dataclass
    class Unrelated:
        x: int

    assert not isinstance(Unrelated(1), MyADT)
