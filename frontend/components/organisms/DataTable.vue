<script setup>
import { computed, ref, onMounted, onUnmounted, nextTick, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useSidebarStore } from '~/stores/useNavSideBar';
import AppLoading from '~/components/atoms/AppLoading.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';
import { useTableColumns } from '~/composables/useTableColumns';

const props = defineProps({
  // --- Legacy mode -------------------------------------------------------
  // CSS grid-template-columns value for the data columns (without the pin
  // column), e.g. "80px,120px,2fr,1fr,50px,120px,150px,150px,130px".
  // Ignored when `columns` is provided.
  gridTemplate: {
    type: String,
    default: '',
  },

  // --- Column mode -------------------------------------------------------
  // Column descriptors; see `useTableColumns` for the shape. When provided the
  // table renders its own header (sorting included), lets the user resize and
  // pick columns, and drops the least important ones on narrow screens.
  columns: {
    type: Array,
    default: null,
  },
  // Stable id used to persist the per-user column layout. Required with `columns`.
  tableKey: {
    type: String,
    default: '',
  },
  // Rows to render. In column mode the table owns the row loop and exposes a
  // `cell-<column key>` slot per column.
  items: {
    type: Array,
    default: () => [],
  },
  rowKey: {
    type: String,
    default: 'id',
  },
  // (item) => class binding for the row wrapper.
  rowClass: {
    type: Function,
    default: null,
  },
  currentSortBy: {
    type: String,
    default: '',
  },
  sortDesc: {
    type: Boolean,
    default: false,
  },

  // --- Shared ------------------------------------------------------------
  // Reserves a leading fixed-width column for a pin/indicator icon, shared by
  // header and rows so an occasional extra column never desyncs the grid.
  pinColumn: {
    type: Boolean,
    default: false,
  },
  pinColumnWidth: {
    type: String,
    default: '12px',
  },
  // Vertical space (px) reserved above the table (title, filters, footer...).
  heightOffset: {
    type: Number,
    default: 230,
  },
  pending: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: [Object, Error, null],
    default: null,
  },
  isEmpty: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['retry', 'scroll', 'sort']);

const { t } = useI18n();
const sidebarStore = useSidebarStore();

const isColumnMode = computed(() => Array.isArray(props.columns) && props.columns.length > 0);

const {
  definitions,
  visibleColumns,
  autoHiddenColumns,
  gridTemplate: managedGridTemplate,
  isVisible,
  isCustomised,
  toggleColumn,
  moveColumnTo,
  moveColumnBy,
  setColumnWidth,
  clearColumnWidth,
  resetColumns,
  setAvailableWidth,
} = useTableColumns(
  props.tableKey || 'data-table',
  computed(() => props.columns || []),
  {
    // Space the tracks never get: the row's own `px-1` + `pr-9` (the column
    // picker button lives there), plus the fixed pin track when present.
    chromeWidth: 4 + 36 + (props.pinColumn ? 12 : 0),
    // Must match the `gap-2` the header and rows use in column mode.
    gapWidth: 8,
  }
);

