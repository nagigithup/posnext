"""Server-rendered thermal receipt PDFs for QZ Tray."""

from __future__ import annotations

import base64

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.pdf import get_pdf


DEFAULT_RECEIPT_FORMAT = "POS Next Receipt"
RECEIPT_WIDTH_MM = 80
MIN_RECEIPT_HEIGHT_MM = 40
MAX_RECEIPT_HEIGHT_MM = 5000


def _validated_print_format(print_format=None):
	print_format = print_format or DEFAULT_RECEIPT_FORMAT
	if print_format == "Standard":
		return print_format

	format_details = frappe.db.get_value(
		"Print Format", print_format, ["doc_type", "disabled"], as_dict=True
	)
	if not format_details or format_details.doc_type != "Sales Invoice" or format_details.disabled:
		return DEFAULT_RECEIPT_FORMAT
	return print_format


def _validated_height(page_height_mm):
	height = flt(page_height_mm)
	if height < MIN_RECEIPT_HEIGHT_MM or height > MAX_RECEIPT_HEIGHT_MM:
		frappe.throw(
			_("Receipt height must be between {0} mm and {1} mm.").format(
				MIN_RECEIPT_HEIGHT_MM, MAX_RECEIPT_HEIGHT_MM
			)
		)
	return round(height, 2)


def _thermal_page_css(height_mm):
	# Frappe's PDF option parser intentionally reads thermal dimensions and margins
	# from .print-format. This overrides only the outer paper, not the selected
	# Print Format's content, CSS, letterhead, logo, QR, or Jinja output.
	return f"""
<style>
	@page {{ size: {RECEIPT_WIDTH_MM}mm {height_mm}mm; margin: 0; }}
	html, body {{
		width: {RECEIPT_WIDTH_MM}mm !important;
		max-width: {RECEIPT_WIDTH_MM}mm !important;
		min-height: 0 !important;
		height: auto !important;
		margin: 0 !important;
		box-sizing: border-box !important;
	}}
	.print-format {{
		page-width: {RECEIPT_WIDTH_MM}mm;
		page-height: {height_mm}mm;
		width: {RECEIPT_WIDTH_MM}mm !important;
		max-width: {RECEIPT_WIDTH_MM}mm !important;
		min-height: 0 !important;
		height: auto !important;
		box-sizing: border-box !important;
		page-break-after: auto !important;
		margin-top: 0mm;
		margin-right: 0mm;
		margin-bottom: 0mm;
		margin-left: 0mm;
	}}
</style>
"""


@frappe.whitelist()
def get_qz_receipt_pdf(
	invoice_name,
	print_format=None,
	page_height_mm=None,
	letterhead=None,
):
	"""Return an Arabic-shaped, thermal-sized Sales Invoice PDF as base64."""
	doc = frappe.get_doc("Sales Invoice", invoice_name)
	selected_format = _validated_print_format(print_format)
	height_mm = _validated_height(page_height_mm)

	html = frappe.get_print(
		"Sales Invoice",
		doc.name,
		print_format=selected_format,
		doc=doc,
		no_letterhead=0 if letterhead else 1,
		letterhead=letterhead or None,
	)
	thermal_css = _thermal_page_css(height_mm)
	html = (
		html.replace("</head>", f"{thermal_css}</head>", 1)
		if "</head>" in html
		else f"{thermal_css}{html}"
	)
	pdf = get_pdf(
		html,
		options={
			"page-width": f"{RECEIPT_WIDTH_MM}mm",
			"page-height": f"{height_mm}mm",
			"margin-top": "0mm",
			"margin-right": "0mm",
			"margin-bottom": "0mm",
			"margin-left": "0mm",
			"javascript-delay": 750,
			"load-error-handling": "ignore",
		},
	)
	return {
		"pdf_base64": base64.b64encode(pdf).decode("ascii"),
		"print_format": selected_format,
		"width_mm": RECEIPT_WIDTH_MM,
		"height_mm": height_mm,
	}
