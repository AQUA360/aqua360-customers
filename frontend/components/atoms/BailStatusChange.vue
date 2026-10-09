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
const titleChanges = ref([])
const title = ref('')
const bailChange = ref(null)



const getData = async () => {
  pending.value = true;
  try {
    const result = await $LoggerApiService.getAll("bail-status", props.id);
    bailChange.value = result.results;
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
  <div v-if="bailChange && bailChange.length > 0">
    <article v-for="change in bailChange" 
      class="relative p-2 text-base bg-white group hover:bg-blue-50 px-4 mt-0 pt-0 pb-5 border-l hover:border-sky-500">
      <span class="absolute left-[-5px] top-0 text-[10px]">
        <Icon name="fa6-solid:circle" class="text-sky-500" />
      </span>
      <footer class="flex justify-between items-center pt-1">
        <div class="flex items-center mb-1">
          <p v-if="change.user" class="text-sm text-gray-700 mr-3">{{ change.user?.username }}</p>
          <p v-else class="text-sm text-gray-700 mr-3">{{  t('common.admin') }}</p>
          <p class="inline-flex items-center text-sm text-gray-900 font-semibold">
            <TimeRelative :datetime=change.timestamp></TimeRelative>
          </p>
        </div>
      </footer>

      <div>
        <p class="text-sm flex gap-3">
          <span class="text-slate-500">{{ change.previous_status }}</span>
          <span>&rarr;</span>
          <span class="text-slate-900">{{ change.current_status }}</span>
        </p>
      </div>

    </article>
  </div>
  <div v-else class="footering text-slate-500 p-2">
    <span class="text-slate-500 mt-1 font-medium text-sm px-2 py-1">
      {{ t('common.no_changes') }}
    </span>
  </div>
</template>