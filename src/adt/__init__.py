"""Algebraic data types."""
import sys

from dataclasses import dataclass
from enum import (
    Flag,
    _EnumDict,
    _is_dunder,
    _make_class_unpicklable,
    _reduce_ex_by_name,
)
from types import (
    DynamicClassAttribute,
    GenericAlias,
    MappingProxyType,
    new_class,
)
from typing import Any


ADT = None


class ADTMeta(type):
    """
    Metaclass for ADT
    """

    def __instancecheck__(self, __instance: Any) -> bool:
        return type(__instance) in self._cls_set_ or isinstance(__instance, super())

    @classmethod
    def __prepare__(metacls, cls, bases, **kwds):
        # check that previous enum members do not exist
        metacls._check_for_existing_members(cls, bases)
        # create the namespace dict
        enum_dict = _EnumDict()
        enum_dict._cls_name = cls
        # inherit previous flags and _generate_next_value_ function
        if len(bases) > 1 and not any(hasattr(b, "_unsealed") for b in bases):
            raise TypeError("ADTs do not support mixins")
        # member_type, first_enum = metacls._get_mixins_(cls, bases)
        # if first_enum is not None:
        #     enum_dict["_generate_next_value_"] = getattr(
        #         first_enum,
        #         "_generate_next_value_",
        #         None,
        #     )
        return enum_dict

    def __new__(metacls, cls, bases, classdict, **kwds):
        # an ADT class is final once enumeration items have been defined.
        #
        # remove any keys listed in _ignore_
        classdict.setdefault("_ignore_", []).append("_ignore_")
        ignore = classdict["_ignore_"]
        for key in ignore:
            classdict.pop(key, None)
        member_type, first_enum = metacls._get_mixins_(cls, [])
        __new__, save_new, use_args = metacls._find_new_(
            classdict,
            member_type,
            first_enum,
        )
        custom_methods = metacls._gather_user_methods(classdict) if bases else {}

        # save enum items into separate mapping so they don't get baked into
        # the new class
        enum_members = {k: classdict[k] for k in classdict._member_names}
        for name in classdict._member_names:
            del classdict[name]

        # adjust the sunders
        _order_ = classdict.pop("_order_", None)

        # check for illegal enum names (any others?)
        invalid_names = set(enum_members) & {"mro", ""}
        if invalid_names:
            raise ValueError(
                "Invalid enum member name: {0}".format(",".join(invalid_names))
            )

        # create a default docstring if one has not been provided
        if "__doc__" not in classdict:
            classdict["__doc__"] = "An ADT."

        enum_class = super().__new__(metacls, cls, bases, classdict, **kwds)
        enum_class._member_names_ = []  # names in definition order
        enum_class._member_map_ = {}  # name->value map
        enum_class._values_map_ = {}  # only for values, not classes
        enum_class._member_type_ = member_type
        enum_class._cls_set_ = set()
        enum_class._unsealed = True

        # save DynamicClassAttribute attributes from super classes so we know
        # if we can take the shortcut of storing members in the class dict
        dynamic_attributes = {
            k
            for c in enum_class.mro()
            for k, v in c.__dict__.items()
            if isinstance(v, DynamicClassAttribute)
        }

        # Reverse value->name map for hashable values.
        enum_class._value2member_map_ = {}

        # If a custom type is mixed into the Enum, and it does not know how
        # to pickle itself, pickle.dumps will succeed but pickle.loads will
        # fail.  Rather than have the error show up later and possibly far
        # from the source, sabotage the pickle protocol for this class so
        # that pickle.dumps also fails.
        #
        # However, if the new class implements its own __reduce_ex__, do not
        # sabotage -- it's on them to make sure it works correctly.  We use
        # __reduce_ex__ instead of any of the others as it is preferred by
        # pickle over __reduce__, and it handles all pickle protocols.
        if "__reduce_ex__" not in classdict:
            if member_type is not object:
                methods = (
                    "__getnewargs_ex__",
                    "__getnewargs__",
                    "__reduce_ex__",
                    "__reduce__",
                )
                if not any(m in member_type.__dict__ for m in methods):
                    if "__new__" in classdict:
                        # too late, sabotage
                        _make_class_unpicklable(enum_class)
                    else:
                        # final attempt to verify that pickling would work:
                        # travel mro until __new__ is found, checking for
                        # __reduce__ and friends along the way -- if any of them
                        # are found before/when __new__ is found, pickling should
                        # work
                        sabotage = None
                        for chain in bases:
                            for base in chain.__mro__:
                                if base is object:
                                    continue
                                elif any(m in base.__dict__ for m in methods):
                                    # found one, we're good
                                    sabotage = False
                                    break
                                elif "__new__" in base.__dict__:
                                    # not good
                                    sabotage = True
                                    break
                            if sabotage is not None:
                                break
                        if sabotage:
                            _make_class_unpicklable(enum_class)
        # instantiate them, checking for duplicates as we go
        # we instantiate first instead of checking for duplicates first in case
        # a custom __new__ is doing something funky with the values -- such as
        # auto-numbering ;)

        def customize_subclass_ns(ns: dict[str, Any]):
            for k, v in custom_methods.items():
                ns[k] = v

        for member_name in classdict._member_names:
            value = enum_members[member_name]
            if not isinstance(value, tuple):
                args = (value,)
            else:
                args = value
            if member_type is tuple:  # special case for tuple enums
                args = (args,)  # wrap it one more time

            value_is_cls = isinstance(value, type)

            if value_is_cls:
                # We subclass the class to add he enum_class to its MRO
                subclass = new_class(
                    value.__qualname__, (value,), exec_body=customize_subclass_ns
                )
                enum_member = subclass
                enum_class._cls_set_.add(subclass)
            else:
                if not use_args:
                    enum_member = __new__(enum_class)
                    if not hasattr(enum_member, "_value_"):
                        enum_member._value_ = value
                else:
                    enum_member = __new__(enum_class, *args)
                    if not hasattr(enum_member, "_value_"):
                        if member_type is object:
                            enum_member._value_ = value
                        else:
                            enum_member._value_ = member_type(*args)
                value = enum_member._value_
                enum_member._name_ = member_name
                enum_member.__objclass__ = enum_class
                enum_member.__init__(*args)
            # If another member with the same value was already defined, the
            # new member becomes an alias to the existing one.
            for name, canonical_member in enum_class._member_map_.items():
                if value_is_cls:
                    if canonical_member == enum_member:
                        enum_member = canonical_member
                        break
                else:
                    if canonical_member._value_ == enum_member._value_:
                        enum_member = canonical_member
                        break
            else:
                # Aliases don't appear in member names (only in __members__).
                enum_class._member_names_.append(member_name)
            # performance boost for any member that would not shadow
            # a DynamicClassAttribute
            if member_name not in dynamic_attributes:
                setattr(enum_class, member_name, enum_member)
            # now add to _member_map_
            enum_class._member_map_[member_name] = enum_member
            if not value_is_cls:
                enum_class._values_map_[member_name] = enum_member
            try:
                # This may fail if value is not hashable. We can't add the value
                # to the map, and by-value lookups for this value will be
                # linear.
                enum_class._value2member_map_[value] = enum_member
            except TypeError:
                pass

        # double check that repr and friends are not the mixin's or various
        # things break (such as pickle)
        # however, if the method is defined in the Enum itself, don't replace
        # it
        for name in ("__repr__", "__str__", "__format__", "__reduce_ex__"):
            if name in classdict:
                continue
            class_method = getattr(enum_class, name)
            obj_method = getattr(member_type, name, None)
            enum_method = getattr(first_enum, name, None)
            if obj_method is not None and obj_method is class_method:
                setattr(enum_class, name, enum_method)

        # replace any other __new__ with our own (as long as Enum is not None,
        # anyway) -- again, this is to support pickle
        if ADT is not None:
            # if the user defined their own __new__, save it before it gets
            # clobbered in case they subclass later
            if save_new:
                enum_class.__new_member__ = __new__
            enum_class.__new__ = ADT.__new__

        # py3 support for definition order (helps keep py2/py3 code in sync)
        if _order_ is not None:
            if isinstance(_order_, str):
                _order_ = _order_.replace(",", " ").split()
            if _order_ != enum_class._member_names_:
                raise TypeError("member order does not match _order_")

        delattr(enum_class, "_unsealed")
        return enum_class

    def __bool__(self):
        """
        classes/types should always be True.
        """
        return True

    def __call__(
        cls, value, names=None, *, module=None, qualname=None, type=None, start=1
    ):
        """
        Either returns an existing member, or creates a new enum class.

        This method is used both when an enum class is given a value to match
        to an enumeration member (i.e. Color(3)) and for the functional API
        (i.e. Color = Enum('Color', names='RED GREEN BLUE')).

        When used for the functional API:

        `value` will be the name of the new class.

        `names` should be either a string of white-space/comma delimited names
        (values will start at `start`), or an iterator/mapping of name, value pairs.

        `module` should be set to the module this class is being created in;
        if it is not set, an attempt to find that module will be made, but if
        it fails the class will not be picklable.

        `qualname` should be set to the actual location this class can be found
        at in its module; by default it is set to the global scope.  If this is
        not correct, unpickling will fail in some circumstances.

        `type`, if set, will be mixed in as the first base class.
        """
        if names is None:  # simple value lookup
            return cls.__new__(cls, value)
        # otherwise, functional API: we're creating a new Enum type
        return cls._create_(
            value,
            names,
            module=module,
            qualname=qualname,
            type=type,
            start=start,
        )

    def __contains__(cls, obj):
        if not isinstance(obj, ADT):
            import warnings

            warnings.warn(
                "in 3.12 __contains__ will no longer raise TypeError, but will return True if\n"
                "obj is a member or a member's value",
                DeprecationWarning,
                stacklevel=2,
            )
            raise TypeError(
                "unsupported operand type(s) for 'in': '%s' and '%s'"
                % (type(obj).__qualname__, cls.__class__.__qualname__)
            )
        return isinstance(obj, cls) and obj._name_ in cls._member_map_

    def __delattr__(cls, attr):
        # nicer error message when someone tries to delete an attribute
        # (see issue19025).
        if attr in cls._member_map_:
            raise AttributeError("%s: cannot delete Enum member." % cls.__name__)
        super().__delattr__(attr)

    def __dir__(self):
        return [
            "__class__",
            "__doc__",
            "__members__",
            "__module__",
        ] + self._member_names_

    def __getattr__(cls, name):
        """
        Return the enum member matching `name`

        We use __getattr__ instead of descriptors or inserting into the enum
        class' __dict__ in order to support `name` and `value` being both
        properties for enum members (which live in the class' __dict__) and
        enum members themselves.
        """
        if _is_dunder(name):
            raise AttributeError(name)
        try:
            return cls._member_map_[name]
        except KeyError:
            raise AttributeError(name) from None

    def __iter__(cls):
        """
        Returns members in definition order.
        """
        return (cls._member_map_[name] for name in cls._member_names_)

    def __len__(cls):
        return len(cls._member_names_)

    @property
    def __members__(cls):
        """
        Returns a mapping of member name->value.

        This mapping lists all enum members, including aliases. Note that this
        is a read-only view of the internal mapping.
        """
        return MappingProxyType(cls._member_map_)

    def __repr__(cls):
        return "<ADT %r>" % cls.__name__

    def __reversed__(cls):
        """
        Returns members in reverse definition order.
        """
        return (cls._member_map_[name] for name in reversed(cls._member_names_))

    def __setattr__(cls, name, value):
        """
        Block attempts to reassign Enum members.

        A simple assignment to the class namespace only changes one of the
        several possible ways to get an Enum member from the Enum class,
        resulting in an inconsistent Enumeration.
        """
        member_map = cls.__dict__.get("_member_map_", {})
        if name in member_map:
            raise AttributeError("Cannot reassign members.")
        super().__setattr__(name, value)

    def _create_(
        cls, class_name, names, *, module=None, qualname=None, type=None, start=1
    ):
        """
        Convenience method to create a new Enum class.

        `names` can be:

        * A string containing member names, separated either with spaces or
          commas.  Values are incremented by 1 from `start`.
        * An iterable of member names.  Values are incremented by 1 from `start`.
        * An iterable of (member name, value) pairs.
        * A mapping of member name -> value pairs.
        """
        metacls = cls.__class__
        bases = (cls,) if type is None else (type, cls)
        _, first_enum = cls._get_mixins_(cls, bases)
        classdict = metacls.__prepare__(class_name, bases)

        # special processing needed for names?
        if isinstance(names, str):
            names = names.replace(",", " ").split()
        if isinstance(names, (tuple, list)) and names and isinstance(names[0], str):
            original_names, names = names, []
            last_values = []
            for count, name in enumerate(original_names):
                value = first_enum._generate_next_value_(
                    name, start, count, last_values[:]
                )
                last_values.append(value)
                names.append((name, value))

        # Here, names is either an iterable of (name, value) or a mapping.
        for item in names:
            if isinstance(item, str):
                member_name, member_value = item, names[item]
            else:
                member_name, member_value = item
            classdict[member_name] = member_value
        enum_class = metacls.__new__(metacls, class_name, bases, classdict)

        # TODO: replace the frame hack if a blessed way to know the calling
        # module is ever developed
        if module is None:
            try:
                module = sys._getframe(2).f_globals["__name__"]
            except (AttributeError, ValueError, KeyError):
                pass
        if module is None:
            _make_class_unpicklable(enum_class)
        else:
            enum_class.__module__ = module
        if qualname is not None:
            enum_class.__qualname__ = qualname

        return enum_class

    def _convert_(cls, name, module, filter, source=None):
        """
        Create a new Enum subclass that replaces a collection of global constants
        """
        # convert all constants from source (or module) that pass filter() to
        # a new Enum called name, and export the enum and its members back to
        # module;
        # also, replace the __reduce_ex__ method so unpickling works in
        # previous Python versions
        module_globals = vars(sys.modules[module])
        if source:
            source = vars(source)
        else:
            source = module_globals
        # _value2member_map_ is populated in the same order every time
        # for a consistent reverse mapping of number to name when there
        # are multiple names for the same number.
        members = [(name, value) for name, value in source.items() if filter(name)]
        try:
            # sort by value
            members.sort(key=lambda t: (t[1], t[0]))
        except TypeError:
            # unless some values aren't comparable, in which case sort by name
            members.sort(key=lambda t: t[0])
        cls = cls(name, members, module=module)
        cls.__reduce_ex__ = _reduce_ex_by_name
        module_globals.update(cls.__members__)
        module_globals[name] = cls
        return cls

    @staticmethod
    def _check_for_existing_members(class_name, bases):
        for chain in bases:
            for base in chain.__mro__:
                if (
                    issubclass(base, ADT)
                    and base._member_names_
                    and not hasattr(base, "_unsealed")
                ):
                    raise TypeError(
                        "%s: cannot extend enumeration %r" % (class_name, base.__name__)
                    )

    @staticmethod
    def _get_mixins_(class_name, bases):
        """
        Returns the type for creating enum members, and the first inherited
        enum class.

        bases: the tuple of bases that was given to __new__
        """
        if not bases:
            return object, ADT

        def _find_data_type(bases):
            data_types = set()
            for chain in bases:
                candidate = None
                for base in chain.__mro__:
                    if base is object:
                        continue
                    elif issubclass(base, ADT):
                        if base._member_type_ is not object:
                            data_types.add(base._member_type_)
                            break
                    elif "__new__" in base.__dict__:
                        if issubclass(base, ADT):
                            continue
                        data_types.add(candidate or base)
                        break
                    else:
                        candidate = candidate or base
            if len(data_types) > 1:
                raise TypeError(
                    "%r: too many data types: %r" % (class_name, data_types)
                )
            elif data_types:
                return data_types.pop()
            else:
                return None

        # ensure final parent class is an Enum derivative, find any concrete
        # data type, and check that Enum has no members
        first_enum = bases[-1]
        if not issubclass(first_enum, ADT):
            raise TypeError(
                "new enumerations should be created as "
                "`EnumName([mixin_type, ...] [data_type,] enum_type)`"
            )
        member_type = _find_data_type(bases) or object
        if first_enum._member_names_:
            raise TypeError("Cannot extend enumerations")
        return member_type, first_enum

    @staticmethod
    def _find_new_(classdict, member_type, first_enum):
        """
        Returns the __new__ to be used for creating the enum members.

        classdict: the class dictionary given to __new__
        member_type: the data type whose __new__ will be used by default
        first_enum: enumeration to check for an overriding __new__
        """
        # now find the correct __new__, checking to see of one was defined
        # by the user; also check earlier enum classes in case a __new__ was
        # saved as __new_member__
        __new__ = classdict.get("__new__", None)

        # should __new__ be saved as __new_member__ later?
        save_new = __new__ is not None

        if __new__ is None:
            # check all possibles for __new_member__ before falling back to
            # __new__
            for method in ("__new_member__", "__new__"):
                for possible in (member_type, first_enum):
                    target = getattr(possible, method, None)
                    if target not in {
                        None,
                        None.__new__,
                        object.__new__,
                        ADT.__new__,
                    }:
                        __new__ = target
                        break
                if __new__ is not None:
                    break
            else:
                __new__ = object.__new__

        # if a non-object.__new__ is used then whatever value/tuple was
        # assigned to the enum member name will be passed to __new__ and to the
        # new enum member's __init__
        if __new__ is object.__new__:
            use_args = False
        else:
            use_args = True
        return __new__, save_new, use_args

    @staticmethod
    def _gather_user_methods(classdict: dict[str, Any]) -> dict:
        res = {}
        for k, v in classdict.items():
            if callable(v):
                res[k] = v

        return res


