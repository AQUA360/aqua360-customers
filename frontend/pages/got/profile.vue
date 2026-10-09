<script setup>
import { ref, onMounted } from "vue";
import { useI18n } from "vue-i18n";

definePageMeta({
  layout: "got",
  title: "Profile",
});

defineEmits(['back']);

const { t } = useI18n();
const { $gotApi } = useNuxtApp();

const operator = ref(null);
const loading = ref(true);

const loadProfile = async () => {
  try {
    loading.value = true;
    const response = await $gotApi.getProfile();

    if (response.success) {
      operator.value = response.operator;
    }
  } catch (error) {
    console.error("Error loading profile:", error);
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadProfile();
});
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-3">
      <div
        class="w-10 h-10 rounded-lg bg-black flex items-center justify-center flex-shrink-0"
      >
        <Icon name="fa6-solid:user" class="text-white text-lg" />
      </div>
      <h1 class="text-3xl font-bold text-gray-900">
        {{ t("GOT.my_profile") }}
      </h1>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center items-center py-20">
      <Icon
        name="fa6-solid:spinner"
        class="animate-spin text-3xl text-gray-300"
      />
    </div>

    <!-- Profile Card -->
    <div
      v-else-if="operator"
      class="bg-white rounded-lg border border-gray-200/60 overflow-hidden"
    >
      <!-- Profile Header -->
      <div class="px-6 py-5 border-b border-gray-200/60">
        <div class="flex items-start gap-4">
          <div
            class="w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center flex-shrink-0 shadow-lg"
          >
            <Icon name="fa6-solid:user" class="text-2xl text-white" />
          </div>
          <div class="flex-1 min-w-0">
            <h2 class="text-xl font-semibold text-gray-900 mb-1">
              {{ operator.name }} {{ operator.surname }}
            </h2>
            <div class="flex items-center gap-2">
              <span class="text-sm text-gray-500"
                >@{{ operator.username }}</span
              >
              <span
                v-if="operator.is_active"
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-50 text-green-700 border border-green-200"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-green-500"></span>
                {{ t("common.active") }}
              </span>
              <span
                v-else
                class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-gray-50 text-gray-700 border border-gray-200"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-gray-500"></span>
                {{ t("common.inactive") }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Profile Details -->
      <div class="px-6 py-5">
        <div class="grid gap-4 sm:grid-cols-2">
          <div class="space-y-1">
            <label
              class="text-xs font-medium text-gray-500 uppercase tracking-wide"
            >
              {{ t("common.username") }}
            </label>
            <p class="text-sm text-gray-900 font-medium">
              {{ operator.username }}
            </p>
          </div>

          <div class="space-y-1">
            <label
              class="text-xs font-medium text-gray-500 uppercase tracking-wide"
            >
              {{ t("common.status") }}
            </label>
            <p class="text-sm text-gray-900 font-medium">
              {{
                operator.is_active ? t("common.active") : t("common.inactive")
              }}
            </p>
          </div>

          <div class="space-y-1">
            <label
              class="text-xs font-medium text-gray-500 uppercase tracking-wide"
            >
              {{ t("GOT.created_at") }}
            </label>
            <div class="flex items-center gap-2">
              <Icon
                name="fa6-solid:calendar-plus"
                class="text-gray-400 text-xs"
              />
              <p class="text-sm text-gray-900">
                {{ new Date(operator.created_at).toLocaleDateString() }}
              </p>
            </div>
          </div>

          <div class="space-y-1">
            <label
              class="text-xs font-medium text-gray-500 uppercase tracking-wide"
            >
              {{ t("GOT.updated_at") }}
            </label>
            <div class="flex items-center gap-2">
              <Icon name="fa6-solid:clock" class="text-gray-400 text-xs" />
              <p class="text-sm text-gray-900">
                {{ new Date(operator.updated_at).toLocaleDateString() }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
