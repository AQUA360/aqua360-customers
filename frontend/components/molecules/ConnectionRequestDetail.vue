<script setup>
import { ref, watch, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();
import ButtonOutline from '~/components/atoms/ButtonOutline.vue';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import OrderTypeDetail from '~/components/molecules/OrderTypeDetail.vue';
import { format } from 'date-fns';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import OptionsDropdown from '~/components/molecules/OptionsDropdown.vue';
import DropdownOption from '~/components/atoms/DropdownOption.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';
import { openAuthenticatedFileUrl } from '~/utils/open-authenticated-file';

const props = defineProps({
  id: Number, // ID de l'element
  reload: {
    type: Boolean,
    default: false
  },
  isRegion: {
    type: Boolean,
    default: false
  },
  canChange: {
    type: Boolean,
    default: true
  }
});

const router = useRouter();
const { $InvoiceApiService, $ConnectionRequestApiService, $ConfiglistApiService, $ConfigProjectApiService, $OrderApiService, $DocumentManagerApiService } = useNuxtApp();

const loadingInvoice = ref(null)
const pending = ref(false);
const error = ref(null);
const data = ref(null);

const order = ref(null);
const orderStatuses = ref([]);
const orderTypes = ref([]);
const orderTypeInstConn = ref(null);
const installConnToken = ref('install_connection');

const invoices = ref([])
const invoice = ref(null)

const { fetchFinalInvoiceTokens, isInvoice, findFinalInvoice } = useFinalInvoiceTokens();

const connectionStatuses = ref([]);

const emits = defineEmits(['clickChangeStatus', 'show-detail']);

const fetchConnectionStatuses = async () => {
  try {
    const data = await $ConfiglistApiService.getAll('service/connection-request-status');
    connectionStatuses.value = data.results;
  } catch (error) {
    console.error('Error fetching connection statuses:', error);
  }
};

const getData = async (load = true) => {
  if (load) pending.value = true;
  error.value = null;
  try {
    const result = await $ConnectionRequestApiService.getDetail(props.id);
    data.value = result;

    const order_types = await $ConfiglistApiService.getAll('order/order-type');
    orderTypes.value = order_types.results;

    const order_type_token = await $ConfigProjectApiService.get('order_type_install_connection_token');
    if (order_type_token) installConnToken.value = order_type_token;
    orderTypeInstConn.value = order_types.results.find(item => item.token == installConnToken.value);
    if (!orderTypeInstConn.value) {
      // Fallback: try to find by name if token fails
      orderTypeInstConn.value = order_types.results.find(item => {
        const n = (item.name || '').toLowerCase();
        return n.includes('instal·lació') && n.includes('escomesa');
      });
    }

    const order_statuses = await $ConfiglistApiService.getAll('order/order-status');
    orderStatuses.value = order_statuses.results;
    getOrder();
    getInvoice();
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const downloadInvoice = async (invoice) => {
  loadingInvoice.value = invoice.id;
  try {
    // if (!invoice.invoice_file) {
      $InvoiceApiService.getTemporaryPDF(invoice.id).then(async (data) => {
        await openAuthenticatedFileUrl(data.url);
        loadingInvoice.value = null;
      }).catch((err) => {
        error.value = err;
        loadingInvoice.value = null;
      });
    // } else {
      // const file = await $DocumentManagerApiService.viewDocument(invoice.invoice_file);
  
      // const pdfBlob = new Blob([file], { type: 'application/pdf' });
      // const blob_file_url = URL.createObjectURL(pdfBlob);
      // const newWindow = window.open(blob_file_url, '_blank');
      // const downloadLink = document.createElement('a');
      // downloadLink.href = blob_file_url;
      // downloadLink.download = `${data.value.token}.pdf`;
      // downloadLink.click();

      // if (newWindow) {
      //   setTimeout(() => {
      //     window.URL.revokeObjectURL(blob_file_url);
      //   }, 250);
      // }

    // }
  } catch (error) {
    console.log(error)
  } finally {
    loadingInvoice.value = null;
  }

}

const showDetail = (component, id) => {
  emits('show-detail', component, id);
}

const getInvoice = async () => {
  try {
    const invoice_response = await $InvoiceApiService.getConnectionRequestInvoice(props.id);
    let invoice_statuses = { results: [] };
    try {
      invoice_statuses = await $ConfiglistApiService.getAll('billing/invoice-status');
    } catch (e) {
      console.error('Error fetching invoice statuses:', e);
    }
    invoices.value = (invoice_response.results || []).map(inv => {
      const statusObj = invoice_statuses.results?.find(s => String(s.id) === String(inv.status));
      const statusToken = statusObj?.token || inv.status_token || inv.status?.token || inv.status_final || (typeof inv.status === 'string' ? inv.status : null);
      return {
        ...inv,
        type_token: inv.type_token || inv.type?.token || inv.type_final || (typeof inv.type === 'string' ? inv.type : null),
        status_token: statusToken,
        status_name: inv.status_name || statusObj?.name || null,
        status_color: inv.status_color || statusObj?.color || null,
      };
    });
    if (invoices.value.length > 0) {
      await fetchFinalInvoiceTokens();
      invoice.value = findFinalInvoice(invoices.value);
    } else {
      invoice.value = null;
    }
  }
  catch (err) {
    console.error(err)
  }
}

const getOrder = async () => {
  try {
    const order_response = await $OrderApiService.getFilterConnectionRequest(props.id);
    try {
      if (orderTypeInstConn.value) {
        order.value = order_response.find(item => item.type?.id == orderTypeInstConn.value.id);
      } else {
        order.value = order_response.find(item => item?.type?.token == installConnToken.value);
      }
    } catch (err) {
      console.error(err);
      order.value = null;
    }
  } catch (err) {
    error.value = err;
  } finally {
    pending.value = false;
  }
};

const generateWorkOrder = async () => {
  try {
    await createOrderInstallConnection();
    getData(false);
  } catch (err) {
    console.error(err);
    toast.error(t('common.error'));
  }
};

const createOrderInstallConnection = async () => {
  if (!orderTypeInstConn.value) {
    toast.error(t('warning_block.warning_order_type_not_found') + ': ' + installConnToken.value);
    return;
  }

  const defaultOrderStatus = orderStatuses.value.find(s => s.is_default == true);
  const statusId = defaultOrderStatus?.id || orderStatuses.value[0]?.id;

  if (!statusId) {
    toast.error(t('warning_block.warning_order_status_not_found'));
    return;
  }

  const description = `${t("address_block.location")}: ${data.value.address_complete || ''}\n` +
    `${t("connection")}:\n` +
    `- ${t("common.type")}: ${data.value.type?.name || ''}\n` +
    `- ${t("common.usage_type")}: ${data.value.use_type?.name || ''}\n` +
    `- ${t("service_block.material")}: ${data.value.material?.name || ''}\n` +
    `- ${t("service_block.diameter")}: ${data.value.diameter?.name || ''}\n` +
    `- ${t("service_block.valve_type")}: ${data.value.valve_type?.name || ''}\n` +
    `- ${t("service_block.installation_type")}: ${data.value.installation_type?.name || ''}`;

  const order_data = {
    token: format(new Date(), 'yyyyMMddHHmmss'),
    connection_request: props.id,
    type: orderTypeInstConn.value.id,
    status: statusId,
    requested_at: format(new Date(), 'yyyy-MM-dd HH:mm:ss'),
    latitude: data.value.latitude,
    longitude: data.value.longitude,
    description: description
  }

  const order_saved = await $OrderApiService.save(order_data);
  return order_saved;
}

const clickDeleteOrder = async (id) => {
  if (id) {
    await $OrderApiService.deleteItem(id);
    getData(false);
  }
}

const showInvoice = () => {
  const url = new URL('/billing/invoice/view/' + invoice.value.id, window.location.origin);
  window.open(url.toString(), '_blank');
}

watch(() => props.reload, () => {
  getData(false);
});

onMounted(() => {
  fetchConnectionStatuses();
  getData();
});

watch(() => props.id, () => {
  getData();
});

// Watch key to trigger data reload
watch(() => props.id, () => {
  getData();
});



</script>

<template>
  <div v-if="pending">
    <p>{{ $t('common.loading') }}...</p>
  </div>
  <div v-else-if="error">
    <p>Error: {{ error.message }}</p>
    <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
    }}</button></p>
  </div>
  <div v-else>
    <div v-if="data" id="item_data" :data-rel=id>

      <fieldset id="solicitant__box" v-if="data.person || data.company" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">
          {{ $t('common.requester') }}
        </legend>
        <template v-if="data.person">
          <p>
            {{ data.person?.name || '' }} {{ data.person?.surname || '' }}
          </p>
          <p>{{ data.person?.token || '' }}</p>
        </template>
        <template v-else-if="data.company">
          <p>{{ data.company?.name || '' }}</p>
          <p>{{ data.company?.vat || '' }}</p>
        </template>
      </fieldset>
      <fieldset id="facturacio__box" v-if="data.person || data.company" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend class="px-3 font-semibold bg-white shadow">
          <h3>{{ t("billing") }}</h3>
        </legend>
        <!-- <ButtonOutline v-if="!invoice" @click="generateInvoice">{{ $t('Generar factura') }}</ButtonOutline> -->
        <div>
          <ButtonOutline v-if="canChange" class="my-2" @click="showDetail('AddInvoiceContract', null)">
            <span v-if="invoices.length == 0">
              {{ $t('billing_block.budget_generate') }}
            </span>
            <span v-else-if="invoices.length > 0 && !invoice">
              {{ $t('common.show') }} {{ $t('common.budget_detail') }}
            </span>
            <span v-else>
              {{ $t('common.show') }} {{ $t('invoice') }}
            </span>
          </ButtonOutline>
          <div class="py-1 px-3 text-sm rounded-md border w-fit mb-5" :class="{
            'bg-green-50 text-green-600 border-green-600': invoice,
            'bg-orange-50 text-orange-600 border-orange-600': !invoice,
          }">
            <span v-if="invoices.length == 0">
              {{ $t('billing_block.budget_invoice_not_generated') }}
            </span>
            <span v-else-if="invoices.length > 0 && !invoice">
              {{ $t('billing_block.budget_invoice_generated') }}
            </span>
            <span v-else>
              {{ $t('billing_block.generated_invoice') }}
            </span>
          </div>
          <div v-for="inv in invoices" :key="inv.id" class="flex items-center gap-4 ">
            <AtomsFieldDetail :label="invoice?.id == inv.id ? t('billing_block.final_invoice') :
              isInvoice(inv) ? t('invoice') : t('common.budget_detail')" :value="inv.serie_final" />
            <AtomsColorBadge v-if="inv.status_name" :value="inv.status_name" :color="inv.status_color" />
            <div class="flex items-center gap-2">
              <button @click="showDetail('InvoiceView', inv.id)"
                class="rounded-full w-6 h-6 border border-orange-500 bg-white mb-2 hover:bg-orange-100 flex items-center"
                :title="t('common.show') + ' ' + t('invoice')">
                <Icon name="fa6-solid:eye" class="text-orange-500 m-auto" />
              </button>
              <button @click="downloadInvoice(inv)"
                class="rounded-full w-6 h-6 border border-orange-500 bg-white mb-2 hover:bg-orange-100 flex items-center"
                :title="t('common.download')">
                <Icon :name="loadingInvoice == inv.id ? 'fa6-solid:spinner' : 'fa6-solid:download'"
                  class="text-orange-500 m-auto" :class="{ 'animate-spin': loadingInvoice == inv.id }" />
              </button>
            </div>
          </div>
        </div>
      </fieldset>

      <fieldset id="ordre_treball__box" class="mb-3 border px-3 py-2 bg-sky-50">
        <legend v-if="!isRegion" class="px-3 font-semibold bg-white shadow">
          <h3>{{ t("order") }}: {{ $t('order_block.connection_installation') }}</h3>
        </legend>

        <p class="font-semibold">{{ t("address_block.location") }}:</p>
        <div class="px-3 mb-3">
          {{ data.address_complete }}<br />
          {{ data.address_postal_code?.code || "" }} - {{ data.address_city?.name || "" }}
        </div>

        <p class="font-semibold">{{ t("connection") }}:</p>
        <div class="px-3 mb-3">
          <span>#{{ data.token || "" }}</span><br />
          <span class="inline-block min-w-80">{{ t("common.type") }}: {{ data.type?.name }}</span>
          <span>{{ data.use_type?.name }}</span><br />
          <span class="inline-block min-w-80">{{ t("service_block.material") }}: {{ data.material?.name }} &#8960; {{
            data.diameter?.name }}</span>
          {{ t("service_block.valve_type") }}: <span>{{ data.valve_type?.name }}</span><br />
          <span>{{ data.installation_type?.name }}</span>
        </div>
        <div v-if="!isRegion">
          <ButtonOutline v-if="!order" @click="generateWorkOrder">
            {{ $t('common.generate') }} {{ $t('common.work_order') }}
          </ButtonOutline>
          <div v-else class="flex items-center justify-between max-w-xl bg-green-100 py-1 px-2 mb-2">
            <OrderTypeDetail :data="order.type" :order="order" @show-detail="showDetail('OrderRegion', order.id)" />
            <button @click="clickDeleteOrder(order.id)" class="text-slate-500 ml-2">
              <Icon name="fa6-solid:trash" />
            </button>
          </div>
        </div>
        <hr class="my-3" />


        <div name="canvi_estat" class="max-w-96 mb-2">
          <label>{{ t("common.status") }}:</label>
          <div class="py-2">
            <AtomsColorBadge :value="data.status?.name || data.status?.token || ''" :color="data.status?.color">
            </AtomsColorBadge>
          </div>
          <div v-if="canChange">
            <ButtonOutline @click="emits('clickChangeStatus')">{{ t("common.change") }} {{ t("common.status") }}</ButtonOutline>
          </div>
        </div>
      </fieldset>
    </div><!-- end if data -->
  </div><!-- end if pending -->
</template>
