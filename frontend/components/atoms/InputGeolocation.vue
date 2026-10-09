<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue';
import { useI18n } from 'vue-i18n';
import 'leaflet/dist/leaflet.css';

const { t } = useI18n();

const props = defineProps({
  modelLatitude: {
    type: [Number, String, null],
    default: null
  },
  modelLongitude: {
    type: [Number, String, null],
    default: null
  }
});

const emit = defineEmits(['update:modelLatitude', 'update:modelLongitude']);

const latitude = ref(props.modelLatitude);
const longitude = ref(props.modelLongitude);
const mapInstance = ref(null);
const markerInstance = ref(null);
const mapReady = ref(false);
const mapContainerId = `geolocation-map-${Math.random().toString(36).substr(2, 9)}`;

// Sync props to local refs
watch(() => props.modelLatitude, (val) => {
  latitude.value = val;
  if (mapReady.value && val && longitude.value) {
    updateMarkerPosition(val, longitude.value);
  }
});

watch(() => props.modelLongitude, (val) => {
  longitude.value = val;
  if (mapReady.value && latitude.value && val) {
    updateMarkerPosition(latitude.value, val);
  }
});

const initMap = async () => {
  if (typeof window === 'undefined' || mapReady.value) return;
  
  const L = await import('leaflet');
  
  // Fix default marker icon issue
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
    iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  });

  // Default center (Spain)
  const defaultLat = latitude.value || 40.4168;
  const defaultLng = longitude.value || -3.7038;
  const defaultZoom = latitude.value && longitude.value ? 15 : 6;

  const mapContainer = document.getElementById(mapContainerId);
  if (!mapContainer || mapInstance.value) return;

  mapInstance.value = L.map(mapContainerId).setView([defaultLat, defaultLng], defaultZoom);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
  }).addTo(mapInstance.value);

  // Add marker if coordinates exist
  if (latitude.value && longitude.value) {
    markerInstance.value = L.marker([latitude.value, longitude.value]).addTo(mapInstance.value);
  }

  // Click handler to set marker
  mapInstance.value.on('click', (e) => {
    const { lat, lng } = e.latlng;
    const newLat = parseFloat(lat.toFixed(14));
    const newLng = parseFloat(lng.toFixed(14));
    latitude.value = newLat;
    longitude.value = newLng;
    emit('update:modelLatitude', newLat);
    emit('update:modelLongitude', newLng);
    updateMarkerPosition(newLat, newLng);
  });

  mapReady.value = true;
};

const updateMarkerPosition = async (lat, lng) => {
  if (!mapInstance.value) return;
  
  const L = await import('leaflet');
  
  if (markerInstance.value) {
    markerInstance.value.setLatLng([lat, lng]);
  } else {
    markerInstance.value = L.marker([lat, lng]).addTo(mapInstance.value);
  }
  mapInstance.value.setView([lat, lng], 15);
};

const onCoordinateChange = () => {
  emit('update:modelLatitude', latitude.value);
  emit('update:modelLongitude', longitude.value);
  
  if (latitude.value && longitude.value && mapReady.value) {
    updateMarkerPosition(latitude.value, longitude.value);
  }
};

const clearCoordinates = async () => {
  latitude.value = null;
  longitude.value = null;
  emit('update:modelLatitude', null);
  emit('update:modelLongitude', null);
  
  if (markerInstance.value && mapInstance.value) {
    mapInstance.value.removeLayer(markerInstance.value);
    markerInstance.value = null;
  }
};

onMounted(() => {
  nextTick(() => {
    initMap();
  });
});

onBeforeUnmount(() => {
  if (mapInstance.value) {
    mapInstance.value.remove();
    mapInstance.value = null;
    markerInstance.value = null;
    mapReady.value = false;
  }
});
</script>

<template>
  <div class="geolocation-input">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-3">
      <div>
        <label class="block text-xs text-slate-400 mb-1">{{ t('service_block.latitude') }}</label>
        <input 
          type="number" 
          step="any"
          v-model.number="latitude" 
          @change="onCoordinateChange"
          :placeholder="t('service_block.latitude')"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
        />
      </div>
      <div>
        <label class="block text-xs text-slate-400 mb-1">{{ t('service_block.longitude') }}</label>
        <input 
          type="number" 
          step="any"
          v-model.number="longitude" 
          @change="onCoordinateChange"
          :placeholder="t('service_block.longitude')"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent"
        />
      </div>
    </div>

    <div v-if="latitude || longitude" class="mb-2">
      <button 
        type="button" 
        @click="clearCoordinates" 
        class="text-sm text-red-500 hover:text-red-700"
      >
        <Icon name="fa6-solid:trash" class="mr-1" /> {{ t('common.clear') }}
      </button>
    </div>

    <ClientOnly>
      <div 
        :id="mapContainerId" 
        class="w-full h-64 rounded-md border border-gray-300"
      ></div>
      <p class="text-xs text-slate-400 mt-1">{{ t('service_block.click_map_to_set_location') }}</p>
    </ClientOnly>
  </div>
</template>

<style scoped>
.geolocation-input :deep(.leaflet-container) {
  z-index: 1;
}
</style>
