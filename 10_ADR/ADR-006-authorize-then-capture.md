# ADR-006: Authorize-then-capture payments
**Status:** Accepted
**Context:** Payment can succeed while order creation fails; late payments can arrive after reservation expiry.
**Decision:** Authorize at checkout; capture only after the order is persisted; void the authorization on compensation.
**Alternatives:** Direct charge (sale) + refund on failure – refunds take days, cost fees, hurt trust.
**Consequences:** + No "charged without order"; voids are instant. − Two gateway calls; authorizations expire (days), so capture must happen within that window (it does: seconds/minutes).