// The legacy `gridTemplate` prop is authored comma-separated (matching the old
// `grid-cols-[a,b,c]` Tailwind convention) and has to be turned into the
// space-separated form CSS expects. Commas INSIDE parentheses (`minmax(a, b)`)
// belong to the track, so only the top-level commas split tracks. The managed
// template is already space-separated and must NOT be split: its tracks contain
// commas of their own, and splitting them collapses the whole grid.
const splitGridTemplate = (template) => {
  const tracks = [];
  let depth = 0;
  let current = '';
  for (const char of template) {
    if (char === '(') depth += 1;
    else if (char === ')') depth = Math.max(0, depth - 1);
    if (char === ',' && depth === 0) {
      tracks.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  tracks.push(current);
  return tracks;
};

const dataColumnsTemplate = computed(() =>
  isColumnMode.value ? managedGridTemplate.value : splitGridTemplate(props.gridTemplate).join(' ')
);

const gridStyle = computed(() => ({
  display: 'grid',
  gridTemplateColumns: props.pinColumn
    ? `${props.pinColumnWidth} ${dataColumnsTemplate.value}`
    : dataColumnsTemplate.value,
}));

const containerStyle = computed(() => ({
  width: 'calc(100vw - ' + sidebarStore.sidebarWidth + 'px)',
  maxWidth: '100%',
  minHeight: 'calc(100vh - ' + props.heightOffset + 'px)',
  maxHeight: 'calc(100vh - ' + props.heightOffset + 'px)',
}));

const scrollStyle = computed(() => ({
  width: 'calc(100vw - ' + sidebarStore.sidebarWidth + 'px)',
  maxWidth: '100%',
}));

// --- Responsive measuring ------------------------------------------------

const container = ref(null);
let resizeObserver = null;
let measureFrame = null;

/**
 * Re-measure the table and let the responsive pass decide which columns fit.
 * Deferred to the next animation frame: the measurement changes the layout that
 * produced it, and reacting synchronously makes the browser report a
 * "ResizeObserver loop completed with undelivered notifications" warning.
 */
const measure = () => {
  if (measureFrame) cancelAnimationFrame(measureFrame);
  measureFrame = requestAnimationFrame(() => {
    measureFrame = null;
    if (container.value) setAvailableWidth(container.value.getBoundingClientRect().width);
  });
};

const attachObserver = () => {
  if (!isColumnMode.value || resizeObserver || !container.value) return;
  if (typeof ResizeObserver === 'undefined') return;
  resizeObserver = new ResizeObserver(measure);
  resizeObserver.observe(container.value);
};

onMounted(() => {
  if (!isColumnMode.value) return;
  nextTick(() => {
    attachObserver();
    // Covers the first paint plus browsers without ResizeObserver, where the
    // window listener below is the only signal we get.
    measure();
  });
  // A window resize always changes the container too, so this is normally
  // redundant with the observer — it is the fallback that keeps the table
  // responsive if the observer could not be created.
  window.addEventListener('resize', measure);
});

// The columns may only arrive after the first render (they depend on loaded
// translations or permissions), so the observer has to be able to attach late.
watch(isColumnMode, (enabled) => {
  if (enabled) nextTick(() => { attachObserver(); measure(); });
});

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect();
  if (measureFrame) cancelAnimationFrame(measureFrame);
  window.removeEventListener('resize', measure);
  stopResize();
});

// --- Column resizing -----------------------------------------------------

const headerRefs = ref({});
const resizingKey = ref(null);
let resizeStartX = 0;
let resizeStartWidth = 0;

const setHeaderRef = (key) => (el) => {
  if (el) headerRefs.value[key] = el;
  else delete headerRefs.value[key];
};

const onResizeMove = (event) => {
  if (!resizingKey.value) return;
  setColumnWidth(resizingKey.value, resizeStartWidth + (event.clientX - resizeStartX));
};

const stopResize = () => {
  if (!resizingKey.value) return;
  resizingKey.value = null;
  document.body.style.userSelect = '';
  document.body.style.cursor = '';
  window.removeEventListener('mousemove', onResizeMove);
  window.removeEventListener('mouseup', stopResize);
};

const startResize = (column, event) => {
  const el = headerRefs.value[column.key];
  if (!el) return;
  resizingKey.value = column.key;
  resizeStartX = event.clientX;
  resizeStartWidth = el.getBoundingClientRect().width;
  // Keep the drag from selecting the header labels it passes over.
  document.body.style.userSelect = 'none';
  document.body.style.cursor = 'col-resize';
  window.addEventListener('mousemove', onResizeMove);
  window.addEventListener('mouseup', stopResize);
};

// --- Column reordering ---------------------------------------------------

const draggedKey = ref(null);
const dropTargetKey = ref(null);

// A drag starting on the resize grip is a resize, not a reorder.
const onHeaderDragStart = (column, event) => {
  if (resizingKey.value) {
    event.preventDefault();
    return;
  }
  draggedKey.value = column.key;
  event.dataTransfer.effectAllowed = 'move';
  // Firefox refuses to start a drag without payload.
  event.dataTransfer.setData('text/plain', column.key);
};

