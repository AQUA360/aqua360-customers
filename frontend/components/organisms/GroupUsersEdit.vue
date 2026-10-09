<script setup>
import { ref, onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import { useToast } from 'vue-toastification';
import H1Region from '../atoms/H1Region.vue';
import Pagination from '../molecules/Pagination.vue';

const props = defineProps({
  users: Array,
  group_name: String,
  group_id: String,
});

const { t } = useI18n();
const emit = defineEmits(['save', 'show-subregion']);
const { $ConfiglistApiService, $UserApiService } = useNuxtApp();

const toast = useToast();
const localUsers = ref([]);
const loading = ref(true);
const error = ref(null);
const loadedUsers = ref([]);
const selectedUsers = ref([]);
const saveUsers = ref([]);
const removeUsers = ref([]);

const showAllUsers = ref(false)
const SubRegion = ref(false);

const pagination = ref({
  page: 1,
  perPage: 50,
  total: 0,
  totalPages: 0,
  previous: null,
  next: null,
  isFiltered: false
});

const save = async () => {
  emit('save', saveUsers.value, removeUsers.value);
}

const getData = async (page = 1, show_all_users = false) => {
  localUsers.value = props.users;
  try {
    let groups = show_all_users ? [] : [props.group_id];
    const data = await $UserApiService.getAll('', page, [], groups, true);
    loadedUsers.value = data.results;

    Object.assign(pagination.value, {
      total: data.count,
      totalPages: Math.ceil(data.count / pagination.value.perPage),
      previous: data.previous,
      next: data.next,
      isFiltered: false
    });

    checkSelectedUsers();

  } catch (error) {
    error.value = error;
  } finally {
    loading.value = false;
  }
}

const checkSelectedUsers = () => {
  const existingSaveUserIds = saveUsers.value.map(u => u.id);
  const newSaveUsers = localUsers.value.filter(user => 
    !existingSaveUserIds.includes(user.id)
  );
  saveUsers.value = [
    ...saveUsers.value,
    ...newSaveUsers
  ];

  const currentPageSelectedUsers = loadedUsers.value.filter(user => 
    localUsers.value.map(u => u.id).includes(user.id) && user.group_name != props.group_name && !user.group_id
  );
  
  const existingSelectedUserIds = selectedUsers.value.map(u => u.id);
  const newSelectedUsers = currentPageSelectedUsers.filter(user => 
    !existingSelectedUserIds.includes(user.id)
  );
  
  selectedUsers.value = [
    ...selectedUsers.value,
    ...newSelectedUsers
  ];
}

const handlePageChange = (newPage) => {
  pagination.value.page = newPage;
  getData(newPage);
}

const handleShowAllUsers = () => {
  pagination.value.page = 1;
  getData(1, showAllUsers.value);
}

const selectUser = (user) => {
  console.log(user?.group_id)
  if (localUsers.value.map(u => u.id).includes(user.id) && user.group_name && user.group_id == props.group_id) {
    toast.warning(t('warning_block.warning_user_in_group'));
    return;
  }

  if (selectedUsers.value.map(u => u.id).includes(user.id)) {
    selectedUsers.value = selectedUsers.value.filter(u => u.id !== user.id);
    saveUsers.value = saveUsers.value.filter(u => u.id !== user.id);
  } else {
    if (user.group_id && user.group_id != props.group_id) {
      if (!confirm(t('confirmation_text_block.confirm_user_in_group'))) return;
    }
    selectedUsers.value.push(user);
    saveUsers.value.push(user);
  }
}

const removeUser = (user) => {
  if (removeUsers.value.map(u => u.id).includes(user.id)) {
    removeUsers.value = removeUsers.value.filter(u => u.id !== user.id);
  } else {
    if(!confirm(t('confirmation_text_block.confirm_remove_user'))) return;
    if (selectedUsers.value.map(u => u.id).includes(user.id)) {
      selectedUsers.value = selectedUsers.value.filter(u => u.id !== user.id);
      saveUsers.value = saveUsers.value.filter(u => u.id !== user.id);
    }
    removeUsers.value.push(user);
  }
}

const checkUsers = () => {
  SubRegion.value = true;
  emit('show-subregion', true);
}

const closeSubRegion = () => {
  SubRegion.value = false;
  emit('show-subregion', false);
}

onMounted(async () => {
  getData()
});

watch(() => props.users, (newVal) => {
  getData()
}, { deep: true });

watch(() => showAllUsers.value, (newVal) => {
  handleShowAllUsers()
});

</script>

<template>
  <div class="region__content">
    <div class="transition-all duration-500 ease" :class="{ 'mr-[48vw]': SubRegion }">
      <div class="flex items-center justify-between gap-2 mb-3">
        <H1Region>{{ $t('users') }}</H1Region>
        <AtomsColorBadge :color="'blue'" :value="group_name" />
      </div>

      <div class="space-y-1.5 mt-3 flex justify-between">
        <!-- <button @click="checkUsers" class="button-default" :disabled="localUsers.length == 0">
          <Icon name="fa6-solid:users" />&nbsp;{{ $t('Consultar usuaris del grup') }}
        </button> -->

        <div>
          <span>
            {{ t('user_group.selected_users') }}: {{ selectedUsers.length }}
          </span>
        </div>

        <label class="inline-flex items-center">
          <input type="checkbox" v-model="showAllUsers"
            class="form-checkbox h-4 w-4 text-sky-600 rounded border-gray-300 focus:ring-sky-500 mb-2" />
          <div class="ml-2">
            <p class="text-sm text-gray-700">{{ t('user_group.show_all_users') }}</p>
            <p class="text-xs text-gray-500 italic">{{ t('user_group.no_superuser') }}</p>
          </div>
        </label>
      </div>

      <div id="list" :style="{
        overflowY: 'auto',
        width: 'calc(100vw)',
        maxWidth: '100%',
        minHeight: 'calc(100vh - 300px)',
        maxHeight: 'calc(100vh - 300px)',
      }">
        <div v-if="loading">
          <p>{{ $t('common.loading') }}...</p>
        </div>
        <div v-else-if="error">
          <p>Error: {{ error.message }}</p>
          <p><button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
              }}</button></p>
        </div>
        <div v-else-if="loadedUsers.length > 0">
          <div v-for="user in loadedUsers" :key="user.id">
            <div class="flex items-center grid grid-cols-[20px,1fr] gap-2 transition-all duration-300 ease rounded-md" 
            :class="{ 
              'bg-sky-50 pl-3': selectedUsers.map(u => u.id).includes(user.id),
              'bg-red-50': removeUsers.map(u => u.id).includes(user.id)
            }">
              <button :disabled="!(localUsers.map(u => u.id).includes(user.id) && user.group_id == props.group_id)"
                @click="removeUser(user)"
                class="w-5 h-5 rounded-full hover:bg-red-500 ml-3 hover:text-white text-red-500 flex items-center justify-center disabled:opacity-0 disabled:cursor-default">
                <Icon name="fa6-solid:trash" class="" />
              </button>
              <button class="w-full text-start" @click="selectUser(user)">
                <AtomsUserBadge :user="user" />
              </button>
            </div>
          </div>
        </div>

      </div>
      <div id="list__footer">
        <Pagination v-if="loadedUsers.length > 0" :pagination="pagination" @update:page="handlePageChange" />
      </div>

      <div class="my-2 px-3 py-1 border border-sky-500 bg-sky-50 rounded text-sky-500">
        {{ t('user_group.info_group_users') }}
      </div>

      <hr class="mb-2" />
      <div class="flex flex-row-reverse gap-3 mt-4">
        <button @click="save" class="button-primary">
          <Icon name="fa6-solid:floppy-disk" />&nbsp;{{ $t('common.save') }}
        </button>
      </div>
    </div>
    <div v-if="SubRegion" role="region" id="subregion"
      class="h-full border-l border-gray-100 transition-all duration-500 ease py-2 text-base bg-white flex flex-col fixed top-0 right-0 w-[48vw] z-50"
      :class="{ 'translate-x-0': SubRegion, 'translate-x-full': !SubRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="closeSubRegion()" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="pl-10 flex-1 overflow-y-auto scrollbar-hide">
        <MoleculesGroupUsersRegion :users="users" :group_name="group_name" />
      </div>
    </div>
  </div>


</template>
