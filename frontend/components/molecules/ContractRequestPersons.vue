<script setup>
// components/molecules/ContractRequestContract.vue
import { ref, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import PersonSearch from '~/components/organisms/PersonSearch.vue';
import AddCnae from '~/components/molecules/AddCnae.vue';
import _ from 'lodash';

const { $ConfiglistApiService, $PersonApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  request: {
    type: Object,
    required: false
  }
});

const emit = defineEmits(['change', 'show-subregion']);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const editingCnae = ref(false);
const cnaes = ref([]);
const cnaes_options = ref([]);
const selected_cnaes = ref([]);

// Objecte per gestionar l'estat de cada rol de persona
const editingPersons = ref({
  holder: false,
  owner: false,
  tenant: false
});

const selectedPersons = ref({
  holder: null,
  owner: null,
  tenant: null
});

// Definició dels rols amb indicació d'obligatorietat
const roles = [
  { key: 'holder', label: 'contract_block.holder', mandatory: true },
  { key: 'owner', label: 'contract_block.owner', mandatory: false },
  { key: 'tenant', label: 'contract_block.tenant', mandatory: false }
];

// Subregions details
const showRegionDetailComponent = ref(null);
const showEditingPerson = ref(null);
const regionDetailId = ref(null);

// Representants
const selectedRepresentatives = ref([]); // Array de { person: Object, type: Object|null }
const representativeTypes = ref([]);

// Funció per tancar totes les regions
const closeAllRegions = () => {
  // Tanquem tots els formularis de persona
  for (const role of roles) {
    editingPersons.value[role.key] = false;
  }

  // Tanquem region
  showRegion.value = false;
  showRegionDetailComponent.value = '';
};

// Funció per emetre els canvis
const emitChange = () => {
  let data = {
    holder: selectedPersons.value.holder?.id || null,
    owner: selectedPersons.value.owner?.id || null,
    tenant: selectedPersons.value.tenant?.id || null,
    representatives: selectedRepresentatives.value.map(rep => ({
      person: rep.person.id,
      type: rep.type ? rep.type.id : null
    })),
    cnaes: Array.isArray(selected_cnaes.value) ? selected_cnaes.value.map(c => c.code): [],
  };

  emit('change', data);
};

const onNewCnae = async (cnae) => {
  showRegion.value = false;
  setTimeout(async ()=> {
    editingCnae.value = false;
    if (cnae && cnae.id) {
      try {
        const personCnae = {
          person: selectedPersons.value['holder'].id,
          cnae: cnae.id,
          token: _.random(10000, 99999)
        }
    
        const res = await $PersonApiService.postCNAE(personCnae);
        
        cnaes.value.push(cnae);
        cnaes_options.value.push({
          label: cnae.description,
          code: res.id
        });
        
        selected_cnaes.value.push({
          label: cnae.description,
          code: res.id
        });
        emitChange();
      }
      catch (error) {
        console.error('Error creating personCNAE:', error);
      }
    }

  },200)
};
// Funcions per obrir els formularis de cada rol
const openPersonForm = (roleKey) => {
  editingCnae.value = false;
  showEditingPerson.value = `editingPersons${roleKey.charAt(0).toUpperCase() + roleKey.slice(1)}`; // 'editingPersonsHolder'
  closeAllRegions();
  editingPersons.value[roleKey] = true;
  showRegion.value = true;
};

// Funció per eliminar una persona seleccionada per rols opcionals
const removePerson = (roleKey) => {
  selectedPersons.value[roleKey] = null;
  emitChange();
};

// Funció per gestionar la salvaguarda d'una persona
const onPersonSaved = async (roleKey, item) => {
  if (roleKey === 'representative') {
    const defaultType = representativeTypes.value.find(type => type.is_default) || null;
    selectedRepresentatives.value.push({
      person: item,
      type: defaultType
    });
  } else {
    selectedPersons.value[roleKey] = item;
  }
  if (roleKey === 'holder') {
    getCNAES(item.id);
  }
  emitChange();
  closeAllRegions();
};

const showCnaeForm = async (id) => {
  editingCnae.value = true;
  showRegion.value = true;
};
const getCNAES = async (res) => {
  cnaes.value = res.cnaes ?? [];

  cnaes_options.value = Array.isArray(res.cnaes)
    ? res.cnaes.map(c => ({
        label: c.cnae?.description ?? '',
        code: c.id
      }))
    : [];
};

