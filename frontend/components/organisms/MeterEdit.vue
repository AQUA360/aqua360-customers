<script setup>
import { toRaw, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { remoteTypeOptions } from '~/utils/service';
import H1 from '~/components/atoms/H1.vue';
import H1Region from '../atoms/H1Region.vue';
import { checkPermission } from '~/middleware/permission';

const props = defineProps({
  meter: Object,
  supply_point: Object,
  prefillCode: {
    type: String,
    default: null
  },
  isSubRegion: {
    type: Boolean,
    default: false
  }
});

const { t,te } = useI18n();
const { $MeterApiService, $ConfiglistApiService, $AddressHelper, $MeterManufacturerApiService, $MeterModelApiService, $AddressApiService } = useNuxtApp();

const emit = defineEmits(['created']);

const loading = ref(true);
const saving = ref(false);
const attemptedSave = ref(false);

const code = ref(null);
const code2 = ref(null);
const is_compound = ref(false);
const is_property = ref(false);
const is_general = ref(false);
const manufacturing_year = ref(null);
const comm_module = ref(null);
const comm_module_type = ref(null);
const comm_technology = ref(null);
const network_provider = ref(null);

const uninstallation_at = ref(null)
const installation_at = ref(null)

const meter_caliber = ref(null)
const latitude = ref(null);
const longitude = ref(null);
const meter_status = ref(null);

const address_data = ref({});
const shown_address_data = ref({});

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingSupplyPoints = ref(false);
const editingMeters = ref(false);
const editingAddress = ref(false);

const meter_calibers = ref([])
const meter_statuses = ref([])
const remote_types = ref([])
const selected_supply_points = ref([])
const selected_child_meters = ref([])

const meter_manufacturer = ref(null)
const meter_manufacturers = ref([])

const meter_model = ref(null)
const meter_models = ref([])

const loading_meter_manufacturers = ref(true);

const loading_calibers = ref(true);
const loading_meter_status = ref(true);

const has_remote_reading = ref(false);
const selected_remote_type = ref(null);

const getData = async () => {

  loading.value = true;
  remoteTypeOptions.forEach(rt => {
    remote_types.value.push({
      label: te(rt.label) ? t(rt.label) : rt.label,
      code: rt.code
    })
  });
  await getCalibers();
  await getMeterStatus();
  await getMeterManufacturers();

  if (props.meter != null && props.meter.id > 0) {
    setValues();
  } 
  else if (props.prefillCode) {
    code.value = props.prefillCode
  }

  if (props.supply_point != null && props.supply_point.id > 0) {
    selected_supply_points.value = [props.supply_point];
    if (props.supply_point.address_id) {
      try {
     const response = await $AddressApiService.getDetail(props.supply_point.address_id);
      if (response) {
        assignExistingAddress(response);
      }
    } catch (error) {
      console.error('Error carregant adreça del comptador:', error);
    }
   }
  }

  loading.value = false;
}

const assignExistingAddress = (address) => {
  let extra_address_data = []
  if (address?.stair) {
    extra_address_data.push(address.stair)
  }
  if (address?.door) {
    extra_address_data.push(address.door)
  }
  if (address?.floor) {
    extra_address_data.push(address.floor)
  }
  const extra_address_data_string = extra_address_data.join(', ');
  address_data.value = {
    cp: (() => {
      const match = address?.postal_code && address?.city
      ? address.city.postal_codes.find(pc => pc.code == address.postal_code)
      : null;
      return match ? { code: match.id, label: address.postal_code } : null;
    })(),
    city: address?.city ? { code: address.city.id, label: address.city.name } : null,
    streetId: address?.street?.id || null,
    street_name: address?.street?.name || null,
    streetNumberType: address?.street_number?.number_type?.type || null,
    street_type: address?.street?.type ? { code: address.street.type.id, label: address.street.type.abbreviation } : null,
    streetNumberTypeRadio: address?.street_number?.number_type?.type || null,
    streetNumberType: address?.street_number?.number_type?.type || null,
    streetNumberNumber: address?.street_number?.number || null,
    streetNumberEnd: address?.street_number?.number_end || null,
    streetNumberSuffix: address?.street_number?.number_suffix || null,
    streetNumberEndSuffix: address?.street_number?.number_end_suffix || null,
    streetNumberId: address?.street_number?.id || null,
    extra_address_data: extra_address_data_string || null,
  }
  //shown_address_data.value = { ...address_data.value };
  updateShownAddress();
}

const getMeterManufacturers = async () => {
  loading_meter_manufacturers.value = true
  try {
    let manufacturers = await $MeterManufacturerApiService.getAll();
    meter_manufacturers.value = [];
    manufacturers.results.forEach(m => {
      meter_manufacturers.value.push({
        label: m.name,
        code: m.id
      })
    })
  }
  catch (error) {
    console.error('Error fetching meter manufacturers:', error);
  }
  loading_meter_manufacturers.value = false;
}

const getMeterModelsByManufacturer = async (manufacturerId) => {
  if (manufacturerId && manufacturerId > 0) {
    try {
      let models = await $MeterModelApiService.getModelsByManufacturer(manufacturerId);
      meter_model.value = null;
      meter_models.value = [];
      models.forEach(m => {
        meter_models.value.push({
          label: m.name,
          code: m.id
        })
      })
    }
    catch (error) {
      console.error('Error fetching meter models:', error);
    }
  }
  else {
    meter_model.value = [];
  }
}

const getMeterStatus = async () => {
  loading_meter_status.value = true;

  try {
    let statuses = await $ConfiglistApiService.getAll('service/meter-status');
    meter_statuses.value = [];

    statuses.results.forEach(status => {
      meter_statuses.value.push({
        label: status.name,
        code: status.id
      })
    });
    meter_status.value = meter_statuses.value[0];
  } catch (error) {
    console.error('Error fetching meter statuses:', error);
  }
  loading_meter_status.value = false;
};

const getCalibers = async () => {
  loading_calibers.value = true;

  try {
    let calibers = await $ConfiglistApiService.getAll('service/meter-caliber');
    meter_calibers.value = [];

    calibers.results.forEach(caliber => {
      meter_calibers.value.push({
        label: caliber.name,
        code: caliber.id
      })
    });
    meter_caliber.value = meter_calibers.value[0];
  } catch (error) {
    console.error('Error fetching connection statuses:', error);
  }
  loading_calibers.value = false;
};

const codeExists = ref(false);
const checkingCode = ref(false);
let codeCheckTimeout = null;

const checkCodeDuplicate = async () => {
  if (!code.value) {
    codeExists.value = false;
    return;
  }
  checkingCode.value = true;
  try {
    const result = await $MeterApiService.checkCode(code.value, props.meter?.id || null);
    codeExists.value = result?.exists || false;
  } catch (err) {
    console.error(err);
    codeExists.value = false;
  } finally {
    checkingCode.value = false;
  }
}

watch(code, () => {
  clearTimeout(codeCheckTimeout);
  codeCheckTimeout = setTimeout(checkCodeDuplicate, 400);
});

const updateSelected = (e) => {
  if (e.entity == 'meter_caliber') {
    meter_caliber.value = e.id;
  }
  else if (e.entity == 'meter_status') {
    meter_status.value = e.id;
  }
  else if (e.entity == 'meter_manufacturer') {
    meter_manufacturer.value = e.id
    getMeterModelsByManufacturer(e.id.code)
  }
  else if (e.entity == 'meter_model') {
    meter_model.value = e.id
  }
}

const handleUpdateAddressData = (updatedValue) => {
  address_data.value = updatedValue;
  updateShownAddress()
  if (updatedValue.closeTab)
    closeAllRegions();
};
const deleteAddress = () => {
  address_data.value = {};
};

const updateShownAddress = () => {
  shown_address_data.value = {
    address_street: {
      type_abbreviation: address_data.value?.street_type?.label,
      type_name: address_data.value?.street_type?.label,
      type: {
        abbreviation: address_data.value?.street_type?.label,
        name: address_data.value?.street_type?.label
      },
      name: address_data.value?.street_name,
      name_2: null
    },

    address_street_number: {
      number_type: {
        type: address_data.value?.streetNumberType,
      },
      number: address_data.value?.streetNumberNumber || null,
      number_end: address_data.value?.streetNumberEnd || null,
      number_suffix: address_data.value?.streetNumberSuffix || null,
      number_end_suffix: address_data.value?.streetNumberEndSuffix || null
    },
    address_city: {
      name: address_data.value?.city?.label || null,
    },
    address_postal_code: {
      code: address_data.value?.cp?.label || null
    },
    extra_address_data: address_data.value?.extra_address_data || null,
  }

};

const save = async () => {
  attemptedSave.value = true;

  if (isValid()) {
    saving.value = true;
    const selectedOptions = {
      code: code.value,
      code2: code2.value,
      is_compound: is_compound.value || false,
      is_property: is_property.value || false,
      is_general: is_general.value || false,
      has_remote_reading: has_remote_reading.value || false,
      manufacturer: meter_manufacturer.value?.label ? meter_manufacturer.value.label : meter_manufacturer.value,
      model: meter_model.value?.label ? meter_model.value.label : meter_model.value,
      manufacturing_year: manufacturing_year.value,
      comm_module: comm_module.value,
      comm_module_type: comm_module_type.value,
      comm_technology: comm_technology.value,
      network_provider: network_provider.value,
      uninstallation_at: uninstallation_at.value,
      installation_at: installation_at.value,
      caliber: meter_caliber.value?.code || null,
      status: meter_status.value?.code || null,
      address_street: address_data.value?.street_type ? {
        type: {
          abbreviation: address_data.value?.street_type?.label || null
        },
        type_abbreviation: address_data.value?.street_type?.label || null,
        name: address_data.value?.street_name
      } : null,
      address_street_number: address_data.value?.streetNumberType ? {
        number_type: {
          type: address_data.value?.streetNumberType,

        },
        number_type_type: address_data.value?.streetNumberType,
      } : null,
      latitude: latitude.value,
      longitude: longitude.value,
      address_city: address_data.value?.city?.code || null,
      address_postal_code: address_data.value?.cp?.code || null
    };

    let mySupplyPoints = [];
    let mySubMeters = [];
    if (selected_supply_points.value.length > 0) {
      selected_supply_points.value.forEach(sp => {
        if (sp.meter_id == null || sp.meter_id == '' || (props.meter && sp.meter_id == props.meter?.id)) {
          mySupplyPoints.push(sp.id);
        }
        else {
          mySubMeters.push(sp.meter_id);
        }
      });
    }

    selectedOptions.supply_points = mySupplyPoints;
    selectedOptions.sub_meters = mySubMeters;
    selectedOptions.remote_reading_type = selected_remote_type.value || null;

    if (selected_child_meters.value.length > 0) {
      selected_child_meters.value.forEach(cm => {
        mySubMeters.push(cm.id);
      });
    }

    if (address_data.value.streetNumberNumber) {
      if (address_data.value?.streetNumberType != 'SN') {
        selectedOptions.address_street_number.number = address_data.value?.streetNumberNumber || null,
          selectedOptions.address_street_number.number_end = address_data.value?.streetNumberEnd || null,
          selectedOptions.address_street_number.number_suffix = address_data.value?.streetNumberSuffix || null,
          selectedOptions.address_street_number.number_end_suffix = address_data.value?.streetNumberEndSuffix || null
      }
    }

    if (props.meter != null && props.meter.address_street_number != null) {
      selectedOptions.address_street_number.street_number_id = props.meter.address_street_number.id;
    }
    else if (address_data.value.streetNumberId) {
      selectedOptions.address_street_number.street_number_id = address_data.value.streetNumberId;
    }

    if (address_data.value.streetId && address_data.value?.street_type) {
      selectedOptions.address_street.street_id = address_data.value?.streetId;
    }

    let meter = null;
    try {
      if (props.meter != null && props.meter.id > 0) {
        selectedOptions.id = props.meter.id;
        meter = await $MeterApiService.updateMeter(selectedOptions);
      }
      else {
        meter = await $MeterApiService.createMeter(selectedOptions);
      }
    } catch (error) {
      console.error('Error saving meter:', error);
      saving.value = false;
      return; // Stop processing after error
    }

    if (!props.isSubRegion) {
      return navigateTo('/service/meters/')
    }
    else {
      emit('created', meter);
    }
  }
  else {
    saving.value = false;
  }
}
const deleteMeter = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    saving.value = true;
    await $MeterApiService.deleteMeter(props.meter.id);
    return navigateTo('/service/meters/')
  }
}

