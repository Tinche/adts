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

## The differences between Python enums (PEP 435) and ADTs

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