// Funció per carregar les dades de la sol·licitud existent
const loadData = async () => {
  if (props.request) {
    for (const role of roles) {
      if (props.request[role.key]) {
        selectedPersons.value[role.key] = await $PersonApiService.getFullDetail(props.request[role.key]);
      }
      if (props.request[role.key] && role.key == 'holder') {
        await getCNAES(selectedPersons.value[role.key])
        selected_cnaes.value = Array.isArray(props.request.cnaes) ? props.request.cnaes.map(c => ({
          label: c.cnae?.description ?? '',
          code: c.id
          })): [];
      }
    }

    // Carregar representants si existeixen
    if (props.request.representatives && Array.isArray(props.request.representatives)) {
      selectedRepresentatives.value = props.request.representatives.map(rep => ({
        person: rep.person,
        type: rep.type || null
      }));
    }
  }
};

// Funció per obtenir els tipus de representant
const fetchRepresentativeType = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('contract/contract-representative-type');
    representativeTypes.value = data.results;
  } catch (error) {
    console.error('Error fetching representative types:', error);
  }
};

// Funció per eliminar un representant
const updateSelectedCnaes = (e) => {
  selected_cnaes.value.push(e);
};

// Funció per eliminar un representant
const removeRepresentative = (index) => {
  selectedRepresentatives.value.splice(index, 1);
  emitChange();
};

// onMounted
onMounted(() => {
  loadData();
  fetchRepresentativeType();
});

// Observa canvis en la sol·licitud per recarregar les dades si cal
watch(() => props.request, (newVal) => {
  loadData();
});

// Observa canvis en els seleccionats per emetre l'esdeveniment
watch(selectedPersons, () => {
  emitChange();
}, { deep: true });

// Observa canvis en els representants per emetre l'esdeveniment
watch(selectedRepresentatives, () => {
  emitChange();
}, { deep: true });

</script>