const setValues = async () => {
  code.value = props.meter.code;
  code2.value = props.meter.code2;
  is_compound.value = props.meter.is_compound;
  is_property.value = props.meter.is_property;
  is_general.value = props.meter.is_general;
  has_remote_reading.value = props.meter.has_remote_reading;
  selected_remote_type.value = props.meter.remote_reading_type || null;
  let meter_manufacturer_name = props.meter.manufacturer;
  let manufacturerId;
  if (meter_manufacturer_name) {
    let meter_manufacturer_object = await $MeterManufacturerApiService.getByName(meter_manufacturer_name);
    manufacturerId = meter_manufacturer_object[0].id
    await getMeterModelsByManufacturer(manufacturerId)
    meter_manufacturer.value = { code: manufacturerId, label: meter_manufacturer_object[0].name }
  }

  let meter_model_name = props.meter.model;
  if (manufacturerId && meter_model_name) {
    let meter_model_object = await $MeterModelApiService.getByName(manufacturerId, meter_model_name);
    meter_model.value = { code: meter_model_object[0].id, label: meter_model_object[0].name }
  }

  manufacturing_year.value = props.meter.manufacturing_year;
  comm_module.value = props.meter.comm_module;
  comm_module_type.value = props.meter.comm_module_type;
  comm_technology.value = props.meter.comm_technology;
  network_provider.value = props.meter.network_provider;
  uninstallation_at.value = props.meter.uninstallation_at;
  installation_at.value = props.meter.installation_at;
  meter_caliber.value = { code: props.meter.caliber.id, label: props.meter.caliber.name };
  meter_status.value = { code: props.meter.status.id, label: props.meter.status.name };

  latitude.value = props.meter.latitude;
  longitude.value = props.meter.longitude;

  let subMeters = props.meter.sub_meters;
  if (!Array.isArray(subMeters) && props.supply_point?.sub_meters) {
    subMeters = props.supply_point.sub_meters;
  }
  if (Array.isArray(subMeters) && subMeters.length > 0) {
    selected_child_meters.value = subMeters;
  }
  const supplyPoints = props.meter.supply_points;
  if (Array.isArray(supplyPoints) && supplyPoints.length > 0) {
    selected_supply_points.value = supplyPoints;
  }

  if (selected_child_meters.value.length > 0 || selected_supply_points.value.length > 1) {
    is_general.value = true;
  }

  if (props.meter.address_street?.id) {
    address_data.value = { streetId: props.meter.address_street.id };
  }

  if (props.meter.address_street) {
    address_data.value = {
      streetId: props.meter.address_street.id,
      street_name: props.meter.address_street.name,
      streetNumberType: props.meter.address_street_number?.number_type?.type || null,
      streetNumberId: props.meter.address_street_number?.id || null,
      streetNumberNumber: props.meter.address_street_number?.number ?? null,
      streetNumberEnd: props.meter.address_street_number?.number_end ?? null,
      streetNumberSuffix: props.meter.address_street_number?.number_suffix ?? null,
      streetNumberEndSuffix: props.meter.address_street_number?.number_end_suffix ?? null,
      street_type: { code: props.meter.address_street.type.id, label: props.meter.address_street.type.abbreviation }
    };
  }

  shown_address_data.value = { ...props.meter }

}

