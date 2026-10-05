-- =====================================================================
-- SALESTORM flash-sale platform - MySQL 8.0.16+ schema (open in MySQL Workbench:
-- File > Open SQL Script, run; or File > Import > Reverse Engineer MySQL Create Script
-- to get an EER diagram). InnoDB required (row locks, FKs, SKIP LOCKED needs 8.0.1+,
-- enforced CHECK constraints need 8.0.16+).
-- Differences vs Postgres version: JSON instead of JSONB, no partial indexes
-- (emulated with STORED generated columns), BIGINT AUTO_INCREMENT instead of BIGSERIAL.
-- =====================================================================
DROP DATABASE IF EXISTS salestorm;
CREATE DATABASE salestorm CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE salestorm;

CREATE TABLE customer (
    customer_id  BIGINT AUTO_INCREMENT PRIMARY KEY,
    email        VARCHAR(255) NOT NULL UNIQUE,
    full_name    VARCHAR(200) NOT NULL,
    phone        VARCHAR(30),
    status       VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE',
    created_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT ck_customer_status CHECK (status IN ('ACTIVE','BLOCKED'))
) ENGINE=InnoDB;

CREATE TABLE category (
    category_id  BIGINT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(120) NOT NULL UNIQUE,
    parent_id    BIGINT NULL,
    CONSTRAINT fk_category_parent FOREIGN KEY (parent_id) REFERENCES category(category_id)
) ENGINE=InnoDB;

CREATE TABLE product (
    product_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    category_id  BIGINT NOT NULL,
    sku          VARCHAR(64)  NOT NULL UNIQUE,
    name         VARCHAR(200) NOT NULL,
    description  TEXT,
    list_price   DECIMAL(12,2) NOT NULL,
    currency     CHAR(3) NOT NULL DEFAULT 'INR',
    version      INT NOT NULL DEFAULT 1,
    updated_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT ck_product_price CHECK (list_price >= 0),
    CONSTRAINT fk_product_category FOREIGN KEY (category_id) REFERENCES category(category_id),
    INDEX idx_product_category (category_id)
) ENGINE=InnoDB;

CREATE TABLE sale (
    sale_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    starts_at    TIMESTAMP(3) NOT NULL,
    ends_at      TIMESTAMP(3) NOT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'SCHEDULED',
    max_per_customer INT NOT NULL DEFAULT 1,
    reservation_ttl_seconds INT NOT NULL DEFAULT 300,
    version      INT NOT NULL DEFAULT 1,
    CONSTRAINT ck_sale_status CHECK (status IN ('SCHEDULED','LIVE','SOLD_OUT','ENDED','CANCELLED')),
    CONSTRAINT ck_sale_window CHECK (ends_at > starts_at),
    CONSTRAINT ck_sale_max CHECK (max_per_customer > 0),
    INDEX idx_sale_status_start (status, starts_at)
) ENGINE=InnoDB;

CREATE TABLE deal (
    deal_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    sale_id      BIGINT NOT NULL,
    product_id   BIGINT NOT NULL,
    deal_price   DECIMAL(12,2) NOT NULL,
    CONSTRAINT ck_deal_price CHECK (deal_price >= 0),
    CONSTRAINT uq_deal UNIQUE (sale_id, product_id),
    CONSTRAINT fk_deal_sale FOREIGN KEY (sale_id) REFERENCES sale(sale_id),
    CONSTRAINT fk_deal_product FOREIGN KEY (product_id) REFERENCES product(product_id)
) ENGINE=InnoDB;

CREATE TABLE coupon (
    coupon_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
    code         VARCHAR(40) NOT NULL UNIQUE,
    discount_type VARCHAR(10) NOT NULL,
    discount_value DECIMAL(12,2) NOT NULL,
    max_redemptions INT NOT NULL,
    redeemed_count INT NOT NULL DEFAULT 0,
    valid_from   TIMESTAMP(3) NOT NULL,
    valid_to     TIMESTAMP(3) NOT NULL,
    CONSTRAINT ck_coupon_type CHECK (discount_type IN ('PERCENT','FLAT')),
    CONSTRAINT ck_coupon_value CHECK (discount_value > 0),
    CONSTRAINT ck_coupon_redeem CHECK (redeemed_count <= max_redemptions)
) ENGINE=InnoDB;

