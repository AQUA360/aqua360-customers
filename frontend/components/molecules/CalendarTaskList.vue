<script setup>
import { formatDate } from '~/utils/date';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
const { t } = useI18n();

const props = defineProps({
  id: Number,       //incident id (perhaps change later and add service if tasks in more places)
  isSubRegion: Boolean,
  data: Object,    //tasks 
});

const { $CalendarTaskApiService, $ConfigProjectApiService } = useNuxtApp();

const emit = defineEmits(['show-detail', 'update:count', 'update:pending', 'refresh']);


const localData = ref(props.data ? { ...props.data } : null);
const SubRegion = ref(props.isSubRegion);
const loading = ref(false);

const sortedData = computed(() => {
  return localData?.value.sort((a, b) => new Date(a.set_date) - new Date(b.set_date));
});

const username = ref(null);
if (process.client) {
    username.value = localStorage.getItem('user_username') || '';
}

const showDetail = function (component, id) {
  emit('show-detail', component, id)
}

const markCompleted = async function (element) {
  try{
    let local_save = {
      id: element.id,
      task_done: !element.task_done
    }
  
    element = await $CalendarTaskApiService.save(local_save);
    localData.value = localData.value.map(item => item.id === element.id ? element : item);
    emit('refresh');
  } catch (err) {
    console.error('Error obtenint les dades:', err);
  }
}

watch(() => props.data, () => {
  localData.value = props.data;
}, { immediate: true });


</script>

<template>
  <div v-if="loading">
    <div class="flex justify-center items-center mt-5">
      <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
      <span class="ml-2">{{ $t('common.loading') }}...</span>
    </div>
  </div>
  <div v-else>
    <div v-if="data.length == 0" class="p-4">
      <div class="footering text-slate-500 p-2">
        <span>{{ t('dashboard.no_tasks') }}</span>
      </div>
    </div>
    <div v-else>
      <table class="min-w-full text-sm text-slate-800 mt-2">
        <thead>
          <tr class="bg-gray-100 border-b text-left">
            <th class="p-2">{{ t('common.date') }}</th>
            <th class="p-2">{{ t('dashboard.task') }}</th>
            <th class="p-2">{{ t('user') }}</th>
            <th class="p-2">{{ t('common.description') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(element, index) in sortedData" :key="element.id" class="border-b relative group"
          :class="{
            'bg-green-50': element.task_done,
            'bg-yellow-50': !element.task_done,
          }">
            <!-- <td class="">
              <abbr :title="element.task_done ? t('dashboard.completed_task') : t('dashboard.pending_task')" class="flex items-center justify-center">
                <Icon :name="element.task_done ? 'fa6-solid:check' : 'fa6-solid:circle-xmark'" 
                :class="element.task_done ? 'text-green-500' : 'text-red-500'" />
              </abbr>
            </td> -->
            <td class="p-2">
              <span>
                {{ formatDate(element.set_date) }}
              </span>
            </td>
            <td class="p-2">
              <span>
                {{ element.name }}
              </span>
            </td>
            <td class="p-2">
              <span>
                {{ element.user ? element.user.username : t('common.no_user_assigned') }}
              </span>
            </td>
            <td class="p-2">
              <span class="truncate block">
                {{ element.description ? element.description : '-' }}
              </span>
            </td>
            <td v-if="!isSubRegion && ((element.user && element.user.username === username) || element.user === null)">
              <button @click="showDetail('CalendarTaskEdit', element.id)"
                class="absolute cursor-pointer hover:text-sky-500 shadow-md border text-sm w-7 h-7 bg-white right-0 top-0 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100">
                <Icon name="fa6-solid:pencil" />
              </button>
            </td>
            <!-- <td v-if="element.user.username === username"> -->
            <td v-if="(element.user && element.user.username === username) || element.user === null">
              <abbr :title="element.task_done ? t('common.mark') + ' ' + t('common.pending') : t('common.mark') + ' ' + t('common.completed')"
                class="flex items-center justify-center absolute cursor-pointer shadow-md border text-sm w-7 h-7 bg-white right-8 top-0 rounded-md text-slate-600 opacity-0 transition-all duration-300 group-hover:opacity-100"
                :class="element.task_done ? 'hover:text-orange-500' : 'hover:text-green-500'">
                <button @click="markCompleted(element)" class="flex items-center justify-center w-7 h-7">
                  <Icon :name="element.task_done ? 'fa6-solid:circle-xmark' : 'fa6-solid:check'" />
                </button>
              </abbr>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <!-- <button class="button-default w-full mt-2 flex items-center justify-center gap-1" @click="showDetail('CalendarTaskEdit', null)">
      <Icon name="fa6-solid:plus" class="text-slate-500 mr-1" />
      <span>
        {{ t('Afegir tasca') }}
      </span>
    </button> -->

  </div>

</template>