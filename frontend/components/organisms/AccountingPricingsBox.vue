<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import debounce from 'lodash.debounce';
import { useToast } from 'vue-toastification';
import Pagination from '~/components/molecules/Pagination.vue';
import { formatDateTime } from '~/utils/date';

const props = defineProps({
  categories: {
    type: Array,
    default: () => [],
  },
  activeExploitation: {
    type: [Number, String],
    default: null,
  },
  showExploitation: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['create', 'edit']);

const { t } = useI18n();
const toast = useToast();
const { $AccountingPricingApiService, $AddressApiService } = useNuxtApp();

const listLoading = ref(false);
const accountingPricingData = ref([]);
const searchQuery = ref('');
const pagination = ref({
  page: 1,
  perPage: 10,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false,
});
const banksCatalog = ref([]);
const activeCategory = ref(props.categories[0]?.token ?? 'invoice');

const activeCategoryLabel = computed(
  () => props.categories.find((item) => item.token === activeCategory.value)?.name ?? '',
);

const groupPricingByConceptToken = (items) => {
  const groups = [];
  const groupByToken = new Map();

  for (const item of items) {
    const concept = item?.accounting_concept ?? null;
    const token = concept?.token || (concept?.id != null ? String(concept.id) : '__none__');
    let group = groupByToken.get(token);
    if (!group) {
      group = { accounting_concept: concept, items: [] };
      groupByToken.set(token, group);
      groups.push(group);
    }
    group.items.push(item);
  }

  return groups;
};

const pricingGroups = computed(() =>
  groupPricingByConceptToken(
    Array.isArray(accountingPricingData.value) ? accountingPricingData.value : [],
  ).filter((group) => group.items.length),
);

const pricingItemCount = computed(() =>
  pricingGroups.value.reduce((count, group) => count + group.items.length, 0),
);

const relatedNames = (items) =>
  (items ?? [])
    .map((item) => {
      if (item == null || item === '') return '';
      if (typeof item !== 'object') return String(item);
      return item.name || item.token || item.label || String(item.id ?? '');
    })
    .filter(Boolean);

const bankListFromResponse = (response) => {
  if (Array.isArray(response)) return response;
  if (Array.isArray(response?.results)) return response.results;
  return [];
};

const loadBanksCatalog = async () => {
  try {
    const collected = [];
    let page = 1;
    let hasNext = true;
    while (hasNext && page <= 50) {
      const response = await $AddressApiService.getBanks(page);
      collected.push(...bankListFromResponse(response));
      hasNext = !Array.isArray(response) && !!response?.next;
      page += 1;
    }
    banksCatalog.value = collected.filter(
      (bank) => bank && (bank.id != null || bank.token || bank.name),
    );
  } catch (error) {
    console.error(error);
    banksCatalog.value = [];
  }
};

const bankCatalogById = computed(() => {
  const map = new Map();
  banksCatalog.value.forEach((bank) => {
    if (bank?.id != null) map.set(String(bank.id), bank);
  });
  return map;
});

const bankTagLabel = (bank) => {
  if (bank == null || bank === '') return '';
  if (typeof bank !== 'object') {
    const fromCatalog = bankCatalogById.value.get(String(bank));
    return fromCatalog ? bankTagLabel(fromCatalog) : String(bank);
  }
  const resolved =
    bank.id != null ? bankCatalogById.value.get(String(bank.id)) || bank : bank;
  const token = resolved.token || bank.token || '';
  const name = resolved.name || bank.name || '';
  if (name && token) return `${name} - ${token}`;
  return name || token || (resolved.id != null ? String(resolved.id) : '');
};

const relatedGroups = (item) =>
  [
    { key: 'products', label: t('product'), names: relatedNames(item.products) },
    { key: 'price_rates', label: t('price_rate'), names: relatedNames(item.price_rates) },
    {
      key: 'line_item_types',
      label: t('pricing_block.line_item_detail'),
      names: relatedNames(item.line_item_types),
    },
    {
      key: 'price_intervals',
      label: t('pricing_block.price_interval_detail'),
      names: relatedNames(item.price_intervals),
    },
    {
      key: 'price_variables',
      label: t('pricing_block.price_variable_detail'),
      names: relatedNames(item.price_variables),
    },
    { key: 'payment_types', label: t('payment_types'), names: relatedNames(item.payment_types) },
    { key: 'origins', label: t('common.origins'), names: relatedNames(item.origins) },
  ].filter((group) => group.names.length);

const displayUser = (user) => user?.username || '—';

const displayAuditDate = (value) => {
  if (!value) return null;
  return formatDateTime(value);
};

const getAccountingPricingData = async (page = pagination.value.page) => {
  listLoading.value = true;
  try {
    const query = String(searchQuery.value ?? '').trim();
    const response = await $AccountingPricingApiService.getAll(
      query,
      page,
      null,
      false,
      false,
      activeCategory.value,
      props.activeExploitation,
      null,
      null,
      pagination.value.perPage,
    );
    const results = Array.isArray(response?.results) ? response.results : [];
    const total = response?.count ?? 0;
    const totalPages = Math.ceil(total / pagination.value.perPage) || 0;

    if (!results.length && page > 1 && totalPages > 0 && page > totalPages) {
      pagination.value.page = totalPages;
      await getAccountingPricingData(totalPages);
      return;
    }

    accountingPricingData.value = results;
    Object.assign(pagination.value, {
      page,
      total,
      totalPages,
      previous: response?.previous ?? null,
      next: response?.next ?? null,
      isFiltered: query !== '',
    });
  } catch (error) {
    console.error(error);
    accountingPricingData.value = [];
    Object.assign(pagination.value, {
      total: 0,
      totalPages: 0,
      previous: null,
      next: null,
      isFiltered: String(searchQuery.value ?? '').trim() !== '',
    });
    toast.error(t('common.error'));
  } finally {
    listLoading.value = false;
  }
};

const debouncedGetAccountingPricingData = debounce((page) => {
  getAccountingPricingData(page);
}, 300);

const setActiveCategory = (token) => {
  if (activeCategory.value === token) return;
  activeCategory.value = token;
  pagination.value.page = 1;
  debouncedGetAccountingPricingData.cancel();
  getAccountingPricingData(1);
};

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetAccountingPricingData(1);
};

