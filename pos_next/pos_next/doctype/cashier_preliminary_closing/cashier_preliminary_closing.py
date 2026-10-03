import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from pos_next.permissions import CASHIER_ROLES


SUCCESS_MESSAGE = "تم إرسال إقفال الوردية إلى المحاسب للمراجعة."


def apply_declarations_to_closing(closing_doc, declarations):
	"""Set physical declarations while leaving POS Next calculations intact."""
	matched = set()
	for row in closing_doc.payment_reconciliation:
		if row.mode_of_payment in declarations:
			row.closing_amount = flt(declarations[row.mode_of_payment])
			matched.add(row.mode_of_payment)

	missing = set(declarations) - matched
	if missing:
		frappe.throw(
			_("Configured payment modes are missing from POS reconciliation: {0}").format(
				", ".join(sorted(missing))
			)
		)
	closing_doc.update_payment_reconciliation()


class CashierPreliminaryClosing(Document):
	def before_insert(self):
		self._load_authoritative_shift_data()

	def validate(self):
		self._validate_cashier()
		self._load_authoritative_shift_data()
		self._validate_amounts()
		self._set_declared_payments()
		self._validate_duplicates()

	def before_submit(self):
		self._lock_opening_shift()
		self._load_authoritative_shift_data()
		self._validate_duplicates(for_submission=True)
		self.pos_closing_shift = self._create_official_draft()
		self._mark_opening_shift_operationally_closed()

	def _validate_cashier(self):
		if frappe.session.user == "Guest":
			frappe.throw(_("Authentication required."), frappe.AuthenticationError)
		if not set(frappe.get_roles()).intersection(CASHIER_ROLES):
			frappe.throw(_("Only a cashier can submit a preliminary closing."), frappe.PermissionError)

	def _load_authoritative_shift_data(self):
		if not self.pos_opening_shift:
			frappe.throw(_("POS Opening Shift is required."))

		fields = ["name", "company", "pos_profile", "user", "period_start_date", "status", "docstatus"]
		if frappe.db.has_column("POS Opening Shift", "custom_preliminary_closed"):
			fields.append("custom_preliminary_closed")

		opening = frappe.db.get_value(
			"POS Opening Shift",
			self.pos_opening_shift,
			fields,
			as_dict=True,
		)
		if not opening:
			frappe.throw(_("POS Opening Shift {0} was not found.").format(self.pos_opening_shift))
		if opening.user != frappe.session.user:
			frappe.throw(_("You cannot close another cashier's shift."), frappe.PermissionError)
		if opening.docstatus != 1 or opening.status != "Open":
			frappe.throw(_("The selected POS Opening Shift is not open."))
		if opening.get("custom_preliminary_closed"):
			frappe.throw(_("The selected POS Opening Shift is already preliminarily closed."))

		self.company = opening.company
		self.pos_profile = opening.pos_profile
		self.cashier = opening.user
		self.opening_datetime = opening.period_start_date
		self.closing_datetime = self.closing_datetime or now_datetime()

	def _validate_amounts(self):
		if flt(self.cash_amount) < 0 or flt(self.network_amount) < 0:
			frappe.throw(_("Declared amounts cannot be negative."))

	def _get_payment_modes(self):
		modes = frappe.db.get_value(
			"POS Profile",
			self.pos_profile,
			["posa_cash_mode_of_payment", "posa_network_mode_of_payment"],
			as_dict=True,
		)
		if not modes or not modes.posa_cash_mode_of_payment:
			frappe.throw(_("Configure Cash Mode of Payment on POS Profile {0}.").format(self.pos_profile))
		if not modes.posa_network_mode_of_payment:
			frappe.throw(_("Configure Network Mode of Payment on POS Profile {0}.").format(self.pos_profile))
		if modes.posa_cash_mode_of_payment == modes.posa_network_mode_of_payment:
			frappe.throw(_("Cash and Network modes of payment must be different."))
		profile_modes = set(
			frappe.get_all(
				"POS Payment Method",
				filters={"parent": self.pos_profile},
				pluck="mode_of_payment",
			)
		)
		missing = {modes.posa_cash_mode_of_payment, modes.posa_network_mode_of_payment} - profile_modes
		if missing:
			frappe.throw(
				_("Configured payment modes are not enabled on POS Profile {0}: {1}").format(
					self.pos_profile, ", ".join(sorted(missing))
				)
			)
		return modes

	def _set_declared_payments(self):
		modes = self._get_payment_modes()
		self.set(
			"payments",
			[
				{
					"mode_of_payment": modes.posa_cash_mode_of_payment,
					"declared_amount": flt(self.cash_amount),
				},
				{
					"mode_of_payment": modes.posa_network_mode_of_payment,
					"declared_amount": flt(self.network_amount),
				},
			],
		)

	def _lock_opening_shift(self):
		locked = frappe.db.sql(
			"SELECT name FROM `tabPOS Opening Shift` WHERE name = %s FOR UPDATE",
			self.pos_opening_shift,
		)
		if not locked:
			frappe.throw(_("POS Opening Shift {0} was not found.").format(self.pos_opening_shift))

	def _validate_duplicates(self, for_submission=False):
		if self.pos_closing_shift:
			frappe.throw(_("An official POS Closing Shift has already been generated."))

		existing_preliminary = frappe.db.get_value(
			"Cashier Preliminary Closing",
			{
				"pos_opening_shift": self.pos_opening_shift,
				"name": ["!=", self.name or ""],
				"docstatus": ["<", 2],
			},
			"name",
		)
		if existing_preliminary:
			frappe.throw(
				_("Preliminary closing {0} already exists for this shift.").format(existing_preliminary)
			)

		existing_closing = frappe.db.get_value(
			"POS Closing Shift",
			{"pos_opening_shift": self.pos_opening_shift, "docstatus": ["<", 2]},
			"name",
		)
		if existing_closing:
			frappe.throw(_("POS Closing Shift {0} already exists for this shift.").format(existing_closing))

		if for_submission:
			frappe.db.sql(
				"SELECT name FROM `tabCashier Preliminary Closing` "
				"WHERE pos_opening_shift = %s AND name != %s AND docstatus < 2 FOR UPDATE",
				(self.pos_opening_shift, self.name),
			)

	def _create_official_draft(self):
		from pos_next.pos_next.doctype.pos_closing_shift.pos_closing_shift import (
			make_closing_shift_from_opening,
		)

		opening = frappe.get_doc("POS Opening Shift", self.pos_opening_shift)
		previous_builder_flag = getattr(frappe.flags, "cashier_preliminary_closing_builder", False)
		frappe.flags.cashier_preliminary_closing_builder = True
		try:
			closing_data = make_closing_shift_from_opening(json.dumps(opening.as_dict(), default=str))
		finally:
			frappe.flags.cashier_preliminary_closing_builder = previous_builder_flag

		closing_doc = frappe.new_doc("POS Closing Shift")
		for field in closing_doc.meta.fields:
			if field.fieldname in closing_data:
				closing_doc.set(field.fieldname, closing_data[field.fieldname])
		closing_doc.custom_preliminary_closing = self.name

		declarations = {row.mode_of_payment: flt(row.declared_amount) for row in self.payments}
		apply_declarations_to_closing(closing_doc, declarations)
		closing_doc.flags.ignore_permissions = True
		closing_doc.insert(ignore_permissions=True)
		return closing_doc.name

	def _mark_opening_shift_operationally_closed(self):
		"""End the cashier-facing session without submitting the official close."""
		if not frappe.db.has_column("POS Opening Shift", "custom_preliminary_closed"):
			return

		values = {"custom_preliminary_closed": 1}
		if frappe.db.has_column("POS Opening Shift", "custom_preliminary_closing"):
			values["custom_preliminary_closing"] = self.name

		frappe.db.set_value(
			"POS Opening Shift",
			self.pos_opening_shift,
			values,
			update_modified=False,
		)
