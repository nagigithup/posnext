import unittest
from unittest.mock import Mock, patch

from pos_next.services.barcode import compute_resolved_item_data, resolve_scale_barcode


SCALE_SETTINGS = {
	"enable_scale_barcode": 1,
	"scale_barcode_start_with": "221",
	"scale_barcode_total_length": 13,
	"scale_item_barcode_length": 7,
	"scale_weight_length": 5,
	"scale_weight_divisor": 1000,
	"scale_check_digit_length": 1,
}


class TestScaleBarcode(unittest.TestCase):
	def _mock_settings_lookup(self, mock_frappe):
		mock_frappe._ = lambda message, *args, **kwargs: message
		mock_frappe.throw.side_effect = Exception
		mock_db = Mock()
		mock_db.get_value.side_effect = ["POS-SETTINGS-1", SCALE_SETTINGS]
		mock_frappe.db = mock_db

	def test_scale_barcode_resolves_configured_item_barcode_and_qty(self):
		with patch("pos_next.services.barcode.frappe") as mock_frappe:
			self._mock_settings_lookup(mock_frappe)

			result = resolve_scale_barcode("2210001013758", "Main POS")

		self.assertEqual(result["item_barcode"], "2210001")
		self.assertEqual(result["qty"], 1.375)
		self.assertEqual(result["check_digit"], "8")
		self.assertEqual(result["barcode_type"], "Weighted")

	def test_scale_barcode_resolves_qty_0545(self):
		with patch("pos_next.services.barcode.frappe") as mock_frappe:
			self._mock_settings_lookup(mock_frappe)

			result = resolve_scale_barcode("2210001005456", "Main POS")

		self.assertEqual(result["item_barcode"], "2210001")
		self.assertEqual(result["qty"], 0.545)

	def test_scale_barcode_resolves_qty_1925(self):
		with patch("pos_next.services.barcode.frappe") as mock_frappe:
			self._mock_settings_lookup(mock_frappe)

			result = resolve_scale_barcode("2210001019255", "Main POS")

		self.assertEqual(result["item_barcode"], "2210001")
		self.assertEqual(result["qty"], 1.925)

	def test_scale_barcode_resolves_another_item(self):
		with patch("pos_next.services.barcode.frappe") as mock_frappe:
			self._mock_settings_lookup(mock_frappe)

			result = resolve_scale_barcode("2210081003254", "Main POS")

		self.assertEqual(result["item_barcode"], "2210081")
		self.assertEqual(result["qty"], 0.325)

	def test_wrong_prefix_does_not_use_scale_parsing(self):
		with patch("pos_next.services.barcode.frappe") as mock_frappe:
			self._mock_settings_lookup(mock_frappe)

			result = resolve_scale_barcode("2220001013758", "Main POS")

		self.assertIsNone(result)

	def test_wrong_total_length_does_not_use_scale_parsing(self):
		with patch("pos_next.services.barcode.frappe") as mock_frappe:
			self._mock_settings_lookup(mock_frappe)

			result = resolve_scale_barcode("221000101375", "Main POS")

		self.assertIsNone(result)

	def test_zero_weight_is_rejected(self):
		with (
			patch("pos_next.services.barcode.frappe") as mock_frappe,
			patch("pos_next.services.barcode._", side_effect=lambda message, *args, **kwargs: message),
		):
			self._mock_settings_lookup(mock_frappe)

			with self.assertRaises(Exception):
				resolve_scale_barcode("2210001000008", "Main POS")

		mock_frappe.throw.assert_called_once()
		self.assertIn("invalid zero weight", mock_frappe.throw.call_args.args[0])

	def test_resolved_weighted_barcode_sets_qty_without_external_resolver_app(self):
		item = {"item_code": "ITEM-001", "uom": "KG", "rate": 40, "uom_prices": {"KG": 40}}
		result = compute_resolved_item_data(
			{"item_barcode": "2210001", "barcode_type": "Weighted", "qty": 1.375},
			item=item,
		)

		self.assertEqual(result["resolved_qty"], 1.375)
		self.assertEqual(result["resolved_uom"], "KG")
		self.assertEqual(result["resolved_price"], 40)


if __name__ == "__main__":
	unittest.main()
