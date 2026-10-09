<script setup>
import { useI18n } from 'vue-i18n';
import H1Region from '../atoms/H1Region.vue';
import { formatDate } from '~/utils/date';
import { formatMoneyWithCurrency } from '~/utils/money';
import { useToast } from 'vue-toastification';

const { t } = useI18n();
const toast = useToast();

const props = defineProps({
  id: Number,
  isSubRegion: {
    type: Boolean,
    default: false
  }
});
const emit = defineEmits(['change']);

const { $PaymentApiService, $ConfigProjectApiService, $PaymentCommitmentApiService } = useNuxtApp();

const loading = ref(false)
const localData = ref(null);

const paymentPaidToken = ref(null);

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}

const getData = async () => {
  loading.value = true
  try {
    paymentPaidToken.value = await $ConfigProjectApiService.get('payment_status_paid_token');
    const result = await $PaymentApiService.getAll(
      '', [], 1,
      null, false, null,
      null, null, null,
      [], null, null,
      null, [], false,
      props.id, null
    );
    localData.value = result.results;
    console.log("localData.value")
    console.log(localData.value);
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false;
  }
}

const returnPayment = async (paymentId) => {
  if (!confirm(t('confirmation_text_block.confirm_modify'))) return
  try {
    let response = await $PaymentCommitmentApiService.returnPayment(paymentId);
    if (response) {
      toast.success(t('common.correct_save'));
      emit('change');
    }
  } catch (err) {
    console.error(err)
  }
}

onMounted(() => {
  getData()
})

</script>
<template>
  <div>
    <div class="mb-3">
      <H1Region>{{ t('common.return_action') + ' ' + t('billing_block.payment').toLowerCase() }}</H1Region>
    </div>

    <div v-if="loading" class="flex gap-3 mx-auto p-1">
      <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
      {{ $t('common.loading') }}...
    </div>
    <div v-else class="mt-4">
      <div v-if="localData && localData.length > 0" class="space-y-3">
        <div v-for="item in localData" :key="item.id"
          class="border rounded-lg transition-all duration-200"
          :class="{
            'border-sky-200 bg-gradient-to-br from-sky-50 to-sky-50/50 hover:border-sky-300': item.status?.token == paymentPaidToken,
            'border-slate-200 bg-gradient-to-br from-slate-50 to-slate-50/50 hover:border-slate-300': item.status?.token != paymentPaidToken
          }">

          <!-- Paid Status: Full Layout with Button -->
          <div v-if="item.status?.token == paymentPaidToken" class="p-4">
            <!-- Header Row: Status and Amount -->
            <div class="flex items-center justify-between mb-3">
              <div class="flex items-center gap-3">
                <AtomsColorBadge :value="item.status?.name" :color="item.status?.color" />
              </div>
              <div class="text-lg font-bold text-slate-900">
                {{ formatMoneyWithCurrency(item.amount) }}
              </div>
            </div>

            <!-- Info Grid: Dates and Payment Method -->
            <div class="grid grid-cols-3 gap-4 mb-3">
              <div class="flex flex-col">
                <span class="text-[10px] text-slate-500 uppercase tracking-wider mb-1 font-semibold">
                  {{ t('billing_block.payment_date') }}
                </span>
                <span class="text-sm text-slate-800 font-medium">
                  {{ item.payment_date ? formatDate(item.payment_date) : '-' }}
                </span>
              </div>

              <div class="flex flex-col">
                <span class="text-[10px] text-slate-500 uppercase tracking-wider mb-1 font-semibold">
                  {{ t('common.due_date') }}
                </span>
                <span class="text-sm text-slate-800 font-medium">
                  {{ item.due_date ? formatDate(item.due_date) : '-' }}
                </span>
              </div>

              <div class="flex flex-col">
                <span class="text-[10px] text-slate-500 uppercase tracking-wider mb-1 font-semibold">
                  {{ t('common.payment_method') }}
                </span>
                <span class="text-sm text-slate-800 font-medium">
                  {{ item.payment_type }}
                </span>
              </div>
            </div>

            <!-- Action Row: Return Button -->
            <div class="flex items-center justify-end pt-2 border-t border-slate-200/60">
              <button 
                @click="returnPayment(item.id)"
                class="button-primary min-w-[110px]">
                {{ t('common.return_action') }}
              </button>
            </div>
          </div>

          <!-- Non-Paid Status: Compact Layout without Button -->
          <div v-else class="p-3">
            <div class="flex items-center gap-4">
              <AtomsColorBadge :value="item.status?.name" :color="item.status?.color" />
              
              <div class="flex-1 grid grid-cols-4 gap-4 items-center">
                <div class="text-sm text-slate-700">
                  <span class="text-slate-500 text-xs">{{ t('billing_block.payment_date') }}: </span>
                  {{ item.payment_date ? formatDate(item.payment_date) : '-' }}
                </div>
                
                <div class="text-sm text-slate-700">
                  <span class="text-slate-500 text-xs">{{ t('common.due_date') }}: </span>
                  {{ item.due_date ? formatDate(item.due_date) : '-' }}
                </div>
                
                <div class="text-sm text-slate-700">
                  <span class="text-slate-500 text-xs">{{ t('common.payment_method') }}: </span>
                  {{ item.payment_type }}
                </div>
                
                <div class="text-right font-semibold text-slate-900">
                  {{ formatMoneyWithCurrency(item.amount) }}
                </div>
              </div>
            </div>
          </div>

        </div>
      </div>
      <div v-else>
        <div class="text-center text-slate-500 p-8 border border-slate-200 rounded-lg bg-slate-50">
          {{ t('common.no_records') }}
        </div>
      </div>
    </div>
  </div>

</template>