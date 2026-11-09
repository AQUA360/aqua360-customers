<script setup>
import { useI18n } from 'vue-i18n';
import { useSidebarStore } from '~/stores/useNavSideBar';
import GeneralNoteList from '~/components/molecules/GeneralNoteList.vue';
import { usePermissions } from '~/middleware/permission';
import { useConfigStore } from '~/stores/useConfigStore';
import { useExploitationStore } from '~/stores/useExploitationStore';
import { storeToRefs } from 'pinia';
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';
import { useNavSidebarLayout } from '~/composables/useNavSidebarLayout';

const { t, locale } = useI18n();
const sideBarStore = useSidebarStore();
const configStore = useConfigStore();
const exploitationStore = useExploitationStore();
const { ovEnabled: ovLogsEnabled, documentSignEnabled, sendBatchEnabled, isAcaOrg } = storeToRefs(configStore);
const { permissions, loading } = usePermissions();
const config = useRuntimeConfig();
const env = config.public.env;

const showDropdown = ref(false);
const {
  deployedAtLabel,
  available: deployInfoAvailable,
  frontendLabel: deployFrontendLabel,
  backendLabel: deployBackendLabel,
  load: loadDeployInfo,
} = useDeployInfo();

const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value;
  showMenuCustomizer.value = false;
  // La informació del deploy només interessa quan s'obre el desplegable.
  if (showDropdown.value) loadDeployInfo();
};

/** Data del deploy i, en passar-hi el ratolí, el commit desplegat de cada repo. */
const deployTooltip = computed(() => [
  `${t('common.deploy_frontend')}: ${deployFrontendLabel.value}`,
  `${t('common.deploy_backend')}: ${deployBackendLabel.value}`,
].join('\n'));

const switchLanguage = (newLocale) => {
  locale.value = newLocale;
  localStorage.setItem('preferred_language', newLocale);
};

const languages = AVAILABLE_LANGUAGES;

// Tasques pendents d'avui i endarrerides, per al comptador del menú. Es refresca
// en canviar de pàgina, com el de notificacions.
const { $CalendarTaskApiService } = useNuxtApp();
const route = useRoute();
const tasksSummary = ref({ today: 0, overdue: 0 });
const pendingTasks = computed(() => (tasksSummary.value.today || 0) + (tasksSummary.value.overdue || 0));
/** Refresh pending task counts, retaining existing counts if the request fails. */
const loadTasksSummary = async () => {
  try {
    tasksSummary.value = await $CalendarTaskApiService.getSummary();
  } catch (e) {
    // comptador informatiu: si falla, no es mostra
  }
};
watch(() => route.path, loadTasksSummary);
watch(() => sideBarStore.tasksVersion, loadTasksSummary);
onMounted(loadTasksSummary);

// Initialize config fetch
configStore.fetchOvEnabled();
configStore.fetchDocumentSignEnabled();
configStore.fetchSendBatchEnabled();
configStore.fetchPublicOrgType();

// Environment-based highlight class as a simple ref
const highlightClass = ref('bg-slate-200');
const hoverClass = ref('hover:bg-slate-200');
const tooltipClasses = ref(['bg-slate-100', 'border-gray-200', 'text-slate-400']);
const upperEnv = (env || '').toString().toUpperCase();
if (upperEnv === 'LOCAL') {
  highlightClass.value = 'bg-green-300';
  hoverClass.value = 'hover:bg-green-300';
  tooltipClasses.value = ['bg-green-200', 'border-green-300', 'text-green-600'];
} else if (upperEnv === 'TEST' || upperEnv === 'STAGING') {
  highlightClass.value = 'bg-yellow-300';
  hoverClass.value = 'hover:bg-yellow-300';
  tooltipClasses.value = ['bg-yellow-200', 'border-yellow-300', 'text-yellow-600'];
}

const verifactuEnabled = config.public.verifactuEnabled;

const logout = () => {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('user_username');
  localStorage.removeItem('exploitation');
  // $router.push('/auth/login');
  return navigateTo('/auth/login')
};

const toggleSearcher = () => {
  sideBarStore.toggleSearcher();
}

/** Cycle: expanded → collapsed (icons only) → closed. */
const collapseOrCloseSidebar = () => {
  sideBarStore.collapseOrCloseSidebar();
};

const expandSidebar = () => {
  sideBarStore.expandSidebar();
};

const closeNavSidebar = () => {
  sideBarStore.closeSidebar();
};

const toggleNotifications = () => {
  sideBarStore.toggleNotifications();
};

const toggleNavSidebar = () => {
  sideBarStore.toggleSidebar();
};

const isCollapsed = computed(() => sideBarStore.isCollapsed);

