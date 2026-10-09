<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import VerifactuBatchRegion from './VerifactuBatchRegion.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import ModelLogs from '../molecules/ModelLogs.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);
const router = useRouter();
const { $VerifactuApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const SubRegion = ref(props.isSubRegionOpen);
const activeTab = ref('details');

// Verifactu invoice statuses colors:
const invoiceStatusesColors = {
  'Correcto': 'green',
  'Incorrecto': 'red',
  'AceptadoConErrores': 'yellow'
}

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $VerifactuApiService.getDetail(props.id);
    data.value = result;
  } catch (err) {
    error.value = err;
    console.error(err);
  } finally {
    pending.value = false;
  }
}

watch(() => props.id, () => {
  if (props.id) {
    getData();
    closeSubRegion();
  }
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}

const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const setActiveTab = (tab) => {
  activeTab.value = tab;
}

onMounted(() => {
  if (props.id) {
    getData();
  }
});

</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="data" class="relative transition-all duration-500 ease" :class="{ 'mr-[48%]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('billing_block.verifactu_invoice') }}</H1Region>
      </div>

      <div class="mt-4" id="item_data" :data-rel="id">
        <div class="flex flex-col mb-4">
          <div class="grid grid-cols-2 gap-3">
            <FieldDetail :label='$t("common.identification")' :value="data.token"></FieldDetail>
            <FieldDetail :label='$t("common.creation_date")' :value="formatDate(data.created_at)"></FieldDetail>
            <FieldDetail :label='$t("common.status")'>
              <AtomsColorBadge :value="t(`common.verifactu_invoice_status.${data.response_status}`)" :color="invoiceStatusesColors[data.response_status]" />
            </FieldDetail>
          </div>
        </div>

        <hr class="my-4" />

        <div class="flex flex-col mb-4">
          <div class="grid grid-cols-2 gap-3">
            <FieldDetail :label='$t("invoice")' v-if="data.invoice_id">
                {{ data.invoice_token || data.invoice?.token || '-' }}
            </FieldDetail>
            <FieldDetail :label='$t("common.validation")' v-if="data.verifactu_qr">
              <a :href="data.verifactu_qr" target="_blank" class="cursor-pointer flex items-center gap-2">
                <Icon name="material-symbols:qr-code" class="h-5" />
                <span>{{ $t('common.view') }}</span>
              </a>
            </FieldDetail>
            <FieldDetail class="col-span-2" :label='$t("billing_block.verifactu_hash")'>
              <span class="text-black-900 break-words overflow-hidden">{{ data.verifactu_hash || '-' }}</span>
            </FieldDetail>
            <FieldDetail class="col-span-2" :label='$t("common.message")' :value="data.message || '-'"></FieldDetail>
          </div>
        </div>

        <AtomsTabs class="py-2">
          <li class="me-2">
            <a href="#tab_details" @click.prevent="setActiveTab('details')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'details', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'details' }">
              <Icon name="fa6-solid:circle-info" class="display-inline mr-2" /> {{ $t("billing_block.hash_detail") }}
            </a>
          </li>
          <li class="me-2">
            <a href="#tab_history" @click.prevent="setActiveTab('history')"
              :class="{ 'text-sky-600 border-sky-600': activeTab === 'history', 'hover:text-gray-600 hover:border-gray-300': activeTab !== 'history' }">
              <Icon name="fa6-solid:clock-rotate-left" class="display-inline mr-2" /> {{ $t("common.history_changes") }}
            </a>
          </li>
        </AtomsTabs>

        <div id="verifactu_invoice_tabpanels">
          <section v-show="activeTab === 'details'" role="tabpanel" id="tab_details" class="bg-white antialiased">
            <div class="flex flex-col mb-4">
              <h3 class="text-lg font-semibold mb-3">{{ $t('billing_block.verifactu_hash_fields') }}</h3>
              <div class="grid grid-cols-2 gap-3">
                <FieldDetail label="ID Emisor" :value="data.hash_IDEmisor || '-'"></FieldDetail>
                <FieldDetail label="Número Serie" :value="data.hash_NumSerie || '-'"></FieldDetail>
                <FieldDetail label="Fecha Expedición" :value="data.hash_FechaExpedicion || '-'"></FieldDetail>
                <FieldDetail label="Tipo Factura" :value="data.hash_TipoFactura || '-'"></FieldDetail>
                <FieldDetail label="Cuota Total" :value="data.hash_CuotaTotal || '-'"></FieldDetail>
                <FieldDetail label="Importe Total" :value="data.hash_ImporteTotal || '-'"></FieldDetail>
                <FieldDetail label="Huella">
                  <span class="text-black-900 break-words overflow-hidden">{{ data.hash_Huella || '-' }}</span>
                </FieldDetail>
                <FieldDetail label="Fecha Hora Huso Gen Registro" :value="data.hash_FechaHoraHusoGenRegistro || '-'"></FieldDetail>
              </div>
            </div>
          </section>

          <section v-show="activeTab === 'history'" role="tabpanel" id="tab_history" class="bg-white antialiased">
            <div class="mt-2">
              <ModelLogs :object_id="props.id" :object_token="data?.token" :service="$VerifactuApiService"
                :title="`${t('common.history_changes')} ${data?.token || ''}`" />
            </div>
          </section>
        </div>
      </div>
    </div>

    <div v-if="SubRegion == true && showRegionDetailComponent != null" role="region" id="subregion"
      class="h-[100vh] border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white overflow-x-hidden fixed top-0 right-0 w-[48%] z-100 overflow-y-auto"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <VerifactuBatchRegion v-if="showRegionDetailComponent === 'VerifactuBatchRegion'" :id="regionDetailId"
          :isSubRegion="true" @close-subregion="closeSubRegion" @changed="getData" />
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId"
          :isSubRegion="true" @close-subregion="closeSubRegion" @changed="getData" />
      </div>
    </div>
  </div>
</template>
