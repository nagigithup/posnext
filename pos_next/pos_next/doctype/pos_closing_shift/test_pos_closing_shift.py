# Copyright (c) 2020, Youssef Restom and Contributors
# See license.txt

import unittest
from unittest.mock import patch

import frappe

from pos_next.api.invoices import (
	_is_abandoned_session_draft,
	cleanup_old_drafts,
	cleanup_session_drafts,
)


class TestPOSClosingShift(unittest.TestCase):
	def _invoice(self, **overrides):
		data = {
			"docstatus": 0,
			"is_pos": 1,
			"custom_is_booking": 0,
			"posa_pos_opening_shift": "SHIFT-A",
			"posa_is_printed": 0,
		}
		data.update(overrides)
		return frappe._dict(data)

	def test_booking_without_payment_is_never_cleanup_eligible(self):
		booking = self._invoice(custom_is_booking=1)
		self.assertFalse(_is_abandoned_session_draft(booking, "SHIFT-A"))

	def test_booking_with_payment_is_never_cleanup_eligible(self):
		booking = self._invoice(custom_is_booking=1, has_payment_entry=1)
		self.assertFalse(_is_abandoned_session_draft(booking, "SHIFT-A"))

	def test_booking_age_does_not_affect_protection(self):
		booking = self._invoice(custom_is_booking=1, modified="2020-01-01 00:00:00")
		self.assertFalse(_is_abandoned_session_draft(booking, "SHIFT-A"))

	def test_booking_is_not_deleted_when_session_is_closed(self):
		booking = self._invoice(custom_is_booking=1)
		with (
			patch("pos_next.api.invoices._is_pos_opening_shift_closed", return_value=True),
			patch.object(frappe, "get_all", return_value=["BOOKING-1"]),
			patch.object(frappe.db, "has_column", return_value=True),
			patch.object(frappe.db, "get_value", return_value=booking),
			patch.object(frappe, "delete_doc") as delete_doc,
		):
			result = cleanup_session_drafts("SHIFT-A")
		self.assertEqual(result["deleted"], 0)
		delete_doc.assert_not_called()

	def test_active_session_draft_is_not_deleted(self):
		with (
			patch("pos_next.api.invoices._is_pos_opening_shift_closed", return_value=False),
			patch.object(frappe, "get_all") as get_all,
			patch.object(frappe, "delete_doc") as delete_doc,
		):
			result = cleanup_session_drafts("SHIFT-A")
		self.assertEqual(result["deleted"], 0)
		get_all.assert_not_called()
		delete_doc.assert_not_called()

	def test_closed_session_abandoned_draft_is_deleted_normally(self):
		draft = self._invoice()
		with (
			patch("pos_next.api.invoices._is_pos_opening_shift_closed", return_value=True),
			patch.object(frappe, "get_all", return_value=["DRAFT-1"]),
			patch.object(frappe.db, "has_column", return_value=True),
			patch.object(frappe.db, "get_value", return_value=draft),
			patch.object(frappe, "delete_doc") as delete_doc,
		):
			result = cleanup_session_drafts("SHIFT-A")
		self.assertEqual(result["deleted"], 1)
		delete_doc.assert_called_once_with("Sales Invoice", "DRAFT-1", ignore_permissions=True)

	def test_draft_from_another_session_is_not_deleted(self):
		draft = self._invoice(posa_pos_opening_shift="SHIFT-B")
		with (
			patch("pos_next.api.invoices._is_pos_opening_shift_closed", return_value=True),
			patch.object(frappe, "get_all", return_value=["DRAFT-B"]),
			patch.object(frappe.db, "has_column", return_value=True),
			patch.object(frappe.db, "get_value", return_value=draft),
			patch.object(frappe, "delete_doc") as delete_doc,
		):
			result = cleanup_session_drafts("SHIFT-A")
		self.assertEqual(result["deleted"], 0)
		delete_doc.assert_not_called()

	def test_submitted_invoice_is_never_cleanup_eligible(self):
		invoice = self._invoice(docstatus=1)
		self.assertFalse(_is_abandoned_session_draft(invoice, "SHIFT-A"))

	def test_age_based_cleanup_endpoint_never_deletes(self):
		with patch.object(frappe, "delete_doc") as delete_doc:
			result = cleanup_old_drafts(pos_profile="POS-A", max_age_hours=1)
		self.assertEqual(result["deleted"], 0)
		delete_doc.assert_not_called()
