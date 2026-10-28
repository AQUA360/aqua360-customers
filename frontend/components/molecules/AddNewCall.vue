<script setup>
import H1Region from '../atoms/H1Region.vue';
import { useToast } from 'vue-toastification';

const props = defineProps({
    data: Object
})

const emit = defineEmits(['exit'])
const { $CallRegisterApiService, $UserApiService, $IncidentApiService, $ConfiglistApiService, $ContractApiService } = useNuxtApp()
const toast = useToast()
const { t } = useI18n();

const contact = ref(null)
const contract = ref(null)
const incident = ref(null)
const isManual = ref(false)
const selectedContactOption = ref(null)
const freeContactEntry = ref(false)

const has_called = ref(false)
const time_called = ref(null)
const call_start = ref('')
const call_end = ref('')
const wait_time = ref(null)
const abandoned_call = ref(false)
const has_answered = ref(false)
const comment = ref(null)
const contacted_by_client = ref(false)
const channel = ref('PHONE')

const users = ref([])
const transfered_to = ref(null)
const transfered_to_custom = ref(false)
const transfered_to_name = ref('')
const transfered_from = ref(null)
const transfered_from_custom = ref(false)
const transfered_from_name = ref('')

const incident_option = ref('none') // 'none' | 'existing' | 'new'
const contract_incidents = ref([])
const selected_incident = ref(null)
const new_incident_name = ref('')
const new_incident_type = ref(null)
const incident_types = ref([])

const phone = ref('')
const email = ref('')

const saving = ref(false)

const isMakingCall = computed(() => !contacted_by_client.value)
const showCallTiming = computed(() => channel.value === 'PHONE' && (has_called.value || isManual.value))
const showIncidentOptions = computed(() => !!contract.value?.id && !incident.value?.id)

const contractContacts = computed(() => {
    const list = contract.value?.contacts
    if (!Array.isArray(list)) return []
    return list.filter(c => c && c.is_active !== false)
})

const phoneContactOptions = computed(() =>
    contractContacts.value
        .filter(c => c.phone)
        .map(c => ({
            code: c.id,
            label: [c.person_full_name || c.role, c.phone].filter(Boolean).join(' · '),
            contact: c,
        }))
)

const emailContactOptions = computed(() =>
    contractContacts.value
        .filter(c => c.email)
        .map(c => ({
            code: c.id,
            label: [c.person_full_name || c.role, c.email].filter(Boolean).join(' · '),
            contact: c,
        }))
)

const channelContactOptions = computed(() =>
    channel.value === 'PHONE' ? phoneContactOptions.value : emailContactOptions.value
)

const canPickContractContact = computed(() =>
    isManual.value && !!contract.value?.id && channelContactOptions.value.length > 0
)

const callDurationMs = computed(() => {
    if (!call_start.value || !call_end.value) return null
    const ms = new Date(call_end.value) - new Date(call_start.value)
    if (Number.isNaN(ms) || ms < 0) return null
    return ms
})

const callDuration = computed(() => {
    if (callDurationMs.value == null) return null
    const totalSeconds = Math.floor(callDurationMs.value / 1000)
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return `${mins}:${String(secs).padStart(2, '0')}`
})

// Wait time must fit inside the call (start → end)
const maxWaitMinutes = computed(() => {
    if (callDurationMs.value == null) return null
    return Math.floor(callDurationMs.value / 60000)
})

const canSetWaitTime = computed(() => maxWaitMinutes.value != null)

watch([call_start, call_end, wait_time], () => {
    if (wait_time.value === null || wait_time.value === '') return
    const value = Number(wait_time.value)
    if (Number.isNaN(value) || value < 0) {
        wait_time.value = 0
        return
    }
    if (maxWaitMinutes.value == null) {
        wait_time.value = null
        return
    }
    if (value > maxWaitMinutes.value) {
        wait_time.value = maxWaitMinutes.value
    }
})

watch(contacted_by_client, (byClient) => {
    if (byClient) has_answered.value = true
})

watch(selectedContactOption, (opt) => {
    if (!opt?.contact) return
    contact.value = opt.contact
    if (channel.value === 'PHONE') {
        phone.value = opt.contact.phone || ''
    } else {
        email.value = opt.contact.email || ''
    }
})

watch(channel, () => {
    selectedContactOption.value = null
    freeContactEntry.value = false
})

