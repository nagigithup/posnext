from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from pos_next.api.printing import (
	DEFAULT_RECEIPT_FORMAT,
	_thermal_page_css,
	_validated_height,
	_validated_print_format,
)


class TestQZReceiptPrinting(IntegrationTestCase):
	@patch("pos_next.api.printing.frappe.db.get_value")
	def test_selected_sales_invoice_format_is_preserved(self, get_value):
		get_value.return_value = frappe._dict({"doc_type": "Sales Invoice", "disabled": 0})
		self.assertEqual(_validated_print_format("Arabic Receipt"), "Arabic Receipt")

	@patch("pos_next.api.printing.frappe.db.get_value", return_value=None)
	def test_invalid_format_falls_back_to_pos_receipt(self, _get_value):
		self.assertEqual(_validated_print_format("Missing"), DEFAULT_RECEIPT_FORMAT)

	def test_thermal_dimensions_are_embedded_in_pdf_css(self):
		height = _validated_height(286.4)
		css = _thermal_page_css(height)
		self.assertIn("page-width: 80mm", css)
		self.assertIn("page-height: 286.4mm", css)
		self.assertIn("margin-left: 0mm", css)
		self.assertIn("min-height: 0 !important", css)
		self.assertIn("page-break-after: auto !important", css)

	def test_receipt_height_is_bounded(self):
		with self.assertRaises(frappe.ValidationError):
			_validated_height(10)
		with self.assertRaises(frappe.ValidationError):
			_validated_height(6000)
