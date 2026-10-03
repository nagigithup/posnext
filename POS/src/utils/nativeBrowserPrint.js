const activeJobs = new Map()
const cooldowns = new Map()

const ERROR_MESSAGE = "تعذر تجهيز المستند للطباعة."
const LOAD_TIMEOUT_MS = 30_000
const ASSET_TIMEOUT_MS = 10_000
const CLEANUP_TIMEOUT_MS = 120_000
const DOUBLE_PRINT_COOLDOWN_MS = 3_000

function withTimeout(promise, timeoutMs, message) {
	let timer
	return Promise.race([
		promise,
		new Promise((_, reject) => {
			timer = window.setTimeout(() => reject(new Error(message)), timeoutMs)
		}),
	]).finally(() => window.clearTimeout(timer))
}

function showPrintError(error) {
	console.error("Native browser printing failed:", error)
	if (window.frappe?.msgprint) {
		window.frappe.msgprint({
			title: window.__ ? window.__("Print Error") : "Print Error",
			message: ERROR_MESSAGE,
			indicator: "red",
		})
	}
}

function waitForImages(doc) {
	return Promise.all(
		Array.from(doc.images || []).map(async (image) => {
			if (!image.complete) {
				await new Promise((resolve) => {
					image.addEventListener("load", resolve, { once: true })
					image.addEventListener("error", resolve, { once: true })
				})
			}
			if (image.decode) await image.decode().catch(() => {})
		}),
	)
}

async function waitForAssets(doc) {
	if (doc.readyState !== "complete") {
		await withTimeout(
			new Promise((resolve) =>
				doc.addEventListener("readystatechange", resolve, { once: true }),
			),
			ASSET_TIMEOUT_MS,
			"Print document readiness timed out",
		)
	}
	await withTimeout(
		waitForImages(doc),
		ASSET_TIMEOUT_MS,
		"Print images timed out",
	)
	if (doc.fonts?.ready) {
		await withTimeout(
			doc.fonts.ready.catch(() => undefined),
			ASSET_TIMEOUT_MS,
			"Print fonts timed out",
		)
	}
	await new Promise((resolve) => {
		window.requestAnimationFrame(() => window.requestAnimationFrame(resolve))
	})
}

function createPrintFrame() {
	const iframe = document.createElement("iframe")
	iframe.title = "Print document"
	iframe.setAttribute("aria-hidden", "true")
	iframe.style.cssText =
		"position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0;pointer-events:none;"
	document.body.appendChild(iframe)
	return iframe
}

function loadFrame(iframe, url) {
	return withTimeout(
		new Promise((resolve, reject) => {
			iframe.addEventListener("load", resolve, { once: true })
			iframe.addEventListener(
				"error",
				() => reject(new Error("Print view failed to load")),
				{
					once: true,
				},
			)
			iframe.src = url
		}),
		LOAD_TIMEOUT_MS,
		"Print view timed out",
	)
}

/**
 * Print a saved document through Frappe's same-origin Print View.
 * Chrome's native print() intentionally handles both normal and --kiosk-printing modes.
 */
export async function nativeBrowserPrint(
	doctype,
	docname,
	printFormat,
	options = {},
) {
	if (
		![doctype, docname, printFormat].every(
			(value) => typeof value === "string" && value.trim(),
		)
	) {
		const error = new Error("A saved document and Print Format are required")
		showPrintError(error)
		throw error
	}

	const key = `${doctype}::${docname}::${printFormat}`
	if (activeJobs.has(key)) return activeJobs.get(key)
	if ((cooldowns.get(key) || 0) > Date.now()) return false

	const job = (async () => {
		const iframe = createPrintFrame()
		let cleanupTimer
		let cleaned = false
		const cleanup = () => {
			if (cleaned) return
			cleaned = true
			window.clearTimeout(cleanupTimer)
			iframe.remove()
		}

		try {
			const params = new URLSearchParams({
				doctype,
				name: docname,
				format: printFormat,
				no_letterhead: options.letterhead ? "0" : "1",
			})
			if (options.letterhead) params.set("letterhead", options.letterhead)
			if (options.language) params.set("_lang", options.language)

			await loadFrame(iframe, `/printview?${params}`)
			const printWindow = iframe.contentWindow
			const printDocument = iframe.contentDocument
			if (
				!printWindow ||
				!printDocument?.body ||
				!printDocument.querySelector(".print-format") ||
				printWindow.location.origin !== window.location.origin ||
				printWindow.location.pathname !== "/printview"
			) {
				throw new Error("Invalid print view response")
			}

			await waitForAssets(printDocument)
			// Retain the iframe while Chrome's print renderer consumes its document.
			printWindow.addEventListener(
				"afterprint",
				() => window.setTimeout(cleanup, 1_000),
				{
					once: true,
				},
			)
			cleanupTimer = window.setTimeout(cleanup, CLEANUP_TIMEOUT_MS)
			cooldowns.set(key, Date.now() + DOUBLE_PRINT_COOLDOWN_MS)
			printWindow.focus()
			printWindow.print()
			return true
		} catch (error) {
			cleanup()
			showPrintError(error)
			throw error
		}
	})()

	activeJobs.set(key, job)
	try {
		return await job
	} finally {
		activeJobs.delete(key)
	}
}