watch(freeContactEntry, (free) => {
    if (free) {
        selectedContactOption.value = null
        // Keep typed values; drop linked person_contact unless outbound already set it
        if (isManual.value && !props.data?.contact) {
            contact.value = null
        }
    }
})

const toLocalDatetime = (date = new Date()) => {
    const d = new Date(date)
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const toISO = (local) => {
    if (!local) return null
    const date = new Date(local)
    return Number.isNaN(date.getTime()) ? null : date.toISOString()
}
// Dades d'atenció: sentit, retorn de trucada, supervisor, transferència i consentiment de gravació
const direction = ref('outbound')
const callback_requested = ref(false)
const supervisor_requested = ref(false)
const transferred_to = ref('')
const recording_consent = ref(false)

const callPerson = () => {
    has_called.value = true
    time_called.value = new Date()
    if (!call_start.value) {
        call_start.value = toLocalDatetime(time_called.value)
    }
    contacted_by_client.value = false
    channel.value = 'PHONE'
    if (contact.value?.phone) {
        window.location.href = `tel:${contact.value.phone}`
    }
}

const cancel = () => {
    emit('exit')
}

const getUsers = async () => {
    try {
        const response = await $UserApiService.getAll()
        users.value = (response.results || []).map(user => ({
            label: user.first_name && user.last_name
                ? `${user.first_name} ${user.last_name}`
                : user.username,
            code: user.id,
            username: user.username
        }))
    } catch (error) {
        console.error(error)
    }
}

const getContractIncidents = async () => {
    if (!contract.value?.id) return
    try {
        const response = await $IncidentApiService.getAll('', [], 1, null, false, contract.value.id)
        contract_incidents.value = (response.results || []).map(item => ({
            label: `${item.token || ''} - ${item.name || ''}`.trim(),
            code: item.id,
            token: item.token,
            name: item.name
        }))
    } catch (error) {
        console.error(error)
    }
}

const getIncidentTypes = async () => {
    try {
        const result = await $ConfiglistApiService.getAll('notification/incident-type')
        incident_types.value = (result.results || []).map(type => ({
            label: type.name,
            code: type.id
        }))
    } catch (error) {
        console.error(error)
    }
}

const ensureContractContacts = async () => {
    if (!contract.value?.id) return
    if (Array.isArray(contract.value.contacts)) return
    try {
        const detail = await $ContractApiService.getDetail(contract.value.id)
        if (detail) {
            contract.value = { ...contract.value, ...detail }
        }
    } catch (error) {
        console.error(error)
    }
}

const matchContactByValue = () => {
    if (!isManual.value || !canPickContractContact.value || freeContactEntry.value) return
    if (selectedContactOption.value) return

    if (channel.value === 'PHONE' && phone.value) {
        const match = phoneContactOptions.value.find(o => o.contact.phone === phone.value)
        if (match) {
            selectedContactOption.value = match
            contact.value = match.contact
        }
    } else if (channel.value === 'EMAIL' && email.value) {
        const match = emailContactOptions.value.find(o => o.contact.email === email.value)
        if (match) {
            selectedContactOption.value = match
            contact.value = match.contact
        }
    }
}

const resolveIncidentId = async () => {
    if (incident.value?.id) return incident.value.id
    if (!showIncidentOptions.value) return null

    if (incident_option.value === 'existing') {
        return selected_incident.value?.code || null
    }

    if (incident_option.value === 'new') {
        if (!new_incident_name.value || !new_incident_type.value?.code) {
            toast.warning(t('contract_block.incident_required_fields'))
            return false
        }
        const created = await $IncidentApiService.save({
            name: new_incident_name.value,
            type: new_incident_type.value.code,
            contract: contract.value.id,
            description: comment.value || ''
        })
        return created?.id || null
    }

    return null
}

const save = async () => {
    if (saving.value) return
    if (!contacted_by_client.value && !has_answered.value && (!comment.value || comment.value === '')) {
        if (!confirm(t('confirmation_text_block.confirm_exit_call'))) return
    }
    saving.value = true
    try {
        const incidentId = await resolveIncidentId()
        if (incidentId === false) return

        const makingCall = isManual.value ? !contacted_by_client.value : true
        const byClient = isManual.value ? contacted_by_client.value : false
        const callChannel = isManual.value ? channel.value : 'PHONE'

        const save_data = {
            contract: contract.value?.id || null,
            incident: props.data.incident?.id || null,
            person_contact: contact.value?.id || null,
            incident: incidentId,
            answered: byClient ? true : has_answered.value,
            comment: comment.value,
            time_call: time_called.value || new Date(),
            call_start: toISO(call_start.value),
            call_end: toISO(call_end.value),
            wait_time: (() => {
                if (!showCallTiming.value || !canSetWaitTime.value) return null
                if (wait_time.value === null || wait_time.value === '') return null
                const value = Number(wait_time.value)
                if (Number.isNaN(value) || value < 0) return null
                return Math.min(value, maxWaitMinutes.value)
            })(),
            direction: direction.value,
            callback_requested: callback_requested.value,
            supervisor_requested: supervisor_requested.value,
            transferred_to: transferred_to.value || null,
            recording_consent: recording_consent.value,
            abandoned_call: abandoned_call.value,
            contacted_by_client: byClient,
            channel: callChannel,
            phone: callChannel === 'PHONE'
                ? (phone.value || contact.value?.phone || null)
                : null,
            email: callChannel === 'EMAIL'
                ? (email.value || contact.value?.email || null)
                : null,
            transfered_to: (!transfered_to_custom.value && makingCall)
                ? (transfered_to.value?.code || null)
                : null,
            transfered_to_name: (transfered_to_custom.value)
                ? (transfered_to_name.value || null)
                : null,
            transfered_from: (!transfered_from_custom.value)
                ? (transfered_from.value?.code || null)
                : null,
            transfered_from_name: (transfered_from_custom.value)
                ? (transfered_from_name.value || null)
                : null,
        }

        const response = await $CallRegisterApiService.save(save_data)
        if (response) {
            toast.success(t('common.correct_save'))
            emit('exit')
        }
    } catch (error) {
        console.error(error)
        toast.error(t('common.error_save') || t('common.error'))
    } finally {
        saving.value = false
    }
}

onMounted(async () => {
    contact.value = props.data?.contact || null
    contract.value = props.data?.contract || null
    incident.value = props.data?.incident || null
    isManual.value = props.data?.mode === 'manual'

    phone.value = contact.value?.phone || ''
    email.value = contact.value?.email || ''

    if (!isManual.value) {
        contacted_by_client.value = false
        channel.value = 'PHONE'
    }

    await Promise.all([
        getUsers(),
        ensureContractContacts(),
        showIncidentOptions.value ? getContractIncidents() : Promise.resolve(),
        showIncidentOptions.value ? getIncidentTypes() : Promise.resolve(),
    ])

    if (isManual.value && contact.value?.id) {
        const options = channelContactOptions.value
        const match = options.find(o => o.code === contact.value.id)
        if (match) selectedContactOption.value = match
        else freeContactEntry.value = true
    }
})

</script>

<template>
    <div v-if="contact || contract || incident || isManual"
        class="bg-white rounded-xl mx-auto max-h-[90vh] overflow-y-auto">
        <!-- Header -->
        <div class="flex items-start justify-between gap-3 mb-4 pb-3 border-b border-sky-100">
            <div>
                <H1Region>{{ $t('contract_block.call_register') }}</H1Region>
                <p v-if="has_called && time_called" class="mt-0.5 text-xs text-slate-400">
                    {{ $t('contract_block.called_at') }}
                    <span class="font-medium text-sky-700">{{ new Date(time_called).toLocaleTimeString() }}</span>
                </p>
            </div>
            <div class="flex flex-wrap items-center justify-end gap-1.5">
                <span v-if="contract"
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium tracking-wide bg-sky-50 text-sky-800 ring-1 ring-sky-200/80">
                    {{ t('contract') }} {{ contract.token || contract.id }}
                </span>
                <span v-if="incident"
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium tracking-wide bg-sky-50 text-sky-800 ring-1 ring-sky-200/80">
                    {{ t('incident') }} {{ incident.token || incident.id }}
                </span>
            </div>
        </div>

        <!-- Contact + call action -->
        <div v-if="contact"
            class="flex items-center gap-3 mb-4 p-3 rounded-xl bg-gradient-to-br from-sky-50 to-sky-100/50 ring-1 ring-sky-200/70">
            <div
                class="w-9 h-9 shrink-0 rounded-full bg-white ring-1 ring-sky-200/80 flex items-center justify-center shadow-sm">
                <Icon name="fa6-solid:user" class="w-3.5 h-3.5 text-sky-600" />
            </div>
            <div class="min-w-0 flex-1">
                <p class="text-sm font-semibold text-slate-900 truncate">{{ contact?.person_full_name }}</p>
                <p class="text-xs text-slate-500 truncate">
                    <span v-if="contact?.person_token">{{ contact.person_token }}</span>
                    <span v-if="contact?.phone"> · {{ contact.phone }}</span>
                    <span v-if="contact?.email"> · {{ contact.email }}</span>
                </p>
            </div>
            <button v-if="!isManual || channel === 'PHONE'" type="button" @click="callPerson()"
                :disabled="has_called || !contact?.phone" class="shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all
                    disabled:opacity-40 disabled:cursor-not-allowed
                    button-primary !py-1.5 !px-3">
                <Icon :name="has_called ? 'fa6-solid:phone-slash' : 'fa6-solid:phone'" class="w-3 h-3" />
                {{ has_called ? $t('contract_block.called') : $t('contract_block.call') }}
            </button>
        </div>

        <div class="space-y-4">
            <!-- Channel / contact / direction -->
            <div v-if="isManual" class="space-y-2.5">
                <div class="flex flex-wrap items-center gap-2">
                    <div class="inline-flex p-0.5 rounded-lg bg-sky-50 ring-1 ring-sky-200/80">
                        <button type="button" @click="channel = 'PHONE'"
                            class="px-2.5 py-1 rounded-md text-xs font-medium transition-all" :class="channel === 'PHONE'
                                ? 'bg-white text-sky-800 shadow-sm ring-1 ring-sky-200'
                                : 'text-slate-500 hover:text-sky-700'">
                            <Icon name="fa6-solid:phone" class="w-3 h-3 inline mr-1 opacity-70" />
                            {{ $t('contract_block.channel_phone') }}
                        </button>
                        <button type="button" @click="channel = 'EMAIL'"
                            class="px-2.5 py-1 rounded-md text-xs font-medium transition-all" :class="channel === 'EMAIL'
                                ? 'bg-white text-sky-800 shadow-sm ring-1 ring-sky-200'
                                : 'text-slate-500 hover:text-sky-700'">
                            <Icon name="fa6-solid:envelope" class="w-3 h-3 inline mr-1 opacity-70" />
                            {{ $t('contract_block.channel_email') }}
                        </button>
                    </div>

                    <button type="button" @click="contacted_by_client = !contacted_by_client"
                        class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ring-1"
                        :class="contacted_by_client
                            ? 'bg-sky-50 text-sky-800 ring-sky-200'
                            : 'bg-white text-slate-500 ring-slate-200 hover:text-slate-700'">
                        <Icon name="fa6-solid:arrow-right-to-bracket" class="w-3 h-3" />
                        {{ $t('contract_block.contacted_by_client') }}
                    </button>
                </div>

                <div class="max-w-md space-y-1.5">
                    <div class="flex items-center justify-between gap-2 min-h-[1.25rem]">
                        <label class="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                            {{ channel === 'PHONE' ? $t('common.tlf') : $t('common.email') }}
                        </label>
                        <button v-if="canPickContractContact" type="button"
                            @click="freeContactEntry = !freeContactEntry"
                            class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ring-1"
                            :class="freeContactEntry
                                ? 'bg-sky-50 text-sky-800 ring-sky-200'
                                : 'bg-white text-sky-700 ring-sky-200 hover:bg-sky-50'">
                            <Icon :name="freeContactEntry ? 'fa6-solid:address-book' : 'fa6-solid:pen'"
                                class="w-3 h-3" />
                            {{ freeContactEntry
                                ? $t('contract_block.select_contract_contact')
                                : $t('contract_block.free_contact_entry') }}
                        </button>
                    </div>

                    <v-select v-if="canPickContractContact && !freeContactEntry" v-model="selectedContactOption"
                        :options="channelContactOptions" class="w-full text-sm"
                        :placeholder="$t('contract_block.select_contract_contact')" />
                    <template v-else>
                        <input v-if="channel === 'PHONE'" type="text" v-model="phone" class="input w-full text-sm"
                            @blur="matchContactByValue" />
                        <input v-else type="text" v-model="email" class="input w-full text-sm"
                            @blur="matchContactByValue" />
                    </template>
                </div>
            </div>

            <!-- Timing -->
            <div v-if="showCallTiming" class="rounded-xl bg-sky-50/60 ring-1 ring-sky-200/70 p-3">
                <div class="flex flex-wrap items-end gap-3">
                    <div class="min-w-[10.5rem] flex-1">
                        <label class="block text-[11px] font-medium uppercase tracking-wide text-sky-700/70 mb-1">
                            {{ $t('contract_block.call_start') }}
                        </label>
                        <input type="datetime-local" v-model="call_start" class="input w-full text-sm" />
                    </div>
                    <div class="min-w-[10.5rem] flex-1">
                        <label class="block text-[11px] font-medium uppercase tracking-wide text-sky-700/70 mb-1">
                            {{ $t('contract_block.call_end') }}
                        </label>
                        <input type="datetime-local" v-model="call_end" class="input w-full text-sm"
                            :min="call_start || undefined" />
                    </div>
                </div>
                <div class="flex flex-wrap items-end gap-3 mt-1">
                    <div class="w-36 shrink-0">
                        <label class="block text-[11px] font-medium uppercase tracking-wide text-sky-700/70 mb-1">
                            {{ $t('contract_block.wait_time') }}
                        </label>
                        <input type="number" min="0" :max="maxWaitMinutes ?? undefined" v-model="wait_time"
                            class="input w-full text-sm tabular-nums disabled:opacity-40 disabled:cursor-not-allowed"
                            :disabled="!canSetWaitTime" :placeholder="$t('contract_block.minutes')" />
                    </div>
                    <div v-if="callDuration"
                        class="shrink-0 mb-0.5 inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-white ring-1 ring-sky-200 text-xs text-sky-800">
                        <Icon name="fa6-solid:stopwatch" class="w-3 h-3 text-sky-600" />
                        <span class="font-semibold tabular-nums">{{ callDuration }}</span>
                    </div>
                </div>
            </div>

            <!-- Status chips -->
            <div class="flex flex-wrap items-center gap-2">
                <button type="button" @click="!contacted_by_client && (has_answered = !has_answered)"
                    :disabled="contacted_by_client"
                    class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ring-1 disabled:cursor-default"
                    :class="has_answered || contacted_by_client
                        ? 'bg-sky-50 text-sky-800 ring-sky-200'
                        : 'bg-white text-slate-500 ring-slate-200 hover:text-sky-700 hover:ring-sky-200'">
                    <Icon
                        :name="(has_answered || contacted_by_client) ? 'fa6-solid:circle-check' : 'fa6-regular:circle'"
                        class="w-3 h-3" />
                    {{ $t('contract_block.has_answered') }}
                </button>
                <button v-if="channel === 'PHONE'" type="button" @click="abandoned_call = !abandoned_call"
                    class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-all ring-1"
                    :class="abandoned_call
                        ? 'bg-amber-50 text-amber-800 ring-amber-200'
                        : 'bg-white text-slate-500 ring-slate-200 hover:text-sky-700 hover:ring-sky-200'">
                    <Icon name="fa6-solid:phone-slash" class="w-3 h-3" />
                    {{ $t('contract_block.abandoned_call') }}
                </button>
            </div>

            <!-- Transfers -->
            <div v-if="isMakingCall || isManual || contacted_by_client"
                class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1 border-t border-sky-100">
                <div v-if="isManual || contacted_by_client" class="space-y-1.5">
                    <div class="flex items-center justify-between gap-2 min-h-[1.25rem]">
                        <label class="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                            {{ $t('contract_block.transfered_to') }}
                        </label>
                        <button type="button" @click="transfered_to_custom = !transfered_to_custom"
                            class="text-[11px] font-medium transition-colors"
                            :class="transfered_to_custom ? 'text-sky-700' : 'text-slate-400 hover:text-slate-600'">
                            {{ $t('contract_block.user_not_registered') }}
                        </button>
                    </div>
                    <v-select v-if="!transfered_to_custom" v-model="transfered_to" :options="users"
                        class="w-full text-sm" :placeholder="$t('contract_block.transfered_to')" />
                    <input v-else type="text" v-model="transfered_to_name" class="input w-full text-sm"
                        :placeholder="$t('contract_block.transfered_to_name')" />
                </div>

                <div v-if="isManual || contacted_by_client" class="space-y-1.5">
                    <div class="flex items-center justify-between gap-2 min-h-[1.25rem]">
                        <label class="text-[11px] font-medium uppercase tracking-wide text-slate-400">
                            {{ $t('contract_block.transfered_from') }}
                        </label>
                        <button type="button" @click="transfered_from_custom = !transfered_from_custom"
                            class="text-[11px] font-medium transition-colors"
                            :class="transfered_from_custom ? 'text-sky-700' : 'text-slate-400 hover:text-slate-600'">
                            {{ $t('contract_block.user_not_registered') }}
                        </button>
                    </div>
                    <v-select v-if="!transfered_from_custom" v-model="transfered_from" :options="users"
                        class="w-full text-sm" :placeholder="$t('contract_block.transfered_from')" />
                    <input v-else type="text" v-model="transfered_from_name" class="input w-full text-sm"
                        :placeholder="$t('contract_block.transfered_from_name')" />
                </div>
            </div>

            <!-- Incident -->
            <div v-if="showIncidentOptions" class="space-y-2 pt-1 border-t border-sky-100">
                <label class="block text-[11px] font-medium uppercase tracking-wide text-sky-700/70">
                    {{ $t('contract_block.incident_option') }}
                </label>
                <div class="inline-flex flex-wrap p-0.5 rounded-lg bg-sky-50 ring-1 ring-sky-200/80 gap-0.5">
                    <button type="button" @click="incident_option = 'none'"
                        class="px-2.5 py-1 rounded-md text-xs font-medium transition-all" :class="incident_option === 'none'
                            ? 'bg-white text-sky-800 shadow-sm ring-1 ring-sky-200'
                            : 'text-slate-500 hover:text-sky-700'">
                        {{ $t('contract_block.no_incident') }}
                    </button>
                    <button type="button" @click="incident_option = 'existing'"
                        class="px-2.5 py-1 rounded-md text-xs font-medium transition-all" :class="incident_option === 'existing'
                            ? 'bg-white text-sky-800 shadow-sm ring-1 ring-sky-200'
                            : 'text-slate-500 hover:text-sky-700'">
                        {{ $t('contract_block.select_incident') }}
                    </button>
                    <button type="button" @click="incident_option = 'new'"
                        class="px-2.5 py-1 rounded-md text-xs font-medium transition-all" :class="incident_option === 'new'
                            ? 'bg-white text-sky-800 shadow-sm ring-1 ring-sky-200'
                            : 'text-slate-500 hover:text-sky-700'">
                        {{ $t('contract_block.create_incident') }}
                    </button>
                </div>

                <div v-if="incident_option === 'existing'" class="max-w-md">
                    <v-select v-model="selected_incident" :options="contract_incidents" class="w-full text-sm"
                        :placeholder="$t('contract_block.select_incident')" />
                </div>

                <div v-if="incident_option === 'new'" class="grid grid-cols-1 sm:grid-cols-2 gap-2.5 max-w-xl">
                    <div>
                        <label class="block text-[11px] font-medium uppercase tracking-wide text-slate-400 mb-1">
                            {{ $t('common.title') }}
                        </label>
                        <input type="text" v-model="new_incident_name" class="input w-full text-sm" />
                    </div>
                    <div>
                        <label class="block text-[11px] font-medium uppercase tracking-wide text-slate-400 mb-1">
                            {{ $t('common.type') }}
                        </label>
                        <v-select v-model="new_incident_type" :options="incident_types" class="w-full text-sm" />
                    </div>
                </div>
            </div>

            <!-- Comment -->
            <div>
                <label for="comment" class="block text-[11px] font-medium uppercase tracking-wide text-slate-400 mb-1">
                    {{ $t('common.comment') }}
                </label>
                <textarea id="comment" v-model="comment" :placeholder="t('common.write_comment')" rows="2"
                    class="input w-full text-sm resize-none min-h-[4rem]"></textarea>
            </div>
        </div>

        <div class="flex justify-end gap-2 mt-5 pt-3 border-t border-sky-100">
            <button type="button" @click="cancel()" :disabled="saving"
                class="button-default flex items-center gap-2 !py-1.5">
                {{ $t('common.cancel') }}
            </button>
            <button @click="save()" :disabled="saving" class="button-primary flex items-center gap-2 !py-1.5">
                <Icon name="fa6-solid:circle-check" class="w-3 h-3" />
                {{ $t('common.finish') }}
            </button>
        </div>
    </div>
</template>