const onHeaderDragOver = (column) => {
  if (!draggedKey.value || draggedKey.value === column.key) return;
  dropTargetKey.value = column.key;
};

const onHeaderDrop = (column) => {
  if (draggedKey.value) moveColumnTo(draggedKey.value, column.key);
  draggedKey.value = null;
  dropTargetKey.value = null;
};

const onDragEnd = () => {
  draggedKey.value = null;
  dropTargetKey.value = null;
};

// --- Column picker -------------------------------------------------------

const isPickerOpen = ref(false);
const picker = ref(null);

const onDocumentClick = (event) => {
  if (picker.value && !picker.value.contains(event.target)) isPickerOpen.value = false;
};

watch(isPickerOpen, (open) => {
  if (open) document.addEventListener('click', onDocumentClick);
  else document.removeEventListener('click', onDocumentClick);
});

onUnmounted(() => document.removeEventListener('click', onDocumentClick));

const pickerColumns = computed(() => definitions.value);

defineExpose({ resetColumns });
</script>

<template>
  <div ref="container" class="data-table flex flex-col overflow-hidden relative" :style="containerStyle">
    <div v-if="isColumnMode" ref="picker" class="absolute top-1 right-2 z-20" @click.stop>
      <button type="button" class="px-2 py-1 hover:bg-slate-200 rounded text-slate-500"
        :title="t('common.configure_columns')" @click="isPickerOpen = !isPickerOpen">
        <Icon name="fa6-solid:table-columns" />
      </button>
      <div v-if="isPickerOpen"
        class="absolute top-full right-0 mt-1 bg-white rounded customers-shadow p-2 w-[260px] max-h-[60vh] overflow-y-auto">
        <p class="text-xs uppercase tracking-wider text-gray-400 px-1 pb-1">
          {{ t('common.visible_columns') }}
        </p>
        <div v-for="(column, index) in pickerColumns" :key="column.key"
          class="flex items-center gap-1 px-1 py-1 hover:bg-slate-100 rounded text-sm"
          :class="{ 'opacity-50': draggedKey === column.key, 'bg-sky-50': dropTargetKey === column.key }"
          draggable="true" @dragstart="onHeaderDragStart(column, $event)"
          @dragover.prevent="onHeaderDragOver(column)" @drop.prevent="onHeaderDrop(column)"
          @dragend="onDragEnd">
          <Icon name="fa6-solid:grip-vertical" class="text-slate-300 cursor-grab shrink-0"
            :title="t('common.drag_to_reorder')" />
          <label class="flex items-center gap-2 flex-1 min-w-0 cursor-pointer">
            <input type="checkbox" :checked="isVisible(column.key)" :disabled="!column.removable"
              @change="toggleColumn(column.key)" />
            <span class="truncate">{{ column.label }}</span>
          </label>
          <button type="button" class="px-1 text-slate-400 hover:text-sky-600 disabled:opacity-30"
            :disabled="index === 0" :title="t('common.move_up')" @click="moveColumnBy(column.key, -1)">
            <Icon name="fa6-solid:chevron-up" />
          </button>
          <button type="button" class="px-1 text-slate-400 hover:text-sky-600 disabled:opacity-30"
            :disabled="index === pickerColumns.length - 1" :title="t('common.move_down')"
            @click="moveColumnBy(column.key, 1)">
            <Icon name="fa6-solid:chevron-down" />
          </button>
        </div>
        <p v-if="autoHiddenColumns.length" class="text-xs text-amber-600 px-1 pt-2">
          {{ t('common.columns_hidden_by_width') }}
        </p>
        <button v-if="isCustomised" type="button"
          class="mt-2 w-full text-sm text-sky-600 hover:underline text-left px-1" @click="resetColumns">
          {{ t('common.restore_default_columns') }}
        </button>
      </div>
    </div>

    <div class="data-table__body flex-1 min-h-0 overflow-y-auto overflow-x-auto" :style="scrollStyle"
      @scroll="emit('scroll', $event)">
      <div
        class="data-table__header sticky top-0 z-0 bg-white text-xs font-medium uppercase tracking-wider text-gray-400 border-b border-gray-200 items-center px-1 py-1"
        :class="isColumnMode ? 'gap-2 pr-9' : 'gap-3'" :style="gridStyle">
        <span v-if="pinColumn" aria-hidden="true"></span>

        <template v-if="isColumnMode">
          <span v-for="column in visibleColumns" :key="column.key" :ref="setHeaderRef(column.key)"
            class="data-table__head-cell relative flex items-center min-w-0"
            :class="[column.headerClass, {
              'is-dragging': draggedKey === column.key,
              'is-drop-target': dropTargetKey === column.key,
            }]"
            draggable="true" :title="t('common.drag_to_reorder')"
            @dragstart="onHeaderDragStart(column, $event)" @dragover.prevent="onHeaderDragOver(column)"
            @drop.prevent="onHeaderDrop(column)" @dragend="onDragEnd">
            <TableHeader :label="column.label" :sortKey="column.sortKey" :sortable="column.sortable"
              :currentSortBy="currentSortBy" :sortDesc="sortDesc" @sort="emit('sort', $event)" />
            <span v-if="column.resizable" class="data-table__resizer" :class="{ 'is-active': resizingKey === column.key }"
              :title="t('common.resize_column')" @mousedown.prevent.stop="startResize(column, $event)"
              @dblclick.stop="clearColumnWidth(column.key)" />
          </span>
        </template>
        <slot v-else name="header" />
      </div>

      <div v-if="pending || loading" class="data-table__state">
        <AppLoading :text="t('common.loading')" />
      </div>
      <div v-else-if="error" class="data-table__state">
        <p>Error: {{ error.message }}</p>
        <p>
          <button @click="emit('retry')" class="underline text-sky-500 hover:no-underline">
            {{ t('common.load_again') }}
          </button>
        </p>
      </div>
      <template v-else>
        <template v-if="isColumnMode">
          <div v-for="item in items" :key="item[rowKey]"
            class="group gap-2 pr-9 text-base border-b border-gray-100 items-center px-1"
            :style="gridStyle" :class="rowClass ? rowClass(item) : null">
            <slot name="pin" :item="item">
              <span v-if="pinColumn" aria-hidden="true"></span>
            </slot>
            <span v-for="column in visibleColumns" :key="column.key" class="p-1 min-w-0" :class="column.cellClass">
              <slot :name="`cell-${column.key}`" :item="item" :column="column" />
            </span>
          </div>
        </template>
        <slot v-else :grid-style="gridStyle" />

        <div v-if="isEmpty" class="data-table__state my-3">
          <p>{{ t('common.no_records') }}</p>
        </div>
      </template>
    </div>
  </div>
