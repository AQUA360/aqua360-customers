<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import DurationDays from '../atoms/DurationDays.vue';

const { $ClaimRequestApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
});

const emit = defineEmits(['show-detail', 'change']);

const toast = useToast();
const isLoading = ref(false);
const error = ref(null);

const localData = ref(props.data ? { ...props.data } : null);

const showDetail = function (component, id) {

  emit('show-detail', component, id);
}

const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $ClaimRequestApiService.getDetail(props.id);
    localData.value = detail;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }

};


onMounted(async () => {
  if (!props.data && props.id) {
    fetchData();
  }
})


watch(() => props.data, (newValue) => async () => {
  data.value = newValue;
}, { immediate: true });

watch(() => props.id, (newValue) => async () => {
  if (!props.data && props.id) {
    fetchData();
  }
}, { immediate: true });


</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <span class="text-red-600">{{
      $t("common.error_load")
      }}</span>
  </div>
  
  <div v-else-if="localData">
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.code")' :value=localData.token></FieldDetail>
      <FieldDetail :label='$t("common.status")'>
        <AtomsColorBadge :value="localData.status_name" :color="localData.status_color">
        </AtomsColorBadge>
      </FieldDetail>
    </div>
    
    <div v-if="localData.description" role="row" class="">
      <FieldDetail :label='$t("common.description")' :value=localData.description></FieldDetail>
    </div>
    
    <hr class="my-2" />
    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("billing_block.step")'>
        <span v-if="isSubRegion">{{ localData.current_step.name }}</span>
        <button v-else @click="showDetail('ClaimStepRegion', localData.current_step.id, null)"
        class="text-start text-sky-500 underline">{{ localData.current_step.name }}</button>
      </FieldDetail>
      <FieldDetail :label='$t("common.duration")'>
        <DurationDays :value="localData.current_step" />
      </FieldDetail>
      <FieldDetail :label='$t("billing_block.due_step")' :value="localData.current_step_due_date ? formatDate(localData.current_step_due_date) : '-'">
      </FieldDetail>
      <FieldDetail :label='$t("contract_block.total_contracts")' :value="(localData.total_contracts).toString()"></FieldDetail>
      <FieldDetail :label='$t("billing_block.total_invoice")' :value="(localData.invoices.length).toString()"></FieldDetail>
      <FieldDetail :label='$t("common.total")' :value=formatMoneyWithCurrency(localData.amount)></FieldDetail>
    </div>
  </div>

</template>
