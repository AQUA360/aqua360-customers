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

</script>
<template>
  <article
    class="relative p-2 text-base bg-white group hover:bg-blue-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-sky-500">
    <span class="absolute left-[-5px] top-0 text-[10px]">
      <Icon name="fa6-solid:circle" class="text-sky-500"/>
      </span>
    <footer class="flex justify-between items-center pt-1">
      <!-- <p class="text-sm text-gray-900 font-semibold flex gap-3">
        {{ object.type?.name }}
      </p> -->
      <div class="flex items-center mb-1">
        <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
          <TimeRelative :datetime=object.timestamp></TimeRelative>
        </p>
      </div>
      <div>
        <span class="text-slate-400 text-sm">{{ formatDateTime(object.approved_at) }}</span>
      </div>
    </footer>
    <p class="text-sm flex gap-3">
      <span class="text-slate-500">{{ object.previous_tenant? object.previous_tenant.full_name : t('contract_block.new_tenant') }}</span>
      <span>&rarr;</span>
      <span class="text-slate-900">{{ object.new_tenant?.full_name }}</span>
    </p>
  </article>
</template>