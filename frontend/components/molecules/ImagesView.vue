<script setup>
import { ref, onMounted, watch, onBeforeUnmount } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const { $DocumentManagerApiService } = useNuxtApp();

const props = defineProps({
    images: {
        type: Array,
        default: () => []
    },
    loading: {
        type: Boolean,
        default: false
    }
});

const imagesData = ref([]);
const currentImageIndex = ref(0);
const isLoadingImage = ref(false);
const currentImageUrl = ref(null);
const error = ref(null);
const thumbnailUrls = ref([]);
const isLoadingThumbnails = ref(false);

const emit = defineEmits(['change']);

const fetchImage = async (imageItem) => {
    isLoadingImage.value = true;
    currentImageUrl.value = null;
    error.value = null;

    try {
        const fileBlob = await $DocumentManagerApiService.viewDocument(imageItem.file.id);
        const blob = new Blob([fileBlob], { type: imageItem.mime_type || 'image/jpeg' });
        const file_url = URL.createObjectURL(blob);
        currentImageUrl.value = file_url
    } catch (err) {
        console.error("Error fetching image:", err);
        error.value = t('Failed to load image.');
        currentImageUrl.value = null;
    } finally {
        isLoadingImage.value = false;
    }
};

const fetchThumbnail = async (imageItem) => {
    try {
        const fileBlob = await $DocumentManagerApiService.viewDocument(imageItem.file.id);
        const blob = new Blob([fileBlob], { type: imageItem.mime_type || 'image/jpeg' });
        const file_url = URL.createObjectURL(blob);
        return file_url
    } catch (err) {
        console.error("Error fetching thumbnail:", err);
        return null; 
    }
};

const loadThumbnails = async (images) => {
    isLoadingThumbnails.value = true;
    thumbnailUrls.value = [];
    const urls = await Promise.all(images.map(fetchThumbnail));
    thumbnailUrls.value = urls;
    isLoadingThumbnails.value = false;
};

const selectImage = (index) => {
    currentImageIndex.value = index;
    fetchImage(imagesData.value[currentImageIndex.value]);
};

onMounted(() => {
    if (props.images.length > 0) {
        imagesData.value = props.images;
        loadThumbnails(imagesData.value);
        fetchImage(imagesData.value[currentImageIndex.value]);
    }
});

watch(() => props.images, (newVal) => {
    imagesData.value = newVal;
    currentImageIndex.value = 0;
    if (imagesData.value.length > 0) {
        loadThumbnails(imagesData.value);
        fetchImage(imagesData.value[currentImageIndex.value]);
    } else {
        currentImageUrl.value = null;
        thumbnailUrls.value = [];
    }
}, { immediate: true });

onBeforeUnmount(() => {
    if (currentImageUrl.value) {
        URL.revokeObjectURL(currentImageUrl.value);
    }
    thumbnailUrls.value.forEach(url => {
        if (url) {
            URL.revokeObjectURL(url);
        }
    });
});

watch(currentImageUrl, (newUrl, oldUrl) => {
    if (oldUrl) {
        URL.revokeObjectURL(oldUrl);
    }
});

watch(thumbnailUrls, (newUrls, oldUrls) => {
    if (oldUrls) {
        oldUrls.forEach(url => {
            if (url) {
                URL.revokeObjectURL(url);
            }
        });
    }
}, { deep: true });

</script>

<template>
    <div class="mx-auto">
        <div class="relative p-4 bg-gray-100 rounded-lg h-[40vh] flex items-center justify-center overflow-hidden mb-4">
            <div v-if="props.loading || isLoadingImage" class="text-gray-500 text-center">
                <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
                <span class="ml-2">{{ $t('common.loading') }}...</span>
            </div>
            <div v-else-if="error" class="text-red-500 text-center">{{ error }}</div>
            <div v-else-if="!currentImageUrl && !props.loading && !isLoadingImage && !error"
                class="text-gray-500 text-center">
                {{ $t('common.no_records') }}
            </div>
            <img v-else :src="currentImageUrl" :alt="$t('common.img')"
                class="max-h-full max-w-full object-contain">
        </div>

        <div v-if="imagesData.length > 0" class="flex overflow-x-auto space-x-2 p-2 bg-gray-50 rounded-lg">
            <div v-if="isLoadingThumbnails" class="flex items-center justify-center w-full text-gray-500">
                <Icon name="fa6-solid:spinner" class="animate-spin text-xl text-slate-500" />
                <span class="ml-2">{{ $t('common.loading') }}...</span>
            </div>
            <div v-else v-for="(image, index) in imagesData" :key="image.file.id"
                class="flex-shrink-0 w-20 h-20 cursor-pointer rounded-md overflow-hidden border-2"
                :class="{ 'border-blue-500': index === currentImageIndex, 'border-transparent': index !== currentImageIndex }"
                @click="selectImage(index)" @mouseover="selectImage(index)">
                <img v-if="thumbnailUrls[index]" :src="thumbnailUrls[index]" :alt="$t('common.miniature')"
                    class="w-full h-full object-cover">
                <div v-else class="w-full h-full bg-gray-200 flex items-center justify-center text-gray-500 text-xs">
                    {{ $t('common.error') }}
                </div>
            </div>
        </div>
    </div>
</template>

<style scoped>
.overflow-x-auto::-webkit-scrollbar {
    height: 8px;
}

.overflow-x-auto::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 10px;
}

.overflow-x-auto::-webkit-scrollbar-thumb {
    background: #888;
    border-radius: 10px;
}

.overflow-x-auto::-webkit-scrollbar-thumb:hover {
    background: #555;
}
</style>
