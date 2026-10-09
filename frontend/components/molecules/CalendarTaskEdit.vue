<script setup>
import { useI18n } from 'vue-i18n';
import H1Region from '~/components/atoms/H1Region.vue';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import { formatDate } from '~/utils/date';
import Date from '~/components/atoms/Date.vue';
import ButtonOutline from '../atoms/ButtonOutline.vue';

const { $CalendarTaskApiService, $UserApiService } = useNuxtApp();
const { t } = useI18n();

const props = defineProps({
  current_date: String,
  id: {
    type: Number,
    required: false
  },
  object_id: {
    type: Number,
    required: false
  },
  object_service: {
    type: Object,
    required: false
  }
});

const emit = defineEmits(['change']);

const isLoading = ref(false);
const attemptedSave = ref(false);
const error = ref(null);

const name = ref('');
const description = ref('');
const color = ref('');
//const user = ref('');
const all_users = ref(true);

const selectedUser = ref(null);
const users = ref([]);

const selectedDate = ref(props.current_date? props.current_date : null);

const getUsers = async () => {
  const response = await $UserApiService.getAll();
  users.value = response.results.map(user => ({
    label: user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : user.username,
    code: user.id,
    username: user.username
  }));
};

// Per defecte, una tasca privada s'assigna a l'usuari que la crea
const selectCurrentUser = () => {
  let currentUsername = null;
  try {
    currentUsername = localStorage.getItem('user_username');
  } catch (e) { /* sense accés a localStorage */ }
  const me = users.value.find(user => user.username === currentUsername);
  if (me) selectedUser.value = me;
};

const setVisibility = (showToAll) => {
  all_users.value = showToAll;
  if (!showToAll && !selectedUser.value) selectCurrentUser();
};

const fetchData = async () => {
  isLoading.value = true;
  try {
    const detail = await $CalendarTaskApiService.getDetail(props.id);
    name.value = detail.name;
    description.value = detail.description;
    all_users.value = detail.user == null;
    selectedUser.value = detail.user
      ? { code: detail.user.id, label: detail.user.username }
      : null;
    selectedDate.value = detail.set_date;
  } catch (err) {
    console.error('Error obtenint les dades:', err);
    error.value = err;
  } finally {
    isLoading.value = false;
  }
};


const handleDescriptionTextareaUpdate = (value) => {
  description.value = value;
};

const updateSelect = (event, entity) => {
  switch (entity) {
    case 'user':
      selectedUser.value = event;
      break;
  }
}

const save = async () => {

  attemptedSave.value = true;
  if (!isValid()) return

  let data = {
    id: props.id,
    name: name.value,
    description: description.value,
    set_date: selectedDate.value,
    all_users: all_users.value,
    user_id: all_users.value ? null : (selectedUser.value ? selectedUser.value.code : null),
  };

  let response = await $CalendarTaskApiService.save(data);
  if (response){
    if (props.object_id && props.object_service) {
      let object_save = {
        id: props.object_id,
        new_task: response.id
      }
      await props.object_service.save(object_save);
    }
    emit('change')
  }

};

const isValid = () => {
  if (name.value == '') return false;
  if (!all_users.value && !selectedUser.value) return false;
  /* if (description.value == '') return false; */
  return true;
}

onMounted(() => {
  getUsers();
  if (props.id) fetchData();
});

watch(() => props.id, (newId, oldId) => {
  if (newId && newId !== oldId) {
    fetchData();
  }
  if (newId == null) {
    name.value = '';
    description.value = '';
    all_users.value = true;
    selectedUser.value = null;
  }
});

const handleColorChanged = () => {
  emit('change', false);
}


</script>

<template>
  <div v-if="isLoading" class="flex justify-center items-center h-48">
    <span class="text-lg text-gray-600">{{ $t("common.loading") }}...</span>
  </div>

  <div v-else-if="error" class="flex justify-center items-center h-48 bg-red-100 rounded-md p-4">
    <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again') }}</button>
  </div>

  <div v-else class="w-[90%]">
    <div class="flex justify-between relative">
      <H1Region class="mb-3">
        {{ id ? $t('dashboard.edit_task') : $t('dashboard.new_task') }}
        <span v-if="current_date" class="text-slate-500 text-sm ml-3">
          {{ formatDate(current_date) }}
        </span>
      </H1Region>
    </div>

    <!-- <div class="mt-2"> -->
    <div class="mt-2 row grid grid-cols-[1fr,auto] gap-3">
      <div class="col-span-2">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('dashboard.task_visibility') }}</label>
        <div class="flex flex-wrap gap-x-6 gap-y-2">
          <label class="flex items-center text-sm text-slate-700 cursor-pointer">
            <input type="radio" name="task_visibility" :checked="all_users" class="mr-2" @change="setVisibility(true)" />
            {{ t('dashboard.show_all') }}
          </label>
          <label class="flex items-center text-sm text-slate-700 cursor-pointer">
            <input type="radio" name="task_visibility" :checked="!all_users" class="mr-2" @change="setVisibility(false)" />
            {{ t('dashboard.show_only_assigned') }}
          </label>
        </div>
        <p class="text-xs text-slate-400 mt-1">
          {{ all_users ? t('dashboard.show_all_info') : t('dashboard.show_only_assigned_info') }}
        </p>
      </div>
      <div v-if="!props.current_date" class="my-2 col-span-2 w-[60%]">
        <AtomsInputDate v-model="selectedDate" :label="t('common.date')" class="mb-2" :required="true" />
      </div>
      <div v-if="!all_users" class="mb-4 col-span-2 w-[60%]">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('dashboard.assigned_user') }}</label>
        <v-select class="block w-full" :class="{ 'invalid': attemptedSave && !selectedUser }" :model-value="selectedUser"
          @update:modelValue="updateSelect($event, 'user')" :options="users" />
      </div>
      <div class="mb-4 w-[60%]">
        <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.title') }}</label>
        <input type="text" v-model="name" class="input"
          :class="{ 'invalid': attemptedSave && name == '' || attemptedSave && name == null }" />
      </div>
      <span v-if="id" class="text-slate-900 p-1 my-auto">
        <AtomsColorPicker :entity="'notification/calendar-task'" :id="id" :code="color" @changed="handleColorChanged" />
      </span>
    </div>
    <div>
      <div class="mb-4">
        <AtomsInputTextarea :autosave="false" @update:text="handleDescriptionTextareaUpdate" :text="description"
          :placeholder="'dashboard.desc_task'" />
      </div>

    </div>

    <div class="col-span-3 flex flex-row-reverse mt-4">
      <button @click="save" class="button-primary">
        <Icon name="fa6-solid:floppy-disk" />&nbsp; {{ t('common.save') }}
      </button>
    </div>

  </div>
</template>

<style scoped>
.error {
  color: red;
}
</style>