const supplyPointClicked = (supplyPoint) => {
  const index = selected_supply_points.value.findIndex(sp => sp.id == supplyPoint.id);
  if (index == -1) {
    selected_supply_points.value.push(supplyPoint);
  }
  else {
    selected_supply_points.value.splice(index, 1)
  }
  if (selected_supply_points.value.length > 1) {
    selected_child_meters.value = [];
  }
  if (!is_general.value) {
    setTimeout(() => {
      closeAllRegions();
    }, 200)
  }
}
const meterClicked = (meter) => {
  const index = selected_child_meters.value.findIndex(m => m.id == meter.id);
  if (index == -1) {
    selected_child_meters.value.push(meter);
  }
  else {
    selected_child_meters.value.splice(index, 1)
  }
  /* setTimeout(() => {
    closeAllRegions();
  }, 200) */
}

/** Formatea calle para mostrar: si es objeto (API) devuelve "ABREV. Nombre", si es string lo devuelve tal cual */
const formatStreetDisplay = (street) => {
  if (street == null || street === '') return '';
  if (typeof street === 'string') return street;
  const abbr = street.type_abbreviation ?? street.type?.abbreviation ?? '';
  const name = street.name ?? '';
  return name ? (abbr ? `${abbr}. ${name}` : name) : abbr;
};

