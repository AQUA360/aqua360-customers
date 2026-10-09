<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { formatDateTime } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import H1 from '~/components/atoms/H1.vue';
import InputDate from '~/components/atoms/InputDate.vue';

const { t } = useI18n();
const toast = useToast();
const route = useRoute();
const { $DailyActivityApiService, $UserApiService, $apiManager, $DocumentManagerApiService } = useNuxtApp();

const today = () => new Date().toLocaleDateString('sv-SE'); // 'YYYY-MM-DD' en horari local

const dateFrom = ref(route.query.date || today());
const dateTo = ref(route.query.date || today());

// null = jo mateix, 'all' = tots els usuaris actius, un id = aquell usuari.
// Qui no té permís de veure usuaris només pot deixar-ho a null: el backend
// respon 403 si demana qualsevol altra cosa.
const selectedUser = ref(route.query.user_id || null);
const canViewOtherUsers = ref(false);
const users = ref([]);
const loadingUsers = ref(false);
// Comptes tècnics que el backend no deixa consultar (l'activitat que hi queda
// registrada és de processos automàtics). Els treu del selector; la llista la
// decideix el backend i arriba a cada resposta del resum.
const excludedUsernames = ref([]);

const activity = ref(null);
const loading = ref(false);
const loadError = ref(null);

const isRangeValid = computed(() => !!dateFrom.value && !!dateTo.value && dateFrom.value <= dateTo.value);

const selectableUsers = computed(() =>
  users.value.filter(user => !excludedUsernames.value.includes(user.username))
);

const userOptions = computed(() => {
  const options = [{ label: t('daily_activity_block.my_activity'), code: null }];
  if (canViewOtherUsers.value) {
    options.push({ label: t('daily_activity_block.all_users'), code: 'all' });
    selectableUsers.value.forEach(user => {
      const name = [user.first_name, user.last_name].filter(Boolean).join(' ');
      options.push({ label: name ? `${name} (${user.username})` : user.username, code: user.id });
    });
  }
  return options;
});

const selectedUserOption = computed(() =>
  userOptions.value.find(option => String(option.code) === String(selectedUser.value)) || userOptions.value[0]
);

const loadUsers = async () => {
  loadingUsers.value = true;
  try {
    // El desplegable ha de portar tots els usuaris, i el llistat va paginat.
    let page = 1;
    const collected = [];
    while (page <= 20) {
      const response = await $UserApiService.getAll('', page);
      collected.push(...(response.results || []));
      if (!response.next) break;
      page += 1;
    }
    users.value = collected;
  } catch (error) {
    // Sense permís de veure usuaris el llistat respon 403: el selector es queda
    // només amb "La meva activitat", que és el que aquest usuari pot consultar.
    console.error(error);
  } finally {
    loadingUsers.value = false;
  }
};

const getActivity = async () => {
  if (!isRangeValid.value) return;
  loading.value = true;
  loadError.value = null;
  try {
    const response = await $DailyActivityApiService.getSummary({
      dateFrom: dateFrom.value,
      dateTo: dateTo.value,
      userIds: selectedUser.value,
    });
    activity.value = response;
    excludedUsernames.value = response.excluded_usernames || [];
    if (response.can_view_other_users && !canViewOtherUsers.value) {
      canViewOtherUsers.value = true;
      loadUsers();
    }
  } catch (error) {
    console.error(error);
    loadError.value = error;
    activity.value = null;
  } finally {
    loading.value = false;
  }
};

const updateUser = (option) => {
  selectedUser.value = option ? option.code : null;
  getActivity();
};

// --- Generació de l'Excel (mateix patró que la resta d'informes: task_id + polling) ---
const generating = ref(false);
const reportTaskId = ref(null);

const generateReport = async () => {
  if (!isRangeValid.value) return;
  generating.value = true;
  try {
    const response = await $DailyActivityApiService.generateReport({
      date_from: dateFrom.value,
      date_to: dateTo.value,
      // null = jo mateix (el backend hi posa l'usuari de la sessió); 'all' el resol
      // com "tots els usuaris actius", sempre que qui ho demana en tingui permís.
      user_ids: selectedUser.value === null ? null : [selectedUser.value],
      name: t('daily_activity_block.report_name'),
    });
    if (response && response.task_id) {
      reportTaskId.value = response.task_id;
    }
  } catch (error) {
    console.error(error);
    toast.error(t('reports_block.report_generation_failed', { name: t('daily_activity_block.report_name') }));
  } finally {
    generating.value = false;
  }
};

