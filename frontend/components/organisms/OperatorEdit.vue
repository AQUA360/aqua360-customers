<script setup>
import { toRaw, ref, onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';

import _ from 'lodash';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';

const props = defineProps({
  id: Number,
});

const { t } = useI18n();
const { $OperatorApiService } = useNuxtApp();

const attemptedSave = ref(false);
const loading = ref(true);
const saving = ref(false);
const usernameError = ref(''); // Backend error for duplicate username

const showForm = ref(false);
const passwordValid = ref(false);
const passwordConfirmValid = ref(false);
const changePassword = ref(false); // Checkbox for password change
const new_app_user = ref({
  username: '',
  name: '',
  surname: '',
  password: '',
  password_confirm: '',
});

const item = ref(null);
const token = ref(null);
const name = ref(null);
const surname = ref(null);
const phone = ref(null);
const email = ref(null);

// Computed to check if operator token starts with GMAO_
const isGmaoOperator = computed(() => {
  return token.value && token.value.startsWith('GMAO_');
});

const showRegion = ref(false);
const isSubRegionOpen = ref(false);

const getData = async () => {
  loading.value = true;

  if (props.id) {
    item.value = await $OperatorApiService.getDetail(props.id);
    name.value = item.value.name;
    surname.value = item.value.surname;
    token.value = item.value.token;
    phone.value = item.value.phone;
    email.value = item.value.email;
    
    // If app_user exists, load it into the form for editing
    if (item.value.app_user) {
      new_app_user.value = {
        username: item.value.app_user.username || '',
        name: item.value.app_user.name || '',
        surname: item.value.app_user.surname || '',
        password: '',
        password_confirm: '',
      };
      showForm.value = true; // Show form with existing data
      changePassword.value = false; // Don't change password by default
    }
  } else {
    item.value = {};
  }

  loading.value = false;
}

const save = async () => {
  attemptedSave.value = true;
  usernameError.value = ''; // Clear previous errors
  try {
    if (isValid()) {
      saving.value = true;
  
      const selectedOptions = {
        id: props.id,
        token: token.value,
        name: name.value,
        surname: surname.value,
        phone: phone.value,
        email: email.value
      };
  
      if (showForm.value) {
        // Build app_user object
        const appUserData = {
          username: new_app_user.value.username,
          name: new_app_user.value.name,
          surname: new_app_user.value.surname,
        };
        
        // Only include password if checkbox is checked (for new or updating)
        if (changePassword.value) {
          appUserData.password = new_app_user.value.password;
          appUserData.password_confirm = new_app_user.value.password_confirm;
        }
        
        selectedOptions.app_user = appUserData;
      }
  
      item.value = await $OperatorApiService.save(selectedOptions);
      return navigateTo('/order/operators/')
    }
    else {
      saving.value = false;
    }
  } catch (error) {
    
    // Check for username duplicate error in different possible locations
    let usernameErrors = null;
    
    // $fetch wraps errors in a data property
    if (error.data?.app_user?.username) {
      usernameErrors = error.data.app_user.username;
    }
    
    if (usernameErrors) {
      if (Array.isArray(usernameErrors)) {
        usernameError.value = usernameErrors[0];
      } else {
        usernameError.value = usernameErrors;
      }
    }
    
    saving.value = false;
  } finally {
    if (saving.value) {
      saving.value = false;
    }
  }
}

const deleteItem = async () => {
  if (confirm(t('confirmation_text_block.confirm_delete'))) {
    saving.value = true;
    await $OperatorApiService.deleteItem(props.id);
    return navigateTo('/order/operators/')
  }
}

const isValid = () => {
  if (name.value == '' || name.value == null) return false;
  if (surname.value == '' || name.value == null) return false;
  if (token.value == '' || token.value == null) return false;
  
  // Validate app_user fields if form is shown
  if (showForm.value) {
    if (!new_app_user.value.username || new_app_user.value.username.trim() === '') return false;
    if (!new_app_user.value.name || new_app_user.value.name.trim() === '') return false;
    if (!new_app_user.value.surname || new_app_user.value.surname.trim() === '') return false;
    
    // Only validate password if changing password OR creating new user
    if (changePassword.value || !item.value.app_user) {
      if (new_app_user.value.password.length < 6) return false;
      if (new_app_user.value.password !== new_app_user.value.password_confirm) return false;
    }
  }
  
  return true;
}

const handlePasswordValidation = (isValid) => {
  passwordValid.value = isValid;
}

const handlePasswordConfirmValidation = (isValid) => {
  passwordConfirmValid.value = isValid;
}

const newAppUser = () => {
  usernameError.value = ''; // Clear username error when creating new
  
  // If app_user already exists, just show the form (data already loaded in getData)
  if (item.value.app_user) {
    showForm.value = true;
    return;
  }
  
  // Only generate new data if creating a new app_user
  let generatedUsername = '';
  if (name.value && surname.value) {
    generatedUsername = `${name.value}_${surname.value}`.toLowerCase().replace(/\s+/g, '_');
  } else if (item.value.name && item.value.surname) {
    generatedUsername = `${item.value.name}_${item.value.surname}`.toLowerCase().replace(/\s+/g, '_');
  }

  new_app_user.value = {
    name: name.value || item.value.name || '',
    surname: surname.value || item.value.surname || '',
    username: generatedUsername,
    password: '',
    password_confirm: '',
  }
  
  showForm.value = true;
  changePassword.value = true; // Enable password fields for new user
}

const toggleForm = () => {
  showForm.value = !showForm.value;
  console.log(showForm.value)
}

// Watch for password checkbox changes - clear passwords when unchecked
watch(changePassword, (newValue) => {
  if (!newValue) {
    new_app_user.value.password = '';
    new_app_user.value.password_confirm = '';
  }
});

onMounted(() => {
  getData()
});

</script>

<template>
  <div class="wrapper text-base p-4 max-w-full">
    <div v-if="loading">
      <AppLoading :text="$t('common.loading')" />
    </div>
    <div v-else class="border border-gray-300 rounded p-4 bg-white">
      <!-- Info banner for GMAO operators -->
      <div v-if="isGmaoOperator" class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <div class="flex items-center gap-2 text-blue-700">
          <Icon name="fa6-solid:circle-info" />
          <span class="text-sm">{{ t('order_block.gmao_operator_readonly') }}</span>
        </div>
      </div>

      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.identificator') }}</label>
          <input type="text" v-model="token" class="input"
            :disabled="isGmaoOperator"
            :class="{ 'invalid': attemptedSave && (token == '' || attemptedSave && token == null), 'bg-gray-100 cursor-not-allowed': isGmaoOperator }" />
        </div>
      </div>

      <div class="row grid grid-cols-2 gap-3 ">

        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.name') }}</label>
          <input type="text" v-model="name" class="input"
            :disabled="isGmaoOperator"
            :class="{ 'invalid': attemptedSave && name == '' || attemptedSave && name == null, 'bg-gray-100 cursor-not-allowed': isGmaoOperator }" />
        </div>


        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.surname') }}</label>
          <input type="text" v-model="surname" class="input"
            :disabled="isGmaoOperator"
            :class="{ 'invalid': attemptedSave && surname == '' || attemptedSave && surname == null, 'bg-gray-100 cursor-not-allowed': isGmaoOperator }" />
        </div>
      </div>


      <div class="row grid grid-cols-2 gap-3 ">
        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.tlf') }}</label>
          <input type="text" v-model="phone" class="input"
            :disabled="isGmaoOperator"
            :class="{ 'invalid': attemptedSave && phone == '' || attemptedSave && phone == null, 'bg-gray-100 cursor-not-allowed': isGmaoOperator }" />
        </div>


        <div class="mb-4">
          <label class="block text-sm font-medium text-slate-500 mb-2">{{ t('common.email') }}</label>
          <input type="text" v-model="email" class="input" v-validate-email
            :disabled="isGmaoOperator"
            :class="{ 'invalid': attemptedSave && email == '' || attemptedSave && email == null, 'bg-gray-100 cursor-not-allowed': isGmaoOperator }" />
        </div>
      </div>


      <hr class="mb-2 col-span-2" />
      <span class="col-span-2 text-sm text-slate-500 flex items-center gap-3">
        {{ t('service_block.app_user') }}
        <AtomsLecturappHelpLink />
      </span>
      <div v-if="!showForm">
        <button class="button-primary my-2" @click="newAppUser">
          {{ item.app_user ? t('service_block.modify_app_user') : t('service_block.new_app_user') }}
        </button>
      </div>
      <div class="col-span-2 relative mt-2" v-if="showForm">

        <button class="rounded-full w-6 h-6  bg-slate-200 p-1 mb-2 absolute top-2 right-2" @click="toggleForm">
          <Icon name="fa6-solid:xmark" />
        </button>

        <div class="col-span-2 grid grid-cols-2 gap-3 rounded-lg border border-gray-300 p-4 bg-slate-50">
          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">
              {{ t('common.name') }} <span class="text-red-500">*</span>
            </label>
            <input type="text" v-model="new_app_user.name" class="input"
              :class="{ 'invalid': attemptedSave && (!new_app_user.name || new_app_user.name.trim() === '') }" />
          </div>

          <div class="mb-4">
            <label class="block text-sm font-medium text-slate-500 mb-2">
              {{ t('common.surname') }} <span class="text-red-500">*</span>
            </label>
            <input type="text" v-model="new_app_user.surname" class="input"
              :class="{ 'invalid': attemptedSave && (!new_app_user.surname || new_app_user.surname.trim() === '') }" />
          </div>

          <div class="mb-4 col-span-2">
            <label class="block text-sm font-medium text-slate-500 mb-2">
              {{ t('common.username') }} <span class="text-red-500">*</span>
            </label>
            <input type="text" v-model="new_app_user.username" class="input"
              :class="{ 'invalid': (attemptedSave && (!new_app_user.username || new_app_user.username.trim() === '')) || usernameError }" />
            <p v-if="usernameError" class="mt-1 text-sm text-red-600">
              {{ usernameError }}
            </p>
          </div>

          <!-- Password change checkbox (only for editing existing user) -->
          <div v-if="item.app_user" class="col-span-2 mb-4">
            <label class="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" v-model="changePassword" class="w-4 h-4 text-sky-600 border-gray-300 rounded focus:ring-sky-500" />
              <span class="text-sm font-medium text-slate-700">
                {{ t('user_group.change_password') }}
              </span>
            </label>
          </div>

          <!-- Password fields (shown if: creating new user OR checkbox is checked) -->
          <template v-if="!item.app_user || changePassword">
            <div class="mb-4">
              <label class="block text-sm font-medium text-slate-500 mb-2">
                {{ t('common.password') }} <span class="text-red-500">*</span>
              </label>
              <input type="password" v-model="new_app_user.password" class="input"
                :class="{ 'invalid': attemptedSave && (changePassword || !item.app_user) && new_app_user.password.length < 6 }" />
              <p v-if="attemptedSave && (changePassword || !item.app_user) && new_app_user.password.length < 6" class="mt-1 text-sm text-red-600">
                {{ t('common.min_length_error', { min: 6 }) }}
              </p>
            </div>

            <div class="mb-4">
              <label class="block text-sm font-medium text-slate-500 mb-2">
                {{ t('user_group.repeat_password') }} <span class="text-red-500">*</span>
              </label>
              <input type="password" v-model="new_app_user.password_confirm" class="input"
                :class="{ 'invalid': attemptedSave && (changePassword || !item.app_user) && (new_app_user.password_confirm.length < 6 || new_app_user.password !== new_app_user.password_confirm) }" />
              <p v-if="attemptedSave && (changePassword || !item.app_user) && new_app_user.password_confirm.length < 6" class="mt-1 text-sm text-red-600">
                {{ t('common.min_length_error', { min: 6 }) }}
              </p>
              <p v-else-if="attemptedSave && (changePassword || !item.app_user) && new_app_user.password !== new_app_user.password_confirm" class="mt-1 text-sm text-red-600">
                {{ t('user_group.passwords_do_not_match') }}
              </p>
            </div>
          </template>
        </div>
      </div>
      <hr class="my-2 col-span-2" />
      <div class="col-span-2 flex flex-row-reverse mt-4">
        <button v-if="id != null && !isGmaoOperator" @click="deleteItem" :disabled="saving" class="button-default mx-5">
          &nbsp; {{ $t('common.delete') }}</button>
        <button @click="save" :disabled="saving" class="button-primary"><Icon name="fa6-solid:floppy-disk" />&nbsp; {{
          $t('common.save') }}</button>
      </div><!-- end contingut botons -->
    </div>

    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-1/2': !isSubRegionOpen }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)"
          class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300"><Icon name="fa6-solid:angles-right"
            class="text-slate-500" /></button>
      </div>
      <div class="px-10">
        <!-- subregions -->
      </div>
    </div>
  </div>
</template>
