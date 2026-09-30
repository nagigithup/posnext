import { ref, watch, nextTick, onUnmounted } from "vue";
import { QueuedMutex } from "@/utils/mutex";

/**
 * Composable for search input, barcode scanning, and auto-add logic.
 *
 * Owns all search-input state, timers, and event handlers with proper
 * concurrency control.  Extracted from ItemsSelector.vue.
 *
 * Concurrency model:
 *   - On Enter (or auto-add timeout), the barcode is **snapshotted** from the
 *     DOM input immediately, then the input is cleared so the next scan starts
 *     into a clean field.
 *   - The snapshot is pushed into a {@link QueuedMutex}-backed queue
 *     (`processBarcodeScan`), which processes barcode lookups sequentially.
 *   - This guarantees no barcode is ever lost, even when scanning different
 *     items faster than the API can respond (~50 ms between scans).
 *
 * @param {Object} options
 * @param {Object} options.itemStore          - Pinia item-search store
 * @param {(item: Object, autoAdd: boolean) => boolean} options.onItemFound
 *        Component's selectItem(). Returns true if item was accepted.
 * @param {import('vue').Ref<boolean>} options.isAnyDialogOpen
 */
export function useSearchInput({
	itemStore,
	onItemFound,
	isAnyDialogOpen,
	onNavigateResults = null,
	onSelectHighlighted = null,
}) {
	// --- Reactive state (exposed) ---
	const searchInputRef = ref(null);
	const autoAddEnabled = ref(false);

	// --- Internal (non-reactive) ---
	let autoSearchTimer = null;
	let inputGeneration = 0;
	let inputStartedAt = 0;
	let lastInputAt = 0;
	let recordedCharacters = 0;
	let previousInputValue = "";
	const barcodeQueue = new QueuedMutex({
		timeout: 10000,
		name: "BarcodeSearch",
	});
	const SCANNER_MIN_LENGTH = 6;
	const SCANNER_MAX_AVERAGE_GAP_MS = 50;
	const SCANNER_ENTER_GAP_MS = 120;

	// ---- Timer helpers ----

	function clearAutoSearchTimer() {
		if (autoSearchTimer) {
			clearTimeout(autoSearchTimer);
			autoSearchTimer = null;
		}
	}

	// ---- Focus ----

	function focusSearchInput() {
		nextTick(() => {
			if (searchInputRef.value) {
				searchInputRef.value.focus();
			}
		});
	}

	function resetInputTiming() {
		inputStartedAt = 0;
		lastInputAt = 0;
		recordedCharacters = 0;
		previousInputValue = "";
	}

	function recordInputTiming(value, now = performance.now()) {
		const addedCharacters = Math.max(0, value.length - previousInputValue.length);
		const continuedInput =
			addedCharacters > 0 && lastInputAt && now - lastInputAt <= SCANNER_MAX_AVERAGE_GAP_MS * 2;

		if (!continuedInput) {
			inputStartedAt = now;
			recordedCharacters = addedCharacters || value.length;
		} else {
			recordedCharacters += addedCharacters;
		}

		lastInputAt = now;
		previousInputValue = value;
	}

	function isLikelyScannerEntry(value, now = performance.now()) {
		if (value.length < SCANNER_MIN_LENGTH || recordedCharacters < value.length || !lastInputAt) {
			return false;
		}
		const averageGap =
			recordedCharacters > 1 ? (lastInputAt - inputStartedAt) / (recordedCharacters - 1) : 0;
		return averageGap <= SCANNER_MAX_AVERAGE_GAP_MS && now - lastInputAt <= SCANNER_ENTER_GAP_MS;
	}

	// ---- Clear ----

	/** Atomic clear: timer -> store -> DOM input.value -> refocus */
	function clearSearchAndResetInput() {
		clearAutoSearchTimer();
		inputGeneration += 1;
		itemStore.clearSearch();
		if (searchInputRef.value) {
			searchInputRef.value.value = "";
		}
		resetInputTiming();
		focusSearchInput();
	}

	// ---- Event handlers ----

	function handleKeyDown(event) {
		if (event.key === "ArrowDown" || event.key === "ArrowUp") {
			if (onNavigateResults?.(event.key === "ArrowDown" ? 1 : -1)) {
				event.preventDefault();
				event.stopPropagation?.();
			}
			return;
		}

		if (event.key === "Enter") {
			event.preventDefault();
			event.stopPropagation?.();
			clearAutoSearchTimer();

			const value = searchInputRef.value?.value?.trim() || itemStore.searchTerm?.trim();
			if (!value) return;

			const shouldTryBarcode =
				/^\d+$/.test(value) || isLikelyScannerEntry(value) || autoAddEnabled.value;
			if (shouldTryBarcode) {
				const generation = inputGeneration;
				itemStore.clearSearch();
				if (searchInputRef.value) searchInputRef.value.value = "";
				resetInputTiming();
				processBarcodeScan(value, generation);
			} else if (onSelectHighlighted?.()) {
				clearSearchAndResetInput();
			} else {
				// Alphanumeric manual input remains a normal Item Code/Name/Barcode search.
				itemStore.setSearchTerm(value);
			}
			return;
		}
	}

	/**
	 * Handles the `input` event on the search <input>.
	 *
	 * Two independent timers exist by design:
	 *   1. itemStore.setSearchTerm() triggers the store's own debounce for
	 *      updating the displayed item grid.
	 *   2. autoSearchTimer (500 ms) triggers auto-add behaviour — completely
	 *      separate from display.
	 */
	function handleSearchInput(event) {
		const value = event.target.value;
		inputGeneration += 1;
		recordInputTiming(value);

		// Guard: ignore stale empty events after search was already cleared
		if (!value && !itemStore.searchTerm) {
			return;
		}

		itemStore.setSearchTerm(value);

		clearAutoSearchTimer();

		// Optional auto-add still performs an exact barcode attempt, then falls
		// back to the same normal search if no barcode matches.
		if (autoAddEnabled.value && value.trim().length > 0) {
			autoSearchTimer = setTimeout(() => {
				const capturedValue = searchInputRef.value?.value?.trim() || itemStore.searchTerm?.trim();
				if (capturedValue) {
					const generation = inputGeneration;
					itemStore.clearSearch();
					if (searchInputRef.value) searchInputRef.value.value = "";
					resetInputTiming();
					processBarcodeScan(capturedValue, generation);
				}
			}, 500);
		}
	}

	/** Clicking the search input clears search + timer atomically. */
	function handleSearchClick() {
		clearSearchAndResetInput();
	}

	/**
	 * Queue a barcode scan for sequential processing.
	 *
	 * The barcode string is already captured (snapshotted) by the caller —
	 * it is never read from shared state here. The {@link QueuedMutex}
	 * ensures scans execute one at a time so every scan is resolved before
	 * the next begins, preventing double-adds and lost barcodes.
	 *
	 * Lookup: exact match via the existing `itemStore.searchByBarcode()` flow.
	 * A miss is restored into the unified field and sent through normal search.
	 *
	 * @param {string} value - Pre-captured input value
	 * @param {number} generation - Input generation captured before clearing
	 */
	function processBarcodeScan(value, generation) {
		return barcodeQueue.withLock(async () => {
			try {
				const item = await itemStore.searchByBarcode(value);
				if (item) {
					onItemFound(item, true);
					focusSearchInput();
					return;
				}
			} catch {
				// A barcode miss is expected for numeric Item Codes and normal searches.
			}

			// Do not overwrite a newer scan or manually entered query while this
			// queued lookup was waiting for the API.
			if (inputGeneration !== generation || searchInputRef.value?.value?.trim()) return;

			if (searchInputRef.value) searchInputRef.value.value = value;
			itemStore.setSearchTerm(value);
			focusSearchInput();
		});
	}

	// ---- Toggles ----

	function toggleAutoAdd() {
		autoAddEnabled.value = !autoAddEnabled.value;

		if (!autoAddEnabled.value) {
			clearAutoSearchTimer();
		}

		if (autoAddEnabled.value) {
			focusSearchInput();
		}
	}

	// ---- Dialog-close watcher ----
	// Keep the unified field ready for the next physical scan after dialogs close.
	const stopDialogWatcher = watch(isAnyDialogOpen, (isOpen, wasOpen) => {
		if (wasOpen && !isOpen) {
			focusSearchInput();
		}
	});

	// ---- Cleanup ----
	function cleanup() {
		clearAutoSearchTimer();
		stopDialogWatcher();
	}

	onUnmounted(cleanup);

	return {
		// State
		searchInputRef,
		autoAddEnabled,

		// Event handlers
		handleSearchInput,
		handleKeyDown,
		handleSearchClick,

		// Toggles
		toggleAutoAdd,

		// Utilities
		focusSearchInput,
		clearSearchAndResetInput,
		cleanup,
	};
}
