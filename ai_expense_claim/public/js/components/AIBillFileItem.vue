<template>
	<div class="ai-bill-file-item">
		<div class="drag-handle" v-html="frappe.utils.icon('drag', 'sm')"></div>
		<div class="item-thumb" @click.stop>
			<img v-if="file.preview" :src="file.preview" :alt="file.name" />
			<div v-else class="pdf-icon">
				<span v-html="frappe.utils.icon('file', 'sm')"></span>
				<span class="pdf-ext">PDF</span>
			</div>
		</div>
		<div class="item-meta">
			<div class="item-name" :title="file.name">{{ file.name }}</div>
			<div class="item-size">{{ fmt_size(file.size) }}</div>
		</div>
		<div class="item-actions">
			<button
				class="btn btn-xs btn-default"
				:title="__('Remove')"
				@click="emit('remove')"
				v-html="frappe.utils.icon('delete', 'sm')"
			></button>
		</div>
	</div>
</template>

<script setup>
const props = defineProps({ file: Object });
const emit = defineEmits(["remove"]);

function fmt_size(bytes) {
	if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + " MB";
	if (bytes >= 1024) return (bytes / 1024).toFixed(1) + " KB";
	return bytes + " B";
}
</script>

<style scoped>
.ai-bill-file-item {
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 10px 12px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius);
	background: var(--card-bg);
	cursor: default;
	transition: all 0.2s;
}

.ai-bill-file-item:hover {
	background: var(--bg-light-gray);
}

.drag-handle {
	cursor: grab;
	color: var(--text-muted);
	flex-shrink: 0;
	display: flex;
	align-items: center;
}

.drag-handle:active {
	cursor: grabbing;
}

.item-thumb {
	width: 48px;
	height: 48px;
	border-radius: var(--border-radius-sm);
	overflow: hidden;
	flex-shrink: 0;
	background: var(--bg-light-gray);
	display: flex;
	align-items: center;
	justify-content: center;
}

.item-thumb img {
	width: 100%;
	height: 100%;
	object-fit: cover;
}

.pdf-icon {
	display: flex;
	flex-direction: column;
	align-items: center;
	line-height: 1;
	color: var(--text-muted);
}

.pdf-ext {
	font-size: 10px;
	font-weight: 700;
	color: var(--red-500);
	margin-top: 2px;
}

.item-meta {
	flex: 1;
	min-width: 0;
}

.item-name {
	font-size: 13px;
	font-weight: 500;
	margin-bottom: 2px;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.item-size {
	font-size: 12px;
	color: var(--text-muted);
}

.item-actions {
	display: flex;
	gap: 6px;
	flex-shrink: 0;
	align-items: center;
}

.item-actions .btn {
	padding: 4px 8px;
	color: var(--text-muted);
}

.item-actions .btn:hover {
	color: var(--text-color);
}
</style>
