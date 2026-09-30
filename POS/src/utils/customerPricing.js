export function getResolvedRate(details = {}) {
	return details.rate || details.price_list_rate || 0;
}

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
	item.is_rate_manually_edited = 0;
	item.original_rate = null;
	return item;
}

export function isCurrentPricingGeneration(responseGeneration, currentGeneration) {
	return responseGeneration === currentGeneration;
}
