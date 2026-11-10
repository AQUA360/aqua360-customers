import { ref, computed, onMounted, onUnmounted, unref } from 'vue';

/**
 * Per-user layout of the side menu, stored in the database (`/dashboard/sidebar/`):
 *  - which sections are shown and in which order,
 *  - which sections are folded so only their title is visible,
 *  - which links of each section are shown and in which order.
 *
 * Section descriptor: { key, label, icon, items: [{ key, label, icon, ... }] }.
 * Only the sections and links the user can access must be passed, so the
 * "keep at least one visible" rule applies to what the user actually sees.
 * Keys saved for sections or links the user cannot access are kept untouched.
 */

const SAVE_DELAY_MS = 500;

const emptyBlock = () => ({ hidden: [], order: [] });

/** Apply a saved key order; entries the user never ordered go at the end. */
const applyOrder = (entries, order) => {
  if (!order || !order.length) return entries;
  const byKey = new Map(entries.map((entry) => [entry.key, entry]));
  const ordered = order.map((key) => byKey.get(key)).filter(Boolean);
  const seen = new Set(ordered.map((entry) => entry.key));
  return [...ordered, ...entries.filter((entry) => !seen.has(entry.key))];
};

/** Move `key` to position `to` of the current key order. */
const reorder = (order, key, to) => {
  const from = order.indexOf(key);
  if (from === -1 || to < 0 || to >= order.length || from === to) return null;
  const result = [...order];
  result.splice(to, 0, ...result.splice(from, 1));
  return result;
};

