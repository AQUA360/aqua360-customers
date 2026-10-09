<script setup>
import { ref, computed, onMounted } from 'vue';

const props = defineProps({
  modelValue: {
    type: [Number, String, null],
    default: null,
  },
  invalid: {
    type: Boolean,
    default: false,
  },
  labelClass: {
    type: String,
    default: '',
  },
  showLabelIcons: {
    type: Boolean,
    default: false,
  },
  selectClass: {
    type: String,
    default: 'w-full text-base border border-gray-300 rounded p-2',
  },
  selectWrapperClass: {
    type: String,
    default: '',
  },
  modelAsNumber: {
    type: Boolean,
    default: false,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['update:modelValue', 'change', 'loaded']);

const { t } = useI18n();
const { $ConfiglistApiService } = useNuxtApp();

const loading = ref(false);
const error = ref(null);
const categoryOptions = ref([]);
const categoryOptionsById = ref([]);

const resolvedLabelClass = computed(() => {
  if (props.labelClass) {
    return props.labelClass;
  }
  return props.showLabelIcons
    ? 'flex text-sm font-medium text-gray-700 mb-3 gap-2'
    : 'block text-sm font-medium text-slate-500 mb-2';
});

const isEmptyModel = (v) => v === null || v === undefined || v === '';

const innerValue = computed({
  get() {
    return props.modelValue;
  },
  set(v) {
    let next = v;
    if (next === '' || next === undefined) {
      next = null;
    } else if (props.modelAsNumber && next != null) {
      next = Number(next);
    }
    emit('update:modelValue', next);
  },
});

const fetchInvoiceCategories = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await $ConfiglistApiService.getAll('billing/invoice-category');
    const list = response.results || [];
    categoryOptions.value = list;
    const byId = [];
    list.forEach((item) => {
      byId[item.id] = item;
    });
    categoryOptionsById.value = byId;
    emit('loaded', { options: list, byId });
  } catch (e) {
    error.value = e;
  } finally {
    loading.value = false;
  }
};

const getCategoryById = (id) => {
  if (isEmptyModel(id)) {
    return null;
  }
  return categoryOptionsById.value[id] ?? null;
};

const onSelectChange = () => {
  emit('change');
};

onMounted(() => {
  fetchInvoiceCategories();
});

const hasOptions = computed(() => categoryOptions.value.length > 0);

defineExpose({
  fetchInvoiceCategories,
  categoryOptions,
  categoryOptionsById,
  getCategoryById,
  hasOptions,
  loading,
  error,
});
</script>

<template>
  <div class="select-invoice-category">
    <div v-if="loading && !categoryOptions.length" class="text-sm text-slate-500">
      {{ t('common.loading') }}...
    </div>
    <div v-else-if="error" class="text-sm text-red-600">
      {{ error.message }}
      <button type="button" class="underline text-sky-500" @click="fetchInvoiceCategories">
        {{ t('common.load_again') }}
      </button>
    </div>
    <template v-else-if="categoryOptions.length">
      <div v-if="selectWrapperClass" :class="selectWrapperClass">
        <select id="invoice_category" v-model="innerValue" :class="[selectClass, { invalid: invalid }]"
          :disabled="disabled" @change="onSelectChange">
          <option :value="null">-- {{ t('common.select') }} --</option>
          <option v-for="category in categoryOptions" :key="category.id" :value="category.id">
            {{ category.name }}
          </option>
        </select>
      </div>
      <select v-else id="invoice_category" v-model="innerValue" :class="[selectClass, { invalid: invalid }]"
        :disabled="disabled" @change="onSelectChange">
        <option :value="null">-- {{ t('common.select') }} --</option>
        <option v-for="category in categoryOptions" :key="category.id" :value="category.id">
          {{ category.name }}
        </option>
      </select>
    </template>
  </div>
</template>
