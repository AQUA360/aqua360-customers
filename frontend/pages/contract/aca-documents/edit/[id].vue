<script setup>
// path: pages/contract/contract-requests/edit/[id].vue
import { ref, onMounted } from 'vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import BonificationDetail from '~/components/molecules/BonificationDetail.vue';
import VariableDetail from '~/components/molecules/VariableDetail.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import debounce from 'lodash.debounce';

const { t } = useI18n();
const route = useRoute()
const toast = useToast();
const objectPermissions = ref(null);
const { $ACADocumentApiService, $PersonApiService, $ContractApiService, $ConfigProjectApiService, $ConfiglistApiService } = useNuxtApp();

const id = ref(0);
const loading = ref(true);
const saving = ref(false);
const doc = ref(null);
const person = ref(null);
const contract = ref(null);
const showSummary = ref(false);

const searchQuery = ref('');
const searchInput = ref(null);
const searchResults = ref([]);

const entries = ref([])
const currentIndex = ref(0)

const warning = ref(false);

const save = async () => {
  const statusToken = await $ConfigProjectApiService.get('aca_bonification_processed');
  const statuses = await $ConfiglistApiService.getAll('contract/aca-document-status');
  const finishStatus = statuses.results.find(s => s.token == statusToken);
  const data = {
    id: doc.value.id,
    status_id: finishStatus.id
  }
  try {
    await $ACADocumentApiService.save(data);
    navigateTo('/contract/aca-documents/');
  }
  catch (error) {
    console.error('Error saving document:', error);
  }
}

const getData = async (showLoading = true) => {
  if (showLoading) {
    loading.value = true;
    doc.value = null;
    entries.value = []
    currentIndex.value = 0;
  }
  try {
    if (id.value) {
      const data = await $ACADocumentApiService.getDetail(id.value);
      doc.value = data;
      entries.value = data.document_changes;

      getUserData();
    }
  } catch (error) {
    console.error('Error loading draft:', error);
  }
  if (showLoading) loading.value = false;
};

const getUserData = async () => {
  const entry = entries.value[currentIndex.value];
  searchResults.value = [];
  try {
    const found = await findPerson(entry);
    if (found) {
      await loadPerson(found.id);
    } else {
      person.value = null;
      contract.value = null;
    }
  } catch (error) {
    console.error('Error loading user data:', error);
    person.value = null;
    contract.value = null;
  }
  saving.value = false;
};

// Persona de la línia: pel DNI i, si no n'hi ha una de sola (DNI genèric com 99999999R,
// compartit per moltes persones, o inexistent), pel nom que porta el fitxer. Si el nom
// en dona més d'una, la que és titular/propietària/llogatera del contracte de la línia;
// si no, es mostren els resultats al cercador perquè l'usuari triï.
const findPerson = async (entry) => {
  try {
    return await $PersonApiService.getDetailByToken(entry.person_NIF);
  } catch (error) {
    // Es continua pel nom.
  }
  if (!entry.person_name) return null;

  const { results = [] } = await $PersonApiService.getAll(entry.person_name);
  if (results.length === 1) return results[0];
  if (results.length === 0) return null;

  const lineContract = await $ContractApiService.getByToken(entry.contract_code);
  const roleIds = ['holder', 'owner', 'tenant']
    .map(role => lineContract?.[role]?.id ?? lineContract?.[role])
    .filter(Boolean);
  const match = results.find(r => roleIds.includes(r.id));
  if (match) return match;

  searchQuery.value = entry.person_name;
  searchResults.value = results;
  return null;
};

const loadPerson = async (personId) => {
  person.value = await $PersonApiService.getDetail(personId);

  try {
    const contracts = await $ContractApiService.getByPerson(personId);
    const c = contracts.find(c => c.token == entries.value[currentIndex.value].contract_code);

    warning.value = !c;
    const selected = c || contracts[0];
    contract.value = selected ? await $ContractApiService.getDetail(selected.id) : null;
  } catch (error) {
    console.error('Error loading contracts:', error);
    contract.value = null;
  }
};

