<script setup>
import { ref, onMounted, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const router = useRouter();
const route = useRoute();
const { $gotApi } = useNuxtApp();

const operator = ref(null);
const showMenu = ref(false);

const showBackButton = computed(() => {
  return route.path !== '/got/orders' && route.path !== '/got/summary';
});

const goBack = () => {
  const fromPage = route.query.from;
  if (fromPage === 'summary') {
    router.push('/got/summary');
  } else if (window.history.length > 1) {
    router.back();
  } else {
    router.push('/got/orders');
  }
};

const loadProfile = async () => {
  try {
    const response = await $gotApi.getProfile();
    if (response.success) {
      operator.value = response.operator;
    }
  } catch (error) {
    console.error('Error loading profile:', error);
  }
};

const logout = async () => {
  try {
    await $gotApi.logout();
    $gotApi.removeToken();
    router.push('/got/login');
  } catch (error) {
    console.error('Error during logout:', error);
  }
};

onMounted(() => {
  loadProfile();
});
</script>

<template>
  <div class="min-h-screen bg-[#fbfbfa]">
    <!-- Desktop Sidebar -->
    <aside class="hidden lg:flex fixed left-0 top-0 h-screen w-60 bg-[#f7f7f5] border-r border-gray-200/60 flex-col">
      <!-- Sidebar Header -->
      <div class="px-3 py-3 border-b border-gray-200/60">
        <div class="flex items-center gap-2 px-2 py-1.5" >
          <img src="/favicon-32x32.png" alt="" class="w-5 h-5"/>
          <span class="text-sm font-semibold text-gray-900">{{ t('GOT.title') }}</span>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        <NuxtLink 
        to="/got/orders"
        class="group flex items-center gap-2.5 px-2 py-1.5 rounded-md text-sm transition-all duration-150 hover:bg-black/5"
        active-class="bg-black/5"
        >
        <Icon name="fa6-solid:list" class="text-base text-gray-500 group-hover:text-gray-700" />
        <span class="text-gray-700 group-hover:text-gray-900 font-medium">{{ t('GOT.my_orders') }}</span>
      </NuxtLink>
      <NuxtLink 
        to="/got/summary"
        class="group flex items-center gap-2.5 px-2 py-1.5 rounded-md text-sm transition-all duration-150 hover:bg-black/5"
        active-class="bg-black/5"
      >
        <Icon name="fa6-solid:sheet-plastic" class="text-base text-gray-500 group-hover:text-gray-700" />
        <span class="text-gray-700 group-hover:text-gray-900 font-medium">{{ t('GOT.summary') }}</span>
      </NuxtLink>
      </nav>

      <!-- User Section -->
      <div class="px-2 py-3 border-t border-gray-200/60">
        <NuxtLink 
          to="/got/profile"
          class="group flex items-center gap-2.5 px-2 py-1.5 rounded-md hover:bg-black/5 transition-all duration-150"
        >
          <div class="w-6 h-6 rounded-full bg-black flex items-center justify-center flex-shrink-0">
            <Icon name="fa6-solid:user" class="text-xs text-white" />
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-700 truncate group-hover:text-gray-900">
              {{ operator?.name || t('GOT.my_profile') }}
            </p>
          </div>
          <button 
            @click.prevent="logout"
            class="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-50 rounded transition-all duration-150"
            :title="t('GOT.logout')"
          >
            <Icon name="fa6-solid:arrow-right-from-bracket" class="text-sm text-gray-500 hover:text-red-600" />
          </button>
        </NuxtLink>
      </div>
    </aside>

    <!-- Mobile Top Bar -->
    <div class="lg:hidden fixed top-0 left-0 right-0 z-40 bg-white/80 backdrop-blur-md border-b border-gray-200/60">
      <div class="flex items-center justify-between px-3 py-2.5 relative">
        <!-- Left: Back Button -->
        <div class="w-10">
          <button 
            v-if="showBackButton"
            @click="goBack"
            class="p-1.5 hover:bg-gray-100 rounded-md transition-colors"
          >
            <Icon name="fa6-solid:arrow-left" class="text-lg text-gray-700" />
          </button>
        </div>

        <!-- Center: Logo + Text -->
        <div class="flex items-center gap-2 cursor-pointer" @click="router.push('/got/orders')">
          <img src="/favicon-32x32.png" alt="" class="w-5 h-5"/>
          <span class="text-sm font-semibold text-gray-900">{{ t('GOT.title') }}</span>
        </div>

        <!-- Right: Menu Button -->
        <div class="w-10 flex justify-end">
          <button 
            @click="showMenu = !showMenu"
            class="p-1.5 hover:bg-gray-100 rounded-md transition-colors"
          >
            <Icon :name="showMenu ? 'fa6-solid:xmark' : 'fa6-solid:bars'" class="text-lg text-gray-700" />
          </button>
        </div>
      </div>

      <!-- Mobile Slide Menu -->
      <Transition
        enter-active-class="transition-all duration-300 ease-out"
        enter-from-class="opacity-0 -translate-y-2"
        enter-to-class="opacity-100 translate-y-0"
        leave-active-class="transition-all duration-200 ease-in"
        leave-from-class="opacity-100 translate-y-0"
        leave-to-class="opacity-0 -translate-y-2"
      >
        <nav 
          v-show="showMenu"
          class="border-t border-gray-200/60 bg-white/95 backdrop-blur-md px-2 py-2 space-y-1"
        >
          <NuxtLink 
            to="/got/orders"
            class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm hover:bg-gray-100 transition-colors"
            active-class="bg-gray-100"
            @click="showMenu = false"
          >
            <Icon name="fa6-solid:list" class="text-base text-gray-500" />
            <span class="text-gray-700 font-medium">{{ t('GOT.my_orders') }}</span>
          </NuxtLink>
          <NuxtLink 
            to="/got/summary"
            class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm hover:bg-gray-100 transition-colors"
            active-class="bg-gray-100"
            @click="showMenu = false"
          >
            <Icon name="fa6-solid:sheet-plastic" class="text-base text-gray-500" />
            <span class="text-gray-700 font-medium">{{ t('GOT.summary') }}</span>
          </NuxtLink>

          <!-- Separator -->
          <div class="border-t border-gray-200/60 my-1"></div>

          <!-- Profile -->
          <NuxtLink 
            to="/got/profile"
            class="flex items-center gap-2.5 px-3 py-2 rounded-md text-sm hover:bg-gray-100 transition-colors"
            active-class="bg-gray-100"
            @click="showMenu = false"
          >
            <div class="w-5 h-5 rounded-full bg-black flex items-center justify-center flex-shrink-0">
              <Icon name="fa6-solid:user" class="text-[10px] text-white" />
            </div>
            <span class="text-gray-700 font-medium truncate">{{ operator?.name || t('GOT.my_profile') }}</span>
          </NuxtLink>

          <!-- Logout -->
          <button 
            @click="logout(); showMenu = false;"
            class="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm hover:bg-red-50 text-red-600 transition-colors text-left"
          >
            <Icon name="fa6-solid:arrow-right-from-bracket" class="text-base flex-shrink-0" />
            <span class="font-medium">{{ t('GOT.logout') }}</span>
          </button>
        </nav>
      </Transition>
    </div>

    <!-- Main Content -->
    <main class="lg:ml-60 min-h-screen pt-14 lg:pt-0">
      <div class="px-4 sm:px-6 lg:px-12 py-6 lg:py-12 max-w-7xl mx-auto">
        <slot />
      </div>
    </main>
  </div>
</template>

<style scoped>
/* Notion-like scrollbar for sidebar */
aside::-webkit-scrollbar {
  width: 6px;
}

aside::-webkit-scrollbar-track {
  background: transparent;
}

aside::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.1);
  border-radius: 3px;
}

aside::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
</style>
