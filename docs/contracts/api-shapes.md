# API Response Contract

All API endpoints should return a top-level JSON object in this shape:

```json
{
  "ok": true,
  "data": {}
}
```

## Contract Rules

- `ok` is a boolean indicating whether the request succeeded.
- `data` contains the payload for successful responses.
- For failures, keep `ok: false` and include structured error details (to be specified later).
- Maintain this envelope consistently across backend endpoints.
