<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { usePermissions } from '~/middleware/permission';
import { formatDate } from '~/utils/date';

const { t } = useI18n();
const toast = useToast();
const {
  $ConfigProjectApiService,
  $ConfiglistApiService,
  $VariableTypeApiService,
  $ProductApiService,
  $PriceRateApiService,
  $BillingRangeApiService,
  $LineItemTypeApiService,
  $ArticleCodeApiService,
  $ContractUseAcaApiService,
} = useNuxtApp();

const { permissions, loading: permissionsLoading } = usePermissions();

const ACA_TOKENS = [
  'aca_cs_token',
  'token_product_aca',
  'token_price_rate_aca_dom',
  'contract_use_aca_mun_tokens',
  'contract_use_aca_ind_tokens',
  'contract_use_aca_dom_tokens',
  'contract_use_aca_gan_tokens',
  'contract_use_aca_dir_variable_token',
  'contract_keeper_use_type_token',
];

const VARIABLE_TYPE_TOKENS = new Set(['aca_cs_token', 'contract_use_aca_dir_variable_token']);
const CONTRACT_USE_TYPE_TOKENS = new Set(['contract_keeper_use_type_token']);
const PRODUCT_TOKEN = 'token_product_aca';
const PRICE_RATE_TOKENS = new Set([
  'token_price_rate_aca_dom',
  'contract_use_aca_mun_tokens',
  'contract_use_aca_ind_tokens',
  'contract_use_aca_dom_tokens',
  'contract_use_aca_gan_tokens',
]);

const SKIP_REASON_KEYS = {
  no_canon_price_rate: 'settings_block.aca_skip_reason_no_canon_price_rate',
  token_no_match: 'settings_block.aca_skip_reason_token_no_match',
  already_correct: 'settings_block.aca_skip_reason_already_correct',
  no_price_rates: 'settings_block.aca_skip_reason_no_price_rates',
};

const pending = ref(true);
const savingConfig = ref(false);
const loadingLineItems = ref(false);
const savingLineItemId = ref(null);

const useAca = ref(false);
const configRows = ref([]);
const configValues = ref({});

const variableTypes = ref([]);
const contractUseTypes = ref([]);
const products = ref([]);
const priceRates = ref([]);
const lineItems = ref([]);
const lineItemArticles = ref({});
const articles = ref([]);

const contractUseAcaStats = ref(null);
const loadingContractUseAcaStats = ref(false);
const runningDryRun = ref(false);
const runningFill = ref(false);
const fillTaskProgress = ref(0);
const updateAllContracts = ref(false);
const fillResult = ref(null);
const SUPPORTS_UPDATE_ALL_CONTRACTS = false;
let fillTaskInterval = null;
let fillTaskPollInFlight = false;

const isFillResultPayload = (value) =>
  value && typeof value === 'object' && ('updated_count' in value || 'total_contracts' in value);

const parseTaskProgress = (payload) => {
  if (!payload || typeof payload !== 'object') {
    return { state: '', result: null, percent: 0 };
  }

  if (isFillResultPayload(payload) && !('state' in payload) && !('status' in payload)) {
    return { state: 'SUCCESS', result: payload, percent: 100 };
  }

  const rawState = payload.state ?? payload.status;
  const state = typeof rawState === 'string' ? rawState.trim().toUpperCase() : '';
  const result = payload.result ?? null;

  if (isFillResultPayload(result)) {
    return { state: state || 'SUCCESS', result, percent: payload.percent ?? 100 };
  }

  return { state, result, percent: payload.percent ?? 0 };
};

const isTaskSuccessState = (state) => ['SUCCESS', 'COMPLETED', 'COMPLETE', 'SUCCEEDED'].includes(state);
const isTaskFailureState = (state) => ['FAILURE', 'FAILED', 'REVOKED'].includes(state);

const checkFillTaskProgress = async (taskId) => {
  const config = useRuntimeConfig();
  const authToken = localStorage.getItem('auth_token') || '';
  return await $fetch(`${config.public.apiHost}/task-progress/${taskId}`, {
    method: 'GET',
    headers: { Authorization: `Token ${authToken}` },
  });
};

