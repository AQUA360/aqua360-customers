<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';

definePageMeta({
  layout: false
});

const { t } = useI18n();
const router = useRouter();
const toast = useToast();
const { $gotApi } = useNuxtApp();

const username = ref('');
const password = ref('');
const loading = ref(false);
const showPassword = ref(false);

const handleLogin = async () => {
  if (!username.value || !password.value) {
    toast.error(t('common.required_fields'));
    return;
  }

  loading.value = true;
  try {
    const response = await $gotApi.login(username.value, password.value);
    
    
    if (response?.success) {
      // Store the token if provided
      if (response.token) {
        $gotApi.setToken(response.token);
      }
      
      toast.success(t('GOT.welcome'));
      await navigateTo('/got/orders');
    } else {
      toast.error(t('GOT.login_wrong_credentials'));
    }
  } catch (error) {
    toast.error(t('GOT.login_wrong_credentials'));
    
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="min-h-screen bg-[#fbfbfa] flex items-center justify-center p-4">
    <div class="bg-white rounded-lg border border-gray-200/60 shadow-sm p-8 w-full max-w-md">
      <!-- Logo & Title -->
      <div class="text-center mb-8">
        <div class="inline-flex items-center justify-center w-12 h-12 rounded-lg  mb-4">
          <img src="/favicon-32x32.png" alt="Logo" class="w-6 h-6" />
        </div>
        <h1 class="text-2xl font-bold text-gray-900 mb-1">{{ $t('GOT.title') }}</h1>
        <p class="text-sm text-gray-500">{{ $t('GOT.login_title') }}</p>
      </div>

      <!-- Login Form -->
      <form @submit.prevent="handleLogin" class="space-y-5">
        <!-- Username Field -->
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1.5">
            {{ $t('common.username') }}
          </label>
          <input
            v-model="username"
            type="text"
            class="w-full px-3 py-2 border border-gray-200/60 rounded-md focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-150 text-sm"
            :placeholder="$t('common.username')"
            required
          />
        </div>

        <!-- Password Field -->
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1.5">
            {{ $t('common.password') }}
          </label>
          <div class="relative">
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              class="w-full px-3 py-2 pr-10 border border-gray-200/60 rounded-md focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all duration-150 text-sm"
              :placeholder="$t('common.password')"
              required
            />
            <button
              type="button"
              @click="showPassword = !showPassword"
              class="absolute right-2.5 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600 p-1"
            >
              <Icon :name="showPassword ? 'fa6-solid:eye-slash' : 'fa6-solid:eye'" class="text-sm" />
            </button>
          </div>
        </div>

        <!-- Submit Button -->
        <button
          type="submit"
          :disabled="loading"
          class="w-full bg-gray-900 text-white py-2.5 px-4 rounded-md hover:bg-gray-800 disabled:bg-gray-400 disabled:cursor-not-allowed transition-all duration-150 font-medium text-sm shadow-sm"
        >
          <span v-if="!loading">{{ $t('dashboard.enter') }}</span>
          <span v-else class="flex items-center justify-center gap-2">
            <Icon name="fa6-solid:spinner" class="animate-spin" />
            {{ $t('common.loading') }}
          </span>
        </button>
      </form>

      <!-- Language Switcher -->
      <div class="mt-6 pt-6 border-t border-gray-200/60 flex justify-center">
        <AtomsLanguageSwitcher />
      </div>
    </div>
  </div>
</template>
