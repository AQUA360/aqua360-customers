<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import { useToast } from 'vue-toastification';
import { usePermissions } from '~/middleware/permission';
import AppLoading from '~/components/atoms/AppLoading.vue';
import { CANONICAL_SUPERUSER_USERNAME, getUserRole } from '~/utils/roles';

const props = defineProps({
  id: String,
});

const { t } = useI18n();
const { $UserApiService, $GroupApiService, $ConfiglistApiService } = useNuxtApp();
const { permissions, loading : pending } = usePermissions();
const toast = useToast();

const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);

const username = ref(null);
const firstName = ref("");
const lastName = ref("");
const email = ref(null);
const password = ref(null);
const repeatPassword = ref(null);
const userRole = ref('none'); // superuser | admin | none
const groups = ref([]);
const selectedGroupId = ref(null);

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const showDetailComponent = ref(null);
const showDetailId = ref(null);

const canManageUsers = computed(() => Boolean(permissions?.value?.permissions?.change_user));
const isCustomersAccount = computed(() => username.value === CANONICAL_SUPERUSER_USERNAME);
const canSelectSuperuser = computed(() => isCustomersAccount.value);
const groupSelectDisabled = computed(() => {
  return !canManageUsers.value || userRole.value === 'superuser' || userRole.value === 'admin';
});

const getGroups = async () => {
  try {
    const response = await $GroupApiService.getAll();
    groups.value = response.results || [];
  } catch (error) {
    console.error(error);
  }
}

