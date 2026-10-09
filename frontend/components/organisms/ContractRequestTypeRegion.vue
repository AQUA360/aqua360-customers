<script setup>
// components/organisms/ContractRequestTypeRegion.vue
import { ref, watch, onMounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import ContractRequestTypeEditRegion from '~/components/organisms/ContractRequestTypeEditRegion.vue';
import ConfigList from '~/components/organisms/ConfigList.vue';
import VariableTypeSelectMultiple from '~/components/organisms/VariableTypeSelectMultiple.vue';
import OrderTypeSelectMultiple from '~/components/organisms/OrderTypeSelectMultiple.vue';
import ClauseTemplateSelectMultiple from '~/components/organisms/ClauseTemplateSelectMultiple.vue';
import PriceRateSelectMultiple from '~/components/organisms/PriceRateSelectMultiple.vue';

import { VariableTypeDataTypeChoices, VariableTypeApplicationChoices } from '~/utils/variable-type';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const props = defineProps({
  id: {
    type: Number,
    required: true
  },
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['show-subregion', 'changed', 'close']);
const router = useRouter();
const { $ContractRequestTypeApiService, $ConfigProjectApiService, $ContractRequestApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const variableTypeSelectedItems = ref([]);
const orderTypeSelectedItems = ref([]);
const clauseTemplateSelectedItems = ref([]);
const priceRateSelectedItems = ref([]);
const registrationPriceRateSelectedItems = ref([]);
const hasPersons = ref(null);

const priceRateFilter = ref(null)
const activePriceRateList = ref(null);

const origin_contract_token = ref(null)
const origin_reading_token = ref(null)
const origin_supply_token = ref(null)

// Funció per inicialitzar `variableTypeSelectedItems` basat en les dades
const initializeVariableTypeSelectedItems = () => {
  if (data.value && data.value.variable_types) {
    variableTypeSelectedItems.value = data.value.variable_types.map(v => v.id);
  }
}

// Funció per inicialitzar `orderTypeSelectedItems` basat en les dades
const initializeOrderTypeSelectedItems = () => {
  if (data.value && data.value.order_types) {
    orderTypeSelectedItems.value = data.value.order_types.map(v => v.id);
  }
}


// Funció per inicialitzar `clauseTemplateSelectedItems` basat en les dades
const initializeClauseTemplateSelectedItems = () => {
  if (data.value && data.value.clause_templates) {
    clauseTemplateSelectedItems.value = data.value.clause_templates.map(v => v.id);
  }
}



// Funció per inicialitzar `clauseTemplateSelectedItems` basat en les dades
const initializePriceRatesSelectedItems = () => {
  if (data.value && data.value.price_rates) {
    priceRateSelectedItems.value = data.value.price_rates.map(v => v.id);
  }
}

const initializeRegistrationPriceRatesSelectedItems = () => {
  if (data.value && data.value.registration_price_rates) {
    registrationPriceRateSelectedItems.value = data.value.registration_price_rates.map(v => v.id);
  }
}


const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $ContractRequestTypeApiService.getDetail(props.id);
    data.value = result;
    hasPersons.value = data.value.has_persons;
    initializeVariableTypeSelectedItems();
    initializeOrderTypeSelectedItems();
    initializeClauseTemplateSelectedItems();
    initializePriceRatesSelectedItems();
    initializeRegistrationPriceRatesSelectedItems();
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

watch(() => props.id, () => {
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

// Watcher per sincronitzar canvis en `data`
watch(() => data.value, () => {
  initializeVariableTypeSelectedItems();
  initializeOrderTypeSelectedItems();
  initializeClauseTemplateSelectedItems();
  initializePriceRatesSelectedItems();
  initializeRegistrationPriceRatesSelectedItems();
}, { immediate: true });

onMounted(async () => {
  objectPermissions.value = await checkPermission($ContractRequestApiService);
  if (!objectPermissions.value.can_view) {
    toast.error(t('common.no_permissions'));
    emit('close')
  }
  origin_contract_token.value = await $ConfigProjectApiService.get('origin_contract_token');
  origin_reading_token.value = await $ConfigProjectApiService.get('origin_reading_token');
  origin_supply_token.value = await $ConfigProjectApiService.get('origin_supply_token');
  getData();
});

// Subregion
const SubRegion = ref(props.isSubRegionOpen);
const showRegionDetailComponent = ref(null);

const closeSubRegion = () => {
  priceRateFilter.value = null
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  activePriceRateList.value = null;
  emit('show-subregion', false);
}

const showSubRegion = () => {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const openEdit = () => {
  showRegionDetailComponent.value = 'ContractRequestTypeEditRegion';
  showSubRegion();
}

const openConfigDocuments = () => {
  showRegionDetailComponent.value = 'ConfigList';
  showSubRegion();
}

const openVariableTypeSelectMultiple = () => {
  showRegionDetailComponent.value = 'VariableTypeSelectMultiple';
  showSubRegion();
}

const openOrderTypeSelectMultiple = () => {
  showRegionDetailComponent.value = 'OrderTypeSelectMultiple';
  showSubRegion();
}

const openPriceRateSelectMultiple = async (filter) => {
  closeSubRegion()
  await nextTick()
  priceRateFilter.value = Array.isArray(filter) ? filter : [filter];
  if (priceRateFilter.value.includes(origin_contract_token.value)) {
    showRegionDetailComponent.value = 'RegistrationPriceRateSelectMultiple';
    activePriceRateList.value = 'registration';
  } else {
    showRegionDetailComponent.value = 'PriceRateSelectMultiple';
    activePriceRateList.value = 'normal';
  }
  showSubRegion();
}
const openClauseTemplateSelectMultiple = () => {
  showRegionDetailComponent.value = 'ClauseTemplateSelectMultiple';
  showSubRegion();
}

const handlePersonChange = async () => {
  if (isSaving.value) return; // Evitar reaccions durant el guardat

  isSaving.value = true;
  const saveObject = {
    id: props.id,
    has_persons: hasPersons.value
  };

  try {
    await $ContractRequestTypeApiService.save(saveObject);
    await getData(); // Actualitzar les dades després de guardar
  } catch (err) {
    console.error('Error al guardar els tipus de variables:', err);
    // Opcional: Mostrar un missatge d'error a l'usuari
  } finally {
    isSaving.value = false;
  }

  emit('changed');
}

const handleDocumentChanged = () => {
  getData();
  emit('changed');
}

const onSavedAdd = (item) => {
  getData();
  closeSubRegion();
  emit('changed');
}


// Watcher per detectar canvis en `variableTypeSelectedItems` i guardar-los
const isSaving = ref(false); // Flag per evitar bucles infinits

watch(variableTypeSelectedItems, async (newItems, oldItems) => {
  if (!objectPermissions.value.can_change) return;
  if (isSaving.value) return; // Evitar reaccions durant el guardat

  // Comprovar si hi ha canvis
  const areDifferent = JSON.stringify(newItems) !== JSON.stringify(oldItems);
  if (!areDifferent) return;

  isSaving.value = true;
  const saveObject = {
    id: props.id,
    variable_types_ids: newItems
  };

  try {
    await $ContractRequestTypeApiService.save(saveObject);
    await getData(); // Actualitzar les dades després de guardar
  } catch (err) {
    console.error('Error al guardar els tipus de variables:', err);
    // Opcional: Mostrar un missatge d'error a l'usuari
  } finally {
    isSaving.value = false;
  }

  emit('changed');
});

// Watcher per detectar canvis en `orderTypeSelectedItems` i guardar-los
watch(orderTypeSelectedItems, async (newItems, oldItems) => {
  if (!objectPermissions.value.can_change) return;
  if (isSaving.value) return; // Evitar reaccions durant el guardat

  // Comprovar si hi ha canvis
  const areDifferent = JSON.stringify(newItems) !== JSON.stringify(oldItems);
  if (!areDifferent) return;

  isSaving.value = true;
  const saveObject = {
    id: props.id,
    order_types_ids: newItems
  };

  try {
    await $ContractRequestTypeApiService.save(saveObject);
    await getData(); // Actualitzar les dades després de guardar
  } catch (err) {
    console.error('Error al guardar els tipus d\'ordres:', err);
    // Opcional: Mostrar un missatge d'error a l'usuari
  } finally {
    isSaving.value = false;
  }

  emit('changed');
});

watch(clauseTemplateSelectedItems, async (newItems, oldItems) => {
  if (!objectPermissions.value.can_change) return;
  if (isSaving.value) return; // Evitar reaccions durant el guardat

  // Comprovar si hi ha canvis
  const areDifferent = JSON.stringify(newItems) !== JSON.stringify(oldItems);
  if (!areDifferent) return;

  isSaving.value = true;
  const saveObject = {
    id: props.id,
    clause_templates_ids: newItems
  };

  try {
    await $ContractRequestTypeApiService.save(saveObject);
    await getData(); // Actualitzar les dades després de guardar
  } catch (err) {
    console.error('Error al guardar les clàusules:', err);
    // Opcional: Mostrar un missatge d'error a l'usuari
  } finally {
    isSaving.value = false;
  }

  emit('changed');
});

watch(registrationPriceRateSelectedItems, async (newItems, oldItems) => {
    console.log('registrationPriceRateSelectedItems', newItems, oldItems);
    console.log('activePriceRateList', activePriceRateList.value);
    if (!objectPermissions.value.can_change) return;
    if (isSaving.value || activePriceRateList.value !== 'registration') return;

    const areDifferent = JSON.stringify(newItems) !== JSON.stringify(oldItems);
    if (!areDifferent) return;

    isSaving.value = true;
    const saveObject = {
      id: props.id,
      registration_price_rates_ids: newItems,
    };
    
    try {
      await $ContractRequestTypeApiService.save(saveObject);
      await getData();
    } catch (err) {
      console.error('Error al guardar les tarifes de registre:', err);
    } finally {
      isSaving.value = false;
    }

    emit('changed');
  }
);

watch(priceRateSelectedItems, async (newItems, oldItems) => {
    console.log('priceRateSelectedItems', newItems, oldItems);
    if (!objectPermissions.value.can_change) return;
    if (isSaving.value || activePriceRateList.value !== 'normal') return;

    // Comprovar si hi ha canvis
    const areDifferent = JSON.stringify(newItems) !== JSON.stringify(oldItems);
    if (!areDifferent) return;

    isSaving.value = true;
    const saveObject = {
      id: props.id,
      price_rates_ids: newItems,
    };
    
    try {
      await $ContractRequestTypeApiService.save(saveObject);
      await getData(); // Actualitzar les dades després de guardar
    } catch (err) {
      console.error('Error al guardar les tarifes:', err);
      // Opcional: Mostrar un missatge d'error a l'usuari
    } finally {
      isSaving.value = false;
    }

    emit('changed');
  }
);

</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p>
        <button @click="getData" class="underline text-sky-500 hover:no-underline">
          {{ $t('common.load_again') }}
        </button>
      </p>
    </div>
    <div v-else class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('contract_block.contracting_type') }}</H1Region>
        <OptionsDropdown v-if="objectPermissions?.can_change" id="ConnectionRequestRegionOptions">
          <DropdownOption :name="$t('common.modify')" @click="openEdit">
            <Icon name="fa6-solid:pencil" class="text-slate mr-1" /> {{ $t('common.modify') }}
          </DropdownOption>
          <hr />
          <DropdownOption :name="`${$t('common.modify')} ${$t('common.doc_type')}`" @click="openConfigDocuments">
            <Icon name="fa6-solid:file-lines" class="text-slate mr-1" /> {{ $t('common.modify') }} {{ $t('common.doc_type') }}
          </DropdownOption>
          <DropdownOption :name="`${$t('common.modify')} ${$t('contract_block.variable_type')}`" @click="openVariableTypeSelectMultiple">
            <Icon name="fa6-solid:gear" class="text-slate mr-1" /> {{ $t('common.modify') }} {{ $t('contract_block.variable_type') }}
          </DropdownOption>
          <DropdownOption :name="`${$t('common.modify')} ${$t('order_block.order_types')}`" @click="openOrderTypeSelectMultiple">
            <Icon name="fa6-solid:screwdriver-wrench" class="text-slate mr-1" /> {{ $t('common.modify') }} {{ $t('order_block.order_types') }}
          </DropdownOption>
            <DropdownOption :name="`${$t('common.modify')} ${$t('contract_block.registration_price_rates')}`" @click="openPriceRateSelectMultiple(origin_contract_token)">
            <Icon name="fa6-solid:money-check" class="text-slate mr-1" /> {{ $t('common.modify') }} {{ $t('contract_block.registration_price_rates') }}
          </DropdownOption>
          <DropdownOption :name="`${$t('common.modify')} ${$t('contract_block.clauses')}`" @click="openClauseTemplateSelectMultiple">
            <Icon name="fa6-solid:paragraph" class="text-slate mr-2" /> {{ $t('common.modify') }} {{ $t('contract_block.clauses') }}
          </DropdownOption>
          <DropdownOption :name="`${$t('common.modify')} ${$t('contract_block.contract_price_rates')}`" @click="openPriceRateSelectMultiple(origin_reading_token)">
            <Icon name="fa6-solid:cube" class="text-slate mr-2" /> {{ $t('common.modify') }} {{ $t('contract_block.contract_price_rates') }}
          </DropdownOption>
        </OptionsDropdown>
      </div>

      <div v-if="data" id="item_data" :data-rel="id">
        <div class="mb-3 grid grid-cols-2 gap-4">
          <FieldDetail label="Nom" :strong="true" :value="data.name">
            <strong class="text-sky-500">{{ data.name }}</strong>
          </FieldDetail>
          <FieldDetail label="Identificador" :value="data.token" />
        </div>
        <div class="mb-3 gap-4 flex items-center">
          <input :disabled="!objectPermissions?.can_change" type="checkbox" v-model="hasPersons" :value="hasPersons" @change="handlePersonChange" /> {{
            t("contract_block.total_persons") }} ({{ t('common.mandatory') }})
        </div>

        <div id="documents" class="mb-3">
          <p class="mb-3 font-semibold">{{ $t('common.doc_types') }} ({{ data.documentation_types.length }})</p>
          <div class="pl-3 pr-3">
            <ul class="mb-2">
              <li v-for="docType in data.documentation_types" :key="docType.id" class="mb-1">
                <span class="text-slate-900 p-1">
                  <Icon name="fa6-regular:file-lines" class="text-slate-500" /> &nbsp;
                  {{ docType.list_name ? docType.list_name : docType.name }}
                  <em v-if="!docType.is_mandatory"> ({{ $t('common.optional') }})</em>
                </span>
              </li>
            </ul>
            <button v-if="data.documentation_types?.length === 0 && objectPermissions?.can_change" @click="openConfigDocuments"
              class="underline text-sky-500 hover:no-underline">
              {{ $t('common.add') }} {{ $t('common.doc_type') }}
            </button>
            <span v-if="data.documentation_types?.length === 0 && !objectPermissions?.can_change" class="text-slate-500">
              {{ $t('common.no_doc_type') }}
            </span>
          </div>
        </div>

        <div id="vars" class="mb-3">
          <p class="mb-3 font-semibold">{{ $t('contract_block.variable_types') }} ({{ data.variable_types.length }})</p>
          <div class="pl-3 pr-3">
            <ul v-if="data.variable_types.length" class="border-t mb-2">
              <li class="grid grid-cols-[1fr,1fr,1fr] text-base border-b items-center bg-white"
                v-for="variable in data.variable_types" :key="variable.id">
                <span class="text-slate-900 p-1 border-l pl-3">
                  <Icon name="fa6-solid:gear" class="text-slate-500" /> &nbsp;
                  {{ variable.name }}
                </span>
                <span class="text-slate-900 p-1 border-l">
                  {{ variable.data_type ? VariableTypeDataTypeChoices[variable.data_type] : '-' }}
                </span>
                <span class="text-slate-900 p-1 border-l">
                  {{ variable.application ? VariableTypeApplicationChoices[variable.application] : '-' }}
                </span>
              </li>
            </ul>
            <button v-if="data.variable_types.length === 0 && objectPermissions?.can_change" @click="openVariableTypeSelectMultiple"
              class="underline text-sky-500 hover:no-underline">
              {{ $t('common.add') }} {{ $t('contract_block.variable_type') }}
            </button>
            <span v-if="data.variable_types.length === 0 && !objectPermissions?.can_change" class="text-slate-500">
              {{ $t('common.no_variable_type') }}
            </span>
          </div>
        </div>

        <div id="orders" class="mb-3">
          <p class="mb-3 font-semibold">{{ $t('order_block.order_types_long') }} ({{ data.order_types.length }})</p>
          <div class="pl-3 pr-3">
            <ul class="mb-2">
              <li v-for="orderType in data.order_types" :key="orderType.id" class="mb-1">
                <span class="text-slate-900 p-1">
                  <Icon name="fa6-solid:screwdriver-wrench" class="text-slate-500" /> &nbsp;
                  {{ orderType.name }}
                </span>
              </li>
            </ul>
            <button v-if="data.order_types.length === 0 && objectPermissions?.can_change" @click="openOrderTypeSelectMultiple"
              class="underline text-sky-500 hover:no-underline">
              {{ $t('common.add') }} {{ $t('order_block.order_types_long') }}
            </button>
            <span v-if="data.order_types.length === 0 && !objectPermissions?.can_change" class="text-slate-500">
              {{ $t('order_block.no_order_types_long') }}
            </span>
          </div>
        </div>


        <div id="clause_templates" class="mb-3">
          <p class="mb-3 font-semibold">{{ $t('contract_block.clauses') }} ({{ data.clause_templates.length }})</p>
          <div class="pl-3 pr-3">
            <ul class="mb-2">
              <li v-for="itemType in data.clause_templates" :key="itemType.id" class="mb-1">
                <MoleculesClauseDetail :item="itemType" />
              </li>
            </ul>
            <button v-if="data.clause_templates.length === 0 && objectPermissions?.can_change" @click="openClauseTemplateSelectMultiple"
              class="underline text-sky-500 hover:no-underline">
              {{ $t('common.add') }} {{ $t('contract_block.clauses') }}
            </button>
            <span v-if="data.clause_templates.length === 0 && !objectPermissions?.can_change" class="text-slate-500">
              {{ $t('contract_block.no_clauses') }}
            </span>
          </div>
        </div>

        <div id="price_rate_templates" class="mb-3">
          <p class="mb-3 font-semibold">{{ $t('contract_block.registration_price_rates') }} ({{ data.registration_price_rates.length }})
          </p>
          <div class="pl-3 pr-3">
            <ul class="mb-2">
              <li v-for="item in data.registration_price_rates" :key="item.id" class="mb-1">
                <Icon name="fa6-solid:cube" class="text-slate-500" /> &nbsp;<span class="font-semibold">{{
                  item.product?.name || $t('pricing_block.no_product') }}</span> - {{ item.name }}
              </li>
            </ul>
            <button v-if="data.registration_price_rates.length === 0 && objectPermissions?.can_change" @click="openPriceRateSelectMultiple(origin_contract_token)"
              class="underline text-sky-500 hover:no-underline">
              {{ $t('common.add') }} {{ $t('common.price_rates') }}
            </button>
            <span v-if="data.registration_price_rates.length === 0 && !objectPermissions?.can_change" class="text-slate-500">
              {{ $t('contract_block.no_registration_price_rates') }}
            </span>
          </div>
        </div>

        <div id="price_rate_templates" class="mb-3">
          <p class="mb-3 font-semibold">{{ $t('contract_block.contract_price_rates') }} ({{ data.price_rates.length }})</p>
          <div class="pl-3 pr-3">
            <ul class="mb-2">
              <li v-for="item in data.price_rates" :key="item.id" class="mb-1">
                <Icon name="fa6-solid:cube" class="text-slate-500" /> &nbsp;<span class="font-semibold">{{
                  item.product?.name || $t('pricing_block.no_product') }}</span> - {{ item.name }}
              </li>
            </ul>
            <button v-if="data.price_rates.length === 0 && objectPermissions?.can_change" @click="openPriceRateSelectMultiple(origin_reading_token)"
              class="underline text-sky-500 hover:no-underline">
              {{ $t('common.add') }} {{ $t('common.price_rates') }}
            </button>
            <span v-if="data.price_rates.length === 0 && !objectPermissions?.can_change" class="text-slate-500">
              {{ $t('contract_block.no_contract_price_rates') }}
            </span>
          </div>
        </div>


      </div><!-- end if data -->
    </div><!-- end if pending -->

    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <ContractRequestTypeEditRegion v-if="showRegionDetailComponent === 'ContractRequestTypeEditRegion'" :item="data"
          :isSubRegionOpen="true" @saved="onSavedAdd" />

        <ConfigList v-if="showRegionDetailComponent === 'ConfigList'" :title="`${$t('common.doc_types')}: ${data.name}`"
          entity="contract/contract-request-documentation-type" :hasColor="false" :hasMandatoryCheck="true" :hasCustomText="true"
          parent_entity="contract_request_type" :parent_id="props.id" @changed="handleDocumentChanged" />

        <VariableTypeSelectMultiple v-if="showRegionDetailComponent === 'VariableTypeSelectMultiple'"
          v-model="variableTypeSelectedItems" />

        <OrderTypeSelectMultiple v-if="showRegionDetailComponent === 'OrderTypeSelectMultiple'"
          v-model="orderTypeSelectedItems" />


        <ClauseTemplateSelectMultiple v-if="showRegionDetailComponent === 'ClauseTemplateSelectMultiple'"
          v-model="clauseTemplateSelectedItems" />

        <PriceRateSelectMultiple v-if="showRegionDetailComponent === 'RegistrationPriceRateSelectMultiple'"
          v-model="registrationPriceRateSelectedItems" :filter="priceRateFilter" :title="$t('contract_block.registration_price_rates')" />
        <PriceRateSelectMultiple v-if="showRegionDetailComponent === 'PriceRateSelectMultiple'"
          v-model="priceRateSelectedItems" :filter="priceRateFilter" :title="$t('contract_block.contract_price_rates')" />

      </div>
    </div>
  </div><!-- end region__content -->
</template>
