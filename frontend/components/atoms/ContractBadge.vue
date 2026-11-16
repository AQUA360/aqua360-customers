<script setup>
import { formatDate } from '~/utils/date';

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
    },
    // Icones que calcula qui fa servir l'etiqueta (p. ex. hidrant o tall al llistat):
    // [{ key, icon, title, iconClass }]. Compten com les altres per decidir quantes es veuen.
    extraIndicators: {
        type: Array,
        default: () => []
    }
});

const { t } = useI18n();

// Amb 3 o més icones no hi caben al costat del número: se'n veu la primera i la resta
// surt en passar el ratolí pels punts suspensius.
const MAX_VISIBLE = 2;

const CIRCLE = 'flex items-center text-center rounded-full text-sm font-medium border w-4 h-4 shrink-0';
const WARNING = 'bg-orange-100 text-orange-500 border-orange-500';

const getVulnerabilityLevel = () => {
    if (props.contract?.holder_vulnerability_level == 2 || props.contract?.tenant_vulnerability_level == 2 || props.contract?.owner_vulnerability_level == 2) {
        return 2;
    } else if (props.contract?.holder_vulnerability_level == 1 || props.contract?.tenant_vulnerability_level == 1 || props.contract?.owner_vulnerability_level == 1) {
        return 1;
    }
    return 0;
}

// Ordenades per importància: si no hi caben, es veu la primera.
const indicators = computed(() => {
    const contract = props.contract || {};
    const list = [];
    const vulnerabilityLevel = getVulnerabilityLevel();
    if (vulnerabilityLevel > 0) {
        list.push({
            key: 'vulnerability',
            vulnerabilityLevel,
            title: vulnerabilityLevel == 2 ? t('informative_block.info_vulnerable_or_pending') : t('contract_block.in_social_risk'),
        });
    }
    list.push(...props.extraIndicators);
    if (contract.block_billing) {
        list.push({ key: 'block_billing', icon: 'fa6-solid:sack-xmark', title: t('contract_block.block_billing'),
            circleClass: 'bg-blue-500 text-blue-100 border-blue-500' });
    }
    if (contract.communication_missing) {
        list.push({ key: 'no_comms', icon: 'fa6-solid:user-large-slash', title: t('contract_block.no_comms'), circleClass: WARNING });
    } else if (contract.email_missing) {
        list.push({ key: 'no_email', icon: 'fa6-solid:at', title: t('contract_block.no_email'), circleClass: WARNING });
    }
    if (contract.contacts?.length == 0) {
        list.push({ key: 'no_tlf', icon: 'fa6-solid:phone-slash', title: t('contract_block.no_tlf'), circleClass: WARNING });
    }
    if (contract.virtual_office_date) {
        list.push({ key: 'virtual_office', icon: 'mdi:laptop-account', iconClass: 'text-sky-600',
            title: `${t('contract_block.virtual_office_since')}: ${formatDate(contract.virtual_office_date)}` });
    }
    return list;
});

const visibleIndicators = computed(() =>
    indicators.value.length > MAX_VISIBLE ? indicators.value.slice(0, 1) : indicators.value
);
const hiddenIndicators = computed(() =>
    indicators.value.length > MAX_VISIBLE ? indicators.value.slice(1) : []
);

// La cel·la del llistat retalla el que en surt: la llista es pinta a <body>.
// Surt a sota del botó si hi cap i, si no, a sobre; mai fora de la pantalla. Es pot
// passar el ratolí del botó a la llista sense que es tanqui.
const GAP = 4;
const MARGIN = 8;
const moreButton = ref(null);
const morePanel = ref(null);
const morePosition = ref(null);
let hideTimer = null;

const placeMore = () => {
    const button = moreButton.value?.getBoundingClientRect();
    const panel = morePanel.value?.getBoundingClientRect();
    if (!button || !panel) return;
    const fitsBelow = button.bottom + GAP + panel.height <= window.innerHeight - MARGIN;
    const top = fitsBelow ? button.bottom + GAP : Math.max(MARGIN, button.top - GAP - panel.height);
    const left = Math.min(Math.max(MARGIN, button.left), window.innerWidth - MARGIN - panel.width);
    morePosition.value = { top: `${top}px`, left: `${Math.max(MARGIN, left)}px` };
}
const showMore = async () => {
    clearTimeout(hideTimer);
    if (morePosition.value) return;
    // Primer es pinta amagada per poder-la mesurar.
    morePosition.value = { top: '0px', left: '0px', visibility: 'hidden' };
    await nextTick();
    placeMore();
}
const hideMore = () => {
    clearTimeout(hideTimer);
    hideTimer = setTimeout(() => { morePosition.value = null; }, 150);
}
onBeforeUnmount(() => clearTimeout(hideTimer));
</script>

<template>
    <span class="gap-1 inline-block rounded px-2 py-0.5 text-sm cursor-default w-full items-center"
        :class="{
            ['badge-' + props.color]: props.color,
            'badge-gray': !props.color,
            'flex flex-row-reverse': props.reverse,
            'flex justify-between': !props.reverse
        }">
        <slot>
            <span class="truncate">{{ contract?.token }}</span>
            <span v-if="indicators.length" class="flex items-center gap-1 shrink-0">
                <template v-for="indicator in visibleIndicators" :key="indicator.key">
                    <AtomsVulnerabilityCheck v-if="indicator.key === 'vulnerability'"
                        :vulnerability_level="indicator.vulnerabilityLevel" :extra_small="true" />
                    <abbr v-else-if="indicator.circleClass" :title="indicator.title" :class="[CIRCLE, indicator.circleClass]">
                        <Icon :name="indicator.icon" class="w-3 h-3 m-auto" />
                    </abbr>
                    <abbr v-else :title="indicator.title" class="flex items-center shrink-0">
                        <Icon :name="indicator.icon" class="w-4 h-4" :class="indicator.iconClass" />
                    </abbr>
                </template>
                <button v-if="hiddenIndicators.length" ref="moreButton" type="button"
                    :aria-label="hiddenIndicators.map(i => i.title).join(', ')"
                    class="flex items-center justify-center rounded-full border border-slate-400 bg-slate-100 text-slate-600 w-4 h-4 shrink-0 text-[10px] leading-none"
                    @mouseenter="showMore" @mouseleave="hideMore" @focus="showMore" @blur="hideMore" @click.stop>
                    &hellip;
                </button>
            </span>
            <Teleport to="body">
                <ul v-if="morePosition" ref="morePanel" :style="morePosition" role="tooltip"
                    @mouseenter="showMore" @mouseleave="hideMore"
                    class="fixed z-[100] bg-white rounded customers-shadow border border-gray-100 p-2 space-y-1 text-sm text-slate-700">
                    <li v-for="indicator in hiddenIndicators" :key="indicator.key" class="flex items-center gap-2 whitespace-nowrap">
                        <AtomsVulnerabilityCheck v-if="indicator.key === 'vulnerability'"
                            :vulnerability_level="indicator.vulnerabilityLevel" :extra_small="true" />
                        <span v-else-if="indicator.circleClass" :class="[CIRCLE, indicator.circleClass]">
                            <Icon :name="indicator.icon" class="w-3 h-3 m-auto" />
                        </span>
                        <Icon v-else :name="indicator.icon" class="w-4 h-4 shrink-0" :class="indicator.iconClass" />
                        <span>{{ indicator.title }}</span>
                    </li>
                </ul>
            </Teleport>
        </slot>
    </span>
</template>