const resetSearch = () => {
  searchQuery.value = '';
  pagination.value.page = 1;
  debouncedGetAccountingPricingData.cancel();
  getAccountingPricingData(1);
};

const handlePageChange = (newPage) => {
  if (newPage === pagination.value.page) return;
  pagination.value.page = newPage;
  debouncedGetAccountingPricingData.cancel();
  getAccountingPricingData(newPage);
};

const deactivateAccountingPricing = async (id) => {
  if (!confirm(t('confirmation_text_block.confirm_deactivate'))) return;
  try {
    const payload = {
      id,
      is_active: false,
    };
    const response = await $AccountingPricingApiService.save(payload);
    if (response) {
      toast.success(t('common.saved_successfully'));
      await getAccountingPricingData();
    }
  } catch (error) {
    console.error(error);
    toast.error(t('common.error'));
  }
};

watch(
  () => props.activeExploitation,
  (next, prev) => {
    if (String(next) === String(prev)) return;
    pagination.value.page = 1;
    debouncedGetAccountingPricingData.cancel();
    getAccountingPricingData(1);
  },
);

watch(
  () => props.categories,
  (categories) => {
    if (!categories?.length) return;
    if (!categories.some((item) => item.token === activeCategory.value)) {
      activeCategory.value = categories[0].token;
    }
  },
  { deep: true },
);

onMounted(async () => {
  await Promise.all([getAccountingPricingData(), loadBanksCatalog()]);
});

defineExpose({
  refresh: getAccountingPricingData,
});
</script>

