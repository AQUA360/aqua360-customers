<script setup lang="ts">
import { useSidebarStore } from '~/stores/useNavSideBar';
import { useExportJobsStore } from '~/stores/useExportJobs';
import NavTop from '~/components/organisms/NavTop.vue';
import NavSidebar from '~/components/organisms/NavSidebar.vue';
import SideBarSearch from '~/components/organisms/SideBarSearch.vue';
import NotificationRegion from '~/components/organisms/NotificationRegion.vue';
import { useToast } from 'vue-toastification';
import { h } from 'vue';

const sidebarStore = useSidebarStore();
const notificationArea = ref<HTMLElement | null>(null);
const toast = useToast();
const { $GeneralNoteApiService } = useNuxtApp();
const { t } = useI18n();

const generalNoteToastContent = (username: string, note: string) => h('div', [
  h('div', { class: 'text-xs opacity-75 mb-1' }, username),
  h('div', note),
]);

// Interval (ms) de comprovació d'avisos generals nous mentre l'usuari està connectat.
const GENERAL_NOTES_POLL_INTERVAL = 60000;
let generalNotesPollTimer: ReturnType<typeof setInterval> | null = null;
// Evita mostrar dues vegades el mateix avís si hi ha una comprovació en curs.
const shownGeneralNoteIds = new Set<number>();

const checkGeneralNotes = async () => {
  try {
    const unseenNotes = await $GeneralNoteApiService.getUnseen();
    for (const note of unseenNotes) {
      if (shownGeneralNoteIds.has(note.id)) continue;
      shownGeneralNoteIds.add(note.id);
      const senderUsername = note.user ? note.user.username : t('common.anonymous');
      toast.info(generalNoteToastContent(senderUsername, note.note), { timeout: false, closeOnClick: false });
      try {
        await $GeneralNoteApiService.save({ id: note.id });
      } catch (err) {
        console.error('Error marking general note as seen:', err);
      }
    }
    const remaining = unseenNotes.filter((note) => !shownGeneralNoteIds.has(note.id)).length;
    sidebarStore.newGeneralNotesFound(remaining);
  } catch (err) {
    console.error('Error checking general notes:', err);
  }
};

const handleKeydown = (event: KeyboardEvent) => {
  if (event.ctrlKey && event.key === 'k') {
    event.preventDefault();
    sidebarStore.openSearch();
  } else if ((event.key === 'Escape')) {
    if (sidebarStore.isSearchOpen) {
      event.preventDefault();
      sidebarStore.closeSearch();
      return;
    }
    // Wait until every other keydown listener has run: a dropdown or confirm that handles
    // the Escape itself calls preventDefault() and the region stays open.
    setTimeout(() => {
      if (!event.defaultPrevented) closeTopRegion();
    });
  } else if (event.ctrlKey && event.key === 'u') {
    event.preventDefault();
    sidebarStore.toggleNotifications();
  } else if (event.ctrlKey && event.key === 'p') {
    event.preventDefault();
    sidebarStore.togglePinnedContract();
  }
};


/* Closes the open region furthest to the right (the innermost one when several are open)
   by simulating the click of its region nav button. Closed regions stay in the DOM translated
   off-screen to the right, so a region is open when its right edge is inside the viewport. */
const closeTopRegion = () => {
  const viewportWidth = window.innerWidth;
  const openRegions = Array.from(document.querySelectorAll<HTMLElement>('[role="region"]'))
    .map((element) => ({ element, rect: element.getBoundingClientRect() }))
    .filter(({ rect }) => rect.width > 0 && rect.height > 0 && rect.left < viewportWidth && rect.right <= viewportWidth + 1);
  if (openRegions.length === 0) return;

  openRegions.sort((a, b) => {
    const diff = b.rect.left - a.rect.left;
    if (Math.abs(diff) > 1) return diff;
    // Same left edge: the nested region goes first
    if (a.element.contains(b.element)) return 1;
    if (b.element.contains(a.element)) return -1;
    return 0;
  });

  const region = openRegions[0].element;
  const nav = Array.from(region.querySelectorAll<HTMLElement>('#region_nav'))
    .find((element) => element.closest('[role="region"]') === region);
  nav?.querySelector<HTMLButtonElement>('button')?.click();
}

/* const handleClickOutside = (event: MouseEvent) => {
  if (sidebarStore.isNotificationsOpen && notificationArea.value && !notificationArea.value.contains(event.target as Node)) {
    sidebarStore.closeNotifications();
  }
}; */

const handleClickOutside = (event: MouseEvent) => {
  if (sidebarStore.isNotificationsOpen) {
    let target = event.target as HTMLElement;
    while (target) {
      if (target.getAttribute) {
        if (target.getAttribute('role') === 'notificationRegion') {
          return;
        }
      }
      target = target.parentNode as HTMLElement;
    }

    if (notificationArea.value && !notificationArea.value.contains(event.target as Node)) {
      sidebarStore.closeNotifications();
    }
  }
};

onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
  document.addEventListener('mousedown', handleClickOutside);

  checkGeneralNotes();
  generalNotesPollTimer = setInterval(checkGeneralNotes, GENERAL_NOTES_POLL_INTERVAL);

  // Downloads queue: resumes the exports still running (and the auto-download of
  // the ones launched from this tab) after a refresh or a new login.
  useExportJobsStore().init();
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
  if (generalNotesPollTimer) clearInterval(generalNotesPollTimer);
});

</script>

<template>
  <div class="wrapper antialiased h-screen overflow-hidden">

    <div class="">
      <SideBarSearch v-if="sidebarStore.isSearchOpen" />
    </div>

    <div class="relative h-full">
      <NavSidebar />
      <div v-if="sidebarStore.isNotificationsOpen"
        class="w-[25%] py-2 border-r fixed left-0 top-0 z-20 bg-white h-screen overflow-y-auto transition-[margin-left] duration-200 ease-in-out"
        :style="{ marginLeft: sidebarStore.sidebarWidth + 'px' }" ref="notificationArea"
        role="notificationRegion">
        <NotificationRegion />
      </div>

      <div
        class="min-w-0 h-full flex flex-col transition-[margin-left,width] duration-200 ease-in-out"
        :style="{
          marginLeft: sidebarStore.sidebarWidth + 'px',
          width: 'calc(100vw - ' + sidebarStore.sidebarWidth + 'px)',
        }">
        <NavTop class="shrink-0" />
        <main id="page" class="px-4 py-5 pb-0 flex-1 min-h-0 overflow-y-auto">
          <slot />
        </main>
      </div><!-- end content -->
    </div>
  </div><!-- end wrapper -->
</template>