CREATE TABLE inventory (
    inventory_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sale_id      BIGINT NOT NULL,
    product_id   BIGINT NOT NULL,
    total        INT NOT NULL,
    available    INT NOT NULL,
    reserved     INT NOT NULL DEFAULT 0,
    sold         INT NOT NULL DEFAULT 0,
    version      INT NOT NULL DEFAULT 1,
    updated_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT uq_inventory_sale_product UNIQUE (sale_id, product_id),
    CONSTRAINT ck_inv_nonneg CHECK (total >= 0 AND available >= 0 AND reserved >= 0 AND sold >= 0),
    CONSTRAINT ck_inventory_conservation CHECK (available + reserved + sold = total),
    CONSTRAINT fk_inventory_sale FOREIGN KEY (sale_id) REFERENCES sale(sale_id),
    CONSTRAINT fk_inventory_product FOREIGN KEY (product_id) REFERENCES product(product_id)
) ENGINE=InnoDB;

CREATE TABLE inventory_unit (
    unit_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    inventory_id BIGINT NOT NULL,
    unit_no      INT NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    reservation_id BIGINT NULL,
    version      INT NOT NULL DEFAULT 1,
    updated_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT uq_unit UNIQUE (inventory_id, unit_no),
    CONSTRAINT ck_unit_status CHECK (status IN ('AVAILABLE','RESERVED','SOLD')),
    CONSTRAINT fk_unit_inventory FOREIGN KEY (inventory_id) REFERENCES inventory(inventory_id),
    INDEX idx_unit_status (inventory_id, status)   -- MySQL has no partial index
) ENGINE=InnoDB;

CREATE TABLE inventory_reservation (
    reservation_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sale_id      BIGINT NOT NULL,
    customer_id  BIGINT NOT NULL,
    product_id   BIGINT NOT NULL,
    unit_id      BIGINT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'RESERVED',
    idempotency_key VARCHAR(100) NOT NULL,
    business_key CHAR(64) NOT NULL,
    fencing_version INT NOT NULL DEFAULT 1,
    last_fence_token BIGINT NOT NULL DEFAULT 0,   -- lease token of last sweeper write; stale tokens rejected
    expires_at   TIMESTAMP(3) NOT NULL,
    created_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT uq_reservation_idem UNIQUE (idempotency_key),
    CONSTRAINT uq_reservation_sale_customer UNIQUE (sale_id, customer_id),
    CONSTRAINT ck_res_status CHECK (status IN ('RESERVED','PAYMENT_PENDING','CONFIRMED','SOLD',
                                               'PAYMENT_FAILED','TIMEOUT','RELEASED')),
    CONSTRAINT fk_res_sale FOREIGN KEY (sale_id) REFERENCES sale(sale_id),
    CONSTRAINT fk_res_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    CONSTRAINT fk_res_product FOREIGN KEY (product_id) REFERENCES product(product_id),
    CONSTRAINT fk_res_unit FOREIGN KEY (unit_id) REFERENCES inventory_unit(unit_id),
    INDEX idx_reservation_expiry (status, expires_at),
    -- emulates the Postgres partial unique index: one live reservation per unit (write-skew guard)
    live_unit_id BIGINT GENERATED ALWAYS AS
        (CASE WHEN status IN ('RESERVED','PAYMENT_PENDING','CONFIRMED','SOLD') THEN unit_id ELSE NULL END) STORED,
    CONSTRAINT uq_reservation_one_live_per_unit UNIQUE (live_unit_id)
) ENGINE=InnoDB;

ALTER TABLE inventory_unit
    ADD CONSTRAINT fk_unit_reservation FOREIGN KEY (reservation_id)
        REFERENCES inventory_reservation(reservation_id);

CREATE TABLE idempotency_record (
    idempotency_key VARCHAR(100) PRIMARY KEY,
    customer_id  BIGINT NOT NULL,
    endpoint     VARCHAR(100) NOT NULL,
    request_hash CHAR(64) NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'IN_PROGRESS',
    response_code INT NULL,
    response_body JSON NULL,
    created_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    expires_at   TIMESTAMP(3) NOT NULL,
    CONSTRAINT ck_idem_status CHECK (status IN ('IN_PROGRESS','COMPLETED','FAILED')),
    CONSTRAINT fk_idem_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    INDEX idx_idem_expires (expires_at)
) ENGINE=InnoDB;

CREATE TABLE cart (
    cart_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id  BIGINT NOT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    updated_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT ck_cart_status CHECK (status IN ('ACTIVE','CHECKED_OUT','ABANDONED')),
    CONSTRAINT fk_cart_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    INDEX idx_cart_customer (customer_id)
) ENGINE=InnoDB;

