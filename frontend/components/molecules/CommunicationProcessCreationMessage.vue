<script setup>
import SearchEntityInput from './SearchEntityInput.vue';
import CommunicationProcessCreationSetupContract from './CommunicationProcessCreationSetupContract.vue';
import { useToast } from 'vue-toastification';

const props = defineProps({
    message: Object,
    persons: Array,
    is_region: {
        type: Boolean,
        default: false
    },
    contract_id: Number,
    // Token de l'origen a preseleccionar segons el context del pas 1 (p. ex. 'billing')
    defaultOriginToken: {
        type: String,
        default: null,
    },
})

const emit = defineEmits(['change', 'load'])
const { t } = useI18n();
const { $ConfiglistApiService, $CommunicationProcessApiService, $MessageTemplateApiService } = useNuxtApp();
const toast = useToast();
const loadingOrigins = ref(false)
const loadingTemplates = ref(false)

const stopWatch = ref(false)

const origins = ref([])
const templates = ref([])
const message_type_templates = ref([])

const selectedOrigin = ref(null)
const selectedTemplate = ref(null)
const selectedMessageTypes = ref([])
const preferedType = ref(null)

const messageData = ref({})

const persons_no_contracts = computed(() => {
    if (props.persons) {
        return props.persons.some(person => !person?.contracts)
    }
    return true
})

// 'Predefinit al contracte' només es pot triar si totes les persones tenen contractes
const canUseContractDefault = computed(() => !(persons_no_contracts.value && !props.contract_id))

/* const handlePreferredSelect = (id) => {
    message_type_templates.value.forEach(template => {
        if (template.id === id) {
            template.preferred = true;
            preferedType.value = template;
        } else {
            template.preferred = false;
        }
    });
    emitChange()
} */

const fetchConfigData = async (service, entity, targetArray, loading) => {
    try {
        loading.value = true;
        const data = await $ConfiglistApiService.getAll(service + '/' + entity);
        targetArray.value = [];

        if (data.results) {
            data.results.forEach(data => {
                targetArray.value.push({
                    label: data.name || data.token,
                    code: data.id,
                    token: data.token
                })
            });
        }
    } catch (error) {
        console.error(`Error fetching ${entity}:`, error);
    } finally {
        loading.value = false;
    }
}

const getMessageTemplates = async () => {
    try {
        templates.value = []
        message_type_templates.value = []
        //preferedType.value = null
        let sel_origin = selectedOrigin.value?.code ? selectedOrigin.value.code : null
        const response = await $MessageTemplateApiService.getAll('', [], 1, null, false, sel_origin)
        response.results.forEach(data => {
            templates.value.push({
                label: data.name || data.token,
                code: data.id
            })
        })
    } catch (error) {
        console.error(error)
    }
}

// applyDefaults: preselecciona el canal quan l'usuari tria plantilla (no en restaurar dades desades)
const getMessageTypeTemplates = async (applyDefaults = false) => {
    try {
        if (selectedTemplate.value) {
            const response = await $MessageTemplateApiService.getMessageTypeTemplates(selectedTemplate.value.code)
            message_type_templates.value = response.results
            const singleTemplateId = message_type_templates.value.length == 1 ? message_type_templates.value[0].id : null
            message_type_templates.value.unshift({
                id: 'default',
                type: {
                    name: t('customer_service_block.contract_default')
                }
            })
            if (applyDefaults) {
                if (canUseContractDefault.value) {
                    handleTypeChecked('default')
                } else if (singleTemplateId) {
                    handleTypeChecked(singleTemplateId)
                }
            }
        } else {
            message_type_templates.value = []
        }
    } catch (error) {
        console.error(error)
    }
}