const completeFillTask = async (result) => {
  if (handleFillSkipped(result)) {
    runningFill.value = false;
    return;
  }
  applyFillResult(result);
  toast.success(t('settings_block.aca_fill_success'));
  try {
    await loadContractUseAcaStats();
  } catch (error) {
    console.error(error);
  }
};

const failFillTask = (result, raw) => {
  clearFillTaskInterval();
  runningFill.value = false;

  if (isFillResultPayload(result)) {
    applyFillResult(result);
    toast.success(t('settings_block.aca_fill_success'));
    loadContractUseAcaStats().catch(console.error);
    return;
  }

  const message =
    (typeof raw?.error === 'string' && raw.error.trim())
    || (typeof result === 'string' && result.trim())
    || t('common.error');
  toast.error(message);
};

const pollFillTaskOnce = async (taskId) => {
  if (fillTaskPollInFlight) return;
  fillTaskPollInFlight = true;
  try {
    const raw = await checkFillTaskProgress(taskId);
    const { state, result, percent } = parseTaskProgress(raw);
    fillTaskProgress.value = percent ?? fillTaskProgress.value;

    if (isTaskSuccessState(state)) {
      clearFillTaskInterval();
      runningFill.value = false;
      await completeFillTask(result ?? raw);
    } else if (isTaskFailureState(state)) {
      failFillTask(result, raw);
    }
  } catch (error) {
    console.error('Error polling fill task:', error);
    if (error?.response?.status === 401) {
      clearFillTaskInterval();
      runningFill.value = false;
      const { $apiManager } = useNuxtApp();
      const message = error?.response?._data?.detail || error?.data?.detail || error?.response?._data?.message || error?.data?.message || error?.message;
      await $apiManager.handleUnauthorized(message);
    }
  } finally {
    fillTaskPollInFlight = false;
  }
};

const canViewContractUseAca = computed(() => !!permissions.value?.permissions?.view_contract);
const canChangeContractUseAca = computed(() => !!permissions.value?.permissions?.change_contract);
const hasPendingUseAca = computed(() => (contractUseAcaStats.value?.pending_use_aca ?? 0) > 0);

const skipReasonEntries = computed(() => {
  const reasons = fillResult.value?.skipped_reasons;
  if (!reasons) return [];
  return Object.entries(reasons)
    .filter(([, count]) => count > 0)
    .map(([key, count]) => ({
      key,
      count,
      label: SKIP_REASON_KEYS[key] ? t(SKIP_REASON_KEYS[key]) : key,
      examples: fillResult.value?.skipped_examples?.[key] ?? [],
    }));
});

const resolveConfigRawValue = (raw) => {
  if (raw === null || raw === undefined) return raw;
  if (typeof raw === 'string') {
    const trimmed = raw.trim();
    if (!trimmed) return raw;
    try {
      return JSON.parse(trimmed);
    } catch {
      return raw;
    }
  }
  return raw;
};

const parseConfigBool = (value) => {
  const resolved = resolveConfigRawValue(value);
  return resolved === true
    || resolved === 'True'
    || resolved === 'true'
    || resolved === 1
    || resolved === '1';
};

const normalizeConfigValue = (value) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value;
  return String(value);
};

const selectedProduct = computed(() => {
  const token = configValues.value[PRODUCT_TOKEN];
  if (!token) return null;
  return products.value.find((p) => p.token === token) ?? null;
});

const canShowLineItems = computed(() => useAca.value && !!selectedProduct.value);

const getFieldType = (token) => {
  if (VARIABLE_TYPE_TOKENS.has(token)) return 'variable_type';
  if (CONTRACT_USE_TYPE_TOKENS.has(token)) return 'contract_use_type';
  if (token === PRODUCT_TOKEN) return 'product';
  if (PRICE_RATE_TOKENS.has(token)) return 'price_rate';
  return 'text';
};

const buildConfigRows = (allConfigs) => {
  const byToken = {};
  allConfigs.forEach((item) => {
    byToken[item.token] = item;
  });

  configRows.value = ACA_TOKENS.map((token) => ({
    token,
    name: byToken[token]?.name ?? token,
  }));

  const values = {};
  ACA_TOKENS.forEach((token) => {
    values[token] = normalizeConfigValue(byToken[token]?.value);
  });
  configValues.value = values;

  const useAcaConfig = byToken.uses_aca;
  useAca.value = useAcaConfig != null ? parseConfigBool(useAcaConfig.value) : false;
};

