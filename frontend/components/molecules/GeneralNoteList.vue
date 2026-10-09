<script setup>
import TimeRelative from '~/components/atoms/TimeRelative.vue';
import H1Region from '~/components/atoms/H1Region.vue';
import { useSidebarStore } from '~/stores/useNavSideBar';
import { useToast } from 'vue-toastification';
import { h } from 'vue';

const { t } = useI18n();
const { $GeneralNoteApiService } = useNuxtApp()
const sideBarStore = useSidebarStore();
const toast = useToast();

const generalNoteToastContent = (username, note) => h('div', [
    h('div', { class: 'text-xs opacity-75 mb-1' }, username),
    h('div', note),
]);

const error = ref(null)
const data = ref([])
const new_note = ref('')
const isSubmitting = ref(false)

const page = ref(1);
const pageSize = 10;
const hasNextPage = ref(true);
const loadingMore = ref(false);
const allDataLoaded = ref(false);
const scrollPosition = ref(0);
const scrollContainer = ref(null);

const username = ref(null);
if (process.client) {
    username.value = localStorage.getItem('user_username') || '';
}

const getData = async () => {
    loadingMore.value = true;
    try {
        const response = await $GeneralNoteApiService.getAll('', page.value)
        if (response.results && response.results.length > 0) {
            if (response.next == null) {
                hasNextPage.value = false;
            }
            const newData = response.results;
            data.value = data.value.concat(newData);
            if (response.results.length < pageSize || !hasNextPage.value) {
                allDataLoaded.value = true;
            } else {
                page.value++;
            }
        } else {
            allDataLoaded.value = true;
        }

    } catch (err) {
        error.value = err
    } finally {
        loadingMore.value = false;
        nextTick(() => {
            if (scrollContainer.value) {
                scrollContainer.value.scrollTop = scrollPosition.value;
            }
        });
    }
}

const setAllToRead = async () => {
    try {
        await $GeneralNoteApiService.setAllToRead()
        sideBarStore.newGeneralNotesFound(0)
        resetData()
        await getData()
    } catch (err) {
        error.value = err
    }
}

const setAsRead = async (item) => {
    try {
        let save_data = {
            id: item.id,
        }
        await $GeneralNoteApiService.save(save_data)
        resetData()
        await getData()
        sideBarStore.newGeneralNotesFound(sideBarStore.newGeneralNotes - 1)
    } catch (err) {
        error.value = err
    }
}

const resetData = () => {
    page.value = 1
    data.value = []
    hasNextPage.value = true
    allDataLoaded.value = false
    loadingMore.value = false
    error.value = null
    isSubmitting.value = false
}

const onScroll = (event) => {
    const { scrollTop, scrollHeight, clientHeight } = event.target;
    scrollPosition.value = scrollTop; // Update the scroll position
    if (!hasNextPage.value || loadingMore.value) return;
    if (scrollTop + clientHeight >= scrollHeight - 20) {
        getData();
    }
};

const save = async () => {
    if (!new_note.value.trim() || isSubmitting.value) return

    isSubmitting.value = true
    try {
        const savedNote = await $GeneralNoteApiService.save({
            note: new_note.value
        })
        new_note.value = ''
        // L'usuari que envia l'avís també l'ha de veure com a Toast, igual que la resta d'usuaris.
        const senderUsername = savedNote.user ? savedNote.user.username : t('common.anonymous')
        toast.info(generalNoteToastContent(senderUsername, savedNote.note), { timeout: false, closeOnClick: false })
        // Es marca com a llegit pel propi autor perquè el poller global (layouts/default.vue)
        // no li torni a mostrar el mateix avís uns segons més tard.
        if (savedNote.id) {
            try {
                await $GeneralNoteApiService.save({ id: savedNote.id })
            } catch (err) {
                console.error('Error marking own general note as read:', err)
            }
        }
        resetData()
        await getData()
    } catch (err) {
        error.value = err
    } finally {
        isSubmitting.value = false
    }
}

const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault()
        save()
    }
}

onMounted(async () => {
    await getData(true)

})
</script>

<template>
    <div>
        <H1Region class="mb-2">
            {{ $t('dashboard.general_notes') }}
        </H1Region>

        <div v-if="error" class="mx-4 my-3 px-4 py-2 text-red-500 text-sm bg-red-50 rounded-md border border-red-100">
            {{ error }}
        </div>

        <div v-else class="p-4">
            <div class="mb-5">
                <div class="relative max-h-[100px]">
                    <textarea v-model="new_note" :placeholder="$t('dashboard.write_note')" @keypress="handleKeyPress"
                        rows="2"
                        class="w-full h-20 text-sm px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg resize-none" />
                    <button @click="save" :disabled="isSubmitting || !new_note.trim()"
                        class="absolute bottom-2 right-2 px-4 py-1.5 text-sm bg-sky-500 hover:bg-sky-700 text-white rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                        {{ $t('common.send') }}
                    </button>
                </div>
            </div>

            <div v-if="data && data.length > 0" class="space-y-2 max-h-[70vh] overflow-y-auto scrollbar-hide" @scroll="onScroll"
                ref="scrollContainer">
                <div v-for="note in data" :key="note.id" class="relative p-4 rounded-lg border border-slate-200" :class="{
                    'bg-slate-50': note.read_by.map(user => user.username).includes(username),
                    'bg-sky-50 font-semibold': !note.read_by.map(user => user.username).includes(username)
                }">
                    <div class="text-slate-700 text-sm mb-3 leading-relaxed whitespace-pre-wrap">
                        {{ note.note }}
                    </div>
                    <div class="flex justify-between items-center text-sm">
                        <div class="flex items-center gap-2 text-slate-500">
                            <span class="font-medium">
                                {{ note.user ? note.user.username : t('common.anonymous') }}
                            </span>
                            <span class="text-slate-400">•</span>
                            <TimeRelative :datetime="note.created_at" class="text-slate-400"></TimeRelative>
                        </div>
                    </div>
                    <button v-if="!note.read_by.map(user => user.username).includes(username)" 
                        @click="setAsRead(note)" 
                        class="absolute w-6 h-6 top-2 right-2 text-slate-400 hover:text-slate-700 hover:bg-white rounded hover:border hover:border-slate-300 flex items-center justify-center">
                        <Icon name="fa6-solid:eye" class="w-3.5 h-3.5" />
                    </button>
                </div>
                <div v-if="loadingMore" class="text-center text-slate-500 py-2">
                    <Icon name="fa6-solid:spinner" class="animate-spin" />
                    {{ $t('common.loading') }}...
                </div>
                <div v-if="allDataLoaded" class="text-center text-slate-500 py-2">
                    {{ $t('common.all_data_loaded') }}
                </div>
            </div>
            <div v-else class="text-center py-8">
                <div class="text-slate-400 text-sm">
                    {{ $t('common.no_data') }}
                </div>
            </div>
        </div>
    </div>
</template>