const handleTypeChecked = (id) => {
    const message_type_template = message_type_templates.value.find(message_type_template => message_type_template.id == id)
    
    if (id === 'default') {
        message_type_templates.value.forEach(template => {
            template.checked = false
        })
        message_type_template.checked = true
    } else {
        message_type_templates.value.forEach(template => {
            if (template.id === 'default') {
                template.checked = false
            }
        })
        message_type_template.checked = !message_type_template.checked
    }

    selectedMessageTypes.value = message_type_templates.value.filter(message_type_template => message_type_template.checked)
    emitChange()
}

const loadData = async () => {
    await fetchConfigData('communication', 'message-origin', origins, loadingOrigins)
    await getMessageTemplates()
    if (!props.message?.message_template) {
        await applyContextDefaults()
    } else {
        messageData.value = props.message
        selectedOrigin.value = origins.value.find(origin => origin.code == messageData.value.origin)
        selectedTemplate.value = templates.value.find(template => template.code == messageData.value.message_template)
        await getMessageTypeTemplates()
        //preferedType.value = message_type_templates.value.find(message_type_template => message_type_template.id == messageData.value.prefered_type)
        const messageTypeIds = messageData.value.message_types?messageData.value.message_types.map(mt => mt !== null ? mt.id : mt): [];
        selectedMessageTypes.value = message_type_templates.value.filter(message_type_template => messageTypeIds.includes(message_type_template.id))
        message_type_templates.value.forEach(message_type_template => {
            /* if (message_type_template.id == messageData.value.prefered_type) {
                message_type_template.preferred = true
            } */
            if (messageTypeIds.includes(message_type_template.id)) {
                message_type_template.checked = true
            }
        })
    }
    //await fetchConfigData('communication', 'message-type', message_types, loadingMessageTypes)
}

// Sense dades desades: origen segons el context del pas 1 i, si només hi ha una plantilla, aquesta
const applyContextDefaults = async () => {
    const origin = props.defaultOriginToken ? origins.value.find(o => o.token == props.defaultOriginToken) : null
    if (!origin) return
    selectedOrigin.value = origin
    await getMessageTemplates()
    if (templates.value.length == 1) {
        selectedTemplate.value = templates.value[0]
        await getMessageTypeTemplates(true)
    }
}

const emitChange = () => {
    messageData.value = {
        origin: selectedOrigin.value.code,
        message_template: selectedTemplate.value.code,
        message_types: selectedMessageTypes.value,
        message_type_ids: selectedMessageTypes.value.map(message_type_template => message_type_template.id).includes('default') ?
            selectedMessageTypes.value.map(message_type_template => message_type_template.id) :
            selectedMessageTypes.value.map(message_type_template => message_type_template.type.id),
        message_type_names: selectedMessageTypes.value.map(message_type_template => message_type_template.type.name),
        type_ids: selectedMessageTypes.value.filter(msg => msg.type?.id).map(msg => msg.type.id)

    }
    emit('change', messageData.value)
}

watch(selectedTemplate, async (newVal) => {
    if (stopWatch.value) return
    if (newVal) {
        await getMessageTypeTemplates(true)
    }
})

watch(selectedOrigin, async (newVal) => {
    if (stopWatch.value) return
    if (newVal) {
        selectedTemplate.value = null
        await getMessageTemplates()
        if (templates.value.length == 1) {
            selectedTemplate.value = templates.value[0]
        }
    }
})

watch(props.message, async (newVal) => {
    if (newVal) {
        stopWatch.value = true
        messageData.value = newVal
        selectedOrigin.value = origins.value.find(origin => origin.code == newVal.origin)
        selectedTemplate.value = templates.value.find(template => template.code == newVal.message_template)
        await getMessageTypeTemplates()
        //preferedType.value = message_type_templates.value.find(message_type_template => message_type_template.id == newVal.prefered_type)
        const messageTypeIds = newVal.message_types? newVal.message_types.map(mt => mt !== null ? mt.id : mt) : [];
        selectedMessageTypes.value = message_type_templates.value.filter(message_type_template => messageTypeIds.includes(message_type_template.id))
        message_type_templates.value.forEach(message_type_template => {
            if (messageTypeIds.includes(message_type_template.id)) {
                message_type_template.checked = true
            } else {
                message_type_template.checked = false
            }
        })
        stopWatch.value = false
    }
})

