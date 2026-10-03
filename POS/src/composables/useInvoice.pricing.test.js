import { createPinia, setActivePinia } from "pinia"
import { beforeEach, describe, expect, it, vi } from "vitest"

vi.mock("frappe-ui", () => ({
	createResource: () => ({ submit: vi.fn() }),
}))

vi.mock("@/utils/offline", () => ({
	isOffline: () => false,
	getCachedItem: vi.fn(),
}))

import { useInvoice } from "./useInvoice"

describe("useInvoice ERPNext pricing", () => {
	beforeEach(() => {
		setActivePinia(createPinia())
	})

	it.each([
		[10, 90, 20, 180],
		[23, 77, 46, 154],
	])(
		"preserves a %s%% server Pricing Rule when adding an item",
		(discountPercentage, rate, discountAmount, netAmount) => {
			const invoice = useInvoice()
			invoice.addItem(
				{
					item_code: "ITEM-1",
					item_name: "Item 1",
					uom: "Nos",
					stock_uom: "Nos",
					price_list_rate: 100,
					rate,
					discount_percentage: discountPercentage,
					discount_amount: discountAmount,
					pricing_rules: "RULE-1",
				},
				2,
			)

			const [item] = invoice.invoiceItems.value
			expect(item).toMatchObject({
				price_list_rate: 100,
				rate,
				discount_percentage: discountPercentage,
				discount_amount: discountAmount,
				pricing_rules: "RULE-1",
				amount: netAmount,
			})
			expect(invoice.subtotal.value).toBe(200)
			expect(invoice.totalDiscount.value).toBe(discountAmount)
			expect(invoice.grandTotal.value).toBe(netAmount)
		},
	)

	it("keeps server pricing through local total and tax recalculation", () => {
		const invoice = useInvoice()
		invoice.addItem(
			{
				item_code: "ITEM-1",
				item_name: "Item 1",
				uom: "Nos",
				stock_uom: "Nos",
				price_list_rate: 100,
				rate: 90,
				discount_percentage: 10,
				discount_amount: 10,
				pricing_rules: "EMPLOYEE-RULE",
			},
			1,
		)

		const [item] = invoice.invoiceItems.value
		invoice.updateItemQuantity("ITEM-1", 3, "Nos")
		invoice.setTaxInclusive(true)

		expect(item.discount_percentage).toBe(10)
		expect(item.discount_amount).toBe(30)
		expect(item.pricing_rules).toBe("EMPLOYEE-RULE")
		expect(item.rate).toBe(90)
		expect(item.amount).toBe(270)
		expect(invoice.grandTotal.value).toBe(270)
	})
})