/** Estado para badge: acepta item con status_name/status_color (plano) o status: { name, color } (API) */
const getStatusForBadge = (item) => ({
  value: item?.status_name ?? item?.status?.name ?? '',
  color: item?.status_color ?? item?.status?.color ?? ''
});

const isValid = () => {
  if (code.value == '' || code.value == null) return false;
  if (address_data.value?.street_name == '' || address_data.value?.street_name == null) return false;
  if (address_data.value?.street_type == null) return false;
  if (meter_status.value == null) return false;
  if (meter_caliber.value == null) return false;
  return true;
}

const openRegion = (region) => {
  closeAllRegions();

  if (region == 'supply_points') {
    editingSupplyPoints.value = true;
  }
  else if (region == 'meters') {
    editingMeters.value = true;
  }
  else if (region == 'address') {
    editingAddress.value = true;
  }
  showRegion.value = true;
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    closeAllRegions();
  }
}

const closeAllRegions = () => {
  // tanquem tots els components
  editingSupplyPoints.value = false;
  editingMeters.value = false;
  editingAddress.value = false;
  // tanquem region
  showRegion.value = false;
};

watch(is_general, () => {
  if (!is_general.value) {
    if (selected_supply_points.value && selected_supply_points.value.length > 1) {
      if (selected_supply_points.value[0].meter_id != null || selected_supply_points.value[0].meter_id != '') {
        selected_supply_points.value = [];
      }
      else {
        selected_supply_points.value = [selected_supply_points.value[0]];
      }
    }
    if (selected_child_meters.value) {
      selected_child_meters.value = [];
    }
  }
});
watch(is_compound, () => {
  if (!is_compound.value) {
    code2.value = null;
  }
});