onMounted(async () => {
    stopWatch.value = true
    await loadData()
    stopWatch.value = false
    
})

</script>

<template>
    <div class="rounded-lg shadow-sm" :class="{ 'p-3 bg-white': !is_region }">
        <!-- FILTER SELECT -->
        <h3 v-if="!is_region" class="text-md font-medium text-gray-900 mb-3">{{ t('customer_service_block.select_comm') }}</h3>
        <div class="grid grid-cols-2 gap-2">
            <div class="mb-5">
                <label class="block text-sm font-medium text-gray-700">{{ t('common.origin') }}</label>
                <v-select class="block w-full mr-2 required" :disabled="loadingOrigins || origins.length == 0"
                    :model-value="selectedOrigin" @update:modelValue="selectedOrigin = $event"
                    :options="origins"></v-select>
            </div>
            <div class="mb-5">
                <label class="block text-sm font-medium text-gray-700">{{ t('common.template') }}</label>
                <v-select class="block w-full mr-2 required" :options="templates"
                    :disabled="loadingTemplates || templates.length == 0 || selectedOrigin == null"
                    :model-value="selectedTemplate" @update:modelValue="selectedTemplate = $event"></v-select>
            </div>
        </div>

        <hr class="my-2">
        <div v-if="message_type_templates.length > 0">
            <div v-for="message in message_type_templates">
                <div class="grid grid-cols-[auto,1fr] items-center gap-2 px-3 py-1.5 rounded-md transition-all duration-200 mb-2"
                    :class="[
                        message.checked ? 
                        'bg-sky-50 ring-1 ring-sky-500 bg-white cursor-pointer' : 
                        (persons_no_contracts && !contract_id) && message.id == 'default' ? 'opacity-50 cursor-not-allowed' : 
                        'hover:bg-gray-50 cursor-pointer']"
                    @click="(persons_no_contracts && !contract_id) && message.id == 'default' ? null : handleTypeChecked(message.id)">
                    <div class="w-3.5 h-3.5 rounded-sm border-2 flex items-center justify-center shrink-0"
                        :class="[message.checked ? 'border-sky-500' : 'border-gray-300']">
                        <div v-if="message.checked" class="w-1.5 h-1.5 rounded-sm bg-sky-500">
                        </div>
                    </div>
                    <span class="" :class="[message.checked ? 'text-sky-700' : 'text-gray-600']">
                        {{ message.type.name }}
                    </span>
                </div>
            </div>
        </div>
        <!-- WARNING -->
        <div v-if="selectedMessageTypes.length > 1"
            class="bg-orange-50 border-l-4 border-orange-400 px-4 py-2 my-4 grid grid-cols-[auto,1fr] flex items-center gap-3">
            <Icon name="fa6-solid:triangle-exclamation" class="text-lg text-orange-400" />
            <span class="text-orange-500 font-semibold">
                {{ t('informative_block.info_all_channels') }}
            </span>
        </div>
        <!-- WILL BE REMOVED WHEN COMPLETED FILTERING -->
        <div v-if="selectedMessageTypes.find(type => type.id == 'default')"
            class="bg-orange-50 border-l-4 border-orange-400 px-4 py-2 my-4 grid grid-cols-[auto,1fr] flex items-center gap-3">
            <Icon name="fa6-solid:triangle-exclamation" class="text-lg text-orange-400" />
            <span class="text-orange-500 font-semibold">
                {{ t('informative_block.info_default_contract') }}
            </span>
        </div>


        <div v-if="!is_region" class="my-20"></div>
    </div>
</template>

<style scoped>
.grid {
    transition: all 0.3s ease;
}
</style>