const downloadReport = async () => {
  try {
    const response = await $apiManager.checkTask(reportTaskId.value);
    if (response && response.result && response.result.document_id) {
      const file = await $DocumentManagerApiService.viewDocument(response.result.document_id);
      const link = document.createElement('a');
      const fileUrl = URL.createObjectURL(file);
      link.href = fileUrl;
      link.download = `activitat_${dateFrom.value}_${dateTo.value}.xlsx`;
      link.click();
      setTimeout(() => window.URL.revokeObjectURL(fileUrl), 250);
    } else if (response && response.state === 'FAILURE') {
      toast.error(t('reports_block.report_generation_failed', { name: t('daily_activity_block.report_name') }));
    }
  } catch (error) {
    console.error(error);
  } finally {
    reportTaskId.value = null;
  }
};

// --- Filtre de categoria sobre la cronologia ---
const activeCategory = ref(null);

const filteredTimeline = computed(() => {
  if (!activity.value) return [];
  if (!activeCategory.value) return activity.value.timeline;
  return activity.value.timeline.filter(entry => entry.category === activeCategory.value);
});

const CATEGORY_ICONS = {
  collections: 'fa6-solid:cash-register',
  orders: 'fa6-solid:screwdriver-wrench',
  contracts: 'fa6-solid:file-signature',
  billing: 'fa6-solid:file-invoice',
  readings: 'fa6-solid:gauge',
  communications: 'fa6-solid:envelope',
  claims: 'fa6-solid:triangle-exclamation',
  service: 'fa6-solid:faucet',
  pricing: 'fa6-solid:tags',
  other: 'fa6-solid:ellipsis',
};

const categoryIcon = (key) => CATEGORY_ICONS[key] || 'fa6-solid:circle-dot';

/**
 * Import que es mostra al costat del comptador d'una categoria. Als cobraments es
 * mostra el cobrat (el net, amb devolucions, és negatiu i al costat del títol
 * "Cobraments" enganya); a la resta de categories amb import només hi ha el net.
 */
const categoryAmount = (category) => {
  const amounts = category.amounts || {};
  if (Number(amounts.charged)) return amounts.charged;
  if (Number(amounts.net)) return amounts.net;
  return null;
};

/**
 * La part de les remeses enviades que no s'ha acabat cobrant (retornada, abonada o
 * en compromís de pagament). És la diferència entre l'import remès i el cobrat per
 * remesa, i és el motiu pel qual el cobrat no és "remès + cobraments manuals".
 */
const notChargedFromRemittances = computed(() => {
  if (!activity.value) return 0;
  const remitted = Number(activity.value.totals.collections_remitted) || 0;
  const charged = Number(activity.value.totals.collections_charged_remittances) || 0;
  const difference = remitted - charged;
  return difference > 0 ? difference : 0;
});

const setPreset = (preset) => {
  const now = new Date();
  if (preset === 'today') {
    dateFrom.value = today();
    dateTo.value = today();
  } else if (preset === 'yesterday') {
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    const value = yesterday.toLocaleDateString('sv-SE');
    dateFrom.value = value;
    dateTo.value = value;
  } else if (preset === 'week') {
    const from = new Date(now);
    from.setDate(from.getDate() - 6);
    dateFrom.value = from.toLocaleDateString('sv-SE');
    dateTo.value = today();
  }
  getActivity();
};

const isSingleDay = computed(() => dateFrom.value === dateTo.value);

