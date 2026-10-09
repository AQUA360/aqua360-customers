<script setup>
import { ref, watch } from 'vue';
import TimeRelative from '../atoms/TimeRelative.vue';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import IBAN from '../atoms/IBAN.vue';


const { $PaymentApiService } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
});

const emit = defineEmits(['showDetail', 'update:count']);

const pending = ref(false);
const localData = ref(props.data ? props.data : null);

const getData = async () => {
  pending.value = true;
  try {
    const data = await $PaymentApiService.getPaymentMovements(props.id);
    localData.value = data.results;
    emit('update:count', localData.value.length);
  } catch (error) {
    console.error(error);
  } finally {
    pending.value = false;
  }
}

onMounted(() => {
  if (props.id && !props.data) {
    getData();
  }
});

watch(() => props.id, () => {
  if (props.id && !props.data) {
    getData();
  }
});

watch(() => props.data, () => {
  localData.value = props.data;
}, { immediate: true, deep: true });

const showDetail = (component, id) => {
  emit('showDetail', component, id);
}


</script>

<template>
  <div v-if="localData && !pending">
    <div class="max-h-[60vh] overflow-y-auto scrollbar-hide">
      <div
        v-for="movement in localData"
        :class="[
          'items-center py-1 px-2 border-b-2 mb-2 rounded',
          movement.is_positive
            ? 'bg-gradient-to-b from-white/50 to-green-50/50 border-green-500'
            : 'bg-gradient-to-b from-white/50 to-red-50/50 border-red-500'
        ]"
      >
        <div class="flex justify-between items-center">
          <div class="flex items-center gap-1 my-1">
            <span class="flex justify-center items-center"
              :aria-label="movement.is_positive ? $t('common.positive_movement') : $t('common.negative_movement')">
              <Icon :name="movement.is_positive ? 'fa6-solid:arrow-up' : 'fa6-solid:arrow-down'" class="w-3 h-3"
                :class="movement.is_positive ? 'text-green-500' : 'text-red-500'" />
            </span>
            <div class="flex items-center gap-1">
              <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
                <TimeRelative :datetime="movement.timestamp" />
              </p>
              <span class="text-slate-400">·</span>
              <span class="text-sm text-gray-700 mr-3">{{ movement.user?.username ?? t('common.admin') }}</span>
            </div>
          </div>
          <div>
            <span class="text-slate-400 text-sm">{{ formatDateTime(movement.timestamp) }}</span>
          </div>
        </div>
        <div class="grid grid-cols-2 flex items-center mt-2 mb-1">
          <FieldDetail class="col-span-2" :label='$t("common.movement_date")'
            :value='formatDate(movement.movement_date)' />
          <FieldDetail class="col-span-2" :label='$t("common.payment_method")'
            :value='movement.payment_type ? movement.payment_type.name : t("common.no_payment_method")' />
          <FieldDetail v-if="movement.payment_bank" :label='$t("common.account_bank")'>
            <IBAN :value="movement.payment_bank" />
          </FieldDetail>
          <FieldDetail v-if="movement.payment_remittance" :label='$t("common.remittance")'
            :value="movement.payment_remittance.token" />
          <FieldDetail class="col-span-2" v-if="movement.reject_motive" :label='$t("common.return_reason")'
            :value="movement.reject_motive.name" />
            
          <div class="col-span-2 grid grid-cols-2 flex items-center">
            <FieldDetail :label='$t("common.previous_status")'>
              <AtomsColorBadge :value="movement.previous_status?.name" :color="movement.previous_status?.color">
              </AtomsColorBadge>
            </FieldDetail>
            <FieldDetail :label='$t("common.actual_status")'>
              <AtomsColorBadge :value="movement.current_status?.name" :color="movement.current_status?.color">
              </AtomsColorBadge>
            </FieldDetail>
          </div>
        </div>
      </div>
      <div v-if="localData.length === 0" class="mt-2">
        <span class="footering text-sm text-slate-500">{{ $t('common.no_data_found') }}</span>
      </div>
    </div>

  </div>
  <div v-else>
    <div class="flex justify-center items-center h-full">
      <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>
  </div>
</template>