// Seccions i enllaços del menú. L'usuari pot amagar-los, reordenar-los i plegar
// les seccions; només s'hi passen els que té permís per veure.
//  - match: tros de ruta que marca l'enllaç com a actiu
//  - image: imatge en lloc d'icona
//  - dailyDocumentsBadge: comptador de documents diaris nous
const menuSections = computed(() => {
  const perms = permissions.value?.permissions || {};
  const sections = [
    {
      key: 'customer_service', id: 'nav-incident', label: t('customer_service'), icon: 'fa6-solid:flag',
      available: perms.view_customer_service,
      items: [
        { key: 'follow_contracts', to: '/contract/follow-contracts/', icon: 'fa6-solid:flag', label: t('customer_service_block.follow_contracts') },
        { key: 'incidents', to: '/incident/incidents/', icon: 'fa6-solid:bug', label: t('common.incidents') },
        { key: 'process_communications', to: '/communication/process-communications/', icon: 'fa6-solid:envelopes-bulk', label: t('common.comms_process') },
        { key: 'communications', to: '/communication/communications/', icon: 'fa6-solid:envelope', label: t('common.comms') },
        { key: 'ov_logs', to: '/incident/ov-logs/', icon: 'fa6-solid:laptop-file', label: t('common.ov_logs'), available: ovLogsEnabled.value },
      ],
    },
    {
      key: 'contract', id: 'nav-contract', label: t('contracting'), icon: 'fa6-solid:file-contract',
      available: perms.view_contract,
      items: [
        { key: 'contracts', to: '/contract/contracts/', match: '/contracts/', icon: 'fa6-solid:file-contract', label: t('common.contracts') },
        { key: 'contract_requests', to: '/contract/contract-requests/', match: '/contract-requests/', icon: 'fa6-solid:file-circle-plus', label: t('contract_requests') },
        { key: 'contract_terminations', to: '/contract/contract-terminations/', match: '/contract-terminations/', icon: 'fa6-solid:file-circle-xmark', label: t('common.contract_terminations') },
        { key: 'persons', to: '/contract/persons/', match: '/persons/', icon: 'fa6-solid:users', label: t('common.persons') },
        { key: 'aca_documents', to: '/contract/aca-documents/', icon: 'fa6-solid:file-lines', label: t('common.aca_documents'), available: isAcaOrg.value },
        { key: 'document_signs', to: '/contract/document-signs/', icon: 'fa6-solid:signature', label: t('contract_block.document_signs'), available: documentSignEnabled.value },
      ],
    },
    {
      key: 'readings', id: 'nav-tarificacio', label: t('readings'), icon: 'fa6-solid:file-arrow-up',
      available: perms.view_reading,
      items: [
        { key: 'readings', to: '/reading/readings/', icon: 'fa6-solid:file-arrow-up', label: t('common.enter_readings') },
        { key: 'reading_batches', to: '/reading/reading-batches/', icon: 'fa6-solid:clipboard-list', label: t('common.reading_batches') },
      ],
    },
    {
      key: 'billing', id: 'nav-fra', label: t('billing'), icon: 'fa6-solid:file-invoice',
      available: perms.view_billing,
      items: [
        { key: 'billing', to: '/billing/billing/', icon: 'fa6-solid:clipboard', label: t('billing') },
        { key: 'invoices', to: '/billing/invoice/', icon: 'fa6-solid:file-invoice', label: t('invoices') },
        { key: 'budgets', to: '/billing/budgets/', icon: 'fa6-solid:calculator', label: t('common.budgets') },
        { key: 'bails', to: '/billing/bails/', icon: 'fa6-solid:money-bills', label: t('common.bails') },
        { key: 'wallet_managements', to: '/billing/wallet-managements/', icon: 'fa6-solid:briefcase', label: t('common.wallet_mngs') },
        { key: 'joined_payments', to: '/billing/joined-payments/', icon: 'fa6-solid:credit-card', label: t('billing_block.joined_payments') },
        { key: 'transfers', to: '/billing/transfer/', icon: 'fa6-solid:file-export', label: t('common.trf_managements') },
        { key: 'sepa', to: '/billing/sepa/', icon: 'fa6-solid:file-import', label: t('common.sepa_managements') },
        { key: 'sepa_returns', to: '/billing/sepa-return/', icon: 'fa6-solid:file-excel', label: t('billing_block.return_sepa_multiple') },
        { key: 'commitment_deposits', to: '/billing/commitment-deposits/', icon: 'fa6-solid:wallet', label: t('claim_block.pay_commitments') },
        { key: 'claim_managements', to: '/billing/claim-managements/', icon: 'fa-solid:exclamation-circle', label: t('claim_block.claim_payments') },
        { key: 'vulnerability_requests', to: '/billing/vulnerability-requests/', icon: 'fa6-solid:shield-halved', label: t('common.vulnerable_reqs') },
        { key: 'verifactu', to: '/verifactu/batches/', image: '/agencia-tributaria-logo.png', label: 'Verifactu', available: verifactuEnabled },
        { key: 'send_batches', to: '/integrations/batches/', icon: 'fa6-solid:file-invoice-dollar', label: t('send_batch_block.batches'), available: sendBatchEnabled.value },
      ],
    },
    {
      key: 'documents', id: 'nav-documents', label: t('common.documentation'), icon: 'fa6-solid:table-list',
      available: perms.view_customer_service,
      items: [
        { key: 'reports', to: '/billing/reports/', icon: 'fa6-solid:table-list', label: t('common.reports') },
        { key: 'custom_reports', to: '/statistics/custom-reports/', match: '/statistics/custom-reports', icon: 'fa6-solid:table-cells', label: t('custom_report_block.title'), available: perms.view_custom_report || perms.change_custom_report },
        { key: 'daily_documents', to: '/statistics/daily-documents/', icon: 'fa6-solid:file-signature', label: t('statistics_block.daily_document'), dailyDocumentsBadge: true },
        { key: 'document_downloads', to: '/billing/document-downloads/', match: '/billing/document-downloads', icon: 'fa6-solid:download', label: t('billing_block.download_history') },
      ],
    },
    {
      key: 'orders', id: 'nav-orders', label: t('work_orders'), icon: 'fa6-solid:screwdriver-wrench',
      available: perms.view_order,
      items: [
        { key: 'orders', to: '/order/orders/', match: '/orders/', icon: 'fa6-solid:screwdriver-wrench', label: t('common.orders') },
        { key: 'operators', to: '/order/operators/', match: '/operators/', icon: 'healthicons:construction-worker', label: t('common.operators') },
      ],
    },
    {
      key: 'service', id: 'nav-subministrament', label: t('service'), icon: 'fa6-solid:street-view',
      available: perms.view_service,
      items: [
        { key: 'supply_points', to: '/service/supplypoints/', match: '/supplypoints/', icon: 'fa6-solid:street-view', label: t('common.supplys') },
        { key: 'properties', to: '/service/properties/', match: '/properties/', icon: 'fa6-solid:house-chimney', label: t('common.properties') },
        { key: 'routes', to: '/service/routes/', match: '/routes/', icon: 'fa6-regular:map', label: t('common.routes') },
        { key: 'meters', to: '/service/meters/', match: '/meters/', icon: 'my-icon:meter-icon-black', label: t('common.meters') },
        { key: 'clusters', to: '/service/clusters/', match: '/clusters/', icon: 'fa6-solid:list', label: t('common.clusters') },
        { key: 'connections', to: '/service/connections/', match: '/connections/', icon: 'fa6-solid:plug', label: t('common.connections') },
        { key: 'connection_requests', to: '/service/connection-requests/', match: '/connection-requests/', icon: 'fa6-solid:plug-circle-plus', label: t('common.connection_requests') },
        { key: 'supply_cuts', to: '/service/supply-cut/', match: '/supply-cut/', icon: 'fa6-solid:scissors', label: t('common.supply_cuts') },
        { key: 'frauds', to: '/fraud/frauds/', icon: 'fa6-solid:mask', label: t('common.fraud_mngs') },
        { key: 'consumption_management', to: '/consumption-management/', icon: 'fa6-solid:droplet', label: t('common.consumption_mngs') },
      ],
    },
    {
      key: 'pricing', id: 'nav-tarificacio-pricing', label: t('pricing'), icon: 'fa6-solid:tag',
      available: perms.view_pricing,
      items: [
        { key: 'products', to: '/pricing/products/', icon: 'fa6-solid:cube', label: t('common.products') },
        { key: 'price_rates', to: '/pricing/price-rates/', icon: 'fa6-solid:tag', label: t('common.price_rates') },
      ],
    },
    {
      key: 'system', id: 'nav-sistema', label: t('common.system'), icon: 'fa6-solid:chart-column',
      available: perms.view_contract,
      items: [
        { key: 'analysis', to: '/statistics/analysis/', icon: 'fa6-solid:chart-column', label: t('statistics_block.analysis_title') },
      ],
    },
  ];
  return sections
    .filter((section) => section.available)
    .map((section) => ({
      ...section,
      // Un enllaç sense `available` sempre hi és; amb `available`, només si és cert.
      items: section.items.filter((item) => !('available' in item) || !!item.available),
    }))
    .filter((section) => section.items.length > 0);
});