const ensureUseAcaConfig = async (allConfigs) => {
  if (allConfigs?.some((item) => item.token === 'uses_aca')) return allConfigs;

  try {
    const filtered = await $ConfigProjectApiService.getAll('uses_aca');
    if (!Array.isArray(filtered) || !filtered.length) return allConfigs;

    const merged = [...(allConfigs ?? [])];
    filtered.forEach((item) => {
      if (!merged.some((existing) => existing.token === item.token)) {
        merged.push(item);
      }
    });
    return merged;
  } catch (error) {
    console.error(error);
    return allConfigs;
  }
};

const loadVariableTypes = async () => {
  const response = await $VariableTypeApiService.getAllUnpaginated();
  variableTypes.value = Array.isArray(response) ? response : [];
};

const loadContractUseTypes = async () => {
  const all = [];
  let page = 1;
  let hasNext = true;

  while (hasNext) {
    const response = await $ConfiglistApiService.getAll('contract/contract-use-type', page);
    all.push(...(response?.results ?? []));
    hasNext = !!response?.next;
    page += 1;
  }

  contractUseTypes.value = all;
};

const loadProducts = async () => {
  const response = await $ProductApiService.getAll('', [], 1, null, false, null, [], true);
  products.value = Array.isArray(response) ? response : [];
};

const loadPriceRates = async (productId) => {
  if (!productId) {
    priceRates.value = [];
    return;
  }
  const response = await $PriceRateApiService.getAll('', [], 1, null, false, productId);
  priceRates.value = response?.results ?? [];
};

const loadArticles = async () => {
  const all = [];
  let page = 1;
  let hasNext = true;

  while (hasNext) {
    const response = await $ArticleCodeApiService.getAll('', [], page, 'token', false);
    all.push(...(response?.results ?? []));
    hasNext = !!response?.next;
    page += 1;
  }

  articles.value = all;
};

const clearFillTaskInterval = () => {
  if (fillTaskInterval) {
    clearInterval(fillTaskInterval);
    fillTaskInterval = null;
  }
};

const loadContractUseAcaStats = async () => {
  if (!useAca.value || !canViewContractUseAca.value) {
    contractUseAcaStats.value = null;
    return;
  }

  loadingContractUseAcaStats.value = true;
  try {
    contractUseAcaStats.value = await $ContractUseAcaApiService.getStats();
  } catch (error) {
    console.error(error);
    contractUseAcaStats.value = null;
  } finally {
    loadingContractUseAcaStats.value = false;
  }
};

const applyFillResult = (result) => {
  fillResult.value = result ?? null;
};

const handleFillSkipped = (result) => {
  if (!result?.skipped) return false;
  if (result.reason === 'uses_aca_disabled') {
    toast.error(t('settings_block.aca_fill_skipped_disabled'));
  }
  applyFillResult(result);
  return true;
};

const pollFillTask = (taskId) => {
  clearFillTaskInterval();
  fillTaskProgress.value = 0;
  runningFill.value = true;
  pollFillTaskOnce(taskId);
  fillTaskInterval = setInterval(() => pollFillTaskOnce(taskId), 2000);
};

const buildFillPayload = ({ dryRun = false, asyncRun = false } = {}) => {
  if (dryRun) return { dry_run: true };
  if (asyncRun) return { async: true };
  return {};
};

const runDryRun = async () => {
  runningDryRun.value = true;
  fillResult.value = null;
  try {
    const payload = buildFillPayload({ dryRun: true });
    if (SUPPORTS_UPDATE_ALL_CONTRACTS && updateAllContracts.value) {
      payload.update_all_contracts = true;
    }
    const result = await $ContractUseAcaApiService.fill(payload);
    if (handleFillSkipped(result)) return;
    applyFillResult(result);
  } catch (error) {
    console.error(error);
  } finally {
    runningDryRun.value = false;
  }
};

