<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import H1Region from '~/components/atoms/H1Region.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import InvoiceRegion from './InvoiceRegion.vue';
import VerifactuInvoiceRegion from './VerifactuInvoiceRegion.vue';
import Pagination from '~/components/molecules/Pagination.vue';
import TableHeader from '~/components/atoms/TableHeader.vue';

const { t } = useI18n();

const props = defineProps({
  id: Number,
  isSubRegion: {
    type: Boolean,
    default: false
  },
  isSubRegionOpen: Boolean
});

const emit = defineEmits(['show-subregion', 'changed', 'close-subregion']);
const router = useRouter();
const { $VerifactuApiService } = useNuxtApp();
const pending = ref(true);
const error = ref(null);
const data = ref(null);
const SubRegion = ref(props.isSubRegionOpen);

const verifactu_notifications = ref([]);
const pendingNotifications = ref(false);
const sortBy = ref(null);
const sortDesc = ref(false);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

// Verifactu statuses colors:
const batchStatusesColors = {
  'Correcto': 'green',
  'Incorrecto': 'red',
  'ParcialmenteCorrecto': 'yellow',
  'Error': 'red'
}
const invoiceStatusesColors = {
  'Correcto': 'green',
  'Incorrecto': 'red',
  'AceptadoConErrores': 'yellow'
}

const getData = async () => {
  pending.value = true;
  error.value = null;
  try {
    const result = await $VerifactuApiService.getBatchDetail(props.id);
    data.value = result;
    await getInvoices(1);
  } catch (err) {
    error.value = err;
    console.error(err);
  } finally {
    pending.value = false;
  }
}

const getNotifications = async (page = 1, sort = null, desc = false) => {
  pendingNotifications.value = true;
  try {
    const notifications = await $VerifactuApiService.getAll('', page, sort, desc, props.id);
    verifactu_notifications.value = notifications.results;
    Object.assign(pagination.value, {
      total: notifications.count,
      totalPages: Math.ceil(notifications.count / pagination.value.perPage),
      previous: notifications.previous,
      next: notifications.next,
      page: page
    });
  } catch (err) {
    console.error(err);
  } finally {
    pendingNotifications.value = false;
  }
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getNotifications(newPage, sortBy.value, sortDesc.value);
}

const handleSort = (key) => {
  if (sortBy.value === key) {
    sortDesc.value = !sortDesc.value;
  } else {
    sortBy.value = key;
    sortDesc.value = false;
  }
  pagination.value.page = 1;
  getNotifications(1, sortBy.value, sortDesc.value);
}

watch(() => props.id, () => {
  if (props.id) {
    getData();
    closeSubRegion();
  }
});

watch(() => props.isSubRegionOpen, (newValue) => {
  SubRegion.value = newValue;
});

const closeSubRegion = function () {
  SubRegion.value = false;
  showRegionDetailComponent.value = null;
  emit('show-subregion', false);
}

const showSubRegion = function () {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const showDetail = function (component, id) {
  showRegionDetailComponent.value = component;
  regionDetailId.value = id;
  showSubRegion();
}

onMounted(() => {
  if (props.id) {
    getData();
  }
});

</script>

<template>
  <div class="region__content">
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="error">
      <p>Error: {{ error.message }}</p>
      <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
      }}</button></p>
    </div>
    <div v-else-if="data" class="relative transition-all duration-500 ease" :class="{ 'mr-[48%]': SubRegion }">
      <div class="flex justify-between relative">
        <H1Region class="mb-3">{{ $t('billing_block.verifactu_comms') }}</H1Region>
      </div>

      <div class="mt-4" id="item_data" :data-rel="id">
        <div class="flex flex-col mb-4">
          <div class="grid grid-cols-2 gap-3">
            <FieldDetail :label='$t("common.identification")' :value="data.token"></FieldDetail>
            <FieldDetail :label='$t("common.date")' :value="formatDate(data.sent_at)"></FieldDetail>
            <FieldDetail :label='$t("common.status")'>
              <AtomsColorBadge :value="t(`common.verifactu_batch_status.${data.response_status}`)" :color="batchStatusesColors[data.response_status]" />
            </FieldDetail>
          </div>
        </div>

        <div v-if="pendingInvoices">
          <p>{{ $t('common.loading') }}...</p>
        </div>
        <div v-else-if="verifactu_notifications && verifactu_notifications.length > 0" class="divide-y divide-slate-300 max-h-[calc(100vh-300px)] overflow-y-auto">
          <div class="grid grid-cols-[1fr,2fr,75px,1fr] gap-3 pt-2 font-semibold sticky top-0 bg-white z-10">
            <TableHeader :label="$t('common.identification')" sortKey="token" :currentSortBy="sortBy" :sortDesc="sortDesc"
              @sort="handleSort" />
            <span class="mt-1 bg-white text-slate-500">{{$t('invoice')}}</span>
            <span class="mt-1 bg-white text-slate-500">{{ $t('common.validation') }}</span>
            <TableHeader :label="$t('common.status')" sortKey="response_status" :currentSortBy="sortBy" :sortDesc="sortDesc"
              @sort="handleSort" />
          </div>
          <div v-for="notification in verifactu_notifications" :key="notification.id" 
            class="grid grid-cols-[1fr,2fr,75px,1fr] gap-3 pt-2 items-center">
            <span>
              <button class="text-sky-500 hover:underline" @click="showDetail('VerifactuInvoiceRegion', notification.id)">
                {{ notification.token }}
              </button>
            </span>
            <span>
              <button class="text-sky-500 hover:underline" @click="showDetail('InvoiceRegion', notification.invoice_id)">
                {{ notification.invoice_token }}
              </button>
            </span>
            <span>
              <a :href="notification.verifactu_qr" target="_blank" class="cursor-pointer ml-6">
                <Icon name="material-symbols:qr-code" class="h-5" />
              </a>
            </span>
            <span>
              <AtomsColorBadge :value="t(`common.verifactu_invoice_status.${notification.response_status}`)" :color="invoiceStatusesColors[notification.response_status]" />
            </span>
          </div>
        </div>
        <div v-else class="my-3">
          <p class="text-slate-500">{{ $t('common.no_records') }}</p>
        </div>
        <div v-if="verifactu_notifications && verifactu_notifications.length > 0" class="mt-4">
          <Pagination v-if="verifactu_notifications.length > 0" :pagination="pagination" @update:page="handlePageChange" />
        </div>
      </div>
    </div>

    <div v-if="SubRegion == true && showRegionDetailComponent != null" role="region" id="subregion"
      class="h-[100vh] border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white overflow-x-hidden fixed top-0 right-0 w-[48%] z-100 overflow-y-auto"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <InvoiceRegion v-if="showRegionDetailComponent === 'InvoiceRegion'" :id="regionDetailId"
          :isSubRegion="true" @close-subregion="closeSubRegion" @changed="getData" />
        <VerifactuInvoiceRegion v-if="showRegionDetailComponent === 'VerifactuInvoiceRegion'" :id="regionDetailId"
          :isSubRegion="true" @close-subregion="closeSubRegion" @changed="getData" />
      </div>
    </div>
  </div>
</template>

