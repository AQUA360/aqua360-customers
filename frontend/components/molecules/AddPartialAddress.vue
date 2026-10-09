<script setup>
import { ref, watch, onMounted, computed, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import CatastroRegion from '../organisms/CatastroRegion.vue';
import StreetPicker from './StreetPicker.vue';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const { $ExploitationApiService, $StreetApiService, $AddressApiService, $CatastroApiService } = useNuxtApp();
const emits = defineEmits(['valueChanged']);
const toast = useToast();

const props = defineProps({
  data: {
    type: Object,
    default: null,
    required: false
  },
  cols: {
    type: Number,
    default: 2,
    required: false
  },
  cols_street_number: {
    type: Number,
    default: 4,
    required: false
  },
  attempted_save: {
    type: Boolean,
    default: false
  },
  disable: {
    type: Boolean,
    default: false
  },
  is_form: {
    type: Boolean,
    default: false
  }
});

const isLoading = ref(true);
const saving = ref(false);
const showRegion = ref(false);
const isCadastreOpen = ref(false);
const cadastreResults = ref([]);

const streetQuery = ref('');
const selectedStreet = ref(null);
const selectedStreetId = ref(null);
const selectedStreetNumberId = ref(null);

const street_type = ref(null);
const street_name = ref('');
const streetNumberTypeRadio = ref('');
const streetNumberNumber = ref('');
const streetNumberEnd = ref('');
const streetNumberSuffix = ref('');
const streetNumberEndSuffix = ref('');
const streetProvince = ref('');

const selectedItem = ref([]);
const creating_street = ref(false);

// Si l'usuari canvia el carrer o el número, l'id del número carregat ja no és vàlid
const streetNumberChanged = ref(false);

const city = ref(null);
const cp = ref(null);

const exploitations = ref([]);
const exploitation = ref(null);

const cities = ref([]);
const allCities = ref([]);
const postalCodes = ref([]);

const longestLabelWidth = (options) => {
  if (!options || options.length === 0) return 0;
  const longest = options.reduce((max, o) => (o.label?.length > max ? o.label.length : max), 0);
  // ~8px per caràcter + marge per la fletxa i el padding intern del vs__dropdown-toggle
  return longest * 8 + 48;
}

const cityMinWidth = computed(() => Math.max(longestLabelWidth(cities.value), 96));
const cpMinWidth = computed(() => Math.max(longestLabelWidth(postalCodes.value), 96));

const street_types = ref([]);

const loading_street_types = ref(true);
const loading_cities = ref(true);

const loading_data = ref(true);

const streetNumberType = computed(() => {
  if (streetNumberTypeRadio.value === 'SN') {
    return 'SN';
  } else if (streetNumberEnd.value) {
    return 'R';
  } else if (streetNumberSuffix.value) {
    return 'S';
  } else {
    return 'N';
  }
});

const getData = async () => {
  if (props.data) {
    await loadData(props.data);
  } else {
    loading_data.value = false;
  }

  await fetchCitiesAndPostalCodes();
  await getStreetTypes();
};

const loadData = async (data) => {
  if (data == null) return;

  loading_data.value = true;

  if (data.address_city != null) {
    city.value = {
      code: data.address_city.id,
      label: data.address_city.name
    };

    streetProvince.value = data.address_city.province
      ? {
          code: data.address_city.province.id,
          label: data.address_city.province.name
        }
      : null;
  } else {
    city.value = null;
  }

  await setPostalCodes();

  if (data.address_postal_code != null) {
    cp.value = {
      code: data.address_postal_code.id,
      label: data.address_postal_code.code
    };
  } else {
    cp.value = null;
  }

  creating_street.value = false;
  streetNumberChanged.value = false;

  if (data.address_street != null) {
    if (data.address_street.type != null) {
      street_type.value = {
        code: data.address_street.type.id,
        label: data.address_street.type.abbreviation
      };
    }

    street_name.value = data.address_street.name;
    streetQuery.value = data.address_street.name;

    selectedStreetId.value = data.address_street.id;
    selectedStreet.value = data.address_street;
  } else {
    street_name.value = null;
    streetQuery.value = null;
    selectedStreetId.value = null;
    selectedStreet.value = null;
  }

  if (data.address_street_number != null) {
    selectedStreetNumberId.value = data.address_street_number.id;
    streetNumberNumber.value = data.address_street_number.number;
    streetNumberEnd.value = data.address_street_number.number_end;
    streetNumberSuffix.value = data.address_street_number.number_suffix;
    streetNumberEndSuffix.value = data.address_street_number.number_end_suffix;
  } else {
    streetNumberNumber.value = null;
    streetNumberEnd.value = null;
    streetNumberSuffix.value = null;
    streetNumberEndSuffix.value = null;
  }

  if (data.address_street_number?.number_type?.type == 'SN') {
    streetNumberTypeRadio.value = data.address_street_number.number_type.type;
  }

  emitChange();

  loading_data.value = false;
  isLoading.value = false;
};

const setAddress = function (item) {
  isCadastreOpen.value = false;
  toggleRegion(false);

  street_name.value = item.dir.nv;

  // Buscar el tipus de carrer a la llista carregada per mantenir la coherència d'objectes
  const foundType = street_types.value.find(t => t.label === item.dir.tv);
  street_type.value = foundType || { label: item.dir.tv };

  creating_street.value = true;
  selectedStreet.value = null;
  selectedStreetId.value = null;
  streetNumberChanged.value = true;

  fieldChanged();
};

const emitChange = (closeTab = false) => {
  emits('valueChanged', getResponseObject(closeTab));
};

const fieldChanged = (closeTab = false) => {
  let close = closeTab === true;

  if (!loading_data.value) {
    emitChange(close);
  }
};

const getResponseObject = (closeTab = false) => {
  return {
    cp: cp.value,
    city: city.value,
    street_type: street_type.value,
    street_name: creating_street.value
      ? street_name.value
      : selectedStreet.value
        ? selectedStreet.value.name
        : street_name.value,
    streetNumberTypeRadio: streetNumberTypeRadio.value,
    streetNumberNumber: streetNumberNumber.value == '' ? null : streetNumberNumber.value,
    streetNumberEnd: streetNumberEnd.value == '' ? null : streetNumberEnd.value,
    streetNumberSuffix: streetNumberSuffix.value == '' ? null : streetNumberSuffix.value,
    streetNumberEndSuffix: streetNumberEndSuffix.value == '' ? null : streetNumberEndSuffix.value,
    streetNumberType: streetNumberType.value,

    // En crear un carrer nou mai s'envia l'id d'un carrer seleccionat abans,
    // i si s'ha canviat el carrer o el número tampoc l'id del número que hi havia.
    streetNumberId: streetNumberChanged.value
      ? null
      : (selectedStreetNumberId.value || props.data?.street_number?.id || null),

    streetId: creating_street.value
      ? null
      : (selectedStreetId.value || null),

    exploitation: exploitation.value?.id || null,
    province: streetProvince?.value || null,
    closeTab: closeTab
  };
};

const getCityId = () => {
  return city.value?.code ||
    (typeof city.value === 'object' ? city.value?.id : city.value);
};

// Pont amb StreetPicker.vue
// v-model: { street, creating, name, type }
const streetModel = computed({
  get: () => ({
    street: selectedStreetId.value
      ? {
          ...(selectedStreet.value || {}),
          id: selectedStreetId.value,
          name: selectedStreet.value?.name || street_name.value
        }
      : null,
    creating: creating_street.value,
    name: street_name.value || '',
    type: street_type.value
  }),

  set: (value) => {
    const newStreetId = value.street?.id ?? null;

    if (
      newStreetId !== (selectedStreetId.value ?? null) ||
      value.creating !== creating_street.value
    ) {
      // Canvia el carrer: l'id del número carregat ja no és vàlid
      streetNumberChanged.value = true;
    }

    selectedStreet.value = value.street;
    selectedStreetId.value = newStreetId;
    creating_street.value = value.creating;
    street_name.value = value.name;
    street_type.value = value.type;
    streetQuery.value = value.street?.name || value.name || '';

    fieldChanged();
  }
});

const onStreetNumberChanged = () => {
  streetNumberChanged.value = true;
  fieldChanged();
};

const fetchCitiesAndPostalCodes = async () => {
  loading_cities.value = true;

  try {
    const data = await $ExploitationApiService.getData();

    exploitations.value = data.results;

    let map_cities = data.results
      .map(exploitation => exploitation.cities)
      .flat();

    allCities.value = map_cities;

    cities.value = Array.from(
      new Map(
        map_cities.map(c => [
          c.id,
          {
            code: c.id,
            label: c.name,
            province: c.province
          }
        ])
      ).values()
    );

    if (cities.value.length === 1) {
      city.value = cities.value[0];
      selectExploitation();
      setPostalCodes();
    }
  } catch (error) {
    console.error(error);
  }

  loading_cities.value = false;
};

const selectExploitation = () => {
  exploitations.value?.forEach(ex => {
    if (ex.cities.find(c => c.id == city.value.code)) {
      exploitation.value = ex;
    }
  });
};

const setPostalCodes = () => {
  console.log('setPostalCodes', city.value);

  if (city.value != null) {
    console.log('allCities', allCities.value);

    const selectedCity = allCities.value.find(
      c => city.value.code == c.id
    );

    postalCodes.value = [];

    if (
      selectedCity != null &&
      selectedCity.postal_codes != null
    ) {
      postalCodes.value = selectedCity.postal_codes.map(cp => {
        return {
          code: cp.id,
          label: cp.code
        };
      });

      if (postalCodes.value.length == 0) {
        cp.value = null;
      } else if (postalCodes.value.length == 1) {
        cp.value = postalCodes.value[0];
      }
    }
  }
};

const getStreetTypes = async () => {
  loading_street_types.value = true;

  try {
    const result = await $StreetApiService.getStreetTypes();

    const mappedTypes = result.results.map(st => ({
      label: st.abbreviation,
      code: st.id
    }));

    street_types.value = mappedTypes;

    // Preserve street_type if it was already set
    if (street_type.value && street_type.value.code) {
      const found = mappedTypes.find(
        t => t.code === street_type.value.code
      );

      if (found) {
        street_type.value = found;
      }
    } else if (
      mappedTypes.length > 0 &&
      !street_type.value
    ) {
      street_type.value = mappedTypes[0];
    }
  } catch (error) {
    console.error('Error fetching street types:', error);
  } finally {
    loading_street_types.value = false;
  }
};

const updateSelected = (e) => {
  if (e.entity == 'city') {
    city.value = e.id;
    selectExploitation();
    setPostalCodes();
  } else if (e.entity == 'cp') {
    cp.value = e.id;
  }

  fieldChanged();
};

// ----------------------------------------- SAVE METHODS -----------------------------------------

/**
 * Desa (o recupera, si ja existeixen) el carrer i el número a `coredata/partial-address/`
 * i deixa el carrer com a seleccionat.
 */
const persistAddress = async ({
  requirePostalCode = false,
  notifySuccess = false
} = {}) => {
  if (!city.value) {
    toast.error(
      t('address_block.error_required_municipality') ||
      'Si us plau, seleccioni un municipi.'
    );

    return null;
  }

  if (requirePostalCode && !cp.value) {
    toast.error(
      t('address_block.error_required_postal_code') ||
      'Si us plau, seleccioni un codi postal.'
    );

    return null;
  }

  const isStreetEmpty = creating_street.value
    ? (!street_name.value || street_name.value.trim() === '')
    : !selectedStreetId.value;

  if (isStreetEmpty) {
    toast.error(
      t('address_block.error_required_street') ||
      'Si us plau, indiqui el carrer.'
    );

    return null;
  }

  if (
    creating_street.value &&
    !street_type.value?.label
  ) {
    toast.error(
      t('address_block.error_required_street_type')
    );

    return null;
  }

  if (
    streetNumberTypeRadio.value !== 'SN' &&
    (!streetNumberNumber.value ||
      streetNumberNumber.value === '')
  ) {
    toast.error(
      t('address_block.error_required_street_number') ||
      'Si l’adreça té número, cal indicar-lo.'
    );

    return null;
  }

  const selected = getResponseObject();

  const data = {
    address_city: selected.city?.code,

    address_street: {
      type: {
        abbreviation: selected.street_type?.label
      },
      type_abbreviation: selected.street_type?.label,
      name: selected.street_name?.trim()
    },

    address_street_number: {
      number_type: {
        type: selected.streetNumberType
      },
      number_type_type: selected.streetNumberType
    }
  };

  if (selected.streetNumberType != 'SN') {
    data.address_street_number.number =
      selected.streetNumberNumber || null;

    data.address_street_number.number_end =
      selected.streetNumberEnd || null;

    data.address_street_number.number_suffix =
      selected.streetNumberSuffix || null;

    data.address_street_number.number_end_suffix =
      selected.streetNumberEndSuffix || null;
  }

  if (
    selected.streetId &&
    !creating_street.value
  ) {
    data.address_street.street_id =
      selected.streetId;
  }

  if (selected.streetNumberId) {
    data.address_street_number.street_number_id =
      selected.streetNumberId;
  }

  try {
    const response =
      await $AddressApiService.savePartialAddress(data);

    selectedStreetId.value = response.street;
    selectedStreetNumberId.value =
      response.street_number;

    streetNumberChanged.value = false;

    if (creating_street.value) {
      // El carrer ja existeix: queda seleccionat com qualsevol altre carrer existent
      const createdName =
        street_name.value.trim();

      selectedStreet.value = {
        id: response.street,
        name: createdName,
        type: street_type.value?.code
          ? {
              id: street_type.value.code,
              abbreviation: street_type.value.label
            }
          : null
      };

      street_name.value = createdName;
      streetQuery.value = createdName;
      creating_street.value = false;
    }

    emitChange();

    if (notifySuccess) {
      toast.success(
        t('address_block.address_saved_ok')
      );
    }

    return response;
  } catch (err) {
    console.log(err);

    toast.error(
      t('address_block.address_saved_ko') ||
      'No s\'ha pogut desar l\'adreça.'
    );

    return null;
  }
};

const save = async () => {
  saving.value = true;

  try {
    const response = await persistAddress({
      requirePostalCode: true,
      notifySuccess: true
    });

    if (response) {
      fieldChanged(true);
    }
  } finally {
    saving.value = false;
  }
};

defineExpose({ persistAddress });

// ------------------------------------------------------------------------------------------------

const toggleRegion = (force) => {
  showRegion.value =
    force !== undefined
      ? force
      : !showRegion.value;

  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    isCadastreOpen.value = false;
  }
};

