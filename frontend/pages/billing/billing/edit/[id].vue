<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import BillingEdit from '~/components/organisms/BillingEdit.vue';

const { t } = useI18n();
const { $BillingApiService, $BillingBatchApiService, $ConfigProjectApiService } = useNuxtApp();
const objectPermissions = ref(null);
const toast = useToast();
const route = useRoute()
const pending = ref(true)
const batches = ref([])
const invoices = ref([])
const task_id = ref("")

const data = ref(null)

const getPermissions = async () => {
  try {
    const data = await $BillingApiService.getPermissions();
    objectPermissions.value = data;
  } catch (err) {
    console.log(err)
  }
}

const loadData = async () => {
  pending.value = true
  try {
    data.value = await $BillingApiService.getDetail(route.params.id)
    batches.value = data.value.billing_batches
    task_id.value = data.value.task_id
    periodStart.value = data.value.period_start || ''
    periodEnd.value = data.value.period_end || ''
    // const data = await $BillingBatchApiService.getInvoices(route.params.id)
    // invoices.value = data.invoices
    // console.log(task_id.value)
  } catch (err) {
    console.error(err)
  } finally {
    pending.value = false
  }
}

const periodStart = ref('')
const periodEnd = ref('')
const savingPeriod = ref(false)
const lockedStatusTokens = ref([])

// El període només es pot canviar mentre la facturació no s'ha processat
// (mateix criteri d'estats que BillingEdit: generant documents o processada).
const periodEditable = computed(() => !lockedStatusTokens.value.includes(data.value?.status?.token))

const savePeriod = async () => {
  if (!periodEditable.value) return
  if (!periodStart.value || !periodEnd.value || periodStart.value > periodEnd.value) {
    toast.error(t('billing_block.invalid_period'))
    return
  }
  savingPeriod.value = true
  try {
    await $BillingApiService.patch(route.params.id, {
      period_start: periodStart.value,
      period_end: periodEnd.value,
    })
    toast.success(t('common.saved_successfully'))
  } catch (err) {
    console.error(err)
    toast.error(t('common.error'))
  } finally {
    savingPeriod.value = false
  }
}

onMounted(async () => {
  await getPermissions();
  if (!objectPermissions.value?.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  try {
    lockedStatusTokens.value = [
      await $ConfigProjectApiService.get('billing_batch_processing_documents'),
      await $ConfigProjectApiService.get('billing_batch_processed'),
    ]
  } catch (err) {
    console.error(err)
  }
  loadData();
})


</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('billing') }}</H1>
    </div>
    <div v-if="pending">
      <p>{{ $t('common.loading') }}...</p>
    </div>
    <div v-else-if="data">
      <div role="row" class="grid grid-cols-2 pb-5 px-5">
        <FieldDetail :label='$t("common.code")' :value=data.token></FieldDetail>
        <FieldDetail :label='$t("common.name")' :value=data.name></FieldDetail>
      </div>
      <div class="px-5 pb-5">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ $t('billing_block.period_to_bill') }}</label>
        <p v-if="!periodEditable">
          {{ periodStart }} – {{ periodEnd }}
        </p>
        <div v-else class="flex gap-2 items-center max-w-xl">
          <input type="date" v-model="periodStart" :aria-label="$t('billing_block.period_start')" class="input w-full text-base border border-gray-300 rounded p-2" />
          <input type="date" v-model="periodEnd" :aria-label="$t('billing_block.period_end')" class="input w-full text-base border border-gray-300 rounded p-2" />
          <button class="button-primary" :disabled="savingPeriod" @click="savePeriod">{{ $t('common.save') }}</button>
        </div>
      </div>
      <BillingEdit :billing="data" :task_id="task_id" :invoices="invoices" />
      <!-- <div v-for="batch in batches" :key="batch.id">
      </div> -->
    </div>
  </div>
</template>