<template>
  <section class="overflow-hidden rounded-md bg-white" style="--accent: #0369a1; --accent-soft: #7dd3fc;">
    
    <div class="flex items-end gap-1.5 overflow-x-auto pt-4 scrollbar-hide">
      <button v-for="category in categories" :key="category.token" type="button"
      class="relative shrink-0 rounded-t-md px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
      :class="activeCategory === category.token
          ? 'bg-[var(--accent)] text-white border border-[var(--accent)]'
          : 'bg-[var(--accent-soft)]/40 text-[var(--accent)] hover:bg-[var(--accent-soft)] border border-b-0 border-[var(--accent-soft)]'
          " @click="setActiveCategory(category.token)">
        {{ category.name }}
      </button>
    </div>
    <div class="relative border rounded-b-lg rounded-tr-lg" style="border-color: var(--accent-soft)">
      <span class="absolute right-0 top-0 z-[1] h-11 w-1.5 rounded-bl-md rounded-tr-md"
        style="background-color: var(--accent)" />

      <header class="flex items-center justify-between gap-3 border-b px-4 py-3"
        style="border-color: var(--accent-soft)">
        <div class="flex min-w-0 items-center gap-2.5">
          <span class="my-auto mr-1 shrink-0 font-mono text-[11px] font-bold tracking-[0.14em]"
            style="color: var(--accent-soft)">
            03
          </span>
          <div class="relative flex size-9 shrink-0 items-center justify-center">
            <span class="absolute left-0 top-0 h-2 w-2 border-l border-t border-sky-200" />
            <span class="absolute right-0 top-0 h-2 w-2 border-r border-t border-sky-200" />
            <span class="absolute bottom-0 left-0 h-2 w-2 border-b border-l border-sky-200" />
            <span class="absolute bottom-0 right-0 h-2 w-2 border-b border-r border-sky-200" />
            <Icon name="fa6-solid:folder-open" class="size-3.5" style="color: var(--accent)" />
          </div>
          <div class="min-w-0">
            <p class="truncate text-sm font-bold text-sky-950">
              {{ activeCategoryLabel }}
            </p>
            <p class="font-mono text-[10px] tracking-widest text-slate-500">
              {{ listLoading ? '—' : String(pagination.total).padStart(2, '0') }}
            </p>
          </div>
        </div>

        <div class="flex min-w-0 shrink-0 items-center gap-2">
          <form role="search" class="flex min-w-0 items-center gap-1.5 rounded-md border bg-white px-2.5 py-1.5"
            style="border-color: var(--accent-soft)" @submit.prevent="handleSearch">
            <Icon name="fa6-solid:magnifying-glass" class="size-3 shrink-0" style="color: var(--accent)" />
            <input id="searchInput" v-model="searchQuery" type="text" name="search" :placeholder="t('dashboard.search')"
              class="w-32 bg-transparent text-[11px] text-sky-950 placeholder:text-slate-400 focus:outline-none sm:w-48"
              autocomplete="off" @input="handleSearch" />
            <button v-if="searchQuery" type="button"
              class="shrink-0 text-slate-400 transition-colors hover:text-[var(--accent)]" :title="t('common.reset')"
              @click="resetSearch">
              <Icon name="fa6-solid:xmark" class="size-3" />
            </button>
          </form>
          <button type="button"
            class="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-[var(--accent-soft)] px-3 py-1.5 text-[11px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white"
            @click="emit('create')">
            <Icon name="fa6-solid:plus" class="size-3 shrink-0" />
            {{ t('pricing_block.new_accounting_pricing') }}
          </button>
        </div>
      </header>

      <ul v-if="listLoading" class="divide-y" style="border-color: var(--accent-soft)">
        <li v-for="n in 3" :key="`skeleton-${n}`" class="flex items-stretch divide-x"
          style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent)">
          <div class="flex w-[4.75rem] shrink-0 flex-col items-center justify-center gap-1.5 px-2 py-3"
            style="background-color: color-mix(in srgb, var(--accent-soft) 25%, white)">
            <span class="h-2.5 w-10 animate-pulse rounded-sm bg-sky-100" />
            <span class="h-2 w-8 animate-pulse rounded-sm bg-sky-100/80" />
          </div>
          <div class="min-w-0 flex-1 px-4 py-3">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0 flex-1 space-y-2">
                <div class="h-3.5 w-2/5 max-w-[12rem] animate-pulse rounded-sm bg-sky-100" />
                <div class="h-2.5 w-1/3 max-w-[9rem] animate-pulse rounded-sm bg-sky-100/80" />
              </div>
              <div class="flex shrink-0 flex-col items-end gap-1.5">
                <div class="h-2.5 w-16 animate-pulse rounded-sm bg-sky-100" />
                <div class="h-2 w-24 animate-pulse rounded-sm bg-sky-100/80" />
              </div>
            </div>
            <div class="mt-3 flex gap-5">
              <div class="h-2 w-36 animate-pulse rounded-sm bg-sky-100/70" />
              <div class="h-2 w-36 animate-pulse rounded-sm bg-sky-100/70" />
            </div>
          </div>
        </li>
      </ul>

      <ul v-else class="max-h-[calc(100vh-340px)] divide-y overflow-y-auto"
        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent)">
        <li v-if="!pricingItemCount" class="flex items-stretch text-slate-400">
          <div class="flex w-[4.75rem] shrink-0 flex-col items-center justify-center border-r px-2 py-4 text-center"
            style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent); background-color: color-mix(in srgb, var(--accent-soft) 18%, white)">
            <span class="font-mono text-[11px] font-bold tracking-[0.14em]">——</span>
            <span class="mt-0.5 font-mono text-[10px] tracking-wider">——</span>
          </div>
          <div class="min-w-0 flex-1 px-4 py-4">
            <h3 class="text-sm font-semibold text-sky-950">
              {{ t('common.no_records') }}
            </h3>
            <p class="mt-0.5 text-sm text-slate-500">—</p>
          </div>
        </li>

        <li v-for="group in pricingGroups"
          :key="group.accounting_concept?.token ?? group.accounting_concept?.id ?? '__none__'"
          class="flex items-stretch" :class="{ 'opacity-55': group.accounting_concept?.is_active === false }">
          <div class="flex w-[4.75rem] shrink-0 flex-col items-stretch justify-start border-r py-3 text-center"
            style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent); background-color: color-mix(in srgb, var(--accent-soft) 22%, white)">
            <span class="px-1.5 font-mono text-[11px] font-bold tracking-[0.14em] text-sky-950">
              {{ group.accounting_concept?.token || '—' }}
            </span>
            <span v-if="group.accounting_concept?.name"
              class="mt-1 line-clamp-2 px-1.5 text-[9px] font-semibold uppercase leading-tight tracking-[0.06em] text-slate-500">
              {{ group.accounting_concept.name }}
            </span>
            <div v-if="group.accounting_concept?.type?.add_taxes || group.accounting_concept?.type?.add_subtotals"
              class="mt-2 flex flex-col gap-1 px-1.5">
              <span v-if="group.accounting_concept?.type?.add_taxes"
                class="rounded-md bg-[var(--accent-soft)] py-0.5 text-[8px] font-semibold uppercase leading-none tracking-wide text-[var(--accent)]">
                {{ t('taxes') }}
              </span>
              <span v-if="group.accounting_concept?.type?.add_subtotals"
                class="rounded-md bg-[var(--accent-soft)] py-0.5 text-[8px] font-semibold uppercase leading-none tracking-wide text-[var(--accent)]">
                {{ t('subtotal') }}
              </span>
            </div>
          </div>

          <ul class="min-w-0 flex-1 divide-y"
            style="border-color: color-mix(in srgb, var(--accent-soft) 40%, transparent)">
            <li v-for="item in group.items" :key="item.id"
              class="group flex items-stretch transition-colors hover:bg-sky-50/60"
              :class="{ 'opacity-55': item.is_active === false }">
              <div class="flex w-12 shrink-0 items-center justify-center border-r px-1 py-3 text-center"
                style="border-color: color-mix(in srgb, var(--accent-soft) 35%, transparent)">
                <span class="font-mono text-[10px] tracking-wider text-slate-500">
                  {{ item.token || '—' }}
                </span>
              </div>

              <div class="relative min-w-0 flex-1 px-4 py-3">
                <div class="flex items-start justify-between gap-3 pr-16">
                  <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <h3 class="truncate text-[15px] font-bold leading-tight text-sky-950">
                        {{ item.name }}
                      </h3>
                      <span v-if="item.is_default"
                        class="rounded-md bg-[var(--accent-soft)] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
                        {{ t('default') }}
                      </span>
                      <span v-if="item.undeclare_previous"
                        class="rounded-md bg-amber-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-amber-700">
                        {{ t('pricing_block.accounting_pricing_undeclare_previous') }}
                      </span>
                      <span v-if="item.is_active === false"
                        class="rounded-md bg-slate-100 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                        {{ t('common.inactive') }}
                      </span>
                    </div>
                    <p class="mt-1 text-[10px] text-slate-500">
                      <span class="font-semibold uppercase tracking-[0.1em] text-slate-400">
                        {{ t('common.updated') }}
                      </span>
                      {{ displayUser(item.last_updated_by) }}
                      <span v-if="displayAuditDate(item.updated_at)">
                        · {{ displayAuditDate(item.updated_at) }}
                      </span>
                    </p>
                  </div>

                  <div class="shrink-0 text-right">
                    <p class="text-[11px] font-semibold tracking-wide text-sky-950">
                      {{ item.company?.alias }}
                    </p>
                    <p v-if="item.company?.name" class="max-w-[13rem] truncate text-[10px] text-slate-500"
                      :title="item.company.name">
                      {{ item.company.name }}
                    </p>
                    <p v-if="showExploitation && item.exploitation" class="mt-0.5 font-mono text-[10px] text-slate-500">
                      {{ item.exploitation.token }}
                      <span v-if="item.exploitation.name"> · {{ item.exploitation.name }}</span>
                    </p>
                  </div>
                </div>

                <div v-if="relatedGroups(item).length" class="mt-2.5 flex flex-wrap gap-x-4 gap-y-1.5">
                  <div v-for="relatedGroup in relatedGroups(item)" :key="relatedGroup.key"
                    class="flex min-w-0 max-w-full flex-wrap items-center gap-1">
                    <span class="text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                      {{ relatedGroup.label }}
                    </span>
                    <span v-for="(name, nameIndex) in relatedGroup.names"
                      :key="`${relatedGroup.key}-${nameIndex}-${name}`"
                      class="inline-flex max-w-full items-center truncate rounded-md border bg-white px-1.5 py-px text-[10px] font-medium leading-tight text-sky-950"
                      style="border-color: var(--accent-soft)" :title="name">
                      {{ name }}
                    </span>
                  </div>
                </div>

                <div
                  class="absolute right-3 top-2.5 flex gap-1 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                  <button type="button"
                    class="flex size-8 items-center justify-center rounded-md border bg-white text-slate-500 transition-colors hover:border-[var(--accent)] hover:bg-[var(--accent-soft)] hover:text-[var(--accent)]"
                    style="border-color: var(--accent-soft)" @click="emit('edit', item.id)">
                    <Icon name="fa6-solid:pencil" class="size-3" />
                  </button>
                  <button type="button"
                    class="flex size-8 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 transition-colors hover:border-rose-300 hover:bg-rose-50 hover:text-rose-600"
                    @click="deactivateAccountingPricing(item.id)">
                    <Icon name="fa6-solid:trash" class="size-3" />
                  </button>
                </div>
              </div>
            </li>
          </ul>
        </li>
      </ul>
    </div>


    <div v-if="pagination.total > 0" class="px-3">
      <Pagination :pagination="pagination" @update:page="handlePageChange" />
    </div>
  </section>
</template>
