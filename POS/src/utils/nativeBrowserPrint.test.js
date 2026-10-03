// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest"

import { nativeBrowserPrint } from "./nativeBrowserPrint"

describe("nativeBrowserPrint", () => {
	afterEach(() => {
		vi.restoreAllMocks()
		vi.unstubAllGlobals()
	})

	it("loads the selected Print Format and calls the iframe native print function", async () => {
		vi.spyOn(window, "setTimeout").mockImplementation(() => 1)
		const listeners = {}
		const printWindow = {
			location: { origin: window.location.origin, pathname: "/printview" },
			addEventListener: vi.fn(),
			focus: vi.fn(),
			print: vi.fn(),
		}
		const printDocument = {
			body: {},
			readyState: "complete",
			images: [],
			fonts: { ready: Promise.resolve() },
			querySelector: vi.fn(() => ({})),
		}
		const iframe = {
			style: {},
			setAttribute: vi.fn(),
			addEventListener: vi.fn((event, callback) => {
				listeners[event] = callback
			}),
			remove: vi.fn(),
			contentWindow: printWindow,
			contentDocument: printDocument,
		}
		Object.defineProperty(iframe, "src", {
			set(value) {
				this.loadedUrl = value
				queueMicrotask(() => listeners.load())
			},
		})
		vi.spyOn(document, "createElement").mockReturnValue(iframe)
		vi.spyOn(document.body, "appendChild").mockImplementation(() => iframe)
		vi.stubGlobal("requestAnimationFrame", (callback) => callback())

		await Promise.all([
			nativeBrowserPrint("Sales Invoice", "SINV/0001", "POS Next Receipt"),
			nativeBrowserPrint("Sales Invoice", "SINV/0001", "POS Next Receipt"),
		])

		expect(iframe.loadedUrl).toContain("/printview?")
		expect(iframe.loadedUrl).toContain("doctype=Sales+Invoice")
		expect(iframe.loadedUrl).toContain("name=SINV%2F0001")
		expect(iframe.loadedUrl).toContain("format=POS+Next+Receipt")
		expect(iframe.loadedUrl).toContain("no_letterhead=1")
		expect(printWindow.focus).toHaveBeenCalledOnce()
		expect(printWindow.print).toHaveBeenCalledOnce()
		expect(document.createElement).toHaveBeenCalledOnce()
		expect(printWindow.addEventListener).toHaveBeenCalledWith(
			"afterprint",
			expect.any(Function),
			{ once: true },
		)
	})
})
