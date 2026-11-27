<script setup>
// Fitxa de l'usuari que ha fet login, oberta a tothom sigui quin sigui el rol o els permisos:
// dades del compte (nom d'usuari, rol i grup, només de lectura), nom, cognoms i correu
// (editables) i, des d'un modal, canvi de la contrasenya pròpia.
import { ref, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import AppLoading from '~/components/atoms/AppLoading.vue';
import ChangeOwnPasswordModal from '~/components/molecules/ChangeOwnPasswordModal.vue';
import { formatDateTime } from '~/utils/date';

const { t } = useI18n();
const toast = useToast();
const { $UserApiService } = useNuxtApp();

const loading = ref(true);
const loadError = ref(false);
const saving = ref(false);
const attemptedSave = ref(false);
const showPasswordModal = ref(false);

const profile = ref(null);
const firstName = ref('');
const lastName = ref('');
const email = ref('');

const fullName = computed(() =>
  [profile.value?.first_name, profile.value?.last_name].filter(Boolean).join(' ')
);
const initials = computed(() => {
  const source = fullName.value || profile.value?.username || '';
  return source.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part.charAt(0).toUpperCase()).join('');
});

const roleLabel = computed(() => {
  const role = profile.value?.role;
  if (role === 'superuser') return t('common.superuser');
  if (role === 'admin') return t('common.admin');
  return t('user_group.role_none');
});

const emailValid = computed(() => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((email.value || '').trim()));
const hasChanges = computed(() => !!profile.value && (
  firstName.value !== (profile.value.first_name || '')
  || lastName.value !== (profile.value.last_name || '')
  || email.value !== (profile.value.email || '')
));

const fillForm = (data) => {
  profile.value = data;
  firstName.value = data.first_name || '';
  lastName.value = data.last_name || '';
  email.value = data.email || '';
};

const getData = async () => {
  loading.value = true;
  loadError.value = false;
  try {
    fillForm(await $UserApiService.getOwnProfile());
  } catch (error) {
    console.error(error);
    loadError.value = true;
  } finally {
    loading.value = false;
  }
};

const discard = () => {
  fillForm(profile.value);
  attemptedSave.value = false;
};

const save = async () => {
  attemptedSave.value = true;
  if (!emailValid.value) {
    toast.warning(t('user_group.profile_email_invalid'));
    return;
  }
  saving.value = true;
  try {
    const response = await $UserApiService.updateOwnProfile({
      first_name: firstName.value.trim(),
      last_name: lastName.value.trim(),
      email: email.value.trim(),
    });
    fillForm(response);
    attemptedSave.value = false;
    toast.success(t('common.correct_save'));
  } catch (error) {
    // L'api-manager ja mostra l'error del backend
    console.error(error);
  } finally {
    saving.value = false;
  }
};

onMounted(getData);
</script>

<template>
  <div id="wrapper" class="text-base p-4 max-w-full">
    <div class="max-w-3xl mx-auto">
      <div class="mb-6">
        <H1>{{ $t('user_group.my_profile') }}</H1>
      </div>

      <AppLoading v-if="loading" :text="$t('common.loading')" />

      <div v-else-if="loadError" role="alert" class="rounded-lg border border-slate-200 p-4 bg-white text-red-600 flex flex-wrap items-center gap-3">
        <Icon name="fa6-solid:triangle-exclamation" aria-hidden="true" />
        <span>{{ $t('user_group.profile_load_error') }}</span>
        <button type="button" class="button-default ml-auto" @click="getData">{{ $t('common.retry') }}</button>
      </div>

      <div v-else class="rounded-lg border border-slate-200 bg-white divide-y divide-slate-200">
        <!-- Capçalera: qui és i què pot fer (només lectura) -->
        <div class="p-5 flex items-center gap-4">
          <div class="shrink-0 w-14 h-14 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-lg font-semibold text-slate-600"
            aria-hidden="true">
            {{ initials }}
          </div>
          <div class="min-w-0">
            <p class="text-lg font-semibold text-slate-800 truncate">{{ fullName || profile.username }}</p>
            <p class="text-sm text-slate-500 truncate">{{ profile.username }}</p>
            <div class="mt-2 flex flex-wrap gap-2 text-xs">
              <span class="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-600">
                <Icon name="fa6-solid:shield-halved" aria-hidden="true" />
                {{ $t('user_group.role') }}: {{ roleLabel }}
              </span>
              <span class="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 font-medium text-slate-600">
                <Icon name="fa6-solid:users" aria-hidden="true" />
                {{ $t('group') }}: {{ profile.group_name || $t('user_group.no_group') }}
              </span>
            </div>
            <p class="text-xs text-slate-500 mt-2">
              <template v-if="profile.last_login">{{ $t('user_group.last_login') }}: {{ formatDateTime(profile.last_login) }} · </template>{{ $t('user_group.profile_account_help') }}
            </p>
          </div>
        </div>

        <!-- Dades personals (editables) -->
        <form class="p-5" @submit.prevent="save">
          <h2 class="text-base font-semibold text-slate-800 mb-4">{{ $t('user_group.profile_info') }}</h2>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label for="profile-first-name" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('common.name') }}</label>
              <input id="profile-first-name" v-model="firstName" type="text" class="input w-full" autocomplete="given-name" maxlength="150" />
            </div>
            <div>
              <label for="profile-last-name" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('common.surname') }}</label>
              <input id="profile-last-name" v-model="lastName" type="text" class="input w-full" autocomplete="family-name" maxlength="150" />
            </div>
            <div class="sm:col-span-2">
              <label for="profile-email" class="block text-sm font-medium text-slate-500 mb-2">{{ $t('common.email_long') }}</label>
              <input id="profile-email" v-model="email" type="email" class="input w-full" autocomplete="email" maxlength="254"
                :class="{ 'invalid': attemptedSave && !emailValid }" />
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-5">
            <button v-if="hasChanges" type="button" class="button-default" :disabled="saving" @click="discard">
              {{ $t('common.cancel') }}
            </button>
            <button type="submit" :disabled="saving || !hasChanges" class="button-primary"
              :class="{ 'opacity-50 cursor-not-allowed': !hasChanges }">
              <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="saving ? 'animate-spin' : ''" />
              &nbsp;{{ $t('common.save') }}
            </button>
          </div>
        </form>

        <!-- Seguretat: la contrasenya es canvia des d'un modal -->
        <div class="p-5 flex flex-wrap items-center justify-between gap-4">
          <div class="min-w-0">
            <h2 class="text-base font-semibold text-slate-800">{{ $t('common.password') }}</h2>
            <p class="text-sm text-slate-500 mt-1">{{ $t('user_group.password_section_help') }}</p>
          </div>
          <button type="button" class="button-default" @click="showPasswordModal = true">
            <Icon name="fa6-solid:key" />
            &nbsp;{{ $t('user_group.change_password') }}
          </button>
        </div>
      </div>
    </div>

    <ChangeOwnPasswordModal v-model:open="showPasswordModal" :username="profile?.username || ''"
      :is-superuser="profile?.role === 'superuser'" />
  </div>
</template>
