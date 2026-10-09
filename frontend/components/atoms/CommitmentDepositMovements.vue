<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

import { formatDate, formatDateTime } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import TimeRelative from '~/components/atoms/TimeRelative.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n()
const props = defineProps({
  id: Number,
});

const { $LoggerApiService } = useNuxtApp();

const emit = defineEmits(['delete', 'update:count']);

const data = ref(null)
const title = ref('')
const pending = ref(false)

const getData = async () => {
  pending.value = true
  try {
    const result = await $LoggerApiService.getAll("commitment-deposit-movement", props.id);
    data.value = result.results;
    emit('update:count', data.value.length)
  } catch (err) {
    console.error(err)
  } finally {
    pending.value = false;
  }
}

onMounted(() => {
  getData()
})


</script>
<template>
  <div v-if="pending">
    <AppLoading :text="$t('common.loading')" :size="40" />
  </div>

  <div v-else>
    <div v-if="data && data.length > 0">
      <div v-for="item in data" :key="item.id" class="">
        <article
          class="relative p-2 text-base bg-white group hover:bg-blue-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-sky-500">
          <span class="absolute left-[-5px] top-0 text-[10px]">
            <Icon name="fa6-solid:circle" class="text-sky-500" />
          </span>
          <footer class="flex justify-between items-center pt-1">
            <!-- <p class="text-sm text-gray-900 font-semibold flex gap-3">
              {{ object.type?.name }}
            </p> -->
            <div class="flex items-center mb-1">
              <p v-if="item.user" class="text-sm text-gray-700 mr-3">{{ item.user?.username }}</p>
              <p v-else class="text-sm text-gray-700 mr-3">{{ t('common.admin') }}</p>
              <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
                <TimeRelative :datetime=item.timestamp></TimeRelative>
              </p>
            </div>
          </footer>


          <p v-if="item?.previous_status?.token !== item?.current_status?.token"
            class="text-sm text-gray-800 flex gap-3 mb-2">
            <AtomsColorBadge v-if="item.previous_status" :value="item.previous_status.name"
              :color="item.previous_status.color" class="opacity-50"></AtomsColorBadge>
            <span v-if="item.previous_status">&rarr;</span>
            <AtomsColorBadge v-if="item.current_status" :value="item.current_status.name"
              :color="item.current_status.color"></AtomsColorBadge>
          </p>

          <div v-if="item.new_payment" class="text-sm text-gray-800 mb-3">
            <p class="text-slate-400 font-medium text-sm mb-1">
              {{ t('billing_block.fractionated_payment') }}
            </p>
            <div>
              <span class="opacity-50">
                {{ item.new_payment.payment_date? formatDate(item.new_payment.payment_date) : t('Sense data de pagament registrada') }}
              </span>
              &rarr;
              <span>
                {{ formatMoneyWithCurrency(item.new_payment.currently_paid) }}
                <span v-if="item.new_payment.payment_type" class="ml-2 opacity-60" >
                  ({{ item.new_payment.payment_type.name }})
                </span>
              </span>
            </div>
          </div>

          <div v-if="item.new_wallet" class="text-sm text-gray-800 mb-3">
            <p class="text-slate-400 font-medium text-sm mb-1">
              {{ t('billing_block.new_wallet_mov') }}
            </p>
            <div>
              <span class="opacity-50">
                {{ item.new_wallet.token }}
              </span>
              &rarr;
              <span>
                {{ item.new_wallet.payment_type }}
                
              </span>
            </div>
          </div>

          <div v-if="item.new_invoices && item.new_invoices.length > 0" class="text-sm text-gray-800 mb-3">
            <p class="text-slate-400 font-medium text-sm mb-1">
              {{ t('billing_block.added_invoices') }}
            </p>
            <div v-for="invoice in item.new_invoices" :key="invoice.id">
              <span class="opacity-50">
                {{ invoice.token }} - {{ invoice.customer_final }} ({{ invoice.customer_token_final }})
              </span>
            </div>
          </div>

          <div v-if="item.previous_remaining !== item.current_remaining" class="text-sm text-gray-800 mb-3">
            <p class="text-slate-400 font-medium text-sm mb-1">
              {{ t('billing_block.bag_amount_change') }}
            </p>
            <div>
              <span class="opacity-50">
                {{ formatMoneyWithCurrency(item.previous_remaining) }}
              </span>
              &rarr;
              {{ formatMoneyWithCurrency(item.current_remaining) }}
            </div>
          </div>

          <div v-if="item.used_remaining > 0" class="text-sm text-gray-800 mb-3">
            <p class="text-slate-400 font-medium text-sm mb-1">
              {{ t('billing_block.used_bag') }}
            </p>
            <div class="flex gap-3">
              <span class="opacity-50">
                {{ formatMoneyWithCurrency(item.used_remaining) }}
              </span>
              &rarr;
              <div class="grid grid-rows-2 gap-2">
                <span v-if="item.paid_invoice">
                  {{ t('billing_block.paid_invoice') }}: {{ item.paid_invoice.token }}
                </span>
                <span v-if="item.paid_invoice_payment">
                  {{ t('billing_block.paid_invoice_payment') }}: {{ item.paid_invoice_payment.token }}
                </span>
              </div>
            </div>
          </div>


        </article>
      </div>
    </div>
    <div v-else>
      <div class="footering text-slate-500 p-2">
        {{ t('common.no_data_found') }}
      </div>
    </div>
  </div>
</template>