<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import ButtonOutline from '../atoms/ButtonOutline.vue';

const { $CalendarTaskApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  id: {
    type: Number,
    required: false
  },
  data: {
    type: Object,
    required: false
  },
  isSubRegion: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['show-detail', 'edit']);

const isLoading = ref(false);
const error = ref(null);

const localData = ref(props.data ? { ...props.data } : null);
const local_checked = ref(props.data ? props.data.task_done : false);

const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $CalendarTaskApiService.getDetail(props.id);
    localData.value = detail;
    local_checked.value = detail.task_done;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }


};

const handleTaskCheck = async (event) => {
  local_checked.value = event.target.checked;
  let local_save = {
    id: localData.value.id,
    task_done: local_checked.value
  }

  localData.value = await $CalendarTaskApiService.save(local_save);
};

const getStyleColor = (color) => {
  if (!color) return "border-slate-200 bg-slate-50";
  //IF DIRECTLY USING return `border-${color}-400 bg-${color}-50`; BORDER WONT APPEAR
  switch (color) {
    case 'gray':
      return `border-gray-400 bg-gray-50`;
    case 'green':
      return `border-green-400 bg-green-50`;
    case 'red':
      return `border-red-400 bg-red-50`;
    case 'yellow':
      return `border-yellow-400 bg-yellow-50`;
    case 'blue':
      return `border-blue-400 bg-blue-50`;
    case 'purple':
      return `border-purple-400 bg-purple-50`;
    case 'pink':
      return `border-pink-400 bg-pink-50`;
    case 'orange':
      return `border-orange-400 bg-orange-50`;
    default:
      return `border-${color}-400 bg-${color}-50`;
  }
};

const showDetail = function (component, id) {
  emit('show-detail', component, id);
}

const edit = function () {
  emit('edit', 'CalendarTaskEdit', localData.value.id);
}

onMounted(() => {
  if (!props.data && props.id) {
    fetchData();
  }
});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
});
</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <span class="text-red-600">{{
      $t("common.error_load")
    }}</span>
  </div>

  <div v-else-if="localData" class="group rounded-md border-l-8 relative" :class="getStyleColor(localData.color)">
    <div class="px-4 py-2">
      <div class="px-4 py-2 flex justify-between">
        <div class=" text-slate-700 font-medium rounded-t-md">
          {{ localData.name }}
        </div>
        <!-- <label class="text-slate-800 text-base flex items-center gap-1">
          {{ t('Completat') }}
          <input @change="handleTaskCheck" type="checkbox" class="mr-2" :checked="local_checked" />
        </label> -->

      </div>

      <div class="mt-2">
        <FieldDetail :label="$t('common.assigned')"
          :value="localData.user ? localData.user.username : t('common.no_user_assigned')" :strong="true" />
        <FieldDetail v-if="localData.description" :label="$t('dashboard.task_description')" :value="localData.description"
          :strong="true" />
        <FieldDetail v-if="localData.contract" :label="$t('contract')" :strong="true" >
          <button v-if="!isSubRegion" @click="showDetail('ContractRegion', localData.contract.id)" class="text-left">
            <span class="text-sky-500 underline hover:no-underline">{{ localData.contract.token }}</span>
          </button>
          <span v-else>
            {{ localData.contract.token }}
          </span>
        </FieldDetail>
      </div>

      <div class="flex justify-end">
        <label class="text-slate-800 text-base flex items-center gap-1">
          {{ t('common.completed') }}
          <input @change="handleTaskCheck" type="checkbox" class="mr-2" :checked="local_checked" />
        </label>
      </div>

    </div>

    <div
      class="absolute customers-shadow right-1 top-1 gap-1 flex items-center justify-center bg-white p-1 rounded-md opacity-0 transition-all duration-300 group-hover:opacity-100">
      <button class="default-xs h-5 w-5 rounded hover:bg-slate-200" @click="edit">
        <Icon name="fa6-solid:pencil" class="text-slate-600 text-xs" />
      </button>
      <button class="default-xs h-5 w-5 rounded hover:bg-slate-200" @click="deleteItem">
        <Icon name="fa6-solid:trash" class="text-slate-600 text-xs" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.error {
  color: red;
  /* Altres estils per als errors */
}
</style>
