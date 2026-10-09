<script setup>
import { ref, onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import { useToast } from 'vue-toastification';
import GroupPermissionsEdit from './GroupPermissionsEdit.vue';
import GroupUsersEdit from './GroupUsersEdit.vue';

const props = defineProps({
  id: String,
});

const { t } = useI18n();
const { $GroupApiService, $ConfiglistApiService } = useNuxtApp();

const toast = useToast();

const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);

const name = ref(null);
const users = ref([])
const permissions = ref([])

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const mainPermissions = ref([]);

const showDetailComponent = ref(null);
const showDetailId = ref(null);

const savePermissionData = ref(null)

/* const permissionDisplayData = computed(() => {
  let permissionTypes = [];

  mainPermissions.value.forEach(type => {
    if (!type.is_default) {
      permissionTypes.push({
        label: type.name,
        viewKey: type.view_key,
        changeKey: type.change_key
      });
    }
  });

  let data = permissionTypes.map(type => ({
    ...type,
    hasView: permissions.value[type.viewKey] || false,
    hasChange: permissions.value[type.changeKey] || false,
    hasAny: permissions.value[type.viewKey] || permissions.value[type.changeKey] || false
  }))
  savePermissionData.value = data;
  return data;
}); */

const getPermissionText = (hasView, hasChange) => {
  if (hasView && hasChange) return `${t('common.check')}, ${t('common.modification')}`;
  if (hasView) return t('common.check');
  if (hasChange) return t('common.modification');
  return t('user_group.no_permissions');
};

const getMainPermissions = async () => {
  try {
    const response = await $ConfiglistApiService.getAll('coredata/main-permission');
    mainPermissions.value = response.results;
  } catch (error) {
    console.error(error);
  }
}

const getData = async () => {
  loading.value = true;

  if (props.id) {
    const response = await $GroupApiService.getDetail(props.id);
    name.value = response.name;
    permissions.value = response.permissions;
    users.value = response.users;
  }
  else {
    name.value = null;
    permissions.value = [];
    users.value = [];
  }
  setPermissionData();
  //getUsers();
  loading.value = false;
}

const setPermissionData = () => {
  let permissionTypes = [];

  mainPermissions.value.forEach(type => {
    if (!type.is_default) {
      permissionTypes.push({
        label: type.name,
        viewKey: type.view_key,
        changeKey: type.change_key
      });
    }
  });

  let data = permissionTypes.map(type => ({
    ...type,
    hasView: permissions.value[type.viewKey] || false,
    hasChange: permissions.value[type.changeKey] || false,
    hasAny: permissions.value[type.viewKey] || permissions.value[type.changeKey] || false
  }))
  savePermissionData.value = data;
}

const updatePermissions = async (permissions) => {
  savePermissionData.value = permissions;
  await toggleRegion(false);
}

const updateUsers = async (datausers, removeusers) => {
  users.value = datausers;
  removeusers.forEach(user => {
    users.value = users.value.filter(u => u.id !== user.id);
  });
  await toggleRegion(false);
}

const save = async () => {
  attemptedSave.value = true;
  if (!isValid()) return;
  if (savePermissionData.value.every(permission => !permission.hasAny)) {
    toast.warning(t('warning_block.save_permissions_warning'));
    return;
  }
  if (users.value.length == 0) {
    if (!confirm(t('confirmation_text_block.confirm_no_users'))) return;
  }

  saving.value = true;
  try {
    let save_data = {
      id: props.id,
      name: name.value,
      permissions_data: savePermissionData.value,
      user_ids: users.value.map(user => user.id)
    }
    const response = await $GroupApiService.save(save_data);
    if (response) {
      toast.success(t('common.correct_save'));
      return navigateTo('/user/groups/')
    } else {
      toast.error(t('common.error_save'));
    }
  } catch (error) {
    console.error(error);
  } finally {
    saving.value = false;
  }
}

const deleteItem = async () => {
  if (confirm(t('warning_block.delete_group_warning'))) {
    saving.value = true;
    try {
      await $GroupApiService.deleteItem(props.id);
      return navigateTo('/user/groups/')
    } catch (error) {
      console.error(error);
    } finally {
      saving.value = false;
    }
  }
}

const isValid = () => {
  return name.value != null && name.value != '';
}

onMounted(async () => {
  await getMainPermissions();
  await getData()
});

