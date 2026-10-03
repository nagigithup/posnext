// @vitest-environment jsdom

import { describe, expect, it, vi } from "vitest";

vi.mock("qz-tray", () => ({
	default: {
		security: {},
		websocket: {},
		printers: {},
		configs: {},
	},
}));
vi.mock("@/utils/apiWrapper", () => ({ call: vi.fn() }));
vi.mock("@/utils/logger", () => ({
	logger: {
		create: () => ({ info: vi.fn(), warn: vi.fn(), error: vi.fn() }),
	},
}));

import { buildBase64PixelPayload, buildThermalPrintOptions, selectSavedPrinter } from "./qzTray";

describe("QZ rendered receipt payload", () => {
	it("sends real PDF bytes as a base64 pixel job", () => {
		expect(buildBase64PixelPayload("pdf", "JVBERi0xLjQ=")).toEqual([
			{
				type: "pixel",
				format: "pdf",
				flavor: "base64",
				data: "JVBERi0xLjQ=",
			},
		]);
	});

	it("uses the measured 80 mm custom receipt dimensions", () => {
		const options = buildThermalPrintOptions("pdf", {
			width: 80,
			height: 247,
			jobName: "Receipt ACC-SINV-1",
		});
		expect(options.size).toEqual({ width: 80, height: 247, custom: true });
		expect(options.units).toBe("mm");
		expect(options.rasterize).toBe(true);
		expect(options.margins).toEqual({ top: 0, right: 0, bottom: 0, left: 0 });
	});

	it("sends offline PNG bytes as a base64 image job", () => {
		expect(buildBase64PixelPayload("image", "iVBORw0KGgo=")[0]).toMatchObject({
			type: "pixel",
			format: "image",
			flavor: "base64",
		});
		expect(buildThermalPrintOptions("image", { height: 120 }).scaleContent).toBe(true);
	});

	it("uses the saved printer only while it is currently available", () => {
		expect(selectSavedPrinter("Receipt Printer", ["Receipt Printer", "Office"])).toBe("Receipt Printer");
		expect(selectSavedPrinter("Missing Printer", ["Office"])).toBe("");
		expect(selectSavedPrinter("", ["Office"])).toBe("");
	});
});
