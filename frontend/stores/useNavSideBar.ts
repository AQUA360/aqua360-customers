import {defineStore} from 'pinia'

export const SIDEBAR_WIDTH_EXPANDED = 250;
export const SIDEBAR_WIDTH_COLLAPSED = 56;

export const useSidebarStore = defineStore('sidebar', {
  state: () => ({
    isOpen: true, // Start with the sidebar open by default
    isCollapsed: false, // When true, show only icons (middle step)
    isSearchOpen: false,
    isNotificationsOpen: false,
    isPinnedContractOpen: false,
    newNotifications: 0,
    newGeneralNotes: 0,
    newDailyDocuments: 0,
  }),
  getters: {
    /** Current sidebar width in px (0 when closed, 56 when collapsed, 250 when expanded). */
    sidebarWidth(): number {
      if (!this.isOpen) return 0;
      return this.isCollapsed ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH_EXPANDED;
    },
  },
  actions: {
    toggleSidebar() {
      this.isOpen = !this.isOpen;
    },
    /** Cycle: expanded → collapsed → closed. When collapsed, click again to close. */
    collapseOrCloseSidebar() {
      if (this.isCollapsed) {
        this.isOpen = false;
      } else {
        this.isCollapsed = true;
      }
    },
    expandSidebar() {
      this.isCollapsed = false;
    },
    closeSidebar() {
      this.isOpen = false;
      this.isCollapsed = false;
    },
    openSidebar() {
      this.isOpen = true;
      this.isCollapsed = false;
    },
    toggleSearcher() {
      this.isSearchOpen = !this.isSearchOpen;
    },
    closeSearch() {
      this.isSearchOpen = false;
    },
    openSearch() {
      this.isSearchOpen = true;
    },
    openNotifications() {
      this.isNotificationsOpen = true;
    },
    closeNotifications() {
      this.isNotificationsOpen = false;
    },
    toggleNotifications() {
      this.isNotificationsOpen = !this.isNotificationsOpen;
    },
    newNotificationsFound(notificationsFound: number){
      this.newNotifications = notificationsFound;
    },
    newGeneralNotesFound(generalNotesFound: number){
      this.newGeneralNotes = generalNotesFound;
    },
    newDailyDocumentsFound(dailyDocumentsFound: number){
      this.newDailyDocuments = dailyDocumentsFound;
    },
    togglePinnedContract() {
      this.isPinnedContractOpen = !this.isPinnedContractOpen;
    },
    closePinnedContract() {
      this.isPinnedContractOpen = false;
    },
  }
});