const isMenuItemActive = (item) => route.path.indexOf(item.match || item.to) !== -1;

const {
  sections: orderedMenuSections,
  visibleSections: visibleMenuSections,
  isVisible: isMenuSectionVisible,
  toggleSection: toggleMenuSection,
  moveSectionTo: moveMenuSectionTo,
  moveSectionBy: moveMenuSectionBy,
  isFolded,
  toggleFolded,
  setAllFolded,
  allFolded,
  orderedItems: orderedMenuItems,
  visibleItems: visibleMenuItems,
  isItemVisible: isMenuItemVisible,
  toggleItem: toggleMenuItem,
  moveItemTo: moveMenuItemTo,
  moveItemBy: moveMenuItemBy,
  isCustomised: isMenuCustomised,
  resetLayout: resetMenuLayout,
} = useNavSidebarLayout(menuSections);

const showMenuCustomizer = ref(false);
// Seccions desplegades al panell de personalització per veure'n els enllaços.
const expandedCustomizerSections = ref([]);

const openMenuCustomizer = () => {
  showDropdown.value = false;
  showMenuCustomizer.value = true;
};

const toggleCustomizerSection = (key) => {
  expandedCustomizerSections.value = expandedCustomizerSections.value.includes(key)
    ? expandedCustomizerSections.value.filter((k) => k !== key)
    : [...expandedCustomizerSections.value, key];
};

