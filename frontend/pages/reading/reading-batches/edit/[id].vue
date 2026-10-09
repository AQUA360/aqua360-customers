<script setup>
import { useI18n } from 'vue-i18n';

import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import ReadingBatchEdit from '~/components/organisms/ReadingBatchEdit.vue';
const { t } = useI18n();
const { $ReadingBatchApiService } = useNuxtApp();

const route = useRoute()
const pending = ref(true)
const counters = ref({})
const countersPending = ref({})
const id = ref(null);
const batchName = ref(null);
const activeStatus = ref(null);
const num_supplies = ref(null);
const num_contracts = ref(null);
const num_no_meters = ref(null);
const no_route_supply_points_count = ref(null);
const missing_billing_data = ref(null)
const allow_force_manual = ref(false)

const loadData = async () => {
  const data = await $ReadingBatchApiService.getSummary(route.params.id)
  console.log('data', data)
  id.value = data.id
  batchName.value = data.name
  counters.value = data.counters
  countersPending.value = data.counters_pending
  pending.value = false
  activeStatus.value = data.status
  num_supplies.value = data.num_supplies
  num_contracts.value = data.num_contracts
  num_no_meters.value = data.num_no_meter
  no_route_supply_points_count.value = data.no_route_supply_points_count
  missing_billing_data.value = data.missing_billing_data
  allow_force_manual.value = data.allow_force_manual
}

onMounted(() => {
  loadData();
})


</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="flex justify-between items-center mb-6">
      <H1>{{ $t('common.reading_batch_detail') }} - {{ batchName }}</H1>
    </div>
    <div v-if="pending">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <ReadingBatchEdit v-else :id="id" :counters="counters" :counters_pending="countersPending"
      :activeStatus="activeStatus" :num_supplies="num_supplies" :num_contracts="num_contracts"
      :num_no_meters="num_no_meters" :no_route_supply_points_count="no_route_supply_points_count"
      :missing_billing_data="missing_billing_data" :allow_force_manual="allow_force_manual" />
  </div>
</template>