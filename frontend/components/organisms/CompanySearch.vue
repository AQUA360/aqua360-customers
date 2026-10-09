<script setup>
import { ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import debounce from 'lodash.debounce';

const { t } = useI18n();
const { $ExploitationApiService } = useNuxtApp();
const emits = defineEmits(['saved']);

const searchQuery = ref('');
const searchInput = ref(null);
const searchResults = ref([]);
const found = ref(true);


const props = defineProps({
  title: {
    type: String,
    required: false,
    default: undefined,
  },
});

const displayTitlePlaceholder = computed(() => {
  return props.title ?? `${t('common.select')} ${t('common.requester')}`;
});


const searchCompany = debounce(async () => {
  // console.log('searchCompany', searchQuery.value)
  if (searchQuery.value) {
    const data = await $ExploitationApiService.getCompanies(searchQuery.value);
    searchResults.value = data.results;
    if (searchResults.value.length === 0) {
      found.value = false;
    }
  } else {
    searchResults.value = [];
    found.value = true;
  }

}, 100);

const selectCompany = (company) => {
  emits('saved', company);
};



onMounted(() => {
  nextTick(() => {
    if (searchInput.value) {
      searchInput.value.focus();
    }
  });
});

</script>

<template>
  <div>
    <h2 class="text-xl font-semibold mb-4">{{ t(displayTitlePlaceholder) }}</h2>

    <div>
      <label for="search" class="block text-sm font-medium text-gray-700 mb-2">
        {{ t('dashboard.search') }} {{ t('service_block.vat') }} {{ t('common.or') }} {{ t('common.name') }}
      </label>
      <input id="search" type="text" v-model="searchQuery" @input="searchCompany" ref="searchInput" class="input"
        :placeholder="`${t('service_block.vat')}/${t('common.name')}`" autocomplete="off" />
      <ul v-if="searchResults.length > 0" class="mt-4 border border-gray-300 rounded-md divide-y divide-gray-200">
        <li v-for="result in searchResults" :key="result.id" @click="selectCompany(result)"
          class="px-4 py-2 cursor-pointer hover:bg-gray-100">
          {{ result.name }} ({{ result.vat }})
        </li>
      </ul>
      <ul v-else-if="!found" class="mt-4 border border-gray-300 rounded-md divide-y divide-gray-200">
        <li class="px-4 py-2 cursor-pointer hover:bg-gray-100">
          {{ t('common.no_search_results') }} {{ searchQuery }}
        </li>
      </ul>
    </div>
  </div>
</template>
