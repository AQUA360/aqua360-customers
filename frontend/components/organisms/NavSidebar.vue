<script setup>
import { useI18n } from 'vue-i18n';
import { useSidebarStore } from '~/stores/useNavSideBar';
import GeneralNoteList from '~/components/molecules/GeneralNoteList.vue';
import { usePermissions } from '~/middleware/permission';
import { useConfigStore } from '~/stores/useConfigStore';
import { useExploitationStore } from '~/stores/useExploitationStore';
import { storeToRefs } from 'pinia';
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';

const { t, locale } = useI18n();
const sideBarStore = useSidebarStore();
const configStore = useConfigStore();
const exploitationStore = useExploitationStore();
const { ovEnabled: ovLogsEnabled, documentSignEnabled } = storeToRefs(configStore);
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

// Initialize config fetch
configStore.fetchOvEnabled();
configStore.fetchDocumentSignEnabled();

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
  if (showDropdown.value && dropdownContainer.value && !dropdownContainer.value.contains(event.target)) {
    showDropdown.value = false;
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
      <div v-if="permissions?.permissions?.view_customer_service" id="nav-incident" class="mb-2">
        <div v-show="!isCollapsed" class="text-sm text-slate-400 p-1">{{ $t('customer_service') }}</div>
        <NuxtLink to="/contract/follow-contracts/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/contract/follow-contracts/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('customer_service_block.follow_contracts') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:flag" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('customer_service_block.follow_contracts') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/incident/incidents/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/incident/incidents/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.incidents') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:bug" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.incidents') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/communication/process-communications/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/communication/process-communications/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.comms_process') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:envelopes-bulk" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.comms_process') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/communication/communications/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/communication/communications/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.comms') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:envelope" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.comms') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink v-if="ovLogsEnabled" to="/incident/ov-logs/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/incident/ov-logs/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.ov_logs') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:laptop-file" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.ov_logs') }}</span>
          </div>
        </NuxtLink>
      </div>

      <div v-if="permissions?.permissions?.view_contract" id="nav-contract" class="mb-2">
        <div v-show="!isCollapsed" class="text-sm text-slate-400 p-1">{{ $t('contracting') }}</div>
        <NuxtLink to="/contract/contracts/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/contracts/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.contracts') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:file-contract" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.contracts') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/contract/contract-requests/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/contract-requests/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('contract_requests') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:file-circle-plus" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('contract_requests') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/contract/contract-terminations/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/contract-terminations/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.contract_terminations') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:file-circle-xmark" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.contract_terminations') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/contract/persons/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/persons/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.persons') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:users" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.persons') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/contract/aca-documents/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/contract/aca-documents/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.aca_documents') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:file-lines" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.aca_documents') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink v-if="documentSignEnabled" to="/contract/document-signs/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/contract/document-signs/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('contract_block.document_signs') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:signature" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('contract_block.document_signs') }}</span>
          </div>
        </NuxtLink>
      </div>

      <div v-if="permissions?.permissions?.view_reading" id="nav-tarificacio" class="mb-2">
        <div v-show="!isCollapsed" class="text-sm text-slate-400 p-1">{{ $t('readings') }}</div>
        <NuxtLink to="/reading/readings/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/reading/readings/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.enter_readings') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:file-arrow-up" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.enter_readings') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/reading/reading-batches/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/reading/reading-batches/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.reading_batches') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:clipboard-list" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.reading_batches') }}</span>
          </div>
        </NuxtLink>
      </div>

      <div v-if="permissions?.permissions?.view_billing" id="nav-fra" class="mb-2">
        <div v-show="!isCollapsed" class="text-sm text-slate-400 p-1">{{ $t('billing') }}</div>
        <NuxtLink to="/billing/billing/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/billing/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('billing') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:clipboard" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('billing') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/billing/invoice/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/invoice/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('invoices') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:file-invoice" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('invoices') }}</span>
          </div>
        </NuxtLink>
        <!-- <NuxtLink to="/billing/reports/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/reports/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.reports') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:table-list" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.reports') }}</span>
          </div>
        </NuxtLink> -->
        <NuxtLink to="/billing/budgets/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/budgets/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.budgets') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:calculator" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.budgets') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/billing/bails/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/bails/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.bails') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:money-bills" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.bails') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/billing/wallet-managements/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/wallet-managements/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.wallet_mngs') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:briefcase" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.wallet_mngs') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/billing/joined-payments/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/joined-payments/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('billing_block.joined_payments') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:credit-card" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('billing_block.joined_payments') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/billing/transfer/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/transfer/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.trf_managements') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:file-export" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.trf_managements') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/billing/sepa/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/sepa/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.sepa_managements') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:file-import" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.sepa_managements') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/billing/sepa-return/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/sepa-return/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.wallet_mngs') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:file-excel" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('billing_block.return_sepa_multiple') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/billing/commitment-deposits/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/commitment-deposits/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('claim_block.pay_commitments') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:wallet" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('claim_block.pay_commitments') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/billing/claim-managements/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/claim-managements/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('claim_block.claim_payments') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa-solid:exclamation-circle" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('claim_block.claim_payments') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/billing/vulnerability-requests/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/vulnerability-requests/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.vulnerable_reqs') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:shield-halved" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.vulnerable_reqs') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink v-if="verifactuEnabled" to="/verifactu/batches/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/verifactu/batches/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? 'Verifactu' : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><img src="/agencia-tributaria-logo.png" alt="Agencia Tributaria" class="h-4 grayscale brightness-75 opacity-70" /></span>
            <span v-show="!isCollapsed" class="truncate">Verifactu</span>
          </div>
        </NuxtLink>
      </div>

      <div v-if="permissions?.permissions?.view_customer_service" id="nav-documents" class="mb-2">
        <div v-show="!isCollapsed" class="text-sm text-slate-400 p-1">{{ $t('common.documentation') }}</div>
        <NuxtLink to="/billing/reports/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/billing/reports/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.reports') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:table-list" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.reports') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/statistics/daily-documents/"
          class="flex w-full items-center px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, {
            [highlightClass]: $route.path.indexOf('/statistics/daily-documents/') != -1,
            'font-[750]': sideBarStore.newDailyDocuments > 0,
            'font-medium': sideBarStore.newDailyDocuments == 0,
            'justify-center': isCollapsed
          }]"
          :title="isCollapsed ? $t('statistics_block.daily_document') + (sideBarStore.newDailyDocuments ? ` (${sideBarStore.newDailyDocuments})` : '') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="relative flex w-6 shrink-0 justify-center">
              <Icon name="fa6-solid:file-signature" class="text-slate-500" />
              <span
                v-if="sideBarStore.newDailyDocuments > 0"
                class="pointer-events-none absolute -top-0.5 -right-0.5 flex size-2"
                aria-hidden="true">
                <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75"></span>
                <span class="relative inline-flex size-2 rounded-full bg-sky-500"></span>
              </span>
            </span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('statistics_block.daily_document') }}</span>
            <span v-show="!isCollapsed">({{ sideBarStore.newDailyDocuments }})</span>
          </div>
        </NuxtLink>
      </div>

      <div v-if="permissions?.permissions?.view_order" id="nav-orders" class="mb-2">
        <div v-show="!isCollapsed" class="text-sm text-slate-400 p-1">{{ $t('work_orders') }}</div>
        <NuxtLink to="/order/orders/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/orders/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.orders') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:screwdriver-wrench" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.orders') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/order/operators/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/operators/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.operators') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="healthicons:construction-worker" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.operators') }}</span>
          </div>
        </NuxtLink>
      </div>

      <div v-if="permissions?.permissions?.view_service" id="nav-subministrament" class="mb-2">
        <div v-show="!isCollapsed" class="text-sm text-slate-400 p-1">{{ $t('service') }}</div>
        <NuxtLink to="/service/supplypoints/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/supplypoints/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.supplys') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:street-view" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.supplys') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/service/properties/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/properties/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.properties') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:house-chimney" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.properties') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/service/routes/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/routes/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.routes') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-regular:map" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.routes') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/service/meters/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/meters/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.meters') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="my-icon:meter-icon-black" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.meters') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/service/clusters/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/clusters/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.clusters') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:list" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.clusters') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/service/connections/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/connections/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.connections') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:plug" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.connections') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/service/connection-requests/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/connection-requests/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.connection_requests') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:plug-circle-plus" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.connection_requests') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/service/supply-cut/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/supply-cut/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.supply_cuts') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:scissors" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.supply_cuts') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/fraud/frauds/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/fraud/frauds/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.fraud_mngs') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:mask" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.fraud_mngs') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/consumption-management/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/consumption-management/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.consumption_mngs') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:droplet" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.consumption_mngs') }}</span>
          </div>
        </NuxtLink>
      </div>

      <div v-if="permissions?.permissions?.view_pricing" id="nav-tarificacio-pricing" class="mb-2">
        <div v-show="!isCollapsed" class="text-sm text-slate-400 p-1">{{ $t('pricing') }}</div>
        <NuxtLink to="/pricing/products/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/pricing/products/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.products') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:cube" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.products') }}</span>
          </div>
        </NuxtLink>
        <NuxtLink to="/pricing/price-rates/"
          class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
          :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/pricing/price-rates/') != -1, 'justify-center': isCollapsed }]"
          :title="isCollapsed ? $t('common.price_rates') : undefined">
          <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
            <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:tag" class="text-slate-500" /></span>
            <span v-show="!isCollapsed" class="truncate">{{ $t('common.price_rates') }}</span>
          </div>
        </NuxtLink>
      </div>

      <div id="nav-sistema" class="mb-2">
        <div v-show="!isCollapsed" class="text-sm text-slate-400 p-1">{{ $t('common.system') }}</div>
        <div v-if="permissions?.permissions?.view_contract" id="nav-statistics" class="mb-2">
          <NuxtLink to="/statistics/analysis/"
            class="flex w-full items-center font-medium px-3 py-2 leading-[14px] text-slate-600 rounded"
            :class="[hoverClass, { [highlightClass]: $route.path.indexOf('/statistics/analysis/') != -1, 'justify-center': isCollapsed }]"
            :title="isCollapsed ? $t('statistics_block.analysis_title') : undefined">
            <div class="flex items-center gap-2 min-w-0 flex-1" :class="{ 'justify-center': isCollapsed }">
              <span class="flex w-6 shrink-0 justify-center"><Icon name="fa6-solid:chart-column" class="text-slate-500" /></span>
              <span v-show="!isCollapsed" class="truncate">{{ $t('statistics_block.analysis_title') }}</span>
            </div>
          </NuxtLink>
        </div>
      </div>
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
