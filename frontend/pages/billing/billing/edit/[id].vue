<script setup>
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import BillingEdit from '~/components/organisms/BillingEdit.vue';

const { t } = useI18n();
const { $BillingApiService, $BillingBatchApiService } = useNuxtApp();
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
    // const data = await $BillingBatchApiService.getInvoices(route.params.id)
    // invoices.value = data.invoices
    // console.log(task_id.value)
  } catch (err) {
    console.error(err)
  } finally {
    pending.value = false
  }
}

onMounted(async () => {
  await getPermissions();
  if (!objectPermissions.value?.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
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
      <BillingEdit :billing="data" :task_id="task_id" :invoices="invoices" />
      <!-- <div v-for="batch in batches" :key="batch.id">
      </div> -->
    </div>
  </div>
</template>