<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import { formatMoney } from '~/utils/money';
import Date from '~/components/atoms/Date.vue';
import ColorBadge from '~/components/atoms/ColorBadge.vue';
import PersonRegion from '~/components/organisms/PersonRegion.vue';
import InvoiceRegion from '~/components/organisms/InvoiceRegion.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import debounce from 'lodash.debounce';

const props = defineProps({
  persons: {
    type: Array,
    default: () => []
  },
  excludedPersons: {
    type: Array,
    default: () => []
  },
  fixed_data: {
    type: Object,
    default: () => { }
  },
  isRegion: {
    type: Boolean,
    default: false
  },
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['close', 'show-detail', 'change-excluded']);
const { $PersonApiService } = useNuxtApp();

const loading = ref(false);
const searchQuery = ref('');
const debouncedSearchQuery = ref('');
const searchInput = ref(null);
const localPersons = ref([]);
const excludedPersons = ref(props.excludedPersons || []);
const showJuridic = ref(false);
const showVulnerable = ref(false);
const showExcluded = ref(false);
const showWithoutPhone = ref(false);
const showWithoutEmail = ref(false);
const showWithoutAddress = ref(false);
const showElectronicInvoice = ref(false);

const loadingPersonId = ref(null);

// Pagination for better performance
const currentPage = ref(1);
const itemsPerPage = ref(100);
const maxVisiblePages = ref(5);
const loadingPersons = ref(true);
const searchingPersons = ref(false);

// localPersons era una còpia local que només es llegia dins onMounted. Amb el salt
// directe al pas 2 (notificació de tall) aquest component munta abans que la tasca
// de Celery acabi, de manera que quedava congelada amb la llista buida: es veia "No
// s'ha trobat resultats" i el spinner de loadingPersons (que només baixa
// fetchPersons) encara girava. Es manté sincronitzat amb el prop perreactivament.
watch(() => props.persons, (newPersons) => {
  localPersons.value = newPersons || [];
  currentPage.value = 1;
}, { immediate: true });

// Mateixa còpia local, mateix problema: el filtre d'exclosos es quedava desfasat
// si el pare canviava la llista.
watch(() => props.excludedPersons, (newExcluded) => {
  excludedPersons.value = newExcluded || [];
}, { immediate: true });

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

// Debounce search query updates
const updateDebouncedSearch = debounce((value) => {
  debouncedSearchQuery.value = value;
  currentPage.value = 1; // Reset to first page on search
}, 300);

watch(searchQuery, (newValue) => {
  updateDebouncedSearch(newValue);
});


// Funció per mostrar detalls
const showDetail = (component, id) => {
  closeAllRegions();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
  emit('show-detail', true);
}

// Reset pagination when filters change
watch([showExcluded, showJuridic, showVulnerable, showWithoutPhone, showWithoutEmail, showWithoutAddress, showElectronicInvoice], () => {
  currentPage.value = 1;
});

const totalExcluded = computed(() => {
  return localPersons.value.filter(person => person.exclude).length;
});

// Search result: IDs that match the search query
const searchedPersonIds = ref(null);

// Search all persons when search query changes
const searchAllPersons = async () => {
  if (!debouncedSearchQuery.value || debouncedSearchQuery.value.trim() === '') {
    searchedPersonIds.value = null;
    searchingPersons.value = false;
    return;
  }

  searchingPersons.value = true;
  try {
    // Get all person IDs from localPersons to search within
    const allPersonData = (localPersons.value || []).map(person => ({
      id: person.id,
      contracts: (person.contracts || []).map(c => c.id)
    }));

    // If no persons to search, return empty
    if (allPersonData.length === 0) {
      searchedPersonIds.value = [];
      return;
    }

    // Search ALL persons at once with the search query
    const get_data = {
      person_data: allPersonData,
      show_vulnerable: showVulnerable.value,
      show_juridic: showJuridic.value,
      search_query: debouncedSearchQuery.value,
    }

    const response = await $PersonApiService.getCommunicationDetail(get_data);
    // Store only the matching IDs
    searchedPersonIds.value = (response.persons || []).map(person => person.id);
  } catch (error) {
    toast.error(t('common.error_load'));
    console.error(error);
    searchedPersonIds.value = [];
  } finally {
    searchingPersons.value = false;
  }
}

// Watch search query and search all persons
watch([debouncedSearchQuery, showVulnerable, showJuridic], () => {
  searchAllPersons();
  currentPage.value = 1; // Reset to first page on search
}, { immediate: false });

// Filtrar els contractes basats en la cerca i l'estat d'exclusió
// Optimized with caching and debounced search
const filteredPersons = computed(() => {
  let persons = localPersons.value || [];

  // Apply search filter first (if search query exists)
  if (debouncedSearchQuery.value && debouncedSearchQuery.value.trim() !== '') {
    if (searchedPersonIds.value !== null) {
      // Filter to only persons that match the search
      persons = persons.filter(person => searchedPersonIds.value.includes(person.id));
    } else {
      // Search is in progress, return empty array to avoid showing stale data
      return [];
    }
  }

  // Apply filters (most selective filters first for better performance)
  if (!showExcluded.value) {
    persons = persons.filter(person => !excludedPersons.value.includes(person.id));
  }
  if (showWithoutEmail.value) {
    persons = persons.filter(person => !person.has_email);
  }
  if (showWithoutAddress.value) {
    persons = persons.filter(person => !person.has_address);
  }
  if (showElectronicInvoice.value) {
    persons = persons.filter(person => person.has_electronic_invoice);
  }

  return persons;
});

// Paginated persons for rendering
const paginatedPersons = ref([]);

const fetchPersons = async (person_data) => {
  loadingPersons.value = true;
  try {
    // Don't pass search_query here since we already filtered by search
    const get_data = {
      person_data: person_data,
      show_vulnerable: showVulnerable.value,
      show_juridic: showJuridic.value,
      search_query: '', // Search is already applied via filteredPersons
    }

    const response = await $PersonApiService.getCommunicationDetail(get_data);
    return response.persons;
  } catch (error) {
    toast.error(t('common.error_load'));
    console.error(error);
    return [];
  } finally {
    loadingPersons.value = false;
  }
}

// Watch for changes and update paginated persons
watch([currentPage, itemsPerPage, filteredPersons, showVulnerable, showJuridic], async () => {
  // Don't trigger if search is in progress
  if (searchingPersons.value || (debouncedSearchQuery.value && debouncedSearchQuery.value.trim() !== '' && searchedPersonIds.value === null)) {
    return;
  }

  const start = (currentPage.value - 1) * itemsPerPage.value;
  const end = start + itemsPerPage.value;
  const person_ids = filteredPersons.value.slice(start, end).map(person => ({
    id: person.id,
    contracts: (person.contracts || []).map(c => c.id)
  }));

  // Only fetch if we have persons to fetch
  if (person_ids.length > 0) {
    const persons = await fetchPersons(person_ids);
    paginatedPersons.value = persons || [];
  } else {
    paginatedPersons.value = [];
  }
}, { immediate: true });

// Total pages
const totalPages = computed(() => {
  return Math.ceil(filteredPersons.value.length / itemsPerPage.value);
});

// Visible page numbers for pagination
const visiblePages = computed(() => {
  const pages = [];
  const halfVisible = Math.floor(maxVisiblePages.value / 2);
  let startPage = Math.max(1, currentPage.value - halfVisible);
  let endPage = Math.min(totalPages.value, startPage + maxVisiblePages.value - 1);

  if (endPage - startPage < maxVisiblePages.value - 1) {
    startPage = Math.max(1, endPage - maxVisiblePages.value + 1);
  }

  for (let i = startPage; i <= endPage; i++) {
    pages.push(i);
  }

  return pages;
});

// Pagination methods
const goToPage = (page) => {
  if (page >= 1 && page <= totalPages.value) {
    currentPage.value = page;
  }
};

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++;
  }
};

const prevPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--;
  }
};

// Excloure un contracte i els seus pagaments
const excludePerson = async (person) => {
  if (!confirm(t('confirmation_text_block.confirm_exclude_recipient'))) return;

  loadingPersonId.value = person.id;
  try {
    if (excludedPersons.value.includes(person.id)) {
      excludedPersons.value = excludedPersons.value.filter(id => id !== person.id);
    } else {
      excludedPersons.value.push(person.id);
    }
    emit('change-excluded', excludedPersons.value);
  } catch (error) {
    toast.error(t('common.error_save'));
    console.error(error);
  } finally {
    loadingPersonId.value = null;
  }
};

const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null
  regionDetailId.value = null
  emit('show-detail', false);
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
}

onMounted(async () => {
  searchInput.value?.focus();
});
</script>

<template>
  <div class="region__content pr-1">

    <div class="h-full flex flex-col transition-all duration-500 ease" :class="{ 'mr-[50%]': showRegion && !isSubRegionOpen, 'mr-[95%]': showRegion && isSubRegionOpen }">
      <div class="flex justify-between items-center mb-2">
        <h3 class="text-lg font-semibold">{{ $t('customer_service_block.recipients_list') }}</h3>
        <div class="flex items-center gap-2">
          <label class="text-sm text-gray-600">{{ $t('common.items_per_page') }}:</label>
          <select v-model.number="itemsPerPage" @change="currentPage = 1"
            class="text-sm border border-gray-300 rounded px-2 py-1">
            <option :value="50">50</option>
            <option :value="100">100</option>
            <option :value="250">250</option>
            <option :value="500">500</option>
          </select>
        </div>
      </div>
      <span class="text-sm text-gray-500 mb-4">
        {{ $t('common.total') }}: {{ filteredPersons.length }}
        <span v-if="totalExcluded > 0">({{ totalExcluded }} {{ $t('billing_block.excluded_multiple') }})</span>
      </span>

      <div class="mb-4 space-y-4">
        <div class="relative">
          <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Icon name="fa6-solid:magnifying-glass" class="text-gray-400" />
          </div>
          <input ref="searchInput" v-model="searchQuery" type="text"
            :placeholder="`${$t('dashboard.search')} ${$t('common.name')}, ${$t('common.identificator')} `"
            class="pl-10 pr-4 py-2 w-full border border-gray-300 rounded-md focus:ring-primary-500 focus:border-primary-500" />
        </div>

        <div class="flex items-center gap-5">
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="showExcluded"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('billing_block.excluded_multiple')
              }}</span>
          </label>
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="showJuridic"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('common.juridics') }}</span>
          </label>
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="showVulnerable"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('contract_block.vulnerables')
              }}</span>
          </label>
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="showWithoutPhone"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('common.no_tlf') }}</span>
          </label>
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="showWithoutEmail"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('common.no_email') }}</span>
          </label>
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="showWithoutAddress"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('address_block.no_address') }}</span>
          </label>
          <label class="inline-flex items-center">
            <input type="checkbox" v-model="showElectronicInvoice"
              class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500" />
            <span class="ml-2 text-sm text-gray-700">{{ $t('common.show') }} {{ $t('common.electronic_invoice')
              }}</span>
          </label>
        </div>
      </div>

      <!-- afegim comptadors -->
      <!-- <div class="flex gap-3 items-center mb-4" v-if="!loading">
        <div>
          {{ $t('Destinataris') }}: {{ localPersons.count }}
        </div>
      </div> -->
      <div class="grid grid-cols-[80px,60px,20px,150px,150px,500px] px-2 gap-2 w-full font-semibold">
        <span class="truncate col-span-4">
          {{ $t('customer_service_block.recipient') }}
        </span>
        <span class="truncate">
          {{ $t('common.email_long') }}
        </span>
        <span class="truncate">
          {{ $t('address_block.address') }}
        </span>

      </div>

      <div class="flex-1 overflow-y-auto">
        <div v-if="loading && !localPersons.results?.length" class="flex justify-center items-center h-full">
          <AppLoading :text="$t('common.loading')" :size="40" />
        </div>
        <div v-else>
          <div class="divide-y divide-gray-200 h-[55vh] overflow-auto">
            <div v-if="filteredPersons.length === 0">
              <div class="footering text-slate-500 p-2">
                {{ t('common.no_data_found') }}
              </div>
            </div>
            <div v-if="loadingPersons || searchingPersons" class="mt-5">
              <AppLoading :text="searchingPersons ? $t('dashboard.search') : $t('common.loading')" :size="40" />
            </div>
            <div v-else>

              <div v-for="(person, index) in paginatedPersons" :key="`person-${person.id}`" class="bg-white">
                <div class="px-2 py-3 flex justify-between items-center hover:bg-gray-50 relative" :class="{
                  'bg-white': index % 2 !== 0,
                  'bg-sky-50': index % 2 === 0,
                  'bg-yellow-50': excludedPersons.includes(person.id),
                }">
                  <div v-if="loadingPersonId === person.id"
                    class="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center">
                    <AppLoading :size="24" />
                  </div>

                  <div class="flex items-center space-x-3">

                    <div>
                      <div class="grid grid-cols-[80px,60px,20px,150px,150px,500px] gap-2 w-full">
                        <button @click="showDetail('PersonRegion', person.id)"
                          class="text-sky-500 hover:text-sky-700 underline text-left"
                          :title="`${$t('common.show')} ${$t('common.details')}`">
                          {{ person.token }}
                        </button>

                        <span class="truncate flex items-center">
                          <abbr v-if="person.electronic_invoice" :title="$t('common.electronic_invoice')" 
                            class="mr-2 bg-green-500 rounded-full w-5 h-5 flex justify-center items-center">
                            <Icon name="fa6-solid:file-invoice" class="text-white m-auto w-3 h-3" />
                          </abbr>
                          <AtomsVulnerabilityCheck v-if="person.vulnerability_level > 0"
                            :vulnerability_level="person.vulnerability_level" :small="true" class="mr-1" />
                        </span>
                        <abbr v-if="person.is_juridic" :title="$t('common.juridic')" class="mr-2">
                          <Icon name="fa6-solid:building" class="text-orange-500" />
                        </abbr>
                        <abbr v-else :title="$t('common.physical')" class="mr-2">
                          <Icon name="fa6-solid:user" class="text-sky-300" />
                        </abbr>
                        <span class="truncate flex items-center gap-1">
                          {{ person.full_name }}
                        </span>
                        <span class="truncate">
                          {{ person.email || t('common.no_email') }}
                        </span>
                        <span class="truncate">

                          {{ person.address || t('address_block.no_address') }}
                        </span>
                      </div>
                      <div v-if="filteredPersons.find(p => p.id === person.id)?.invoices?.length > 0"
                        class="mt-3 pl-4 border-l border-slate-200">
                        <div class="flex flex-wrap gap-2">
                          <button v-for="invoice in filteredPersons.find(p => p.id === person.id)?.invoices"
                            :key="invoice.id" @click="showDetail('InvoiceRegion', invoice.id)"
                            class="px-2 py-1 text-xs rounded-full border border-sky-200 text-sky-600 hover:bg-sky-50 truncate max-w-[120px]"
                            :title="$t('common.show') + ' ' + $t('billing_block.invoice')">
                            {{ invoice.serie_final }}
                          </button>
                        </div>
                      </div>
                      <div v-if="filteredPersons.find(p => p.id === person.id)?.readings?.length > 0"
                        class="mt-3 pl-4 border-l border-slate-200">
                        <div class="flex flex-wrap gap-2">
                          <span v-for="reading in filteredPersons.find(p => p.id === person.id)?.readings" :key="reading.id"
                            :class="{ 'bg-white': index % 2 == 0, 'bg-sky-50': index % 2 !== 0 }"
                            class="px-2 py-1 text-xs rounded border-l-2 border-sky-200 text-sky-600">
                            <!-- <span class="font-semibold"> ({{ reading.meter_code }}) </span> -->
                            {{ formatDate(reading.reading_date) }} - 
                            <span class="font-semibold"> {{ reading.reading_value }} m3 </span> &rarr; {{ t('billing_block.consumption') }}: <span class="font-semibold"> {{ reading.calculated_value }} m3 </span>
                          </span>
                        </div>
                      </div>
                      <!-- <div v-if="filteredPersons.find(p => p.id === person.id)?.contracts?.length > 0">
                        <div v-for="contract in filteredPersons.find(p => p.id === person.id)?.contracts" :key="contract.id">
                          <div class="flex items-center gap-2">
                            <span class="truncate">
                              {{ contract.token }}
                            </span>
                          </div>
                        </div>
                      </div> -->

                    </div>
                  </div>
                  <button @click="excludePerson(person)"
                    class="flex items-center gap-2 text-red-600 hover:text-red-900 text-lg w-[150px] ml-2"
                    :disabled="loadingPersonId === person.id" :title="excludedPersons.includes(person.id) ?
                      `${$t('common.includes')} ${$t('customer_service_block.recipient')}` :
                      `${$t('billing_block.exclude')} ${$t('customer_service_block.recipient')}`">
                    <Icon
                      :name="excludedPersons.includes(person.id) ? 'fa6-solid:arrow-up-from-bracket' : 'fa6-solid:ban'" />
                    <span class="text-sm w-[100px]">
                      {{ excludedPersons.includes(person.id) ?
                        `${$t('common.includes')} ${$t('customer_service_block.recipient')}` :
                        `${$t('billing_block.exclude')} ${$t('customer_service_block.recipient')}` }}</span>
                  </button>
                </div>
              </div>
            </div>

          </div>

          <!-- Pagination Controls -->
          <div v-if="totalPages > 1" class="flex justify-center items-center gap-2 mt-4 pb-2">
            <button @click="prevPage" :disabled="currentPage === 1"
              class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
              :title="$t('common.previous')">
              <Icon name="fa6-solid:chevron-left" />
            </button>

            <button v-if="visiblePages[0] > 1" @click="goToPage(1)"
              class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100">
              1
            </button>

            <span v-if="visiblePages[0] > 2" class="px-2">...</span>

            <button v-for="page in visiblePages" :key="page" @click="goToPage(page)" :class="{
              'bg-sky-500 text-white border-sky-500': page === currentPage,
              'border-gray-300 hover:bg-gray-100': page !== currentPage
            }" class="px-3 py-1 border rounded">
              {{ page }}
            </button>

            <span v-if="visiblePages[visiblePages.length - 1] < totalPages - 1" class="px-2">...</span>

            <button v-if="visiblePages[visiblePages.length - 1] < totalPages" @click="goToPage(totalPages)"
              class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100">
              {{ totalPages }}
            </button>

            <button @click="nextPage" :disabled="currentPage === totalPages"
              class="px-3 py-1 border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
              :title="$t('common.next')">
              <Icon name="fa6-solid:chevron-right" />
            </button>

            <span class="ml-4 text-sm text-gray-600">
              {{ $t('common.page') }} {{ currentPage }} {{ $t('common.of') }} {{ totalPages }}
            </span>
          </div>
        </div>
      </div>
    </div>
    <div role="region" :id="isRegion ? 'subregion' : 'right_page'"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white fixed top-0 right-0 z-10" :class="{
        'translate-x-0': showRegion,
        'translate-x-[2000px]': !showRegion,
        'w-[95%]': isSubRegionOpen,
        'w-[50%]': !isSubRegionOpen
      }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeAllRegions()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <PersonRegion v-if="showRegionDetailComponent == 'PersonRegion'" :id="parseInt(regionDetailId)"
          :isSubRegionOpen="isSubRegionOpen" :isSubRegion="isRegion" @show-subregion="handleSubRegionEvent">
        </PersonRegion>
        <InvoiceRegion v-if="showRegionDetailComponent == 'InvoiceRegion'" :id="parseInt(regionDetailId)"
          :isSubRegionOpen="isSubRegionOpen" :isSubRegion="isRegion" @show-subregion="handleSubRegionEvent">
        </InvoiceRegion>
      </div>
    </div>
  </div>
</template>