<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Time from '~/components/atoms/Time.vue';
import PersonDetail from './PersonDetail.vue';


const { $AddressHelper, $PiggyBankApiService, $PersonPiggyBankApiService } = useNuxtApp();

const { t } = useI18n();

const props = defineProps({
  id: Number, // ID de l'element
  isSubRegion: false,
  isSubRegionOpen: Boolean,
  data: Object,
  isPerson: false,
  canChange: Boolean
});

const emit = defineEmits(['showDetail']);

const pending = ref(false);
const localData = ref(props.data ? props.data : null);

const getData = async () => {
  pending.value = true;
  try {
    if (!props.isPerson) {
      const data = await $PiggyBankApiService.getDetail(props.id);
      localData.value = data;
    } else {
      const data = await $PersonPiggyBankApiService.getDetail(props.id);
      localData.value = data;
    }
  } catch (error) {
    console.error(error);
  } finally {
    pending.value = false;
  }
}

onMounted(() => {
  if (props.id && !props.data) {
    getData();
  }
});

watch(() => props.id, () => {
  if (props.id && !props.data) {
    getData();
  }
});

watch(() => props.data, () => {
  localData.value = props.data;
}, { immediate: true, deep: true });

const showDetail = (component, id) => {
  emit('showDetail', component, id);
}


</script>

<template>
  <div v-if="localData && !pending">
    <div class="flex justify-between items-start gap-4 mb-4">
      <div role="row" class="grid grid-cols-2 flex-1">
        <FieldDetail v-if="!isPerson" :label='$t("contract")' :value=localData.token></FieldDetail>
        <FieldDetail :label='$t("contract_block.holder")' :value="localData.person?.full_name"></FieldDetail>
        <FieldDetail :label='$t("common.total")' :value=formatMoneyWithCurrency(localData.amount) class="font-bold text-sky-700"></FieldDetail>
      </div>
      <div v-if="canChange" class="flex flex-col gap-2">
        <button @click="showDetail('AddPiggyBankBalance', localData.id)"
          class="flex items-center gap-2 px-3 py-2 bg-sky-50 text-sky-700 border border-sky-200 rounded-lg hover:bg-sky-100 hover:border-sky-300 transition-all shadow-sm text-xs font-semibold whitespace-nowrap">
          <Icon name="fa6-solid:plus" />
          {{ t('common.add') }} {{ t('contract_block.balance') }}
        </button>
        <button :disabled="localData.amount <= 0" @click="showDetail('ReturnPiggyBankRegion', localData.id)"
          class="flex items-center gap-2 px-3 py-2 bg-red-50 text-red-700 border border-red-200 rounded-lg enabled:hover:bg-red-100 enabled:hover:border-red-300 disabled:opacity-50 disabled:grayscale transition-all shadow-sm text-xs font-semibold whitespace-nowrap">
          <Icon name="fa6-solid:minus" />
          {{ t('common.return_action') }} {{ t('contract_block.balance') }}
        </button>
      </div>
    </div>
    <hr class="my-2">
    <div class="h-[60vh] overflow-y-auto scrollbar-hide">
      <div v-for="movement in localData.movements"
        class="grid grid-cols-[50px,1fr] items-center py-1 px-2 border rounded-lg mb-2"
        :class="{ 'bg-green-50 border-green-500': movement.is_positive, 'bg-red-50 border-red-500': !movement.is_positive }">
        <Icon name="fa6-solid:angles-right" class="text-slate-400" />
        <div class="grid grid-cols-2 flex items-center mt-1">
          <FieldDetail :label='movement.is_positive ? $t("common.in_date") : $t("common.out_date")'
            :value=formatDate(movement.movement_date)></FieldDetail>
          <FieldDetail :label='$t("common.amount")' :value=formatMoneyWithCurrency(movement.amount)></FieldDetail>
          <FieldDetail v-if="movement.bail" :label='$t("bail")'>
            <button @click="showDetail('BailRegion', movement.bail.id)"
              class="text-start text-sky-500 underline hover:text-sky-600 hover:no-underline">
              {{ movement.bail.token }}
            </button>
          </FieldDetail>
          <FieldDetail v-if="movement.payment" :label='movement.is_positive? 
          $t("billing_block.entry_payment") : movement.payment.invoice_id || movement.payment.commitment_deposit_id ?
          $t("billing_block.payment") : $t("billing_block.returned_payment")'>
            <button @click="showDetail('PaymentRegion', movement.payment.id)"
              class="text-start text-sky-500 underline hover:text-sky-600 hover:no-underline">
              {{ movement.payment.token }}
            </button>
          </FieldDetail>
          <FieldDetail v-if="movement.commitment_deposit" :label='$t("commitment_deposit")'>
            <button @click="showDetail('CommitmentDepositRegion', movement.commitment_deposit.id)"
              class="text-start text-sky-500 underline hover:text-sky-600 hover:no-underline">
              {{ movement.commitment_deposit.token }}
            </button>
          </FieldDetail>
          <FieldDetail v-if="movement.user" :label='$t("user")' :value="movement.user.username"/>
        </div>
      </div>
      <div v-if="localData.movements.length === 0">
        <p class="text-center text-slate-500">{{ $t('common.no_records') }}</p>
      </div>
    </div>

  </div>
  <div v-else>
    <div class="flex justify-center items-center h-full">
      <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>
  </div>
</template>