onMounted(() => {
  getData()
});

</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full relative min-h-screen">
    <div v-if="isSubRegion">
      <H1Region class="mb-3">{{ $t('service_block.new_meter') }}</H1Region>
    </div>
    <div v-if="loading">
      <div class="border border-gray-300 rounded p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else class="border border-gray-300 rounded p-4 bg-white">
      <div class="row grid grid-cols-3 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.code') }}</label>
          <input type="text" v-model="code" class="input"
            :class="{ 'invalid': attemptedSave && (code == '' || code == null) }" />
            <p v-if="codeExists" class="text-amber-600 text-xs mt-1">
              <Icon name="fa6-solid:triangle-exclamation" /> {{ t('warning_block.meter_code_already_exists') }}
            </p>
        </div>
        <div class="mb-2 grid grid-cols-2 gap-2">
          <div class="flex items-center mt-9 ml-2">
            <input v-model="is_property" type="checkbox" id="is_property" name="is_property" class="checkbox" />
            <label for="is_property" class="ml-2">{{ t("service_block.is_property") }}</label>
          </div>
          <div class="flex items-center mt-9 ml-2">
            <input v-model="is_compound" type="checkbox" id="is_compound" name="is_compound" class="checkbox" />
            <label for="is_compound" class="ml-2">{{ t("service_block.is_compound") }}</label>
          </div>
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.code') }} (2)</label>
          <input type="text" :disabled="!is_compound" v-model="code2" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.manufacturer') }}</label>
          <!--<input type="text" v-model="meter_manufacturer" class="input" />-->
          <v-select :model-value="meter_manufacturer" class="block w-full mr-2" :options="meter_manufacturers"
            :taggable="true" @update:modelValue="updateSelected({ entity: 'meter_manufacturer', id: $event })">
            <template #no-options="{ search, searching, loading }">
              {{ t('common.no_records') }}
            </template>
          </v-select>
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.model') }}</label>
          <!--<input type="text" v-model="model" class="input" />-->
          <v-select :model-value="meter_model" :disabled="loading_meter_manufacturers || !meter_manufacturer"
            class="block w-full mr-2" :options="meter_models" :taggable="true"
            @update:modelValue="updateSelected({ entity: 'meter_model', id: $event })">
            <template #no-options="{ search, searching, loading }">
              {{ t('common.no_records') }}
            </template>
          </v-select>
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.manufacturing_year')
            }}</label>
          <input v-numeric-only maxlength="4" type="text" v-model="manufacturing_year" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ $t('common.status') }}</label>
          <v-select class="required" :class="{ 'invalid': attemptedSave && meter_status == null }"
            :disabled="loading_meter_status || meter_statuses.length == 0" :model-value="meter_status"
            @update:modelValue="updateSelected({ entity: 'meter_status', id: $event })" :options="meter_statuses">
            <template #no-options="{ search, searching, loading }">
              {{ t('common.no_records') }}
            </template>
          </v-select>
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.telecontrol') }}</label>
          <div class="flex items-center pt-2">
            <input v-model="has_remote_reading" type="checkbox" id="has_remote_reading" name="has_remote_reading"
              class="checkbox" />
            <label for="has_remote_reading" class="ml-2">{{ t('service_block.has_remote_reading') }}</label>
          </div>
        </div>

        <div v-if="has_remote_reading">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.remote_type') }}</label>
          <v-select v-model="selected_remote_type" :options="remote_types" label="label" track-by="code"
            :reduce="option => option.code">
            <template #no-options="{ search, searching, loading }">
              {{ t('common.no_records') }}
            </template>
          </v-select>
        </div>


        <hr class="mb-2 col-span-3" />
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.comm_module') }}</label>
          <input type="text" v-model="comm_module" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.comm_module_type') }}</label>
          <input type="text" v-model="comm_module_type" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.comm_tech') }}</label>
          <input type="text" v-model="comm_technology" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.network_provider') }}</label>
          <input type="text" v-model="network_provider" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.short_install_date')
            }}</label>
          <input type="date" v-model="installation_at" class="input" />
        </div>
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.short_uninstall_date')
            }}</label>
          <input type="date" v-model="uninstallation_at" class="input" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ $t('service_block.caliber') }}</label>
          <v-select class="required" :class="{ 'invalid': attemptedSave && meter_caliber == null }"
            :disabled="loading_calibers || meter_calibers.length == 0" :model-value="meter_caliber"
            @update:modelValue="updateSelected({ entity: 'meter_caliber', id: $event })" :options="meter_calibers">
            <template #no-options="{ search, searching, loading }">
              {{ t('common.no_records') }}
            </template>
          </v-select>
        </div>
        <hr class="mb-2 col-span-3" />
        <div class="mb-2">
          <div class="flex items-center mt-5 ml-2">
            <input v-model="is_general" type="checkbox" id="is_general" name="is_general" class="checkbox" />
            <label for="is_general" class="ml-2">{{ t('service_block.is_general') }}</label>
          </div>
        </div>
        <div class="mb-2 col-span-2">
          <div class="field flex items-center gap-1">
            <label for="Supply_points" class="block text-sm font-medium text-slate-500 mb-2">
              {{ $t('common.supply_points') }} ({{ $t('service_block.no_meters') }})
            </label>
            <abbr v-if="is_general" class="flex items-center justify-center mb-2"
              :title="t('informative_block.info_select_supply_points')">
              <Icon name="fa6-solid:circle-info" class="text-slate-500" />
            </abbr>
          </div>
          <div :class="{ 'mt-1': selected_supply_points.length == 0 }" class="text-gray-900 divide-y rounded shadow">
            <div v-if="selected_supply_points.length > 0"
              class="group grid grid-cols-3 divide-x text-sm text-center leading-4 ">
              <span class="p-1 text-slate-400">
                {{ t('common.code') }}
              </span>
              <span class="p-1 text-slate-400">
                {{ t('address_block.address') }}
              </span>
              <!-- <span v-if="is_general" class="p-1 text-slate-400">
                {{ t('Comptador') }}
              </span> -->
              <span class="p-1 text-slate-400">
                {{ t('common.status') }}
              </span>
            </div>
            <div v-for="item in selected_supply_points"
              class="group grid grid-cols-3 divide-x text-sm text-center leading-4 ">
              <div class="p-2 text-slate-800">{{ item.token }}</div>
              <div class="p-2 text-slate-800 relative">
                {{ item.address_complete }}
              </div>
              <!-- <div v-if="is_general" class="p-2 text-slate-800 relative">
                {{ item.meter_code || item.meter || '' }}
              </div> -->
              <div class="p-2 text-slate-800 relative">
                <AtomsColorBadge :value="item.status_name" :color="item.status_color" />
                <button
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                  @click="supplyPointClicked(item)">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
            </div>
            <div class="footering"
              v-if="is_general || selected_supply_points == null || (selected_supply_points != null && selected_supply_points.length == 0)">
              <button @click="openRegion('supply_points')"
                :disabled="selected_child_meters.length > 0 && selected_supply_points.length > 0"
                class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300 disabled:opacity-75 disabled:cursor-not-allowed disabled:bg-slate-200">
                <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
              </button>
            </div>
          </div>
        </div>
        <div v-if="is_general" class="mb-2 col-span-3">
          <div class="field flex items-center gap-1">
            <label for="child_meters" class="block text-sm font-medium text-slate-500 mb-2">
              {{ $t('service_block.child_meters') }}
            </label>
            <abbr v-if="is_general" class="flex items-center justify-center mb-2"
              :title="t('informative_block.info_child_meters')">
              <Icon name="fa6-solid:circle-info" class="text-slate-500" />
            </abbr>
          </div>
          <div :class="{ 'mt-1': selected_child_meters.length == 0 }" class="text-gray-900 divide-y rounded shadow">
            <div v-if="selected_child_meters.length > 0"
              class="group grid grid-cols-3 divide-x text-sm text-center leading-4 ">
              <span class="p-1 text-slate-400">
                {{ t('common.code') }}
              </span>
              <span class="p-1 text-slate-400">
                {{ t('service_block.placement') }}
              </span>
              <span class="p-1 text-slate-400">
                {{ t('common.status') }}
              </span>
            </div>
            <div v-for="item in selected_child_meters"
              class="group grid grid-cols-3 divide-x text-sm text-center leading-4 ">
              <div class="p-2 text-slate-800">{{ item.code }}</div>
              <div class="p-2 text-slate-800">{{ formatStreetDisplay(item.address_street) }}</div>
              <div class="p-2 text-slate-800 relative">
                <AtomsColorBadge :value="getStatusForBadge(item).value" :color="getStatusForBadge(item).color" />
                <button
                  class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                  @click="meterClicked(item)">
                  <Icon name="fa6-solid:trash" />
                </button>
              </div>
            </div>
            <div class="footering">
              <button @click="openRegion('meters')" :disabled="selected_supply_points.length > 1"
                class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300 disabled:opacity-75 disabled:cursor-not-allowed disabled:bg-slate-200">
                <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
              </button>
            </div>
          </div>
        </div>
        <hr class="mb-2 col-span-3" />

        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('service_block.meter_location') }} *</label>
          <div v-if="address_data.streetId == null" class="footering text-gray-900 rounded shadow">
            <button @click="openRegion('address')"
              :class="{ 'invalid': attemptedSave && address_data.streetId == null }"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.assign') }} {{
                $t('address_block.address') }}
            </button>
          </div>
          <div v-else class="relative group footering text-slate-500 rounded shadow p-2">
            {{ $AddressHelper.getAddressString(shown_address_data) }}
            <button
              class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-8 top-1 rounded-md text-slate-600 hover:text-blue-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
              @click="openRegion('address')">
              <Icon name="fa6-solid:pencil" />
            </button>
            <button
              class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
              @click="deleteAddress()">
              <Icon name="fa6-solid:trash" />
            </button>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.latitude') }}</label>
          <input v-numeric-only type="text" v-model="latitude" class="input" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.longitude') }}</label>
          <input v-numeric-only type="text" v-model="longitude" class="input" />
        </div>
        <hr class="mb-2 col-span-3" />
        <div class="col-span-3 flex flex-row-reverse mt-4">
          <button v-if="meter != null" @click="deleteMeter" :disabled="saving" class="button-default mx-5">
            &nbsp; {{ $t('common.delete') }}</button>
          <button @click="save" :disabled="saving" class="button-primary">
            <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
              :class="saving ? 'animate-spin' : ''" />&nbsp;
            {{
              saving ? $t('common.loading') : $t('common.save') }}
          </button>
        </div>
      </div>

    </div>

    <div role="region" :id="isSubRegion ? 'subregion' : 'right_page'"
      class="h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10 overflow-x-hidden"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-[40%]': !isSubRegionOpen,
        'fixed': true
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <MoleculesAddSupplyPoints v-if="editingSupplyPoints" :show="editingSupplyPoints"
          :selected_items="selected_supply_points" @item-clicked="supplyPointClicked" :noMeter="true"
          :multiple="is_general && selected_child_meters.length == 0" />
        <MoleculesAddMeters :exclude="props.meter?.id" v-if="is_general && editingMeters" @item-clicked="meterClicked"
          :multiple="true" :selected_items="selected_child_meters" />
        <MoleculesAddPartialAddress v-if="editingAddress" :attempted_save="attemptedSave" :cols=3 :cols_street_number=3
          class="col-span-3" :data="props.meter" @valueChanged="handleUpdateAddressData" :is_form="true" />
      </div>
    </div>
  </div>
</template>
