import frappe


CASHIER_ROLES = {"Cashier", "POSNext Cashier"}
PRELIMINARY_REVIEW_ROLES = {
	"Accounts User",
	"Accounts Manager",
	"System Manager",
	"Sales Manager",
	"Nexus POS Manager",
}


def get_preliminary_closing_query_conditions(user=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	if roles.intersection(PRELIMINARY_REVIEW_ROLES):
		return None
	if roles.intersection(CASHIER_ROLES):
		return f"`tabCashier Preliminary Closing`.`cashier` = {frappe.db.escape(user)}"
	return "1=0"


def has_preliminary_closing_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	if roles.intersection(PRELIMINARY_REVIEW_ROLES):
		return None
	if not roles.intersection(CASHIER_ROLES):
		return False
	if permission_type == "create":
		return True
	if permission_type == "cancel":
		return False
	return doc.cashier == user and doc.owner == user


def get_official_closing_query_conditions(user=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	if roles.intersection(PRELIMINARY_REVIEW_ROLES):
		return None
	if roles.intersection(CASHIER_ROLES):
		return "1=0"
	return None


def has_official_closing_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))
	if roles.intersection(PRELIMINARY_REVIEW_ROLES):
		return None
	if roles.intersection(CASHIER_ROLES):
		return False
	return None
