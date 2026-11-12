import { computed, effectScope, inject, provide, ref, watch } from 'vue';
import { useSidebarStore } from '~/stores/useNavSideBar';

const INSIDE_PINNED_CONTRACT = Symbol('insidePinnedContract');

// Slide-out duration of the pinned panel (duration-500 in NavTopPinned)
const PANEL_TRANSITION_MS = 500;

// True while the pinned contract panel is open or still sliding out
const panelOverPage = ref(false);
let watching = false;
let closeTimer: ReturnType<typeof setTimeout> | null = null;

const startWatching = () => {
  if (watching) return;
  watching = true;
  const sidebarStore = useSidebarStore();
  // Detached scope: the watcher must outlive the component that started it (e.g. a layout change)
  effectScope(true).run(() => watch(() => sidebarStore.isPinnedContractOpen, (open) => {
    if (closeTimer) clearTimeout(closeTimer);
    closeTimer = null;
    if (open) {
      panelOverPage.value = true;
    } else if (panelOverPage.value) {
      // Keep the page below the panel until it has slid out, or the page would cover it meanwhile
      closeTimer = setTimeout(() => { panelOverPage.value = false; }, PANEL_TRANSITION_MS);
    }
  }, { immediate: true }));
};

/**
 * Marks the component tree below as part of the pinned contract panel (ContractPinned).
 */
export const providePinnedContractScope = () => {
  provide(INSIDE_PINNED_CONTRACT, true);
};

/**
 * True while the pinned contract panel (NavTopPinned, z-[45]) is open, or still sliding out.
 * The layout uses it to `isolate` <main>, so the page regions stay below the panel.
 */
export const usePinnedContractOverPage = () => {
  startWatching();
  return computed(() => panelOverPage.value);
};

/**
 * True when the pinned contract panel is over the page and the calling component belongs to
 * the page, not to the pinned panel. Layers that a page teleports to <body> escape the `isolate`
 * of <main>, so they must use this to drop below z-[45]; the ones inside the pinned panel keep
 * their z-index.
 */
export const usePinnedContractCoversPage = () => {
  const insidePinned = inject(INSIDE_PINNED_CONTRACT, false);
  const overPage = usePinnedContractOverPage();
  return computed(() => overPage.value && !insidePinned);
};
