<script setup>
import H1Region from '~/components/atoms/H1Region.vue';
import {Map,Layers,Sources, Geometries, Styles} from "vue3-openlayers";
import { transform, fromLonLat } from 'ol/proj';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const pending = ref(true);
const error = ref(null);

const props = defineProps({
  longitude: Number,
  latitude: Number,
  address: String
});

const coords = ref([])

const getData = () => {
    pending.value = true
    if (props.longitude && props.latitude) {
        coords.value = transform([props.longitude, props.latitude], 'EPSG:4326', 'EPSG:3857')
        console.log('coords', coords.value)
    }
    else {
        error.value = {
            message: t('billing_block.warning_check_geolocation')
        }
    }
    pending.value = false
}

watch(() => props.longitude, (newValue) => {
    getData()
});

watch(() => props.latitude, (newValue) => {
    getData()
});

onMounted(() => {
  getData()
})
</script>

<template>
    <div class="region__content">
        <div v-if="pending">
            <p>{{ $t('common.loading') }}...</p>
        </div>
        <div v-else-if="error">
            <p>Error: {{ error.message }}</p>
        </div>
        <div v-else class="map-container">
            <H1Region class="mb-3">{{ $t('service_block.geolocation') }}</H1Region>

            <div v-if="address || (longitude && latitude)" class="mb-3 text-sm text-gray-700 space-y-1">
                <p v-if="address" class="font-medium">{{ address }}</p>
                <p v-if="longitude && latitude" class="text-gray-500">
                    {{ $t('address_block.latitude') }}: {{ latitude }} &nbsp;|&nbsp; {{ $t('address_block.longitude') }}: {{ longitude }}
                </p>
            </div>

            <Map.OlMap style="min-width: 400px; height: 400px">
                <Map.OlView :center="coords" :zoom="15" projection="EPSG:3857" :markers="[coords]"/>
                <Layers.OlTileLayer>
                    <Layers.OlVectorLayer>

                        <Sources.OlSourceVector>
                            <Map.OlFeature>
                                <Geometries.OlGeomPoint :coordinates="coords" />
                            </Map.OlFeature>
                        </Sources.OlSourceVector>

                        <Styles.OlStyle>
                            <Styles.OlStyleIcon :scale="0.2" :src="'/marker-crimson.svg'" />
                        </Styles.OlStyle>

                    </Layers.OlVectorLayer>
                    <Sources.OlSourceOSM />
                </Layers.OlTileLayer>
            </Map.OlMap>
        </div>
    </div>
</template>

<style scoped>
</style>