import sqlite3
import unittest

from resolver import db

SAMPLE_ORDER = {
    "record_id": "REC0001",
    "razorpay_payment_id": "pay_test0001",
    "order_id": "ORD1001",
    "amount": 41397,
    "razorpay_status": "captured",
    "merchant_order_status": "SUCCESS",
    "event_type": "PAYMENT_UPDATE",
    "timestamp": "2026-09-01T09:03:00",
}

SAMPLE_AUDIT_ROW = {
    "record_id": "REC0001",
    "correlation_ok": 1,
    "razorpay_status": "captured",
    "merchant_status": "SUCCESS",
    "drift_direction": "MATCH",
    "action_taken": "VERIFIED_IN_SYNC",
    "reason": "razorpay_status and merchant_order_status both resolve to SUCCESS",
    "timestamp": "2026-09-01T09:03:00",
}


def make_test_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    db.reset_schema(conn)
    db.seed_orders_batch(conn, [SAMPLE_ORDER])
    return conn


class TestInsertAuditRowIdempotency(unittest.TestCase):
    def test_duplicate_insert_is_rejected_not_duplicated(self):
        """Submitting the identical record_id twice must not create a
        second audit_log row — this is the record_id primary key
        idempotency guarantee, exercised directly rather than just
        confirmed by hand."""
        conn = make_test_connection()

        first_inserted = db.insert_audit_row(conn, SAMPLE_AUDIT_ROW)
        second_inserted = db.insert_audit_row(conn, dict(SAMPLE_AUDIT_ROW))

        rows = db.fetch_audit_log(conn)
        matching = [r for r in rows if r["record_id"] == "REC0001"]

        self.assertTrue(first_inserted, "first insert should report success")
        self.assertFalse(second_inserted, "duplicate insert should report as a no-op")
        self.assertEqual(len(matching), 1, "duplicate submission must not create a second row")
        conn.close()


if __name__ == "__main__":
    unittest.main()
