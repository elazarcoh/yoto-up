---
applyTo: '**/*.py'
name: How to use htmx v2
description: Instructions for using htmx v2 in Python files.
---

Syntax:

```python
d.Div(
  hx_get="/some-endpoint",  # hx-get
  hx_target="#some-target",  # hx-target
  hx_swap="innerHTML" ,  # hx-swap
  hx_on__after_request="console.log('Request completed')"  # hx-on::after-request
)(...)
```

Guides:
- Use `hx_get`, `hx_post`, etc. to define the HTTP method and endpoint.
- Use `hx_target` to specify the target element for content replacement.
- Use `hx_swap` to define how the content is swapped (e.g., `innerHTML`, `outerHTML`, etc.).
- Use `hx_on__eventname` to attach JavaScript event handlers for htmx events.
- Ensure that the target element specified in `hx_target` exists in the DOM.
- Polling can be set up with `hx_trigger="load delay:2s"` to refresh content every 2 seconds. `hx_poll` is not a thing.
- Do not use `**{ 'hx-...': '...' }` syntax; use direct keyword arguments instead for clarity.
- In general, prefer htmx over custom JavaScript. If JavaScript is necessary, keep it minimal and focused on user interactions.
- Debounce user input events using `hx_trigger="keyup changed delay:500ms"` to avoid excessive requests.
- Throttle frequent events with `hx_trigger="scroll throttle:200ms"` for scroll events.

