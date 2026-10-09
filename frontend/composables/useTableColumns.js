import { ref, computed, onMounted, unref } from 'vue';

/**
 * Per-user, per-table column configuration for `DataTable`.
 *
 * Each column is declared once by the page (see the `columns` prop of
 * `DataTable.vue`) and this composable takes care of:
 *  - which columns the user chose to see (persisted),
 *  - how wide the user dragged each one (persisted),
 *  - dropping the least important columns automatically when the viewport is
 *    too narrow to fit every chosen column at its minimum width.
 *
 * The configuration is stored in localStorage namespaced by the logged-in
 * username, so two users sharing a browser keep separate layouts.
 *
 * Column descriptor:
 *   {
 *     key: 'holder',              // unique, stable id (also the storage key)
 *     label: 'Titular',           // header text
 *     sortKey: 'holder__name',    // omit to make the column non sortable
 *     width: 150,                 // preferred width in px (used when grow = 0)
 *     min: 90,                    // never shrinks below this
 *     grow: 1,                    // >0 => takes a share of the leftover space
 *     priority: 2,                // 1 = never auto-hidden, higher = dropped first
 *     removable: false,           // false => user cannot hide it in the picker
 *     defaultVisible: true,       // hidden until the user opts in when false
 *   }
 */

const STORAGE_PREFIX = 'dataTableColumns';

const storageKeyFor = (tableKey) => {
  let user = '';
  try {
    user = localStorage.getItem('user_username') || '';
  } catch {
    user = '';
  }
  return `${STORAGE_PREFIX}:${tableKey}:${user}`;
};

const normalize = (column) => ({
  key: column.key,
  label: column.label ?? '',
  sortKey: column.sortKey ?? '',
  sortable: column.sortKey !== undefined && column.sortKey !== null && column.sortKey !== '',
  width: column.width ?? 120,
  min: column.min ?? 60,
  grow: column.grow ?? 0,
  priority: column.priority ?? 2,
  removable: column.removable !== false,
  defaultVisible: column.defaultVisible !== false,
  resizable: column.resizable !== false,
  cellClass: column.cellClass ?? '',
  headerClass: column.headerClass ?? '',
});