const showCadastre = async (searchText = null) => {
  const province =
    streetProvince.value ||
    city.value?.province;

  if (!city.value || !province) {
    toast.warning(
      t('address_block.error_required_municipality') ||
      'Por favor, seleccione un municipio.'
    );

    return;
  }

  const prov =
    typeof province === 'object'
      ? (province.label || province.name)
      : province;

  const mun =
    typeof city.value === 'object'
      ? city.value.label
      : city.value;

  const searchName =
    searchText ||
    street_name.value ||
    streetQuery.value ||
    '';

  try {
    // Intento búsqueda exacta
    let result =
      await $CatastroApiService.getData(
        prov,
        mun,
        '',
        searchName
      );

    let hasData =
      result?.consulta_callejeroResult
        ?.callejero != null;

    // Si no hay datos, búsqueda más permisiva
    if (!hasData) {
      const words = searchName
        .split(' ')
        .filter(w => w.length > 2);

      for (const word of words) {
        result =
          await $CatastroApiService.getData(
            prov,
            mun,
            '',
            ''
          );

        if (
          result?.consulta_callejeroResult
            ?.callejero
        ) {
          hasData = true;
          break;
        }
      }
    }

    if (hasData) {
      cadastreResults.value =
        result?.consulta_callejeroResult
          ?.callejero || [];

      isCadastreOpen.value = true;
      toggleRegion(true);
      creating_street.value = true;
    } else {
      toast.info(
        t('address_block.no_cadastre_found') ||
        'No se han encontrado datos en el catastro para esta dirección.'
      );
    }
  } catch (err) {
    console.error(
      'Error checking cadastre:',
      err
    );

    toast.error(
      t('address_block.catastro_api_error') ||
      'Error al consultar el catastro.'
    );
  }
};

