-- =====================================================================
-- SALESTORM flash-sale platform - PostgreSQL schema (source of truth, tier L4)
-- Rule: "Caches can say NO; only the database can say YES."
-- Tested with PostgreSQL 14+:  psql -v ON_ERROR_STOP=1 -f schema_postgres.sql
-- =====================================================================
BEGIN;

DROP SCHEMA IF EXISTS salestorm CASCADE;
CREATE SCHEMA salestorm;
SET search_path TO salestorm;

-- ---------- Catalog & customers ----------
CREATE TABLE customer (
    customer_id     BIGSERIAL PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    full_name       VARCHAR(200) NOT NULL,
    phone           VARCHAR(30),
    status          VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','BLOCKED')),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE category (
    category_id     BIGSERIAL PRIMARY KEY,
    name            VARCHAR(120) NOT NULL UNIQUE,
    parent_id       BIGINT REFERENCES category(category_id)
);

CREATE TABLE product (
    product_id      BIGSERIAL PRIMARY KEY,
    category_id     BIGINT NOT NULL REFERENCES category(category_id),
    sku             VARCHAR(64)  NOT NULL UNIQUE,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    list_price      NUMERIC(12,2) NOT NULL CHECK (list_price >= 0),
    currency        CHAR(3)      NOT NULL DEFAULT 'INR',
    version         INT          NOT NULL DEFAULT 1,   -- used in versioned cache keys
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_product_category ON product(category_id);

-- ---------- Flash sale ----------
CREATE TABLE sale (
    sale_id         BIGSERIAL PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    starts_at       TIMESTAMPTZ  NOT NULL,
    ends_at         TIMESTAMPTZ  NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'SCHEDULED'
                    CHECK (status IN ('SCHEDULED','LIVE','SOLD_OUT','ENDED','CANCELLED')),
    max_per_customer INT         NOT NULL DEFAULT 1 CHECK (max_per_customer > 0),
    reservation_ttl_seconds INT  NOT NULL DEFAULT 300,
    version         INT          NOT NULL DEFAULT 1,
    CHECK (ends_at > starts_at)
);
CREATE INDEX idx_sale_status_start ON sale(status, starts_at);

CREATE TABLE deal (
    deal_id         BIGSERIAL PRIMARY KEY,
    sale_id         BIGINT NOT NULL REFERENCES sale(sale_id),
    product_id      BIGINT NOT NULL REFERENCES product(product_id),
    deal_price      NUMERIC(12,2) NOT NULL CHECK (deal_price >= 0),
    UNIQUE (sale_id, product_id)
);

CREATE TABLE coupon (
    coupon_id       BIGSERIAL PRIMARY KEY,
    code            VARCHAR(40)  NOT NULL UNIQUE,
    discount_type   VARCHAR(10)  NOT NULL CHECK (discount_type IN ('PERCENT','FLAT')),
    discount_value  NUMERIC(12,2) NOT NULL CHECK (discount_value > 0),
    max_redemptions INT          NOT NULL CHECK (max_redemptions >= 0),
    redeemed_count  INT          NOT NULL DEFAULT 0,
    valid_from      TIMESTAMPTZ  NOT NULL,
    valid_to        TIMESTAMPTZ  NOT NULL,
    CHECK (redeemed_count <= max_redemptions)
);

-- ---------- Inventory (aggregate counter + per-unit rows) ----------
CREATE TABLE inventory (
    inventory_id    BIGSERIAL PRIMARY KEY,
    sale_id         BIGINT NOT NULL REFERENCES sale(sale_id),
    product_id      BIGINT NOT NULL REFERENCES product(product_id),
    total           INT NOT NULL CHECK (total >= 0),
    available       INT NOT NULL CHECK (available >= 0),
    reserved        INT NOT NULL DEFAULT 0 CHECK (reserved >= 0),
    sold            INT NOT NULL DEFAULT 0 CHECK (sold >= 0),
    version         INT NOT NULL DEFAULT 1,               -- optimistic locking alternative
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_inventory_sale_product UNIQUE (sale_id, product_id),
    CONSTRAINT ck_inventory_conservation CHECK (available + reserved + sold = total)
);

CREATE TABLE inventory_unit (
    unit_id         BIGSERIAL PRIMARY KEY,
    inventory_id    BIGINT NOT NULL REFERENCES inventory(inventory_id),
    unit_no         INT    NOT NULL,                       -- 1..100
    status          VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE'
                    CHECK (status IN ('AVAILABLE','RESERVED','SOLD')),
    reservation_id  BIGINT,                                -- FK added after reservation table
    version         INT NOT NULL DEFAULT 1,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (inventory_id, unit_no),
    CHECK ((status = 'AVAILABLE') = (reservation_id IS NULL))
);
-- Partial index makes "find a free unit" cheap even under SKIP LOCKED scans
CREATE INDEX idx_unit_available ON inventory_unit(inventory_id) WHERE status = 'AVAILABLE';

CREATE TABLE inventory_reservation (
    reservation_id  BIGSERIAL PRIMARY KEY,
    sale_id         BIGINT NOT NULL REFERENCES sale(sale_id),
    customer_id     BIGINT NOT NULL REFERENCES customer(customer_id),
    product_id      BIGINT NOT NULL REFERENCES product(product_id),
    unit_id         BIGINT REFERENCES inventory_unit(unit_id),
    status          VARCHAR(20) NOT NULL DEFAULT 'RESERVED'
                    CHECK (status IN ('RESERVED','PAYMENT_PENDING','CONFIRMED','SOLD',
                                      'PAYMENT_FAILED','TIMEOUT','RELEASED')),
    idempotency_key VARCHAR(100) NOT NULL UNIQUE,
    business_key    CHAR(64)     NOT NULL,   -- sha256(customer_id,sale_id,product_id)
    fencing_version INT          NOT NULL DEFAULT 1,  -- bumped on expiry/release; late payment must match
    last_fence_token BIGINT      NOT NULL DEFAULT 0,  -- lease token of the last sweeper write; stale tokens rejected
    expires_at      TIMESTAMPTZ  NOT NULL,            -- event-time deadline (sweeper compares against watermark)
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT uq_reservation_sale_customer UNIQUE (sale_id, customer_id)
);
CREATE INDEX idx_reservation_expiry ON inventory_reservation(expires_at)
    WHERE status IN ('RESERVED','PAYMENT_PENDING');   -- sweeper fallback scan
-- Write-skew guard: a unit can belong to at most one live reservation, whatever the app code does
CREATE UNIQUE INDEX uq_reservation_one_live_per_unit ON inventory_reservation(unit_id)
    WHERE status IN ('RESERVED','PAYMENT_PENDING','CONFIRMED','SOLD');

ALTER TABLE inventory_unit
    ADD CONSTRAINT fk_unit_reservation FOREIGN KEY (reservation_id)
    REFERENCES inventory_reservation(reservation_id);

-- ---------- Idempotency ----------
CREATE TABLE idempotency_record (
    idempotency_key VARCHAR(100) PRIMARY KEY,
    customer_id     BIGINT NOT NULL REFERENCES customer(customer_id),
    endpoint        VARCHAR(100) NOT NULL,          -- e.g. 'POST /sales/{id}/reservations'
    request_hash    CHAR(64)     NOT NULL,          -- same key + different body => 422
    status          VARCHAR(20)  NOT NULL DEFAULT 'IN_PROGRESS'
                    CHECK (status IN ('IN_PROGRESS','COMPLETED','FAILED')),
    response_code   INT,
    response_body   JSONB,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ  NOT NULL
);
CREATE INDEX idx_idem_expires ON idempotency_record(expires_at);

-- ---------- Cart ----------
CREATE TABLE cart (
    cart_id         BIGSERIAL PRIMARY KEY,
    customer_id     BIGINT NOT NULL REFERENCES customer(customer_id),
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','CHECKED_OUT','ABANDONED')),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cart_customer ON cart(customer_id);

CREATE TABLE cart_item (
    cart_item_id    BIGSERIAL PRIMARY KEY,
    cart_id         BIGINT NOT NULL REFERENCES cart(cart_id) ON DELETE CASCADE,
    product_id      BIGINT NOT NULL REFERENCES product(product_id),
    sale_id         BIGINT REFERENCES sale(sale_id),
    reservation_id  BIGINT REFERENCES inventory_reservation(reservation_id),
    quantity        INT NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
    UNIQUE (cart_id, product_id)
);

-- ---------- Orders ----------
CREATE TABLE orders (
    order_id        BIGSERIAL PRIMARY KEY,
    customer_id     BIGINT NOT NULL REFERENCES customer(customer_id),
    reservation_id  BIGINT UNIQUE REFERENCES inventory_reservation(reservation_id), -- one order per reservation
    coupon_id       BIGINT REFERENCES coupon(coupon_id),
    status          VARCHAR(20) NOT NULL DEFAULT 'CREATED'
                    CHECK (status IN ('CREATED','PAYMENT_PENDING','CONFIRMED','PROCESSING','SHIPPED',
                                      'OUT_FOR_DELIVERY','DELIVERED','CANCELLED','REFUNDED')),
    total_amount    NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
    currency        CHAR(3) NOT NULL DEFAULT 'INR',
    idempotency_key VARCHAR(100) NOT NULL UNIQUE,   -- consumer dedupe for PaymentAuthorized events
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_orders_customer_created ON orders(customer_id, created_at DESC);

CREATE TABLE order_item (
    order_item_id   BIGSERIAL PRIMARY KEY,
    order_id        BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id      BIGINT NOT NULL REFERENCES product(product_id),
    unit_id         BIGINT REFERENCES inventory_unit(unit_id),
    quantity        INT NOT NULL CHECK (quantity > 0),
    unit_price      NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0)
);
CREATE INDEX idx_order_item_order ON order_item(order_id);

-- ---------- Payment ----------
CREATE TABLE payment (
    payment_id      BIGSERIAL PRIMARY KEY,
    reservation_id  BIGINT NOT NULL REFERENCES inventory_reservation(reservation_id),
    order_id        BIGINT REFERENCES orders(order_id),   -- null until order persisted
    customer_id     BIGINT NOT NULL REFERENCES customer(customer_id),
    provider        VARCHAR(40)  NOT NULL,                -- adapter name (razorpay, stripe, ...)
    provider_txn_ref VARCHAR(100) UNIQUE,                 -- gateway reference; null until gateway replies
    idempotency_key VARCHAR(100) NOT NULL UNIQUE,         -- same key on every retry => no double charge
    amount          NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    currency        CHAR(3)      NOT NULL DEFAULT 'INR',
    status          VARCHAR(20)  NOT NULL DEFAULT 'INITIATED'
                    CHECK (status IN ('INITIATED','AUTHORIZED','CAPTURED','FAILED','TIMEOUT','VOIDED','REFUNDED')),
    fencing_version INT          NOT NULL,                -- copy of reservation.fencing_version at initiation
    gateway_event_at TIMESTAMPTZ,                         -- event time reported by the PSP (webhook occurred_at)
    failure_reason  VARCHAR(200),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_payment_reservation ON payment(reservation_id);
CREATE INDEX idx_payment_status_updated ON payment(status, updated_at);  -- reconciler scans TIMEOUT
-- At most one live (authorized/captured) payment per reservation => no double charge
CREATE UNIQUE INDEX uq_payment_one_live_per_reservation ON payment(reservation_id)
    WHERE status IN ('AUTHORIZED','CAPTURED');

-- ---------- Fulfilment & notifications ----------
CREATE TABLE shipment (
    shipment_id     BIGSERIAL PRIMARY KEY,
    order_id        BIGINT NOT NULL UNIQUE REFERENCES orders(order_id),
    carrier         VARCHAR(60),
    tracking_number VARCHAR(100) UNIQUE,
    status          VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                    CHECK (status IN ('PENDING','PACKED','SHIPPED','OUT_FOR_DELIVERY','DELIVERED','RETURNED')),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE notification (
    notification_id BIGSERIAL PRIMARY KEY,
    customer_id     BIGINT NOT NULL REFERENCES customer(customer_id),
    channel         VARCHAR(10) NOT NULL CHECK (channel IN ('EMAIL','SMS','PUSH')),
    template        VARCHAR(60) NOT NULL,
    payload         JSONB,
    status          VARCHAR(10) NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED','SENT','FAILED')),
    dedupe_key      VARCHAR(120) NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_notification_customer ON notification(customer_id, created_at DESC);

-- ---------- Transactional outbox & audit ----------
CREATE TABLE outbox_event (
    event_id        UUID PRIMARY KEY,
    aggregate_type  VARCHAR(40)  NOT NULL,     -- RESERVATION, PAYMENT, ORDER, INVENTORY
    aggregate_id    BIGINT       NOT NULL,
    event_type      VARCHAR(60)  NOT NULL,     -- PaymentAuthorized, StockSoldOut, ...
    payload         JSONB        NOT NULL,
    status          VARCHAR(12)  NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','PUBLISHED','FAILED')),
    attempts        INT          NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ  NOT NULL DEFAULT now(),  -- backoff with full jitter, set by the relay
    publisher_fence_token BIGINT,                          -- relay lease token that published it
    occurred_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),   -- event time (business moment), not publish time
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    published_at    TIMESTAMPTZ
);
CREATE INDEX idx_outbox_pending ON outbox_event(next_attempt_at) WHERE status = 'PENDING';

-- ---------- Resilience: inbox (consumer dedupe), leases (fencing), late events ----------
-- Inbox: at-least-once delivery + this PK = effectively-once handling at each consumer
CREATE TABLE inbox_message (
    consumer        VARCHAR(40)  NOT NULL
                    CHECK (consumer IN ('ORDER','NOTIFICATION','SHIPMENT','RECONCILIATION','PAYMENT')),
    message_id      UUID         NOT NULL,             -- = outbox_event.event_id
    event_type      VARCHAR(60)  NOT NULL,
    occurred_at     TIMESTAMPTZ  NOT NULL,             -- event time carried in the message
    processed_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer, message_id)
);
CREATE INDEX idx_inbox_processed ON inbox_message(processed_at);   -- purge rows older than Kafka retention

-- Lease with a monotonically increasing fencing token (sweeper, outbox relay, reconciler leaders)
CREATE TABLE lease (
    lease_name      VARCHAR(80)  PRIMARY KEY,          -- e.g. 'reservation-sweeper:sale-1'
    holder          VARCHAR(100),                      -- pod name of the current leader
    fence_token     BIGINT       NOT NULL DEFAULT 0 CHECK (fence_token >= 0),  -- only ever increases
    expires_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Side output for events that arrive after the watermark (e.g. PSP webhook after reservation expiry)
CREATE TABLE reconciliation_case (
    case_id         BIGSERIAL    PRIMARY KEY,
    source          VARCHAR(40)  NOT NULL CHECK (source IN ('PAYMENT_WEBHOOK','SETTLEMENT_FILE','INVARIANT_JOB')),
    payment_id      BIGINT       REFERENCES payment(payment_id),
    reservation_id  BIGINT       REFERENCES inventory_reservation(reservation_id),
    occurred_at     TIMESTAMPTZ  NOT NULL,             -- event time from the source
    received_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    watermark_at    TIMESTAMPTZ  NOT NULL,             -- watermark when it arrived (occurred_at < watermark => late)
    action          VARCHAR(20)  NOT NULL CHECK (action IN ('VOID_AUTH','REFUND','REATTACH_UNIT','NONE')),
    status          VARCHAR(12)  NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','DONE','FAILED')),
    dedupe_key      VARCHAR(120) NOT NULL UNIQUE,      -- e.g. 'PAYMENT_WEBHOOK:pay_123:authorized'
    CHECK (received_at >= occurred_at - interval '5 minutes')   -- tolerate small clock skew only
);
CREATE INDEX idx_recon_open ON reconciliation_case(status, received_at) WHERE status = 'OPEN';

CREATE TABLE audit_log (
    audit_id        BIGSERIAL PRIMARY KEY,
    actor           VARCHAR(100) NOT NULL,     -- user id / service name
    action          VARCHAR(60)  NOT NULL,
    entity_type     VARCHAR(40)  NOT NULL,
    entity_id       BIGINT       NOT NULL,
    before_state    JSONB,
    after_state     JSONB,
    trace_id        VARCHAR(64),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id, created_at);

COMMIT;

-- =====================================================================
-- Seed: one flash sale of Product X with exactly 100 units
-- =====================================================================
BEGIN;
SET search_path TO salestorm;
INSERT INTO category(name) VALUES ('Electronics');
INSERT INTO product(category_id, sku, name, list_price) VALUES (1, 'PX-001', 'Product X', 49999.00);
INSERT INTO sale(name, starts_at, ends_at, status) VALUES ('Big Bang Flash Sale', now(), now() + interval '1 hour', 'LIVE');
INSERT INTO deal(sale_id, product_id, deal_price) VALUES (1, 1, 9999.00);
INSERT INTO inventory(sale_id, product_id, total, available) VALUES (1, 1, 100, 100);
INSERT INTO inventory_unit(inventory_id, unit_no) SELECT 1, g FROM generate_series(1,100) g;
INSERT INTO customer(email, full_name) SELECT 'user'||g||'@example.com', 'User '||g FROM generate_series(1,5) g;
INSERT INTO lease(lease_name) VALUES ('reservation-sweeper:sale-1'), ('outbox-relay:p0'), ('reconciler');
COMMIT;

-- =====================================================================
-- EXAMPLE TRANSACTIONS (commented; copy into psql to try)
-- =====================================================================

-- (A) Reserve one unit: SKIP LOCKED claim (no hot row; 10 txns grab 10 different units)
-- BEGIN;
--   -- 1. idempotency guard: second insert with same key fails -> return stored response
--   INSERT INTO salestorm.idempotency_record(idempotency_key, customer_id, endpoint, request_hash, expires_at)
--   VALUES ('7f9c...-uuid', 1, 'POST /sales/1/reservations', repeat('a',64), now() + interval '24 hours');
--   -- 2. claim any free unit without waiting on rows other buyers already locked
--   SELECT unit_id FROM salestorm.inventory_unit
--    WHERE inventory_id = 1 AND status = 'AVAILABLE'
--    ORDER BY unit_id
--    FOR UPDATE SKIP LOCKED
--    LIMIT 1;                                   -- returns e.g. 17 ; zero rows => SOLD_OUT
--   -- 3. create reservation (UNIQUE(sale_id,customer_id) blocks a second reservation per buyer)
--   INSERT INTO salestorm.inventory_reservation(sale_id, customer_id, product_id, unit_id, idempotency_key,
--                                     business_key, expires_at)
--   VALUES (1, 1, 1, 17, '7f9c...-uuid', repeat('b',64), now() + interval '5 minutes')
--   RETURNING reservation_id;                  -- e.g. 1
--   UPDATE salestorm.inventory_unit SET status='RESERVED', reservation_id=1, version=version+1, updated_at=now()
--    WHERE unit_id = 17;
--   -- 4. aggregate counter; CHECKs make overselling impossible even if app code is wrong
--   UPDATE salestorm.inventory SET available=available-1, reserved=reserved+1, version=version+1, updated_at=now()
--    WHERE inventory_id = 1 AND available >= 1;
--   UPDATE salestorm.idempotency_record SET status='COMPLETED', response_code=201,
--          response_body='{"reservationId":1}' WHERE idempotency_key='7f9c...-uuid';
-- COMMIT;

-- (B) Conditional UPDATE alternative (single counter row; simple but a hot row at 10k rps)
-- UPDATE salestorm.inventory
--    SET available = available - 1, reserved = reserved + 1, version = version + 1, updated_at = now()
--  WHERE sale_id = 1 AND product_id = 1 AND available >= 1;
-- -- rowcount 1 => reserved ; rowcount 0 => SOLD_OUT (never negative)

-- (C) Optimistic locking alternative (retry on rowcount 0)
-- UPDATE salestorm.inventory SET available = available - 1, reserved = reserved + 1, version = version + 1
--  WHERE inventory_id = 1 AND version = :read_version AND available >= 1;

-- (D) Expiry with fencing (sweeper / delayed-queue handler)
-- BEGIN;
--   UPDATE salestorm.inventory_reservation
--      SET status='TIMEOUT', fencing_version = fencing_version + 1, updated_at = now()
--    WHERE reservation_id = 1 AND status IN ('RESERVED','PAYMENT_PENDING') AND expires_at < now()
--   RETURNING unit_id;
--   UPDATE salestorm.inventory_unit SET status='AVAILABLE', reservation_id=NULL, version=version+1 WHERE unit_id = 17;
--   UPDATE salestorm.inventory SET available=available+1, reserved=reserved-1, version=version+1 WHERE inventory_id=1;
--   UPDATE salestorm.inventory_reservation SET status='RELEASED' WHERE reservation_id = 1;
-- COMMIT;

-- (E) Late payment success must present the fencing token it started with
-- UPDATE salestorm.inventory_reservation SET status='CONFIRMED', updated_at=now()
--  WHERE reservation_id = 1 AND fencing_version = :payment_fencing_version AND status='PAYMENT_PENDING';
-- -- rowcount 0 => reservation expired meanwhile: try to re-attach a free unit (query A step 2), else VOID/REFUND

-- (F) Order consumer: payment authorized -> order + outbox in ONE transaction (idempotent on idempotency_key)
-- BEGIN;
--   INSERT INTO salestorm.orders(customer_id, reservation_id, total_amount, idempotency_key, status)
--   VALUES (1, 1, 9999.00, 'order-for-res-1', 'CONFIRMED')
--   ON CONFLICT (idempotency_key) DO NOTHING;
--   INSERT INTO salestorm.outbox_event(event_id, aggregate_type, aggregate_id, event_type, payload)
--   VALUES (gen_random_uuid(), 'ORDER', 1, 'OrderCreated', '{"orderId":1}');
-- COMMIT;

-- (G) Outbox relay: claim a batch without double-publishing across relay instances
-- SELECT event_id, event_type, payload FROM salestorm.outbox_event
--  WHERE status='PENDING' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 100;

-- (H) Inbox dedupe at a consumer (Order Service): same TX as the business write
-- BEGIN;
--   INSERT INTO salestorm.inbox_message(consumer, message_id, event_type, occurred_at)
--   VALUES ('ORDER', :event_id, 'PaymentAuthorized', :occurred_at)
--   ON CONFLICT DO NOTHING;                    -- 0 rows => already handled: commit offset, do nothing else
--   -- only if 1 row was inserted: INSERT INTO orders ... ; INSERT INTO outbox_event ...
-- COMMIT;

-- (I) Acquire / renew a lease: every new holder gets a strictly larger fence_token
-- UPDATE salestorm.lease
--    SET holder = :me, fence_token = fence_token + 1, expires_at = now() + interval '10 seconds', updated_at = now()
--  WHERE lease_name = 'reservation-sweeper:sale-1' AND (expires_at < now() OR holder = :me)
-- RETURNING fence_token;                       -- 0 rows => someone else is leader

-- (J) Fenced sweeper write: a paused ex-leader with an old token changes nothing
-- UPDATE salestorm.inventory_reservation
--    SET status = 'TIMEOUT', fencing_version = fencing_version + 1, last_fence_token = :token, updated_at = now()
--  WHERE reservation_id = :rid AND status IN ('RESERVED','PAYMENT_PENDING') AND expires_at < :watermark
--    AND last_fence_token <= :token
--    AND :token = (SELECT fence_token FROM salestorm.lease WHERE lease_name = 'reservation-sweeper:sale-1');
-- -- rowcount 0 => stale token (or already handled): stop, re-acquire the lease

-- (K) Late PSP webhook (occurred_at before the watermark, reservation already expired) -> side output
-- INSERT INTO salestorm.reconciliation_case(source, payment_id, reservation_id, occurred_at, watermark_at, action, dedupe_key)
-- VALUES ('PAYMENT_WEBHOOK', :payment_id, :rid, :occurred_at, :watermark, 'VOID_AUTH', 'PAYMENT_WEBHOOK:' || :psp_ref || ':authorized')
-- ON CONFLICT (dedupe_key) DO NOTHING;