const validateChange = async (validate) => {
  try {
    saving.value = true;
    const res = await $ACADocumentApiService.validateChange(entries.value[currentIndex.value].id, validate);
    entries.value[currentIndex.value].accepted = validate;
    changeIndex(1);
    saving.value = false;
  } catch (error) {
    console.error('Error loading user data:', error);
    saving.value = false;
  }
};

const searchPerson = debounce(async () => {
  // console.log('searchPerson', searchQuery.value)
  if (searchQuery.value) {
    const data = await $PersonApiService.getAll(searchQuery.value);
    searchResults.value = data.results;
  } else {
    searchResults.value = [];
  }
}, 300);

const handleClickOutside = () => {
  searchResults.value = [];
};

const selectPerson = async (p) => {
  searchResults.value = [];
  searchQuery.value = '';
  // Per id i no per DNI: n'hi pot haver de repetits (99999999R).
  try {
    await loadPerson(p.id);
  } catch (error) {
    console.error('Error loading person:', error);
    person.value = null;
    contract.value = null;
  }
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($ACADocumentApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  id.value = parseInt(route.params.id);
  getData();
});

const changeIndex = async (i) => {
  saving.value = true;
  if ((i > 0 && currentIndex.value + 1 < entries.value.length) || i < 0 && currentIndex.value > 0) {
    currentIndex.value += i
    await getUserData()
  }
  else if (i > 0 && currentIndex.value + 1 == entries.value.length) {
    showSummary.value = true;
  }

  saving.value = false;
}


</script>

