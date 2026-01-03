import functools
import typing_extensions as t
from fastapi import Request
from pydom.context.context import Context, PropertyTransformer

from pydom.html import Script, Style
from pydom.types.html import HTMLScriptElement

T = t.TypeVar("T")


async def ensure_awaitable(v: t.Union[T, t.Awaitable[T]]) -> T:
    if isinstance(v, t.Awaitable):
        return await v
    else:
        return v


if t.TYPE_CHECKING:
    from pydom.types import ChildType


class PartialScript(Script):
    def __init__(self, *children: "ChildType", **kwargs: t.Unpack["HTMLScriptElement"]):
        super().__init__(*children, **kwargs)

    def __call__(self, **more: t.Unpack[HTMLScriptElement]) -> Script:
        props_not_in_self: dict = {k: v for k, v in more.items() if k not in self.props}
        final_props = {**self.props, **props_not_in_self}
        return Script(**final_props)


class HTMX:
    def __init__(self, version="2.0.4"):
        self.script = PartialScript(
            src=f"https://unpkg.com/htmx.org@{version}",
            cross_origin="anonymous",
        )
        self.unminified_script = PartialScript(
            src=f"https://unpkg.com/htmx.org@{version}/dist/htmx.js",
            cross_origin="anonymous",
        )

    def transformer(self) -> PropertyTransformer:
        return HTMXTransformer()


class HTMXExtension(t.Protocol):
    name: str
    script: PartialScript
    mapping: t.Dict[str, str]
    link: t.Optional[str] = None

    def transformer(self) -> PropertyTransformer:
        class Transformer(PropertyTransformer):
            def __init__(self, mapping):
                self.mapping = mapping

            def match(self, key, _):
                return key in self.mapping

            def transform(self, key, value, element):
                element.props[self.mapping[key]] = value
                del element.props[key]

        return Transformer(self.mapping)

    def render(self):
        yield self.script()


class HTMXSSEExtension(HTMXExtension):
    name = "sse"
    link = "https://github.com/bigskysoftware/htmx-extensions/tree/main/src/sse"
    mapping = {
        "sse_connect": "hx-sse-connect",
        "sse_swap": "hx-sse-swap",
        "sse_close": "hx-sse-close",
    }

    def __init__(self, version="2.2.2"):
        self.script = PartialScript(src=f"https://unpkg.com/htmx-ext-sse@{version}/sse.js")


class HTMXWebSocketExtension(HTMXExtension):
    name = "websocket"
    link = "https://htmx.org/extensions/ws"
    mapping = {}

    def __init__(self, version="2.0.2"):
        self.script = PartialScript(src=f"/static/js/htmx-ext-ws@{version}.js")


class HTMXJsonEncExtension(HTMXExtension):
    name = "json_enc"
    link = "https://github.com/bigskysoftware/htmx-extensions/tree/main/src/json-enc"
    mapping = {}

    def __init__(self, version="2.0.1"):
        self.script = PartialScript(src="/static/js/json-enc.js")


class HTMXMultiSwapExtension(HTMXExtension):
    name = "multi_swap"
    link = "https://github.com/bigskysoftware/htmx-extensions/blob/main/src/multi-swap/README.md"
    mapping = {}

    def __init__(self, version="2.0.0"):
        self.script = PartialScript(src="/static/js/multi-swap.js")


class HTMXLoadingStatesExtension(HTMXExtension):
    name = "loading_states"
    link = "https://github.com/bigskysoftware/htmx-extensions/tree/main/src/loading-states"
    mapping = {}

    def __init__(self, version="2.0.0"):
        self.script = PartialScript(src="/static/js/loading-states.js")
        self.style = Style("@layer utilities { [data-loading] { @apply hidden; } }")

    def render(self):
        yield from super().render()
        yield self.style()


class HTMXClassToolsExtension(HTMXExtension):
    name = "class_tools"
    link = "https://github.com/bigskysoftware/htmx-extensions/tree/main/src/class-tools"
    mapping = {
        "hx_classes": "classes",
    }

    def __init__(self, version="2.0.1"):
        self.script = PartialScript(
            src=f"https://unpkg.com/htmx-ext-class-tools@{version}/class-tools.js"
        )


class HTMXDownloadExtension(HTMXExtension):
    name = "htmx-download"
    link = "https://github.com/dakixr/htmx-download"
    mapping = {}

    def __init__(self):
        self.script = PartialScript(src="/static/js/htmx-download.js")


class HTMXOobAlternativeExtension(HTMXExtension):
    name = "oob-alternatives"
    mapping = {}

    def __init__(self):
        self.script = PartialScript(src="/static/js/oob-alternatives.js")


class HtmxExtensions:
    sse = HTMXSSEExtension()
    ws = HTMXWebSocketExtension()
    json_enc = HTMXJsonEncExtension()
    multi_swap = HTMXMultiSwapExtension()
    loading_states = HTMXLoadingStatesExtension()
    class_tools = HTMXClassToolsExtension()
    htmx_download = HTMXDownloadExtension()
    oob_alternatives = HTMXOobAlternativeExtension()


_RIn = t.TypeVar("_RIn")
_ROut = t.TypeVar("_ROut")
_MaybeAwaitable = t.Union[t.Awaitable[_RIn], _RIn]