CREATE TABLE cart_item (
    cart_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    cart_id      BIGINT NOT NULL,
    product_id   BIGINT NOT NULL,
    sale_id      BIGINT NULL,
    reservation_id BIGINT NULL,
    quantity     INT NOT NULL,
    unit_price   DECIMAL(12,2) NOT NULL,
    CONSTRAINT uq_cart_item UNIQUE (cart_id, product_id),
    CONSTRAINT ck_cart_item CHECK (quantity > 0 AND unit_price >= 0),
    CONSTRAINT fk_ci_cart FOREIGN KEY (cart_id) REFERENCES cart(cart_id) ON DELETE CASCADE,
    CONSTRAINT fk_ci_product FOREIGN KEY (product_id) REFERENCES product(product_id),
    CONSTRAINT fk_ci_sale FOREIGN KEY (sale_id) REFERENCES sale(sale_id),
    CONSTRAINT fk_ci_res FOREIGN KEY (reservation_id) REFERENCES inventory_reservation(reservation_id)
) ENGINE=InnoDB;

CREATE TABLE orders (
    order_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id  BIGINT NOT NULL,
    reservation_id BIGINT NULL,
    coupon_id    BIGINT NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'CREATED',
    total_amount DECIMAL(12,2) NOT NULL,
    currency     CHAR(3) NOT NULL DEFAULT 'INR',
    idempotency_key VARCHAR(100) NOT NULL,
    created_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT uq_orders_reservation UNIQUE (reservation_id),
    CONSTRAINT uq_orders_idem UNIQUE (idempotency_key),
    CONSTRAINT ck_orders_status CHECK (status IN ('CREATED','PAYMENT_PENDING','CONFIRMED','PROCESSING','SHIPPED',
                                                  'OUT_FOR_DELIVERY','DELIVERED','CANCELLED','REFUNDED')),
    CONSTRAINT ck_orders_amount CHECK (total_amount >= 0),
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    CONSTRAINT fk_orders_res FOREIGN KEY (reservation_id) REFERENCES inventory_reservation(reservation_id),
    CONSTRAINT fk_orders_coupon FOREIGN KEY (coupon_id) REFERENCES coupon(coupon_id),
    INDEX idx_orders_customer_created (customer_id, created_at)
) ENGINE=InnoDB;

CREATE TABLE order_item (
    order_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id     BIGINT NOT NULL,
    product_id   BIGINT NOT NULL,
    unit_id      BIGINT NULL,
    quantity     INT NOT NULL,
    unit_price   DECIMAL(12,2) NOT NULL,
    CONSTRAINT ck_order_item CHECK (quantity > 0 AND unit_price >= 0),
    CONSTRAINT fk_oi_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    CONSTRAINT fk_oi_product FOREIGN KEY (product_id) REFERENCES product(product_id),
    CONSTRAINT fk_oi_unit FOREIGN KEY (unit_id) REFERENCES inventory_unit(unit_id)
) ENGINE=InnoDB;

CREATE TABLE payment (
    payment_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    reservation_id BIGINT NOT NULL,
    order_id     BIGINT NULL,
    customer_id  BIGINT NOT NULL,
    provider     VARCHAR(40) NOT NULL,
    provider_txn_ref VARCHAR(100) NULL,
    idempotency_key VARCHAR(100) NOT NULL,
    amount       DECIMAL(12,2) NOT NULL,
    currency     CHAR(3) NOT NULL DEFAULT 'INR',
    status       VARCHAR(20) NOT NULL DEFAULT 'INITIATED',
    fencing_version INT NOT NULL,
    gateway_event_at TIMESTAMP(3) NULL,            -- event time reported by the PSP webhook
    failure_reason VARCHAR(200) NULL,
    created_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    -- emulates Postgres partial unique index: one AUTHORIZED/CAPTURED payment per reservation
    live_reservation_id BIGINT GENERATED ALWAYS AS
        (CASE WHEN status IN ('AUTHORIZED','CAPTURED') THEN reservation_id ELSE NULL END) STORED,
    CONSTRAINT uq_payment_txn UNIQUE (provider_txn_ref),
    CONSTRAINT uq_payment_idem UNIQUE (idempotency_key),
    CONSTRAINT uq_payment_one_live UNIQUE (live_reservation_id),
    CONSTRAINT ck_payment_status CHECK (status IN ('INITIATED','AUTHORIZED','CAPTURED','FAILED','TIMEOUT','VOIDED','REFUNDED')),
    CONSTRAINT ck_payment_amount CHECK (amount > 0),
    CONSTRAINT fk_pay_res FOREIGN KEY (reservation_id) REFERENCES inventory_reservation(reservation_id),
    CONSTRAINT fk_pay_order FOREIGN KEY (order_id) REFERENCES orders(order_id),
    CONSTRAINT fk_pay_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    INDEX idx_payment_status_updated (status, updated_at)
) ENGINE=InnoDB;