export function useTableColumns(tableKey, columnsSource, options = {}) {
  // Reserved for the pin/indicator column plus the container's horizontal padding.
  const chromeWidth = options.chromeWidth ?? 40;
  // Horizontal gap between columns, in px (must match the row's `gap-*` class).
  const gapWidth = options.gapWidth ?? 12;

  const definitions = computed(() => (unref(columnsSource) || []).map(normalize));

  // User overrides, keyed by column key. `null` means "never configured".
  const hiddenKeys = ref(null);
  const customWidths = ref({});
  const columnOrder = ref(null);
  const availableWidth = ref(0);

  const loadState = () => {
    try {
      const raw = localStorage.getItem(storageKeyFor(tableKey));
      if (!raw) {
        hiddenKeys.value = null;
        return;
      }
      const parsed = JSON.parse(raw);
      hiddenKeys.value = Array.isArray(parsed.hidden) ? parsed.hidden : null;
      customWidths.value = parsed.widths && typeof parsed.widths === 'object' ? parsed.widths : {};
      columnOrder.value = Array.isArray(parsed.order) ? parsed.order : null;
    } catch (e) {
      console.error('Could not read table column settings', e);
      hiddenKeys.value = null;
      customWidths.value = {};
      columnOrder.value = null;
    }
  };

  const saveState = () => {
    try {
      localStorage.setItem(
        storageKeyFor(tableKey),
        JSON.stringify({
          hidden: hiddenKeys.value ?? [],
          widths: customWidths.value,
          order: columnOrder.value ?? [],
        })
      );
    } catch (e) {
      console.error('Could not persist table column settings', e);
    }
  };

  /**
   * Declaration order with the user's reordering applied. Keys the user never
   * saw (a column added to the page after they saved a layout) keep their
   * declared position relative to the end, so new columns never disappear.
   */
  const orderedDefinitions = computed(() => {
    const order = columnOrder.value;
    if (!order || !order.length) return definitions.value;

    const byKey = new Map(definitions.value.map((col) => [col.key, col]));
    const ordered = order.map((key) => byKey.get(key)).filter(Boolean);
    const seen = new Set(ordered.map((col) => col.key));
    return [...ordered, ...definitions.value.filter((col) => !seen.has(col.key))];
  });

  /** Columns the user wants to see (before the responsive pass). */
  const selectedColumns = computed(() => {
    const hidden = hiddenKeys.value;
    return orderedDefinitions.value.filter((col) => {
      if (!col.removable) return true;
      // Until the user touches the picker, fall back to the column's default.
      if (hidden === null) return col.defaultVisible;
      return !hidden.includes(col.key);
    });
  });

  /**
   * The narrowest a column can ever get: the width the user pinned by dragging,
   * or its declared minimum. This is the floor the responsive pass budgets
   * against — anything wider is negotiable and gets squeezed before a column
   * is dropped.
   */
  const floorOf = (col) => customWidths.value[col.key] ?? col.min;

  /** What a column asks for when there is no pressure. */
  const preferredOf = (col) => customWidths.value[col.key] ?? Math.max(col.min, col.width);

  /**
   * Drop the least important columns while the selection cannot fit at its
   * minimum widths. Columns with priority 1 are always kept — if even those do
   * not fit the table scrolls horizontally instead.
   */
  const visibleColumns = computed(() => {
    const kept = [...selectedColumns.value];
    if (!availableWidth.value) return kept;

    const budget = availableWidth.value - chromeWidth;
    // Only drop a column once everything left is already at its floor. The gaps
    // between the tracks count towards the total too.
    const required = () =>
      kept.reduce((sum, col) => sum + floorOf(col), 0) + gapWidth * kept.length;

    while (required() > budget) {
      // Highest priority number = least important; break ties by declaration order.
      let candidateIndex = -1;
      let candidatePriority = 1;
      kept.forEach((col, index) => {
        if (col.priority > candidatePriority) {
          candidatePriority = col.priority;
          candidateIndex = index;
        }
      });
      if (candidateIndex === -1) break;
      kept.splice(candidateIndex, 1);
    }
    return kept;
  });

  /** Columns hidden by the responsive pass rather than by the user. */
  const autoHiddenColumns = computed(() => {
    const visible = new Set(visibleColumns.value.map((col) => col.key));
    return selectedColumns.value.filter((col) => !visible.has(col.key));
  });

  /**
   * Final pixel width of every visible column.
   *
   * Doing this in JS rather than leaving it to `fr` tracks is what lets a
   * column both shrink below its preferred width when space is tight AND grow
   * past it when there is space to spare — CSS `minmax(min, width)` caps a
   * track at `width` forever, so on a wide screen the surplus all ended up in
   * the few `fr` columns while the rest stayed truncated.
   *
   *  - surplus: handed out in proportion to each column's `grow` weight;
   *  - deficit: taken back in proportion to the slack each column has above
   *    its minimum, so the roomiest columns give way first.
   *
   * A column the user resized by hand is excluded from both passes: their
   * explicit choice wins over the automatic distribution.
   */
  const layout = computed(() => {
    const cols = visibleColumns.value;
    const widths = {};
    cols.forEach((col) => {
      widths[col.key] = preferredOf(col);
    });
    if (!availableWidth.value || !cols.length) return widths;

    const budget = availableWidth.value - chromeWidth - gapWidth * cols.length;
    const total = cols.reduce((sum, col) => sum + widths[col.key], 0);

    if (total < budget) {
      // A width the user dragged is a baseline, not a freeze: the column still
      // takes its share of free space, so widening the window widens it too.
      // Nothing here is persisted, so the growth is recomputed from that
      // baseline every time and never accumulates.
      const growable = cols.filter((col) => col.grow > 0);
      const weight = growable.reduce((sum, col) => sum + col.grow, 0);
      if (weight > 0) {
        const surplus = budget - total;
        growable.forEach((col) => {
          widths[col.key] += (surplus * col.grow) / weight;
        });
      }
    } else if (total > budget) {
      // Shrinking is the other way round: a hand-set width holds its ground and
      // the space is taken from the columns that were sized automatically, so
      // that dragging a column wider actually sticks.
      const slack = cols.map((col) =>
        customWidths.value[col.key] != null ? 0 : Math.max(0, widths[col.key] - col.min)
      );
      const totalSlack = slack.reduce((a, b) => a + b, 0);
      if (totalSlack > 0) {
        const factor = Math.min(1, (total - budget) / totalSlack);
        cols.forEach((col, index) => {
          widths[col.key] -= slack[index] * factor;
        });
      }
    }

    cols.forEach((col) => {
      widths[col.key] = Math.round(widths[col.key]);
    });

    // Rounding ten fractional widths can drift a pixel or two off the budget,
    // which is enough to trip the container's horizontal scrollbar. Absorb the
    // drift into the widest flexible column, where it is invisible.
    const drift = cols.reduce((sum, col) => sum + widths[col.key], 0) - budget;
    if (drift !== 0) {
      const absorber = cols
        .filter((col) => col.grow > 0)
        .sort((a, b) => widths[b.key] - widths[a.key])[0];
      if (absorber && widths[absorber.key] - drift >= absorber.min) {
        widths[absorber.key] -= drift;
      }
    }
    return widths;
  });

  /**
   * grid-template-columns for the visible set. Before the first measurement
   * (SSR and the first paint) fall back to CSS-resolved tracks so the table is
   * never rendered with the wrong shape.
   */
  const gridTemplate = computed(() => {
    if (!availableWidth.value) {
      return visibleColumns.value
        .map((col) => {
          const custom = customWidths.value[col.key];
          if (custom) return `${custom}px`;
          if (col.grow > 0) return `minmax(${col.min}px, ${col.grow}fr)`;
          return `minmax(${col.min}px, ${col.width}px)`;
        })
        // Space separated: tracks contain commas of their own (`minmax(a, b)`),
        // so they must never be re-split on ',' downstream.
        .join(' ');
    }
    return visibleColumns.value.map((col) => `${layout.value[col.key]}px`).join(' ');
  });

  const isVisible = (key) => visibleColumns.value.some((col) => col.key === key);

  const toggleColumn = (key) => {
    const definition = definitions.value.find((col) => col.key === key);
    if (!definition || !definition.removable) return;

    // First interaction: materialise the current defaults so toggling one
    // column does not silently reset the others.
    if (hiddenKeys.value === null) {
      hiddenKeys.value = definitions.value
        .filter((col) => col.removable && !col.defaultVisible)
        .map((col) => col.key);
    }

    const index = hiddenKeys.value.indexOf(key);
    if (index === -1) {
      hiddenKeys.value = [...hiddenKeys.value, key];
    } else {
      hiddenKeys.value = hiddenKeys.value.filter((k) => k !== key);
    }
    saveState();
  };

  const setColumnWidth = (key, width) => {
    const definition = definitions.value.find((col) => col.key === key);
    if (!definition) return;
    customWidths.value = {
      ...customWidths.value,
      [key]: Math.max(definition.min, Math.round(width)),
    };
    saveState();
  };

  /** Snapshot the current order so a move has a concrete list to work on. */
  const currentOrder = () => orderedDefinitions.value.map((col) => col.key);

  /** Drop `key` at the position currently held by `targetKey`. */
  const moveColumnTo = (key, targetKey) => {
    if (key === targetKey) return;
    const order = currentOrder();
    const from = order.indexOf(key);
    const to = order.indexOf(targetKey);
    if (from === -1 || to === -1) return;
    order.splice(to, 0, ...order.splice(from, 1));
    columnOrder.value = order;
    saveState();
  };

  /** Shift a column one position left (-1) or right (+1). */
  const moveColumnBy = (key, offset) => {
    const order = currentOrder();
    const from = order.indexOf(key);
    const to = from + offset;
    if (from === -1 || to < 0 || to >= order.length) return;
    order.splice(to, 0, ...order.splice(from, 1));
    columnOrder.value = order;
    saveState();
  };

  /** Give one column its natural width back (double click on the resize grip). */
  const clearColumnWidth = (key) => {
    if (!(key in customWidths.value)) return;
    const { [key]: _removed, ...rest } = customWidths.value;
    customWidths.value = rest;
    saveState();
  };

  const resetColumns = () => {
    hiddenKeys.value = null;
    customWidths.value = {};
    columnOrder.value = null;
    try {
      localStorage.removeItem(storageKeyFor(tableKey));
    } catch (e) {
      console.error('Could not clear table column settings', e);
    }
  };

  const isCustomised = computed(
    () =>
      hiddenKeys.value !== null ||
      Object.keys(customWidths.value).length > 0 ||
      (columnOrder.value !== null && columnOrder.value.length > 0)
  );

  const setAvailableWidth = (width) => {
    availableWidth.value = width;
  };

  onMounted(loadState);

  return {
    definitions: orderedDefinitions,
    selectedColumns,
    visibleColumns,
    autoHiddenColumns,
    gridTemplate,
    isVisible,
    isCustomised,
    toggleColumn,
    moveColumnTo,
    moveColumnBy,
    setColumnWidth,
    clearColumnWidth,
    resetColumns,
    setAvailableWidth,
  };
}
