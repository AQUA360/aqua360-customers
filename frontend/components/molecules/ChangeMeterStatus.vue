<script setup>
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  orderId: { type: Number, required: true },
  orderType: { type: String, default: null },
  refreshKey: { type: Number, default: 0 },
  alreadyApplied: { type: Boolean, default: false },
});
const emit = defineEmits(['preview']);

const { $OrderApiService } = useNuxtApp();

const CHANGE_METER_ORDER_TYPES = ['change_meter', 'install_meter'];
const isChangeMeter = computed(() =>
  CHANGE_METER_ORDER_TYPES.includes((props.orderType || '').toLowerCase())
);

const checking = ref(false);
const checkFailed = ref(false);
const canApply = ref(false);
const missingFields = ref([]);

const validate = async () => {
  if (!isChangeMeter.value) return;
  checking.value = true;
  checkFailed.value = false;
  try {
    const result = await $OrderApiService.validateChangeMeter(props.orderId);
    canApply.value = result?.can_apply || false;
    missingFields.value = result?.missing_fields || [];
  } catch (err) {
    console.error(err);
    checkFailed.value = true;
    canApply.value = false;
    missingFields.value = [];
  } finally {
    checking.value = false;
  }
};

onMounted(validate);
watch(() => [props.orderId, props.orderType, props.refreshKey], validate);
</script>

<template>
  <div v-if="isChangeMeter" class="mb-4 rounded-md border p-3 text-sm" :class="{
    'bg-green-50 border-green-200 text-green-800': !checking && !checkFailed && (canApply || alreadyApplied),
    'bg-amber-50 border-amber-200 text-amber-800': !checking && (checkFailed || (!canApply && !alreadyApplied)),
    'bg-slate-50 border-slate-200 text-slate-600': checking,
  }">
    <div v-if="checking" class="flex items-center gap-2">
      <Icon name="fa6-solid:spinner" class="animate-spin" />
      <span>{{ t('common.loading') }}...</span>
    </div>

    <div v-else-if="checkFailed" class="flex items-center gap-2">
      <Icon name="fa6-solid:triangle-exclamation" />
      <span>{{ t('order_block.change_meter_check_error') }}</span>
    </div>

    <div v-else-if="alreadyApplied" class="flex items-center gap-2">
      <Icon name="fa6-solid:circle-check" />
      <span>
        {{ t('order_block.change_meter_applied_to_system') }}
        {{ t('order_block.suggest_status_change') }}
      </span>
    </div>

    <div v-else-if="canApply" class="flex items-center justify-between gap-3">
      <div class="flex items-center gap-2">
        <Icon name="fa6-solid:circle-check" />
        <span>{{ t('order_block.change_meter_ready') }}</span>
      </div>
      <button type="button" @click="emit('preview')"
        class="px-3 py-1.5 rounded-md text-sm font-medium flex items-center gap-2 bg-sky-500 text-white hover:bg-sky-600 transition-colors">
        <Icon name="fa6-solid:eye" />
        {{ t('order_block.preview_change_meter') }}
      </button>
    </div>

    <div v-else>
      <div class="flex items-center gap-2 font-medium">
        <Icon name="fa6-solid:triangle-exclamation" />
        <span>{{ t('order_block.change_meter_missing') }}</span>
      </div>
      <ul class="mt-1 list-disc list-inside">
        <li v-for="field in missingFields" :key="field">{{ field }}</li>
      </ul>
    </div>
  </div>
</template>