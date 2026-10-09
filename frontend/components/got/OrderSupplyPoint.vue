<template>
  <div v-if="supplyPoint">
    <div class="flex items-center gap-2 mb-3">
      <Icon name="fa6-solid:street-view" class="text-black-600 text-sm" />
      <h3 class="text-sm font-semibold text-gray-900">{{ supplyPoint.address_complete || '-' }}</h3>
    </div>
    <div class="grid grid-cols-3 gap-x-4 gap-y-3">
      <!-- Token -->
      <div class="space-y-0.5">
        <p class="text-sm text-gray-900 font-medium">
          {{ supplyPoint.token || '-' }}
        </p>
      </div>

      <!-- Status -->
      <div class="space-y-0.5">
        <div class="flex items-center gap-1.5">
          <span 
            class="w-1.5 h-1.5 rounded-full" 
            :class="{
              'bg-green-500': supplyPoint.status_color === 'green',
              'bg-red-500': supplyPoint.status_color === 'red',
              'bg-blue-500': supplyPoint.status_color === 'blue',
              'bg-yellow-500': supplyPoint.status_color === 'yellow',
              'bg-gray-500': !supplyPoint.status_color
            }"
          ></span>
          <p class="text-sm text-gray-900 font-medium truncate">
            {{ supplyPoint.status_name || '-' }}
          </p>
        </div>
      </div>

      <!-- Meter Code -->
      <div v-if="supplyPoint.meter_code" class="space-y-0.5">
        <p class="text-sm text-gray-900 font-medium">
          <Icon name="my-icon:meter-icon-black" class="text-slate-500" />{{ supplyPoint.meter_code }}
        </p>
      </div>

      <!-- Telecontrol -->
      <div class="space-y-0.5">
        <span 
          class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
          :class="supplyPoint.is_telecontrol 
            ? 'bg-green-50 text-green-700 border border-green-200/60' 
            : 'bg-gray-50 text-gray-700 border border-gray-200/60'"
        >
          <Icon 
            :name="supplyPoint.is_telecontrol ? 'fa6-solid:tower-broadcast' : 'fa6-solid:hand'" 
            class="text-[10px]"
          />
          {{ supplyPoint.is_telecontrol ? $t('GOT.telecontrol') : $t('GOT.manual_reading') }}
        </span>
      </div>

    </div>
  </div>
</template>

<script setup>
defineProps({
  supplyPoint: {
    type: Object,
    default: null
  }
});
</script>
