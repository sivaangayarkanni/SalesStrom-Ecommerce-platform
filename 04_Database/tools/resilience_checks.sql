-- Behaviour checks for the resilience tables (run AFTER schema_postgres.sql):
--   psql -v ON_ERROR_STOP=1 -f schema_postgres.sql && psql -v ON_ERROR_STOP=1 -f resilience_checks.sql
-- Every block raises an exception if the guard does not hold. Changes are rolled back at the end.
BEGIN;
SET search_path TO salestorm;
-- setup: customer 1 reserves unit 17 (expired)
INSERT INTO inventory_reservation(sale_id, customer_id, product_id, unit_id, idempotency_key, business_key, expires_at)
VALUES (1, 1, 1, 17, 'k-1', repeat('b',64), now() - interval '1 minute');
UPDATE inventory_unit SET status='RESERVED', reservation_id=1 WHERE unit_id=17;

DO $$
DECLARE tok_a BIGINT; tok_b BIGINT; n INT;
BEGIN
  -- 1. Fencing: sweeper A takes the lease, "pauses", lease expires, sweeper B takes it
  UPDATE lease SET holder='sweeper-a', fence_token=fence_token+1, expires_at=now()-interval '1 second'
   WHERE lease_name='reservation-sweeper:sale-1' RETURNING fence_token INTO tok_a;
  UPDATE lease SET holder='sweeper-b', fence_token=fence_token+1, expires_at=now()+interval '10 seconds'
   WHERE lease_name='reservation-sweeper:sale-1' AND (expires_at < now() OR holder='sweeper-b')
   RETURNING fence_token INTO tok_b;
  IF tok_b IS NULL OR tok_b <= tok_a THEN RAISE EXCEPTION 'lease not taken over with larger token'; END IF;
  UPDATE inventory_reservation SET status='TIMEOUT', fencing_version=fencing_version+1, last_fence_token=tok_b
   WHERE reservation_id=1 AND status IN ('RESERVED','PAYMENT_PENDING') AND expires_at < now()
     AND last_fence_token <= tok_b
     AND tok_b = (SELECT fence_token FROM lease WHERE lease_name='reservation-sweeper:sale-1');
  GET DIAGNOSTICS n = ROW_COUNT; IF n <> 1 THEN RAISE EXCEPTION 'current leader write failed'; END IF;
  -- A wakes up with the old token and tries to touch the same row
  UPDATE inventory_reservation SET status='RELEASED', last_fence_token=tok_a
   WHERE reservation_id=1 AND last_fence_token <= tok_a
     AND tok_a = (SELECT fence_token FROM lease WHERE lease_name='reservation-sweeper:sale-1');
  GET DIAGNOSTICS n = ROW_COUNT; IF n <> 0 THEN RAISE EXCEPTION 'stale fencing token was accepted'; END IF;
  RAISE NOTICE 'fencing: token % accepted, stale token % rejected', tok_b, tok_a;

  -- 2. Inbox: the same message delivered twice is handled once
  INSERT INTO inbox_message(consumer, message_id, event_type, occurred_at)
  VALUES ('ORDER','11111111-1111-1111-1111-111111111111','PaymentAuthorized', now()) ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT; IF n <> 1 THEN RAISE EXCEPTION 'first delivery not recorded'; END IF;
  INSERT INTO inbox_message(consumer, message_id, event_type, occurred_at)
  VALUES ('ORDER','11111111-1111-1111-1111-111111111111','PaymentAuthorized', now()) ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT; IF n <> 0 THEN RAISE EXCEPTION 'duplicate delivery not deduped'; END IF;
  -- a different consumer group handles the same message independently
  INSERT INTO inbox_message(consumer, message_id, event_type, occurred_at)
  VALUES ('NOTIFICATION','11111111-1111-1111-1111-111111111111','PaymentAuthorized', now()) ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS n = ROW_COUNT; IF n <> 1 THEN RAISE EXCEPTION 'per-consumer inbox broken'; END IF;
  RAISE NOTICE 'inbox: duplicate delivery ignored';

  -- 3. Write skew: a second live reservation on unit 18 must fail even if app code skipped the row lock
  INSERT INTO inventory_reservation(sale_id, customer_id, product_id, unit_id, idempotency_key, business_key, expires_at)
  VALUES (1, 2, 1, 18, 'k-2', repeat('c',64), now() + interval '5 minutes');
  BEGIN
    INSERT INTO inventory_reservation(sale_id, customer_id, product_id, unit_id, idempotency_key, business_key, expires_at)
    VALUES (1, 3, 1, 18, 'k-3', repeat('d',64), now() + interval '5 minutes');
    RAISE EXCEPTION 'two live reservations on one unit were allowed';
  EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'write skew: second reservation on unit 18 rejected';
  END;
  -- and counters can never go negative / break conservation
  BEGIN
    UPDATE inventory SET available = available - 101, sold = sold + 101 WHERE inventory_id = 1;
    RAISE EXCEPTION 'oversell accepted';
  EXCEPTION WHEN check_violation THEN RAISE NOTICE 'oversell: CHECK constraint rejected sold=101';
  END;
END $$;
ROLLBACK;
