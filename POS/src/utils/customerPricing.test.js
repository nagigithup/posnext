import { describe, expect, it } from "vitest";
import {
	applyCustomerPricing,
	buildCustomerPricedItem,
	isCurrentPricingGeneration,
} from "./customerPricing";

describe("customer POS pricing", () => {
	it("prices newly added items from the resolved customer list", () => {
		const item = buildCustomerPricedItem(
			{ item_code: "ITEM-X", rate: 100, price_list_rate: 100, uom: "Nos" },
			{ rate: 0, price_list_rate: 90, effective_price_list: "Retail" }
		);
		expect(item.rate).toBe(90);
		expect(item.price_list_rate).toBe(90);
	});

	it("reprices an existing cart row and clears stale manual pricing", () => {
		const item = {
			item_code: "ITEM-X",
			rate: 100,
			price_list_rate: 100,
			is_rate_manually_edited: 1,
			original_rate: 100,
		};
		applyCustomerPricing(item, { rate: 0, price_list_rate: 80 });
		expect(item).toMatchObject({
			rate: 80,
			price_list_rate: 80,
			is_rate_manually_edited: 0,
			original_rate: null,
		});
	});

	it("copies all ERPNext pricing fields from an authoritative response", () => {
		const item = { item_code: "ITEM-X", discount_percentage: 23 };
		applyCustomerPricing(item, {
			rate: 77,
			price_list_rate: 100,
			base_price_list_rate: 100,
			base_rate: 77,
			net_rate: 77,
			net_amount: 154,
			discount_percentage: 23,
			discount_amount: 46,
			pricing_rules: "RULE-23",
		});

		expect(item).toMatchObject({
			rate: 77,
			price_list_rate: 100,
			base_price_list_rate: 100,
			base_rate: 77,
			net_rate: 77,
			net_amount: 154,
			discount_percentage: 23,
			discount_amount: 46,
			pricing_rules: "RULE-23",
		});
	});

	it("follows authoritative pricing across employee and normal customer changes", () => {
		const item = { item_code: "ITEM-X" };

		applyCustomerPricing(item, {
			rate: 90,
			price_list_rate: 100,
			discount_percentage: 10,
			discount_amount: 10,
			pricing_rules: "EMPLOYEE-RULE",
		});
		expect(item.discount_percentage).toBe(10);

		applyCustomerPricing(item, { rate: 100, price_list_rate: 100 });
		expect(item).toMatchObject({
			rate: 100,
			discount_percentage: 0,
			discount_amount: 0,
			pricing_rules: "",
		});

		applyCustomerPricing(item, {
			rate: 90,
			price_list_rate: 100,
			discount_percentage: 10,
			discount_amount: 10,
			pricing_rules: "EMPLOYEE-RULE",
		});
		expect(item.discount_percentage).toBe(10);
	});

	it("keeps a missing Item Price at zero instead of using an old list", () => {
		const item = { item_code: "ITEM-X", rate: 100, price_list_rate: 100 };
		applyCustomerPricing(item, { rate: 0, price_list_rate: 0 });
		expect(item.rate).toBe(0);
		expect(item.price_list_rate).toBe(0);
	});

	it("rejects stale responses during A to B to A switching", () => {
		expect(isCurrentPricingGeneration(1, 3)).toBe(false);
		expect(isCurrentPricingGeneration(2, 3)).toBe(false);
		expect(isCurrentPricingGeneration(3, 3)).toBe(true);
	});
});