</template>

<style>
/* Every header/row cell truncates its own overflowing content with an
   ellipsis instead of wrapping or breaking the grid layout. Opt a specific
   cell out with the `data-table-no-truncate` class when it needs to wrap
   or size itself freely (e.g. a badge meant to grow). */
.data-table__header > *,
.data-table__body > div:not(.data-table__state) > * {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.data-table__header > .data-table-no-truncate,
.data-table__body > div:not(.data-table__state) > .data-table-no-truncate {
  overflow: visible;
  text-overflow: unset;
  white-space: normal;
  min-width: auto;
}

.data-table__resizer {
  position: absolute;
  top: 0;
  right: 0;
  width: 8px;
  height: 100%;
  cursor: col-resize;
  z-index: 1;
}

/* The grip is always faintly visible so the affordance is discoverable, and
   turns solid on hover or while dragging. */
.data-table__resizer::after {
  content: '';
  position: absolute;
  top: 15%;
  left: 3px;
  width: 2px;
  height: 70%;
  background: rgb(203 213 225); /* slate-300 */
  transition: background 120ms ease;
}

.data-table__resizer:hover::after,
.data-table__resizer.is-active::after {
  background: rgb(14 165 233); /* sky-500 */
  width: 3px;
}

.data-table__head-cell {
  cursor: grab;
}

.data-table__head-cell.is-dragging {
  opacity: 0.4;
}

.data-table__head-cell.is-drop-target {
  box-shadow: inset 2px 0 0 rgb(14 165 233); /* sky-500 */
}
</style>
