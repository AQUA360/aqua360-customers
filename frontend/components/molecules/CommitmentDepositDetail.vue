<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import PersonDetail from '../molecules/PersonDetail.vue';

const { $CommitmentDepositApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  data: {
    type: Object,
    required: false
  },
  isSubRegion: {
    type: Boolean,
    default: false,
  }
});

const emit = defineEmits(['show-detail', 'edit']);

const isLoading = ref(false);
const error = ref(null);

const localData = ref(props.data ? { ...props.data } : null);

const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $CommitmentDepositApiService.getDetail(props.id);
    localData.value = detail;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }

};

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}


onMounted(() => {
  if (!props.data && props.id) {
    fetchData();
  }
});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});
</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <span class="text-red-600">{{
      $t("common.error_load")
      }}</span>
  </div>

  <div v-else-if="localData">

    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.identification")' :value=localData.token />
      <FieldDetail :label="$t('contract')">
        <div v-if="!isSubRegion" class="flex gap-2">
          <button @click="showDetail('ContractRegion', localData.contract.id)"
            class="text-start text-sky-500 underline">{{ localData.contract.token }}</button>
          <AtomsRedirectButton :id="localData.contract.id" :path="'/contract/contracts/'" />
        </div>
        <span v-else>{{ localData.contract.token }}</span>
      </FieldDetail>
      <FieldDetail :label='$t("common.status")'>
        <AtomsColorBadge :value=localData.status.name :color=localData.status.color />
      </FieldDetail>
      <FieldDetail :label='$t("common.due_date")' :value="localData.due_date ? formatDate(localData.due_date) : '-' " />
    </div>

    <hr class="my-2" />

    <div role="row" class="grid grid-cols-2">
      <FieldDetail class="col-span-2" :label='$t("contract_block.holder")' :value="localData.customer_final + ' (' + localData.customer_token_final + ')'" />
      <FieldDetail :label='$t("address_block.address")' :value=localData.address_final></FieldDetail>
      <FieldDetail :label='$t("address_block.location")' :value="localData.location_final"></FieldDetail>
    </div>

    <hr class="my-2" />

    <div role="row" class="grid grid-cols-2">
      <FieldDetail :label='$t("common.total")' :value="formatMoneyWithCurrency(localData.total)" />
      <FieldDetail :label='$t("common.pending")' :value=formatMoneyWithCurrency(localData.remaining) />
      <FieldDetail :label='$t("common.accumulated")' :value=formatMoneyWithCurrency(localData.remaining_to_share) />
    </div>


    <!-- <fieldset v-if="localData.holder && !isSubRegion" class="py-1 px-5 rounded bg-sky-50 m-4">
      <legend class="px-3 font-semibold bg-white shadow">
        {{ t('Afectat') }}
      </legend>
      <PersonDetail :id="localData.holder"/>
    </fieldset> -->

  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>