// Arrossegament al panell: una secció entre seccions o un enllaç dins la seva secció.
const dragged = ref(null); // { sectionKey, itemKey? }
const dropTarget = ref(null);

const isDragged = (sectionKey, itemKey = null) =>
  dragged.value?.sectionKey === sectionKey && (dragged.value?.itemKey ?? null) === itemKey;

const isDropTarget = (sectionKey, itemKey = null) =>
  dropTarget.value?.sectionKey === sectionKey && (dropTarget.value?.itemKey ?? null) === itemKey;

const canDropOn = (sectionKey, itemKey = null) => {
  if (!dragged.value) return false;
  const draggingItem = dragged.value.itemKey != null;
  if (draggingItem !== (itemKey != null)) return false;
  if (draggingItem && dragged.value.sectionKey !== sectionKey) return false;
  return !isDragged(sectionKey, itemKey);
};

const onCustomizerDragStart = (event, sectionKey, itemKey = null) => {
  dragged.value = { sectionKey, itemKey };
  event.dataTransfer.effectAllowed = 'move';
  // Firefox no inicia l'arrossegament sense dades.
  event.dataTransfer.setData('text/plain', itemKey || sectionKey);
};

const onCustomizerDragOver = (event, sectionKey, itemKey = null) => {
  if (!canDropOn(sectionKey, itemKey)) return;
  event.preventDefault();
  dropTarget.value = { sectionKey, itemKey };
};

const onCustomizerDrop = (section, itemKey = null) => {
  if (canDropOn(section.key, itemKey)) {
    if (itemKey) moveMenuItemTo(section, dragged.value.itemKey, itemKey);
    else moveMenuSectionTo(dragged.value.sectionKey, section.key);
  }
  onCustomizerDragEnd();
};

const onCustomizerDragEnd = () => {
  dragged.value = null;
  dropTarget.value = null;
};

const appTitle = computed(() => {
  const name = exploitationStore.current?.name;
  return name ? `Customers - ${name}` : 'Customers';
});

// Fetch exploitation detail to get company name and logo
const { $ExploitationApiService } = useNuxtApp();
const currentExploitation = ref(null);
const username = ref('');

const getCurrentExploitation = async () => {
  try {
    const exploitation_id = localStorage.getItem('exploitation');
    if (exploitation_id) {
      currentExploitation.value = await $ExploitationApiService.getDetail(exploitation_id);
    } else {
      const exploitationsResponse = await $ExploitationApiService.getData();
      if (exploitationsResponse?.results?.length === 1) {
        const defaultExploitation = exploitationsResponse.results[0];
        currentExploitation.value = await $ExploitationApiService.getDetail(defaultExploitation.id);
      } else {
        const companiesResponse = await $ExploitationApiService.getCompanies();
        if (companiesResponse?.results?.length > 0) {
          const defaultCompany = companiesResponse.results.find((c) => c.is_default);
          const selectedCompany = defaultCompany || companiesResponse.results[0];
          currentExploitation.value = { company: selectedCompany };
        }
      }
    }
    exploitationStore.setCurrent(currentExploitation.value);
  } catch (error) {
    console.error('Error fetching current exploitation:', error);
  }
};

const dropdownContainer = ref(null);

const handleClickOutside = (event) => {
  if (dropdownContainer.value && !dropdownContainer.value.contains(event.target)) {
    showDropdown.value = false;
    showMenuCustomizer.value = false;
  }
};

onMounted(() => {
  getCurrentExploitation();
  username.value = localStorage.getItem('user_username') || '';
  document.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside);
});

</script>

