<script setup>
// components/organisms/ContractDetail.vue
import { ref, watch, nextTick, onBeforeUnmount, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
// Importar el component SupplyPointRegion per a la subregion
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import BankDetail from '~/components/molecules/BankDetail.vue';
import SepaQuickActions from '~/components/molecules/SepaQuickActions.vue';
import DeliquencyLevel from '~/components/atoms/DelinquencyLevel.vue';
import ContractStatusBadges from '~/components/molecules/ContractStatusBadges.vue';
import { AVAILABLE_LANGUAGES } from '~/utils/languages';

const { t } = useI18n();

const languageLabel = (code) => {
  const lang = AVAILABLE_LANGUAGES.find((l) => l.code === code);
  return lang ? t(lang.name) : null;
};

const props = defineProps({
  data: Object,
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean,
  showPayment: {
    type: Boolean,
    default: true
  },
  showCommunication: {
    type: Boolean,
    default: true
  },
  reducedDetail: {
    type: Boolean,
    default: false
  },
  showImportantObservations: {
    type: Boolean,
    default: true
  },
  canChange: Boolean
});

const { $ContractApiService, $ObservationApiService, $ConfigProjectApiService } = useNuxtApp();

const useMultipleCompanies = ref(false);
const emit = defineEmits(['show-subregion', 'clickChangeTotalPersons', 'change', 'new-call']);
const SubRegion = ref(props.isSubRegionOpen);
const loading = ref(false)

const isEditingPersons = ref(false);
const isEditingRemittance = ref(false);
const totalPersons = ref(props.data?.total_persons ? props.data.total_persons : 3);
const remittance_date = ref(props.data?.remittance_date ? parseInt(props.data.remittance_date) : null);
const localData = ref(props.data ? props.data : null);

const { fireUsageTypeTokens, fetchFireUsageTypeTokens } = useFireUsageTypeTokens();
const isFireContract = computed(() => {
  return localData.value && (
    fireUsageTypeTokens.value.includes(localData.value.use_type_token) ||
    fireUsageTypeTokens.value.includes(localData.value.use_type?.token) ||
    localData.value.is_fire
  );
});

const { fetchSupplyPointCutStatusToken, isSupplyPointCut } = useSupplyPointCutStatusToken();
const isContractSupplyCut = computed(() => isSupplyPointCut(localData.value));

// Mandate history: overlay dropdown (placeholder data until API is wired).
const openMandateHistoryDropdown = ref(false);
const mandateHistoryAnchor = ref(null);
const mandateHistoryPanel = ref(null);
const mandateHistoryPosition = ref({ top: 0, left: 0 });

const updateMandateHistoryPosition = () => {
  const anchorEl = mandateHistoryAnchor.value;
  if (!anchorEl || typeof window === 'undefined') return;

  const rect = anchorEl.getBoundingClientRect();
  const margin = 8;
  const panelWidth = 320;
  let left = rect.right - panelWidth;
  if (left < margin) left = margin;
  if (left + panelWidth + margin > window.innerWidth) {
    left = Math.max(margin, window.innerWidth - panelWidth - margin);
  }

  mandateHistoryPosition.value = {
    top: rect.bottom + 4,
    left,
  };
};

const closeMandateHistoryDropdown = () => {
  openMandateHistoryDropdown.value = false;
};

// Close on page scroll, but keep open when scrolling inside the panel itself.
const onMandateHistoryScroll = (event) => {
  const panel = mandateHistoryPanel.value;
  if (panel && (event.target === panel || panel.contains(event.target))) return;
  closeMandateHistoryDropdown();
};

const toggleMandateHistoryDropdown = () => {
  openMandateHistoryDropdown.value = !openMandateHistoryDropdown.value;
};

watch(openMandateHistoryDropdown, async (open) => {
  if (typeof window === 'undefined') return;

  if (open) {
    await nextTick();
    updateMandateHistoryPosition();
    window.addEventListener('resize', updateMandateHistoryPosition);
    window.addEventListener('scroll', onMandateHistoryScroll, true);
  } else {
    window.removeEventListener('resize', updateMandateHistoryPosition);
    window.removeEventListener('scroll', onMandateHistoryScroll, true);
  }
});

// Invoice details: overlay dropdown to avoid taking a lot of inline space.
const invoiceDropdownOpen = ref(false);
const invoiceDropdownAnchor = ref(null);
const invoiceDropdownPanel = ref(null);
const invoiceDropdownPosition = ref({ top: 0, left: 0, width: 0 });

const updateInvoiceDropdownPosition = () => {
  const anchorEl = invoiceDropdownAnchor.value;
  if (!anchorEl || typeof window === 'undefined') return;

  const rect = anchorEl.getBoundingClientRect();
  const margin = 8;

  // Keep within viewport horizontally.
  const maxWidth = Math.max(0, window.innerWidth - rect.left - margin);
  let width = Math.min(rect.width, maxWidth);
  if (width <= 0) width = Math.min(rect.width, window.innerWidth - margin * 2);

  let left = rect.left;
  if (left + width + margin > window.innerWidth) {
    left = Math.max(margin, window.innerWidth - width - margin);
  }

  invoiceDropdownPosition.value = {
    top: rect.bottom,
    left,
    width
  };
};

const closeInvoiceDropdown = () => {
  invoiceDropdownOpen.value = false;
};

const onInvoiceDropdownKeydown = (e) => {
  if (e.key === 'Escape') {
    e.preventDefault();
    closeInvoiceDropdown();
  }
};

watch(invoiceDropdownOpen, async (open) => {
  if (typeof window === 'undefined') return;

  if (open) {
    await nextTick();
    updateInvoiceDropdownPosition();

    window.addEventListener('keydown', onInvoiceDropdownKeydown);
    window.addEventListener('resize', updateInvoiceDropdownPosition);
    // Scrolling changes the anchor position; close to keep alignment.
    window.addEventListener('scroll', closeInvoiceDropdown);
  } else {
    window.removeEventListener('keydown', onInvoiceDropdownKeydown);
    window.removeEventListener('resize', updateInvoiceDropdownPosition);
    window.removeEventListener('scroll', closeInvoiceDropdown);
  }
});

onBeforeUnmount(() => {
  if (typeof window === 'undefined') return;
  window.removeEventListener('resize', updateMandateHistoryPosition);
  window.removeEventListener('scroll', onMandateHistoryScroll, true);
  window.removeEventListener('keydown', onInvoiceDropdownKeydown);
  window.removeEventListener('resize', updateInvoiceDropdownPosition);
  window.removeEventListener('scroll', closeInvoiceDropdown);
});

const toggleInvoiceDropdown = () => {
  invoiceDropdownOpen.value = !invoiceDropdownOpen.value;
};


const applyRemittanceDate = (value) => {
  remittance_date.value = value;
  if (localData.value) {
    localData.value.remittance_date = value;
  }
};

const emitChange = () => {
  const payload = {
    id: props.data.id,
    total_persons: totalPersons.value ? totalPersons.value : null,
    remittance_date: remittance_date.value ? remittance_date.value : null,
  };
  const shouldRefreshParent = isEditingPersons.value;
  applyRemittanceDate(payload.remittance_date);
  if (localData.value && isEditingPersons.value) {
    localData.value.total_persons = payload.total_persons;
  }
  isEditingPersons.value = false;
  isEditingRemittance.value = false;

  $ContractApiService.save(payload).then((response) => {
    if (response && localData.value) {
      localData.value.remittance_date = response.remittance_date ?? null;
    }
    if (shouldRefreshParent) {
      emit('change');
    }
  });
};

const clearRemittance = async () => {
  const previous = localData.value?.remittance_date ?? remittance_date.value;
  applyRemittanceDate(null);
  isEditingRemittance.value = false;
  await nextTick();
  if (!confirm(t('confirmation_text_block.confirm_delete'))) {
    applyRemittanceDate(previous);
    return;
  }
  $ContractApiService.save({
    id: props.data.id,
    remittance_date: null,
  }).catch((err) => {
    console.error(err);
    applyRemittanceDate(previous);
  });
};

const getData = async () => {
  try {
    const result = await $ContractApiService.getDetail(props.id);
    localData.value = result;
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', showRegionDetailComponent.value, regionDetailId.value);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

const onSepaSaved = (sepaDocument) => {
  if (localData.value?.payment) {
    localData.value.payment.sepa_document = sepaDocument;
  }
};

const startCall = async (item) => {
  emit('new-call', item)
}

onMounted(async () => {
  try {
    const multi = await $ConfigProjectApiService.get('use_multiple_companies');
    useMultipleCompanies.value = multi === true || multi === 'True' || multi === 'true';
  } catch {
    useMultipleCompanies.value = false;
  }
  await fetchFireUsageTypeTokens();
  await fetchSupplyPointCutStatusToken();
  if (props.id && (!props.data || props.data.length == 0)) {
    loading.value = true
    getData()
  }
  console.log('localData', localData.value);
})

watch(() => props.id, (newValue) => {
  loading.value = true
  getData()
})

watch(() => props.data, (newValue) => {
  localData.value = newValue;
}, { deep: true });

</script>

<template>
  <div v-if="loading">
    <div class="p-4">
      <div class="flex justify-center items-center">
        <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
        <span class="ml-2">{{ $t('common.loading') }}...</span>
      </div>
    </div>
  </div>
  <div v-else>
    <div v-if="localData" class="region__content">
      <div class="mb-2">
        <div v-if="localData.active_claim_requests" role="row" class="mb-2">
          <div class="flex justify-center items-center gap-2 border border-sky-500 rounded p-1 w-fit">
            <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-sky-500 my-auto" />
            <span class="text-sky-400 font-semibold">
              {{ $t('informative_block.info_contract_claim') }}
            </span>
          </div>
        </div>

        <div v-if="localData.active_contract_termination" role="row" class="mb-2">
          <div class="flex justify-center items-center gap-2 border border-red-500 rounded p-1 w-fit">
            <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-red-500 my-auto" />
            <span class="text-red-400 font-semibold">
              {{ $t('informative_block.info_contract_termination') }}
            </span>
          </div>
        </div>
        <div v-if="localData.block_billing" role="row" class="mb-2">
          <div class="flex justify-center items-center gap-2 border border-blue-500 rounded p-1 w-fit">
            <Icon name="fa6-solid:sack-xmark" class="font-bold text-blue-500 my-auto" />
            <span class="text-blue-400 font-semibold">
              {{ $t('contract_block.block_billing') }}
            </span>
          </div>
        </div>
      </div>
      <div v-if="showImportantObservations && localData.important_observations.length > 0" class="col-span-3 mb-3">
        <span v-for="observation in localData.important_observations" :key="observation.id"
          class="flex items-center gap-2 text-orange-600 font-semibold p-1 pr-2 text-left border-l-2 border-orange-500 bg-orange-100 rounded-r-md w-fit">
          <Icon name="fa6-solid:circle-exclamation" class="text-orange-600" />
          {{ observation.observation }}
        </span>
      </div>
      <div role="row" class="grid grid-cols-3 gap-x-3">
        <FieldDetail :label="t('common.identification')" :value="localData.token" class="font-bold">
          <button v-if="reducedDetail && !isSubRegion" @click="showDetail('ContractRegion', localData.id)">
            <div class="flex items-center gap-2 text-start text-sky-500 hover:underline">
              <span>{{ localData.token }}</span>
              <Icon v-if="isFireContract" name="mdi:fire-hydrant" class="text-red-500"
                :title="t('common.fire_hydrant')" />
              <Icon v-if="isContractSupplyCut" name="fa6-solid:scissors" class="text-red-600"
                :title="t('service_block.active_supply_cut_warning')" />
              <abbr :title="t('claim_block.active_commitment')" v-if="localData.active_commitment_deposits > 0"
                class="flex items-center gap-2">
                <DeliquencyLevel :level="2" :title="t('claim_block.active_commitment')" />
                <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-sm text-sky-500 m-auto" />
              </abbr>
            </div>
          </button>
          <div v-else class="flex items-center gap-2">
            <span>{{ localData.token }}</span>
            <Icon v-if="isFireContract" name="mdi:fire-hydrant" class="text-red-500"
              :title="t('common.fire_hydrant')" />
            <Icon v-if="isContractSupplyCut" name="fa6-solid:scissors" class="text-red-600"
              :title="t('service_block.active_supply_cut_warning')" />
            <abbr :title="t('claim_block.active_commitment')" v-if="localData.active_commitment_deposits > 0"
              class="flex items-center gap-2">
              <DeliquencyLevel :level="2" :title="t('claim_block.active_commitment')" />
              <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-sm text-sky-500 m-auto" />
            </abbr>
          </div>
        </FieldDetail>
        <FieldDetail v-if="localData.registration_date || localData.created_at" :label="t('common.registration_date')"
          :value="formatDate(localData.registration_date || localData.created_at)">
          <AtomsDate :date="localData.registration_date || localData.created_at"></AtomsDate>
        </FieldDetail>
        <FieldDetail v-if="localData.language" :label="t('common.language')"
          :value="languageLabel(localData.language)" />
      </div>
      <div v-if="localData.termination_date" role="row" class="grid grid-cols-3 gap-x-3">
        <FieldDetail :label="t('common.termination_date')" :value="formatDate(localData.termination_date)">
          <AtomsDate :date="localData.termination_date"></AtomsDate>
        </FieldDetail>
      </div>
      <div v-if="useMultipleCompanies && localData.company?.alias" role="row" class="grid grid-cols-3 gap-x-3">
        <FieldDetail :label="t('company')" :value="localData.company.alias" />
      </div>
      <div role="row" class="grid grid-cols-2">
        <FieldDetail :label="$t('contract_block.holder')" :value="localData.holder.full_name" class="mr-5">
          <!-- <abbr :title="localData.holder.token">{{ localData.holder.full_name }}</abbr> -->
          <div class=" flex items-center"
            :class="{ 'grid grid-cols-[auto,1fr]': localData.holder.vulnerability_level > 0 }">
            <AtomsVulnerabilityCheck v-if="localData.holder.vulnerability_level > 0"
              :vulnerability_level="localData.holder.vulnerability_level" :small="true" class="mr-1" />
            <AtomsPersonBadge :person="localData.holder" class="font-bold" />
          </div>
        </FieldDetail>
        <FieldDetail :label="$t('common.short_supply')">
          <div v-if="!isSubRegion" class="flex gap-2">
            <button @click="showDetail('SupplyPointRegion', localData.supply_point_default?.id)"
              class="text-start text-sky-500 underline flex items-center gap-2">
              {{ localData.supply_point_default?.address_complete }}
              <abbr v-if="localData.supply_point_default.current_fraud" :title="t('service_block.has_fraud')"
                class="mt-auto">
                <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-lg text-sky-500 m-auto" />
              </abbr>
            </button>
            <AtomsRedirectButton :id="localData.supply_point_default.id" :path="'/service/supplypoints/'" />
          </div>
          <span v-else>
            {{ localData.supply_point_default?.address_complete }}
            <abbr v-if="localData.supply_point_default.current_fraud" :title="t('service_block.has_fraud')"
              class="mt-auto">
              <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-lg text-sky-500 m-auto" />
            </abbr>
          </span>
        </FieldDetail>
      </div>
      <!-- <div v-if="localData.supply_points.length > 0" role="row" class="">
        <label for="setup__box" class="mb-3 border px-3 py-2 bg-sky-50">
          <legend class="px-3 font-semibold bg-white">{{ $t('Punts de subministrament adicionals') }}</legend>
        </label>
        <div v-for="supplyPoint in localData.supply_points" :key="supplyPoint.id">
          <button v-if="!isSubRegion" @click="showDetail('SupplyPointRegion', supplyPoint.id)"
            class="text-start text-sky-500 underline">{{ supplyPoint.token }}</button>
          <span v-else>{{ supplyPoint.token }}</span>
  
        </div>
      </div> -->
      <div role="row" class="grid grid-cols-2">
        <span></span>
        <div v-if="localData.supply_points.filter(v => v.id != localData.supply_point_default.id).length > 0" class="">
          <legend class="font-medium text-slate-400">{{ $t('contract_block.additional_supply_points') }}</legend>
          <fieldset id="setup__box" class="mb-3 px-3 py-2 bg-sky-50 border">
            <div v-for="supplyPoint in localData.supply_points.filter(v => v.id != localData.supply_point_default.id)"
              :key="supplyPoint.id">
              <div v-if="!isSubRegion" class="flex gap-2">
                <button @click="showDetail('SupplyPointRegion', supplyPoint.id)"
                  class="text-start text-sky-500 underline">
                  {{ supplyPoint.token }}
                  <abbr v-if="supplyPoint.current_fraud" :title="t('service_block.has_fraud')" class="mt-auto">
                    <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-lg text-sky-500 m-auto" />
                  </abbr>
                </button>
                <AtomsRedirectButton :id="supplyPoint.id" :path="'/service/supplypoints/'" />
              </div>
              <span v-else>
                {{ supplyPoint.token }}
                <abbr v-if="supplyPoint.current_fraud" :title="t('service_block.has_fraud')" class="mt-auto">
                  <Icon name="fa6-solid:triangle-exclamation" class="font-bold text-lg text-sky-500 m-auto" />
                </abbr>
              </span>

            </div>
          </fieldset>
        </div>
      </div>

      <div v-if="localData.representatives">
        <div v-for="representant in localData.representatives" class="grid grid-cols-2">
          <FieldDetail :label="$t('contract_block.representative')" :value="representant.full_name" class="flex mr-5">
            <AtomsPersonBadge :person="representant.person" class="font-bold" />
          </FieldDetail>
          <FieldDetail :label="$t('contract_block.representative_role')" :value="representant.type?.name || null">
          </FieldDetail>
        </div>
      </div>

      <!-- <div v-if="!reducedDetail">
        <hr class="my-2" />
        <div role="row" class="grid grid-cols-2">
          <FieldDetail v-for="bag in localData.estimated_bags" :key="bag.id" :label="$t('Bossa de consum')">
            <div v-if="!isSubRegion" class="flex gap-2">
              <button @click="showDetail('EstimatedBagRegion', bag.id)"
                class="text-start text-sky-500 underline flex items-center gap-2">
                {{ bag.supply_point.token }}
              </button>
            </div>
            <span v-else>
              {{ bag.supply_point.token }}
            </span>
          </FieldDetail>
        </div>
      </div> -->

      <div>
        <hr class="my-2" />
        <div role="row" class="mb-2">
          <ContractStatusBadges :contract="localData" :isSubRegion="isSubRegion" @show-detail="showDetail" />
        </div>
        <div role="row" class="grid grid-cols-3 gap-x-3">
          <FieldDetail :label="$t('contract_block.client_type')"
            :value="localData.client_type ? localData.client_type?.name : t('contract_block.no_client_type')">
          </FieldDetail>
          <FieldDetail :label="$t('common.usage_type')"
            :value="localData.use_type ? localData.use_type?.name : t('common.no_usage_type')"></FieldDetail>
          <FieldDetail :label="$t('contract_block.category')"
            :value="localData.category ? localData.category?.name : t('contract_block.no_category')"></FieldDetail>
        </div>
        <div v-if="localData.supply_point_default?.meter_code" role="row" class="grid grid-cols-2">
          <FieldDetail :label="$t('meter')">
            <div v-if="!isSubRegion" class="flex gap-2">
              <button @click="showDetail('MeterRegion', localData.supply_point_default.meter_id)"
                class="text-start text-sky-500 underline flex items-center gap-2">
                {{ localData.supply_point_default.meter_code }}
              </button>
              <AtomsRedirectButton :id="localData.supply_point_default.meter_id" :path="'/service/meters/'" />
            </div>
            <span v-else>
              {{ localData.supply_point_default.meter_code }}
            </span>
          </FieldDetail>
        </div>

        <div v-if="localData.owner || localData.tenant">
          <hr class="my-2" />
          <div class="grid grid-cols-2">
            <div>
              <FieldDetail v-if="localData.owner" :label="$t('contract_block.owner')" :value="localData.owner?.token"
                class="flex mr-5">
                <!-- <abbr :title="localData.holder.token">{{ localData.holder.full_name }}</abbr> -->
                <div class=" flex items-center"
                  :class="{ 'grid grid-cols-[auto,1fr]': localData.owner?.vulnerability_level > 0 }">
                  <AtomsVulnerabilityCheck v-if="localData.owner?.vulnerability_level > 0"
                    :vulnerability_level="localData.owner?.vulnerability_level" :small="true" class="mr-1" />
                  <AtomsPersonBadge :person="localData.owner" class="font-bold" :color="'white'" />
                </div>
              </FieldDetail>
              <FieldDetail v-if="localData.tenant" :label="$t('contract_block.tenant')" :value="localData.tenant?.token"
                class="flex mr-5">
                <!-- <abbr :title="localData.holder.token">{{ localData.holder.full_name }}</abbr> -->
                <div class=" flex items-center"
                  :class="{ 'grid grid-cols-[auto,1fr]': localData.tenant?.vulnerability_level > 0 }">
                  <AtomsVulnerabilityCheck v-if="localData.tenant?.vulnerability_level > 0"
                    :vulnerability_level="localData.tenant?.vulnerability_level" :small="true" class="mr-1" />
                  <AtomsPersonBadge :person="localData.tenant" class="font-bold" :color="'white'" />
                </div>
              </FieldDetail>
            </div>
            <!-- <div v-if="localData?.contract_request_type?.has_persons">
              <div v-if="!isEditingPersons" class="grid grid-cols-2">
                <FieldDetail :label='$t("common.persons")' :value="(localData.total_persons).toString() || '-'"
                  class="items-center">
                  <span v-if="!isSubRegion && canChange">
                    <span class="p-3">{{ localData.total_persons ? localData.total_persons : 3 }}</span>
                    <button class="px-2 py-1 text-gray-500" @click="isEditingPersons = !isEditingPersons">
                      <Icon name="fa6-solid:pencil" />
                    </button>
                  </span>
                  <span v-else>
                    <span class="p-3">{{ localData.total_persons }}</span>
                  </span>
                </FieldDetail>
              </div>
              <div v-else class="grid grid-cols-2">
                <FieldDetail :label='$t("common.persons")' :value="localData.total_persons || '-'" class="items-center">
                  <span class="flex gap-3 w-full h-[75%]">
                    <input type="number" v-model="totalPersons" class="input" />
                    <button class=" py-1 text-gray-500" @click="emitChange">
                      <Icon name="fa6-solid:floppy-disk" />
                    </button>
                  </span>
                </FieldDetail>
              </div>
            </div> -->
          </div>

        </div>

        <div v-if="showPayment || showCommunication" class="grid grid-cols-2 gap-2">
          <hr class="my-2 col-span-2" />

          <fieldset v-if="showPayment" id="setup__box" class="mb-3 border px-3 py-2 bg-sky-50">
            <legend class="px-3 font-semibold bg-white shadow">{{ t('billing_block.payment') }}</legend>
            <div v-if="localData.general_invoice"
              class="flex items-center gap-2 mb-2 px-2 py-1 bg-sky-50 border-l-2 border-sky-500 text-sky-700 text-xs font-medium rounded-r">
              <Icon name="fa6-solid:circle-info" class="text-sky-500 flex-shrink-0" />
              <span>{{ t('informative_block.info_general_invoice') }}</span>
            </div>
            <div>
              <div :class="{
                'grid grid-cols-2 gap-x-3': localData.payment?.IBAN?.updated_at
              }">
                <FieldDetail
                  v-if="localData.payment?.IBAN && localData.payment?.IBAN?.dni && localData.payment?.IBAN?.dni != localData.holder.dni"
                  class="col-span-2" :label="$t('contract_block.holder')"
                  :value="`${localData.payment?.IBAN?.name} (${localData.payment?.IBAN?.dni})`" />
                <FieldDetail
                  v-else-if="localData.payment?.IBAN && localData.payment?.IBAN?.person.token != localData.holder.token"
                  class="col-span-2" :label="$t('contract_block.holder')"
                  :value="`${localData.payment?.IBAN?.person?.name} (${localData.payment?.IBAN?.person?.token})`" />
                <FieldDetail class="col-span-2" :label="$t('common.payment_method')">
                  <abbr class="truncate" :title="localData.payment?.type?.name">
                    <span class="truncate">
                      {{ localData.payment?.type?.name }}
                    </span>
                  </abbr>
                </FieldDetail>
                <FieldDetail class="col-span-2" v-if="localData.payment?.IBAN?.updated_at" :label="$t('common.updated')"
                  :value="formatDate(localData.payment?.IBAN?.updated_at)" />
              </div>
              <div v-if="localData.payment?.type?.token == 'DIRECT_DEBIT'" class="relative group">
                <BankDetail :item="localData.payment?.IBAN" :is_detail="true"
                  :sepa="localData.payment?.sepa_document || null" :show_sepa="true">
                  <template v-if="!isSubRegion && canChange" #sepa-actions>
                    <SepaQuickActions :payment="localData.payment" :sepa="localData.payment?.sepa_document"
                      :owner="localData" value="contract" @saved="onSepaSaved" />
                  </template>
                </BankDetail>
                <span v-if="localData.payment?.mandate_id" class="flex items-center gap-x-1">
                  <FieldDetail class="flex-1 min-w-0" :label="$t('common.mandate_id')"
                    :value="localData.payment?.mandate_id" />
                  <div class="relative flex-shrink-0 " >
                    <button ref="mandateHistoryAnchor" type="button"
                      class="px-1.5 py-1 text-slate-400 hover:text-sky-600 rounded bg-white/80 border-2 border-slate-400 flex items-center justify-center hover:bg-white hover:border-sky-600"
                      :aria-expanded="openMandateHistoryDropdown" :title="$t('common.history')"
                      @click.stop="toggleMandateHistoryDropdown">
                      <Icon name="fa6-solid:clock-rotate-left" class="w-3.5 h-3.5" />
                    </button>

                    <Teleport to="body">
                      <div v-if="openMandateHistoryDropdown" class="fixed inset-0 z-50">
                        <button type="button" class="absolute inset-0 w-full h-full bg-transparent"
                          :aria-label="$t('common.close')" @click.stop="toggleMandateHistoryDropdown" />

                        <div
                          ref="mandateHistoryPanel"
                          class="absolute bg-white border border-slate-200 shadow-lg rounded-md text-xs overflow-auto max-h-64 w-80"
                          :style="{ top: mandateHistoryPosition.top + 'px', left: mandateHistoryPosition.left + 'px' }"
                          @click.stop
                          @mousedown.stop>
                          <div
                            class="px-3 py-2 border-b border-slate-100 font-medium text-slate-600 sticky top-0 bg-white">
                            {{ $t('common.history') }}
                          </div>
                          <ul v-if="localData.payment?.mandate_logs?.length" class="divide-y">
                            <li v-for="(entry, index) in localData.payment?.mandate_logs" :key="index" 
                            class="px-3 py-2 space-y-0.5" :class="{ 
                              'bg-blue-50 divide-blue-100': entry.is_manual,
                              'divide-slate-100': !entry.is_manual
                              }">
                              <div class="flex items-center justify-between gap-2 text-slate-700">
                                <span class="font-medium truncate">{{ entry.user?.username || 'Admin' }}</span>
                                <div class="flex items-center gap-x-2">
                                  <span v-if="entry.is_manual" class="text-blue-500 uppercase font-bold">
                                    {{ $t('common.manual') }}
                                  </span>
                                  <span class="text-slate-400 whitespace-nowrap">
                                    {{ formatDate(entry.created_at) }}</span>
                                </div>
                              </div>
                              <div class="text-slate-500 truncate">
                                <span class="text-slate-400">{{ $t('common.previous') }}:</span>
                                {{ entry.previous_mandate_id || '-' }}
                              </div>
                              <div class="text-slate-500 truncate">
                                <span class="text-slate-400">{{ $t('common.mandate_id') }}:</span>
                                {{ entry.new_mandate_id || '-' }}
                              </div>
                            </li>
                          </ul>
                          <div v-else class="px-3 py-4 text-center text-slate-400">
                            {{ $t('common.no_data') }}
                          </div>
                        </div>
                      </div>
                    </Teleport>
                  </div>
                </span>
              </div>


              <div v-if="!isEditingRemittance && localData.remittance_date" class="grid grid-cols-2 mt-1 mb-3">
                <FieldDetail :label='$t("common.remittance_day")' class="items-center"
                  :value="localData.remittance_date ? localData.remittance_date.toString() : '-'">
                  <span v-if="!isSubRegion">
                    <span class="p-3">{{ localData.remittance_date ? localData.remittance_date : '-' }}</span>
                    <button class="px-2 py-1 text-gray-500" @click="isEditingRemittance = !isEditingRemittance">
                      <Icon name="fa6-solid:pencil" />
                    </button>
                  </span>
                  <span v-else>
                    <span class="p-3">{{ localData.remittance_date }}</span>
                  </span>
                </FieldDetail>
              </div>
              <div v-else-if="isEditingRemittance" class="grid grid-cols-2">
                <FieldDetail :label='$t("common.remittance_day")'
                  :value="(remittance_date ?? '-').toString()" class="items-center">
                  <span class="flex gap-3 w-full h-[75%]">
                    <input type="number" v-model="remittance_date" class="input w-3/4" />
                    <button class="py-1 text-gray-500 hover:text-sky-600" @click="emitChange">
                      <Icon name="fa6-solid:floppy-disk" />
                    </button>
                    <button v-if="localData.remittance_date" class="py-1 text-gray-500 hover:text-red-500"
                      @click="clearRemittance">
                      <Icon name="fa6-solid:trash" />
                    </button>
                  </span>
                </FieldDetail>
              </div>
            </div>

          </fieldset>

          <fieldset v-if="showCommunication" id="setup__box" class="relative mb-3 border px-3 py-2 bg-sky-50">
            <legend class="px-3 font-semibold bg-white shadow">{{ t('communication') }}</legend>
            <div class="flex flex-col gap-2">

              <div class="relative">
                <div class="">
                  <div class="space-y-2">
                    <div v-if="localData.address_billing">
                      <div class="flex items-center gap-2">
                        <Icon name="fa6-solid:house" class="w-3.5 h-3.5 text-sky-500" />
                        <div class="text-xs font-medium text-slate-500">{{ $t('common.fiscal_address') }}</div>
                      </div>
                      <div class="text-sm pl-5">{{ localData.address_billing.address_complete }}</div>
                    </div>
                    <div v-if="localData.address_contact">
                      <div class="text-xs font-medium text-slate-500">{{ $t('contract_block.contact_address') }}</div>
                      <div class="text-sm pl-5">{{ localData.address_contact.address_complete }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="relative">
                <div class="flex items-center gap-2 text-sm text-slate-600 mb-2">
                  <Icon
                    :name="localData.communication_type == 'DIGITAL' ? 'fa6-solid:at' : (localData.communication_type == 'PAPER' ? 'fa6-solid:envelope' : 'fa6-solid:envelope-open-text')"
                    class="w-3.5 h-3.5 text-sky-500" />
                  <span class="text-xs font-medium text-slate-500">
                    <span v-if="localData.communication_type == 'PAPER'">{{ $t('contract_block.paper_comm') }}</span>
                    <span v-else-if="localData.communication_type == 'DIGITAL'">{{ $t('contract_block.digital_comm')
                    }}</span>
                    <span v-else-if="localData.communication_type == 'BOTH'">{{ $t('contract_block.both_comm') }}</span>
                    <span v-else-if="localData.communication_type == 'NONE'">{{ $t('contract_block.no_comm') }}</span>
                  </span>
                </div>
                <div v-if="localData.communication_type == 'DIGITAL' || localData.communication_type == 'BOTH'"
                  class="">

                  <div class="text-sm pl-5">
                    <a v-if="localData.person_contact_email?.email"
                      :href="'mailto:' + localData.person_contact_email?.email" class="text-sky-500 hover:text-sky-600">
                      {{ localData.person_contact_email?.email }}</a>
                    <span v-else>{{ $t('common.no_email_long') }}</span>
                    <!-- <div v-if="localData.person_contact_sms.length > 0" class="mt-1">
                      <div v-for="phone in localData.person_contact_sms" :key="phone.id"
                        class="flex items-center gap-1 text-slate-600">
                        <span class="text-xs">SMS:</span>
                        <button @click="startCall(phone)" class="text-sky-500 hover:text-sky-600">
                          {{ phone.phone }}</button>
                      </div>
                    </div> -->
                    <div class="text-xs text-slate-400">{{ $t('customer_service_block.no_tlf_sms') }}</div>
                  </div>

                </div>
              </div>

              <div class="relative">
                <div class="flex items-center gap-2 text-sm text-slate-600 mb-2">
                  <Icon name="fa6-solid:comments" class="w-3.5 h-3.5 text-sky-500" />
                  <span class="text-xs font-medium text-slate-500">{{ $t('common.contacts') }} ({{
                    localData.contacts.length }})</span>
                </div>
                <div class="">
                  <div v-if="localData.contacts.length == 0" class="text-sm text-slate-400">
                    {{ $t('common.no_contact') }}
                  </div>
                  <div v-else class="space-y-1">
                    <div v-for="item in localData.contacts" :key="item.id"
                      class="border border-slate-200 px-3 py-2 rounded">
                      <div v-if="item.email && localData.person_contact_email?.email == item.email"
                        class="grid grid-cols-[20px,1fr] items-center">
                        <Icon name="fa6-solid:at" class="text-xs text-slate-400" />
                        <a :href="'mailto:' + item.email" class="text-sky-500 underline hover:no-underline">{{
                          item.email }}</a>
                      </div>
                      <div v-if="item.phone" class="grid grid-cols-[auto,1fr,1fr] gap-x-2 items-center">
                        <div class="flex items-center gap-1">
                          <Icon name="fa6-solid:phone" class="text-xs text-slate-400" />
                          <Icon
                            v-if="localData.person_contact_sms.length > 0 && localData.person_contact_sms.find(sms => sms.id == item.id)"
                            name="fa6-solid:comment-sms" class="text-xs text-slate-400" />

                        </div>
                        <button v-if="item.phone" @click="startCall(item)"
                          class="text-left text-sky-500 underline hover:no-underline">{{ item.phone }}</button>
                        <span v-if="item.role">({{ item.role }})</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div
                v-if="localData.payment?.accounting_office && localData.payment?.managing_body && localData.payment?.processing_unit"
                class="mt-3 border border-slate-200 rounded-md"
                :class="invoiceDropdownOpen ? 'rounded-b-none border-b-transparent' : 'overflow-hidden'">
                <button ref="invoiceDropdownAnchor" type="button"
                  class="flex items-center justify-between gap-2 px-2 py-2 bg-slate-50 hover:bg-slate-100 cursor-pointer group w-full text-left"
                  :aria-expanded="invoiceDropdownOpen" @click="toggleInvoiceDropdown">
                  <div class="flex items-center gap-2">
                    <Icon name="fa6-solid:file-invoice" class="w-3.5 h-3.5 text-slate-400 group-hover:text-slate-600" />
                    <span class="text-sm font-medium text-slate-600 group-hover:text-slate-700">
                      {{ t('common.electronic_invoice') }}
                    </span>
                    <!-- <Icon name="fa6-solid:circle-check" class="w-3.5 h-3.5 text-green-600" /> -->
                  </div>
                  <Icon name="fa6-solid:chevron-down"
                    class="w-3 h-3 text-slate-400 transition-transform group-hover:text-slate-600"
                    :class="{ 'rotate-180': invoiceDropdownOpen }" />
                </button>

                <Teleport to="body">
                  <div v-if="invoiceDropdownOpen" class="fixed inset-0 z-50">
                    <button type="button" class="absolute inset-0 w-full h-full bg-transparent" aria-label="Close"
                      @click="closeInvoiceDropdown" />

                    <div ref="invoiceDropdownPanel"
                      class="absolute bg-white border border-slate-200 shadow-lg rounded-md text-sm overflow-auto max-h-[70vh] rounded-t-none"
                      :style="{
                        top: invoiceDropdownPosition.top + 'px',
                        left: invoiceDropdownPosition.left + 'px',
                        width: invoiceDropdownPosition.width + 'px'
                      }">
                      <div class="px-3 py-3 bg-white">
                        <FieldDetail :label="$t('billing_block.short_accounting_office')">
                          <span class="truncate">
                            {{ localData.payment?.accounting_office }}
                          </span>
                        </FieldDetail>
                        <FieldDetail :label="$t('billing_block.short_managing_body')">
                          <span class="truncate">
                            {{ localData.payment?.managing_body }}
                          </span>
                        </FieldDetail>
                        <FieldDetail :label="$t('billing_block.short_processing_unit')">
                          <span class="truncate">
                            {{ localData.payment?.processing_unit }}
                          </span>
                        </FieldDetail>
                        <FieldDetail v-if="localData.holder?.current_record" :label="$t('billing_block.record')">
                          <span class="truncate">
                            {{ localData.holder?.current_record }}
                          </span>
                        </FieldDetail>
                        <FieldDetail v-if="localData.payment?.command" :label="$t('billing_block.command')">
                          <span class="truncate">
                            {{ localData.payment?.command }}
                          </span>
                        </FieldDetail>
                        <FieldDetail v-if="localData.payment?.record" :label="$t('billing_block.record')">
                          <span class="truncate">
                            {{ localData.payment?.record }}
                          </span>
                        </FieldDetail>
                      </div>
                    </div>
                  </div>
                </Teleport>
              </div>


            </div>
            <div class="grid grid-cols-2 gap-2 mt-1">
              <div
                v-if="localData.communication_type == 'DIGITAL' && (!localData.person_contact_email || localData.person_contact_email?.email == null)"
                class="flex items-center gap-2 bg-orange-100 text-orange-500 border border-orange-500 rounded-md px-2 py-1">
                <!-- sense email-->
                <Icon name="fa6-solid:at" class="w-3.5 h-3.5 text-orange-500" />
                <span>{{ $t('common.no_email_long') }}</span>
              </div>

            </div>
          </fieldset>

        </div>
      </div>

    </div><!-- end region__content -->
  </div>
</template>
