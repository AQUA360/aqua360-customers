<script setup>
import { ref, onMounted } from 'vue';

import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import LocationSearch from '~/components/organisms/LocationSearch.vue';
import AddAddress from '~/components/molecules/AddAddress.vue';

const { $SupplyPointRequestApiService, $ConfiglistApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  request: Object
});

const emit = defineEmits(['change-person', 'refresh']);

const loading = ref(true);
const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingPerson = ref(false);
const editingLocation = ref(false);

const selectedPerson = ref(null);
const selectedAddress = ref(null);
const dataToLoad = ref(null);

const cadastral = ref('')

const address_id = ref(null)
const address = ref(null)

const contractUploaded = ref(null)
const contractFile = ref(null)
const contractDelete = ref(null)
const documentationUploaded = ref(null)

const documentTypes = ref([])

const closeAllRegions = () => {
  // tanquem tots els components
  editingPerson.value = false;
  editingLocation.value = false;

  // tanquem region
  showRegion.value = false;
};

const newAddress = (new_address) => {
  address_id.value = new_address.id;
  address.value = new_address;
  selectedAddress.value = new_address;
  closeAllRegions()

  emitChange()
}

const emitChange = () => {

  let data = {
    cadastral: cadastral.value || null,
    address_id: address_id.value || null,
    person_id: selectedPerson.value?.id || null,
    contract: contractFile.value || null
  }

  if (contractDelete.value) {
    data.contract_delete = true;
  }

  emit('change-person', data);
}

const getDocumentTypes = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('service/supply-point-request-document-type');

    documentTypes.value= [];
    // data.results.forEach(docType => {
    for (let docType of data.results) {
      let index = props.request.documents.findIndex(doc => doc.supply_point_request_document_type?.id == docType.id);
      if (index > -1) {
        docType.document = props.request.documents[index];
      }
      else {

        const docData = {
          supply_point_request: props.request.id,
          supply_point_request_document_type: docType.id,
          checked: false
        }
        const response = await $SupplyPointRequestApiService.saveDocument(docData);
        docType.document = response;
      }
      documentTypes.value.push(docType);
    }
  } catch (error) {
    console.error('Error fetching document types:', error);
  }
}

const handleContractUpdate = (doc) => {
  contractFile.value = doc;
  emitChange();
}
const handleContractDelete = () => {
  contractDelete.value = true;
  emitChange();
}
const handleDocumentUpdate = async (doc, docType) => {

  try {

    const data = {
      supply_point_request: props.request.id,
      supply_point_request_document_type: docType.id,
      file: doc
    }

    if (docType.document) {
      data.checked = docType.document.checked;
      if (docType.document.id) data.id = docType.document.id;
    }

    const response = await $SupplyPointRequestApiService.saveDocument(data);

    let docs = [... documentTypes.value];
    
    let index = docs.findIndex(doc => doc.id == docType.id);
    if (index > -1) {
      docs[index].document = response;
    }

    documentationUploaded.value = docs;
    emit('refresh');
  } catch (error) {
    console.log(error)
  }
}

const handleDocumentCheck = async (bool, docType) => {

  try {

  const data = {
    supply_point_request: props.request.id,
    supply_point_request_document_type: docType.id,
    checked: bool
  }

  if (docType.document?.id) {
    data.id = docType.document.id;
  }

  const response = await $SupplyPointRequestApiService.saveDocument(data);

  let docs = [... documentTypes.value];

  let index = docs.findIndex(doc => doc.id == docType.id);
  if (index > -1) {
    docs[index].document = response;
  }

  documentTypes.value = docs;
  emit('refresh');
  } catch (error) {
  console.log(error)
  }
}

const handleDocumentDelete = async (doc) => {
  try {
    await $SupplyPointRequestApiService.deleteDocument(doc.id);
    documentationUploaded.value = documentationUploaded.value.filter(element => element.id != doc.id);

    doc.checked = false;

    emit('refresh');

  } catch (error) {
    console.log(error)
  }
}

const openPersonForm = () => {
  closeAllRegions();
  editingPerson.value = true;
  showRegion.value = true;
};

const openLocationForm = () => {

  if (props.request && props.request.property && !props.request.address) {
    dataToLoad.value = {
      city: props.request.property.address_city,
      province: props.request.property.address_city?.province,
      country: props.request.property.address_city?.province?.country,
      postal_code: props.request.property.address_postal_code?.code,
      street: props.request.property.address_street,
      street_number: props.request.property.address_street_number
    }
  }

  closeAllRegions();
  editingLocation.value = true;
  showRegion.value = true;
};

const fetchPerson = async (item) => {
  selectedPerson.value = item;

  emitChange()
  closeAllRegions();
};

const loadData = async () => {
  if (props.request) {
    if (props.request.person) {
      selectedPerson.value = props.request.person;
    }
    if (props.request.address) {
      selectedAddress.value = props.request.address;
    }
    if (props.request.contract) {
      contractUploaded.value = props.request.contract;
    }
    if (props.request.documents) {
      documentationUploaded.value = props.request.documents;
    }
    else {
      documentationUploaded.value = [];
    }
    cadastral.value = props.request.cadastral || null;
  }
};

