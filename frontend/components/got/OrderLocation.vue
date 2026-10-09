<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import 'leaflet/dist/leaflet.css';

const props = defineProps({
  latitude: {
    type: [Number, String, null],
    default: null
  },
  longitude: {
    type: [Number, String, null],
    default: null
  }
});

const mapContainerId = `got-order-map-${Math.random().toString(36).substr(2, 9)}`;
const mapInstance = ref(null);
const markerInstance = ref(null);

const coords = computed(() => {
  const lat = parseFloat(props.latitude);
  const lng = parseFloat(props.longitude);
  if (isNaN(lat) || isNaN(lng)) return null;
  return { lat, lng };
});

const mapsUrl = computed(() => {
  if (!coords.value) return null;
  return `https://www.google.com/maps/search/?api=1&query=${coords.value.lat},${coords.value.lng}`;
});

const initMap = async () => {
  if (typeof window === 'undefined' || !coords.value || mapInstance.value) return;

  const L = await import('leaflet');

  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  });

  const container = document.getElementById(mapContainerId);
  if (!container) return;

  mapInstance.value = L.map(mapContainerId, { attributionControl: false })
    .setView([coords.value.lat, coords.value.lng], 16);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(mapInstance.value);

  markerInstance.value = L.marker([coords.value.lat, coords.value.lng]).addTo(mapInstance.value);
};

const destroyMap = () => {
  if (mapInstance.value) {
    mapInstance.value.remove();
    mapInstance.value = null;
    markerInstance.value = null;
  }
};

watch(coords, (val) => {
  if (!val) {
    destroyMap();
    return;
  }
  if (!mapInstance.value) {
    nextTick(() => initMap());
    return;
  }
  markerInstance.value?.setLatLng([val.lat, val.lng]);
  mapInstance.value.setView([val.lat, val.lng], 16);
});

onMounted(() => {
  nextTick(() => initMap());
});

onBeforeUnmount(destroyMap);
</script>

<template>
  <div v-if="coords">
    <div class="flex items-center gap-2 mb-3">
      <Icon name="fa6-solid:map-location-dot" class="text-black text-sm" />
      <h3 class="text-sm font-semibold text-gray-900">{{ $t('GOT.location') }}</h3>
    </div>

    <div class="grid grid-cols-2 gap-x-4 gap-y-3 mb-3">
      <div class="space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('order_block.latitude') }}
        </label>
        <p class="text-sm text-gray-900 font-medium">{{ coords.lat }}</p>
      </div>
      <div class="space-y-0.5">
        <label class="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
          {{ $t('order_block.longitude') }}
        </label>
        <p class="text-sm text-gray-900 font-medium">{{ coords.lng }}</p>
      </div>
    </div>

    <ClientOnly>
      <div :id="mapContainerId" class="w-full h-48 rounded-md border border-gray-200/60"></div>
    </ClientOnly>

    <a
      :href="mapsUrl"
      target="_blank"
      rel="noopener"
      class="mt-2 inline-flex items-center gap-2 text-sm font-medium text-sky-600 hover:text-sky-700"
    >
      <Icon name="fa6-solid:diamond-turn-right" class="text-xs" />
      {{ $t('GOT.open_in_maps') }}
    </a>
  </div>
</template>

<style scoped>
:deep(.leaflet-container) {
  z-index: 1;
}
</style>
