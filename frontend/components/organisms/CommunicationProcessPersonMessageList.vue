<script setup>
import { ref, computed, onMounted, watch, shallowRef } from 'vue';
import { format } from 'date-fns';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import { useNuxtApp } from '#app';
import { formatMoney } from '~/utils/money';
import ColorBadge from '~/components/atoms/ColorBadge.vue';
import PersonRegion from '~/components/organisms/PersonRegion.vue';
import InvoiceRegion from '~/components/organisms/InvoiceRegion.vue';
import debounce from 'lodash.debounce';
import { formatMessageTextForPreview } from '~/utils/messages';

const props = defineProps({
  persons: {
    type: Array,
    default: () => []
  },
  excludedPersons: {
    type: Array,
    default: () => []
  },
  final_data: {
    type: Object,
    default: () => { }
  },
  fixed_data: {
    type: Object,
    default: () => { }
  },
  isRegion: {
    type: Boolean,
    default: false
  }
});

const { t } = useI18n();
const toast = useToast();
const emit = defineEmits(['close', 'show-detail', 'change', 'change-excluded']);
const { $PersonApiService } = useNuxtApp();

const loading = ref(false);
const searchQuery = ref('');
const debouncedSearchQuery = ref('');
const searchInput = ref(null);
const localPersons = shallowRef([]); // Use shallowRef for better performance
const excludedPersons = ref(props.excludedPersons || []);
const expandedContracts = ref(new Set());
const showJuridic = ref(false);
const showVulnerable = ref(false);
const showExcluded = ref(false);
const showWithoutPhone = ref(false);
const showWithoutEmail = ref(false);
const showWithoutAddress = ref(false);
const showElectronicInvoice = ref(false);

const messageBody = ref('');
const messageSubject = ref('');

const loadingPersonId = ref(null);

// Pagination for better performance
const currentPage = ref(1);
const itemsPerPage = ref(100);
const maxVisiblePages = ref(5);
const loadingPersons = ref(true);

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

const personsWithoutEmail = computed(() => {
  return localPersons.value.filter(person => (!props.excludedPersons.includes(person.id) && !person?.has_email));
});
const personsWithoutAddress = computed(() => {
  return localPersons.value.filter(person => (!props.excludedPersons.includes(person.id) && !person?.has_address));
});
const totalExcluded = computed(() => {
  return localPersons.value.filter(person => props.excludedPersons.includes(person.id)).length;
});

// Funcions per gestionar els contractes expandits
const togglePerson = (person) => {
  if (expandedContracts.value.has(person)) {
    expandedContracts.value.delete(person)
  } else {
    expandedContracts.value.add(person)
  }
}

const isPersonExpanded = (person) => {

  return expandedContracts.value.has(person)
}

// Funció per mostrar detalls
const showDetail = (component, id) => {
  closeAllRegions();
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showRegion.value = true;
  emit('show-detail', true);
}