onMounted(() => {
  loadData();
  getDocumentTypes();
});

watch(() => props.request, (newVal) => {
  loadData()
});

</script>

<template>
  <div id="wrapper" class="text-base">
    <h2 class="text-xl font-semibold mb-4"> {{ $t('billing_block.step') }} 3: {{ $t('service_block.request_person_title') }}</h2>

    <div class="mb-4">
      <label for="person" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
        <Icon v-show="selectedPerson" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
        <Icon v-show="!selectedPerson" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
        <span>{{ $t('common.requester') }}:</span>
      </label>

      <div v-if="selectedPerson" class="bg-green-100 p-4 rounded relative group">
        <p class="font-semibold">{{ selectedPerson.name }} {{ selectedPerson.surname }}<br />
          <span class="text-sm text-gray-500">{{ selectedPerson.token }}</span>
        </p>
        <button @click="openPersonForm"
          class="absolute focus:border-none focus:outline-none hover:text-sky-500 cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
          <Icon name="fa6-solid:pencil"/>
        </button>
      </div>
      <div v-else>
        <ButtonSeleccio @click="openPersonForm">{{ $t('common.select') }} {{ $t('common.requester') }}</ButtonSeleccio>
      </div>
    </div>

    <div class="mb-4">
      <label for="location" class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
        <Icon v-show="selectedAddress" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
        <Icon v-show="!selectedAddress" name="fa6-solid:asterisk" class="text-lg text-slate-400" />
        <span>{{ $t('service_block.placement') }}:</span>
      </label>

      <div v-if="selectedAddress" class="relative bg-green-100 p-4 rounded group">
        <p>
          <span class="font-semibold">{{ selectedAddress.address_complete }}</span><br />
          <span class="text-sm text-gray-500">{{ selectedAddress.postal_code }}</span> - <span
            class="text-sm text-gray-500">{{ selectedAddress.city?.name }}</span>
          <span v-if="selectedAddress.latitude && selectedAddress.longitude"><br />
            <a :href="`https://maps.google.com/?q=${selectedAddress.latitude},${selectedAddress.longitude}`"
              class="text-sky-500 underline" target="_blank">{{ selectedAddress.latitude }}, {{
                selectedAddress.longitude }}</a>
          </span>
        </p>
        <button @click="openLocationForm"
          class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
          <Icon name="fa6-solid:pencil"/>
        </button>
      </div>
      <div v-else>
        <ButtonSeleccio @click="openLocationForm">{{ $t('common.select') }} {{ $t('address_block.location') }}</ButtonSeleccio>
      </div>
    </div>

    <div class="mb-2">
      <label class="block text-sm font-medium text-slate-500 mb-2">{{ $t('common.cadastral') }}</label>
      <input type="text" v-model="cadastral" @change="emitChange" class="input"/>
    </div>

    <div class="mb-4">
      <div class="flex">
        <label for="contract" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('contract') }} </label>
      </div>
      <AtomsInputFile @update="handleContractUpdate" @delete="handleContractDelete" :name="'contractFile'"
        :uploaded="contractUploaded" :fullWidth="true"/>
    </div>

    <div class="mb-4">
      <div class="flex">
        <label for="documents" class="block text-sm font-medium text-gray-700 mb-2">{{ $t('common.documentation') }} </label>
      </div>
      
      <div v-for="doc in documentTypes" class="flex gap-2 items-center">
        <fieldset id="solicitant__box" class="mb-3 border px-3 py-2 bg-sky-50 w-full rounded">
          <legend class="px-3 font-semibold bg-white shadow">{{ doc.name }}</legend>
          <span class="flex gap-3 pl-1 pt-1">
            <label class="text-slate-800 text-base flex items-center gap-1" >
              <input @change="handleDocumentCheck(doc.document.checked, doc)" type="checkbox" class="mr-2" v-model="doc.document.checked" /> {{ t('common.checked') }}
            </label>
            <AtomsInputFile :disabled="!doc.document.checked" @update="handleDocumentUpdate($event, doc)" @delete="handleDocumentDelete(doc.document)" :name="'contractFile'"
              :uploaded="doc.document.file" :fullWidth="true" class="w-full"/>
          </span>
        </fieldset>
      </div>
    </div>

  </div><!-- end tab-content -->
  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="showRegion = false" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="px-10">
      <PersonSearch v-if="editingPerson" @saved="fetchPerson" />

      <AddAddress :selectedAddress="selectedAddress || dataToLoad" @new-address="newAddress" v-if="editingLocation"
        :isSubRegion="true" />

      <!-- <OrganismsTankEdit :id="null" v-if="editingTank" @saved="fetchTank" />
        <ChangeStatus v-if="editingStatus" entity="connection-request" parent_entity="connection_request" 
                      :id="connectionRequestId"  
                      :status="statusId" 
                      module="service" 
                      @changed="handleStatusChanged" /> -->
    </div>
  </div>
</template>
