<script setup>
import { ref, computed, onMounted } from 'vue';

const props = defineProps({
  modelValue: {
    type: [Number, String, null],
    default: null,
  },
  excludeTokens: {
    type: Array,
    default: () => ['BALANCE'],
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
const paymentTypeOptions = ref([]);
const paymentTypeOptionsById = ref([]);

const excludeSet = computed(() => new Set(props.excludeTokens ?? []));

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

const fetchPaymentTypes = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await $ConfiglistApiService.getAll('contract/contract-payment-type');
    const list = response.results.filter((item) => !excludeSet.value.has(item.token));
    paymentTypeOptions.value = list;
    const byId = [];
    list.forEach((item) => {
      byId[item.id] = item;
    });
    paymentTypeOptionsById.value = byId;
    emit('loaded', { options: list, byId });
  } catch (e) {
    error.value = e;
  } finally {
    loading.value = false;
  }
};

const getTypeById = (id) => {
  if (isEmptyModel(id)) {
    return null;
  }
  return paymentTypeOptionsById.value[id] ?? null;
};

const onSelectChange = () => {
  emit('change');
};

onMounted(() => {
  fetchPaymentTypes();
});

defineExpose({
  fetchPaymentTypes,
  paymentTypeOptions,
  paymentTypeOptionsById,
  getTypeById,
  loading,
  error,
});
</script>

<template>
  <div class="select-payment-type">
    <div v-if="loading && !paymentTypeOptions.length" class="text-sm text-slate-500">
      {{ t('common.loading') }}...
    </div>
    <div v-else-if="error" class="text-sm text-red-600">
      {{ error.message }}
      <button type="button" class="underline text-sky-500" @click="fetchPaymentTypes">
        {{ t('common.load_again') }}
      </button>
    </div>
    <template v-else>
      <slot name="label">
        <label for="payment_method" :class="resolvedLabelClass">
          <template v-if="showLabelIcons">
            <Icon v-show="!isEmptyModel(modelValue)" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
            <Icon v-show="isEmptyModel(modelValue)" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
          </template>
          <span>{{ t('common.payment_method') }}:</span>
        </label>
      </slot>

      <div v-if="selectWrapperClass" :class="selectWrapperClass">
        <select id="payment_method" v-model="innerValue" :class="[selectClass, { invalid: invalid }]"
          :disabled="disabled" @change="onSelectChange">
          <option :value="null">-- {{ t('common.select_payment_method') }} --</option>
          <option v-for="type in paymentTypeOptions" :key="type.id" :value="type.id">
            {{ type.name }}
          </option>
        </select>
      </div>
      <select v-else id="payment_method" v-model="innerValue" :class="[selectClass, { invalid: invalid }]"
        :disabled="disabled" @change="onSelectChange">
        <option :value="null">-- {{ t('common.select_payment_method') }} --</option>
        <option v-for="type in paymentTypeOptions" :key="type.id" :value="type.id">
          {{ type.name }}
        </option>
      </select>
    </template>
  </div>
</template>
