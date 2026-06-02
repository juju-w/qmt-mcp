# qmt-gateway placeholder

Port `8765` is reserved for a future read-only QMT gateway.

Initial direction:

- Run Windows Python inside the same Wine prefix as MiniQMT and xtquant.
- Start with read-only endpoints such as `/health`, `/qmt/status`, `/account/asset`, `/account/positions`, and `/market/tick`.
- Keep order placement out of the first PoC.
