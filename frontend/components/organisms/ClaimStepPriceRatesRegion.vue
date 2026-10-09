<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();
const { $ExploitationApiService, $ProductApiService, $PriceRateApiService } = useNuxtApp();

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  priceRates: {
    type: Array,
    default: () => []
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['update:modelValue', 'change', 'show-subregion']);

const loading = ref(true);
const loadingProducts = ref(false);
const loadingRates = ref(false);
const error = ref(null);

const exploitationId = ref(null);
const exploitations = ref([]);

const openExploitation = ref(null);
const products = ref([]);
const productSearch = ref('');
const originFilter = ref(null);

const selectedProduct = ref(null);
const rates = ref([]);

const selection = ref({});

const selectedList = computed(() => Object.values(selection.value));

const normalizeRate = (rate, product = null, exploitation = null) => ({
  id: rate.id,
  name: rate.name || rate.token,
  token: rate.token,
  is_bail: rate.is_bail || false,
  product_id: rate.product?.id || product?.id || null,
  product_name: rate.product?.name || rate.product_name || product?.name || t('pricing_block.no_product'),
  exploitation_name: exploitation?.name || product?.exploitation_name || null
});

const setSelectionFromProp = () => {
  const initial = {};
  props.priceRates.forEach(rate => {
    if (rate?.id) initial[rate.id] = normalizeRate(rate);
  });
  props.modelValue.forEach(id => {
    if (id && !initial[id]) {
      initial[id] = { id, name: `#${id}`, product_name: t('pricing_block.no_product') };
    }
  });
  selection.value = initial;
};

const emitSelection = () => {
  emit('update:modelValue', selectedList.value.map(rate => rate.id));
  emit('change', selectedList.value);
};

const isSelected = (id) => !!selection.value[id];

const toggleRate = (rate) => {
  const next = { ...selection.value };
  if (next[rate.id]) {
    delete next[rate.id];
  } else {
    next[rate.id] = normalizeRate(rate, selectedProduct.value?.product, selectedProduct.value?.exploitation);
  }
  selection.value = next;
  emitSelection();
};

const removeRate = (id) => {
  const next = { ...selection.value };
  delete next[id];
  selection.value = next;
  emitSelection();
};

const clearSelection = () => {
  selection.value = {};
  emitSelection();
};

const origins = computed(() => {
  const map = new Map();
  products.value.forEach(product => {
    const token = product.origin_token || 'null';
    const entry = map.get(token);
    if (entry) {
      entry.count += 1;
    } else {
      map.set(token, {
        token,
        name: product.origin_name || t('common.no_origin'),
        count: 1
      });
    }
  });
  return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
});

const filteredProducts = computed(() => {
  const query = productSearch.value.trim().toLowerCase();
  return products.value.filter(product => {
    if (originFilter.value && (product.origin_token || 'null') !== originFilter.value) return false;
    if (!query) return true;
    return (product.name || '').toLowerCase().includes(query)
      || (product.token || '').toLowerCase().includes(query)
      || (product.origin_name || '').toLowerCase().includes(query);
  });
});

const selectedCountByProduct = computed(() => {
  const counts = {};
  selectedList.value.forEach(rate => {
    if (!rate.product_id) return;
    counts[rate.product_id] = (counts[rate.product_id] || 0) + 1;
  });
  return counts;
});

const getExploitations = async () => {
  const response = await $ExploitationApiService.getData('', 1, 'token', false);
  const results = response?.results || [];
  exploitations.value = exploitationId.value
    ? results.filter(item => String(item.id) === String(exploitationId.value))
    : results;
};

const getProducts = async (exploitation) => {
  loadingProducts.value = true;
  try {
    const response = await $ProductApiService.getAll('', [], 1, null, false, null, [], true, exploitation.id);
    products.value = Array.isArray(response) ? response : (response?.results || []);
  } catch (err) {
    console.error(err);
    products.value = [];
  } finally {
    loadingProducts.value = false;
  }
};

const toggleExploitation = async (exploitation) => {
  if (openExploitation.value?.id === exploitation.id) {
    openExploitation.value = null;
    products.value = [];
    return;
  }
  openExploitation.value = exploitation;
  products.value = [];
  productSearch.value = '';
  originFilter.value = null;
  await getProducts(exploitation);
};

const getRates = async (product, exploitation) => {
  loadingRates.value = true;
  try {
    const response = await $PriceRateApiService.getAll('', [], 1, null, false, product.id, null, true, exploitation?.id || null);
    rates.value = response?.results || [];
    console.log("rates")
    console.log(rates.value);
  } catch (err) {
    console.error(err);
    rates.value = [];
  } finally {
    loadingRates.value = false;
  }
};

const selectProduct = async (product) => {
  selectedProduct.value = { product, exploitation: openExploitation.value };
  rates.value = [];
  emit('show-subregion', true);
  await getRates(product, openExploitation.value);
};

const backToProducts = () => {
  selectedProduct.value = null;
  rates.value = [];
  emit('show-subregion', false);
};

const activeRange = (rate) => rate.billing_range_active || rate.billing_ranges?.[0] || null;

