<template>
	<Dialog v-model="open" :options="{ title: 'قفل الكاشير المبدئي', size: 'lg' }">
		<template #body-content>
			<div dir="rtl" class="text-right">
				<div v-if="loading" class="py-12 flex justify-center" aria-live="polite">
					<div class="h-10 w-10 animate-spin rounded-full border-4 border-gray-200 border-t-emerald-600"></div>
				</div>

				<p
					v-else-if="submitted"
					class="py-12 text-center text-base font-semibold text-emerald-800"
					aria-live="polite"
				>
					تم إرسال إقفال الوردية إلى المحاسب للمراجعة.
				</p>

				<form v-else class="space-y-5" @submit.prevent="submitDeclaration">
					<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
						<div>
							<label class="mb-1.5 block text-sm font-medium text-gray-700">POS Profile</label>
							<div class="min-h-10 border-b border-gray-200 py-2 text-sm text-gray-900">
								{{ context?.pos_profile }}
							</div>
						</div>
						<div>
							<label class="mb-1.5 block text-sm font-medium text-gray-700">وقت فتح الوردية</label>
							<div class="min-h-10 border-b border-gray-200 py-2 text-sm text-gray-900">
								{{ formatDateTime(context?.opening_datetime) }}
							</div>
						</div>
					</div>

					<div>
						<label for="cashier-cash-amount" class="mb-1.5 block text-sm font-medium text-gray-800">
							رصيد الخزينة
						</label>
						<input
							id="cashier-cash-amount"
							v-model.number="cashAmount"
							type="number"
							min="0"
							step="0.01"
							inputmode="decimal"
							required
							class="h-12 w-full rounded-md border border-gray-300 bg-white px-3 text-lg text-gray-900 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
						/>
					</div>

					<div>
						<label for="cashier-network-amount" class="mb-1.5 block text-sm font-medium text-gray-800">
							رصيد مبيعات الشبكة
						</label>
						<input
							id="cashier-network-amount"
							v-model.number="networkAmount"
							type="number"
							min="0"
							step="0.01"
							inputmode="decimal"
							required
							class="h-12 w-full rounded-md border border-gray-300 bg-white px-3 text-lg text-gray-900 outline-none focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100"
						/>
					</div>

					<p v-if="errorMessage" class="text-sm text-red-700" role="alert">
						{{ errorMessage }}
					</p>

					<button
						type="submit"
						:disabled="submitting"
						class="h-12 w-full rounded-md bg-emerald-700 px-4 text-base font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-60"
					>
						{{ submitting ? "جارٍ الإرسال..." : "إرسال" }}
					</button>
				</form>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { call } from "@/utils/apiWrapper"
import { Dialog } from "frappe-ui"
import { computed, ref, watch } from "vue"

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	openingShift: { type: String, default: null },
})
const emit = defineEmits(["update:modelValue", "submitted"])

const context = ref(null)
const cashAmount = ref(null)
const networkAmount = ref(null)
const loading = ref(false)
const submitting = ref(false)
const submitted = ref(false)
const errorMessage = ref("")

const open = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
})

watch(
	() => props.modelValue,
	(value) => {
		if (value && !submitted.value) loadContext()
	},
)

async function loadContext() {
	loading.value = true
	errorMessage.value = ""
	try {
		const data = await call(
			"pos_next.api.preliminary_closing.get_preliminary_closing_context",
			{},
		)
		if (props.openingShift && data?.pos_opening_shift !== props.openingShift) {
			throw new Error("وردية الفتح الحالية لا تطابق وردية الكاشير.")
		}
		context.value = data
	} catch (error) {
		errorMessage.value = getErrorMessage(error)
	} finally {
		loading.value = false
	}
}

async function submitDeclaration() {
	if (!context.value || submitting.value) return
	submitting.value = true
	errorMessage.value = ""
	try {
		await call("pos_next.api.preliminary_closing.submit_preliminary_closing", {
			pos_opening_shift: context.value.pos_opening_shift,
			cash_amount: cashAmount.value,
			network_amount: networkAmount.value,
		})
		submitted.value = true
		emit("submitted")
	} catch (error) {
		errorMessage.value = getErrorMessage(error)
	} finally {
		submitting.value = false
	}
}

function formatDateTime(value) {
	if (!value) return ""
	return new Intl.DateTimeFormat("ar", {
		dateStyle: "medium",
		timeStyle: "short",
	}).format(new Date(value))
}

function getErrorMessage(error) {
	return error?.messages?.[0] || error?.message || "تعذر إرسال الإقفال المبدئي."
}
</script>
