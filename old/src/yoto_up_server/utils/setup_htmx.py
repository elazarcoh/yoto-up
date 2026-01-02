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
        self.script = PartialScript(
            src=f"https://unpkg.com/htmx-ext-sse@{version}/sse.js"
        )


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
    link = (
        "https://github.com/bigskysoftware/htmx-extensions/tree/main/src/loading-states"
    )
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
        self.script = PartialScript(src=f"https://unpkg.com/htmx-ext-class-tools@{version}/class-tools.js")


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


def _test_htmx_transformer():
    htmx_attributes = {
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
    htmx_events = {
        "hx_on_htmx_abort": "hx-on:htmx:abort",
        "hx_on_htmx_after_on_load": "hx-on:htmx:after-on-load",
        "hx_on_htmx_after_process_node": "hx-on:htmx:after-process-node",
        "hx_on_htmx_after_request": "hx-on:htmx:after-request",
        "hx_on_htmx_after_settle": "hx-on:htmx:after-settle",
        "hx_on_htmx_after_swap": "hx-on:htmx:after-swap",
        "hx_on_htmx_before_cleanup_element": "hx-on:htmx:before-cleanup-element",
        "hx_on_htmx_before_on_load": "hx-on:htmx:before-on-load",
        "hx_on_htmx_before_process_node": "hx-on:htmx:before-process-node",
        "hx_on_htmx_before_request": "hx-on:htmx:before-request",
        "hx_on_htmx_before_swap": "hx-on:htmx:before-swap",
        "hx_on_htmx_before_send": "hx-on:htmx:before-send",
        "hx_on_htmx_config_request": "hx-on:htmx:config-request",
        "hx_on_htmx_confirm": "hx-on:htmx:confirm",
        "hx_on_htmx_history_cache_error": "hx-on:htmx:history-cache-error",
        "hx_on_htmx_history_cache_miss": "hx-on:htmx:history-cache-miss",
        "hx_on_htmx_history_cache_miss_error": "hx-on:htmx:history-cache-miss-error",
        "hx_on_htmx_history_cache_miss_load": "hx-on:htmx:history-cache-miss-load",
        "hx_on_htmx_history_restore": "hx-on:htmx:history-restore",
        "hx_on_htmx_before_history_save": "hx-on:htmx:before-history-save",
        "hx_on_htmx_load": "hx-on:htmx:load",
        "hx_on_htmx_no_sse_source_error": "hx-on:htmx:no-sse-source-error",
        "hx_on_htmx_on_load_error": "hx-on:htmx:on-load-error",
        "hx_on_htmx_oob_after_swap": "hx-on:htmx:oob-after-swap",
        "hx_on_htmx_oob_before_swap": "hx-on:htmx:oob-before-swap",
        "hx_on_htmx_oob_error_no_target": "hx-on:htmx:oob-error-no-target",
        "hx_on_htmx_prompt": "hx-on:htmx:prompt",
        "hx_on_htmx_pushed_into_history": "hx-on:htmx:pushed-into-history",
        "hx_on_htmx_response_error": "hx-on:htmx:response-error",
        "hx_on_htmx_send_error": "hx-on:htmx:send-error",
        "hx_on_htmx_sse_error": "hx-on:htmx:sse-error",
        "hx_on_htmx_sse_open": "hx-on:htmx:sse-open",
        "hx_on_htmx_swap_error": "hx-on:htmx:swap-error",
        "hx_on_htmx_target_error": "hx-on:htmx:target-error",
        "hx_on_htmx_timeout": "hx-on:htmx:timeout",
        "hx_on_htmx_validation__validate": "hx-on:htmx:validation:validate",
        "hx_on_htmx_validation__failed": "hx-on:htmx:validation:failed",
        "hx_on_htmx_validation__halted": "hx-on:htmx:validation:halted",
        "hx_on_htmx_xhr__abort": "hx-on:htmx:xhr:abort",
        "hx_on_htmx_xhr__loadend": "hx-on:htmx:xhr:loadend",
        "hx_on_htmx_xhr__loadstart": "hx-on:htmx:xhr:loadstart",
        "hx_on_htmx_xhr__progress": "hx-on:htmx:xhr:progress",
    }
    htmx_events_short = {
        k.replace("hx_on_htmx_", "hx_on__"): v.replace("hx-on:htmx:", "hx-on::")
        for k, v in htmx_events.items()
    }
    some_normal_events = {
        "hx_on_click": "hx-on:click",
        "hx_on_mouseover": "hx-on:mouseover",
        "hx_on_mouseout": "hx-on:mouseout",
        "hx_on_mouseenter": "hx-on:mouseenter",
        "hx_on_mouseleave": "hx-on:mouseleave",
        "hx_on_focus": "hx-on:focus",
    }

    context = PydomHTMXContext.default()

    from pydom.html import Div
    from pydom.rendering.props import transform_props
    from pydom.rendering.tree import ElementNode
    from pydom.rendering.tree.nodes import ContextNode

    def test_transformer(key, value, expected):
        element = Div(**{key: value})
        element = ElementNode(
            tag_name=element.tag_name, props=element.props, children=[]
        )
        element_dict = transform_props(
            ContextNode(element, context=context), context=context
        )
        assert expected in element_dict, (
            f"Expected key {expected} not found ({element_dict}, {key=}, {value=})"
        )  # nosec: B101

    for key, expected in htmx_attributes.items():
        test_transformer(key, "value", expected)

    for key, expected in htmx_events.items():
        test_transformer(key, "alert('hello')", expected)

    for key, expected in htmx_events_short.items():
        test_transformer(key, "alert('hello')", expected)

    for key, expected in some_normal_events.items():
        test_transformer(key, "alert('hello')", expected)


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

        without_default_params = {
            p: None for p in params if p.default == inspect.Parameter.empty
        }
        with_default_params = {
            p: p.default for p in params if p.default != inspect.Parameter.empty
        }
        params = {**without_default_params, **with_default_params}

        wrapper.__signature__ = inspect.Signature(
            parameters=list(params.keys()),
            return_annotation=inspect.signature(handler).return_annotation,
        )
        wrapper = functools.update_wrapper(wrapper, handler)

        return wrapper

    return decorator


def generate_typing_overrides(root_folder):
    from pathlib import Path

    html_element_props_relative_path = Path("pydom/types/html/html_element_props.pyi")
    html_element_props_content = f"""\
# This file is generated by {Path(__file__).name}

from typing_extensions import TypedDict, Literal
from pydom.types.html.aria_props import AriaProps
from pydom.types.html.html_element import HTMLElement
from pydom.types.html.html_event_props import HTMLEventProps

SwapValues = Literal[
    "innerHTML",
    "outerHTML",
    "textContent",
    "beforebegin",
    "afterbegin",
    "beforeend",
    "afterend",
    "delete",
    "none",
]
TargetValues = Literal[
    "this",
    "closest ",
    "find ",
    "next",
    "next ",
    "previous",
    "previous ",
]
EventValues = Literal[
    "click",
    "submit",
    "change",
    # non-standard
    "load",
    "revealed",
    "intersect",
]
ParamsValues = Literal[
    "*",
    "none",
    "not ",
]

class HTMXProps(TypedDict, total=False):
    hx_get: str
    hx_post: str
    hx_get: str
    hx_post: str
    hx_push_url: str | Literal["true", "false"]
    hx_select: str
    hx_select_oob: str
    hx_swap: SwapValues | str
    hx_swap_oob: Literal[True] | SwapValues | str
    hx_target: TargetValues | str
    hx_trigger: EventValues | str
    hx_vals: str
    hx_boost: Literal[True, "true", "false"]
    hx_confirm: str
    hx_delete: str
    hx_disable: Literal[True]
    hx_disabled_elt: TargetValues | str
    hx_disinherit: str
    hx_encoding: str
    hx_ext: str
    hx_headers: str
    hx_history: Literal["false"]
    hx_history_elt: Literal[True]
    hx_include: TargetValues | str
    hx_indicator: TargetValues | str
    hx_inherit: str
    hx_params: ParamsValues | str
    hx_patch: str
    hx_preserve: Literal[True]
    hx_prompt: str
    hx_put: str
    hx_replace_url: Literal["true", "false"] | str
    hx_request: str
    hx_sync: str
    hx_validate: Literal["true", True]
    hx_vars: str

    # TODO: events
    # hx-on:htmx:*
    # hx-on::*
    # hx-on:*

class HTMXSSE(TypedDict, total=False):
    sse_connect: str
    sse_swap: str
    sse_close: str

class HTMXWebSocketExtension(TypedDict, total=False):
    ws_connect: str
    ws_send: str

class HTMXExtensions(HTMXSSE, HTMXWebSocketExtension):
    pass

class CustomAttributes(TypedDict, total=False):
    for_: str

# fmt:off
class HTMLElementProps(
    HTMLElement, AriaProps, HTMLEventProps,
    HTMXProps, HTMXExtensions,
    CustomAttributes
):
    pass
# fmt:on

    """

    html_element_props_file = Path(root_folder) / html_element_props_relative_path
    html_element_props_file.parent.mkdir(parents=True, exist_ok=True)
    html_element_props_file.write_text(html_element_props_content)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "typings_root_folder",
        help="The root folder of the typings",
    )
    args = parser.parse_args()

    generate_typing_overrides(args.typings_root_folder)
