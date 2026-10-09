<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import debounce from 'lodash.debounce';

const { t } = useI18n();
const { $PersonApiService } = useNuxtApp();
const emits = defineEmits(['saved']);

const isExistingApplicant = ref(true);
const searchQuery = ref('');
const searchInput = ref(null);
const searchResults = ref([]);
const isJuridic = ref(false);
const name = ref('');
const surname = ref('');
const token = ref('');
const found = ref(true);


const props = defineProps({
  title: {
    type: String,
    required: false,
    default: null,
  },
  personLabel: {
    type: String,
    required: false,
    default: 'common.requester',
  },
  isExistingLabel: {
    type: String,
    required: false,
    default: 'contract_block.is_existing_applicant',
  },
  allowCreate: {
    type: Boolean,
    required: false,
    default: true,
  },
});


const searchPerson = debounce(async () => {
  // console.log('searchPerson', searchQuery.value)
  if (searchQuery.value) {
    const data = await $PersonApiService.getAll(searchQuery.value);
    searchResults.value = data.results;
    if (searchResults.value.length === 0) {
      found.value = false;
    }
  } else {
    searchResults.value = [];
    found.value = true;
  }

}, 100);

const selectPerson = (person) => {
  emits('saved', person);
};

const createPerson = async () => {
  const newPerson = {
    name: name.value,
    surname: isJuridic.value ? '' : surname.value,
    token: token.value,
    is_juridic: isJuridic.value,
  };
  const savedPerson = await $PersonApiService.save(newPerson);
  selectPerson(savedPerson);
};


onMounted(() => {
  nextTick(() => {
    if (searchInput.value) {
      searchInput.value.focus();
    }
  });
});

watch(isJuridic, () => {
  if (isJuridic.value) {
    surname.value = '';
  }
});
</script>

<template>
  <div id="wrapper" class="text-base">
    <h2 class="text-xl font-semibold mb-4">{{ title ? title : `${t('common.select')} ${t('common.or')} ${t('common.add')} ${t(personLabel)}` }}</h2>

    <div class="mb-4">
      <label class="block text-sm font-medium text-gray-700 mb-2">{{ t(isExistingLabel) }}</label>
      <div class="flex items-center mb-4">
        <label class="mr-4">
          <input type="radio" v-model="isExistingApplicant" :value="true" /> {{ t('common.yes') }}, {{ t('dashboard.search') }} {{ t(personLabel) }}
        </label>
        <label v-if="allowCreate">
          <input type="radio" v-model="isExistingApplicant" :value="false" /> {{ t('common.no') }}, {{ t('common.create_new') }}
        </label>
      </div>
    </div>

    <div v-if="isExistingApplicant === true">
      <label for="search" class="block text-sm font-medium text-gray-700 mb-2">
        {{ `${$t('dashboard.search')} ${$t('common.name')} ${$t('common.or')} ${$t('common.person_id')}` }}</label>
      <input id="search" type="text" v-model="searchQuery" @input="searchPerson" ref="searchInput" class="input"
        :placeholder="`${$t('common.person_id')}, ${$t('common.name')}...`" autocomplete="off" />
      <ul v-if="searchResults.length > 0" class="mt-4 border border-gray-300 rounded-md divide-y divide-gray-200">
        <li v-for="result in searchResults" :key="result.id" @click="selectPerson(result)"
          class="px-4 py-2 cursor-pointer hover:bg-gray-100">
          {{ result.name }} {{ result.surname }} ({{ result.token }})
        </li>
      </ul>
      <ul v-else-if="!found" class="mt-4 border border-gray-300 rounded-md divide-y divide-gray-200">
        <li class="px-4 py-2 cursor-pointer hover:bg-gray-100">
          {{ t('common.no_search_results') }} {{ searchQuery }}
        </li>
      </ul>
    </div>

    <div v-if="isExistingApplicant === false">
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-2">
          <input type="checkbox" v-model="isJuridic" /> {{ t('contract_block.is_juridic') }}
        </label>
      </div>
      <div class="mb-4">
        <label for="name" class="block text-sm font-medium text-gray-700 mb-2">{{ isJuridic ? t('common.name_social') : t('common.name')
          }}</label>
        <input id="name" type="text" v-model="name"
          class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
      </div>
      <div v-if="!isJuridic" class="mb-4">
        <label for="surname" class="block text-sm font-medium text-gray-700 mb-2">{{ t('common.surname') }}</label>
        <input id="surname" type="text" v-model="surname"
          class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
      </div>
      <div class="mb-4">
        <label for="token" class="block text-sm font-medium text-gray-700 mb-2">
          {{ isJuridic ? t('service_block.vat') : t('common.person_id') }}</label>
        <input id="token" type="text" v-model="token"
          class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
      </div>
      <button @click="createPerson" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">{{ t('common.new_requester') }}</button>
    </div>
  </div>
</template>
