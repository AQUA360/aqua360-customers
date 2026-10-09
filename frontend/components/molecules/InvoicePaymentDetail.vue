<script setup>
import { formatDate } from '~/utils/date';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
const { t } = useI18n();

const props = defineProps({
  invoice_id: {
    type: Number,
    default: null
  },
  isSubRegion: {
    type: Boolean,
    default: false
  }
});

const { $PaymentApiService, $ConfigProjectApiService } = useNuxtApp();

const data = ref([]);
const SubRegion = ref(props.isSubRegion);
const loading = ref(false);
const status_paid_token = ref(null);

const getData = async () => {
  loading.value = true
  try {
    status_paid_token.value = await $ConfigProjectApiService.get('invoice_status_paid_token');
    const response = await $PaymentApiService.getAll('', [], 1, null, false, props.invoice_id);
    data.value = []
    //sort results by payment_date
    data.value = response.results.sort((a, b) => a.payment_date - b.payment_date);
  } catch (error) {
    console.log(error)
  } finally {
    loading.value = false
  }
}

const generatePaymentProof = function (id, payment_date) {
  emit('generate-payment-proof', id, payment_date)
}

const emit = defineEmits(['show-detail', 'generate-payment-proof']);

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

getData();

</script>

<template>
  <div v-if="loading">
    <div class="flex justify-center items-center mt-5">
      <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>
  </div>
  <div v-else>
    <div v-if="data.length == 0" class="">
      <span class="footering text-slate-500 p-2">
        {{ t('common.no_data_found') }}
      </span>
    </div>
    <div v-else>
      <table class="min-w-full text-sm text-slate-800 mt-2">
        <thead>
          <tr class="bg-gray-100 border-b text-left">
            <th class="p-2 truncate">{{ t('billing_block.payment_date') }}</th>
            <th class="p-2 truncate">{{ t('common.identification') }}</th>
            <th class="p-2 truncate">{{ t('common.due_date') }}</th>
            <th class="p-2 truncate">{{ t('common.status') }}</th>
            <th class="p-1 w-[50px]"></th>
            <th class="p-1 w-[150px]"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(element, index) in data" :key="element.id" class="border-b">
            <td class="p-2">{{ element.payment_date ? formatDate(element.payment_date) : '-' }}</td>
            <td class="p-2">
              <div class="flex items-center gap-2">
                <button class="text-start text-sky-500 underline"
                  @click="showDetail('PaymentRegion', element.id)">
                  {{ element.token }}
                </button>
                <!-- <div v-else class="flex items-center ">
                  <span class="text-slate-500 text-sm">
                    {{ element.token }}
                  </span>
                </div> -->
                <span v-if="element.is_duplicate" class="text-slate-500 text-sm">
                  ({{ $t('common.duplicate') }})
                </span>
              </div>
            </td>
            <td class="p-2">{{ element.due_date ? formatDate(element.due_date) : '-' }}</td>
            <td class="p-2">
              <AtomsColorBadge :value="element.status?.name" :color="element.status?.color"></AtomsColorBadge>
            </td>
            <td class="p-1 w-[50px]">
              <abbr v-if="element.status?.token == status_paid_token" :title="t('billing_block.payment_proof')">
                <button 
                  @click="generatePaymentProof(element.id, element.payment_date)"
                  class="h-6 w-6 rounded-full bg-green-500 hover:bg-green-600 text-white transition-colors duration-200 shadow-sm hover:shadow-md flex items-center justify-center">
                  <Icon name="fa6-solid:receipt" class="text-sm"></Icon>
                </button>
              </abbr>
            </td>
            <td class="p-1 w-[150px]">
              <AtomsColorBadge v-if="element.is_excluded" :value="t('billing_block.excluded')" :color="'purple'">
              </AtomsColorBadge>
            </td>

          </tr>
        </tbody>
      </table>
    </div>
  </div>

</template>