<template>
  <div id="wrapper" class="text-base">
    <!-- Títol -->
    <h2 class="text-xl font-semibold mb-4">
      {{ $t('contract_block.request_persons_title') }}
    </h2>

    <!-- Selecció de Persones per Rols -->
    <div class="mb-4" v-for="role in roles" :key="role.key">
      <label :for="role.key" class="flex items-center text-sm font-medium text-gray-700 mb-3 gap-2">
        <!-- Icona segons si la persona està seleccionada -->
        <Icon v-show="selectedPersons[role.key]" name="fa6-solid:circle-check" class="text-xl text-emerald-600" />
        <Icon v-show="!selectedPersons[role.key] && role.mandatory" name="fa6-solid:asterisk"
          class="text-lg text-pink-600" />
        <Icon v-show="!selectedPersons[role.key] && !role.mandatory" name="fa6-solid:circle"
          class="text-lg text-slate-400" />
        <!-- Nom del rol -->
        <span>
          {{ $t(role.label) }}
        </span>
      </label>

      <!-- Persona seleccionada -->
      <div v-if="selectedPersons[role.key]" class="bg-green-100 p-4 rounded relative max-w-xl group">
        <p class="font-semibold flex gap-3">
          <AtomsVulnerabilityCheck v-if="selectedPersons[role.key].vulnerability_level>0"
              :vulnerability_level="selectedPersons[role.key].vulnerability_level" :small="true" class="mr-1" />
          <span>{{ selectedPersons[role.key].name }} {{ selectedPersons[role.key].surname }}</span>
          <span class="text-sm text-gray-500">{{ selectedPersons[role.key].token }}</span>
        </p>
        <button @click="openPersonForm(role.key)"
          class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-12 top-3 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100"
          :title="`${t('common.modify')} ${t(role.label)}`">
          <Icon name="fa6-solid:pencil" />
        </button>
        <!-- Botó per eliminar persona seleccionada per rols opcionals -->
        <button v-if="!role.mandatory" @click="removePerson(role.key)"
          class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-red-600 opacity-0 transition-all duration-300 group-hover:opacity-100"
          :title="`${t('common.delete')} ${t(role.label)}`">
          <Icon name="fa6-solid:trash" />
        </button>
        <div v-if="role.key === 'holder' && selectedPersons[role.key].is_juridic">
          <div class="mb-2 border rounded bg-slate-100 mt-2 px-3 pb-3 pt-2">
            <div class="field">
              <div class="flex">
                <label for="Zone" class="font-semibold flex gap-3">{{ $t('common.select') }} {{ $t('contract_block.cnae') }}</label>
              </div>
            </div>
            <div class="flex">
              <v-select class="block w-full mr-1 required"  v-model="selected_cnaes" :options="cnaes_options" multiple placeholder="Select options" @update:modelValue="emitChange" />
              <button
                class="w-9 h-9 border-gray-300 border rounded enabled:hover:bg-slate-200 transition-all duration-200 bg-white flex items-center justify-center"
                @click="showCnaeForm">
                <Icon name="fa6-solid:plus" class="text-md text-slate-600" />
              </button>
            </div>
          </div>
        </div>
      </div>
      <!-- Botó per seleccionar o afegir persona -->
      <div v-else>
        <ButtonSeleccio @click="openPersonForm(role.key)" class="py-2">
          {{ $t('common.select') }} {{ $t(`${role.label}`) }}
        </ButtonSeleccio>
      </div>
    </div>
    <!-- /end Selecció de Persones per Rols -->

    <!-- Selecció de Representants -->
    <div class="mb-4">
      <div class="text-sm font-medium text-gray-700 mb-3">
        <label class="block mb-1">{{ $t('contract_block.representatives') }}:</label>
        <button @click="openPersonForm('representative')"
          class="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600" :title="`${t('common.add')} ${t('contract_block.representative')}`">
          + {{ $t('common.add') }} {{ $t('contract_block.representative') }}
        </button>
      </div>

      <!-- Llista de representants -->
      <div v-if="selectedRepresentatives.length > 0" class="space-y-4">
        <div v-for="(rep, index) in selectedRepresentatives" :key="index"
          class="bg-yellow-100 p-4 rounded relative max-w-xl group">
          <p class="font-semibold flex flex-col sm:flex-row sm:justify-between sm:items-center gap-3">
            <span>{{ rep.person.name }} {{ rep.person.surname }}</span>
            <span class="text-sm text-gray-500 mr-10">{{ rep.person.token }}</span>
          </p>
          <div class="mt-2">
            <label class="text-sm font-medium text-gray-700">{{ $t('contract_block.representative_type') }}:</label>
            <select v-model="rep.type"
              class="mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-sky-500 focus:border-sky-500 sm:text-sm rounded-md">
              <option value="" disabled :selected="!rep.type">-- {{ $t('common.select') }} {{ $t('common.type') }} --</option>
              <option v-for="type in representativeTypes" :key="type.id" :value="type" :selected="type.is_default">
                {{ type.name }}
              </option>
            </select>
          </div>
          <button @click="removeRepresentative(index)"
            class="absolute cursor-pointer shadow-md border text-sm w-8 h-8 bg-white right-3 top-3 rounded-md text-red-600 opacity-0 transition-all duration-300 group-hover:opacity-100"
            aria-label="Eliminar Persona">
            <Icon name="fa6-solid:trash" />
          </button>

        </div>
      </div>
      <!-- /end Llista de representants -->
    </div>
    <!-- /end Selecció de Representants -->

    <!-- Regió lateral per formularis -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-transform duration-500 ease py-2 text-base bg-white z-10"
      :class="{
        'translate-x-0': showRegion,
        'translate-x-full': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-1/2': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3 flex justify-start">
        <button @click="showRegion = false"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300 rounded" aria-label="Tancar formulari">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <!-- Formularis per cada rol -->
        <PersonSearch v-if="showEditingPerson === 'editingPersonsHolder' && editingPersons.holder"
          @saved="onPersonSaved('holder', $event)" :title="`${t('common.select')} ${t('common.or')} ${t('common.add')} ${t('contract_block.holder')}`" />
        <PersonSearch v-if="showEditingPerson === 'editingPersonsOwner' && editingPersons.owner"
          @saved="onPersonSaved('owner', $event)" :title="`${t('common.select')} ${t('common.or')} ${t('common.add')} ${t('contract_block.owner')}`" />
        <PersonSearch v-if="showEditingPerson === 'editingPersonsTenant' && editingPersons.tenant"
          @saved="onPersonSaved('tenant', $event)" :title="`${t('common.select')} ${t('common.or')} ${t('common.add')} ${t('contract_block.tenant')}`" />
        <!-- Formulari per afegir representant -->
        <PersonSearch v-if="showEditingPerson === 'editingPersonsRepresentative' && editingPersons.representative"
          @saved="onPersonSaved('representative', $event)" :title="`${t('common.select')} ${t('common.or')} ${t('common.add')} ${t('contract_block.representative')}`" />
        <AddCnae v-model="cnaes" @item-clicked="onNewCnae" v-if="editingCnae" :blockDelete="true" />
      </div>
    </div><!-- /end Regió lateral per formularis -->

  </div><!-- /end #wrapper -->
</template>