const runFill = async () => {
  const confirmMessage = (SUPPORTS_UPDATE_ALL_CONTRACTS && updateAllContracts.value)
    ? t('settings_block.aca_confirm_fill_all')
    : t('settings_block.aca_confirm_fill');
  if (!window.confirm(confirmMessage)) return;

  runningFill.value = true;
  fillResult.value = null;
  try {
    const payload = buildFillPayload({ asyncRun: true });
    if (SUPPORTS_UPDATE_ALL_CONTRACTS && updateAllContracts.value) {
      payload.update_all_contracts = true;
    }
    const result = await $ContractUseAcaApiService.fill(payload);

    if (handleFillSkipped(result)) {
      runningFill.value = false;
      return;
    }

    if (result?.task_id) {
      pollFillTask(result.task_id);
      return;
    }

    applyFillResult(result);
    toast.success(t('settings_block.aca_fill_success'));
    await loadContractUseAcaStats();
  } catch (error) {
    console.error(error);
  } finally {
    if (!fillTaskInterval) {
      runningFill.value = false;
    }
  }
};

const loadLineItems = async () => {
  if (!selectedProduct.value?.id) {
    lineItems.value = [];
    lineItemArticles.value = {};
    return;
  }

  loadingLineItems.value = true;
  try {
    const priceRatesResponse = await $PriceRateApiService.getAll(
      '',
      [],
      1,
      null,
      false,
      selectedProduct.value.id,
    );
    const productPriceRates = priceRatesResponse?.results ?? [];

    const rowsNested = await Promise.all(
      productPriceRates.map(async (priceRate) => {
        const activeBillingRangeId = priceRate.billing_range_active?.id ?? null;
        const billingRangesResponse = await $BillingRangeApiService.getAll(
          '',
          [],
          1,
          null,
          false,
          priceRate.id,
        );
        const billingRanges = billingRangesResponse?.results ?? [];

        const rangeRows = await Promise.all(
          billingRanges.map(async (billingRange) => {
            const lineItemsResponse = await $LineItemTypeApiService.getByBillingRange(billingRange.id);
            const lineItemTypes = lineItemsResponse?.results ?? [];

            return lineItemTypes.map((lineItem) => ({
              ...lineItem,
              price_rate_id: priceRate.id,
              price_rate_name: priceRate.name,
              price_rate_token: priceRate.token,
              billing_range_id: billingRange.id,
              billing_range_name: billingRange.name,
              billing_range_token: billingRange.token,
              billing_range_start: billingRange.start,
              billing_range_end: billingRange.end,
              is_active_billing_range: billingRange.id === activeBillingRangeId,
            }));
          }),
        );

        return rangeRows.flat();
      }),
    );

    lineItems.value = rowsNested.flat();
    const articleMap = {};
    lineItems.value.forEach((item) => {
      articleMap[item.id] = item.article?.id ?? '';
    });
    lineItemArticles.value = articleMap;
  } catch (error) {
    console.error(error);
    lineItems.value = [];
    lineItemArticles.value = {};
  } finally {
    loadingLineItems.value = false;
  }
};

const loadData = async () => {
  pending.value = true;
  try {
    let allConfigs = await $ConfigProjectApiService.getAll();
    allConfigs = await ensureUseAcaConfig(allConfigs);
    await Promise.all([
      loadVariableTypes(),
      loadContractUseTypes(),
      loadProducts(),
      loadArticles(),
    ]);
    buildConfigRows(allConfigs);
    await loadPriceRates(selectedProduct.value?.id);
    if (canShowLineItems.value) {
      await loadLineItems();
    }
    await loadContractUseAcaStats();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    pending.value = false;
  }
};

watch(
  () => configValues.value[PRODUCT_TOKEN],
  async (newToken, oldToken) => {
    if (pending.value || newToken === oldToken) return;

    const product = products.value.find((p) => p.token === newToken);
    await loadPriceRates(product?.id ?? null);

    if (product?.id) {
      PRICE_RATE_TOKENS.forEach((token) => {
        const current = configValues.value[token];
        if (current && !priceRates.value.some((pr) => pr.token === current)) {
          configValues.value[token] = '';
        }
      });
      if (useAca.value) {
        await loadLineItems();
      }
    } else {
      lineItems.value = [];
      lineItemArticles.value = {};
    }
  }
);