CREATE TABLE shipment (
    shipment_id  BIGINT AUTO_INCREMENT PRIMARY KEY,
    order_id     BIGINT NOT NULL,
    carrier      VARCHAR(60) NULL,
    tracking_number VARCHAR(100) NULL,
    status       VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    updated_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT uq_shipment_order UNIQUE (order_id),
    CONSTRAINT uq_shipment_tracking UNIQUE (tracking_number),
    CONSTRAINT ck_shipment_status CHECK (status IN ('PENDING','PACKED','SHIPPED','OUT_FOR_DELIVERY','DELIVERED','RETURNED')),
    CONSTRAINT fk_ship_order FOREIGN KEY (order_id) REFERENCES orders(order_id)
) ENGINE=InnoDB;

CREATE TABLE notification (
    notification_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id  BIGINT NOT NULL,
    channel      VARCHAR(10) NOT NULL,
    template     VARCHAR(60) NOT NULL,
    payload      JSON NULL,
    status       VARCHAR(10) NOT NULL DEFAULT 'QUEUED',
    dedupe_key   VARCHAR(120) NOT NULL,
    created_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    CONSTRAINT uq_notification_dedupe UNIQUE (dedupe_key),
    CONSTRAINT ck_notif_channel CHECK (channel IN ('EMAIL','SMS','PUSH')),
    CONSTRAINT ck_notif_status CHECK (status IN ('QUEUED','SENT','FAILED')),
    CONSTRAINT fk_notif_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    INDEX idx_notification_customer (customer_id, created_at)
) ENGINE=InnoDB;

CREATE TABLE outbox_event (
    event_id     CHAR(36) PRIMARY KEY,
    aggregate_type VARCHAR(40) NOT NULL,
    aggregate_id BIGINT NOT NULL,
    event_type   VARCHAR(60) NOT NULL,
    payload      JSON NOT NULL,
    status       VARCHAR(12) NOT NULL DEFAULT 'PENDING',
    attempts     INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),   -- backoff + full jitter
    publisher_fence_token BIGINT NULL,
    occurred_at  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),      -- event time
    created_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    published_at TIMESTAMP(3) NULL,
    CONSTRAINT ck_outbox_status CHECK (status IN ('PENDING','PUBLISHED','FAILED')),
    INDEX idx_outbox_pending (status, next_attempt_at)
) ENGINE=InnoDB;

-- ---------- Resilience: inbox, leases (fencing), late events ----------
CREATE TABLE inbox_message (
    consumer     VARCHAR(40) NOT NULL,
    message_id   CHAR(36) NOT NULL,              -- = outbox_event.event_id
    event_type   VARCHAR(60) NOT NULL,
    occurred_at  TIMESTAMP(3) NOT NULL,
    processed_at TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    PRIMARY KEY (consumer, message_id),
    CONSTRAINT ck_inbox_consumer CHECK (consumer IN ('ORDER','NOTIFICATION','SHIPMENT','RECONCILIATION','PAYMENT')),
    INDEX idx_inbox_processed (processed_at)
) ENGINE=InnoDB;

CREATE TABLE lease (
    lease_name   VARCHAR(80) PRIMARY KEY,
    holder       VARCHAR(100) NULL,
    fence_token  BIGINT NOT NULL DEFAULT 0,
    expires_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    updated_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3) ON UPDATE CURRENT_TIMESTAMP(3),
    CONSTRAINT ck_lease_token CHECK (fence_token >= 0)
) ENGINE=InnoDB;

CREATE TABLE reconciliation_case (
    case_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    source       VARCHAR(40) NOT NULL,
    payment_id   BIGINT NULL,
    reservation_id BIGINT NULL,
    occurred_at  TIMESTAMP(3) NOT NULL,
    received_at  TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    watermark_at TIMESTAMP(3) NOT NULL,
    action       VARCHAR(20) NOT NULL,
    status       VARCHAR(12) NOT NULL DEFAULT 'OPEN',
    dedupe_key   VARCHAR(120) NOT NULL,
    CONSTRAINT uq_recon_dedupe UNIQUE (dedupe_key),
    CONSTRAINT ck_recon_source CHECK (source IN ('PAYMENT_WEBHOOK','SETTLEMENT_FILE','INVARIANT_JOB')),
    CONSTRAINT ck_recon_action CHECK (action IN ('VOID_AUTH','REFUND','REATTACH_UNIT','NONE')),
    CONSTRAINT ck_recon_status CHECK (status IN ('OPEN','DONE','FAILED')),
    CONSTRAINT fk_recon_payment FOREIGN KEY (payment_id) REFERENCES payment(payment_id),
    CONSTRAINT fk_recon_res FOREIGN KEY (reservation_id) REFERENCES inventory_reservation(reservation_id),
    INDEX idx_recon_open (status, received_at)
) ENGINE=InnoDB;

