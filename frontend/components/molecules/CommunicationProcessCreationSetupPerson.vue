<script setup>
import SearchEntityInput from './SearchEntityInput.vue';
import OptionSelectorGroup from '../atoms/OptionSelectorGroup.vue';

const props = defineProps({
  person_data: Object,
})

const { t } = useI18n();
const emit = defineEmits(['change'])
const { $ConfiglistApiService, $StreetApiService, $AddressApiService } = useNuxtApp();


const banks = ref([])

const selectedBank = ref(null)
const selectedPersons = ref([])
const selectMorosity = ref(['is_not_debtor'])
const selectVulnerability = ref(['0'])
const selectJuridic = ref(['0', '1'])

const loadingBanks = ref(false)

const contract_filter_data = ref({})

const morosityTypesOptions = [
  { value: 'is_not_debtor', name: 'contract_block.no_debtor'},
  { value: 'is_debtor', name: 'contract_block.debtor'},
]

const vulnerabilityTypesOptions = [
  { value: '0', name: 'contract_block.no_vulnerable' },
  { value: '1', name: 'contract_block.short_in_social_risk' },
  { value: '2', name: 'contract_block.vulnerable' },
]

const juridicOptions = [
  { value: '0', name: 'common.physical' },
  { value: '1', name: 'common.juridic' },
]

const loadSelectData = async () => {

}

const changeMorosity = (value) => {
  if (selectMorosity.value.includes(value)) {
    selectMorosity.value = selectMorosity.value.filter(a => a !== value)
  }
  else {
    selectMorosity.value.push(value)
  }
}

const changeVulnerability = (value) => {
  if (selectVulnerability.value.includes(value)) {
    selectVulnerability.value = selectVulnerability.value.filter(a => a !== value)
  }
  else {
    selectVulnerability.value.push(value)
  }
}

const changeJuridic = (value) => {
  if (selectJuridic.value.includes(value)) {
    selectJuridic.value = selectJuridic.value.filter(a => a !== value)
  }
  else {
    selectJuridic.value.push(value)
  }
}

const getBanks = async (page = 1, search = '') => {
  let response = null;
  loadingBanks.value = true;
  try {
    response = await $AddressApiService.getBanks(search, [], page, null, false);
    const items = response.map(item => ({
      value: item.id,
      label: item.name + ' (' + item.token + ')'
    }));

    banks.value = items;

    return {
      items: items,
      hasNextPage: response && response.next ? true : false
    };
  } catch (error) {
    console.error(`Error fetching banks:`, error);
    return {
      items: [],
      hasNextPage: false
    };
  } finally {
    loadingBanks.value = false;
  }
}

const onPersonSelected = async (event) => {
  selectedBank.value = null
  selectMorosity.value = []
  selectVulnerability.value = []
  selectJuridic.value = []
  if (selectedPersons.value.includes(event)) {
    selectedPersons.value = selectedPersons.value.filter(a => a.id !== event.id)
  }
  else {
    selectedPersons.value.push(event)
  }
  await emitChange()
}

const removeSelectedPerson = (person) => {
  selectedPersons.value = selectedPersons.value.filter(a => a.id !== person.id)
  emitChange()
}

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'bank':
      selectedBank.value = event;
      emitChange()
      break;
  }
}

const loadData = async (contractData) => {
  if (contractData?.bank) selectedBank.value = banks.value.filter(b => contractData?.bank === b.value)
  if (contractData?.persons) selectedPersons.value = contractData?.persons
  if (contractData?.morosity) selectMorosity.value = morosityTypesOptions.filter(m => contractData?.morosity.includes(m.value))
  if (contractData?.vulnerability) selectVulnerability.value = vulnerabilityTypesOptions.filter(v => contractData?.vulnerability.includes(v.value))
  if (contractData?.juridic) selectJuridic.value = juridicOptions.filter(j => contractData?.juridic.includes(j.value))
}


const emitChange = () => {
  contract_filter_data.value = {
    bank: selectedBank.value ? selectedBank.value.value : null,
    morosity: selectMorosity.value,
    vulnerability: selectVulnerability.value,
    juridic: selectJuridic.value,
    persons: selectedPersons.value
  }
  emit('change', contract_filter_data.value)
}