// Carregar els contractes associats a la reclamació
const loadPersons = async () => {
  loading.value = true;
  try {
    console.log("props.persons");
    console.log(props.persons);
    // Use Object.freeze to prevent deep reactivity on large arrays
    // This significantly improves performance with thousands of items
    localPersons.value = props.persons.map(person => {
      // Keep person objects reactive for updates, but freeze nested arrays
      if (person.addresses) person.addresses = Object.freeze(person.addresses);
      if (person.phones) person.phones = Object.freeze(person.phones);
      if (person.emails) person.emails = Object.freeze(person.emails);
      if (person.contracts) person.contracts = Object.freeze(person.contracts);
      if (person.invoices) person.invoices = Object.freeze(person.invoices);
      if (person.readings) person.readings = Object.freeze(person.readings);
      return person;
    });
    console.log("localPersons");
    console.log(localPersons.value);
  } catch (error) {
    toast.error(t('common.error_load'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// Reset pagination when filters change
watch([showExcluded, showJuridic, showVulnerable, showWithoutPhone, showWithoutEmail, showWithoutAddress, showElectronicInvoice], () => {
  currentPage.value = 1;
});

// Filtrar els contractes basats en la cerca i l'estat d'exclusió
// Optimized with caching and debounced search
const filteredPersons = computed(() => {
  let persons = localPersons.value || [];

  // Apply filters first (most selective filters first for better performance)
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
    const get_data = {
      person_data: person_data,
      show_vulnerable: showVulnerable.value,
      show_juridic: showJuridic.value,
      search_query: debouncedSearchQuery.value,
    }

    const response = await $PersonApiService.getCommunicationDetail(get_data);
    console.log("response");
    console.log(response);
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
watch([currentPage, itemsPerPage, filteredPersons, showVulnerable, showJuridic, debouncedSearchQuery], async () => {
  const start = (currentPage.value - 1) * itemsPerPage.value;
  const end = start + itemsPerPage.value;
  const person_ids = filteredPersons.value.slice(start, end).map(person => ({
    id: person.id,
    contracts: (person.contracts || []).map(c => c.id),
    invoices: (person.invoices || []).map(i => i.id),
    readings: (person.readings || []).map(r => r.id)
  }));
  const persons = await fetchPersons(person_ids);
  paginatedPersons.value = persons || [];
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
    //localPersons.value = localPersons.value.filter(c => c.id !== person.id);
    if (excludedPersons.value.includes(person.id)) {
      excludedPersons.value = excludedPersons.value.filter(id => id !== person.id);
    } else {
      excludedPersons.value.push(person.id);
    }
    emit('change-excluded', excludedPersons.value);

  } catch (error) {
    toast.error(t('common.error'));
    console.error(error);
  } finally {
    loadingPersonId.value = null;
  }
};

const personalizeText = (text, person) => {
  let personalizedText = text;
  personalizedText = personalizedText.replaceAll('%person.name', person.full_name);
  personalizedText = personalizedText.replaceAll('%person.token', person.token);
  personalizedText = personalizedText.replaceAll('%person.address_complete', person.address);

  personalizedText = personalizedText.replaceAll('%company.name', props.final_data?.company?.company?.name);
  personalizedText = personalizedText.replaceAll('%company.phone', props.final_data?.company?.company?.phone);
  personalizedText = personalizedText.replaceAll('%company.email', props.final_data?.company?.company?.email);
  personalizedText = personalizedText.replaceAll('%company.address_complete', props.final_data?.company?.company?.address_complete);


  personalizedText = personalizedText.replaceAll('%contract.token', filteredPersons?.value.find(p => p.id === person.id)?.contracts.map(contract => contract.token).join(', '));

  let today = format(new Date(), 'yyyy-MM-dd').toString();
  personalizedText = personalizedText.replaceAll('%date.today', today);
  personalizedText = personalizedText.replaceAll('%communication.due_date', formatDate(props.final_data?.due_date));

  personalizedText = personalizedText.replaceAll('%contract.persons', props.final_data?.company?.company?.persons?.length);
  personalizedText = personalizedText.replaceAll('%contract.supply_address', filteredPersons?.value.find(p => p.id === person.id)?.contracts.map(contract => contract.supply_address).join('\n'));

  personalizedText = personalizedText.replaceAll('%invoice.issue_date', formatDate(person?.invoices[0]?.issue_date));
  personalizedText = personalizedText.replaceAll('%invoice.serie_final', person?.invoices.map(invoice => invoice.serie_final).join(', '));
  personalizedText = personalizedText.replaceAll('%invoice.consumption', person?.invoices.reduce((sum, invoice) => sum + (Number(invoice.consumption) || 0), 0).toString() + 'm3');
  personalizedText = personalizedText.replaceAll('%invoice.total', formatMoneyWithCurrency(person?.invoices.reduce((sum, invoice) => sum + (Number(invoice.total) || 0), 0).toString()));

  personalizedText = personalizedText.replaceAll('%reading.data', `${person?.readings?.map(
      reading => `${t('meter')} ${reading.meter_code} - ${t('reading')} ${parseInt(reading.reading_value)} ${t('billing_block.reading_date').toLowerCase()}: ${formatDate(reading.reading_date)} . ${t('billing_block.consumption')}: ${parseInt(reading.calculated_value)} m3 ${reading.leak_value ? `- ${t('billing_block.leak')}: ${parseInt(reading.leak_value)} m3` : ''}`
  ).join('\n')}`);
  personalizedText = personalizedText.replaceAll('%reading.meter_code', person?.readings[0]?.meter_code);
  personalizedText = personalizedText.replaceAll('%reading.reading_value', person?.readings[0]?.reading_value);
  personalizedText = personalizedText.replaceAll('%reading.reading_date', person?.readings[0]?.reading_date ? formatDate(person?.readings[0]?.reading_date) : '');
  personalizedText = personalizedText.replaceAll('%reading.calculated_value', person?.readings[0]?.calculated_value ? parseInt(person?.readings[0]?.calculated_value) : 0);
  personalizedText = personalizedText.replaceAll('%reading.leak_value', person?.readings[0]?.leak_value ? parseInt(person?.readings[0]?.leak_value) : 0);
  personalizedText = personalizedText.replaceAll('%reading.previous_reading_value', person?.readings[0]?.previous_reading_value ? parseInt(person?.readings[0]?.previous_reading_value) : 0);
  personalizedText = personalizedText.replaceAll('%reading.previous_reading_date', person?.readings[0]?.previous_reading_date ? formatDate(person?.readings[0]?.previous_reading_date) : '');

  return personalizedText;
}

const getPersonalizedTextWithHighlighting = (text, person) => {
  return formatMessageTextForPreview(personalizeText(text ?? '', person));
}

const getOriginalTextWithHighlighting = (text) => {
  return formatMessageTextForPreview(text ?? '');
}

const getPersonalizedSubject = (person, message) => {
  return getPersonalizedTextWithHighlighting(message.msg_data.subject, person);
}

const getPersonalizedBody = (person, message) => {
  return getPersonalizedTextWithHighlighting(message.msg_data.body, person);
}

const getTextareaHeight = (text) => {
  if (!text) return 60;

  const lines = text.split('\n').length;
  const estimatedCharsPerLine = 80;
  const charsPerLine = Math.min(estimatedCharsPerLine, text.length);
  const estimatedLines = Math.ceil(text.length / charsPerLine);
  const totalLines = Math.max(lines, estimatedLines);

  const lineHeight = 20;
  const padding = 10;
  const minHeight = 60;

  return Math.max(minHeight, (totalLines * lineHeight));
}

const closeAllRegions = () => {
  showRegion.value = false;
  showRegionDetailComponent.value = null
  regionDetailId.value = null
  emit('show-detail', false);
};

const handleSubRegionEvent = (event) => {
  isSubRegionOpen.value = event;
};

onMounted(async () => {
  console.log("props.final_data");
  console.log(props.final_data);
  messageBody.value = props.final_data?.body;
  messageSubject.value = props.final_data?.subject;
  await loadPersons();
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
      <div class="grid grid-cols-3 gap-2 w-[75%] items-center mb-2">
        <span class="pl-2 border-l-2 border-slate-300 text-sm text-gray-500 mb-4">
          {{ $t('common.total') }}: {{ filteredPersons.length }}
        </span>

        <span class="pl-2 border-l-2 border-slate-300 text-sm text-gray-500 mb-4">
          {{ $t('billing_block.excluded_multiple') }}: {{ excludedPersons.length }}
        </span>

        <span></span>

        <span class="pl-2 border-l-2 border-slate-300 text-sm text-gray-500 mb-4">
          {{ $t('common.no_email_long') }}:
          <span class="text-red-500 font-semibold">
            {{ personsWithoutEmail.length }}
          </span>
        </span>
        <span class="pl-2 border-l-2 border-slate-300 text-sm text-gray-500 mb-4">
          {{ $t('address_block.no_address') }}:
          <span class="text-red-500 font-semibold">
            {{ personsWithoutAddress.length }}
          </span>
        </span>
      </div>

      <div class="mb-4 space-y-4">
        <div class="relative">
          <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Icon name="fa6-solid:magnifying-glass" class="text-gray-400" />
          </div>
          <input ref="searchInput" v-model="searchQuery" type="text"
            :placeholder="`${$t('dashboard.search')} ${$t('common.name')}, ${$t('common.identificator')}  ${$t('common.or')} ${$t('contract')}`"
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
      <div class="grid grid-cols-[27px,80px,60px,20px,150px,150px,500px] gap-2 w-full font-semibold">
        <span></span>
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
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl" />
        </div>
        <div v-else>
          <div class="divide-y divide-gray-200 h-[55vh] overflow-auto">
            <div v-if="filteredPersons.length === 0">
              <div class="footering text-slate-500 p-2">
                {{ t('common.no_data_found') }}
              </div>
            </div>
            <div v-if="loadingPersons" class="mt-5">
              <div class="flex justify-center items-center h-full text-slate-500 gap-2">
                <span>
                  {{ $t('common.loading') }}...
                </span>
                <Icon name="fa6-solid:spinner" class="animate-spin text-2xl" />
              </div>
            </div>
            <div v-else>

              <div v-for="(person, index) in paginatedPersons" :key="`person-${person.id}`" class="bg-white">
                <div class="px-4 py-3 flex justify-between items-center hover:bg-gray-50 relative" :class="{
                  'bg-white': index % 2 !== 0,
                  'bg-sky-50': index % 2 === 0,
                  'bg-yellow-50': excludedPersons.includes(person.id),
                }">
                  <div v-if="loadingPersonId === person.id"
                    class="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center">
                    <Icon name="fa6-solid:spinner" class="animate-spin text-xl text-sky-600" />
                  </div>

                  <div class="flex items-center space-x-3">
                    <button @click="togglePerson(person)" class="text-gray-500 hover:text-gray-700"
                      :disabled="loadingPersonId === person.id"
                      :title="`${$t('common.expand')}/${$t('common.collapse')} ${$t('customer_service_block.recipient')}`">
                      <Icon :name="isPersonExpanded(person) ? 'fa6-solid:chevron-down' : 'fa6-solid:chevron-right'" />
                    </button>
                    <div>
                      <div class="grid grid-cols-[80px,60px,20px,150px,150px,500px] gap-2 w-full">
                        <button @click="showDetail('PersonRegion', person.id)"
                          class="text-sky-500 hover:text-sky-700 underline text-left"
                          :title="`${$t('common.show')} ${$t('common.details')}`">
                          {{ person.token }}
                        </button>
                        <span class="truncate flex items-center gap-1">
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
                        <span v-if="person.contract_token" class="truncate">
                          {{ person.contract_token }}
                        </span>
                        <span v-else>
                        </span>

                      </div>

                    </div>
                  </div>
                  <button @click="excludePerson(person)"
                    class="flex items-center gap-2 text-red-600 hover:text-red-900 text-lg w-[150px]"
                    :disabled="loadingPersonId === person.id" :title="excludedPersons.includes(person.id) ?
                      `${$t('common.includes')} ${$t('customer_service_block.recipient')}` :
                      `${$t('billing_block.exclude')} ${$t('customer_service_block.recipient')}`">
                    <Icon
                      :name="excludedPersons.includes(person.id) ? 'fa6-solid:arrow-up-from-bracket' : 'fa6-solid:ban'" />
                    <span class="text-sm w-[100px]">
                      {{ excludedPersons.includes(person.id) ?
                        `${$t('common.includes')} ${$t('customer_service_block.recipient')}` :
                        `${$t('billing_block.exclude')} ${$t('customer_service_block.recipient')}` }}
                    </span>
                  </button>
                </div>
                <div v-if="isPersonExpanded(person)" class="px-4 py-2 border border-slate-300 rounded mx-2">
                  <div class="bg-white">
                    <div v-for="message in props.final_data.messages_data">
                      <div v-if="message.type.token == 'email' && person.email ||
                        message.type.token == 'letter' && person.address">
                        <label for="message" class="text-sm text-slate-500 font-semibold">
                          {{ message.type.name }}
                        </label>
                        <div>
                          <div class="border-b border-slate-300">
                            <span class="text-sm text-slate-400 italic"
                              v-html="getPersonalizedSubject(person, message)">
                            </span>
                          </div>
                          <div class="p-2 rounded border border-slate-300 bg-slate-50 w-full overflow-auto">
                            <div class="text-sm text-gray-500 w-full bg-slate-50 min-h-[60px] overflow-auto over whitespace-pre-wrap"
                              v-html="getPersonalizedTextWithHighlighting(message.msg_data.body, person)"
                              :style="{ height: getTextareaHeight(message.msg_data.body) + 'px' }" />
                          </div>
                        </div>
                      </div>

                      <div v-if="person?.invoices?.length > 0 && props?.fixed_data?.entity === 'billing'"
                        class="text-sm text-gray-500 mt-2 flex items-center gap-2">
                        <span>
                          {{ t('invoices') }}:
                        </span>
                        <button class="text-sky-400 hover:text-sky-600 hover:underline"
                          v-for="invoice in person.invoices" @click="showDetail('InvoiceRegion', invoice.id)">
                          {{ invoice.serie_final }}
                        </button>
                      </div>
                      <div v-if="person?.readings?.length > 0"
                        class="text-sm text-gray-500 mt-2 flex items-center gap-2">
                        <span>
                          {{ t('readings') }}:
                        </span>
                        <span v-for="reading in person.readings" 
                        :class="{ 'bg-white': index % 2 == 0, 'bg-sky-50': index % 2 !== 0 }"
                          class="px-2 py-1 text-xs rounded border-l-2 border-sky-200 text-sky-600">
                          {{ reading.serie_final }}
                        </span>
                      </div>
                    </div>
                  </div>
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