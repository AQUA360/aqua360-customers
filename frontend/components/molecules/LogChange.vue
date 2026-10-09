<script setup>
import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

import { formatDate, formatDateTime } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import TimeRelative from '~/components/atoms/TimeRelative.vue';

const props = defineProps({
  id: Number,
  object: Object
});

const emit = defineEmits(['delete']);

const deleteItem = () => {
  emit('delete', props.id)
}

</script>
<template>
  <article
    class="relative p-2 text-base bg-white group hover:bg-blue-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-sky-500">
    <span class="absolute left-[-5px] top-0 text-[10px]"><Icon name="fa6-solid:circle"
        class="text-sky-500"/></span>
    <footer class="flex justify-between items-center pt-1">
      <div class="flex items-center mb-1">
        <p v-if="object.user" class="text-sm text-gray-700 mr-3">{{ object.user?.username }}</p>
        <p v-else class="text-sm text-gray-700 mr-3">{{ $t('common.admin') }}</p>
        <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
          <TimeRelative :datetime=object.timestamp></TimeRelative>
        </p>
      </div>
      <div>
        <span class="text-slate-400 text-sm">{{ formatDateTime(object.timestamp) }}</span>
      </div>
    </footer>
    <div class="text-sm text-gray-800 flex gap-3">
      <div v-if="object.action == 'activate'" class="grid grid-cols-[80px,1fr]">
        <span>{{ $t('common.active') }}: </span>
        <AtomsColorBadge v-if="object.current_status" :value="object.current_status.name"
          :color="object.current_status.color" class=""></AtomsColorBadge>
      </div>

      <div v-if="object.action == 'deactivate'" class="grid grid-cols-[80px,1fr]">
        <span>{{ $t('common.termination') }}: </span>
        <div>
          <AtomsColorBadge v-if="object.previous_status" :value="object.previous_status.name"
            :color="object.previous_status.color" class="opacity-50"></AtomsColorBadge>
          <span v-if="object.previous_status">&rarr;</span>
          <AtomsColorBadge v-if="object.current_status" :value="object.current_status.name"
            :color="object.current_status.color"></AtomsColorBadge>
        </div>
      </div>

      <div v-if="object.action == 'cut'" class="grid grid-cols-[80px,1fr]">
        <span>{{ $t('common.cut') }}: </span>
        <div>
          <AtomsColorBadge v-if="object.previous_status" :value="object.previous_status.name"
            :color="object.previous_status.color" class="opacity-50"></AtomsColorBadge>
          <span v-if="object.previous_status">&rarr;</span>
          <AtomsColorBadge v-if="object.current_status" :value="object.current_status.name"
            :color="object.current_status.color"></AtomsColorBadge>
        </div>
      </div>

      <div v-if="object.action == 'meter'" class="grid grid-cols-[120px,1fr]">
        <span>{{ $t('common.change') }} {{ $t('meter') }}: </span>
        <span>
          <span class="opacity-50">{{ object.previous_value }}</span> &rarr; <span class="">{{ object.current_value
            }}</span>
        </span>
      </div>

      <div v-if="object.action == 'connection'" class="grid grid-cols-[120px,1fr]">
        <span>{{ $t('common.change') }} {{ $t('connection') }}: </span>
        <span>
          <span class="opacity-50">{{ object.previous_value }}</span> &rarr; <span class="">{{ object.current_value
            }}</span>
        </span>
      </div>

      <div v-if="object.action == 'address'" class="grid grid-cols-[120px,1fr]">
        <span>{{ $t('common.change') }} {{ $t('address_block.address') }}: </span>
        <span>
          <span class="opacity-50">{{ object.previous_value }}</span> &rarr; <span class="">{{ object.current_value
            }}</span>
        </span>
      </div>
    </div>
    <p class="text-sm text-gray-800 italic" v-if="object.observation">{{ object.observation }}</p>
  </article>
</template>
<style scoped>
article {
  margin-left: -1px !important;
}
</style>