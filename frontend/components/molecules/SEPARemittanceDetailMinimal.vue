<script setup>
import { ref, onMounted, nextTick, watch } from 'vue';
import { useRouter } from 'vue-router';
import debounce from 'lodash.debounce';
import { useI18n } from 'vue-i18n';
import H1Region from '../atoms/H1Region.vue';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  remittance_id: {
    type: Number,
    required: true
  },
  info: Object,
});

const emit = defineEmits(['remittance-updated']);

const route = useRoute();
const router = useRouter();
const {$ConfiglistApiService, $SepaRemittanceApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const items = ref([]);
const remittanceDetails = ref(null);
const searchInput = ref('');
const filter_status = ref([]);
const sortBy = ref(null);
const sortDesc = ref(false);

const sent_at = ref(new Date(Date.now()).toISOString().split('T')[0]);
const desired_send_at = ref(null);

const statuses = ref([])

const showRegion = ref(false);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    detail.value = null
    selectedItemId.value = null
    selectedItemComponent.value = null
  }
}


const getPayments = async (searchQuery = '', filters = [], page = 1, sort = null, desc = false) => {
  pending.value = true;
  error.value = null;
  try {
    const data = await $SepaRemittanceApiService.getPayments(
      props.remittance_id,
      searchQuery,
      filters,
      page,
      sort,
      desc
    );

    items.value = data.results;
    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: String(searchQuery).trim() !== ''
    });

    nextTick(() => {
      const searchElement = document.getElementById('searchInputRemittance');
      if (searchElement) {
        searchElement.focus();
      }
    });
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
}

const getFilterStatus = async () => {
  error.value = null;
  try {
    const data = await $ConfiglistApiService.getAll('billing/payment-status')
    filter_status.value = data.results;
  } catch (err) {
    error.value = err;
  }
}

// Obtenir detalls de la remesa
const getRemittanceDetails = async () => {
  try {
    const data = await $SepaRemittanceApiService.getDetail(props.remittance_id);
    remittanceDetails.value = data;
    if (data.send_at){
      desired_send_at.value = data.send_at;
      sent_at.value = data.send_at;
    }
  } catch (err) {
    console.error('Error obtenint detalls de la remesa:', err);
  }
}

const debouncedGetPayments = debounce((query, filters, sort, desc) => {
  getPayments(query, filters, pagination.value.page, sort, desc);
}, 300);

const handleSearch = () => {
  pagination.value.page = 1;
  debouncedGetPayments(searchInput.value, statuses.value, sortBy.value, sortDesc.value);
}


onMounted(() => {
  getPayments();
  getRemittanceDetails();
  getFilterStatus();
  if (route.query?.action == 'showDetail') {
    showDetail(route.query.component, route.query.id)
    router.replace({
      path: route.path
    });
  }
});

const detail = ref(null);
const selectedItemId = ref(null);
const selectedItemComponent = ref(null);
const showDetail = async (component, id) => {
  await toggleRegion(false);
  detail.value = id;
  selectedItemId.value = id;
  selectedItemComponent.value = component;
  toggleRegion(true);
}

// Watch for changes in searchInput and selectedFilters and reset pagination to 1
watch([searchInput], () => {
  pagination.value.page = 1;
  handleSearch();
});

</script>

<template>
  <div id="wrapper" class="region__content">
    <div>
      <H1Region>{{ $t('billing_block.sepa_remittance_detail') }}</H1Region>

      <!-- Loading state -->
      <div v-if="!remittanceDetails" class="my-4">
        <p>{{ $t('common.loading') }}...</p>
      </div>

      <!-- Contingut principal quan tenim dades -->
      <template v-else>
        <div class="flex gap-3 items-center mb-2">
          <span class="truncate text-slate-400 text-sm">{{ remittanceDetails.token || info?.token }}</span>
          <AtomsColorBadge :value="remittanceDetails.status_name" :color="remittanceDetails.status_color" />
          <span class="ml-auto text-xs text-slate-500 whitespace-nowrap">
            {{ $t('billing_block.payments') }}:
            <span class="font-semibold text-slate-700">{{ remittanceDetails.total_payments || 0 }}</span>
          </span>
        </div>
      </template>
    </div>
  </div><!-- end wrapper -->
</template>