# ADTs for Python

Create algebraic data types (ADTs) easily, using syntax based on the `enum` module.

In simple terms, picture enriching the `enum` module with support for member classes, in addition to constant values.

A simple example:

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

process_event(Event.Message("test"))
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

#### Class members may be defined externally

A class member can, but doesn't have to be defined inside the ADT.

```python
@dataclass
class Outer:
    a: int

class MyADT(ADT):
    @dataclass
    class Inner:
        b: int

    Outer = Outer
```

## The differences between Python enums (PEP 435) and ADTs

### No methods on the ADT class

Enums may define methods which are available on all their members.

```python
class EnumWithMethod(Enum):
    A = 1
    B = 2

    def is_a(self) -> bool:
        return self._value_ == 1

>>> EnumWithMethod.A.is_a()
True
```

Since this would require invasive changes to the class members of the ADTs, this is not supported.

### No mixins

Enums may mix in a class for their members.

```python
class IntEnum(int, Enum):
    A = 1
```

This adds the mixed-in class to each member's MRO, so `instance(IntEnum.A, int)` holds.

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
