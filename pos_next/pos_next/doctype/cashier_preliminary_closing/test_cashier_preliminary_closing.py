import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe
from pos_next.api import preliminary_closing as api
from pos_next.permissions import has_official_closing_permission, has_preliminary_closing_permission
from pos_next.pos_next.doctype.cashier_preliminary_closing.cashier_preliminary_closing import (
	CashierPreliminaryClosing,
	apply_declarations_to_closing,
)
from pos_next.pos_next.doctype.pos_closing_shift.pos_closing_shift import (
	POSClosingShift,
	get_pos_invoices,
	get_supported_invoice_sources,
	validate_official_closing_access,
)


class TestCashierPreliminaryClosing(unittest.TestCase):
	def test_cashier_cannot_close_another_cashiers_shift(self):
		doc = SimpleNamespace(pos_opening_shift="SHIFT-B")
		opening = frappe._dict(
			name="SHIFT-B",
			company="Test Company",
			pos_profile="Test POS",
			user="cashier-b@example.com",
			period_start_date="2026-08-25 08:00:00",
			status="Open",
			docstatus=1,
		)
		previous_session = frappe.local.session
		frappe.local.session = frappe._dict(user="cashier-a@example.com")
		try:
			with patch.object(frappe.db, "get_value", return_value=opening), self.assertRaises(
				frappe.PermissionError
			):
				CashierPreliminaryClosing._load_authoritative_shift_data(doc)
		finally:
			frappe.local.session = previous_session

	def test_cashier_api_contains_no_reconciliation_values(self):
		shift = frappe._dict(
			pos_opening_shift="SHIFT-A",
			company="Test Company",
			pos_profile="Test POS",
			cashier="cashier-a@example.com",
			opening_datetime="2026-08-25 08:00:00",
		)
		with patch.object(api, "_require_cashier"), patch.object(
			api, "_get_valid_opening_shifts", return_value=[shift]
		):
			result = api.get_preliminary_closing_context()
		for forbidden in {
			"expected_amount",
			"difference",
			"grand_total",
			"net_total",
			"pos_transactions",
			"taxes",
			"payment_reconciliation",
		}:
			self.assertNotIn(forbidden, result)

	def test_submission_creates_exactly_one_official_draft(self):
		doc = SimpleNamespace(
			_lock_opening_shift=MagicMock(),
			_load_authoritative_shift_data=MagicMock(),
			_validate_duplicates=MagicMock(),
			_create_official_draft=MagicMock(return_value="CLOSE-1"),
			pos_closing_shift=None,
		)
		CashierPreliminaryClosing.before_submit(doc)
		doc._create_official_draft.assert_called_once_with()
		self.assertEqual(doc.pos_closing_shift, "CLOSE-1")

	def test_cash_declaration_maps_to_configured_row(self):
		closing = self._closing([("Cash AED", 100, 0), ("Network AED", 200, 0)])
		apply_declarations_to_closing(closing, {"Cash AED": 125, "Network AED": 215})
		self.assertEqual(closing.payment_reconciliation[0].closing_amount, 125)

	def test_network_declaration_maps_to_configured_row(self):
		closing = self._closing([("Cash AED", 100, 0), ("Network AED", 200, 0)])
		apply_declarations_to_closing(closing, {"Cash AED": 125, "Network AED": 215})
		self.assertEqual(closing.payment_reconciliation[1].closing_amount, 215)

	def test_expected_amount_is_not_overwritten_by_cashier_input(self):
		closing = self._closing([("Cash AED", 310, 0), ("Network AED", 420, 0)])
		apply_declarations_to_closing(closing, {"Cash AED": 10, "Network AED": 20})
		self.assertEqual(closing.payment_reconciliation[0].expected_amount, 310)
		self.assertEqual(closing.payment_reconciliation[1].expected_amount, 420)

	def test_difference_uses_pos_next_reconciliation_logic(self):
		row = frappe._dict(expected_amount=100, closing_amount=94, difference=0)
		doc = SimpleNamespace(payment_reconciliation=[row])
		with patch.object(frappe, "get_cached_value", return_value=2):
			POSClosingShift.update_payment_reconciliation(doc)
		self.assertEqual(row.difference, -6)

	def test_duplicate_preliminary_closing_is_rejected(self):
		doc = SimpleNamespace(
			pos_closing_shift=None,
			pos_opening_shift="SHIFT-A",
			name="CPC-1",
		)
		with patch.object(frappe.db, "get_value", return_value="CPC-2"), self.assertRaises(
			frappe.ValidationError
		):
			CashierPreliminaryClosing._validate_duplicates(doc)

	def test_duplicate_official_closing_is_rejected(self):
		doc = SimpleNamespace(
			pos_closing_shift=None,
			pos_opening_shift="SHIFT-A",
			name="CPC-1",
		)
		with patch.object(frappe.db, "get_value", side_effect=[None, "CLOSE-2"]), self.assertRaises(
			frappe.ValidationError
		):
			CashierPreliminaryClosing._validate_duplicates(doc)

	def test_accountant_can_access_official_closing(self):
		with patch("pos_next.permissions.frappe.get_roles", return_value=["Accounts User"]):
			self.assertIsNone(has_official_closing_permission(SimpleNamespace()))

	def test_cashier_cannot_access_official_reconciliation(self):
		with patch(
			"pos_next.pos_next.doctype.pos_closing_shift.pos_closing_shift.frappe.get_roles",
			return_value=["Cashier"],
		), self.assertRaises(frappe.PermissionError):
			validate_official_closing_access()

	def test_cashier_can_create_preliminary_before_owner_is_assigned(self):
		with patch("pos_next.permissions.frappe.get_roles", return_value=["Cashier"]):
			self.assertTrue(
				has_preliminary_closing_permission(
					SimpleNamespace(owner=None, cashier=None),
					user="cashier@example.com",
					permission_type="create",
				)
			)

	def test_sales_invoice_and_native_pos_invoice_sources_are_supported(self):
		with patch.object(frappe.db, "exists", return_value=True):
			self.assertEqual(
				get_supported_invoice_sources(),
				[("Sales Invoice", "sales_invoice"), ("POS Invoice", "pos_invoice")],
			)

	def test_consolidated_pos_invoices_are_excluded(self):
		with (
			patch(
				"pos_next.pos_next.doctype.pos_closing_shift.pos_closing_shift.validate_official_closing_access"
			),
			patch.object(frappe.db, "has_column", return_value=True),
			patch(
				"pos_next.pos_next.doctype.pos_closing_shift.pos_closing_shift.submit_printed_invoices"
			),
			patch.object(frappe.db, "sql", return_value=[]) as sql,
		):
			get_pos_invoices("SHIFT-A", "POS Invoice")
		self.assertIn("ifnull(consolidated_invoice,'') = ''", sql.call_args.args[0])

	def test_concurrent_submission_locks_opening_shift(self):
		doc = SimpleNamespace(pos_opening_shift="SHIFT-A")
		with patch.object(frappe.db, "sql", return_value=[("SHIFT-A",)]) as sql:
			CashierPreliminaryClosing._lock_opening_shift(doc)
		self.assertIn("FOR UPDATE", sql.call_args.args[0])

	def test_submit_api_returns_only_safe_identifiers(self):
		doc = MagicMock(name="preliminary")
		doc.name = "CPC-1"
		doc.pos_closing_shift = "CLOSE-1"
		with patch.object(api, "_require_cashier"), patch.object(frappe, "get_doc", return_value=doc):
			result = api.submit_preliminary_closing("SHIFT-A", 10, 20)
		self.assertEqual(
			set(result), {"cashier_preliminary_closing", "pos_closing_shift", "message"}
		)
		doc.insert.assert_called_once_with()
		doc.submit.assert_called_once_with()

	@staticmethod
	def _closing(rows):
		payment_rows = [
			frappe._dict(
				mode_of_payment=mode,
				expected_amount=expected,
				closing_amount=closing,
				difference=0,
			)
			for mode, expected, closing in rows
		]
		closing = SimpleNamespace(payment_reconciliation=payment_rows)
		closing.update_payment_reconciliation = lambda: POSClosingShift.update_payment_reconciliation(closing)
		return closing