onMounted(async () => {
  await loadSelectData()
  await loadData(props.person_data)
})


watch([
  selectedBank,
  selectMorosity,
  selectVulnerability,
  selectJuridic
], async () => {
  if (selectedPersons.value.length > 0) {
    if (selectedBank.value ||
      selectMorosity.value.length > 0 ||
      selectVulnerability.value.length > 0 ||
      selectJuridic.value.length > 0) {
      selectedPersons.value = []
    }
  }
  await emitChange()
}, { deep: true });

watch(props.person_data, async (newVal) => {
  await loadData(newVal)
}, { deep: true });

</script>

<template>
  <div class="py-3 bg-white rounded-lg shadow-sm">

    <div class="grid grid-cols-2 gap-4">

      <div>
        <div class="text-sm font-medium text-gray-500 mb-2 flex items-center gap-2">
          <abbr :title="t('informative_block.info_show_all_data')"
            class="flex items-center">
            <Icon name="fa6-solid:circle-info" class="text-slate-500" />
          </abbr>
          <span>
            {{ t('contract_block.deliquency') }}
          </span>
        </div>
        <OptionSelectorGroup
          :options="morosityTypesOptions"
          :selected-values="selectMorosity"
          selection-mode="multiple"
          indicator-type="radio"
          @select="changeMorosity"
        />
      </div>

      <div>
        <div class="text-sm font-medium text-gray-500 mb-2 flex items-center gap-2">
          <abbr :title="t('informative_block.info_show_all_persons')"
            class="flex items-center">
            <Icon name="fa6-solid:circle-info" class="text-slate-500" />
          </abbr>
          <span>
            {{ t('contract_block.vulnerability') }}
          </span>
        </div>
        <OptionSelectorGroup
          :options="vulnerabilityTypesOptions"
          :selected-values="selectVulnerability"
          selection-mode="multiple"
          indicator-type="radio"
          @select="changeVulnerability"
        />
      </div>

      <div>
        <div class="text-sm font-medium text-gray-500 mb-2 flex items-center gap-2">
          <abbr :title="t('informative_block.info_show_all_persons')"
            class="flex items-center">
            <Icon name="fa6-solid:circle-info" class="text-slate-500" />
          </abbr>
          <span>
            {{ t('customer_service_block.customer_type') }}
          </span>
        </div>
        <OptionSelectorGroup
          :options="juridicOptions"
          :selected-values="selectJuridic"
          selection-mode="multiple"
          indicator-type="radio"
          @select="changeJuridic"
        />
      </div>

      <span></span>

      <SearchEntityInput :service="$PersonApiService" @select="onPersonSelected" :title="$t('search_block.search_person')"
        :result_value="'full_name'" class="mt-auto" />

      <div v-if="selectedPersons?.length > 0" class="mb-2">
        <label class="block text-sm font-medium text-slate-600 mb-2">{{ $t('contract_block.selected_persons') }}</label>
        <div class="flex flex-wrap gap-2 ">
          <span v-for="person in selectedPersons" :key="person.id"
            class="group relative bg-slate-100 text-slate-800 px-3 py-1 rounded-full text-sm border border-slate-300 flex items-center gap-2">
            <span>
              {{ person.full_name }}
              <span class="ml-2 text-xs text-slate-500">
                {{ person.token }}
              </span>
            </span>
            <button @click="removeSelectedPerson(person)"
              class="absolute right-0 top-0 h-4 w-4 bg-white rounded-full text-slate-500 opacity-0 hover:text-slate-700 hover:underline group-hover:opacity-100 transition-all duration-300">
              <Icon name="fa6-solid:xmark"
                class="text-red-500 text-sm m-auto opacity-0 group-hover:opacity-100 m-auto" />
            </button>
          </span>
        </div>
      </div>
      <span v-else></span>

      <AtomsInfiniteScrollVueSelect :labelText="t('common.bank')" :loadFunction="getBanks" :item="selectedBank"
        @update:modelValue="updateSelect($event, 'bank')">
      </AtomsInfiniteScrollVueSelect>
    </div>
  </div>
</template>

<style scoped>
.grid {
  transition: all 0.3s ease;
}
</style>