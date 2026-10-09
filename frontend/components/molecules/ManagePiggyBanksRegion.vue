<script setup>
import { computed, ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '../atoms/FieldDetail.vue';

const { t } = useI18n();
const toast = useToast();
const props = defineProps({
  data: Object,
  id: Number, // ID del piggy bank
  isPerson: false
});

const { $PiggyBankApiService, $ConfiglistApiService, $PersonPiggyBankApiService, $PersonApiService } = useNuxtApp();
const emit = defineEmits(['close']);
const loading = ref(false)
const saving = ref(false)
const localData = ref(props.data ? props.data : null);

const relatedPiggyBanks = ref([])
const transferTotals = computed(() => {
  const piggyBanksWithAmount = relatedPiggyBanks.value.filter((piggyBank) => Number(piggyBank.amount_to_transfer) > 0)
  const totalIncoming = piggyBanksWithAmount
    .filter((piggyBank) => !piggyBank.isGiving)
    .reduce((sum, piggyBank) => sum + Number(piggyBank.amount_to_transfer || 0), 0)
  const totalOutgoing = piggyBanksWithAmount
    .filter((piggyBank) => piggyBank.isGiving)
    .reduce((sum, piggyBank) => sum + Number(piggyBank.amount_to_transfer || 0), 0)
  return {
    incoming: totalIncoming,
    outgoing: totalOutgoing,
    net: totalIncoming - totalOutgoing
  }
})

const getAvailableForOutgoing = (currentPiggyBankId = null) => {
  const totalIncoming = relatedPiggyBanks.value
    .filter((piggyBank) => Number(piggyBank.amount_to_transfer) > 0 && !piggyBank.isGiving)
    .reduce((sum, piggyBank) => sum + Number(piggyBank.amount_to_transfer || 0), 0)
  const totalOutgoingWithoutCurrent = relatedPiggyBanks.value
    .filter((piggyBank) =>
      Number(piggyBank.amount_to_transfer) > 0 &&
      piggyBank.isGiving &&
      piggyBank.id !== currentPiggyBankId
    )
    .reduce((sum, piggyBank) => sum + Number(piggyBank.amount_to_transfer || 0), 0)

  return Number(localData.value?.amount || 0) + totalIncoming - totalOutgoingWithoutCurrent
}

const canSave = computed(() =>
  relatedPiggyBanks.value.some((piggyBank) =>
    Number(piggyBank.amount_to_transfer) > 0
  )
)

const loadData = async () => {
  try {
    loading.value = true;
    const get_data = await $PiggyBankApiService.getRelatedPiggyBankData(props.id, props.isPerson == true);
    relatedPiggyBanks.value = get_data.related_piggy_banks;
    relatedPiggyBanks.value.forEach(piggyBank => {
      piggyBank.amount_to_transfer = 0;
      piggyBank.isGiving = false;
      piggyBank.warnAmount = false;
    });

  } catch (error) {
    console.error(error)
  } finally {
    loading.value = false;
  }
}


const save = async () => {
  saving.value = true;
  try {
    let save_data = {
      related_piggy_banks: relatedPiggyBanks.value
        .filter((piggyBank) => Number(piggyBank.amount_to_transfer) != 0)
        .map((piggyBank) => ({
          id: piggyBank.id,
          amount_to_transfer: Number(piggyBank.amount_to_transfer),
          is_giving: piggyBank.isGiving
        })),
      total_to_transfer: transferTotals.value.net,
      total_incoming: transferTotals.value.incoming,
      total_outgoing: transferTotals.value.outgoing,
      is_person: props.isPerson == true
    }
    const response = await $PiggyBankApiService.moveBalance(props.id, save_data);
    if (response) {
      emit('close');
    }
  } catch (error) {
    console.error(error)
  } finally {
    saving.value = false;
  }
}

const checkAmount = (relatedPiggyBank) => {
  relatedPiggyBank.warnAmount = false
  if (relatedPiggyBank.amount_to_transfer < 0) {
    relatedPiggyBank.warnAmount = true
    relatedPiggyBank.amount_to_transfer = 0
  }

  if (relatedPiggyBank.isGiving) {
    const maxOutgoing = Math.max(getAvailableForOutgoing(relatedPiggyBank.id), 0)
    if (relatedPiggyBank.amount_to_transfer > maxOutgoing) {
      relatedPiggyBank.warnAmount = true
      relatedPiggyBank.amount_to_transfer = maxOutgoing
    }
    return
  }

  if (relatedPiggyBank.amount_to_transfer > relatedPiggyBank.amount) {
    relatedPiggyBank.warnAmount = true
    relatedPiggyBank.amount_to_transfer = relatedPiggyBank.amount
  }
}

const checkDisabled = (relatedPiggyBank) => {
  const hasOutgoingCapacity = getAvailableForOutgoing(relatedPiggyBank.id) > 0
  const hasIncomingCapacity = relatedPiggyBank.amount > 0
  if ((relatedPiggyBank.isGiving && !hasOutgoingCapacity) || (!relatedPiggyBank.isGiving && !hasIncomingCapacity)) {
    relatedPiggyBank.amount_to_transfer = 0
    return false
  }
  return true
}

const toggleGiving = (relatedPiggyBank) => {
  relatedPiggyBank.isGiving = !relatedPiggyBank.isGiving;
  checkAmount(relatedPiggyBank);
  checkDisabled(relatedPiggyBank);
}

const getRelationRole = (relatedPiggyBank) => {
  if (localData.value?.person?.id == relatedPiggyBank.contract_holder?.id) {
    return t('contract_block.holder')
  }
  if (relatedPiggyBank.contract_tenant && relatedPiggyBank.person?.id == relatedPiggyBank.contract_tenant?.id) {
    return t('contract_block.tenant')
  }
  if (relatedPiggyBank.contract_owner && relatedPiggyBank.person?.id == relatedPiggyBank.contract_owner?.id) {
    return t('contract_block.owner')
  }
  return '-'
}

onMounted(async () => {
  await loadData()
})

</script>

<template>
  <div class="h-full">
    <div v-if="loading" class="flex h-full items-center justify-center py-2">
      <div
        class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/80 px-4 py-2 text-sm text-slate-600 shadow-sm">
        <Icon name="fa6-solid:spinner" class="animate-spin text-lg text-slate-500" />
        <span>{{ $t('common.loading') }}...</span>
      </div>
    </div>

    <div v-else-if="localData" class="region__content">
      <div>
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <H1Region>
            {{ $t('billing_block.manage_piggy_banks') }}
          </H1Region>
          <div
            class="inline-flex w-fit items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700">
            <Icon name="fa6-solid:piggy-bank" class="text-sky-500" />
            <span class="uppercase tracking-wide">
              {{ t('contract_block.available_balance') }}
            </span>
            <span class="font-bold text-emerald-600">
              {{ formatMoneyWithCurrency(localData.amount) }}
            </span>
          </div>
        </div>

        <div
          class="mb-3 flex items-center justify-between gap-3 py-1">
          <div
            class="inline-flex w-fit items-center gap-2 rounded-full border border-sky-200 bg-white px-3 py-1 text-xs font-semibold text-sky-700">
            <Icon name="fa6-solid:scale-balanced" class="text-sky-500" />
            <span class="uppercase tracking-wide">
              {{ t('billing_block.total_to_transfer') }}
            </span>
            <span class="font-bold" :class="transferTotals.net > 0 ? 'text-emerald-600' : 'text-orange-600'">
              {{ transferTotals.net > 0 ? '+' : '' }}{{ formatMoneyWithCurrency(transferTotals.net) }}
            </span>
          </div>

          <div class="flex flex-wrap items-center gap-2 md:justify-end">
            <div v-if="transferTotals.incoming > 0"
              class="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
              <Icon name="fa6-solid:piggy-bank" class="text-emerald-500" />
              <span class="uppercase tracking-wide">
                {{ t('billing_block.obtain_balance') }}
              </span>
              <span class="font-bold">
                +{{ formatMoneyWithCurrency(transferTotals.incoming) }}
              </span>
            </div>
            <div v-if="transferTotals.outgoing > 0"
              class="inline-flex items-center gap-2 rounded-full border border-orange-200 bg-orange-50 px-3 py-1 text-xs font-semibold text-orange-700">
              <Icon name="fa6-solid:piggy-bank" class="text-orange-500" />
              <span class="uppercase tracking-wide">
                {{ t('billing_block.give_balance') }}
              </span>
              <span class="font-bold">
                -{{ formatMoneyWithCurrency(transferTotals.outgoing) }}
              </span>
            </div>
          </div>
        </div>

        <div class="space-y-2.5">
          <div v-for="relatedPiggyBank in relatedPiggyBanks" :key="relatedPiggyBank.id"
            class="grid grid-cols-1 gap-3 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-[1fr,15rem] md:items-center">
            <div class="min-w-0">
              <p class="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                {{ t('contract_block.piggy_bank') }}
              </p>
              <div class="my-1 flex flex-wrap items-center gap-2">
                <span class="truncate text-sm font-semibold text-slate-800">{{ relatedPiggyBank.token }}</span>
                <AtomsColorBadge v-if="isPerson" :color="relatedPiggyBank.contract_status_color"
                  :value="relatedPiggyBank.contract_status_name" />
                <span v-if="isPerson"
                  class="inline-flex items-center rounded-md bg-sky-100 px-2 py-0.5 text-xs font-semibold text-sky-700">
                  {{ getRelationRole(relatedPiggyBank) }}
                </span>
              </div>
              <div>
                <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {{ t('contract_block.available_balance') }}: 
                </span>
                <span class="font-bold text-emerald-600">
                  {{ formatMoneyWithCurrency(relatedPiggyBank.amount) }}
                </span>
              </div>
            </div>

            <div class="rounded-lg border border-slate-200 bg-slate-50 p-2.5">
              <p class="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
                {{ t('contract_block.balance_to_move') }} (€)
              </p>
              <input type="number" :disabled="!checkDisabled(relatedPiggyBank)"
                v-model="relatedPiggyBank.amount_to_transfer" @input="checkAmount(relatedPiggyBank)"
                class="input h-8 w-full rounded-md bg-white text-sm"
                :class="{ 'border-orange-500 text-orange-500': relatedPiggyBank.warnAmount }" />

              <div class="mt-2 grid grid-cols-2 gap-1 text-[11px] font-semibold">
                <button type="button" class="rounded-md px-2 py-1.5 leading-none transition"
                  :class="!relatedPiggyBank.isGiving ? 'bg-emerald-500 text-white shadow-sm' : 'bg-white text-slate-600 hover:bg-slate-100'"
                  @click="toggleGiving(relatedPiggyBank)">
                  {{ $t('billing_block.obtain_balance') }}
                </button>
                <button type="button" class="rounded-md px-2 py-1.5 leading-none transition"
                  :class="relatedPiggyBank.isGiving ? 'bg-orange-500 text-white shadow-sm' : 'bg-white text-slate-600 hover:bg-slate-100'"
                  @click="toggleGiving(relatedPiggyBank)">
                  {{ $t('billing_block.give_balance') }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div class="mt-4 flex justify-end border-t border-slate-100 pt-3">
          <button class="button-primary justify-center flex items-center gap-x-2"
            :disabled="!canSave || saving" @click="save">
            <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="saving ? 'animate-spin' : ''" />
            {{ t('common.save') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
