<script setup>
const props = defineProps({
    contract: {
        type: Object,
        required: false
    },
    color: {
        type: String,
        default: null
    },
    reverse: {
        type: Boolean,
        default: false
    }
});

const { t } = useI18n();

const getVulnerabilityLevel = () => {
    if (props.contract?.holder_vulnerability_level == 2 || props.contract?.tenant_vulnerability_level == 2 || props.contract?.owner_vulnerability_level == 2) {
        return 2;
    } else if (props.contract?.holder_vulnerability_level == 1 || props.contract?.tenant_vulnerability_level == 1 || props.contract?.owner_vulnerability_level == 1) {
        return 1;
    }
    return 0;
}

</script>

<template>
    <span class="gap-2 inline-block rounded px-2 py-0.5 text-sm cursor-default w-full items-center"
        :class="{
            ['badge-' + props.color]: props.color,
            'badge-gray': !props.color,
            'flex flex-row-reverse': props.reverse,
            'flex justify-between': !props.reverse
        }">
        <slot>
            <span>{{ contract?.token }}</span>
            <AtomsVulnerabilityCheck v-if="getVulnerabilityLevel() > 0" :vulnerability_level="getVulnerabilityLevel()"
                :extra_small="true" class="w-1 h-1" />
            <abbr :title="t('contract_block.no_tlf')"  v-if="contract.contacts?.length == 0"
            class="flex items-center text-center rounded-full text-sm font-medium border bg-orange-100 text-orange-500 border-orange-500 w-4 h-4" >
                <Icon name="fa6-solid:phone-slash" class="w-3 h-3 m-auto" />
            </abbr>
            <abbr :title="t('contract_block.no_comms')"  v-if="contract.communication_missing"
            class="flex items-center text-center rounded-full text-sm font-medium border bg-orange-100 text-orange-500 border-orange-500 w-4 h-4" >
                <Icon name="fa6-solid:user-large-slash" class="w-3 h-3 m-auto" />
            </abbr>
            <abbr :title="t('contract_block.no_email')"  v-if="contract.email_missing && !contract.communication_missing"
            class="flex items-center text-center rounded-full text-sm font-medium border bg-orange-100 text-orange-500 border-orange-500 w-4 h-4" >
                <Icon name="fa6-solid:at" class="w-3 h-3 m-auto" />
            </abbr>
            <abbr :title="t('contract_block.block_billing')"  v-if="contract.block_billing"
            class="flex items-center text-center rounded-full text-sm font-medium border bg-blue-500 text-blue-100 border-blue-500 w-4 h-4" >
                <Icon name="fa6-solid:sack-xmark" class="w-3 h-3 m-auto" />
            </abbr>
        </slot>
    </span>
</template>