class HTMXTransformer(PropertyTransformer):
    NORMAL_KEYS = {
        "hx_get": "hx-get",
        "hx_post": "hx-post",
        "hx_push_url": "hx-push-url",
        "hx_select": "hx-select",
        "hx_select_oob": "hx-select-oob",
        "hx_swap": "hx-swap",
        "hx_swap_oob": "hx-swap-oob",
        "hx_target": "hx-target",
        "hx_trigger": "hx-trigger",
        "hx_vals": "hx-vals",
        "hx_boost": "hx-boost",
        "hx_confirm": "hx-confirm",
        "hx_delete": "hx-delete",
        "hx_disable": "hx-disable",
        "hx_disabled_elt": "hx-disabled-elt",
        "hx_disinherit": "hx-disinherit",
        "hx_encoding": "hx-encoding",
        "hx_ext": "hx-ext",
        "hx_headers": "hx-headers",
        "hx_history": "hx-history",
        "hx_history_elt": "hx-history-elt",
        "hx_include": "hx-include",
        "hx_indicator": "hx-indicator",
        "hx_inherit": "hx-inherit",
        "hx_params": "hx-params",
        "hx_patch": "hx-patch",
        "hx_preserve": "hx-preserve",
        "hx_prompt": "hx-prompt",
        "hx_put": "hx-put",
        "hx_replace_url": "hx-replace-url",
        "hx_request": "hx-request",
        "hx_sync": "hx-sync",
        "hx_validate": "hx-validate",
        "hx_vars": "hx-vars",
    }

    def match(self, key: str, value):
        return key.startswith("hx_")

    def transform(self, key: str, value, element):
        if key in self.NORMAL_KEYS:
            element.props[self.NORMAL_KEYS[key]] = value
            del element.props[key]

        # hx-on:*
        elif key.startswith("hx_on_"):
            if key.startswith("hx_on_htmx_"):
                # Special case for htmx events: hx-on:htmx:*
                prefix = "hx-on:htmx:"
                event = key.removeprefix("hx_on_htmx_")

            elif key.startswith("hx_on__"):
                # Special case for htmx events: hx-on::*
                prefix = "hx-on::"
                event = key.removeprefix("hx_on__")

            else:  # key.startswith("hx_on_")
                # regular events: hx-on:*
                prefix = "hx-on:"
                event = key.removeprefix("hx_on_")

            if "__" in event:
                # some events uses : as a separator, in python we use __ to indicate that
                event = event.replace("__", ":")

            event = event.replace("_", "-")

            new_key = f"{prefix}{event}"

            element.props[new_key] = value
            del element.props[key]


class MoreSimpleTransformer(PropertyTransformer):
    SIMPLE_TRANSFORMERS = {
        "for_": "for",
    }

    def match(self, key, _):
        return key in self.SIMPLE_TRANSFORMERS

    def transform(self, key, value, element):
        element.props[self.SIMPLE_TRANSFORMERS[key]] = value
        del element.props[key]


class PydomHTMXContext(Context):
    @classmethod
    def default(cls) -> "PydomHTMXContext":
        from pydom.context.standard.transformers.html_events_transformer import (
            HTMLEventsTransformer,
        )

        ctx = cls.standard()
        ctx.add_prop_transformer(
            MoreSimpleTransformer(),
            before=[HTMLEventsTransformer],
        )
        ctx.add_prop_transformer(
            HTMXTransformer(),
            before=[HTMLEventsTransformer],
        )
        return ctx

    def add_extensions(self, *extensions: HTMXExtension):
        for extension in extensions:
            match, transform = extension.transformer()
            self.add_prop_transformer(match, transform)


def wrap_non_htmx(non_htmx_wrapper: t.Callable[[_RIn], _ROut], post_process=None):
    def decorator(handler: t.Callable[..., _MaybeAwaitable[_RIn]]):
        async def wrapper(request: Request, **kwargs):
            if handler_need_request:
                kwargs["request"] = request
            inner = await ensure_awaitable(handler(**kwargs))

            post_process_ = post_process or (lambda x: x)
            if request.headers.get("HX-Request") == "true":
                # is an htmx request, return the inner component
                return await ensure_awaitable(post_process_(inner))
            else:
                # not an htmx request, wrap the inner component
                return await ensure_awaitable(post_process_(non_htmx_wrapper(inner)))

        import inspect

        # ensure:
        # - wrapper has the request parameter
        # - wrapper has the same signature as the handler
        # - no duplicate parameters in the signature
        params: t.Dict[inspect.Parameter, None] = {}
        params |= dict.fromkeys(inspect.signature(handler).parameters.values())

        # check if the handler needs the request parameter, so we know to pass it when calling the handler
        handler_need_request = any(p.name == "request" for p in params)

        params |= dict.fromkeys(
            filter(
                lambda p: p.kind
                not in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                ),
                inspect.signature(wrapper).parameters.values(),
            )
        )

        without_default_params = {p: None for p in params if p.default == inspect.Parameter.empty}
        with_default_params = {p: p.default for p in params if p.default != inspect.Parameter.empty}
        params = {**without_default_params, **with_default_params}

        wrapper.__signature__ = inspect.Signature(
            parameters=list(params.keys()),
            return_annotation=inspect.signature(handler).return_annotation,
        )
        wrapper = functools.update_wrapper(wrapper, handler)

        return wrapper

    return decorator
