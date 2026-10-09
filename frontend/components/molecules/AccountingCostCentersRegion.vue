<script setup>
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';
import H1Region from '~/components/atoms/H1Region.vue';

const emit = defineEmits(['close', 'changed']);

const { t } = useI18n();
const toast = useToast();
const { $AccountingCostCenterApiService, $PriceRateApiService } = useNuxtApp();

const objectPermissions = ref(null);
const pending = ref(false);
const saving = ref(false);
const error = ref(null);
const localItems = ref([]);
const searchQuery = ref('');

const isAdding = ref(false);
const editingId = ref(null);
const formToken = ref('');
const formName = ref('');

const filteredItems = computed(() => {
  const q = searchQuery.value.trim().toLowerCase();
  if (!q) return localItems.value;
  return localItems.value.filter((item) => {
    const haystack = [item?.token, item?.name].filter(Boolean).join(' ').toLowerCase();
    return haystack.includes(q);
  });
});

const isFormValid = computed(
  () => formToken.value.trim() !== '' && formName.value.trim() !== '',
);

const resetForm = () => {
  formToken.value = '';
  formName.value = '';
  isAdding.value = false;
  editingId.value = null;
};

const startAdd = () => {
  editingId.value = null;
  formToken.value = '';
  formName.value = '';
  isAdding.value = true;
};

const startEdit = (item) => {
  if (!item?.id) return;
  isAdding.value = false;
  editingId.value = item.id;
  formToken.value = item.token ?? '';
  formName.value = item.name ?? '';
};

const cancelForm = () => {
  resetForm();
};

const loadItems = async () => {
  pending.value = true;
  error.value = null;
  try {
    const response = await $AccountingCostCenterApiService.getAll();
    localItems.value = Array.isArray(response) ? response : (response?.results ?? []);
  } catch (err) {
    error.value = err;
    localItems.value = [];
    console.error(err);
  } finally {
    pending.value = false;
  }
};

const saveItem = async () => {
  if (!isFormValid.value || saving.value) return;

  const isEdit = editingId.value != null;
  if (isEdit && !confirm(t('confirmation_text_block.confirm_save'))) return;

  saving.value = true;
  try {
    const payload = {
      token: formToken.value.trim(),
      name: formName.value.trim(),
    };
    if (isEdit) payload.id = editingId.value;

    const response = await $AccountingCostCenterApiService.save(payload);
    if (response) {
      toast.success(t('common.saved_successfully'));
      resetForm();
      await loadItems();
      emit('changed');
    }
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  } finally {
    saving.value = false;
  }
};

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
        {{ t('common.check') }}: {{ t('pricing_block.accounting_cost_centers') }}
      </H1Region>
      <button type="button" class="button-primary flex items-center gap-x-2" :disabled="isAdding || editingId != null"
        @click="startAdd">
        <Icon name="fa6-solid:plus" class="size-3 shrink-0" />
        {{ t('pricing_block.new_accounting_cost_center') }}
      </button>
    </div>

    <span class="input-group mt-3 flex w-80 items-center gap-2">
      <Icon name="fa6-solid:magnifying-glass" class="text-slate-500" />
      <input v-model="searchQuery" type="text" name="search" :placeholder="t('dashboard.search')"
        class="w-full rounded-md p-1 focus:outline-none focus-visible:border-0" autocomplete="off" />
    </span>

    <div v-if="pending" class="py-6 text-sm text-sky-700">
      {{ t('common.loading') }}...
    </div>
    <div v-else-if="error" class="py-4 text-sm">
      <p>{{ t('common.error') }}: {{ error.message }}</p>
      <button type="button" class="text-sky-500 underline hover:no-underline" @click="loadItems">
        {{ t('common.load_again') }}
      </button>
    </div>
    <div v-else class="mt-3 overflow-y-auto" :style="{ maxHeight: 'calc(100vh - 220px)' }">
      <ul class="divide-y divide-sky-100 border-y border-sky-100 text-sm">
        <li v-if="isAdding" class="flex items-center gap-2 bg-sky-50/60 px-2 py-2.5">
          <input v-model="formToken" type="text" class="input !w-24 shrink-0 font-mono text-[12px]"
            :placeholder="t('common.code')" autocomplete="off" @keydown.enter.prevent="saveItem" />
          <input v-model="formName" type="text" class="input min-w-0 flex-1 !w-auto text-[13px]"
            :placeholder="t('common.name')" autocomplete="off" @keydown.enter.prevent="saveItem" />
          <div class="flex shrink-0 items-center gap-1">
            <button type="button" class="button-primary px-2 py-1 text-[11px]" :disabled="!isFormValid || saving"
              @click="saveItem">
              {{ t('common.save') }}
            </button>
            <button type="button"
              class="rounded-lg border border-slate-200 px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-100"
              :disabled="saving" @click="cancelForm">
              {{ t('common.cancel') }}
            </button>
          </div>
        </li>

        <li v-if="!filteredItems.length && !isAdding" class="px-3 py-8 text-center text-sky-500">
          {{ t('common.no_records') }}
        </li>

        <li v-for="item in filteredItems" :key="item.id"
          class="group flex items-center gap-3 px-2 py-2.5 transition-colors">
          <template v-if="editingId === item.id">
            <input v-model="formToken" type="text" class="input !w-24 shrink-0 font-mono text-[12px]"
              :placeholder="t('common.code')" autocomplete="off" @keydown.enter.prevent="saveItem" />
            <input v-model="formName" type="text" class="input min-w-0 flex-1 !w-auto text-[13px]"
              :placeholder="t('common.name')" autocomplete="off" @keydown.enter.prevent="saveItem" />
            <div class="flex shrink-0 items-center gap-1">
              <button type="button" class="button-primary px-2 py-1 text-[11px]" :disabled="!isFormValid || saving"
                @click="saveItem">
                {{ t('common.save') }}
              </button>
              <button type="button"
                class="rounded-lg border border-slate-200 px-2 py-1 text-[11px] text-slate-600 hover:bg-slate-100"
                :disabled="saving" @click="cancelForm">
                {{ t('common.cancel') }}
              </button>
            </div>
          </template>

          <template v-else>
            <span
              class="flex h-8 w-12 shrink-0 items-center justify-center rounded-sm bg-sky-100 font-mono text-[11px] font-bold tracking-[0.1em] text-sky-950"
              :title="t('common.code')">
              {{ item.token || '—' }}
            </span>

            <div class="min-w-0 flex-1">
              <p class="truncate text-[14px] font-semibold leading-tight text-sky-950" :title="item.name">
                {{ item.name }}
              </p>
            </div>

            <div class="flex shrink-0 items-center gap-1">
              <button type="button"
                class="flex h-7 w-7 items-center justify-center rounded-lg border border-sky-100 text-sky-600 transition-colors hover:border-none hover:bg-sky-100 hover:text-sky-950"
                :title="t('common.edit')" :aria-label="t('common.edit')" :disabled="isAdding || editingId != null"
                @click="startEdit(item)">
                <Icon name="fa6-solid:pencil" class="size-3" />
              </button>
            </div>
          </template>
        </li>
      </ul>
    </div>
  </div>
</template>