onMounted(async () => {
  await getData();
});

/**
 * Només recarrega les dades quan props.data realment CANVIA.
 * No executa loadData durant el muntatge.
 */
watch(
  () => props.data,
  async (newVal, oldVal) => {
    if (!newVal || newVal === oldVal) return;

    await loadData(newVal);
    emitChange();
  }
);

const isSubRegionOpen = ref(false);

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};
</script>

<template>

  <div class="row grid grid-cols-[max-content_max-content] gap-3">

    <!-- MUNICIPI -->
    <div class="address-field">
      <label class="block text-sm font-medium text-slate-500 mb-2">
        {{ $t('address_block.municipality') }}
      </label>

      <v-select
        :disabled="
          loading_cities ||
          cities.length == 0 ||
          props.disable
        "
        :model-value="city"
        class="address-select required"
        :style="{ minWidth: cityMinWidth + 'px' }"
        :class="{
          'invalid':
            props.attempted_save && !city
        }"
        @update:modelValue="
          updateSelected({
            entity: 'city',
            id: $event
          })
        "
        :options="cities"
      />
    </div>

    <!-- CODI POSTAL -->
    <div class="address-field">
      <label class="block text-sm font-medium text-slate-500 mb-2">
        {{ $t('address_block.postal_code') }}
      </label>

      <v-select
        :disabled="
          loading_cities ||
          postalCodes.length == 0 ||
          props.disable
        "
        :model-value="cp"
        class="address-select required"
        :style="{ minWidth: cpMinWidth + 'px' }"
        :class="{
          'invalid':
            props.attempted_save && !cp
        }"
        @update:modelValue="
          updateSelected({
            entity: 'cp',
            id: $event
          })
        "
        :options="postalCodes"
      />
    </div>

    <!-- CARRER -->
    <div
      class="mb-4"
      :class="'col-span-' + props.cols"
    >
      <label class="block text-sm font-medium text-slate-500 mb-2">
        {{
          creating_street
            ? $t('address_block.create_street')
            : $t('address_block.select_street')
        }}
      </label>

      <StreetPicker
        v-model="streetModel"
        :street-types="street_types"
        :loading-street-types="loading_street_types"
        :city-id="getCityId()"
        :disable="props.disable"
        :attempted-save="props.attempted_save"
        @cadastre="showCadastre"
      />
    </div>

    <!-- NÚMERO DE CARRER -->
    <div
      v-if="
        selectedStreetId != null ||
        (creating_street && street_name)
      "
      class="mb-4"
      :class="'col-span-' + props.cols"
    >
      <label class="block text-sm font-medium text-slate-500 mb-2">
        {{ t('address_block.street_number') }}
      </label>

      <div class="flex items-center mb-2">
        <label class="mr-4">
          <input
            type="radio"
            :disabled="props.disable"
            v-model="streetNumberTypeRadio"
            value="SN"
            @change="onStreetNumberChanged"
          />

          {{ t('address_block.no_number') }}
        </label>

        <label>
          <input
            type="radio"
            :disabled="props.disable"
            v-model="streetNumberTypeRadio"
            value=""
            @change="onStreetNumberChanged"
          />

          {{ t('common.number') }}
        </label>
      </div>

      <div
        v-if="streetNumberTypeRadio !== 'SN'"
        class="grid gap-3 mb-2"
        :class="
          'grid-cols-' +
          props.cols_street_number
        "
      >
        <!-- NÚMERO -->
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">
            {{ t('common.number') }}
          </label>

          <input
            v-numeric-only
            :disabled="props.disable"
            type="text"
            v-model="streetNumberNumber"
            class="input"
            :class="{
              'invalid':
                props.attempted_save &&
                streetNumberTypeRadio !== 'SN' &&
                (
                  !streetNumberNumber ||
                  streetNumberNumber === ''
                )
            }"
            @change="onStreetNumberChanged"
          />
        </div>

        <!-- SUFIX -->
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">
            {{ t('address_block.suffix') }}
          </label>

          <input
            type="text"
            :disabled="props.disable"
            maxlength="10"
            v-model="streetNumberSuffix"
            class="input"
            @change="onStreetNumberChanged"
          />
        </div>

        <!-- NÚMERO FINAL -->
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">
            {{ t('address_block.end_number') }}
          </label>

          <input
            v-numeric-only
            :disabled="props.disable"
            type="text"
            v-model="streetNumberEnd"
            class="input"
            @change="onStreetNumberChanged"
          />
        </div>

        <!-- SUFIX FINAL -->
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">
            {{ t('address_block.suffix') }}
          </label>

          <input
            type="text"
            :disabled="props.disable"
            maxlength="10"
            v-model="streetNumberEndSuffix"
            class="input"
            @change="onStreetNumberChanged"
          />
        </div>
      </div>
    </div>

    <slot></slot>

    <!-- BOTÓ DESAR -->
    <div
      v-if="props.is_form"
      class="col-span-3 flex flex-row-reverse mt-4"
    >
      <button
        @click="save"
        :disabled="saving"
        class="button-primary"
      >
        <Icon name="fa6-solid:floppy-disk" />

        &nbsp;

        {{ $t('common.save') }}
      </button>
    </div>

    <!-- REGIÓ DRETA -->
    <div
      role="region"
      id="right_page"
      class="
        fixed
        h-full
        border-l
        border-gray-100
        top-0
        right-0
        transition-transform
        duration-500
        ease
        py-2
        text-base
        bg-white
        z-10
        w-[95%]
        overflow-y-auto
        overflow-x-hidden
      "
      :class="{
        'translate-x-0': showRegion,
        'translate-x-full': !showRegion,
        'w-1/2': !isSubRegionOpen
      }"
    >
      <div
        id="region_nav"
        class="mb-3 px-3"
      >
        <button
          @click="toggleRegion(false)"
          class="
            px-2
            py-1
            text-sky-500
            hover:bg-slate-200
            active:bg-slate-300
          "
        >
          <Icon
            name="fa6-solid:angles-right"
            class="text-slate-500"
          />
        </button>
      </div>

      <div
        v-if="isCadastreOpen"
        class="px-10"
      >
        <CatastroRegion
          :isSubRegionOpen="isSubRegionOpen"
          :selectedItem="selectedItem"
          :city="city"
          :streetName="street_name"
          :cadastreData="cadastreResults"
          @show-subregion="handleSubRegionEvent"
          @item-clicked="setAddress"
        />
      </div>
    </div>

  </div>
</template>

<style>
.vs--disabled .vs__actions {
  opacity: 0;
}

/*
 * Camps de Municipi i Codi postal
 */
.address-field {
  width: max-content;
  min-width: 0;
}

.address-select {
  width: auto;
}

.address-select .vs__dropdown-toggle {
  width: 100%;
}

.address-select .vs__selected {
  white-space: nowrap;
}

/*
 * MENÚ DESPLEGABLE
 *
 * El menú pot ser més ample que el select si alguna
 * de les opcions és més llarga.
 */
.address-select .vs__dropdown-menu {
  width: max-content;
  min-width: 100%;
  max-width: none;
  white-space: nowrap;
  overflow-x: visible;
}

/*
 * Les opcions tampoc es poden tallar.
 */
.address-select .vs__dropdown-option {
  white-space: nowrap;
  overflow: visible;
  text-overflow: unset;
}
</style>