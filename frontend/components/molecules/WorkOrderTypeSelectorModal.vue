<script setup>
import { ref, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const open = defineModel('open', { type: Boolean, default: false });

const props = defineProps({
  orderTypes: {
    type: Array,
    default: () => [],
  },
  excludedTypeIds: {
    type: Array,
    default: () => [],
  },
  title: {
    type: String,
    default: null,
  },
  warning: {
    type: String,
    default: null,
  },
});

const emit = defineEmits(['select']);

const searchText = ref('');

const titleText = computed(() =>
  props.title ?? `${t('common.select')} ${t('order_block.order_type')}`,
);

const filteredTypes = computed(() => {
  const query = searchText.value.trim().toLowerCase();
  if (!query) return props.orderTypes;
  return props.orderTypes.filter(
    (item) =>
      (item.name || '').toLowerCase().includes(query) ||
      (item.token || '').toLowerCase().includes(query),
  );
});

const isExcluded = (type) => props.excludedTypeIds.includes(type.id);

watch(open, (isOpen) => {
  if (!isOpen) searchText.value = '';
});

const close = () => {
  open.value = false;
};

const handleBackdropClick = () => {
  close();
};

const selectType = (type) => {
  if (isExcluded(type)) return;
  emit('select', type);
  close();
};
</script>

<template>
  <Teleport to="body">
    <div v-if="open">
      <div class="fixed inset-0 bg-black bg-opacity-50 z-[60]" @click="handleBackdropClick" />
      <div class="fixed inset-0 z-[70] flex items-center justify-center overflow-y-auto p-4" role="dialog"
        aria-modal="true" aria-labelledby="work-order-selector-title" @click="handleBackdropClick">
        <div class="bg-white rounded-lg shadow-xl p-6 max-w-lg w-full relative" @click.stop>
          <button type="button" class="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            :aria-label="t('common.cancel')" @click="close">
            <Icon name="fa6-solid:xmark" class="text-xl" />
          </button>

          <p id="work-order-selector-title" class="text-base font-semibold text-slate-700 mb-3 pr-8">
            {{ titleText }}
          </p>

          <p v-if="warning"
            class="flex items-center gap-2 text-sm font-semibold text-amber-700 bg-amber-50 border border-amber-300 rounded-md px-3 py-2 mb-3">
            <Icon name="fa6-solid:triangle-exclamation" class="text-amber-500" />
            {{ warning }}
          </p>

          <input v-model="searchText" type="text" :placeholder="t('common.search')" autocomplete="off"
            class="w-full border border-slate-300 rounded-md px-3 py-2 text-sm text-slate-700 mb-3 focus:outline-none" />

          <ul v-if="filteredTypes.length"
            class="max-h-72 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-md">
            <li v-for="type in filteredTypes" :key="type.id">
              <button type="button" :disabled="isExcluded(type)" @click="selectType(type)"
                class="w-full flex items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-white">
                <Icon name="fa6-solid:screwdriver-wrench" class="text-slate-400" />
                <span class="font-medium text-slate-700">{{ type.name }}</span>
                <span v-if="type.token" class="text-xs text-slate-400">{{ type.token }}</span>
              </button>
            </li>
          </ul>
          <p v-else class="text-sm text-slate-400 py-6 text-center">{{ t('common.no_records') }}</p>

          <div class="flex justify-end gap-2 mt-4">
            <button type="button" class="button-default" @click="close">{{ t('common.cancel') }}</button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