const getData = async () => {
  loading.value = true;
  error.value = null;
  try {
    const storedExploitation = localStorage.getItem('exploitation');
    exploitationId.value = storedExploitation && storedExploitation !== 'null' ? storedExploitation : null;
    await getExploitations();
    if (exploitations.value.length === 1) {
      await toggleExploitation(exploitations.value[0]);
    }
  } catch (err) {
    console.error(err);
    error.value = err;
  } finally {
    loading.value = false;
  }
};

watch(() => props.priceRates, (newValue) => {
  const incoming = (newValue || []).map(rate => rate?.id).filter(Boolean).sort();
  const current = selectedList.value.map(rate => rate.id).sort();
  if (JSON.stringify(incoming) === JSON.stringify(current)) return;
  setSelectionFromProp();
}, { deep: true });

onMounted(async () => {
  setSelectionFromProp();
  await getData();
});
</script>

<template>
  <div class="region__content">
    <div class="flex items-start justify-between gap-3">
      <H1Region class="mb-3">{{ $t('common.modify') }} {{ $t('common.price_rates') }}</H1Region>
      <span class="shrink-0 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-600">
        {{ $t('common.selected') }}: {{ selectedList.length }}
      </span>
    </div>

    <div v-if="selectedList.length" class="mb-4 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
      <div class="flex flex-wrap gap-2">
        <span v-for="rate in selectedList" :key="rate.id"
          class="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-sm text-slate-700">
          <Icon name="fa6-solid:cube" class="text-sky-500" />
          <span class="font-semibold">{{ rate.name }}</span>
          <span class="text-slate-400">·</span>
          <span class="text-slate-500">{{ rate.product_name }}</span>
          <button class="text-slate-400 transition hover:text-rose-500" @click="removeRate(rate.id)">
            <Icon name="fa6-solid:xmark" />
          </button>
        </span>
      </div>
      <button class="mt-3 text-xs text-sky-500 underline hover:no-underline" @click="clearSelection">
        {{ $t('common.clear') }}
      </button>
    </div>

    <AppLoading v-if="loading" :text="$t('common.loading')" />

    <div v-else-if="error" class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-6 text-rose-600">
      <p>{{ $t('common.error') }}: {{ error.message }}</p>
      <button class="mt-2 text-sky-600 underline hover:no-underline" @click="getData">
        {{ $t('common.load_again') }}
      </button>
    </div>

    <Transition v-else name="stage" mode="out-in">
      <!-- Selecció d'explotació i producte -->
      <div v-if="!selectedProduct" key="products" class="flex flex-col gap-3">
        <p v-if="!exploitations.length"
          class="rounded-2xl border border-dashed border-slate-200 bg-white/60 px-4 py-10 text-center text-sm text-slate-500">
          {{ $t('common.no_data_found') }}
        </p>

        <article v-for="exploitation in exploitations" :key="exploitation.id"
          class="rounded-2xl border bg-white shadow-sm transition"
          :class="openExploitation?.id === exploitation.id ? 'border-sky-500 shadow-md' : 'border-slate-200'">
          <button
            class="flex w-full items-center justify-between gap-3 rounded-2xl px-4 py-3 text-left transition hover:bg-sky-50"
            @click="toggleExploitation(exploitation)">
            <div class="flex flex-col gap-1">
              <p class="text-xs font-semibold uppercase tracking-wide text-sky-500">{{ $t('exploitation') }}</p>
              <p class="text-base font-semibold text-slate-800">{{ exploitation.name || exploitation.token }}</p>
            </div>
            <div class="flex h-8 w-8 items-center justify-center rounded-full border text-slate-500 transition"
              :class="openExploitation?.id === exploitation.id ? 'border-sky-500 bg-sky-500 text-white' : 'border-slate-200 bg-white'">
              <Icon
                :name="openExploitation?.id === exploitation.id ? 'fa6-solid:chevron-up' : 'fa6-solid:chevron-down'" />
            </div>
          </button>

          <div v-if="openExploitation?.id === exploitation.id" class="border-t border-slate-100 bg-slate-50/60">
            <AppLoading v-if="loadingProducts" :text="$t('common.loading')" />

            <div v-else class="space-y-4 p-4">
              <div class="input-group border-b border-slate-200">
                <span class="input-group flex w-full items-center gap-2">
                  <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
                  <input v-model="productSearch" type="text" name="search" :placeholder="$t('dashboard.search')"
                    class="w-full rounded-md p-1 focus:outline-none focus-visible:border-0" autocomplete="off" />
                </span>
              </div>

              <div v-if="origins.length > 1" class="flex flex-wrap items-center gap-2">
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  {{ $t('common.origins') }}
                </span>
                <button class="rounded-full border px-3 py-1 text-xs font-medium transition"
                  :class="!originFilter ? 'border-sky-500 bg-sky-500 text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-sky-300'"
                  @click="originFilter = null">
                  {{ $t('common.all') }} ({{ products.length }})
                </button>
                <button v-for="origin in origins" :key="origin.token"
                  class="rounded-full border px-3 py-1 text-xs font-medium transition"
                  :class="originFilter === origin.token ? 'border-sky-500 bg-sky-500 text-white' : 'border-slate-200 bg-white text-slate-600 hover:border-sky-300'"
                  @click="originFilter = origin.token">
                  {{ origin.name }} ({{ origin.count }})
                </button>
              </div>

              <p v-if="!filteredProducts.length"
                class="rounded-xl border border-dashed border-slate-200 bg-white/70 px-4 py-6 text-center text-sm text-slate-500">
                {{ $t('common.no_data_found') }}
              </p>

              <div v-else class="grid gap-2 md:grid-cols-2">
                <button v-for="product in filteredProducts" :key="product.id"
                  class="group flex items-center justify-between gap-3 rounded-xl border bg-white px-4 py-3 text-left shadow-sm transition hover:border-sky-400 hover:shadow-md"
                  :class="selectedCountByProduct[product.id] ? 'border-sky-500' : 'border-slate-200'"
                  @click="selectProduct(product)">
                  <div class="min-w-0">
                    <p class="text-xs font-semibold uppercase tracking-wide text-sky-500">
                      {{ product.origin_name || $t('common.no_origin') }}
                    </p>
                    <p class="truncate text-base font-semibold text-slate-800">{{ product.name }}</p>
                  </div>
                  <div class="flex shrink-0 items-center gap-2">
                    <span v-if="selectedCountByProduct[product.id]"
                      class="rounded-full bg-sky-500 px-2 py-0.5 text-xs font-semibold text-white">
                      {{ selectedCountByProduct[product.id] }}
                    </span>
                    <Icon name="fa6-solid:chevron-right" class="text-slate-400 transition group-hover:text-sky-500" />
                  </div>
                </button>
              </div>
            </div>
          </div>
        </article>
      </div>

      <!-- Selecció de tarifes del producte -->
      <div v-else key="rates" class="flex flex-col gap-4">
        <div class="flex items-center gap-3">
          <button
            class="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-600 shadow-sm transition hover:border-sky-400 hover:text-sky-600"
            @click="backToProducts">
            <Icon name="fa6-solid:arrow-left" />
            {{ $t('common.go_back') }}
          </button>
          <div class="min-w-0">
            <p class="text-xs font-semibold uppercase tracking-wide text-sky-500">
              {{ selectedProduct.exploitation?.name }} · {{ selectedProduct.product.origin_name ||
                $t('common.no_origin') }}
            </p>
            <p class="truncate text-base font-semibold text-slate-800">
              {{ selectedProduct.product.name }}
            </p>
          </div>
        </div>

        <AppLoading v-if="loadingRates" :text="$t('common.loading')" />

        <template v-else>
          <p v-if="!rates.length"
            class="rounded-2xl border border-dashed border-slate-200 bg-white/60 px-4 py-10 text-center text-sm text-slate-500">
            {{ $t('common.no_data_found') }}
          </p>

          <div v-else class="flex flex-col gap-2">
            <div class="text-right text-sm text-slate-500">{{ $t('common.total') }}: {{ rates.length }}</div>

            <button v-for="rate in rates" :key="rate.id"
              class="flex items-start gap-3 rounded-xl border bg-white px-4 py-3 text-left shadow-sm transition hover:shadow-md"
              :class="isSelected(rate.id) ? 'border-sky-500 bg-sky-50/60' : 'border-slate-200 hover:border-sky-300'"
              @click="toggleRate(rate)">
              <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded border transition"
                :class="isSelected(rate.id) ? 'border-sky-500 bg-sky-500 text-white' : 'border-slate-300 bg-white'">
                <Icon v-if="isSelected(rate.id)" name="fa6-solid:check" class="h-3 w-3" />
              </span>

              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-x-2 justify-between">
                  <div class="flex flex-wrap items-center gap-2">
                    <p class="text-base font-semibold text-slate-800">{{ rate.name || rate.token }}</p>
                    <span v-if="rate.is_bail"
                      class="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-600">
                      {{ $t('bail') }}
                    </span>
                    <span v-if="!rate.is_active"
                      class="rounded-full border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-500">
                      {{ $t('common.inactive') }}
                    </span>
                  </div>
                  <p v-if="activeRange(rate)" class="text-xs text-slate-500">
                    {{ $t('common.start') }}: {{ activeRange(rate).start }}
                    <span v-if="activeRange(rate).end"> · {{ $t('common.end') }}: {{ activeRange(rate).end }}</span>
                    <span v-if="activeRange(rate).line_item_types?.length">
                      · {{ $t('line_items') }}: {{ activeRange(rate).line_item_types.length }}
                    </span>
                  </p>
                </div>
              </div>
            </button>
          </div>
        </template>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.stage-enter-active,
.stage-leave-active {
  transition: opacity 0.25s ease, transform 0.35s ease;
}

.stage-enter-from {
  opacity: 0;
  transform: translateX(2rem);
}

.stage-leave-to {
  opacity: 0;
  transform: translateX(-2rem);
}
</style>
