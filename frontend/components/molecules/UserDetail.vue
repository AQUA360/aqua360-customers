<script setup>
import FieldDetail from '../atoms/FieldDetail.vue';
import { useI18n } from 'vue-i18n';

const props = defineProps({
    id: Number,
    data: Object,
    isSubRegion: Boolean
});

const { t } = useI18n();
const { $UserApiService } = useNuxtApp();
const emit = defineEmits(['show-subregion']);
const localData = ref(null);
const loading = ref(true);

const getData = async () => {
    loading.value = true;
    try {
        const result = await $UserApiService.getDetail(props.id);
        localData.value = result;
    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
    }
}

const showDetail = (component, id) => {
    emit('show-subregion', component, id);
}

onMounted(() => {
    if (props.data) {
        localData.value = props.data;
        loading.value = false;
    } else if (props.id) {
        getData();
    }
});

watch(() => props.data, () => {
    if (props.data) {
        localData.value = props.data;
        loading.value = false;
    }
});

watch(() => props.id, () => {
    if (props.id) {
        getData();
    }
});

</script>

<template>
    <div id="wrapper" class="text-base">
        <div v-if="loading">
            <div class="p-4">
                <div class="flex justify-center items-center">
                    <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
                    <span class="ml-2">{{ $t('common.loading') }}...</span>
                </div>
            </div>
        </div>
        <div v-else-if="localData">
            <div role="row" class="grid grid-cols-2 gap-3">
                <FieldDetail :label='$t("user")' :value=localData?.username />
            </div>
            <div role="row" class="grid grid-cols-2 gap-3">
                <FieldDetail :label='$t("common.name")' :value="localData?.first_name + ' ' + localData?.last_name" />
                <FieldDetail :label='$t("common.email")' :value="localData?.email ? localData?.email : t('common.no_email')" />
                <FieldDetail :label='$t("group")'>
                    <div v-if="localData?.group_name == null">
                        <span v-if="localData.is_superuser">{{ t('common.admin') }}</span>
                        <span v-else>{{ t('user_group.no_group') }}</span>
                    </div>
                    <div v-else>
                        <button v-if="!isSubRegion" @click="showDetail('GroupRegion', localData?.group_id)"
                            class="text-start text-sky-500 underline hover:no-underline">
                            <span>{{ localData?.group_name }}</span>
                        </button>
                        <span v-else>{{ localData?.group_name }}</span>
                    </div>
                </FieldDetail>
            </div>
        </div>
    </div>
</template>