<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import Draggable from 'vuedraggable';
import { DASHBOARD_SIZE_CLASSES, defaultCardConfig, newCardId } from '~/utils/dashboardCards';
import DashboardCardCatalogModal from '~/components/molecules/dashboard/DashboardCardCatalogModal.vue';
import DashboardCardConfigModal from '~/components/molecules/dashboard/DashboardCardConfigModal.vue';
import DashboardKpiCard from '~/components/molecules/dashboard/DashboardKpiCard.vue';
import DashboardOrdersCard from '~/components/molecules/dashboard/DashboardOrdersCard.vue';
import DashboardReadingBatchesCard from '~/components/molecules/dashboard/DashboardReadingBatchesCard.vue';
import DashboardTasksCard from '~/components/molecules/dashboard/DashboardTasksCard.vue';
import DashboardDailyActivityCard from '~/components/molecules/dashboard/DashboardDailyActivityCard.vue';
import DashboardRecentSearchesCard from '~/components/molecules/dashboard/DashboardRecentSearchesCard.vue';
import DashboardCalendarCard from '~/components/molecules/dashboard/DashboardCalendarCard.vue';
import DashboardQuickAccessCard from '~/components/molecules/dashboard/DashboardQuickAccessCard.vue';

/**
 * Pàgina d'inici: dashboard personalitzable per usuari. La disposició (quines
 * cards, en quin ordre, amb quina mida i configuració) es desa al backend, i
 * cada card carrega les seves dades per separat.
 */

const { t } = useI18n()
const sidebarStore = useSidebarStore();
const { $DashboardApiService } = useNuxtApp();

// Cada card va dins d'una columna amb `min-w-0`: sense això, el contingut ample
// (p. ex. una fila amb scroll horitzontal) eixampla la columna de la graella.
// No es pot posar com a comentari dins del slot #item del Draggable: en
// desenvolupament compta com un node i vuedraggable exigeix un sol fill.
const CARD_COMPONENTS = {
  daily_activity: DashboardDailyActivityCard,
  tasks_today: DashboardTasksCard,
  orders_to_validate: DashboardOrdersCard,
  change_meter_pending: DashboardOrdersCard,
  reading_batches_in_progress: DashboardReadingBatchesCard,
  invoices_issued: DashboardKpiCard,
  invoice_cancellations: DashboardKpiCard,
  rebillings: DashboardKpiCard,
  recent_searches: DashboardRecentSearchesCard,
  calendar: DashboardCalendarCard,
  quick_access: DashboardQuickAccessCard,
};

const handleKeydown = (event) => {
    if (event.ctrlKey && event.key === 'k') {
        event.preventDefault();
        sidebarStore.openSearch();
    } else if ((event.key === 'Escape') && sidebarStore.isSearchOpen) {
        event.preventDefault();
        sidebarStore.closeSearch();
    }
};

const username = ref('')
if (process.client) {
    username.value = localStorage.getItem('user_username') || '';
}

const loading = ref(true);
const loadFailed = ref(false);
const layout = ref([]);
const availableCards = ref([]);
const editing = ref(false);
const saving = ref(false);
const showCatalog = ref(false);
const configItem = ref(null);

const cardsByKey = computed(() => Object.fromEntries(availableCards.value.map(card => [card.key, card])));
// Només es pinten les cards que el frontend sap mostrar
const visibleLayout = computed(() => layout.value.filter(item => CARD_COMPONENTS[item.key]));
const usedKeys = computed(() => layout.value.map(item => item.key));
const configCard = computed(() => configItem.value ? cardsByKey.value[configItem.value.key] : null);
const showConfig = computed({
    get: () => !!configItem.value,
    set: (value) => { if (!value) configItem.value = null; },
});

/**
 * Sessió amb què s'ha carregat la disposició. Cada petició llegeix el token de
 * localStorage en el moment de fer-la, i aquest és compartit per totes les pestanyes:
 * si en una altra pestanya es tanca la sessió o s'entra amb un altre usuari, aquesta
 * pestanya no ha de desar la disposició que mostra (és de l'usuari anterior) al
 * compte del nou usuari.
 */
const readToken = () => {
    try { return localStorage.getItem('auth_token'); } catch (e) { return null; }
};
let sessionToken = null;
const isSameSession = () => !!sessionToken && readToken() === sessionToken;

const loadDashboard = async () => {
    loading.value = true;
    loadFailed.value = false;
    sessionToken = readToken();
    try {
        const [layoutResponse, cards] = await Promise.all([
            $DashboardApiService.getLayout(),
            $DashboardApiService.getCards(),
        ]);
        layout.value = layoutResponse.layout;
        availableCards.value = cards;
    } catch (error) {
        console.error(error);
        loadFailed.value = true;
    } finally {
        loading.value = false;
    }
};

let saveTimeout = null;
const saveLayout = async () => {
    saveTimeout = null;
    if (!isSameSession()) return;
    saving.value = true;
    try {
        await $DashboardApiService.saveLayout(layout.value);
    } catch (error) {
        console.error(error);
    } finally {
        saving.value = false;
    }
};
// Es desa poc després de cada canvi, sense botó de desar
const scheduleSave = () => {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(saveLayout, 600);
};