CREATE TABLE audit_log (
    audit_id     BIGINT AUTO_INCREMENT PRIMARY KEY,
    actor        VARCHAR(100) NOT NULL,
    action       VARCHAR(60) NOT NULL,
    entity_type  VARCHAR(40) NOT NULL,
    entity_id    BIGINT NOT NULL,
    before_state JSON NULL,
    after_state  JSON NULL,
    trace_id     VARCHAR(64) NULL,
    created_at   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
    INDEX idx_audit_entity (entity_type, entity_id, created_at)
) ENGINE=InnoDB;

-- ---------- Seed: 100 units of Product X ----------
INSERT INTO category(name) VALUES ('Electronics');
INSERT INTO product(category_id, sku, name, list_price) VALUES (1, 'PX-001', 'Product X', 49999.00);
INSERT INTO sale(name, starts_at, ends_at, status)
VALUES ('Big Bang Flash Sale', CURRENT_TIMESTAMP(3), CURRENT_TIMESTAMP(3) + INTERVAL 1 HOUR, 'LIVE');
INSERT INTO deal(sale_id, product_id, deal_price) VALUES (1, 1, 9999.00);
INSERT INTO inventory(sale_id, product_id, total, available) VALUES (1, 1, 100, 100);
INSERT INTO inventory_unit(inventory_id, unit_no)
WITH RECURSIVE seq(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM seq WHERE n < 100)
SELECT 1, n FROM seq;
INSERT INTO lease(lease_name) VALUES ('reservation-sweeper:sale-1'), ('outbox-relay:p0'), ('reconciler');

-- =====================================================================
-- EXAMPLE TRANSACTIONS (commented)
-- =====================================================================
-- (A) SKIP LOCKED claim (MySQL 8.0.1+)
-- START TRANSACTION;
--   SELECT unit_id FROM inventory_unit
--    WHERE inventory_id = 1 AND status = 'AVAILABLE'
--    ORDER BY unit_id LIMIT 1
--    FOR UPDATE SKIP LOCKED;                 -- zero rows => SOLD_OUT
--   INSERT INTO inventory_reservation(sale_id, customer_id, product_id, unit_id, idempotency_key, business_key, expires_at)
--   VALUES (1, 1, 1, @unit, 'uuid-key', SHA2('1|1|1',256), CURRENT_TIMESTAMP(3) + INTERVAL 5 MINUTE);
--   UPDATE inventory_unit SET status='RESERVED', reservation_id=LAST_INSERT_ID(), version=version+1 WHERE unit_id=@unit;
--   UPDATE inventory SET available=available-1, reserved=reserved+1, version=version+1
--    WHERE inventory_id=1 AND available >= 1;
-- COMMIT;
-- (B) Conditional UPDATE: ROW_COUNT() = 0 => SOLD_OUT
-- UPDATE inventory SET available=available-1, reserved=reserved+1, version=version+1
--  WHERE sale_id=1 AND product_id=1 AND available >= 1;
-- SELECT ROW_COUNT();
-- (C) Late payment fencing
-- UPDATE inventory_reservation SET status='CONFIRMED'
--  WHERE reservation_id=@r AND fencing_version=@fv AND status='PAYMENT_PENDING';

-- (H) Inbox dedupe:  INSERT IGNORE INTO inbox_message(consumer, message_id, event_type, occurred_at) VALUES ('ORDER', @eid, 'PaymentAuthorized', @occ);
--     ROW_COUNT() = 0  => already processed, skip the business write.
-- (I) Lease:  UPDATE lease SET holder=@me, fence_token=fence_token+1, expires_at=CURRENT_TIMESTAMP(3)+INTERVAL 10 SECOND
--             WHERE lease_name='reservation-sweeper:sale-1' AND (expires_at < CURRENT_TIMESTAMP(3) OR holder=@me);
-- (J) Fenced write: UPDATE inventory_reservation SET status='TIMEOUT', last_fence_token=@tok
--             WHERE reservation_id=@r AND last_fence_token <= @tok
--               AND @tok = (SELECT fence_token FROM lease WHERE lease_name='reservation-sweeper:sale-1');