onMounted(() => {
  getActivity();
  loadUsers();
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <div class="flex justify-between items-start mb-2 gap-4">
      <div>
        <H1 class="mb-2">{{ $t('daily_activity_block.title') }}</H1>
        <p class="text-slate-500 max-w-2xl">{{ $t('daily_activity_block.description') }}</p>
      </div>
      <NuxtLink to="/billing/reports/" class="button-secondary shrink-0">{{ $t('common.reports') }}</NuxtLink>
    </div>

    <!-- Filtres -->
    <div class="border border-slate-200 rounded-md p-4 mb-6">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <InputDate v-model="dateFrom" :label="$t('daily_activity_block.date_from')" required
          :invalid="!isRangeValid" />
        <InputDate v-model="dateTo" :label="$t('daily_activity_block.date_to')" required :start-date="dateFrom"
          :invalid="!isRangeValid" />
        <div class="input-group mb-4">
          <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('user') }}</label>
          <v-select class="block w-full custom-select bg-white rounded" :model-value="selectedUserOption"
            :clearable="false" :loading="loadingUsers" :options="userOptions"
            @update:modelValue="updateUser" />
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <button type="button" class="button-default" @click="setPreset('today')">{{ $t('daily_activity_block.preset_today') }}</button>
        <button type="button" class="button-default" @click="setPreset('yesterday')">{{ $t('daily_activity_block.preset_yesterday') }}</button>
        <button type="button" class="button-default" @click="setPreset('week')">{{ $t('daily_activity_block.preset_last_week') }}</button>
        <span class="grow"></span>
        <button type="button" class="button-default flex items-center gap-2" :disabled="!isRangeValid || loading"
          @click="getActivity">
          <Icon :name="loading ? 'fa6-solid:spinner' : 'fa6-solid:magnifying-glass'" :class="{ 'animate-spin': loading }" />
          {{ $t('common.search') }}
        </button>
        <button type="button" class="button-primary flex items-center gap-2"
          :disabled="!isRangeValid || generating || !!reportTaskId" @click="generateReport">
          <Icon :name="generating ? 'fa6-solid:spinner' : 'fa6-solid:file-excel'" :class="{ 'animate-spin': generating }" />
          {{ $t('reports_block.generate_report') }}
        </button>
        <AtomsProcessColorBadge v-if="reportTaskId" class="w-fit" @refresh="downloadReport"
          :value="t('common.loading')" :color="'green'" :taskId="reportTaskId" />
      </div>
    </div>

    <div v-if="!isRangeValid" class="text-sm text-amber-600 flex items-center gap-2 mb-4">
      <Icon name="fa6-solid:triangle-exclamation" />
      {{ $t('daily_activity_block.invalid_range') }}
    </div>

    <div v-if="loading" class="flex justify-center py-16">
      <AtomsSkeleton class="w-full" :height="8" :has_icon="false" />
    </div>

    <div v-else-if="loadError" class="border border-red-200 bg-red-50 rounded-md p-4 text-sm text-red-700">
      {{ $t('daily_activity_block.load_error') }}
    </div>

    <template v-else-if="activity">
      <!-- Totals -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 mb-6">
        <div class="customers-shadow rounded-lg bg-white p-4">
          <div class="text-xs font-semibold text-slate-500 uppercase mb-1">{{ $t('daily_activity_block.total_actions') }}</div>
          <div class="text-2xl font-bold text-sky-700">{{ activity.totals.total_actions }}</div>
        </div>

        <!-- Cobraments i devolucions en dos blocs separats: no són la mateixa cosa i
             un dia pot tenir només devolucions de remeses cobrades un altre dia. A
             tots dos la xifra gran és l'import, no el nombre de moviments: el
             cobrament massiu es fa per remesa (una acció, milers de rebuts). -->
        <div class="customers-shadow rounded-lg bg-white p-4">
          <div class="text-xs font-semibold text-slate-500 uppercase mb-1">{{ $t('daily_activity_block.collections') }}</div>
          <div class="text-xl font-bold text-slate-800">
            {{ formatMoneyWithCurrency(activity.totals.collections_charged) }}
          </div>
          <!-- Les dues parts de l'import, amb el seu import cadascuna: el cobrat NO és
               el remès més els manuals, perquè part de la remesa acaba retornada,
               abonada o en compromís de pagament i no s'ha cobrat mai. Ensenyar el
               remès i el que se n'ha cobrat de veritat fa que la suma es pugui seguir. -->
          <div class="text-xs mt-1 space-y-0.5">
            <div v-if="activity.totals.remittances_sent_count" class="text-slate-600">
              {{ $t('daily_activity_block.remittances_sent') }}: {{ activity.totals.remittances_sent_count }} ·
              {{ formatMoneyWithCurrency(activity.totals.collections_charged_remittances) }}
            </div>
            <div v-if="activity.totals.remittances_sent_count" class="text-slate-400 pl-2">
              {{ $t('daily_activity_block.remitted') }}: {{ formatMoneyWithCurrency(activity.totals.collections_remitted) }}
              <span v-if="notChargedFromRemittances">
                ({{ $t('daily_activity_block.not_charged') }} {{ formatMoneyWithCurrency(notChargedFromRemittances) }})
              </span>
            </div>
            <div v-if="activity.totals.collections_count" class="text-slate-600">
              {{ $t('daily_activity_block.manual_collections') }}: {{ activity.totals.collections_count }} ·
              {{ formatMoneyWithCurrency(activity.totals.collections_charged_manual) }}
            </div>
            <div v-if="!activity.totals.remittances_sent_count && !activity.totals.collections_count"
              class="text-slate-400">
              {{ $t('daily_activity_block.no_collections') }}
            </div>
          </div>
        </div>

        <div class="customers-shadow rounded-lg bg-white p-4">
          <div class="text-xs font-semibold text-slate-500 uppercase mb-1">{{ $t('daily_activity_block.returns') }}</div>
          <div class="text-xl font-bold" :class="activity.totals.returns_count ? 'text-red-600' : 'text-slate-800'">
            {{ formatMoneyWithCurrency(activity.totals.collections_returned) }}
          </div>
          <div class="text-xs mt-1 space-y-0.5">
            <div v-if="activity.totals.returns_count" class="text-slate-600">
              {{ $t('daily_activity_block.returned_receipts') }}: {{ activity.totals.returns_count }}
            </div>
            <div v-if="activity.totals.remittance_returns_count" class="text-slate-600">
              {{ $t('daily_activity_block.return_files') }}: {{ activity.totals.remittance_returns_count }}
            </div>
            <div v-if="activity.totals.returns_count && Number(activity.totals.collections_charged)"
              class="text-slate-500">
              {{ $t('daily_activity_block.net') }}: {{ formatMoneyWithCurrency(activity.totals.collections_net) }}
            </div>
            <div v-if="!activity.totals.returns_count && !activity.totals.remittance_returns_count"
              class="text-slate-400">
              {{ $t('daily_activity_block.no_returns') }}
            </div>
          </div>
        </div>

        <div class="customers-shadow rounded-lg bg-white p-4">
          <div class="text-xs font-semibold text-slate-500 uppercase mb-1">{{ $t('daily_activity_block.new_orders') }}</div>
          <div class="text-2xl font-bold text-slate-800">{{ activity.totals.orders_count }}</div>
        </div>
        <div class="customers-shadow rounded-lg bg-white p-4">
          <div class="text-xs font-semibold text-slate-500 uppercase mb-1">{{ $t('daily_activity_block.contract_managements') }}</div>
          <div class="text-2xl font-bold text-slate-800">{{ activity.totals.contracts_count }}</div>
        </div>
      </div>

      <div v-if="activity.totals.total_actions === 0"
        class="border border-slate-200 rounded-md p-10 text-center text-slate-500">
        <Icon name="fa6-solid:mug-hot" class="text-3xl text-slate-300 mb-3" />
        <p>{{ isSingleDay ? $t('daily_activity_block.empty_day') : $t('daily_activity_block.empty_range') }}</p>
      </div>

      <template v-else>
        <!-- Desglossament per categoria -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
          <div v-for="category in activity.categories" :key="category.key"
            class="border border-slate-200 rounded-md overflow-hidden">
            <button type="button"
              class="w-full flex items-center justify-between gap-3 px-4 py-3 bg-slate-50 hover:bg-slate-100 text-left"
              :class="{ 'bg-sky-50': activeCategory === category.key }"
              @click="activeCategory = activeCategory === category.key ? null : category.key">
              <span class="flex items-center gap-2 font-semibold text-slate-700 min-w-0">
                <Icon :name="categoryIcon(category.key)" class="text-slate-400 shrink-0" />
                <span class="truncate">{{ category.label }}</span>
              </span>
              <span class="flex items-center gap-2 shrink-0">
                <span v-if="categoryAmount(category) !== null" class="text-xs text-slate-500">
                  {{ formatMoneyWithCurrency(categoryAmount(category)) }}
                </span>
                <span class="rounded-full bg-slate-200 text-slate-700 px-2 py-0.5 text-sm font-semibold">
                  {{ category.count }}
                </span>
              </span>
            </button>
            <div class="divide-y divide-slate-100">
              <div v-for="source in category.sources" :key="source.key"
                class="flex items-center justify-between gap-3 px-4 py-2 text-sm">
                <span class="text-slate-600 truncate">{{ source.label }}</span>
                <span class="font-medium text-slate-800 shrink-0">{{ source.count }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Repartiment per usuari (només quan l'informe agrupa més d'un usuari) -->
        <div v-if="activity.by_user.length > 1" class="border border-slate-200 rounded-md mb-6 overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-slate-50">
              <tr class="text-left text-slate-500">
                <th class="p-2">{{ $t('user') }}</th>
                <th class="p-2 text-right">{{ $t('daily_activity_block.total_actions') }}</th>
                <th v-for="category in activity.categories" :key="category.key" class="p-2 text-right whitespace-nowrap">
                  {{ category.label }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in activity.by_user" :key="user.id" class="border-t border-slate-100"
                :class="{ 'text-slate-400': user.total === 0 }">
                <td class="p-2 truncate">{{ user.name || user.username }}</td>
                <td class="p-2 text-right font-semibold">{{ user.total }}</td>
                <td v-for="category in activity.categories" :key="category.key" class="p-2 text-right">
                  {{ user.categories[category.key] || 0 }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Cronologia -->
        <div class="flex items-center justify-between gap-3 mb-2">
          <h2 class="font-semibold text-slate-700 flex items-center gap-2">
            <Icon name="fa6-solid:clock-rotate-left" class="text-slate-400" />
            {{ $t('daily_activity_block.timeline') }}
          </h2>
          <button v-if="activeCategory" type="button" class="text-sm text-sky-600 hover:underline"
            @click="activeCategory = null">
            {{ $t('daily_activity_block.clear_category_filter') }}
          </button>
        </div>

        <p v-if="activity.timeline_truncated" class="text-xs text-amber-600 mb-2 flex items-center gap-1">
          <Icon name="fa6-solid:triangle-exclamation" />
          {{ $t('daily_activity_block.timeline_truncated') }}
        </p>

        <div class="border border-slate-200 rounded-md overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-slate-50 sticky top-0">
              <tr class="text-left text-slate-500">
                <th class="p-2 whitespace-nowrap">{{ $t('common.date') }}</th>
                <th v-if="activity.users.length > 1" class="p-2">{{ $t('user') }}</th>
                <th class="p-2">{{ $t('daily_activity_block.action') }}</th>
                <th class="p-2">{{ $t('daily_activity_block.reference') }}</th>
                <th class="p-2">{{ $t('contract') }}</th>
                <th class="p-2">{{ $t('daily_activity_block.detail') }}</th>
                <th class="p-2 text-right whitespace-nowrap">{{ $t('common.amount') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(entry, index) in filteredTimeline" :key="index" class="border-t border-slate-100">
                <td class="p-2 whitespace-nowrap text-slate-500">{{ formatDateTime(entry.occurred_at) }}</td>
                <td v-if="activity.users.length > 1" class="p-2 truncate">{{ entry.user || '-' }}</td>
                <td class="p-2">
                  <span class="flex items-center gap-2">
                    <Icon :name="categoryIcon(entry.category)" class="text-slate-300 shrink-0" />
                    <span class="truncate">{{ entry.source_label }}</span>
                  </span>
                </td>
                <td class="p-2 font-medium truncate">{{ entry.reference || '-' }}</td>
                <td class="p-2 truncate">{{ entry.contract || '-' }}</td>
                <td class="p-2 text-slate-500">{{ entry.detail || '-' }}</td>
                <td class="p-2 text-right whitespace-nowrap"
                  :class="entry.amount < 0 ? 'text-red-600' : 'text-slate-700'">
                  {{ entry.amount === null || entry.amount === undefined ? '' : formatMoneyWithCurrency(entry.amount) }}
                </td>
              </tr>
              <tr v-if="filteredTimeline.length === 0">
                <td colspan="7" class="p-4 text-center text-slate-400">{{ $t('common.no_results') }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
    </template>
  </div>
</template>
