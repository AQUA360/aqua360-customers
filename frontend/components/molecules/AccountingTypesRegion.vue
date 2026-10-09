<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { checkPermission } from '~/middleware/permission';

const props = defineProps({
  items: {
    type: Array,
    default: null,
  },
});

const emit = defineEmits(['close', 'changed']);

const { t } = useI18n();
const toast = useToast();
const { $AccountingTypeApiService, $PriceRateApiService } = useNuxtApp();

const objectPermissions = ref(null);
const pending = ref(false);
const error = ref(null);
const localItems = ref([]);
const searchQuery = ref('');
const expandedId = ref(null);

const sourceItems = computed(() =>
  Array.isArray(props.items) ? props.items : localItems.value,
);

const filteredItems = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return sourceItems.value;
  return sourceItems.value.filter((item) => {
    const haystack = [item?.token, item?.name]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return haystack.includes(q);
  });
});

const loadItems = async () => {
  if (Array.isArray(props.items)) return;
  pending.value = true;
  error.value = null;
  try {
    const response = await $AccountingTypeApiService.getAll();
    localItems.value = Array.isArray(response) ? response : (response?.results ?? []);
  } catch (err) {
    error.value = err;
    localItems.value = [];
    console.error(err);
  } finally {
    pending.value = false;
  }
};

const openNew = () => {
  // Functionality will be added later.
};

const toggleExpanded = (id) => {
  expandedId.value = expandedId.value === id ? null : id;
};

const yesNo = (value) => (value ? t('common.yes') : t('common.no'));

watch(
  () => props.items,
  () => {
    if (!Array.isArray(props.items)) loadItems();
  },
);

onMounted(async () => {
  objectPermissions.value = await checkPermission($PriceRateApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close');
    return;
  }
  await loadItems();
});
</script>

<template>
  <div v-if="objectPermissions?.can_view" class="region__content pr-4">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <H1Region class="!mb-0">
        {{ t('common.check') }}: {{ t('pricing_block.accounting_types') }}
      </H1Region>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-sm border border-sky-700 bg-sky-950 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-white transition-colors hover:bg-sky-800"
        @click="openNew"
      >
        <Icon name="fa6-solid:plus" class="size-3 shrink-0" />
        {{ t('pricing_block.new_accounting_type') }}
      </button>
    </div>

    <span class="input-group mt-3 flex w-80 items-center gap-2">
      <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
      <input
        v-model="searchQuery"
        type="text"
        name="search"
        :placeholder="t('dashboard.search')"
        class="w-full rounded-md p-1 focus:outline-none focus-visible:border-0"
        autocomplete="off"
      />
    </span>

    <hr class="my-3 border-sky-100" />

    <div v-if="pending" class="py-6 text-sm text-sky-700">
      {{ t('common.loading') }}...
    </div>
    <div v-else-if="error" class="py-4 text-sm">
      <p>{{ t('common.error') }}: {{ error.message }}</p>
      <button type="button" class="text-sky-500 underline hover:no-underline" @click="loadItems">
        {{ t('common.load_again') }}
      </button>
    </div>
    <div v-else class="overflow-y-auto" :style="{ maxHeight: 'calc(100vh - 220px)' }">
      <ul class="divide-y divide-sky-200 border-b border-sky-200 text-sm">
        <li v-if="!filteredItems.length" class="px-3 py-6 text-center text-sky-500">
          {{ t('common.no_records') }}
        </li>
        <li
          v-for="item in filteredItems"
          :key="item.id"
          class="px-3 py-2.5 transition-colors hover:bg-sky-50"
          :class="{ 'opacity-55': item.is_active === false }"
        >
          <button
            type="button"
            class="flex w-full items-start gap-3 text-left"
            @click="toggleExpanded(item.id)"
          >
            <span
              class="mt-0.5 min-w-[3.25rem] shrink-0 rounded-sm bg-sky-100 px-1.5 py-1 text-center font-mono text-[11px] font-bold tracking-[0.12em] text-sky-950"
            >
              {{ item.token || '—' }}
            </span>
            <span class="min-w-0 flex-1">
              <span class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span class="truncate text-[14px] font-semibold text-sky-950">{{ item.name }}</span>
                <span
                  v-if="item.add_taxes"
                  class="rounded-sm border border-sky-700 bg-sky-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-sky-950"
                >
                  {{ t('taxes') }}
                </span>
                <span
                  v-if="item.add_subtotals"
                  class="rounded-sm border border-sky-700 bg-sky-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-sky-950"
                >
                  {{ t('subtotal') }}
                </span>
                <span
                  v-if="item.is_active === false"
                  class="rounded-sm bg-slate-200 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-700"
                >
                  {{ t('common.inactive') }}
                </span>
              </span>
            </span>
            <Icon
              name="fa6-solid:chevron-down"
              class="mt-1 size-3 shrink-0 text-sky-500 transition-transform"
              :class="{ 'rotate-180': expandedId === item.id }"
            />
          </button>

          <div
            v-if="expandedId === item.id"
            class="mt-2 ml-[4rem] rounded-sm border border-sky-200 bg-white px-3 py-2"
          >
            <FieldDetail :label="t('common.code')" :value="item.token" />
            <FieldDetail :label="t('common.name')" :value="item.name" />
            <FieldDetail :label="t('taxes')" :value="yesNo(item.add_taxes)" />
            <FieldDetail :label="t('subtotal')" :value="yesNo(item.add_subtotals)" />
            <FieldDetail
              :label="t('common.active')"
              :value="item.is_active === false ? t('common.inactive') : t('common.active')"
            />
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>