<template>
  <nav :class="{
    'fixed left-0 top-0 h-lvh flex flex-col border-slate-200 border border-y-0 border-l-0 px-2 py-1.5 text-base transition-[width,transform] duration-200 ease-in-out': true,
    'w-[250px] min-w-[250px] shrink-0': sideBarStore.isOpen && !sideBarStore.isCollapsed,
    'w-14 min-w-14 shrink-0 px-1.5': sideBarStore.isOpen && sideBarStore.isCollapsed,
    'w-[250px] min-w-[250px]': !sideBarStore.isOpen,
    'translate-x-0': sideBarStore.isOpen,
    '-translate-x-full': !sideBarStore.isOpen,
    'bg-green-100': env.toUpperCase() === 'LOCAL',
    'bg-yellow-100': env.toUpperCase() === 'TEST',
    'bg-slate-100': env.toUpperCase() !== 'TEST' && env.toUpperCase() !== 'LOCAL',
  }">
    <!-- Fixed Top Part -->
    <div class="flex-shrink-0 border-b border-slate-200/60 pb-2 mb-2">
      <div id="nav-logo" class="flex items-center gap-1 mb-2" :class="isCollapsed ? 'flex-col' : 'grid grid-cols-[4fr,1fr]'">
        <NuxtLink to="/"
          class="flex gap-3 items-center font-medium px-2 py-1.5 leading-[14px] rounded min-w-0 flex-1"
          :class="[hoverClass, { 'justify-center': isCollapsed }]"
          :title="isCollapsed ? appTitle : undefined">
          <img src="/favicon-32x32.png" alt="" class="shrink-0" style="width: 25px;" />
          <span v-show="!isCollapsed" class="truncate">{{ appTitle }}</span>
        </NuxtLink>
        <div class="flex gap-1 shrink-0" :class="isCollapsed ? 'flex-col' : 'justify-end'">
          <button
            v-if="sideBarStore.isOpen && !sideBarStore.isCollapsed"
            class="flex opacity-50 items-center border rounded px-2 py-1 my-1 text-slate-600 hover:opacity-100 hover:border-slate-400 active:bg-slate-300"
            title="Collapse to icons"
            @click="collapseOrCloseSidebar">
            <Icon name="fa6-solid:angles-left" class="text-slate-400" />
          </button>
          <template v-if="sideBarStore.isCollapsed">
            <button
              class="flex items-center justify-center border rounded p-1.5 text-slate-600 hover:opacity-100 hover:border-slate-400 active:bg-slate-300"
              title="Expand sidebar"
              @click="expandSidebar">
              <Icon name="fa6-solid:angles-right" class="text-slate-400 text-sm" />
            </button>
            <button
              class="flex items-center justify-center border rounded p-1.5 text-slate-600 hover:opacity-100 hover:border-slate-400 active:bg-slate-300"
              title="Close sidebar"
              @click="closeNavSidebar">
              <Icon name="fa6-solid:angles-left" class="text-slate-400 text-sm" />
            </button>
          </template>
        </div>
      </div>

      <div id="nav-favorites" class="mb-2">
        <NuxtLink to="/"
          class="flex w-full max-h-8 items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path === '/', 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('dashboard.dashboard') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:house" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('dashboard.dashboard') }}</span>
          </div>
        </NuxtLink>

        <NuxtLink to="/calendar"
          class="flex w-full max-h-8 items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.startsWith('/calendar'), 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('calendar_tasks.title') + (pendingTasks ? ` (${pendingTasks})` : '') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center relative">
              <Icon name="fa6-solid:calendar-days" class="text-slate-500" />
              <span v-if="isCollapsed && pendingTasks" class="absolute -top-1 -right-1 h-2 w-2 rounded-full"
                :class="tasksSummary.overdue ? 'bg-red-500' : 'bg-sky-500'" />
            </span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('calendar_tasks.title') }}</span>
          </div>
          <span v-show="!isCollapsed && pendingTasks" class="text-xs font-semibold text-white rounded-full px-1.5 py-0.5 shrink-0"
            :class="tasksSummary.overdue ? 'bg-red-500' : 'bg-sky-500'"
            :title="$t('calendar_tasks.badge_title', { today: tasksSummary.today, overdue: tasksSummary.overdue })">
            {{ pendingTasks }}
          </span>
        </NuxtLink>

        <button
          class="flex w-full max-h-8 items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('dashboard.search') : undefined"
          @click="toggleSearcher">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:magnifying-glass" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('dashboard.search') }}</span>
          </div>
          <kbd v-show="!isCollapsed" class="px-1 py-1.5 text-xs font-light border rounded-lg shrink-0" :class="tooltipClasses">Ctrl k</kbd>
        </button>

        <button
          class="flex w-full max-h-8 items-center px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, {
            'font-[750]': sideBarStore.newNotifications > 0,
            'font-medium': sideBarStore.newNotifications == 0,
            'justify-center': isCollapsed
          }]"
          :title="isCollapsed ? $t('dashboard.notifications') + (sideBarStore.newNotifications ? ` (${sideBarStore.newNotifications})` : '') : undefined"
          @click="toggleNotifications"
          role="notificationRegion">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:bell" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('dashboard.notifications') }}</span>
            <span v-show="!isCollapsed">({{ sideBarStore.newNotifications }})</span>
          </div>
          <kbd v-show="!isCollapsed" class="px-1 py-1.5 text-xs font-light border rounded-lg shrink-0" :class="tooltipClasses">Ctrl u</kbd>
        </button>
      </div>
    </div>

    <!-- Scrollable Middle Part -->
    <div class="flex-1 overflow-y-auto pr-1 select-none scrollbar-thin">
      <MoleculesNavSidebarSection v-for="section in visibleMenuSections" :key="section.key" :id="section.id"
        :title="section.label" :folded="isFolded(section.key)" :icons-only="isCollapsed"
        @toggle="toggleFolded(section.key)">
        <NuxtLink v-for="item in visibleMenuItems(section)" :key="item.key" :to="item.to"
          class="flex w-full items-center px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, {
            [highlightClass]: isMenuItemActive(item),
            'font-[750]': item.dailyDocumentsBadge && sideBarStore.newDailyDocuments > 0,
            'font-medium': !(item.dailyDocumentsBadge && sideBarStore.newDailyDocuments > 0),
            'justify-center': isCollapsed
          }]"
          :title="isCollapsed ? item.label + (item.dailyDocumentsBadge && sideBarStore.newDailyDocuments ? ` (${sideBarStore.newDailyDocuments})` : '') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="relative flex w-6 shrink-0 justify-center">
              <img v-if="item.image" :src="item.image" alt="" class="h-4 grayscale brightness-75 opacity-70" />
              <Icon v-else :name="item.icon" class="text-slate-500" />
              <span
                v-if="item.dailyDocumentsBadge && sideBarStore.newDailyDocuments > 0"
                class="pointer-events-none absolute -top-0.5 -right-0.5 flex size-2"
                aria-hidden="true">
                <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75"></span>
                <span class="relative inline-flex size-2 rounded-full bg-sky-500"></span>
              </span>
            </span>
            <span v-show="!isCollapsed" class="truncate">{{ item.label }}</span>
            <span v-if="item.dailyDocumentsBadge" v-show="!isCollapsed">({{ sideBarStore.newDailyDocuments }})</span>
          </div>
        </NuxtLink>
      </MoleculesNavSidebarSection>

      <!-- Accés visible a la personalització, sempre al final de les seccions -->
      <button type="button"
        class="flex w-full items-center px-3 py-2 leading-[14px] text-sm text-slate-400 rounded hover:text-slate-600"
        :class="[hoverClass, { 'justify-center': isCollapsed, 'text-slate-600': showMenuCustomizer }]"
        :title="$t('common.customize_menu')"
        @click.stop="showMenuCustomizer ? (showMenuCustomizer = false) : openMenuCustomizer()">
        <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
          <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:sliders" /></span>
          <span v-show="!isCollapsed" class="truncate">{{ $t('common.customize_menu') }}</span>
        </div>
      </button>
    </div>

    <!-- Fixed Bottom Part -->
    <div ref="dropdownContainer" class="flex-shrink-0 pt-2 border-t border-slate-200/60 mt-auto flex flex-col gap-2 relative">
      <!-- Exploitation Dropdown Menu -->
      <div v-show="showDropdown" 
        class="absolute bottom-full left-0 mb-2 w-full bg-white border border-slate-200 rounded-lg shadow-lg py-2 z-30 flex flex-col gap-1 text-sm text-slate-700">
        

        <!-- Language Select -->
        <div class="px-3 py-1 flex flex-col gap-1.5">
          <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">{{ $t('common.language') }}</span>
          <select :value="locale" @change="switchLanguage($event.target.value)"
            class="input h-8 text-xs">
            <option v-for="lang in languages" :key="lang.code" :value="lang.code">
              {{ $t(lang.name) }}
            </option>
          </select>
        </div>

        <div class="border-t border-slate-100 my-1"></div>

        <!-- Configuration button -->
        <NuxtLink to="/settings/" @click="showDropdown = false"
          class="flex items-center gap-2 px-3 py-2 hover:bg-slate-50 transition-colors">
          <Icon name="fa6-solid:gear" class="w-4 h-4 text-slate-500" />
          <span>{{ $t('common.settings') }}</span>
        </NuxtLink>

        <!-- Personalitzar el menú lateral -->
        <button type="button" @click="openMenuCustomizer"
          class="flex items-center gap-2 px-3 py-2 hover:bg-slate-50 transition-colors w-full text-left">
          <Icon name="fa6-solid:sliders" class="w-4 h-4 text-slate-500" />
          <span>{{ $t('common.customize_menu') }}</span>
        </button>

        <div class="border-t border-slate-100 my-1"></div>

        <!-- Help button -->
        <a :href="`https://docs.customers.aqua360.cloud/${locale}/`" target="_blank" rel="noopener noreferrer" @click="showDropdown = false"
          class="flex items-center gap-2 px-3 py-2 hover:bg-slate-50 transition-colors">
          <Icon name="fa6-solid:circle-question" class="w-4 h-4 text-slate-500" />
          <span>{{ $t('common.help') }}</span>
        </a>

        <!-- Deploy info: data del deploy i, en hover, els commits desplegats -->
        <div class="px-3 py-2 flex items-center gap-2 text-slate-500 select-none cursor-help"
          :title="deployInfoAvailable ? deployTooltip : $t('common.deploy_unknown')">
          <Icon name="fa6-solid:code-branch" class="w-4 h-4 text-slate-400 shrink-0" />
          <span class="text-xs truncate">
            {{ $t('common.deploy') }}:
            <span class="font-medium text-slate-600">{{ deployedAtLabel || '—' }}</span>
          </span>
        </div>

        <!-- User Profile Info -->
        <div v-if="username" class="px-3 py-1.5 flex items-center gap-2 select-none">
          <div class="rounded-full w-4 h-4 bg-slate-100 flex items-center justify-center border font-semibold text-slate-600 text-xs shrink-0">
            {{ username.charAt(0).toUpperCase() }}
          </div>
          <div class="flex flex-col min-w-0">
            <span class="text-xs font-semibold text-slate-700 truncate" :title="username">{{ username }}</span>
          </div>
        </div>

        <!-- Exit button -->
        <button @click="logout(); showDropdown = false;"
          class="flex items-center gap-2 px-3 py-2 hover:bg-red-50 text-red-600 transition-colors w-full text-left">
          <Icon name="fa6-solid:arrow-right-from-bracket" class="w-4 h-4 text-red-500" />
          <span>{{ $t('common.exit') }}</span>
        </button>
      </div>

      <!-- Personalització del menú: seccions i enllaços visibles, i el seu ordre -->
      <div v-if="showMenuCustomizer"
        class="absolute bottom-full left-0 mb-2 w-[300px] max-h-[75vh] overflow-y-auto bg-white border border-slate-200 rounded-lg shadow-lg p-2 z-30 text-sm text-slate-700">
        <div class="flex items-center justify-between px-1">
          <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">{{ $t('common.customize_menu') }}</span>
          <button type="button" class="px-1 text-slate-400 hover:text-slate-600" :title="$t('common.close')"
            @click="showMenuCustomizer = false">
            <Icon name="fa6-solid:xmark" />
          </button>
        </div>
        <p class="text-xs text-slate-400 px-1 pb-2">{{ $t('common.customize_menu_help') }}</p>

        <div v-for="(section, index) in orderedMenuSections" :key="section.key">
          <div class="flex items-center gap-1 px-1 py-1 hover:bg-slate-100 rounded"
            :class="{ 'opacity-50': isDragged(section.key), 'bg-sky-50': isDropTarget(section.key) }"
            draggable="true" @dragstart="onCustomizerDragStart($event, section.key)"
            @dragover="onCustomizerDragOver($event, section.key)" @drop.prevent="onCustomizerDrop(section)"
            @dragend="onCustomizerDragEnd">
            <Icon name="fa6-solid:grip-vertical" class="text-slate-300 cursor-grab shrink-0"
              :title="$t('common.drag_to_reorder')" />
            <label class="flex items-center gap-2 flex-1 min-w-0 cursor-pointer font-medium">
              <input type="checkbox" :checked="isMenuSectionVisible(section.key)"
                :disabled="isMenuSectionVisible(section.key) && visibleMenuSections.length <= 1"
                @change="toggleMenuSection(section.key)" />
              <Icon :name="section.icon" class="text-slate-500 shrink-0" />
              <span class="truncate">{{ section.label }}</span>
            </label>
            <button type="button" class="px-1 text-slate-400 hover:text-sky-600"
              :title="$t('common.show_section_links')" :aria-expanded="expandedCustomizerSections.includes(section.key)"
              @click="toggleCustomizerSection(section.key)">
              <Icon name="fa6-solid:chevron-right" class="text-xs transition-transform"
                :class="{ 'rotate-90': expandedCustomizerSections.includes(section.key) }" />
            </button>
            <button type="button" class="px-1 text-slate-400 hover:text-sky-600 disabled:opacity-30"
              :disabled="index === 0" :title="$t('common.move_up')" @click="moveMenuSectionBy(section.key, -1)">
              <Icon name="fa6-solid:arrow-up" class="text-xs" />
            </button>
            <button type="button" class="px-1 text-slate-400 hover:text-sky-600 disabled:opacity-30"
              :disabled="index === orderedMenuSections.length - 1" :title="$t('common.move_down')"
              @click="moveMenuSectionBy(section.key, 1)">
              <Icon name="fa6-solid:arrow-down" class="text-xs" />
            </button>
          </div>

          <!-- Enllaços de la secció -->
          <div v-if="expandedCustomizerSections.includes(section.key)" class="ml-5 pl-1 border-l border-slate-100">
            <div v-for="(item, itemIndex) in orderedMenuItems(section)" :key="item.key"
              class="flex items-center gap-1 px-1 py-0.5 hover:bg-slate-100 rounded"
              :class="{ 'opacity-50': isDragged(section.key, item.key), 'bg-sky-50': isDropTarget(section.key, item.key) }"
              draggable="true" @dragstart="onCustomizerDragStart($event, section.key, item.key)"
              @dragover="onCustomizerDragOver($event, section.key, item.key)"
              @drop.prevent="onCustomizerDrop(section, item.key)" @dragend="onCustomizerDragEnd">
              <Icon name="fa6-solid:grip-vertical" class="text-slate-300 cursor-grab shrink-0"
                :title="$t('common.drag_to_reorder')" />
              <label class="flex items-center gap-2 flex-1 min-w-0 cursor-pointer">
                <input type="checkbox" :checked="isMenuItemVisible(section.key, item.key)"
                  :disabled="isMenuItemVisible(section.key, item.key) && visibleMenuItems(section).length <= 1"
                  @change="toggleMenuItem(section, item.key)" />
                <img v-if="item.image" :src="item.image" alt="" class="h-3.5 shrink-0 grayscale brightness-75 opacity-70" />
                <Icon v-else :name="item.icon" class="text-slate-500 shrink-0" />
                <span class="truncate">{{ item.label }}</span>
              </label>
              <button type="button" class="px-1 text-slate-400 hover:text-sky-600 disabled:opacity-30"
                :disabled="itemIndex === 0" :title="$t('common.move_up')" @click="moveMenuItemBy(section, item.key, -1)">
                <Icon name="fa6-solid:arrow-up" class="text-xs" />
              </button>
              <button type="button" class="px-1 text-slate-400 hover:text-sky-600 disabled:opacity-30"
                :disabled="itemIndex === section.items.length - 1" :title="$t('common.move_down')"
                @click="moveMenuItemBy(section, item.key, 1)">
                <Icon name="fa6-solid:arrow-down" class="text-xs" />
              </button>
            </div>
          </div>
        </div>

        <div class="border-t border-slate-100 mt-2 pt-2 flex flex-col items-start gap-1 px-1">
          <button type="button" class="text-sky-600 hover:underline" @click="setAllFolded(!allFolded)">
            {{ allFolded ? $t('common.unfold_all_sections') : $t('common.fold_all_sections') }}
          </button>
          <button v-if="isMenuCustomised" type="button" class="text-sky-600 hover:underline" @click="resetMenuLayout">
            {{ $t('common.restore_default_menu') }}
          </button>
        </div>
      </div>

      <!-- Exploitation Trigger Button -->
      <button @click="toggleDropdown" v-if="currentExploitation?.company" 
        class="w-full text-left px-2 py-1.5 flex items-center gap-2 border border-slate-200/40 rounded bg-white/40 min-w-0 hover:bg-slate-200/40 active:bg-slate-200/60 transition-all duration-150" 
        :class="{ 'justify-center': isCollapsed }"
        :title="isCollapsed ? (currentExploitation.name ? `${currentExploitation.company.name} (${currentExploitation.name})` : currentExploitation.company.name) : undefined">
        <div v-if="currentExploitation.company.logo" 
          class="rounded shrink-0 w-8 h-8 bg-cover bg-center border"
          :style="{ 'background-image': `url(${currentExploitation.company.logo})` }">
        </div>
        <div v-else 
          class="rounded shrink-0 w-8 h-8 bg-slate-200 flex items-center justify-center border font-bold text-slate-600 text-sm">
          {{ currentExploitation.company.name.charAt(0) }}
        </div>
        <div v-show="!isCollapsed" class="flex flex-col min-w-0 flex-1">
          <span class="text-xs font-semibold text-slate-800 truncate" :title="currentExploitation.company.name">{{ currentExploitation.company.name }}</span>
          <span v-if="currentExploitation.name" class="text-[10px] text-slate-500 truncate" :title="currentExploitation.name">{{ currentExploitation.name }}</span>
        </div>
        <Icon v-show="!isCollapsed" name="fa6-solid:chevron-up" class="w-3 h-3 text-slate-400 transition-transform duration-200 shrink-0" :class="{ 'rotate-180': showDropdown }" />
      </button>
    </div>

  </nav>
</template>

<style scoped>
/* Integrated custom scrollbar that doesn't stand out */
.overflow-y-auto::-webkit-scrollbar {
  width: 4px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: transparent;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.12);
  border-radius: 2px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.24);
}
</style>
