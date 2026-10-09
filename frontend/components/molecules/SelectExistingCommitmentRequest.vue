<script setup>
import CommitmentDepositRegion from '../organisms/CommitmentDepositRegion.vue';

const { t } = useI18n()

const props = defineProps({
    requests: Array,
});

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const showRegionDetailComponent = ref(null);
const regionDetailId = ref(null);

const emit = defineEmits(['close']);

const toggleRegion = (force) => {
    showRegion.value = force !== undefined ? force : !showRegion.value;
    if (showRegion.value == false) {
        isSubRegionOpen.value = false;
        showRegionDetailComponent.value = null;
        regionDetailId.value = null;
    }
}

const showDetail = (component, id) => {
    showRegionDetailComponent.value = component;
    regionDetailId.value = id;
    toggleRegion(true);
}

const handleSubRegionEvent = (event) => {
    isSubRegionOpen.value = event;
}

const emitClose = () => {
    emit('close');
}

const openExistingDeposit = async (id) => {
    return navigateTo('/billing/commitment-deposits/edit/' + id)
}

</script>
<template>
    <div>
        <div class="w-full max-w-md mx-auto bg-white rounded-xl shadow-lg p-6">
            <h2 class="text-2xl font-bold text-gray-800 mb-4">
                {{ t("claim_block.holder_commitments") }}
            </h2>

            <p class="text-sm text-gray-600 mb-6">
                {{ t("informative_block.info_mng_commitment") }}
            </p>

            <div class="max-h-[250px] overflow-y-auto mb-6 space-y-3">
                <div v-for="request in props.requests" :key="request.id"
                    class="flex items-center justify-between border border-gray-200 rounded-md p-3 bg-gray-50 hover:bg-gray-100 transition duration-150 ease-in-out">
                    <div class="flex-1 mr-4">
                        <span class="text-base font-medium text-sky-600 hover:underline cursor-pointer"
                            @click="showDetail('CommitmentDepositRegion', request.id)">
                            {{ request.token }}
                        </span>
                    </div>
                    <div class="flex items-center space-x-3">
                        <AtomsColorBadge :color="request.status_color" :value="request.status_name" />
                        <abbr :title="`${t('common.select')} ${t('common.or')} ${t('common.add')} ${t('claim_block.commitment')}`">
                            <button @click="openExistingDeposit(request.id)"
                                class="flex-shrink-0 w-8 h-8 rounded-full bg-orange-500 hover:bg-orange-600 active:bg-orange-700 transition duration-150 ease-in-out flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-opacity-50">
                                <Icon name="fa6-solid:angle-right" class="text-white text-lg" />
                            </button>
                        </abbr>
                    </div>
                </div>
                <p v-if="props.requests.length === 0" class="text-center text-gray-500 italic">
                    {{ t("common.no_records") }}
                </p>
            </div>

            <div class="flex justify-end">
                <button class="button-default px-4 py-2" @click="emitClose">
                    {{ t("common.cancel") }}
                </button>
            </div>
        </div>
        <div role="region" id="right_page"
            class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white"
            :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen, 'w-[60%]': !isSubRegionOpen }">
            <div id="region_nav" class="mb-3 px-3">
                <button @click="toggleRegion(false)"
                    class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
                    <Icon name="fa6-solid:angles-right" class="text-slate-500" />
                </button>
            </div>
            <div class="px-10">
                <CommitmentDepositRegion v-if="showRegionDetailComponent === 'CommitmentDepositRegion'"
                    :id="parseInt(regionDetailId)" :isSubRegion="true" />
            </div>
        </div>
    </div>
</template>