export function useNavSidebarLayout(sectionsSource) {
  const { $DashboardApiService } = useNuxtApp();

  const definitions = computed(() => unref(sectionsSource) || []);
  const sectionKeys = computed(() => definitions.value.map((section) => section.key));

  const sectionsLayout = ref(emptyBlock());
  const foldedKeys = ref([]);
  // { [sectionKey]: { hidden: [itemKey], order: [itemKey] } }
  const itemsLayout = ref({});

  // --- Persistence -------------------------------------------------------------

  // Si l'usuari canvia alguna cosa abans que arribi la configuració desada, no
  // se sobreescriu el que acaba de fer.
  let changedBeforeLoad = false;
  let loaded = false;
  let saveTimer = null;

  const applyLayout = (layout) => {
    const sections = layout?.sections || {};
    sectionsLayout.value = {
      hidden: Array.isArray(sections.hidden) ? sections.hidden : [],
      order: Array.isArray(sections.order) ? sections.order : [],
    };
    foldedKeys.value = Array.isArray(layout?.folded) ? layout.folded : [];
    itemsLayout.value = layout?.items && typeof layout.items === 'object' ? layout.items : {};
  };

  const loadLayout = async () => {
    try {
      const response = await $DashboardApiService.getSidebarLayout();
      if (!changedBeforeLoad) applyLayout(response?.layout);
    } catch (e) {
      // Sense la configuració desada es mostra el menú per defecte.
      console.error('Could not load side menu layout', e);
    } finally {
      loaded = true;
    }
  };

  const currentLayout = () => ({
    sections: sectionsLayout.value,
    folded: foldedKeys.value,
    items: itemsLayout.value,
  });

  const flushSave = async () => {
    saveTimer = null;
    try {
      await $DashboardApiService.saveSidebarLayout(currentLayout());
    } catch (e) {
      // L'apiManager ja mostra l'error; el menú es queda com l'ha deixat l'usuari.
      console.error('Could not save side menu layout', e);
    }
  };

  /** Save after a short pause, so clicking the arrows several times sends one request. */
  const scheduleSave = () => {
    if (!loaded) changedBeforeLoad = true;
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(flushSave, SAVE_DELAY_MS);
  };

  // --- Sections ------------------------------------------------------------------

  /** All the sections in the user's order (hidden ones included). */
  const sections = computed(() => applyOrder(definitions.value, sectionsLayout.value.order));

  const isVisible = (key) => !sectionsLayout.value.hidden.includes(key);

  const visibleSections = computed(() => sections.value.filter((section) => isVisible(section.key)));

  const toggleSection = (key) => {
    const { hidden } = sectionsLayout.value;
    if (isVisible(key)) {
      // Keep at least one section, otherwise the menu would be empty.
      if (visibleSections.value.length <= 1) return;
      sectionsLayout.value = { ...sectionsLayout.value, hidden: [...hidden, key] };
    } else {
      sectionsLayout.value = { ...sectionsLayout.value, hidden: hidden.filter((k) => k !== key) };
    }
    scheduleSave();
  };

  const moveSection = (key, to) => {
    const order = reorder(sections.value.map((section) => section.key), key, to);
    if (!order) return;
    sectionsLayout.value = { ...sectionsLayout.value, order };
    scheduleSave();
  };

  /** Drop section `key` at the position currently held by `targetKey`. */
  const moveSectionTo = (key, targetKey) =>
    moveSection(key, sections.value.findIndex((section) => section.key === targetKey));

  /** Shift a section one position up (-1) or down (+1). */
  const moveSectionBy = (key, offset) =>
    moveSection(key, sections.value.findIndex((section) => section.key === key) + offset);

  // --- Folding -------------------------------------------------------------------

  const isFolded = (key) => foldedKeys.value.includes(key);

  const toggleFolded = (key) => {
    foldedKeys.value = isFolded(key)
      ? foldedKeys.value.filter((k) => k !== key)
      : [...foldedKeys.value, key];
    scheduleSave();
  };

  /** Fold (true) or unfold (false) every section the user can see. */
  const setAllFolded = (folded) => {
    const others = foldedKeys.value.filter((k) => !sectionKeys.value.includes(k));
    foldedKeys.value = folded ? [...others, ...sectionKeys.value] : others;
    scheduleSave();
  };

  const allFolded = computed(
    () => sectionKeys.value.length > 0 && sectionKeys.value.every((key) => isFolded(key))
  );

  // --- Links inside each section -------------------------------------------------

  const itemsStateOf = (sectionKey) => {
    const state = itemsLayout.value[sectionKey] || {};
    return {
      hidden: Array.isArray(state.hidden) ? state.hidden : [],
      order: Array.isArray(state.order) ? state.order : [],
    };
  };

  const updateItemsState = (sectionKey, patch) => {
    itemsLayout.value = {
      ...itemsLayout.value,
      [sectionKey]: { ...itemsStateOf(sectionKey), ...patch },
    };
    scheduleSave();
  };

  /** All the links of a section in the user's order (hidden ones included). */
  const orderedItems = (section) => applyOrder(section.items || [], itemsStateOf(section.key).order);

  const isItemVisible = (sectionKey, itemKey) => !itemsStateOf(sectionKey).hidden.includes(itemKey);

  const visibleItems = (section) =>
    orderedItems(section).filter((item) => isItemVisible(section.key, item.key));

  const toggleItem = (section, itemKey) => {
    const { hidden } = itemsStateOf(section.key);
    if (isItemVisible(section.key, itemKey)) {
      // At least one link per section: to hide them all, hide the section.
      if (visibleItems(section).length <= 1) return;
      updateItemsState(section.key, { hidden: [...hidden, itemKey] });
    } else {
      updateItemsState(section.key, { hidden: hidden.filter((k) => k !== itemKey) });
    }
  };

  const moveItem = (section, itemKey, to) => {
    const order = reorder(orderedItems(section).map((item) => item.key), itemKey, to);
    if (order) updateItemsState(section.key, { order });
  };

  /** Drop `itemKey` at the position currently held by `targetKey`. */
  const moveItemTo = (section, itemKey, targetKey) =>
    moveItem(section, itemKey, orderedItems(section).findIndex((item) => item.key === targetKey));

  /** Shift a link one position up (-1) or down (+1) inside its section. */
  const moveItemBy = (section, itemKey, offset) =>
    moveItem(section, itemKey, orderedItems(section).findIndex((item) => item.key === itemKey) + offset);

  // --- Whole layout --------------------------------------------------------------

  const isCustomised = computed(
    () =>
      sectionsLayout.value.hidden.length > 0 ||
      sectionsLayout.value.order.length > 0 ||
      foldedKeys.value.length > 0 ||
      Object.keys(itemsLayout.value).some((key) => {
        const { hidden, order } = itemsStateOf(key);
        return hidden.length > 0 || order.length > 0;
      })
  );

  /** Restore the default sections and links, in their order and unfolded. */
  const resetLayout = async () => {
    if (saveTimer) {
      clearTimeout(saveTimer);
      saveTimer = null;
    }
    if (!loaded) changedBeforeLoad = true;
    applyLayout({});
    try {
      await $DashboardApiService.resetSidebarLayout();
    } catch (e) {
      console.error('Could not reset side menu layout', e);
    }
  };

  onMounted(loadLayout);

  // Si el menú es desmunta amb un desat pendent, s'envia igualment (llevat que
  // sigui perquè l'usuari ha sortit i ja no hi ha sessió).
  onUnmounted(() => {
    if (!saveTimer) return;
    clearTimeout(saveTimer);
    saveTimer = null;
    let hasSession = false;
    try {
      hasSession = !!localStorage.getItem('auth_token');
    } catch {
      hasSession = false;
    }
    if (hasSession) flushSave();
  });

  return {
    sections,
    visibleSections,
    isVisible,
    toggleSection,
    moveSectionTo,
    moveSectionBy,
    isFolded,
    toggleFolded,
    setAllFolded,
    allFolded,
    orderedItems,
    visibleItems,
    isItemVisible,
    toggleItem,
    moveItemTo,
    moveItemBy,
    isCustomised,
    resetLayout,
  };
}
