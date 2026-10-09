<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

import { formatDate, formatDateTime } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import TimeRelative from '~/components/atoms/TimeRelative.vue';

const { t } = useI18n()
const props = defineProps({
  id: Number,
  object: Object
});

const emit = defineEmits(['delete']);

const { $LoggerApiService } = useNuxtApp();

const pending = ref(true);
const changes = ref(null)


const getData = async () => {
  pending.value = true;
  try {
    const result = await $LoggerApiService.getAll("claim-request-contract-change", props.id);
    changes.value = result.results

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
    <div class="flex justify-center items-center">
      <Icon name="fa6-solid:spinner" class="animate-spin text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}</span>
    </div>
  </div>
  <div v-else-if="!pending && changes && changes.length == 0">
    <div class="footering text-slate-500 p-2">
      {{ t('common.no_changes') }}
    </div>

  </div>
  <div v-else>

    <div v-if="changes && changes.length > 0">
      <article v-for="change in changes"
        class="relative p-2 text-base bg-white group hover:bg-blue-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-sky-500">
        <span class="absolute left-[-5px] top-0 text-[10px]">
          <Icon name="fa6-solid:circle" class="text-sky-500" />
        </span>
        <footer class="flex justify-between items-center pt-1">
          <div class="flex items-center mb-1">
            <p v-if="change.user" class="text-sm text-gray-700 mr-3">{{ change.user?.username }}</p>
            <p v-else class="text-sm text-gray-700 mr-3">{{ t('common.admin') }}</p>
            <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
              <TimeRelative :datetime=change.timestamp></TimeRelative>
            </p>
          </div>

        </footer>

        <div>

          <div>
            <p class="text-slate-500 italic text-xs">{{ t("billing_block.excluded") }}</p>
            <p v-if="change.deleted_contract" class="text-sm flex gap-3">
              <span>
                <span class="text-slate-500 mr-3">
                  {{ change.deleted_contract?.token }}
                </span>
                <span class="text-slate-500 text-xs">
                  ({{ change.deleted_contract?.holder }})
                </span>
              </span>
              <span>&rarr;</span>
              <span v-if="change.current_debt_management" class="text-slate-900">{{ change.current_debt_management.name
              }}</span>
              <span v-else-if="change.amount_paid" class="text-slate-900">{{ t('Factura pagada: ') +
                formatMoneyWithCurrency(change.amount_paid) }}</span>
              <span v-else class="text-slate-900">{{ t('billing_block.manual_exclusion') }}</span>
            </p>
            <p v-else-if="change.previous_status" class="text-sm flex gap-3">
              <AtomsColorBadge v-if="change.previous_status" :value="change.previous_status.name"
                :color="change.previous_status.color" class="opacity-50"></AtomsColorBadge>
              <span v-if="change.previous_status">&rarr;</span>
              <AtomsColorBadge v-if="change.current_status" :value="change.current_status.name"
                :color="change.current_status.color"></AtomsColorBadge>
            </p>
          </div>
        </div>
      </article>
    </div>
  </div>

</template>