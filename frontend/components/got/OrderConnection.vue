<template>
  <div v-if="connection">
    <div class="flex items-center gap-2 mb-3">
      <Icon name="fa6-solid:plug" class="text-black-600 text-sm" />
      <h3 class="text-sm font-semibold text-gray-900">{{ $t('GOT.connection') }}</h3>
    </div>
    <div class="grid grid-cols-2 gap-x-4 gap-y-3">
      <!-- Token -->
      <div class="space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('GOT.token') }}
        </label>
        <p class="text-sm text-gray-900 font-medium">
          {{ connection.token || '-' }}
        </p>
      </div>

      <!-- Type -->
      <div class="space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('GOT.type') }}
        </label>
        <p class="text-sm text-gray-900 font-medium">
          {{ connection.type || '-' }}
        </p>
      </div>

      <!-- Installation Date -->
      <div v-if="connection.installation_at" class="space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('GOT.installation_date') }}
        </label>
        <div class="flex items-center gap-1.5">
          <Icon name="fa6-solid:calendar" class="text-gray-400 text-xs" />
          <p class="text-sm text-gray-900">
            {{ new Date(connection.installation_at).toLocaleDateString() }}
          </p>
        </div>
      </div>

      <!-- Diameter -->
      <div v-if="connection.diameter" class="space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('GOT.diameter') }}
        </label>
        <p class="text-sm text-gray-900 font-medium">
          {{ connection.diameter }} mm
        </p>
      </div>

      <!-- Use Type -->
      <div v-if="connection.use_type" class="space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('GOT.use_type') }}
        </label>
        <p class="text-sm text-gray-900 truncate">
          {{ connection.use_type }}
        </p>
      </div>

      <!-- Installation Type -->
      <div v-if="connection.installation_type" class="space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('GOT.installation_type') }}
        </label>
        <p class="text-sm text-gray-900 truncate">
          {{ connection.installation_type }}
        </p>
      </div>

      <!-- Supply Type -->
      <div v-if="connection.supply_type" class="space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('GOT.supply_type') }}
        </label>
        <p class="text-sm text-gray-900 truncate">
          {{ connection.supply_type }}
        </p>
      </div>

      <!-- Code GIS -->
      <div v-if="connection.code_gis" class="space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('GOT.code_gis') }}
        </label>
        <p class="text-sm text-gray-900 font-mono truncate">
          {{ connection.code_gis }}
        </p>
      </div>

      <!-- Address -->
      <div v-if="connection.address" class="col-span-2 space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('GOT.address') }}
        </label>
        <div class="flex items-start gap-2">
          <Icon name="fa6-solid:location-dot" class="text-gray-400 text-xs mt-0.5 flex-shrink-0" />
          <p class="text-sm text-gray-900 leading-snug">
            {{ connection.address }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  connection: {
    type: Object,
    default: null
  }
});
</script>
