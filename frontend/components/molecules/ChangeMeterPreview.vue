<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';

const { t } = useI18n();
const toast = useToast();
const { $OrderApiService } = useNuxtApp();

const props = defineProps({
  id: { type: Number, required: true }, // Order id
  isSubRegion: { type: Boolean, default: false },
  refreshKey: { type: Number, default: 0 },
});
const emit = defineEmits(['create-meter', 'applied']);

const loading = ref(true);
const data = ref(null);

const getData = async () => {
  loading.value = true;
  try {
    data.value = await $OrderApiService.previewChangeMeter(props.id);
  } catch (err) {
    console.error(err);
  } finally {
    loading.value = false;
  }
}

onMounted(getData);
watch(() => props.refreshKey, getData);

const readyToApply = computed(() =>
  !!data.value && data.value.meter_old?.matches && data.value.meter_new?.exists
);

const applying = ref(false);

const applyChangeMeter = async () => {
  if (!readyToApply.value || applying.value) return;
  applying.value = true;
  try {
    const result = await $OrderApiService.applyChangeMeter(props.id);
    if (result?.applied) {
      toast.success(t('order_block.change_meter_applied_ok'));
      emit('applied');
    } else {
      toast.error(t('order_block.change_meter_applied_error'));
    }
  } catch (err) {
    console.error(err);
    toast.error(t('order_block.change_meter_applied_error'));
  } finally {
    applying.value = false;
  }
}
</script>

<template>
  <div class="text-base p-1">
    <H1Region class="mb-3">{{ t('order_block.preview_change_meter') }}</H1Region>

    <div v-if="loading" class="flex justify-center items-center p-4">
      <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
    </div>

    <div v-else-if="data" class="space-y-4">
      <div v-if="data.supply_point" class="text-sm text-slate-500">
        {{ t('supply_point') }}: <span class="font-medium text-slate-700">{{ data.supply_point.token }}</span>
        <div>{{ data.supply_point.address }}</div>
      </div>

      <!-- Comptador sortint -->
      <div class="border border-gray-300 rounded p-4 bg-white">
        <h3 class="font-medium text-slate-700 mb-3">{{ t('order_block.outgoing_meter') }}</h3>
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>
            <div class="text-slate-400">{{ t('order_block.form_code') }}</div>
            <div class="font-medium">{{ data.meter_old?.form_code ?? '-' }}</div>
          </div>
          <div>
            <div class="text-slate-400">{{ t('order_block.system_code') }}</div>
            <div class="font-medium">{{ data.meter_old?.system_meter?.code ?? '-' }}</div>
          </div>
          <div class="col-span-2">
            <div class="text-slate-400">{{ t('order_block.reading_old') }}</div>
            <div class="font-medium">{{ data.reading_old ?? '-' }}</div>
          </div>
        </div>

        <div v-if="!data.meter_old?.matches"
          class="mt-3 flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2">
          <Icon name="fa6-solid:triangle-exclamation" />
          <span>{{ t('order_block.meter_mismatch') }}</span>
        </div>
        <div v-else class="mt-3 flex items-center gap-2 text-sm text-green-700">
          <Icon name="fa6-solid:circle-check" />
          <span>{{ t('order_block.meter_matches') }}</span>
        </div>
      </div>

      <!-- Comptador entrant -->
      <div class="border border-gray-300 rounded p-4 bg-white">
        <h3 class="font-medium text-slate-700 mb-3">{{ t('order_block.incoming_meter') }}</h3>
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>
            <div class="text-slate-400">{{ t('order_block.form_code') }}</div>
            <div class="font-medium">{{ data.meter_new?.form_code ?? '-' }}</div>
          </div>
          <div class="col-span-2">
            <div class="text-slate-400">{{ t('order_block.reading_new') }}</div>
            <div class="font-medium">{{ data.reading_new ?? '-' }}</div>
          </div>
        </div>

        <div v-if="data.meter_new?.exists"
          class="mt-3 flex items-center gap-2 text-sm text-green-700">
          <Icon name="fa6-solid:circle-check" />
          <span>{{ t('order_block.meter_exists') }}</span>
        </div>
        <div v-else class="mt-3 flex items-center justify-between gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2">
          <span class="flex items-center gap-2">
            <Icon name="fa6-solid:triangle-exclamation" />
            {{ t('order_block.meter_not_exists') }}
          </span>
          <button type="button" @click="emit('create-meter', data.meter_new?.form_code)"
            class="px-2 py-1 rounded-md text-xs font-medium bg-sky-500 text-white hover:bg-sky-600 whitespace-nowrap">
            {{ t('order_block.create_meter') }}
          </button>
        </div>
      </div>
      <div v-if="readyToApply" class="flex justify-end pt-2">
        <button type="button" @click="applyChangeMeter" :disabled="applying"
          class="px-4 py-2 rounded-md text-sm font-medium flex items-center gap-2 bg-sky-500 text-white hover:bg-sky-600 transition-colors disabled:opacity-60">
          <Icon v-if="applying" name="fa6-solid:spinner" class="animate-spin" />
          <Icon v-else name="fa6-solid:gauge" />
          {{ t('order_block.apply_change_meter') }}
        </button>
      </div>
    </div>
  </div>
</template>