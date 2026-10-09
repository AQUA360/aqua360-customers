<script setup>
import H1Region from '../atoms/H1Region.vue';
import { useToast } from 'vue-toastification';

const props = defineProps({
    data: Object
})

const emit = defineEmits(['exit'])
const { $CallRegisterApiService } = useNuxtApp()
const toast = useToast()
const { t } = useI18n();
const contact = ref(null)
const contract = ref(null)
const has_called = ref(false)
const time_called = ref(null)

const has_answered = ref(false)
const comment = ref(null)

const callPerson = () => {
    has_called.value = true
    time_called.value = new Date()
    window.location.href = `tel:${contact.value.phone}`
}

const saving = ref(false)

const cancel = () => {
    emit('exit')
}

const save = async () => {
    if (saving.value) return;
    if (!has_answered.value && (!comment.value || comment.value == '')) {
        if (!confirm(t('confirmation_text_block.confirm_exit_call'))) return;
    }
    saving.value = true
    try {
        let save_data = {
            contract: contract?.value?.id || null,
            person_contact: contact.value?.id || null,
            answered: has_answered.value,
            comment: comment.value,
            time_call: time_called.value || new Date(),
        }
        let response = await $CallRegisterApiService.save(save_data)
        if (response) {
            toast.success(t('common.correct_save'))
            emit('exit')
        }
    } catch (error) {
        console.error(error)
    } finally {
        saving.value = false
    }
}

onMounted(() => {
    contact.value = props.data.contact
    contract.value = props.data.contract
})

</script>

<template>
    <div v-if="contact || contract" class="bg-white rounded-lg py-2 mx-auto">
        <div class="flex items-center justify-between mb-6 pb-2 border-b border-slate-200">
            <H1Region>{{ $t('contract_block.call_register') }}</H1Region>
            <div class="flex items-center gap-2">
                                <span v-if="contract"
                    class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                    {{ t('contract') }}: {{ contract.token }}
                </span>
            </div>
        </div>

        <div class="grid grid-cols-3 gap-4 mb-6">
            <div class="col-span-2">
                <div class="bg-sky-100 rounded-lg p-4">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 bg-white rounded-full flex items-center justify-center">
                            <Icon name="fa6-solid:user" class="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <h3 class="font-medium text-slate-900">{{ contact?.person_full_name }}</h3>
                            <p class="text-sm text-slate-600">{{ contact?.person_token }}</p>
                            <p class="text-sm text-slate-600">{{ $t('common.tlf') }}: {{ contact?.phone }}</p>
                        </div>
                    </div>
                </div>
            </div>

            <div class="flex flex-col gap-3">
                <button @click="callPerson()" :disabled="has_called"
                    class="w-full button-primary flex items-center justify-center gap-2 py-3 px-4 rounded-lg font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed">
                    <Icon :name="has_called ? 'fa6-solid:phone-slash' : 'fa6-solid:phone'" class="w-4 h-4" />
                    {{ has_called ? $t('contract_block.called') : $t('contract_block.call') }}
                </button>

                <div v-if="has_called && time_called" class="text-center">
                    <p class="text-xs text-slate-500">{{ $t('contract_block.called_at') }}</p>
                    <p class="text-sm font-medium text-slate-900">{{ new Date(time_called).toLocaleTimeString() }}</p>
                </div>
            </div>
        </div>

        <div class="space-y-4 mb-6">
            <div class="flex items-center gap-3 p-3 bg-sky-100 rounded-lg">
                <input type="checkbox" id="has_answered" v-model="has_answered"
                    class="w-4 h-4 text-primary border-slate-300 rounded" />
                <label for="has_answered" class="text-sm font-medium text-slate-700 cursor-pointer">
                    {{ $t('contract_block.has_answered') }}
                </label>
            </div>

            <div>
                <label for="comment" class="block text-sm font-medium text-slate-700 mb-2">
                    {{ $t('common.comment') }}
                </label>
                <textarea id="comment" v-model="comment" :placeholder="t('common.write_comment')" rows="3"
                    class="w-full border border-slate-300 rounded-lg p-3 text-sm focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary resize-none"></textarea>
            </div>
        </div>

        <div class="flex justify-end gap-2 pt-4 border-t border-slate-200">
            <button type="button" @click="cancel()" :disabled="saving" class="button-secondary flex items-center gap-2">
                <Icon name="fa6-solid:xmark" class="w-3 h-3" />
                {{ $t('common.cancel') }}
            </button>
            <button @click="save()" :disabled="saving" class="button-primary flex items-center gap-2">
                <Icon name="fa6-solid:circle-check" class="w-3 h-3" />
                {{ $t('common.finish') }}
            </button>
        </div>
    </div>
</template>