const showDetail = async (component, id) => {
  await toggleRegion(false);
  showDetailComponent.value = component;
  showDetailId.value = id;
  toggleRegion(true);
}

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
    showDetailComponent.value = null;
    showDetailId.value = null;
  }
}

const handleSubRegionEvent = (value) => {
  isSubRegionOpen.value = value;
}

</script>

<template>
  <div class="wrapper text-base max-w-full">

    <div v-if="loading">
      <div class="rounded p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else class="rounded p-4 bg-white">

      <div class="row grid grid-cols-2 gap-3 my-3">
        <div class="grid grid-rows-[auto,1fr]">
          <div>
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
            <input type="text" v-model="name" class="input"
              :class="{ 'invalid': attemptedSave && (name == null || name == '') }" />
          </div>
          <div class="mt-3 grid grid-rows-[auto,1fr]">
            <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('users') }}</label>
            <div class="relative group">
              <button @click="showDetail('GroupUsersEdit', null)"
                class="absolute top-1 right-1 w-7 h-7 border border-slate-300 rounded-md bg-white hover:bg-slate-300 group-hover:opacity-100 opacity-0 transition-all duration-300">
                <Icon name="fa6-solid:pencil" class="text-slate-500" />
              </button>
              <div class="border border-slate-300 rounded-md p-2 gap-3 h-full items-start">
                <div v-if="users.length == 0" class="flex items-center gap-2 my-1">
                  <Icon name="fa6-solid:ban" class="text-slate-500" />
                  <span class="text-sm font-medium text-slate-500">{{ t('user_group.no_users') }}</span>
                </div>
                <div v-else class="space-y-2">
                  <div v-for="user in users" :key="user.id" class="flex items-center grid grid-cols-[20px,1fr,1fr,1fr] gap-2 text-xs font-medium text-slate-500">
                    <Icon name="fa6-solid:circle-user" class="text-slate-500" />
                    <span class="text-base text-slate-800">{{ user.username }}</span>
                    <span>{{ user.email? user.email : t('common.no_email') }}</span>
                    <span v-if="user.group_name != name">{{ user.group_name? user.group_name : t('user_group.no_group') }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('permissions') }}</label>
          <div class="relative group">
            <button @click="showDetail('GroupPermissionsEdit', null)"
              class="absolute top-1 right-1 w-7 h-7 border border-slate-400 rounded-md bg-white hover:bg-slate-300 group-hover:opacity-100 opacity-0 transition-all duration-300">
              <Icon name="fa6-solid:pencil" class="text-slate-500" />
            </button>
            <div class="border border-slate-200 rounded-lg p-3 max-h-[55vh] overflow-y-auto">
              <div v-for="permission in savePermissionData" :key="permission.key"
                class="flex items-center justify-between py-2 px-3 bg-white rounded-md border-b border-slate-200 mb-2 last:mb-0 last:border-none">
                <div class="flex items-center gap-3">
                  <div class="w-2 h-2 rounded-full" :class="permission.hasAny ? 'bg-emerald-500' : 'bg-slate-300'">
                  </div>
                  <span class="text-sm font-semibold text-slate-700 truncate">{{ t(permission.label) }}</span>
                </div>
                <div class="flex items-center gap-2 ml-4">
                  <Icon :name="permission.hasAny ? 'fa6-solid:check' : 'fa6-solid:xmark'"
                    :class="permission.hasAny ? 'text-emerald-500' : 'text-slate-400'" class="text-sm" />
                  <span class="text-xs font-medium text-slate-600 min-w-0">{{ getPermissionText(permission.hasView,
                    permission.hasChange) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

      </div>


      <hr class="mb-2 col-span-2" />
      <div class="col-span-2 flex flex-row-reverse gap-3 mt-4">
        <button v-if="id != null" @click="deleteItem" :disabled="saving" class="button-default">
          <Icon name="fa6-solid:trash" />&nbsp;{{ $t('common.delete') }}
        </button>
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="saving ? 'animate-spin' : ''" />&nbsp;{{ $t('common.save') }}
        </button>
      </div>
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">
        <GroupPermissionsEdit v-if="showDetailComponent == 'GroupPermissionsEdit'" :group_name="name" :group_id="id"
          :permissions="savePermissionData" :mainPermissions="mainPermissions" @save="updatePermissions" />
        <GroupUsersEdit v-if="showDetailComponent == 'GroupUsersEdit'" :users="users" :group_name="name" :group_id="id"
          @show-subregion="handleSubRegionEvent" @save="updateUsers" />
      </div>
    </div>
  </div>
</template>