watch(useAca, async (enabled) => {
  if (pending.value) return;
  if (!enabled) {
    contractUseAcaStats.value = null;
    fillResult.value = null;
    return;
  }
  await loadContractUseAcaStats();
  if (selectedProduct.value) {
    await loadLineItems();
  }
});

const configPayload = () => {
  const items = [{ token: 'uses_aca', value: useAca.value }];
  ACA_TOKENS.forEach((token) => {
    items.push({
      token,
      value: configValues.value[token] || '',
    });
  });
  return items;
};

const saveConfig = async () => {
  savingConfig.value = true;
  try {
    await $ConfigProjectApiService.bulkUpdateValues(configPayload());
    toast.success(t('common.correct_save'));
    if (useAca.value && selectedProduct.value) {
      await loadLineItems();
    }
    await loadContractUseAcaStats();
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    savingConfig.value = false;
  }
};

const saveLineItemArticle = async (lineItem) => {
  const articleId = lineItemArticles.value[lineItem.id];
  if (!articleId) {
    toast.error(t('settings_block.aca_select_article_code'));
    return;
  }

  savingLineItemId.value = lineItem.id;
  try {
    await $LineItemTypeApiService.saveArticle({
      id: lineItem.id,
      code: lineItem.code,
      line_item_type_id: lineItem.id,
      stretch_id: null,
      is_fix: false,
      article_id: articleId,
    });
    toast.success(t('common.correct_save'));
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  } finally {
    savingLineItemId.value = null;
  }
};

onMounted(() => {
  loadData();
});

onBeforeUnmount(() => {
  clearFillTaskInterval();
});
</script>

