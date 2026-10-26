import { ref, computed, onMounted, unref } from 'vue';

/**
 * Per-user tab layout for a tab bar: which tabs are shown, in which order, and
 * whether the bar is collapsed to icons only.
 *
 * Stored in localStorage namespaced by the logged-in username (same approach
 * as `useTableColumns`), so two users sharing a browser keep separate layouts.
 *
 * Tab descriptor: { key: 'invoices', ... } — only `key` is used here, the rest
 * is passed through untouched for the template.
 */

const STORAGE_PREFIX = 'tabsLayout';

const storageKeyFor = (layoutKey) => {
  let user = '';
  try {
    user = localStorage.getItem('user_username') || '';
  } catch {
    user = '';
  }
  return `${STORAGE_PREFIX}:${layoutKey}:${user}`;
};

export function useTabsLayout(layoutKey, tabsSource) {
  const definitions = computed(() => unref(tabsSource) || []);

  const hiddenKeys = ref([]);
  const tabOrder = ref(null);
  const collapsed = ref(false);

  const loadState = () => {
    try {
      const raw = localStorage.getItem(storageKeyFor(layoutKey));
      if (!raw) return;
      const parsed = JSON.parse(raw);
      hiddenKeys.value = Array.isArray(parsed.hidden) ? parsed.hidden : [];
      tabOrder.value = Array.isArray(parsed.order) ? parsed.order : null;
      collapsed.value = parsed.collapsed === true;
    } catch (e) {
      console.error('Could not read tabs layout', e);
    }
  };

  const saveState = () => {
    try {
      localStorage.setItem(
        storageKeyFor(layoutKey),
        JSON.stringify({
          hidden: hiddenKeys.value,
          order: tabOrder.value ?? [],
          collapsed: collapsed.value,
        })
      );
    } catch (e) {
      console.error('Could not persist tabs layout', e);
    }
  };

  /**
   * Declaration order with the user's reordering applied. Tabs added after the
   * user saved a layout are appended at the end, so they never disappear.
   */
  const orderedTabs = computed(() => {
    const order = tabOrder.value;
    if (!order || !order.length) return definitions.value;

    const byKey = new Map(definitions.value.map((tab) => [tab.key, tab]));
    const ordered = order.map((key) => byKey.get(key)).filter(Boolean);
    const seen = new Set(ordered.map((tab) => tab.key));
    return [...ordered, ...definitions.value.filter((tab) => !seen.has(tab.key))];
  });

  const isVisible = (key) => !hiddenKeys.value.includes(key);

  const visibleTabs = computed(() => orderedTabs.value.filter((tab) => isVisible(tab.key)));

  const toggleTab = (key) => {
    if (isVisible(key)) {
      // Keep at least one tab, otherwise the bar (and its settings) vanish.
      if (visibleTabs.value.length <= 1) return;
      hiddenKeys.value = [...hiddenKeys.value, key];
    } else {
      hiddenKeys.value = hiddenKeys.value.filter((k) => k !== key);
    }
    saveState();
  };

  const currentOrder = () => orderedTabs.value.map((tab) => tab.key);

  /** Drop `key` at the position currently held by `targetKey`. */
  const moveTabTo = (key, targetKey) => {
    if (key === targetKey) return;
    const order = currentOrder();
    const from = order.indexOf(key);
    const to = order.indexOf(targetKey);
    if (from === -1 || to === -1) return;
    order.splice(to, 0, ...order.splice(from, 1));
    tabOrder.value = order;
    saveState();
  };

  /** Shift a tab one position up/left (-1) or down/right (+1). */
  const moveTabBy = (key, offset) => {
    const order = currentOrder();
    const from = order.indexOf(key);
    const to = from + offset;
    if (from === -1 || to < 0 || to >= order.length) return;
    order.splice(to, 0, ...order.splice(from, 1));
    tabOrder.value = order;
    saveState();
  };

  const toggleCollapsed = () => {
    collapsed.value = !collapsed.value;
    saveState();
  };

  const isCustomised = computed(
    () => hiddenKeys.value.length > 0 || (tabOrder.value !== null && tabOrder.value.length > 0)
  );

  /** Restore the default tabs and order; the collapsed toggle is kept. */
  const resetTabs = () => {
    hiddenKeys.value = [];
    tabOrder.value = null;
    saveState();
  };

  onMounted(loadState);

  return {
    tabs: orderedTabs,
    visibleTabs,
    collapsed,
    isVisible,
    isCustomised,
    toggleTab,
    moveTabTo,
    moveTabBy,
    toggleCollapsed,
    resetTabs,
  };
}
