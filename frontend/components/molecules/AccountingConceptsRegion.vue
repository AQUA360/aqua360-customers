<script setup>
import { ref, computed, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import H1Region from '~/components/atoms/H1Region.vue';
import AccountingConceptsEdit from '../organisms/AccountingConceptsEdit.vue';

const props = defineProps({
  items: {
    type: Array,
    default: null,
  },
  categories: {
    type: Array,
    default: () => [],
  },
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['close', 'changed', 'show-subregion']);

const { t } = useI18n();
const toast = useToast();
const { $AccountingConceptApiService, $PriceRateApiService } = useNuxtApp();

const objectPermissions = ref(null);
const pending = ref(false);
const deactivatingId = ref(null);
const error = ref(null);
const localItems = ref([]);
const searchQuery = ref('');

const sourceItems = computed(() =>
  Array.isArray(props.items) ? props.items : localItems.value,
);

const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const filteredItems = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return sourceItems.value;
  return sourceItems.value.filter((item) => {
    const haystack = [
      item?.token,
      item?.name,
      item?.category,
      item?.type?.token,
      item?.type?.name,
    ]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return haystack.includes(q);
  });
});

const categoryLabel = (token) =>
  props.categories.find((item) => item.token === token)?.name || token || '—';

const loadItems = async () => {
  if (Array.isArray(props.items)) return;
  pending.value = true;
  error.value = null;
  try {
    const response = await $AccountingConceptApiService.getAll();
    localItems.value = Array.isArray(response) ? response : (response?.results ?? []);
  } catch (err) {
    error.value = err;
    localItems.value = [];
    console.error(err);
  } finally {
    pending.value = false;
  }
};

const deactivateItem = async (item) => {
  if (!item?.id) return;
  if (!confirm(item.is_active ? t('confirmation_text_block.confirm_deactivate') : t('confirmation_text_block.confirm_activate'))) return;

  deactivatingId.value = item.id;
  try {
    const payload = {
      id: item.id,
      is_active: !item.is_active,
    }
    const response = await $AccountingConceptApiService.save(payload);
    if (response) {
      toast.success(t('common.saved_successfully'));
      await loadItems();
      emit('changed');
    }
  } catch (err) {
    console.error(err);
  } finally {
    deactivatingId.value = null;
  }
};

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  regionDetailId.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showDetail = async function (component, id) {
  await closeSubRegion(); 
  showRegionDetailComponent.value = component
  regionDetailId.value = id;
  showSubRegion();
}

const refresh = async () => {
  await closeSubRegion()
  await loadItems();
  emit('changed');
}

watch(
  () => props.items,
  () => {
    if (!Array.isArray(props.items)) loadItems();
  },
);

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

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
  <div v-if="objectPermissions?.can_view" class="region__content">
    <div class="pr-4" :class="{ 'h-full overflow-y-auto': !isSubRegion, 'mr-[50%]': SubRegion }">

      <div class="flex flex-wrap items-start justify-between gap-3">
        <H1Region class="!mb-0">
          {{ t('common.check') }}: {{ t('pricing_block.accounting_concepts') }}
        </H1Region>
        <button type="button" class="button-primary flex items-center gap-x-2" @click="showDetail('AccountingConceptsEdit', null)">
          <Icon name="fa6-solid:plus" class="size-3 shrink-0" />
          {{ t('pricing_block.new_accounting_concept') }}
        </button>
      </div>
  
      <span class="input-group mt-3 flex w-80 items-center gap-2">
        <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
        <input v-model="searchQuery" type="text" name="search" :placeholder="t('dashboard.search')"
          class="w-full rounded-md p-1 focus:outline-none focus-visible:border-0" autocomplete="off" />
      </span>
  
      <!-- <hr class="my-3 border-sky-100" /> -->
  
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
        <ul class="divide-y divide-sky-100 border-y border-sky-100 text-sm">
          <li v-if="!filteredItems.length" class="px-3 py-8 text-center text-sky-500">
            {{ t('common.no_records') }}
          </li>
          <li v-for="item in filteredItems" :key="item.id"
            class="group flex items-center gap-3 px-2 py-2.5 transition-colors"
            :class="{ 'opacity-55': item.is_active === false }">
            <span
              class="flex h-8 w-12 shrink-0 items-center justify-center rounded-sm bg-sky-100 font-mono text-[11px] font-bold tracking-[0.1em] text-sky-950"
              :title="t('common.code')">
              {{ item.token || '—' }}
            </span>
  
            <div class="min-w-0 flex-1">
              <div class="flex min-w-0 items-center gap-2">
                <p class="truncate text-[14px] font-semibold leading-tight text-sky-950" :title="item.name">
                  {{ item.name }}
                </p>
                <span v-if="item.is_active === false"
                  class="shrink-0 rounded-sm bg-slate-200 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-700">
                  {{ t('common.inactive') }}
                </span>
              </div>
              <p class="mt-0.5 truncate text-[11px] text-sky-700">
                <span class="uppercase tracking-[0.08em]">{{ categoryLabel(item.category) }}</span>
                <span v-if="item.type?.name" class="text-sky-300"> · </span>
                <span v-if="item.type?.name">{{ item.type.name }}</span>
              </p>
            </div>
  
            <div class="flex shrink-0 items-center gap-1">
              <button type="button"
                class="flex h-7 w-7 items-center justify-center rounded-sm text-sky-600 transition-colors border border-sky-100 hover:border-none rounded-lg hover:bg-sky-100 hover:text-sky-950"
                :title="t('common.edit')" :aria-label="t('common.edit')" @click="showDetail('AccountingConceptsEdit', item.id)">
                <Icon name="fa6-solid:pencil" class="size-3" />
              </button>
              <button type="button"
                class="flex h-7 w-7 items-center justify-center rounded-sm transition-colors border hover:border-none rounded-lg disabled:opacity-50"
                :class="{ 'border-red-100 hover:text-red-600 hover:bg-red-50 text-red-600': item.is_active, 'border-green-100 hover:text-green-600 hover:bg-green-50 text-green-600': !item.is_active }"
                :title="item.is_active ? t('common.deactivate') : t('common.activate')" :aria-label="item.is_active ? t('common.deactivate') : t('common.activate')"
                :disabled="deactivatingId === item.id" @click="deactivateItem(item)">
                <Icon :name="item.is_active ? 'fa6-solid:ban' : 'fa6-solid:arrow-rotate-left'" class="size-3"/>
              </button>
            </div>
          </li>
        </ul>
      </div>
    </div>
    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease text-base bg-white flex flex-col overflow-hidden fixed top-0 right-0 w-[48%] z-10"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto pb-24 pr-2">
        <AccountingConceptsEdit v-if="showRegionDetailComponent === 'AccountingConceptsEdit'" :id="regionDetailId" 
        @change="refresh" @close="closeSubRegion" />
      </div>
    </div>
  </div>
</template>
