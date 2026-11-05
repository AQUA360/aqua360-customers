<script setup>
// Navegador de l'esquema (taules i columnes consultables) dels informes personalitzats.
import { ref, computed } from 'vue';

const props = defineProps({
  schema: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
});
const emit = defineEmits(['insert']);
const { t } = useI18n();

const filter = ref('');
const expanded = ref(new Set());

const filtered = computed(() => {
  const q = filter.value.trim().toLowerCase();
  if (!q) return props.schema.map((table) => ({ ...table, visibleColumns: table.columns, forceOpen: false }));
  return props.schema
    .map((table) => {
      const tableMatch = table.table.toLowerCase().includes(q);
      const columns = tableMatch ? table.columns : table.columns.filter((c) => c.name.toLowerCase().includes(q));
      return { ...table, visibleColumns: columns, forceOpen: !tableMatch && columns.length > 0 };
    })
    .filter((table) => table.table.toLowerCase().includes(q) || table.visibleColumns.length > 0);
});

const toggle = (name) => {
  const next = new Set(expanded.value);
  next.has(name) ? next.delete(name) : next.add(name);
  expanded.value = next;
};
const isOpen = (table) => table.forceOpen || expanded.value.has(table.table);
</script>

<template>
  <div class="flex h-full min-h-0 flex-col">
    <input
      v-model="filter"
      type="search"
      class="mb-2 w-full rounded border border-slate-300 px-2 py-1.5 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
      :placeholder="t('custom_report_block.schema_filter')"
    />
    <p class="mb-2 text-xs text-slate-500">{{ t('custom_report_block.schema_insert_hint') }}</p>
    <div v-if="loading" class="py-4 text-center text-sm text-slate-500">{{ t('custom_report_block.schema_loading') }}</div>
    <ul v-else class="min-h-0 flex-1 overflow-y-auto pr-1 text-sm">
      <li v-for="table in filtered" :key="table.table" class="mb-0.5">
        <div class="flex items-center gap-1">
          <button type="button" class="rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700" @click="toggle(table.table)">
            <Icon :name="isOpen(table) ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" class="text-[10px]" />
          </button>
          <button
            type="button"
            class="min-w-0 truncate rounded px-1 text-left font-mono text-[13px] text-slate-800 hover:bg-sky-50 hover:text-sky-800"
            :title="table.table"
            @click="emit('insert', table.table)"
          >
            {{ table.table }}
          </button>
          <span v-if="table.is_view" class="shrink-0 rounded bg-slate-100 px-1 text-[10px] uppercase text-slate-500">{{ t('custom_report_block.view') }}</span>
        </div>
        <ul v-if="isOpen(table)" class="ml-5 border-l border-slate-200 pl-2">
          <li v-for="column in table.visibleColumns" :key="column.name">
            <button
              type="button"
              class="flex w-full items-baseline justify-between gap-2 rounded px-1 text-left hover:bg-sky-50"
              @click="emit('insert', column.name)"
            >
              <span class="truncate font-mono text-[12px] text-slate-700">{{ column.name }}</span>
              <span class="shrink-0 text-[10px] text-slate-400">{{ column.type }}</span>
            </button>
          </li>
        </ul>
      </li>
    </ul>
  </div>
</template>
