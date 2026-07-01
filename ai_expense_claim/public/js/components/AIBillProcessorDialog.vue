<template>
	<div class="ai-bill-processor-wrapper">
		<div
			class="ai-dropzone"
			:class="{ dragover: is_dragging }"
			@dragover.prevent="is_dragging = true"
			@dragleave.prevent="is_dragging = false"
			@drop.prevent="on_drop"
			@click="$refs.file_input.click()"
		>
			<input
				ref="file_input"
				type="file"
				class="hidden"
				multiple
				accept="image/*,.pdf"
				@change="on_file_input"
			/>
			<div class="ai-drop-icon" v-html="frappe.utils.icon('upload', 'xl')"></div>
			<p class="ai-drop-label">{{ __("Click or drop files here") }}</p>
			<p class="ai-drop-hint">{{ __("Supports PDF and images (JPG, PNG, WEBP)") }}</p>
		</div>

		<template v-if="files.length">
			<div class="ai-list-header">
				<span>{{ __("Files to process") }}</span>
				<span class="badge badge-pill badge-primary">{{ files.length }}</span>
			</div>
			<div ref="sortable_el" class="ai-file-list">
				<AIBillFileItem
					v-for="file in files"
					:key="file.id"
					:file="file"
					@remove="remove_file(file.id)"
				/>
			</div>
		</template>
	</div>
</template>

<script setup>
import { ref, nextTick } from "vue";
import AIBillFileItem from "./AIBillFileItem.vue";

const props = defineProps({
	frm: { required: true }
});

const file_input = ref(null);
const sortable_el = ref(null);
const files = ref([]);
const is_dragging = ref(false);

let id_seq = 0;
let sortable = null;

function init_sortable() {
	if (!window.Sortable || !sortable_el.value || sortable) return;
	sortable = new window.Sortable(sortable_el.value, {
		animation: 150,
		handle: ".drag-handle",
		onEnd(evt) {
			const moved = files.value.splice(evt.oldIndex, 1)[0];
			files.value.splice(evt.newIndex, 0, moved);
		},
	});
}

function on_file_input(e) {
	add_files(e.target.files);
	e.target.value = "";
}

function on_drop(e) {
	is_dragging.value = false;
	add_files(e.dataTransfer.files);
}

function add_files(file_list) {
	const allowed = ["image/jpeg", "image/png", "image/webp", "application/pdf"];
	
	const added = Array.from(file_list)
		.filter((f) => {
			const ok = allowed.includes(f.type);
			if (!ok) {
				frappe.show_alert({
					message: __('"{0}" is not supported. Use PDF or image files.', [f.name]),
					indicator: "orange",
				});
			}
			return ok;
		})
		.filter((f) => {
			// Check for duplicates
			const duplicate = files.value.find(existing => 
				existing.name === f.name && existing.size === f.size
			);
			return !duplicate;
		})
		.map((f) => {
			const item = {
				id: ++id_seq,
				file_obj: f,
				name: f.name,
				type: f.type,
				size: f.size,
				preview: null,
			};
			
			if (f.type.startsWith("image/")) {
				const reader = new FileReader();
				reader.onload = (e) => (item.preview = e.target.result);
				reader.readAsDataURL(f);
			}
			
			return item;
		});

	files.value = files.value.concat(added);
	nextTick(() => init_sortable());
}

function remove_file(id) {
	files.value = files.value.filter((f) => f.id !== id);
	if (!files.value.length) {
		sortable?.destroy();
		sortable = null;
	}
}

async function process_bills() {
	if (!files.value.length) {
		frappe.show_alert({ 
			message: __("Please select at least one file to process."), 
			indicator: "orange" 
		});
		return null;
	}

	try {
		// Convert files to base64
		const file_data = await Promise.all(
			files.value.map(
				(f) =>
					new Promise((resolve, reject) => {
						const reader = new FileReader();
						reader.onload = (e) => resolve({
							name: f.name,
							data: e.target.result,
							type: f.type
						});
						reader.onerror = reject;
						reader.readAsDataURL(f.file_obj);
					})
			)
		);

		// Call backend to process bills
		const r = await frappe.call({
			method: "ai_expense_claim.api.expense.prepare_grouped_expenses",
			args: { files: JSON.stringify(file_data) },
			freeze: true,
			freeze_message: __("Processing Your Bills...")
		});

		const response = r.message || {};
		const groups = response.groups || [];
		const low_confidence_files = response.low_confidence_files || [];
		
		if (!groups.length && !low_confidence_files.length) {
			frappe.throw(__("No data could be extracted from the files."));
		}
		
		// Show warnings for low confidence files
		if (low_confidence_files.length > 0) {
			const warnings = low_confidence_files.map(f => 
				`<li><strong>${f.file}</strong>: ${f.reason} (${f.confidence}% confidence)</li>`
			).join("");
			frappe.msgprint({
				title: __("Some Files Skipped"),
				message: `
					<p>${__("The following files were skipped due to low confidence:")}</p>
					<ul>${warnings}</ul>
				`,
				indicator: "orange"
			});
			
			if (groups.length === 0) return null;
		}
		
		return groups;
		
	} catch (err) {
		console.error("Bill processing error:", err);
		frappe.msgprint({
			title: __("Error"),
			message: err.message || __("Failed to process bills"),
			indicator: "red"
		});
		return null;
	}
}

// Expose methods to parent
defineExpose({
	process_bills,
	has_files: () => files.value.length > 0
});
</script>

<style scoped>
.ai-bill-processor-wrapper {
	min-height: 200px;
}

.ai-dropzone {
	border: 2px dashed var(--border-color);
	border-radius: var(--border-radius-lg);
	padding: 48px 20px;
	text-align: center;
	cursor: pointer;
	transition: all 0.3s;
	background: var(--bg-light-gray);
	margin-bottom: 16px;
}

.ai-dropzone:hover {
	border-color: var(--primary);
	background: var(--blue-50, #eff6ff);
}

.ai-dropzone.dragover {
	border-color: var(--primary);
	background: var(--blue-100, #dbeafe);
	transform: scale(1.01);
}

.ai-drop-icon {
	font-size: 48px;
	color: var(--text-muted);
	margin-bottom: 12px;
	display: flex;
	justify-content: center;
}

.ai-drop-label {
	font-size: 15px;
	font-weight: 500;
	margin: 0 0 6px;
	color: var(--text-color);
}

.ai-drop-hint {
	font-size: 13px;
	color: var(--text-muted);
	margin: 0;
}

.ai-list-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	margin: 16px 0 8px;
	font-size: 12px;
	color: var(--text-muted);
}

.ai-file-list {
	display: flex;
	flex-direction: column;
	gap: 8px;
	margin-top: 8px;
}
</style>
