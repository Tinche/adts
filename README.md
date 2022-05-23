# ADTs for Python

Create algebraic data types (ADTs) easily, using syntax modeled on the `enum` module.

In simple terms, picture enriching the `enum` module with support for member classes in addition to constant values.

```python
class Event(ADT):
    QUIT = "quit"

    @dataclass
    class Message:
        msg: str

def process_event(event: Event) -> str:
    match event:
        case Event.QUIT:
            return "quit"
        case Event.Message(msg):
            return f"Message: {msg}"

>>> process_event(Event.Message("test"))
"Message: test"
```

The focus is on sum types, since product types are already well-served by the language.

#### Generics are supported

ADTs may also be generic:

```python
from __future__ import annotations

T = TypeVar("T")


class Tree(ADT[T]):
    EMPTY = "empty"

    @dataclass
    class Node:
        left: Tree[T]
        right: Tree[T]
```

This requires the postponed evaluation of annotations (aka PEP 563), which is activated by importing `annotations` from `__future__`.

#### Class enum members get methods from the enum

A class member will have access to any method on the enum.
Since this involves replacing the class with a special subclass, class members must be defined inside the enum.

```python
class MyADT(ADT):
    @dataclass
    class Inner:
        b: int

    def a_method(self) -> int:
        return 1

>>> MyADT.Inner(1).a_method()
1
```

## The differences between Python enums (PEP 435) and ADTs

### No mixins

Enums may mix in a class for their members.

```python
class IntEnum(int, Enum):
    A = 1
```

This adds the mixed-in class to each member's MRO, so `isinstance(IntEnum.A, int)` holds.

Since ADTs can be heterogenous, no class may be mixed in.

### No class getitem

Enums support a class-level `__getitem__`, which allows fetching enum members by name.

```python
class MyEnum(Enum):
    A = 1

>>> MyEnum['A']
<MyEnum.A: 1>
```

Since ADTs need to be able to be generic, this syntax conflicts with parametrizing a generic ADT, so it is not supported.

```python
T = TypeVar("T")
E = TypeVar("E", bound=BaseException)

class Result(ADT[T, E]):
    @dataclass
    class Ok:
        val: T

    @dataclass
    class Err:
        err: E
```
