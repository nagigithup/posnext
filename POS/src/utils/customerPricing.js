export function getResolvedRate(details = {}) {
	return details.rate || details.price_list_rate || 0;
}

const OPTIONAL_PRICING_FIELDS = [
	"base_price_list_rate",
	"base_rate",
	"base_rate_with_margin",
	"rate_with_margin",
	"net_rate",
	"net_amount",
	"amount",
];

export function buildCustomerPricedItem(item, details = {}) {
	return {
		...item,
		...details,
		item_code: item.item_code,
		uom: item.uom || details.uom || item.stock_uom,
		stock_uom: item.stock_uom || details.stock_uom,
		rate: getResolvedRate(details),
		price_list_rate: details.price_list_rate || details.rate || 0,
	};
}

export function applyCustomerPricing(item, details = {}) {
	item.rate = getResolvedRate(details);
	item.price_list_rate = details.price_list_rate || details.rate || 0;
	item.discount_percentage = details.discount_percentage || 0;
	item.discount_amount = details.discount_amount || 0;
	item.pricing_rules = details.pricing_rules || "";
	for (const field of OPTIONAL_PRICING_FIELDS) {
		if (Object.hasOwn(details, field)) item[field] = details[field];
	}
	item.is_rate_manually_edited = 0;
	item.original_rate = null;
	return item;
}

export function isCurrentPricingGeneration(responseGeneration, currentGeneration) {
	return responseGeneration === currentGeneration;
}
