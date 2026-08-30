import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from pos_next.permissions import CASHIER_ROLES
from pos_next.pos_next.doctype.cashier_preliminary_closing.cashier_preliminary_closing import (
	SUCCESS_MESSAGE,
)


SAFE_CONTEXT_KEYS = {
	"pos_opening_shift",
	"company",
	"pos_profile",
	"cashier",
	"opening_datetime",
	"closing_datetime",
}


def _require_cashier():
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required."), frappe.AuthenticationError)
	if not set(frappe.get_roles()).intersection(CASHIER_ROLES):
		frappe.throw(_("Only a cashier can use preliminary closing."), frappe.PermissionError)


def _get_valid_opening_shifts():
	preliminary_closed_condition = (
		"AND IFNULL(opening.custom_preliminary_closed, 0) = 0"
		if frappe.db.has_column("POS Opening Shift", "custom_preliminary_closed")
		else ""
	)
	return frappe.db.sql(
		f"""
		SELECT opening.name AS pos_opening_shift,
		       opening.company,
		       opening.pos_profile,
		       opening.user AS cashier,
		       opening.period_start_date AS opening_datetime
		FROM `tabPOS Opening Shift` opening
		LEFT JOIN `tabCashier Preliminary Closing` preliminary
		       ON preliminary.pos_opening_shift = opening.name
		      AND preliminary.docstatus < 2
		LEFT JOIN `tabPOS Closing Shift` closing
		       ON closing.pos_opening_shift = opening.name
		      AND closing.docstatus < 2
		WHERE opening.user = %s
		  AND opening.docstatus = 1
		  AND opening.status = 'Open'
		  {preliminary_closed_condition}
		  AND preliminary.name IS NULL
		  AND closing.name IS NULL
		ORDER BY opening.period_start_date DESC
		""",
		(frappe.session.user,),
		as_dict=True,
	)


@frappe.whitelist()
def get_preliminary_closing_context():
	"""Return only metadata safe for the cashier declaration screen."""
	_require_cashier()
	shifts = _get_valid_opening_shifts()
	if not shifts:
		frappe.throw(_("No open POS Opening Shift is available for preliminary closing."))
	if len(shifts) > 1:
		frappe.throw(_("More than one open shift was found. Ask a POS manager to resolve it."))

	context = shifts[0]
	context.closing_datetime = now_datetime()
	return {key: context.get(key) for key in SAFE_CONTEXT_KEYS}


@frappe.whitelist()
def submit_preliminary_closing(pos_opening_shift, cash_amount=0, network_amount=0):
	"""Create and submit one declaration, returning no reconciliation values."""
	_require_cashier()
	doc = frappe.get_doc(
		{
			"doctype": "Cashier Preliminary Closing",
			"pos_opening_shift": pos_opening_shift,
			"cash_amount": flt(cash_amount),
			"network_amount": flt(network_amount),
		}
	)
	doc.insert()
	doc.submit()
	return {
		"cashier_preliminary_closing": doc.name,
		"pos_closing_shift": doc.pos_closing_shift,
		"message": SUCCESS_MESSAGE,
	}
