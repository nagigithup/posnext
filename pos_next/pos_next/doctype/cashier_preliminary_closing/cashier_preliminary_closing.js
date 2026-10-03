frappe.ui.form.on("Cashier Preliminary Closing", {
	refresh(frm) {
		frm.set_df_property("pos_opening_shift", "read_only", 1);
		if (!frm.is_new()) return;

		frappe.call({
			method: "pos_next.api.preliminary_closing.get_preliminary_closing_context",
			callback(response) {
				const data = response.message;
				if (!data) return;
				frm.set_value({
					pos_opening_shift: data.pos_opening_shift,
					company: data.company,
					pos_profile: data.pos_profile,
					cashier: data.cashier,
					opening_datetime: data.opening_datetime,
					closing_datetime: data.closing_datetime,
				});
			},
		});
	},
});
