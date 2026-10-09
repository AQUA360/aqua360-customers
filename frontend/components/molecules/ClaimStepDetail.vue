<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import DurationDays from '../atoms/DurationDays.vue';
import ClaimStepMiniDetail from './ClaimStepMiniDetail.vue';

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
const showDetail = function (component, id) {
  emit('show-detail', component, id);
}

onMounted(async () => {
})

watch(() => props.data, (newValue) => async () => {
  console.log("watch data")
  console.log(newValue)
  data.value = newValue;
}, { immediate: true, deep: true });


</script>

<template>
  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.identification")' :value=data?.token></FieldDetail>
    <FieldDetail :label='$t("billing_block.step")' :value=data?.name></FieldDetail>
  </div>

  <div role="row" class="grid grid-cols-2">
    <FieldDetail :label='$t("common.duration")'>
      <DurationDays :value="data" />
    </FieldDetail>
  </div>
  <!-- <div v-if="data?.description" role="row" class="">
    <FieldDetail :label='$t("Descripció")' :value=data?.description></FieldDetail>
  </div> -->
  
  <hr v-if="data?.next_step" class="my-2" />
  <div role="row" class="">
    <FieldDetail v-if="data?.next_step" :label='$t("common.next")'>
      <span v-if="isSubRegion">{{ data?.next_step_name }}</span>
      <button v-else @click="showDetail('ClaimStepRegion', data?.next_step_id)"
        class="text-start text-sky-500 underline">{{ data?.next_step_name }}</button>
    </FieldDetail>
  </div>




</template>
