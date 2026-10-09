<script setup>
import { useI18n } from 'vue-i18n';
import AppLoading from '~/components/atoms/AppLoading.vue';

const { t } = useI18n();

const props = defineProps({
    labelText: String,  // ℹ labelText is the text shown in the label
    loadFunction: {     // ℹ loadFunction needs to return an object with an array of objects and a boolean value indicating if the is a next page
        type: Function,
        required: true
    },
    item: Object,
});

const emit = defineEmits(['update:modelValue']);

var page = ref(1)

const items = ref([])

const hasNextPage = ref(false)

var observer = null;

const searchTerm = ref('')

const isLoading = ref(false)

const fetchData = async (pageNum = 1, searchString = '') => {
    if (pageNum === 1) {
        isLoading.value = true;
        items.value = [];
    }
    try {
        const result = await props.loadFunction(pageNum, searchString);
        if (result) {
            if (pageNum === 1) {
                items.value = result.items;
            } else {
                result.items.forEach(i => {
                    items.value.push({
                        value: i.value,
                        label: i.label
                    });
                });
            }
            hasNextPage.value = result.hasNextPage;
        }
    } catch (err) {
        console.error(err);
    } finally {
        if (pageNum === 1) isLoading.value = false;
    }
}

const onOpen = async () => {
  if (hasNextPage.value) {
    await nextTick()
    let observed = document.getElementById('vue-select-footer')
    observer?.observe(observed)
  }
}

const onClose = async () => {
    observer?.disconnect()
    searchTerm.value = ''
    page.value = 1
    await fetchData(1, '');
}

const infiniteScroll = async ([{ isIntersecting, target }]) => {
    if (isIntersecting) {
        const ul = target.offsetParent
        const scrollTop = target.offsetParent.scrollTop
        await loadNextPage();
        await nextTick()
        ul.scrollTop = scrollTop
    }
}

const loadNextPage = async () => {
    page.value++;
    await fetchData(page.value, searchTerm.value);
}

const onSearch = async (search, loading) => {
    if (search === searchTerm.value) return;
    
    searchTerm.value = search;
    page.value = 1;
    loading(true);
    await fetchData(1, search);
    loading(false);
}

const updateSelect = (event) => {
    props.item = event;
    emit('update:modelValue', event);
}

watch(props.loadFunction, async () => {
    page.value = 1;
    searchTerm.value = '';
    await fetchData(1, '');
}, { deep: true })

watch(() => props.item, (newValue, oldValue) => {
    if (newValue) {
        console.log('Prop changed:', newValue);
        items.value.push(newValue)
        props.item = newValue    
    }
});

onMounted(async () => {  
    if (props.loadFunction) {
        await fetchData(1, '');
    }
    observer = new IntersectionObserver(infiniteScroll)
});
</script>

<template>
    <div>
        <label v-if="labelText" class="block text-sm font-medium text-slate-500 mb-2">{{ labelText }}</label>
        <div class="flex">
            <v-select class="block w-full mr-1 required" :model-value="item" :options="items" @open="onOpen" @close="onClose"
                @update:modelValue="updateSelect($event)" @search="onSearch" :filterable="false" :clearable="true" :loading="isLoading">
                <template #no-options="{ search, searching, loading }">
                    <div v-if="isLoading" class="p-2 flex flex-col items-center">
                        <AppLoading :text="$t('common.loading') + '...'" :size="24" />
                    </div>
                    <span v-else>{{ $t('common.no_options') }}</span>
                </template>
                <template #list-footer>
                    <li v-show="hasNextPage" ref="load" id="vue-select-footer" class="py-2">
                        <AppLoading :text="$t('common.loading')" :size="24" />
                    </li>
                </template>
            </v-select>
            <slot></slot>
        </div>
    </div>
</template>