<template>
  <div v-if="objectPermissions?.can_change" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1 v-if="doc?.closing" class="mb-3">{{ $t('contract_block.validate_bonifications_closing') }}</H1>
      <H1 v-else class="mb-3">{{ $t('contract_block.validate_bonifications') }}</H1>
    </div>
    <div v-if="loading">
      <div class="border border-gray-300 rounded-b p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else>
      <div>
        <a :href="doc.file" target="_blank" class="text-sky-500">{{ doc.file }}</a>

        <div class="grid grid-cols-2 gap-3 my-5">
          <FieldDetail :label='$t("common.type")' :value=doc.type></FieldDetail>
          <FieldDetail :label='$t("contract_block.supplier")' :value=doc.supplier></FieldDetail>

          <FieldDetail :label='$t("common.date")' :value=doc.date></FieldDetail>
          <FieldDetail :label='$t("common.origin")' :value=doc.source></FieldDetail>

          <FieldDetail :label='$t("common.number")' :value=doc.number></FieldDetail>
        </div>
      </div>
      <div v-if="!showSummary">
        <div class="flex items-center">
          <span class="text-xl font-bold">{{ t('common.check_changes') }}:</span>
          <button @click="changeIndex(-1)" :disabled="currentIndex == 0 || saving"
            class="transition-all duration-150 bg-gray-200 text-gray-500 p-2 enabled:hover:bg-gray-300 rounded-full w-6 h-6 flex items-center justify-center mx-3 disabled:opacity-50">
            <Icon name="fa6-solid:chevron-left" /> <!-- Font Awesome Right Chevron -->
          </button>
          <span class="text-xl font-bold">({{ currentIndex + 1 }} / {{ entries.length }})</span>
          <button @click="changeIndex(1)" :disabled="currentIndex + 1 == entries.length || saving"
            class="transition-all duration-150 bg-gray-200 text-gray-500 p-2 enabled:hover:bg-gray-300 rounded-full w-6 h-6 flex items-center justify-center mx-3 disabled:opacity-50">
            <Icon name="fa6-solid:chevron-right" /> <!-- Font Awesome Right Chevron -->
          </button>
        </div>
        <div class="mt-4" v-if="entries.length > 0 && entries[currentIndex]">
          <div class="grid grid-cols-3 gap-4">
            <div class="pr-4 border-r">
              <fieldset id="setup__box" class="mb-3 border px-3 py-2 bg-sky-50">
                <legend class="px-3 font-semibold bg-white shadow">{{ $t('contract_block.aca_document_data') }}</legend>
                <div> <!-- class="grid grid-cols-2 gap-3" -->
                  <FieldDetail class="py-2" :label='$t("common.name")' :value=entries[currentIndex].person_name></FieldDetail>
                  <FieldDetail class="py-2" :label='$t("common.person_id")' :value=entries[currentIndex].person_NIF>
                  </FieldDetail>
                  <FieldDetail class="py-2" :label='$t("address_block.address")' :value=entries[currentIndex].address></FieldDetail>
                  <FieldDetail class="py-2" :label='$t("address_block.postal_code")' :value=entries[currentIndex].postal_code>
                  </FieldDetail>
                  <FieldDetail class="py-2" :label='$t("address_block.city_code")' :value=entries[currentIndex].city_code>
                  </FieldDetail>
                  <FieldDetail class="py-2" :label='$t("contract_block.contract_code")' :value=entries[currentIndex].contract_code>
                  </FieldDetail>
                </div>
              </fieldset>
            </div>

            <div class="col-span-2">
              <div class="mb-2" v-click-outside="handleClickOutside">
                <label for="search" class="block text-sm font-medium text-gray-700 mb-2">
                  {{ t('dashboard.search') }} {{ t('common.person_id') }} {{ t('common.or') }} {{ t('common.name') }}
                </label>
                <input id="search" type="text" v-model="searchQuery" @input="searchPerson" ref="searchInput"
                  class="input" :placeholder="t('contract_block.add_person_id')" autocomplete="off" />
                <ul v-if="searchResults && searchResults.length > 0" class="border border-gray-300 rounded-md divide-y divide-gray-200 absolute z-10 bg-white shadow-lg max-h-60 overflow-y-auto">
                  <li v-for="result in searchResults" :key="result.id" @click="selectPerson(result)"
                    class="px-4 py-2 cursor-pointer hover:bg-gray-100">
                    {{ result.name }} {{ result.surname }} ({{ result.token }})
                  </li>
                </ul>
              </div>
              <fieldset id="setup__box" class="mb-3 border px-3 py-2 bg-sky-50">
                <legend class="px-3 font-semibold bg-white shadow">{{ $t('contract_block.customers_data') }}</legend>
                <div v-if="person" class="grid grid-cols-2 gap-3">
                  <FieldDetail :label='$t("common.name")' :value=person.full_name></FieldDetail>
                  <FieldDetail :label='$t("common.person_id")' :value=person.token></FieldDetail>
                </div>
                <div v-else>
                  <div class="text-center text-xl text-red-600">{{ $t('contract_block.no_person_found') +
                    entries[currentIndex].person_NIF }}</div>
                </div>
              </fieldset>
              <fieldset v-if="person" id="setup__box" class="mb-3 border px-3 py-2 bg-sky-50">
                <legend class="px-3 font-semibold bg-white shadow">{{ $t('contract') }}</legend>
                <div v-if="contract" class="grid grid-cols-2 gap-3">
                  <span v-if="warning" class="text-yellow-600 col-span-2">{{ $t('contract_block.person_no_contract_token') }}: {{ entries[currentIndex].contract_code }}</span>
                  <div role="row" class="grid grid-cols-2">
                    <FieldDetail :label="t('common.identification')" :value="contract.token" class="font-bold"></FieldDetail>
                    <FieldDetail :label="t('common.creation_date')" :value="formatDate(contract.created_at)">
                      <AtomsDate :date="contract.created_at"></AtomsDate>
                    </FieldDetail>
                  </div>
                  <div role="row" class="grid grid-cols-2">
                    <FieldDetail :label="$t('contract_block.holder')" :value="contract.holder?.full_name" class="mr-5">
                    </FieldDetail>
                    <FieldDetail :label="$t('common.short_supply')">
                      <span>{{ contract.supply_point_default?.address_complete }}</span>
                    </FieldDetail>
                  </div>

                  <div v-if="contract.representatives && contract.representatives.length > 0">
                    <div v-for="representant in contract.representatives" class="grid grid-cols-2">
                      <FieldDetail :label="$t('contract_block.representative')" :value="representant.full_name" class="flex mr-5">
                        <AtomsPersonBadge :person="representant.person" class="font-bold" />
                      </FieldDetail>
                      <FieldDetail :label="$t('contract_block.representative_role')" :value="representant.type?.name || null">
                      </FieldDetail>
                    </div>
                  </div>

                  <div role="row" class="grid grid-cols-2">
                    <FieldDetail :label="$t('common.status')" class="flex mr-5">
                      <AtomsColorBadge :value="contract.status?.name" :color="contract.status?.color" />
                    </FieldDetail>
                    <FieldDetail :label="$t('common.usage_type')" :value="contract.use_type?.name"></FieldDetail>
                  </div>
                  <div role="row" class="grid grid-cols-2">
                    <FieldDetail :label="$t('contract_block.client_type')" :value="contract.client_type?.name"></FieldDetail>
                    <FieldDetail :label="$t('contract_block.category')" :value="contract.category?.name"></FieldDetail>
                  </div>
                  <div v-if="contract.owner || contract.tenant">
                    <div class="grid grid-cols-2">
                      <FieldDetail v-if="contract.owner" :label="$t('contract_block.owner')" :value="contract.owner?.token">
                        <abbr :title="contract.owner.token">{{ contract.owner.full_name }}</abbr>
                      </FieldDetail>
                      <FieldDetail v-if="contract.tenant" :label="$t('contract_block.tenant')"
                        :value="contract.tenant?.token">
                        <abbr :title="contract.tenant.token">{{ contract.tenant.full_name }}</abbr>
                      </FieldDetail>
                    </div>
                  </div>
                  <hr class="my-2 col-span-2" />
                  <div class="grid grid-cols-2 col-span-2 gap-3">
                    <!-- Selecció de Bonificacions -->
                    <div class="mb-4">
                      <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
                        <span>{{ $t('bonifications') }}:</span>
                      </label>
                      <div>
                        <div v-if="contract.bonifications" class="mt-2">
                          <BonificationDetail v-for="bonification in contract.bonifications" :deleteButton="false"
                            :item="bonification" class="mb-2 text-slate-slate bg-green-100" />
                        </div>
                      </div>
                    </div>
                    <!-- /end Selecció de Bonificacions -->

                    <!-- Selecció de Variables -->
                    <div class="mb-4">
                      <label class="flex text-sm font-medium text-gray-700 mb-3 gap-2">
                        <span>{{ $t('variables') }}:</span>
                      </label>
                      <div>
                        <div v-if="contract.variables">
                          <div v-for="variable in contract.variables" class="mt-2 text-sm bg-green-100 p-2">
                            <VariableDetail :item="variable" class="bg-green-100" :deleteButton="false" />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else>
                  <div class="text-center text-xl text-red-600"> {{ $t('contract_block.person_no_contract') }}</div>
                </div>
              </fieldset>
            </div>
          </div>
          <div class="flex items-center space-x-2">
            <span class="text-l font-bold">{{ t('common.accepted_changes') }}:</span>
            <Icon name="fa6-solid:check" v-show="entries[currentIndex].accepted" class="text-xl text-green-600" />
            <Icon v-show="!entries[currentIndex].accepted" name="fa6-solid:xmark" class="text-xl text-red-600" />
          </div>
        </div>
        <hr class="mb-2 mt-3" />
      </div>
      <div v-else>
        <MoleculesAcaChangesTable :document_changes="entries" />
      </div>

      <div v-if="!showSummary" class="flex flex-row-reverse mt-4 h-10">
        <button @click="showSummary = true" :disabled="saving" class="button-success">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
            $t('common.finish') }}
        </button>
        <div class="border-r border-slate-400 h-full mx-10">
        </div>
        <button @click="validateChange(true)" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:check" />&nbsp; {{
            $t('common.validate') }}
        </button>
        <button @click="validateChange(false)" :disabled="saving" class="button-delete mr-5">
          <Icon name="fa6-solid:xmark" />&nbsp; {{ $t('common.reject') }}
        </button>
      </div>

      <div v-else class="flex flex-row-reverse mt-4 h-10">
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp; {{
            $t('common.save') }}
        </button>
        <div class="border-r border-slate-400 h-full mx-10">
        </div>
        <button @click="showSummary = false" :disabled="saving" class="button-default">
          <Icon name="fa6-solid:eye" />&nbsp; {{
            $t('common.modifications') }}
        </button>
      </div>
    </div>
  </div>
</template>