const getData = async () => {
  loading.value = true;
  try {
    await getGroups();

    if (props.id) {
      const response = await $UserApiService.getDetail(props.id);
      username.value = response.username;
      firstName.value = response.first_name;
      lastName.value = response.last_name;
      email.value = response.email;
      userRole.value = getUserRole(response);
      selectedGroupId.value = response.group_id || null;
    }
    else {
      username.value = null;
      firstName.value = null;
      lastName.value = null;
      email.value = null;
      userRole.value = 'none';
      selectedGroupId.value = null;
    }
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
}

const save = async () => {
  attemptedSave.value = true;
  if (!isValid()) return;

  if (!canManageUsers.value) {
    toast.error(t('common.no_permissions'));
    return;
  }

  if (userRole.value === 'superuser' && !isCustomersAccount.value) {
    toast.error(t('user_group.only_customers_superuser'));
    return;
  }

  if (props.id) {
    if (password.value != null && password.value != '') {
      if(!confirm(t('confirmation_text_block.confirm_change_password'))) return;
    }
  } else {
    if (password.value == null || password.value == '') {
      if(!confirm(t('confirmation_text_block.confirm_create_user_no_password'))) return;
    }
  }

  saving.value = true;
  try {
    let save_data = {
      id: props.id,
      username: username.value,
      first_name: firstName.value || '',
      last_name: lastName.value || '',
      email: email.value,
      role: userRole.value,
      group_id: userRole.value === 'none' ? selectedGroupId.value : null,
    }

    if (password.value != null && password.value != '') {
      save_data.new_pwd = password.value;
    } else if (!props.id) {
      save_data.new_pwd = '';
    }
    
    const response = await $UserApiService.save(save_data);
    if (response) {
      toast.success(t('common.correct_save'));
      return navigateTo('/user/users/')
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
  if (confirm(t('warning_block.delete_user_warning'))) {
    saving.value = true;
    try {
      await $UserApiService.deleteItem(props.id);
      return navigateTo('/user/users/')
    } catch (error) {
      console.error(error);
    } finally {
      saving.value = false;
    }
  }
}

const isValid = () => {
  if (password.value != null && password.value != ''){
    if (password.value != repeatPassword.value){
      toast.warning(t('user_group.password_not_match'));
      return false;
    }
  }
  return username.value != null && username.value != '' && email.value != null && email.value != '';
}

watch(userRole, (newValue) => {
  if (newValue === 'superuser' || newValue === 'admin') {
    selectedGroupId.value = null;
  }
});

watch(username, (newValue) => {
  if (newValue !== CANONICAL_SUPERUSER_USERNAME && userRole.value === 'superuser') {
    userRole.value = 'admin';
  }
});

onMounted(async () => {
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
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="rounded p-4 bg-white">

      <div class="row grid grid-cols-2 gap-3 my-3 items-center">
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.username') }}</label>
          <input type="text" v-model="username" class="input" :placeholder="CANONICAL_SUPERUSER_USERNAME"
            :disabled="!canManageUsers"
            :class="{ 'invalid': attemptedSave && (username == null || username == ''), 'opacity-50 cursor-not-allowed': !canManageUsers }" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('user_group.role') }}</label>
          <div class="flex flex-col gap-2 ml-1" :class="{ 'opacity-50': !canManageUsers }">
            <label class="flex items-center gap-x-2 text-slate-700"
              :class="(canManageUsers && canSelectSuperuser) ? 'cursor-pointer' : 'cursor-not-allowed'">
              <input v-model="userRole" value="superuser"
                :disabled="!canManageUsers || !canSelectSuperuser" type="radio" name="userRole" />
              {{ t('common.superuser') }}
              <abbr :title="t('user_group.superuser_permissions')" class="flex items-center">
                <Icon name="fa6-solid:circle-info" class="text-slate-500" />
              </abbr>
            </label>
            <label class="flex items-center gap-x-2 text-slate-700" :class="canManageUsers ? 'cursor-pointer' : 'cursor-not-allowed'">
              <input v-model="userRole" value="admin" :disabled="!canManageUsers || isCustomersAccount" type="radio" name="userRole" />
              {{ t('common.admin') }}
              <abbr :title="t('user_group.admin_permissions')" class="flex items-center">
                <Icon name="fa6-solid:circle-info" class="text-slate-500" />
              </abbr>
            </label>
            <label class="flex items-center gap-x-2 text-slate-700" :class="canManageUsers ? 'cursor-pointer' : 'cursor-not-allowed'">
              <input v-model="userRole" value="none" :disabled="!canManageUsers || isCustomersAccount" type="radio" name="userRole" />
              {{ t('user_group.role_none') }}
              <abbr :title="t('user_group.role_none_permissions')" class="flex items-center">
                <Icon name="fa6-solid:circle-info" class="text-slate-500" />
              </abbr>
            </label>
          </div>
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
          <input type="text" v-model="firstName" class="input" :disabled="!canManageUsers" :class="{ 'opacity-50 cursor-not-allowed': !canManageUsers }" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.surname') }}</label>
          <input type="text" v-model="lastName" class="input" :disabled="!canManageUsers" :class="{ 'opacity-50 cursor-not-allowed': !canManageUsers }" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.email_long') }}</label>
          <input type="text" v-model="email" class="input" :placeholder="'customers@customers.com'"
            :disabled="!canManageUsers"
            :class="{ 'invalid': attemptedSave && (email == null || email == ''), 'opacity-50 cursor-not-allowed': !canManageUsers }" />
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('group') }}</label>
          <select v-model="selectedGroupId" :disabled="groupSelectDisabled" class="input"
            :class="{ 'opacity-50 cursor-not-allowed': groupSelectDisabled }">
            <option :value="null">{{ t('None') }}</option>
            <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ props.id? 
          `${t('common.change')} ${t('common.password')}` : t('common.password') }}</label>
          <input type="password" v-model="password" class="input" :disabled="!canManageUsers" :class="{ 'opacity-50 cursor-not-allowed': !canManageUsers }"/>
        </div>
        <div>
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('user_group.repeat_password') }}</label>
          <input type="password" v-model="repeatPassword" class="input" :disabled="!canManageUsers" :class="{ 'opacity-50 cursor-not-allowed': !canManageUsers }"/>
        </div>
      </div>


      <hr class="mb-2 col-span-2" />
      <div v-if="canManageUsers" class="col-span-2 flex flex-row-reverse gap-3 mt-4">
        <button v-if="id != null" @click="deleteItem" :disabled="saving" class="button-default">
          <Icon name="fa6-solid:trash" />&nbsp;{{ $t('common.delete') }}
        </button>
        <button @click="save" :disabled="saving" class="button-primary">
          <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="saving ? 'animate-spin' : ''" />
          &nbsp;{{ $t('common.save') }}
        </button>
      </div>
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-full': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">

      </div>
    </div>
  </div>
</template>