const addCard = (card) => {
    layout.value.push({
        id: newCardId(),
        key: card.key,
        size: card.default_size,
        config: defaultCardConfig(card),
    });
    scheduleSave();
};

const removeCard = (item) => {
    layout.value = layout.value.filter(current => current.id !== item.id);
    scheduleSave();
};

const updateCard = (updated) => {
    layout.value = layout.value.map(item => item.id === updated.id ? updated : item);
    scheduleSave();
};

const resetLayout = async () => {
    if (!confirm(t('home_dashboard.reset_confirm'))) return;
    clearTimeout(saveTimeout);
    if (!isSameSession()) return loadDashboard();
    const response = await $DashboardApiService.resetLayout();
    layout.value = response.layout;
};

const finishEditing = async () => {
    editing.value = false;
    if (saveTimeout) {
        clearTimeout(saveTimeout);
        await saveLayout();
    }
};

// Canvi de sessió en una altra pestanya del mateix navegador (logout o un altre usuari):
// es descarten els canvis pendents i es carrega el dashboard del nou usuari.
const handleStorage = (event) => {
    if (event.key !== null && event.key !== 'auth_token' && event.key !== 'user_username') return;
    if (readToken() === sessionToken) {
        username.value = localStorage.getItem('user_username') || '';
        return;
    }
    clearTimeout(saveTimeout);
    saveTimeout = null;
    editing.value = false;
    showCatalog.value = false;
    configItem.value = null;
    if (!readToken()) {
        navigateTo('/auth/login');
        return;
    }
    username.value = localStorage.getItem('user_username') || '';
    loadDashboard();
};

onMounted(() => {
    window.addEventListener('keydown', handleKeydown);
    window.addEventListener('storage', handleStorage);
    loadDashboard();
});

onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown);
    window.removeEventListener('storage', handleStorage);
    // En sortir de la pàgina es desen els canvis pendents (no si la sessió ja és una altra o s'ha tancat)
    if (saveTimeout) {
        clearTimeout(saveTimeout);
        saveLayout();
    }
});
</script>
<template>
    <div class="w-full max-w-7xl mx-auto px-6 pb-24">

        <div class="flex flex-wrap items-center justify-between gap-3 mb-6">
            <h1 class="text-3xl font-semibold text-slate-800">{{ $t('dashboard.welcome') + ', ' + username }}</h1>
            <div class="flex items-center gap-2">
                <span v-if="saving" class="text-xs text-slate-400">{{ t('home_dashboard.saving') }}...</span>
                <template v-if="editing">
                    <button type="button" class="button-default" @click="resetLayout">
                        <Icon name="fa6-solid:arrow-rotate-left" />&nbsp;{{ t('home_dashboard.reset') }}
                    </button>
                    <button type="button" class="button-default" @click="showCatalog = true">
                        <Icon name="fa6-solid:plus" />&nbsp;{{ t('home_dashboard.add_card') }}
                    </button>
                    <button type="button" class="button-primary" @click="finishEditing">
                        <Icon name="fa6-solid:check" />&nbsp;{{ t('home_dashboard.done') }}
                    </button>
                </template>
                <button v-else-if="!loading && !loadFailed" type="button" class="button-default" @click="editing = true">
                    <Icon name="fa6-solid:table-cells-large" />&nbsp;{{ t('home_dashboard.customize') }}
                </button>
            </div>
        </div>

        <div v-if="loading" class="grid grid-cols-6 gap-4">
            <div v-for="n in 4" :key="n" class="col-span-6 xl:col-span-3 customers-shadow rounded-lg p-6">
                <AtomsSkeleton class="w-full" :height="3" :has_icon="false" />
            </div>
        </div>

        <div v-else-if="loadFailed" class="customers-shadow rounded-lg p-6 text-center text-slate-500">
            {{ t('common.error_load') }}
            <button class="underline text-sky-500 ml-2" @click="loadDashboard">{{ t('common.load_again') }}</button>
        </div>

        <div v-else-if="!visibleLayout.length" class="customers-shadow rounded-lg p-10 text-center">
            <p class="text-slate-500 mb-4">{{ t('home_dashboard.empty') }}</p>
            <button type="button" class="button-primary" @click="editing = true; showCatalog = true">
                <Icon name="fa6-solid:plus" />&nbsp;{{ t('home_dashboard.add_card') }}
            </button>
        </div>

        <Draggable v-else v-model="layout" item-key="id" handle=".card-handle" :disabled="!editing"
            class="grid grid-cols-6 gap-4 items-stretch" ghost-class="opacity-40" @end="scheduleSave">
            <template #item="{ element }">
                <div class="min-w-0" :class="DASHBOARD_SIZE_CLASSES[element.size] || DASHBOARD_SIZE_CLASSES.md">
                    <component :is="CARD_COMPONENTS[element.key]" :item="element" :editing="editing"
                        @configure="configItem = element" @remove="removeCard(element)" />
                </div>
            </template>
        </Draggable>

        <DashboardCardCatalogModal v-model:open="showCatalog" :cards="availableCards" :used-keys="usedKeys" @add="addCard" />
        <DashboardCardConfigModal v-model:open="showConfig" :item="configItem" :card="configCard" @save="updateCard" />
    </div>
</template>
