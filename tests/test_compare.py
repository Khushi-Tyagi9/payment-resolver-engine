import unittest

from resolver.compare import determine_drift, MATCH, DRIFT_SAFE, DRIFT_RISKY, DRIFT_OTHER
from resolver.correlate import build_correlation_index, correlate
from resolver.lookup import normalize_razorpay_status, SUCCESS, PENDING, FAILED


class TestNormalizeStatus(unittest.TestCase):
    def test_known_codes_map_to_signal(self):
        self.assertEqual(normalize_razorpay_status("captured"), SUCCESS)
        self.assertEqual(normalize_razorpay_status("failed"), FAILED)
        self.assertEqual(normalize_razorpay_status("authorized"), PENDING)

    def test_unmapped_code_returns_none(self):
        self.assertIsNone(normalize_razorpay_status("npci_timeout"))


class TestDetermineDrift(unittest.TestCase):
    def test_match(self):
        self.assertEqual(determine_drift(SUCCESS, SUCCESS), MATCH)
        self.assertEqual(determine_drift(PENDING, PENDING), MATCH)

    def test_safe_direction_drift(self):
        self.assertEqual(determine_drift(SUCCESS, PENDING), DRIFT_SAFE)
        self.assertEqual(determine_drift(SUCCESS, FAILED), DRIFT_SAFE)

    def test_risky_direction_drift(self):
        self.assertEqual(determine_drift(FAILED, SUCCESS), DRIFT_RISKY)

    def test_other_mismatch_is_not_auto_correctable(self):
        self.assertEqual(determine_drift(PENDING, SUCCESS), DRIFT_OTHER)
        self.assertEqual(determine_drift(FAILED, PENDING), DRIFT_OTHER)


class TestCorrelate(unittest.TestCase):
    def test_correlation_ok_when_payment_id_maps_to_single_order_and_amount(self):
        batch = [
            {"razorpay_payment_id": "pay_1", "order_id": "ORD1", "amount": 100},
            {"razorpay_payment_id": "pay_2", "order_id": "ORD2", "amount": 200},
        ]
        index = build_correlation_index(batch)
        self.assertTrue(correlate(batch[0], index))
        self.assertTrue(correlate(batch[1], index))

    def test_correlation_ok_for_reversal_pair_sharing_same_payment(self):
        batch = [
            {"razorpay_payment_id": "pay_1", "order_id": "ORD1", "amount": 100},
            {"razorpay_payment_id": "pay_1", "order_id": "ORD1", "amount": 100},
        ]
        index = build_correlation_index(batch)
        self.assertTrue(correlate(batch[0], index))
        self.assertTrue(correlate(batch[1], index))

    def test_correlation_fails_when_payment_id_maps_to_two_order_ids(self):
        batch = [
            {"razorpay_payment_id": "pay_1", "order_id": "ORD1", "amount": 100},
            {"razorpay_payment_id": "pay_1", "order_id": "ORD2", "amount": 100},
        ]
        index = build_correlation_index(batch)
        self.assertFalse(correlate(batch[0], index))
        self.assertFalse(correlate(batch[1], index))

    def test_correlation_fails_when_amount_mismatches(self):
        batch = [
            {"razorpay_payment_id": "pay_1", "order_id": "ORD1", "amount": 100},
            {"razorpay_payment_id": "pay_1", "order_id": "ORD1", "amount": 150},
        ]
        index = build_correlation_index(batch)
        self.assertFalse(correlate(batch[0], index))
        self.assertFalse(correlate(batch[1], index))


if __name__ == "__main__":
    unittest.main()
