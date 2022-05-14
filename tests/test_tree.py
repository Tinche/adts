from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from adt import ADT


T = TypeVar("T")


class Tree(ADT[T]):
    EMPTY = "empty"

    @dataclass
    class Node:
        left: Tree[T]
        right: Tree[T]


IntTree = Tree[int]


def test_match():
    def process(m: Tree) -> str:
        match m:
            case Tree.EMPTY:
                return "empty"
            case Tree.Node(left, right):
                return f"Node({process(left)}, {process(right)})"

    assert process(Tree.EMPTY) == "empty"
    assert (
        process(Tree.Node(Tree.EMPTY, Tree.Node(Tree.EMPTY, Tree.EMPTY)))
        == "Node(empty, Node(empty, empty))"
    )
