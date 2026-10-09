<script setup>
const { $gotApi } = useNuxtApp();

// Check if user is authenticated
const isAuthenticated = process.client ? !!$gotApi.getToken() : false;

// Redirect based on auth status
if (process.client) {
  if (isAuthenticated) {
    navigateTo('/got/orders');
  } else {
    navigateTo('/got/login');
  }
}
import AppLoading from '~/components/atoms/AppLoading.vue';
</script>

<template>
  <div class="flex items-center justify-center min-h-screen">
    <AppLoading />
  </div>
</template>
