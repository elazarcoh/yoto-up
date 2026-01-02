import json
from typing import Any, overload


class WithValue:
    def __init__(self, name: str, value: Any):
        self.name = name
        self.value = value

    def keys(self):
        return [self.name]

    def __getitem__(self, key):
        if key == self.name:
            return self.value
        raise KeyError(key)


class _AttrBase:
    NEXT: type["_AttrBase"] | None = None
    SEP: str

    def __init__(self, name: str):
        self.name = name

    def __getattr__(self, attr_name):
        if not self.NEXT:
            raise AttributeError(f"No further attributes for {self.name}")

        return self.NEXT(f"{self.name}{self.SEP}{attr_name}")

    def __call__(self, other: Any) -> WithValue:
        return WithValue(self.name, other)


class classproperty:
    def __init__(self, func):
        self.fget = func

    def __get__(self, instance, owner):
        return self.fget(owner)


# =======================================================================
# Xon (Alpine.js x-on) Attribute Builder
# =======================================================================


class _XonModifiers:
    prevent: "XonModifier"
    stop: "XonModifier"
    outside: "XonModifier"
    window: "XonModifier"
    document: "XonModifier"
    once: "XonModifier"
    debounce: "XonModifier"
    throttle: "XonModifier"
    self: "XonModifier"
    camel: "XonModifier"
    dot: "XonModifier"
    passive: "XonModifier"
    capture: "XonModifier"


class _KeyboardEvent(_AttrBase):
    shift: "XonModifier"
    enter: "XonModifier"
    space: "XonModifier"
    ctrl: "XonModifier"
    cmd: "XonModifier"
    meta: "XonModifier"
    alt: "XonModifier"
    up: "XonModifier"
    escape: "XonModifier"
    tab: "XonModifier"

    # Special case for 'caps-lock' since it has a hyphen
    @property
    def capslock(self) -> "XonModifier":
        return self.__getattr__("caps-lock")

    equal: "XonModifier"
    period: "XonModifier"
    comma: "XonModifier"
    slash: "XonModifier"


class _XonEvents:
    click: "XonEvent"
    change: "XonEvent"
    input: "XonEvent"
    submit: "XonEvent"

    @property
    def keydown(self) -> _KeyboardEvent:
        return self.__getattr__("keydown")

    @property
    def keyup(self) -> _KeyboardEvent:
        return self.__getattr__("keyup")

    mouseover: "XonEvent"
    mouseout: "XonEvent"
    load: "XonEvent"
    scroll: "XonEvent"


class XonModifier(_AttrBase, _XonModifiers):
    @classproperty
    def NEXT(cls) -> type["XonModifier"]:
        return XonModifier

    SEP = "."


class XonEvent(_AttrBase, _XonModifiers):
    NEXT = XonModifier
    SEP = "."


class Xon(_AttrBase, _XonEvents):
    def __init__(self):
        super().__init__("x-on")

    NEXT = XonEvent
    SEP = ":"


def xon():
    return Xon()


# =======================================================================
# Xbind Attribute Builder
# =======================================================================


class _XbindAttrs:
    style: "Xbind"
    disabled: "Xbind"
    href: "Xbind"
    src: "Xbind"
    value: "Xbind"
    title: "Xbind"


class XbindAttrs(_AttrBase):
    NEXT = None
    SEP = "."


class Xbind(_AttrBase, _XbindAttrs):
    NEXT = XbindAttrs
    SEP = ":"

    def __init__(self):
        super().__init__("x-bind")

    # Special handler for 'class' attribute
    @property
    def classes(self):
        return super().__getattr__("class")


def xbind() -> Xbind:
    return Xbind()


# =======================================================================
# Xdata Attribute Builder
# =======================================================================


def xdata(data: str | dict) -> WithValue:
    if isinstance(data, str):
        return WithValue("x-data", data)
    else:
        return WithValue("x-data", json.dumps(data))


# =======================================================================
# Xshow Attribute Builder
class Xshow(_AttrBase):
    NEXT = _AttrBase
    SEP = "."

    def __init__(self):
        super().__init__("x-show")

    @property
    def important(self):
        return super().__getattr__("important")


@overload
def xshow(condition: str) -> WithValue: ...


@overload
def xshow(condition: None = None) -> Xshow: ...


def xshow(condition: str | None = None):
    if condition is not None:
        return WithValue("x-show", condition)
    return Xshow()


# =======================================================================
# Xtext Attribute Builder
# =======================================================================
def xtext(value: str) -> WithValue:
    return WithValue("x-text", value)


# =======================================================================
# xmodel Attribute Builder


class XmodelModifiers:
    lazy: "XmodelModifier"
    number: "XmodelModifier"
    boolean: "XmodelModifier"

    @property
    def debounce(self) -> "XmodelWithTimeoutModifier":
        return XmodelWithTimeoutModifier(f"{self.name}.debounce")

    @property
    def throttle(self) -> "XmodelWithTimeoutModifier":
        return XmodelWithTimeoutModifier(f"{self.name}.throttle")

    fill: "XmodelModifier"


class XmodelWithTimeoutModifier(XmodelModifiers, _AttrBase):
    @overload
    def __call__(self) -> "XmodelWithTimeoutModifier": ...
    @overload
    def __call__(self, timeout_or_value: None) -> "XmodelWithTimeoutModifier": ...
    @overload
    def __call__(self, timeout_or_value: int) -> "XmodelModifier": ...
    @overload
    def __call__(self, timeout_or_value: str) -> WithValue: ...

    def __call__(self, timeout_or_value: str | None = None):
        if timeout_or_value is None:
            return self
        elif isinstance(timeout_or_value, int):
            return XmodelModifier(f"{self.name}.{timeout_or_value}ms")
        else:
            # treat as value
            return WithValue(self.name, timeout_or_value)


class XmodelModifier(_AttrBase, XmodelModifiers):
    @classproperty
    def NEXT(cls) -> type["XmodelModifier"]:
        return XmodelModifier

    SEP = "."


class Xmodel(_AttrBase, XmodelModifiers):
    NEXT = XmodelModifier
    SEP = "."

    def __init__(self):
        super().__init__("x-model")


@overload
def xmodel(value: str) -> WithValue: ...
@overload
def xmodel(value: None = None) -> Xmodel: ...


def xmodel(value: str | None = None):
    if value is not None:
        return WithValue("x-model", value)
    return Xmodel()


# =======================================================================
# Xif Attribute Builder
# =======================================================================


def xif(condition: str) -> WithValue:
    return WithValue("x-if", condition)
