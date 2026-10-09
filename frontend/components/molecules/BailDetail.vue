<script setup>
// components/organisms/ClusterDetail.vue
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';

const { $BailApiService } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  data: Object,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  },
  hideContract: {
    type: Boolean,
    default: false
  },
  disabled: Boolean,
});

const emit = defineEmits(['show-detail', 'change']);

const pending = ref(false);
const localData = ref(props.data || null);

const returnBail = async () => {
  //TODO: retornar bail
  await $BailApiService.doReturn(localData.value.id);
  emit('change');
}

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

const getData = async () => {
  pending.value = true;
  try {
    const result = await $BailApiService.getDetail(props.id);

    localData.value = result
  } catch (err) {
    console.error(err)
  } finally {
    pending.value = false;
  }
}

onMounted(async () => {
  if (props.id && !props.data) {
    await getData();
  }
})

watch(() => props.id, async () => {
  await getData();
});

watch(() => props.data, () => {
  localData.value = props.data;
}, { deep: true, immediate: true });

</script>

<template>
  <div v-if="!pending && localData" id="wrapper" class="text-base">
    <div role="row" class="">
      <FieldDetail :label='$t("bail")' :value=localData.token />

    </div>
    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("billing_block.payment")' :value="localData.payment_date? formatDate(localData.payment_date) : '-'" />
      <FieldDetail :label='$t("product")'>
        <span v-if="isSubRegion && localData.product">{{ localData.product.name }}</span>
        <div v-else-if="!isSubRegion && localData.product" class="flex gap-2">
          <button @click="showDetail('ProductRegion', localData.product.id)" class="text-start text-sky-500 underline">
            <span>{{ localData.product.name }}</span>
          </button>
          <AtomsRedirectButton :id="localData.product.id" :path="'/pricing/products/'" />
        </div>
      </FieldDetail>
    </div>
    <div v-if="!hideContract" role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("contract")'>
        <span v-if="isSubRegion && localData.contract">{{ localData.contract.token }} - 
          {{ localData.contract.holder? localData.contract.holder.name : localData.contract.holder_name }} 
          {{ localData.contract.holder? localData.contract.holder.surname : localData.contract.holder_surname }}
        </span>
        <div v-else-if="!isSubRegion && localData.contract" class="flex gap-2">
          <button @click="showDetail('ContractRegion', localData.contract.id)"
            class="text-start text-sky-500 underline">
            <span>{{ localData.contract.token }} - {{ localData.contract.holder_name }} {{
              localData.contract.holder_surname }}</span>
          </button>
          <AtomsRedirectButton :id="localData.contract.id" :path="'/contract/contracts/'" />
        </div>
      </FieldDetail>
      <FieldDetail :label='$t("billing_block.contract_status")' :value="localData.contract?.status_name" class="items-center">
        <span>
          <AtomsColorBadge :color="localData.contract?.status_color" :value="localData.contract?.status_name">
          </AtomsColorBadge>
        </span>
      </FieldDetail>
    </div>
    <hr v-if="!hideContract" class="my-2" />
    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("common.amount")' :value=localData.amount />
      <FieldDetail :label='$t("common.status")' :value="localData.status?.name || localData.token" class="items-center">
        <span>
          <AtomsColorBadge :color="localData.status?.color" :value="localData.status?.name"></AtomsColorBadge>
          <!-- <button class="px-2 py-1 text-gray-500" @click="emit('clickChangeStatus')"><Icon name="fa6-solid:pencil" /></button> -->
        </span>
      </FieldDetail>
    </div>
    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail :label='$t("invoice")'>
        <span v-if="isSubRegion && localData.invoice && localData.invoice.serie_final">{{ localData.invoice.serie_final }}</span>
        <button v-else-if="!isSubRegion && localData.invoice && localData.invoice.serie_final"
          @click="showDetail('InvoiceRegion', localData.invoice.id)" class="text-start text-sky-500 underline">
          <span>{{ localData.invoice.serie_final }}</span>
        </button>
        <span v-else>-</span>
      </FieldDetail>
      <!-- <button v-if="localData.status.token === 'pendent'" class="mr-20 font-semibold border border-sky-200 hover:border-sky-600 hover:bg-sky-100 text-sky-500 hover:text-sky-600" @click="returnBail()">
        {{ t('Retornar fiança') }}</button> -->
    </div>
    <div role="row" class="grid grid-cols-2 gap-3">
      <FieldDetail v-if="localData.status.token === 'retornat'" :label='$t("common.returned")'
        :value="localData.return_date ? formatDate(localData.return_date) : '-'" />
    </div>

  </div>

  <div v-else>
    <div class="flex justify-center">
      <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>

  </div>

</template>
