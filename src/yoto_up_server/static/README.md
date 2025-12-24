# Yoto Up Server Static Files

This folder contains static assets for the Yoto Up Server web interface.

## Structure

```
static/
├── css/
│   └── style.css      # Main stylesheet
└── js/
    └── app.js         # Main JavaScript file
```

## External Dependencies (CDN)

The following libraries are loaded from CDN in the base template:

- **HTMX v2.0.4**: Core library for HTML-driven interactivity
  - Source: https://unpkg.com/htmx.org@2.0.4
  - SSE Extension: https://unpkg.com/htmx-ext-sse@2.2.2/sse.js

## Notes

- All CSS uses CSS variables for theming
- JavaScript is minimal - most interactivity is handled by HTMX
- The app uses HTMX indicators for loading states
- SSE (Server-Sent Events) is used for real-time upload progress