<template>
  <div class="pb-6 px-4">
    <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
      <H1 class="!mb-0">{{ t('settings_block.config_aca') }}</H1>
      <NuxtLink
        to="/settings/"
        class="text-sm text-sky-500 underline hover:no-underline"
      >
        {{ t('common.settings') }}
      </NuxtLink>
    </div>

    <div v-if="permissionsLoading || pending" class="rounded-md border border-slate-200 bg-white p-8">
      <AppLoading :text="t('common.loading')" />
    </div>

    <template v-else-if="permissions?.permissions?.view_user">
      <section class="mb-8 rounded-md border border-slate-200 bg-white p-4 shadow-sm">
        <div class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">{{ t('settings_block.aca_enable') }}</h2>
            <p class="mt-1 text-sm text-slate-600">{{ t('settings_block.aca_enable_help') }}</p>
          </div>
          <button
            type="button"
            class="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full focus:outline-none"
            :class="useAca ? 'bg-sky-500' : 'bg-gray-300'"
            role="switch"
            :aria-checked="useAca"
            :disabled="savingConfig"
            @click="useAca = !useAca"
          >
            <span
              class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
              :class="useAca ? 'translate-x-6' : 'translate-x-1'"
            />
          </button>
        </div>

        <div v-if="useAca" class="mt-4 overflow-x-auto">
          <table class="w-full min-w-[48rem] border-collapse text-sm">
            <thead>
              <tr class="border-b border-slate-200 bg-slate-50 text-left text-slate-700">
                <th scope="col" class="px-3 py-2.5 font-semibold">{{ t('common.name') }}</th>
                <th scope="col" class="px-3 py-2.5 font-semibold">Token</th>
                <th scope="col" class="px-3 py-2.5 font-semibold">{{ t('common.value') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in configRows"
                :key="row.token"
                class="border-b border-slate-100 last:border-b-0"
              >
                <td class="px-3 py-3 align-middle font-medium text-slate-800">{{ row.name }}</td>
                <td class="px-3 py-3 align-middle font-mono text-xs text-slate-500">{{ row.token }}</td>
                <td class="px-3 py-3 align-middle">
                  <select
                    v-if="getFieldType(row.token) === 'variable_type'"
                    v-model="configValues[row.token]"
                    class="w-full min-w-[14rem] rounded border border-slate-300 px-2 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                    :disabled="savingConfig"
                  >
                    <option value="">{{ t('None') }}</option>
                    <option
                      v-for="vt in variableTypes"
                      :key="vt.id"
                      :value="vt.token"
                    >
                      {{ vt.token }} - {{ vt.name }}
                    </option>
                  </select>

                  <select
                    v-else-if="getFieldType(row.token) === 'contract_use_type'"
                    v-model="configValues[row.token]"
                    class="w-full min-w-[14rem] rounded border border-slate-300 px-2 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                    :disabled="savingConfig"
                  >
                    <option value="">{{ t('None') }}</option>
                    <option
                      v-for="useType in contractUseTypes"
                      :key="useType.id"
                      :value="useType.token"
                    >
                      {{ useType.token }} - {{ useType.name }}
                    </option>
                  </select>

                  <select
                    v-else-if="getFieldType(row.token) === 'product'"
                    v-model="configValues[row.token]"
                    class="w-full min-w-[14rem] rounded border border-slate-300 px-2 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                    :disabled="savingConfig"
                  >
                    <option value="">{{ t('None') }}</option>
                    <option
                      v-for="product in products"
                      :key="product.id"
                      :value="product.token"
                    >
                      {{ product.token }} - {{ product.name }}
                    </option>
                  </select>

                  <select
                    v-else-if="getFieldType(row.token) === 'price_rate'"
                    v-model="configValues[row.token]"
                    class="w-full min-w-[14rem] rounded border border-slate-300 px-2 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                    :disabled="savingConfig || !selectedProduct"
                  >
                    <option value="">{{ t('None') }}</option>
                    <option
                      v-for="priceRate in priceRates"
                      :key="priceRate.id"
                      :value="priceRate.token"
                    >
                      {{ priceRate.token }} - {{ priceRate.name }}
                    </option>
                  </select>

                  <input
                    v-else
                    v-model="configValues[row.token]"
                    type="text"
                    class="w-full min-w-[14rem] rounded border border-slate-300 px-2 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                    :disabled="savingConfig"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-else class="mt-4 text-sm text-slate-500">{{ t('settings_block.aca_disabled_hint') }}</p>

        <div class="mt-4 flex justify-end border-t border-slate-100 pt-4">
          <button
            type="button"
            class="inline-flex items-center gap-1.5 rounded-md border border-sky-400/60 bg-sky-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="savingConfig"
            @click="saveConfig"
          >
            <Icon
              :name="savingConfig ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
              class="size-4 shrink-0"
              :class="{ 'animate-spin': savingConfig }"
            />
            {{ t('common.save') }}
          </button>
        </div>
      </section>

      <section
        v-if="useAca && canViewContractUseAca"
        class="mb-8 rounded-md border border-slate-200 bg-white p-4 shadow-sm"
      >
        <h2 class="mb-1 text-lg font-semibold text-slate-900">{{ t('settings_block.aca_contracts_use_aca') }}</h2>
        <p class="mb-4 text-sm text-slate-600">{{ t('settings_block.aca_contracts_use_aca_help') }}</p>

        <div v-if="loadingContractUseAcaStats" class="py-6">
          <AppLoading :text="t('common.loading')" />
        </div>

        <template v-else-if="contractUseAcaStats">
          <div class="mb-4 grid gap-3 sm:grid-cols-3">
            <div class="rounded-md border border-slate-200 bg-slate-50 px-4 py-3">
              <p class="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {{ t('settings_block.aca_active_contracts') }}
              </p>
              <p class="mt-1 text-2xl font-semibold text-slate-900">{{ contractUseAcaStats.active_contracts }}</p>
            </div>
            <div class="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3">
              <p class="text-xs font-semibold uppercase tracking-wide text-emerald-700">
                {{ t('settings_block.aca_filled_use_aca') }}
              </p>
              <p class="mt-1 text-2xl font-semibold text-emerald-900">{{ contractUseAcaStats.filled_use_aca }}</p>
            </div>
            <div
              class="rounded-md border px-4 py-3"
              :class="hasPendingUseAca ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-slate-50'"
            >
              <p
                class="text-xs font-semibold uppercase tracking-wide"
                :class="hasPendingUseAca ? 'text-amber-800' : 'text-slate-500'"
              >
                {{ t('settings_block.aca_pending_use_aca') }}
              </p>
              <p
                class="mt-1 text-2xl font-semibold"
                :class="hasPendingUseAca ? 'text-amber-900' : 'text-slate-900'"
              >
                {{ contractUseAcaStats.pending_use_aca }}
              </p>
            </div>
          </div>

          <p
            v-if="!hasPendingUseAca"
            class="mb-4 rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
          >
            {{ t('settings_block.aca_all_contracts_have_use_aca') }}
          </p>

          <div
            v-if="canChangeContractUseAca"
            class="flex flex-wrap items-center gap-4 border-t border-slate-100 pt-4"
          >
            <label
              v-if="SUPPORTS_UPDATE_ALL_CONTRACTS"
              class="inline-flex items-center gap-2 text-sm text-slate-700"
            >
              <input
                v-model="updateAllContracts"
                type="checkbox"
                class="rounded border-slate-300 text-sky-500 focus:ring-sky-500"
                :disabled="runningDryRun || runningFill"
              />
              {{ t('settings_block.aca_update_all_contracts') }}
            </label>

            <div class="flex flex-wrap gap-2">
              <button
                type="button"
                class="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="runningDryRun || runningFill"
                @click="runDryRun"
              >
                <Icon
                  :name="runningDryRun ? 'fa6-solid:spinner' : 'fa6-solid:flask'"
                  class="size-4 shrink-0"
                  :class="{ 'animate-spin': runningDryRun }"
                />
                {{ t('settings_block.aca_simulate_fill') }}
              </button>

              <button
                type="button"
                class="inline-flex items-center gap-1.5 rounded-md border border-sky-400/60 bg-sky-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="runningDryRun || runningFill || (!SUPPORTS_UPDATE_ALL_CONTRACTS && !updateAllContracts && !hasPendingUseAca)"
                @click="runFill"
              >
                <Icon
                  :name="runningFill ? 'fa6-solid:spinner' : 'fa6-solid:play'"
                  class="size-4 shrink-0"
                  :class="{ 'animate-spin': runningFill }"
                />
                {{ t('settings_block.aca_fill_use_aca') }}
              </button>
            </div>
          </div>

          <div
            v-else
            class="rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600"
          >
            {{ t('common.no_permissions') }}
          </div>

          <div v-if="runningFill" class="mt-4">
            <p class="mb-2 text-sm text-slate-600">{{ t('settings_block.aca_fill_running') }}</p>
            <div class="h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                class="h-full rounded-full bg-sky-500 transition-all duration-300"
                :style="{ width: `${fillTaskProgress}%` }"
              />
            </div>
            <p class="mt-1 text-xs font-mono text-slate-500">{{ fillTaskProgress }}%</p>
          </div>

          <div
            v-if="fillResult && !fillResult.skipped"
            class="mt-4 rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-800"
          >
            <h3 class="mb-2 font-semibold text-slate-900">
              {{ fillResult.dry_run ? t('settings_block.aca_dry_run_result') : t('settings_block.aca_fill_result') }}
            </h3>
            <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              <p>{{ t('settings_block.aca_total_contracts') }}: <strong>{{ fillResult.total_contracts ?? 0 }}</strong></p>
              <p>{{ t('settings_block.aca_updated_count') }}: <strong>{{ fillResult.updated_count ?? 0 }}</strong></p>
              <p>{{ t('settings_block.aca_skipped_count') }}: <strong>{{ fillResult.skipped_count ?? 0 }}</strong></p>
              <p>{{ t('settings_block.aca_error_count') }}: <strong>{{ fillResult.error_count ?? 0 }}</strong></p>
            </div>

            <div v-if="skipReasonEntries.length" class="mt-3 space-y-2">
              <p class="font-medium text-slate-700">{{ t('common.details') }}:</p>
              <ul class="list-disc space-y-1 pl-5">
                <li v-for="entry in skipReasonEntries" :key="entry.key">
                  {{ entry.label }}: {{ entry.count }}
                  <span v-if="entry.examples.length" class="text-slate-500">
                    ({{ entry.examples.join(', ') }})
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </template>
      </section>

      <section
        v-if="canShowLineItems"
        class="rounded-md border border-slate-200 bg-white p-4 shadow-sm"
      >
        <h2 class="mb-1 text-lg font-semibold text-slate-900">{{ t('settings_block.aca_line_items') }}</h2>
        <p class="mb-4 text-sm text-slate-600">{{ t('settings_block.aca_line_items_help') }}</p>

        <div v-if="loadingLineItems" class="py-8">
          <AppLoading :text="t('common.loading')" />
        </div>

        <div v-else-if="!lineItems.length" class="rounded border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500">
          {{ t('common.no_data_found') }}
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full min-w-[56rem] border-collapse text-sm">
            <thead>
              <tr class="border-b border-slate-200 bg-slate-50 text-left text-slate-700">
                <th scope="col" class="px-3 py-2.5 font-semibold">{{ t('price_rate') }}</th>
                <th scope="col" class="px-3 py-2.5 font-semibold">{{ t('billing_block.billing_range') }}</th>
                <th scope="col" class="px-3 py-2.5 font-semibold">{{ t('pricing_block.line_items') }}</th>
                <th scope="col" class="px-3 py-2.5 font-semibold">{{ t('pricing_block.account_code') }}</th>
                <th scope="col" class="px-3 py-2.5 font-semibold w-24">{{ t('common.actions') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="lineItem in lineItems"
                :key="lineItem.id"
                class="border-b border-slate-100 last:border-b-0"
                :class="{ 'bg-amber-50': lineItem.is_active_billing_range }"
              >
                <td class="px-3 py-3 align-middle text-slate-800">
                  <div class="font-medium">{{ lineItem.price_rate_name }}</div>
                  <div v-if="lineItem.price_rate_token" class="text-xs text-slate-500">{{ lineItem.price_rate_token }}</div>
                </td>
                <td class="px-3 py-3 align-middle text-slate-800">
                  <div class="font-medium">
                    {{ lineItem.billing_range_name || lineItem.billing_range_token || '-' }}
                  </div>
                  <div v-if="lineItem.billing_range_token" class="text-xs text-slate-500">
                    {{ lineItem.billing_range_token }}
                  </div>
                  <div v-if="lineItem.billing_range_start" class="text-xs text-slate-500">
                    {{ formatDate(lineItem.billing_range_start) }}
                    <template v-if="lineItem.billing_range_end">
                      — {{ formatDate(lineItem.billing_range_end) }}
                    </template>
                  </div>
                  <span
                    v-if="lineItem.is_active_billing_range"
                    class="mt-1 inline-block rounded bg-amber-200 px-2 py-0.5 text-xs font-semibold text-amber-900"
                  >
                    {{ t('pricing_block.current_billing_range') }}
                  </span>
                </td>
                <td class="px-3 py-3 align-middle text-slate-800">
                  {{ lineItem.token }} - {{ lineItem.name }}
                </td>
                <td class="px-3 py-3 align-middle">
                  <select
                    v-model="lineItemArticles[lineItem.id]"
                    class="w-full min-w-[16rem] rounded border border-slate-300 px-2 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
                    :disabled="savingLineItemId === lineItem.id"
                  >
                    <option value="">{{ t('None') }}</option>
                    <option
                      v-for="article in articles"
                      :key="article.id"
                      :value="article.id"
                    >
                      {{ article.token }} - {{ article.name }}
                    </option>
                  </select>
                </td>
                <td class="px-3 py-3 align-middle">
                  <button
                    type="button"
                    class="inline-flex h-9 w-9 items-center justify-center rounded-full border border-sky-500 text-sky-500 transition hover:bg-sky-600 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                    :disabled="savingLineItemId === lineItem.id"
                    :aria-label="t('common.save')"
                    @click="saveLineItemArticle(lineItem)"
                  >
                    <Icon
                      :name="savingLineItemId === lineItem.id ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
                      class="h-4 w-4"
                      :class="{ 'animate-spin': savingLineItemId === lineItem.id }"
                    />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <div v-else class="rounded-md border border-rose-200 bg-rose-50 px-4 py-6 text-rose-700">
      {{ t('common.no_permissions') }}
    </div>
  </div>
</template>
