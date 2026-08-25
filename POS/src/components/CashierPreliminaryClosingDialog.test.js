import { describe, expect, it } from "vitest"
import source from "./CashierPreliminaryClosingDialog.vue?raw"

describe("CashierPreliminaryClosingDialog", () => {
	it("renders the Arabic RTL declaration fields and success message", () => {
		expect(source).toContain('dir="rtl"')
		expect(source).toContain("رصيد الخزينة")
		expect(source).toContain("رصيد مبيعات الشبكة")
		expect(source).toContain("تم إرسال إقفال الوردية إلى المحاسب للمراجعة.")
	})

	it("does not contain official reconciliation data", () => {
		for (const forbidden of [
			"expected_amount",
			"difference",
			"grand_total",
			"net_total",
			"pos_transactions",
			"payment_reconciliation",
		]) {
			expect(source).not.toContain(forbidden)
		}
	})
})
