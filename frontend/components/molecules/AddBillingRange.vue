<script setup>
import { ref, resolveDirective, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import AddPublication from './AddPublication.vue';
import _ from 'lodash';
import { useToast } from 'vue-toastification';


const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  pr_id: {
    type: Number,
    default: null
  }, // ID de l'element
  li_id: {
    type: Number,
    default: null
  }, // ID de l'element
  br_id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'new-br']);
const router = useRouter();
const { $BillingRangeApiService, $PublicationApiService, $PriceRateApiService } = useNuxtApp();
const SubRegion = ref(props.isSubRegionOpen);
const observationNumber = ref(0)

const token = ref('')
const name = ref('')
const priceRate = ref(null)
const startDate = ref(null)
const endDate = ref(null)

const publications = ref([])
const selectedPublication = ref(null)

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingPublication = ref(false);

const attemptedSave = ref(false);
const saving = ref(false);

const updateObservationCount = (num) => {
  observationNumber.value = num;
}

const getData = async () => {
  console.log(props.pr_id)
  console.log(props.li_id)
  if (props.br_id != null) {
    const response = await $BillingRangeApiService.getDetail(props.br_id);
    token.value = response.token;
    name.value = response.name;
    selectedPublication.value = { value: response.publication?.id, label: response.publication?.name } || null
    startDate.value = response.start;
    endDate.value = response.end;
  }
  else {
    name.value = '';
  }

  getPublications();
  getPriceRate();
}

const getPublications = async (page = 1, search = '') => {
  const response = await $PublicationApiService.getAll(search, [] , page); 
  publications.value = []

  response.results.forEach(item => {
    publications.value.push({
      value: item.id,
      label: item.name
    })
  });
  let result = {
    items: publications.value,
    hasNextPage: response && response.next ? true : false
  }
  return result;
}

const getPriceRate = async () => {
  const response = await $PriceRateApiService.getDetail(props.pr_id);
  priceRate.value = response;
}

const save = async () => {
  let duplicate_check = false
  if (props.li_id) {
    duplicate_check = confirm(t("pricing_block.duplicate_check"))
  }
  if (isValid()) {
    saving.value = true;
    const selectedOptions = {
      price_rate: props?.pr_id || null,
      name: name.value,
      duplicate_check: duplicate_check,
      publication: selectedPublication?.value?.value || null,
      start: startDate?.value,
      end_active: endDate?.value
    };

    
    const br = await $BillingRangeApiService.save(selectedOptions);
    finishAndClose(br);
  }
  else {
    attemptedSave.value = true;
    saving.value = false;
  }
}
/* 
const createPublication = async () => {
  console.log("createPublication")
  selectedPublication.value = null
  openRegion('publication')
}
 */
const newPublication = async (new_publication) => {
  console.log(new_publication)
  selectedPublication.value = { value: new_publication.id, label: new_publication.name }
  closeSubRegion();
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'publication':
      selectedPublication.value = event;
      break;
  }
}

const finishAndClose = (br) => {
  saving.value = false;
  emit('new-br', br);
}

const isValid = () => {
  if (name.value == '' || startDate.value == null || selectedPublication.value == null) {
    toast.error(t('common.required_fields'));
    return false;
  }
  return true;
}

watch(() => props.br_id, () => {
  getData();
  closeSubRegion();
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

getData();

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}
const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

// subregions details
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}



</script>

<template>
  <div class="region__content" :class="{ 'grid grid-cols-2': SubRegion && !SubRegion }">
    <div>
      <div class="flex justify-between items-center mb-2">
        <H1Region>{{ props.br_id > 0 ? `${$t('common.modify')} ${t('common.range')}` : $t('pricing_block.new_billing_range') }}</H1Region>
      </div>

      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-2">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }} *</label>
          <input required type="text" v-model="name" :class="{ 'invalid': attemptedSave && name == '' }"
            class="input" />
        </div>

        <div class="mb-2">
          <AtomsInfiniteScrollVueSelect :labelText="t('pricing_block.publication_detail')" :loadFunction="getPublications" :item="selectedPublication"
            @update:modelValue="updateSelect($event, 'publication')">
            <button class="w-9 h-9 border-gray-300 border rounded enabled:hover:bg-slate-200 transition-all duration-200"
              @click="showDetail('PublicationRegion', null)">
            <Icon name="fa6-solid:plus" class="text-md text-slate-600" />
            </button>
          </AtomsInfiniteScrollVueSelect>
        </div>
      </div>
      <div class="row grid grid-cols-2 gap-3">

        <div class="mb-2">
          <AtomsInputDate v-model="startDate" :label="t('common.start_date')" class="mb-2"
            :invalid="attemptedSave && (startDate == null || startDate == '')" />
        </div>

      </div>
      <hr />
      <div v-if="props.li_id != null" class="row grid grid-cols-2 gap-3">

        <div class="mb-2">
          <AtomsInputDate v-model="endDate" :label="t('pricing_block.end_date_range')" class="mb-2" />
        </div>
      </div>
      <hr />

      <hr />
      <div class="flex flex-row-reverse mt-4">
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ $t('common.save') }}
        </button>
      </div><!-- end contingut botons -->

    </div>
    <div v-if="SubRegion == true" role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-10 w-[47%] overflow-y-auto overflow-x-hidden"
      :class="{
        'translate-x-0': SubRegion,
        'translate-x-full': !SubRegion,
        
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <AddPublication :id="null" v-if="showRegionDetailComponent === 'PublicationRegion'"
          :isSubRegionOpen="isSubRegionOpen" :object="regionDetailId"
          @new-publication="newPublication" />
      </div>
    </div>

  </div><!-- end wrapper -->
</template>