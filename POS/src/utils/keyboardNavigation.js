export function isMultilineTarget(target) {
	return Boolean(
		target &&
			(target.tagName === "TEXTAREA" ||
				target.isContentEditable ||
				target.getAttribute?.("role") === "textbox" && target.getAttribute?.("aria-multiline") === "true")
	);
}

export function isInteractiveTarget(target) {
	return Boolean(target?.closest?.("button, a, input, select, textarea, [contenteditable='true']"));
}

export function focusElement(element) {
	if (!element || element.disabled || element.getAttribute?.("aria-hidden") === "true") return false;
	element.focus({ preventScroll: true });
	element.scrollIntoView?.({ block: "nearest", inline: "nearest" });
	return true;
}

export function focusPOSItemSearch() {
	requestAnimationFrame(() => {
		const inputs = [...document.querySelectorAll("#item-search")];
		const visibleInput = inputs.find((input) => input.getClientRects().length > 0) || inputs[0];
		focusElement(visibleInput);
	});
}

export function moveListFocus(elements, currentIndex, delta) {
	const available = elements.filter(Boolean);
	if (!available.length) return -1;
	const start = currentIndex < 0 ? (delta > 0 ? -1 : 0) : currentIndex;
	const nextIndex = (start + delta + available.length) % available.length;
	focusElement(available[nextIndex]);
	return nextIndex;
}