class ADT(metaclass=ADTMeta):
    """
    An abstract data type.

    Derive from this class to define new abstract data types.
    """

    def __new__(cls, value):
        # all adt constants are actually created during class construction
        # without calling this method; this method is called by the metaclass'
        # __call__ (i.e. Color(3) ), and by pickle
        val_type = type(value)
        if val_type is cls:
            # For lookups like Color(Color.RED)
            return value

        if val_type in cls._cls_set_:
            return value
        # by-value search for a matching enum member
        # see if it's in the reverse mapping (for hashable values)
        try:
            return cls._value2member_map_[value]
        except KeyError:
            # Not found, no need to do long O(n) search
            pass
        except TypeError:
            # not there, now do long search -- O(n) behavior
            for member in cls._values_map_.values():
                if member._value_ == value:
                    return member
        # still not found -- try _missing_ hook
        try:
            exc = None
            result = cls._missing_(value)
        except Exception as e:
            exc = e
            result = None
        try:
            if isinstance(result, cls):
                return result
            else:
                ve_exc = ValueError("%r is not a valid %s" % (value, cls.__qualname__))
                if result is None and exc is None:
                    raise ve_exc
                elif exc is None:
                    exc = TypeError(
                        "error in %s._missing_: returned %r instead of None or a valid member"
                        % (cls.__name__, result)
                    )
                if not isinstance(exc, ValueError):
                    exc.__context__ = ve_exc
                raise exc
        finally:
            # ensure all variables that could hold an exception are destroyed
            exc = None
            ve_exc = None

    def _generate_next_value_(name, start, count, last_values):
        """
        Generate the next value when not given.

        name: the name of the member
        start: the initial start value or None
        count: the number of existing members
        last_value: the last value assigned or None
        """
        for last_value in reversed(last_values):
            try:
                return last_value + 1
            except TypeError:
                pass
        else:
            return start

    @classmethod
    def _missing_(cls, value):
        return None

    def __repr__(self):
        return "<%s.%s: %r>" % (self.__class__.__name__, self._name_, self._value_)

    def __str__(self):
        return "%s.%s" % (self.__class__.__name__, self._name_)

    def __dir__(self):
        """
        Returns all members and all public methods
        """
        added_behavior = [
            m
            for cls in self.__class__.mro()
            for m in cls.__dict__
            if m[0] != "_" and m not in self._member_map_
        ] + [m for m in self.__dict__ if m[0] != "_"]
        return ["__class__", "__doc__", "__module__"] + added_behavior

    def __format__(self, format_spec):
        """
        Returns format using actual value type unless __str__ has been overridden.
        """
        # mixed-in Enums should use the mixed-in type's __format__, otherwise
        # we can get strange results with the Enum name showing up instead of
        # the value

        # pure Enum branch, or branch with __str__ explicitly overridden
        str_overridden = type(self).__str__ not in (ADT.__str__, Flag.__str__)
        if self._member_type_ is object or str_overridden:
            cls = str
            val = str(self)
        # mix-in branch
        else:
            cls = self._member_type_
            val = self._value_
        return cls.__format__(val, format_spec)

    def __hash__(self):
        return hash(self._name_)

    def __reduce_ex__(self, proto):
        return self.__class__, (self._value_,)

    def __instancecheck__(self, __instance: Any) -> bool:
        return type(__instance) in self._cls_set_ or isinstance(__instance, super())

    # DynamicClassAttribute is used to provide access to the `name` and
    # `value` properties of enum members while keeping some measure of
    # protection from modification, while still allowing for an enumeration
    # to have members named `name` and `value`.  This works because enumeration
    # members are not set directly on the enum class -- __getattr__ is
    # used to look them up.

    @DynamicClassAttribute
    def name(self):
        """The name of the Enum member."""
        return self._name_

    @DynamicClassAttribute
    def value(self):
        """The value of the Enum member."""
        return self._value_

    def __class_getitem__(cls, types):
        return GenericAlias(cls, types)
