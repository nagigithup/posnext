// @vitest-environment jsdom

import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";
import { useSearchInput } from "./useSearchInput";

vi.mock("vue", async (importOriginal) => {
	const actual = await importOriginal();
	return { ...actual, onUnmounted: vi.fn() };
});

function setup({ barcodeResult = null, barcodeError = null } = {}) {
	const itemStore = {
		searchTerm: "",
		clearSearch: vi.fn(function () {
			this.searchTerm = "";
		}),
		setSearchTerm: vi.fn(function (value) {
			this.searchTerm = value;
			return Promise.resolve(value ? [{ item_code: value }] : []);
		}),
		searchByBarcode: barcodeError
			? vi.fn().mockRejectedValue(barcodeError)
			: vi.fn().mockResolvedValue(barcodeResult),
	};
	const onItemFound = vi.fn();
	const search = useSearchInput({
		itemStore,
		onItemFound,
		isAnyDialogOpen: ref(false),
	});
	const input = { value: "", focus: vi.fn() };
	search.searchInputRef.value = input;
	return { input, itemStore, onItemFound, search };
}

function pressEnter(search) {
	search.handleKeyDown({ key: "Enter", preventDefault: vi.fn(), stopPropagation: vi.fn() });
}

describe("unified POS smart search", () => {
	it("tries the existing barcode flow first for numeric input and auto-adds a match", async () => {
		const item = {
			item_code: "ITEM-1",
			resolved_qty: 1.25,
			resolved_barcode_type: "Weighted",
		};
		const { input, itemStore, onItemFound, search } = setup({
			barcodeResult: item,
		});
		input.value = "2210001012500";

		pressEnter(search);

		await vi.waitFor(() => expect(onItemFound).toHaveBeenCalledWith(item, true));
		expect(itemStore.searchByBarcode).toHaveBeenCalledWith("2210001012500");
		expect(itemStore.setSearchTerm).not.toHaveBeenCalled();
		expect(input.value).toBe("");
	});

	it("falls back to normal Item Code search when a numeric barcode misses", async () => {
		const { input, itemStore, onItemFound, search } = setup({
			barcodeError: new Error("not found"),
		});
		input.value = "000123";

		pressEnter(search);

		await vi.waitFor(() => expect(itemStore.setSearchTerm).toHaveBeenCalledWith("000123"));
		expect(onItemFound).not.toHaveBeenCalled();
		expect(input.value).toBe("000123");
	});

	it("keeps manually entered alphanumeric values in normal search", () => {
		const { input, itemStore, search } = setup();
		input.value = "ITEM-A12";

		pressEnter(search);

		expect(itemStore.setSearchTerm).toHaveBeenCalledWith("ITEM-A12");
		expect(itemStore.searchByBarcode).not.toHaveBeenCalled();
		expect(input.value).toBe("ITEM-A12");
	});

	it("recognizes a rapid alphanumeric scanner entry and auto-adds it", async () => {
		const item = { item_code: "ITEM-SCAN" };
		const { input, itemStore, onItemFound, search } = setup({
			barcodeResult: item,
		});

		for (const value of ["A", "AB", "ABC", "ABC1", "ABC12", "ABC123"]) {
			input.value = value;
			search.handleSearchInput({ target: input });
		}
		itemStore.setSearchTerm.mockClear();

		pressEnter(search);

		await vi.waitFor(() => expect(onItemFound).toHaveBeenCalledWith(item, true));
		expect(itemStore.searchByBarcode).toHaveBeenCalledWith("ABC123");
	});

	it("moves through normal results with arrow keys", () => {
		const onNavigateResults = vi.fn().mockReturnValue(true);
		const { search } = setup();
		search.cleanup();
		const replacement = useSearchInput({
			itemStore: { clearSearch: vi.fn(), setSearchTerm: vi.fn(), searchTerm: "" },
			onItemFound: vi.fn(),
			isAnyDialogOpen: ref(false),
			onNavigateResults,
		});
		const event = { key: "ArrowDown", preventDefault: vi.fn(), stopPropagation: vi.fn() };

		replacement.handleKeyDown(event);

		expect(onNavigateResults).toHaveBeenCalledWith(1);
		expect(event.preventDefault).toHaveBeenCalled();
	});

	it("selects a highlighted alphanumeric result without invoking barcode lookup", () => {
		const itemStore = {
			searchTerm: "ITEM-A12",
			clearSearch: vi.fn(function () { this.searchTerm = ""; }),
			setSearchTerm: vi.fn(),
			searchByBarcode: vi.fn(),
		};
		const onSelectHighlighted = vi.fn().mockReturnValue(true);
		const search = useSearchInput({
			itemStore,
			onItemFound: vi.fn(),
			isAnyDialogOpen: ref(false),
			onSelectHighlighted,
		});
		search.searchInputRef.value = { value: "ITEM-A12", focus: vi.fn() };

		pressEnter(search);

		expect(onSelectHighlighted).toHaveBeenCalledOnce();
		expect(itemStore.searchByBarcode).not.toHaveBeenCalled();
		expect(itemStore.clearSearch).toHaveBeenCalled();
	});
});
