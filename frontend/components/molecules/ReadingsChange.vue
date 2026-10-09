<script setup>
import { format } from 'date-fns';
import { useI18n } from 'vue-i18n';
import { useToast } from 'vue-toastification';
import AppLoading from '../atoms/AppLoading.vue';

const { t } = useI18n();
const toast = useToast();
const props = defineProps({
    contract_id: Number,
    supply_point_id: Number,
    estimated_bag: Object,
    current_meter_id: Number,
    persisted_draft: Object,
});
const { $ContractApiService, $ReadingApiService } = useNuxtApp();

const emit = defineEmits(['changed', 'allowSave']);

const recalculating = ref(false);
const loading = ref(false);
const readings = ref([]);
const new_readings = ref([]);
const readingsToDelete = ref([]);
const readingsToPassToControl = ref([]);
const readingsToKeepEstimated = ref([]);
const readingsToAvoidUseEstimatedBag = ref([]);
const selectedReading = ref(null);
const showControlReadings = ref(false);

const contractCreatedAt = ref(null);
const meterLastReadingValue = ref(null);

const total_consumption_last_estimated = ref(0);
const sp_estimated_bag = ref(props.estimated_bag);
const total_estimated_bag = ref(0);

const maintainEstimatedBag = ref(false);

const loadingMeterIds = ref(false);
const loadingBatches = ref(false);
const meters = ref([]);
const batches = ref([]);

const initialReadings = ref([]);

const unmodified_readings = ref([])

const period_data = ref(null);
const termination_reading = ref(null);
const contracts = ref([]);

const showAddingReadingDialog = ref(false);
const addedReadings = ref([]);
const addedIsClose = ref(false);
const addedIsControl = ref(false);
const addedIsInitial = ref(false);
const addedIsEstimated = ref(false);
const lastNewReadingIsEstimated = ref(null);
const lastNewReadingReal = ref(null);
const nextTempReadingId = ref(-1);
const wrongReadingDate = ref('');
const contractDateCheckTimeouts = new Map();

const lastReading = ref(null);
const hasPendingBilling = computed(() => contracts.value.some(c => c.pending_billing));

const previousToLastReading = computed(() => {
    const sortableReadings = new_readings.value
        .filter(r => !r.is_control && !r.is_close && r.reading_date < lastReading.value?.reading_date)
        .sort((a, b) => {
            if (b.reading_date !== a.reading_date) return b.reading_date.localeCompare(a.reading_date);
            return b.id - a.id;
        });

    return sortableReadings[0] || null;
});

const isTerminationReading = (reading) => {
    return termination_reading.value != null && reading?.id === termination_reading.value;
};

const isPendingBillingLastReading = (reading) => {
    return hasPendingBilling.value && !!lastReading.value && lastReading.value.id === reading?.id;
};

const isPendingBillingPreviousReading = (reading) => {
    return hasPendingBilling.value && !!previousToLastReading.value && previousToLastReading.value.id === reading?.id;
};

const allowSave = computed(() => {
    let allow = true
    if (new_readings.value.some(r => r.leak_value && r.leak_value > (r.calculated_value - Number(r.estimated_used || 0)))) allow = false;
    if (new_readings.value.some(r => r.estimated_used && r.estimated_used > (r.calculated_value - Number(r.leak_value || 0)))) allow = false;
    if (new_readings.value.some(r => r.within_period && !unmodified_readings.value.includes(r.id))) allow = false;
    emit('allowSave', allow);
    return allow;
});

const allowToAdd = computed(() => {
    return addedReadings.value.length > 0 &&
        ((!addedIsClose.value && addedReadings.value.length == 1) ||
            (addedIsClose.value && addedReadings.value.length == 2 && !addedReadings.value.every(r => r.meter_id == props.current_meter_id))) &&
        addedReadings.value.every(r => r.reading_value != null && r.reading_value >= 0 && r.reading_date && r.meter_id);
});

const formatPreviousReadingOption = (option) => {
    if (!option) return '';
    const date = formatDate(option.reading_date) || '-';
    const meter = option.meter_code ? ` [${option.meter_code}]` : '';
    const val = option.reading_value !== undefined ? ` (${option.reading_value})` : '';
    const control = option.is_control ? ` [${t('billing_block.control_reading')}]` : '';
    return `${t('common.date')}: ${date}${meter}${val}${control}`;
};

const formatMeterOption = (meter) => {
    if (!meter) return '';
    return meter.code;
};

const formatBatchOption = (batch) => {
    if (!batch) return '';
    const name = batch.name || batch.token;
    const status = batch.status_name || batch.status?.name || batch.status;
    return status ? `${name} · ${status}` : name;
};

const getPreviousReadingLinkedInfo = (currentReading) => {
    const linkedReading = findSelectedPreviousReading(currentReading);
    if (!linkedReading) return null;

    return {
        id: linkedReading.id,
        value: parseInt(linkedReading.reading_value || 0),
    };
};

const getPreviousReadingLinkedSummary = (currentReading) => {
    const linkedInfo = getPreviousReadingLinkedInfo(currentReading);
    return linkedInfo ? `${linkedInfo.value}` : '';
};

const getReadingKey = (r) => {
    if (!r) return null;
    const meterId = r.meter?.id || r.meter_id || '';
    return `${r.id}|${r.reading_date}|${meterId}|${r.reading_value}|${r.calculated_value}|${r.is_control ? '1' : '0'}`;
}

const compareReadingsDesc = (a, b) => {
    const dateA = a?.reading_date || '';
    const dateB = b?.reading_date || '';
    if (dateB !== dateA) return dateB.localeCompare(dateA);
    const isCloseA = a?.is_close ?? false;
    const isCloseB = b?.is_close ?? false;
    if (isCloseA !== isCloseB) return isCloseA ? 1 : -1;
    return (b?.id || 0) - (a?.id || 0);
};

const compareReadingsAsc = (a, b) => compareReadingsDesc(b, a);

const sortReadingsDesc = (list) => [...list].sort(compareReadingsDesc);

const makePreviousReadingOption = (r) => ({
    option_key: getReadingKey(r),
    reading_date: r.reading_date,
    reading_id: r.id,
    reading_value: r.reading_value,
    meter_code: r.meter?.code || meters.value.find(m => m.id === (r.meter_id || r.meter?.id))?.code || '',
    is_control: r.is_control,
    is_close: r.is_close,
});

const getNextTempReadingId = () => {
    const id = nextTempReadingId.value;
    nextTempReadingId.value -= 1;
    return id;
};

const buildModifiedReadingFromOriginal = (r) => ({
    id: r.id,
    supply_point_id: r.supply_point?.id || null,
    reading_date: r.reading_date,
    reading_value: r.reading_value,
    leak_value: r.leak_value,
    consumption_days: r.consumption_days,
    calculated_value: r.calculated_value - (r.estimated_used || 0),
    real_calculated_value: r.calculated_value - (r.estimated_used || 0),
    origin: t('common.modification'),
    use_previous_reading: false,
    previous_reading_id: r.previous_reading,
    previous_reading_source: 'original',
    previous_reading_option_key: r.previous_reading
        ? getReadingKey(readings.value.find(rr => rr.id === r.previous_reading))
        : null,
    meter_id: r.meter?.id || null,
    batch_id: r.batch?.id || null,
    reading_batch: r.batch,
    is_initial: r.is_initial,
    is_close: r.is_close,
    is_estimated: false,
    within_period: false,
    is_control: r.is_control,
    estimated_used: r.estimated_used,
    block_estimate_correction: false,
    invoice: r.invoice,
});

const restoreDeletedExistingReadings = () => {
    readingsToDelete.value.forEach((deletedId) => {
        const alreadyLoaded = new_readings.value.some(r => r.id === deletedId);
        if (alreadyLoaded) return;

        const originalReading = readings.value.find(r => r.id === deletedId);
        if (!originalReading) return;

        new_readings.value.push(buildModifiedReadingFromOriginal(originalReading));
    });
};

const ensureModifiedReadingsFromId = (readingId) => {
    const orderedReadings = sortReadingsDesc(readings.value);
    const selectedIndex = orderedReadings.findIndex(r => r.id === readingId);
    if (selectedIndex !== -1) {
        orderedReadings.slice(0, selectedIndex + 1).forEach((r) => {
            if (!new_readings.value.find(nr => nr.id === r.id)) {
                if (!r.is_control) {
                    new_readings.value.push(buildModifiedReadingFromOriginal(r));
                }
            }
        });
    }
};

const applyInsertedReadingLinks = (insertedReading) => {
    if (!insertedReading || insertedReading.is_control) return;

    const nearestNewerOriginal = readings.value
        .filter(r => !r.is_control && r.reading_date > insertedReading.reading_date)
        .sort(compareReadingsAsc)[0] || null;

    let nearestNewer = new_readings.value
        .filter(r =>
            !r.is_control &&
            !readingsToDelete.value.includes(r.id) &&
            r.reading_date > insertedReading.reading_date
        )
        .sort(compareReadingsAsc)[0] || null;

    if (
        nearestNewerOriginal &&
        (
            !nearestNewer ||
            nearestNewerOriginal.reading_date < nearestNewer.reading_date
        )
    ) {
        ensureModifiedReadingsFromId(nearestNewerOriginal.id);
        nearestNewer = new_readings.value.find(r => r.id === nearestNewerOriginal.id) || null;
    }

    if (!nearestNewer) return;

    insertedReading.previous_reading_id = nearestNewer.previous_reading_id || null;
    insertedReading.previous_reading_source = nearestNewer.previous_reading_source || null;
    insertedReading.previous_reading_option_key = nearestNewer.previous_reading_option_key || null;

    nearestNewer.previous_reading_id = insertedReading.id;
    nearestNewer.previous_reading_source = 'modified';
    nearestNewer.previous_reading_option_key = getReadingKey(insertedReading);
};

const isPreviousReadingCandidate = (candidate, currentReading) => {
    if (!candidate || !currentReading) return false;
    if (candidate.id === currentReading.id) return false;
    if (candidate.is_control) return false;
    if (candidate.reading_date < currentReading.reading_date) return true;
    return candidate.reading_date === currentReading.reading_date &&
        !!candidate.is_close &&
        !currentReading.is_close &&
        getReadingMeterId(candidate) !== getReadingMeterId(currentReading);
};


const updatePreviousReadingSelection = (reading, selectedKey) => {
    if (!selectedKey) {
        reading.previous_reading_id = null;
        reading.previous_reading_source = null;
        return;
    }

    const modifiedMatch = new_readings.value.find(r =>
        r.id !== reading.id &&
        !readingsToDelete.value.includes(r.id) &&
        getReadingKey(r) === selectedKey &&
        (!reading?.is_new || r.is_new)
    );

    if (modifiedMatch) {
        reading.previous_reading_id = modifiedMatch.id;
        reading.previous_reading_source = 'modified';
        return;
    }

    if (reading?.is_new) {
        reading.previous_reading_id = null;
        reading.previous_reading_source = null;
        return;
    }

    const originalMatch = readings.value.find(r =>
        r.id !== reading.id &&
        getReadingKey(r) === selectedKey,
    );

    reading.previous_reading_id = originalMatch?.id || null;
    reading.previous_reading_source = originalMatch ? 'original' : null;
};

const getData = async () => {
    loading.value = true;
    try {
        const res_data = {
            contract_id: props.contract_id,
            supply_point_id: props.supply_point_id,
        }
        const response = await $ReadingApiService.getModificationData(res_data);
        readings.value = response.readings;
        meters.value = response.meters;
        batches.value = response.batches;
        period_data.value = response.period_data;
        termination_reading.value = response.termination_reading ?? null;
        contracts.value = response.contracts || [];
        initialReadings.value = JSON.parse(JSON.stringify(readings.value));
        contractCreatedAt.value = (response.registration_date || response.contract_created_at) ? format(new Date(response.registration_date || response.contract_created_at), 'yyyy-MM-dd').toString() : null;
        meterLastReadingValue.value = response.meter_last_reading;
        // console.log("initialReadings", initialReadings.value);

        for (const reading of readings.value) {
            if (!reading.is_estimated) break;
            total_consumption_last_estimated.value += reading.calculated_value;
        }
        lastNewReadingReal.value = readings.value.filter(r => !r.is_estimated && !r.is_control && !r.is_close).sort((a, b) => b.reading_date.localeCompare(a.reading_date))[0]?.reading_date;

    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
    }
}

const selectReading = async (reading) => {
    if (!reading) {
        new_readings.value = []
        total_estimated_bag.value = parseInt(sp_estimated_bag.value?.total_consumption) || 0;
        return;
    }
    selectedReading.value = reading;
    new_readings.value = new_readings.value.filter(r => r.is_new);
    const orderedReadings = sortReadingsDesc(readings.value);
    const selectedIndex = orderedReadings.findIndex(r => r.id === reading.id);
    if (selectedIndex !== -1) {
        orderedReadings.slice(0, selectedIndex + 1).forEach(r => {
            new_readings.value.push(buildModifiedReadingFromOriginal(r));
        });
    }
    readingsToDelete.value = [];
    await recalculateNewReadingsConsumption(false);
}

const toggleDeleteReading = (readingId) => {
    if (readingsToDelete.value.includes(readingId)) {
        readingsToDelete.value = readingsToDelete.value.filter(id => id !== readingId);
        // If we undelete, it's already in new_readings (or should be)
    } else {
        if (new_readings.value.find(r => r.id === readingId)?.is_new) {
            new_readings.value = new_readings.value.filter(r => r.id !== readingId);
        } else {
            readingsToDelete.value.push(readingId);
        }
    }

    recalculateNewReadingsConsumption(false, true);
    emitChange();
}

const toggleAvoidUseEstimatedBagReading = (modReading) => {
    if (readingsToAvoidUseEstimatedBag.value.includes(modReading.id)) {
        readingsToAvoidUseEstimatedBag.value = readingsToAvoidUseEstimatedBag.value.filter(id => id !== modReading.id);
        const reading = new_readings.value.find(r => r.id === modReading.id);
        if (reading) {
            reading.estimated_used = pairedReadings.value.find(p => p.modified?.id === modReading.id)?.original?.estimated_used || null;
        }
    } else {
        readingsToAvoidUseEstimatedBag.value.push(modReading.id);
        const reading = new_readings.value?.find(r => r.id === modReading.id);
        if (reading) {
            reading.estimated_used = 0;
        }
    }
    emitChange();
}

const toggleKeepEstimatedReading = (mod_reading, force = false) => {
    if (readingsToKeepEstimated.value.includes(mod_reading.id) && !force) {
        readingsToKeepEstimated.value = readingsToKeepEstimated.value.filter(id => id !== mod_reading.id);
        mod_reading.is_estimated = false;
    } else {
        if (!readingsToKeepEstimated.value.includes(mod_reading.id)) readingsToKeepEstimated.value.push(mod_reading.id);
        mod_reading.is_estimated = true;
    }
    recalculateNewReadingsConsumption(false, true);
    emitChange();
}

const togglePassToControlReading = (mod_reading) => {
    mod_reading.is_control = !mod_reading.is_control;
    if (readingsToPassToControl.value.includes(mod_reading.id)) {
        readingsToPassToControl.value = readingsToPassToControl.value.filter(id => id !== mod_reading.id);
    } else {
        readingsToPassToControl.value.push(mod_reading.id);
    }
    recalculateNewReadingsConsumption(false, true);
    emitChange();
}

const getReadingMeterId = (reading) => reading?.meter_id || reading?.meter?.id || null;

const findClosestPreviousReading = (list, currentReading) => {
    const currentMeterId = getReadingMeterId(currentReading);
    const activeCandidates = list.map(rr => {
        const modified = new_readings.value.find(m => m.id === rr.id);
        return modified || rr;
    }).filter(rr =>
        rr.id !== currentReading.id &&
        !readingsToDelete.value.includes(rr.id) &&
        !rr.is_control,
    );

    const sameDateOtherMeter = activeCandidates.filter(rr =>
        rr.reading_date === currentReading.reading_date &&
        getReadingMeterId(rr) !== currentMeterId,
    );
    const sameDateDifferentMeter = sameDateOtherMeter.find(rr => rr.is_close) || sameDateOtherMeter[0] || null;
    // For closing readings, force previous-date lookup instead of same-date pairing.
    if (sameDateDifferentMeter && !currentReading?.is_close) return sameDateDifferentMeter;

    const candidateSameMeter = activeCandidates
        .filter(rr => rr.reading_date < currentReading.reading_date && getReadingMeterId(rr) === currentMeterId)
        .sort(compareReadingsDesc)[0] || null;
    if (candidateSameMeter && !candidateSameMeter.is_close) return candidateSameMeter;
    return activeCandidates
        .filter(rr => rr.reading_date < currentReading.reading_date)
        .sort(compareReadingsDesc)[0] || null;
}

const findClosestNextReading = (list, currentReading) => {
    /* return list
        .filter(rr => rr.id !== currentReading.id && rr.reading_date > currentReading.reading_date && !readingsToDelete.value.includes(rr.id) && !rr.is_control)
        .sort((a, b) => a.reading_date.localeCompare(b.reading_date))[0] || null; */
    const currentMeterId = getReadingMeterId(currentReading);
    const activeCandidates = list.map(rr => {
        const modified = new_readings.value.find(m => m.id === rr.id);
        return modified || rr;
    }).filter(rr =>
        rr.id !== currentReading.id &&
        !readingsToDelete.value.includes(rr.id) &&
        !rr.is_control,
    );

    const sameDateOtherMeter = activeCandidates.filter(rr =>
        rr.reading_date === currentReading.reading_date &&
        getReadingMeterId(rr) !== currentMeterId,
    );
    const sameDateDifferentMeter = sameDateOtherMeter.find(rr => !rr.is_close) || sameDateOtherMeter[0] || null;
    // A closing reading is immediately followed by the first reading of the new meter,
    // which shares its date. For any other reading that same-date one is its previous.
    if (sameDateDifferentMeter && currentReading?.is_close) return sameDateDifferentMeter;

    return activeCandidates
        .filter(rr => rr.reading_date > currentReading.reading_date)
        .sort(compareReadingsAsc)[0] || null;
}

const findSelectedPreviousReading = (currentReading) => {
    if (currentReading?.previous_reading_id && currentReading?.previous_reading_source) {
        if (currentReading.previous_reading_source === 'modified') {
            const modifiedById = new_readings.value.find(rr =>
                rr.id === currentReading.previous_reading_id &&
                rr.id !== currentReading.id &&
                !readingsToDelete.value.includes(rr.id),
            );
            if (modifiedById) return modifiedById;
        }

        if (currentReading.previous_reading_source === 'original') {
            const originalById = readings.value.find(rr =>
                rr.id === currentReading.previous_reading_id &&
                rr.id !== currentReading.id,
            );
            if (originalById) return originalById;
        }
    }

    if (!currentReading?.previous_reading_option_key) return null;

    const selectedKey = currentReading.previous_reading_option_key;

    const modifiedMatch = new_readings.value.find(rr =>
        rr.id !== currentReading.id &&
        !readingsToDelete.value.includes(rr.id) &&
        getReadingKey(rr) === selectedKey &&
        (!currentReading?.is_new || rr.is_new)
    );
    if (modifiedMatch) return modifiedMatch;

    if (currentReading?.is_new) return null;

    return readings.value.find(rr =>
        rr.id !== currentReading.id &&
        getReadingKey(rr) === selectedKey,
    ) || null;
}

const isValidPreviousReading = (currentReading, previousReading) => {
    if (!currentReading || !previousReading) return false;
    if (currentReading.id === previousReading.id) return false;
    if (readingsToDelete.value.includes(previousReading.id)) return false;
    if (previousReading.is_control) return false;
    return previousReading.reading_date < currentReading.reading_date;
};

const recalculateNewReadingsConsumption = async (keep_calculated_value = false, reverse = false, reset_estimated_bag = true) => {
    console.log("recalculating new readings consumption", keep_calculated_value, reverse, reset_estimated_bag);
    recalculating.value = true;
    if (!maintainEstimatedBag.value) {
        total_estimated_bag.value = sp_estimated_bag.value?.total_consumption || 0;
    }
    // total_estimated_bag.value = sp_estimated_bag.value?.total_consumption || 0;
    /* if (reset_estimated_bag && !isApplyingPersistedDraft.value) {
        console.log("resetting estimated bag", sp_estimated_bag.value?.total_consumption);
        total_estimated_bag.value = sp_estimated_bag.value?.total_consumption || 0;
    } */
    const activeNewReadings = new_readings.value
        .filter(r => !readingsToDelete.value.includes(r.id))
        .sort(reverse ? compareReadingsDesc : compareReadingsAsc);
    const activeTimeline = activeNewReadings
        .filter(r => !r.is_control);

    lastNewReadingIsEstimated.value = null;
    activeNewReadings.forEach(r => {
        if (readingsToDelete.value.includes(r.id)) return;
        // console.log("new reading", r.reading_date, r.calculated_value);
        if (r.is_control) {
            r.use_previous_reading = false;
            r.previous_reading_id = null;
            r.previous_reading_source = null;
            r.previous_reading_option_key = null;
            // r.calculated_value = 0;
            // r.real_calculated_value = 0;
            r.consumption_days = 0;
            r.estimated_used = null;
            r.within_period = false;
            r.is_estimated = false;
            // return;
        }


        if (r.reading_value === null || r.reading_value === undefined || r.reading_value === '') {
            r.calculated_value = 0;
            r.real_calculated_value = 0;
            r.consumption_days = 0;
            r.estimated_used = null;
            r.is_estimated = false;
            return;
        }
        const og_reading = initialReadings.value.find(or => or.id === r.id);


        r.pending_billing = og_reading?.pending_billing || false;
        r.origin = r.origin || pairedReadings.value.find(p => p.modified?.id === r.id)?.original?.origin || t('common.manual');
        r.estimated_used = parseInt(r.estimated_used) || null;
        // console.log("\n\n", r.reading_date)
        let previous_readings = activeTimeline
            .filter(rr => rr.id !== r.id && rr.reading_date < r.reading_date && !readingsToDelete.value.includes(rr.id) && !rr.is_control)
            .sort((a, b) => b.reading_date.localeCompare(a.reading_date))
        let previous_reading = findClosestPreviousReading(activeTimeline, r);

        r.use_previous_reading = false;
        // console.log("previous_reading", previous_reading);

        if (!previous_reading) {
            previous_reading = findClosestPreviousReading(readings.value, r);
            previous_readings = readings.value
                .filter(rr => rr.id !== r.id && rr.reading_date < r.reading_date && !readingsToDelete.value.includes(rr.id) && !rr.is_control)
                .sort((a, b) => b.reading_date.localeCompare(a.reading_date))
            r.use_previous_reading = true
        }

        if (previous_reading) {
            const isModifiedPrevious = new_readings.value.some(rr => rr.id === previous_reading.id);
            r.previous_reading_id = previous_reading.id;
            r.previous_reading_source = isModifiedPrevious ? 'modified' : 'original';
            r.previous_reading_option_key = getReadingKey(previous_reading);
        } else {
            r.previous_reading_id = null;
            r.previous_reading_source = null;
            r.previous_reading_option_key = null;
        }
        console.log("previous_reading reading", r.reading_value);
        console.log("previous_reading", previous_reading?.reading_value);

        if (!keep_calculated_value && !(r.is_estimated && r.calculated_value > 0)) {
            if (previous_reading) {
                r.calculated_value = parseInt(Number(r.reading_value) - Number(previous_reading.reading_value));
            } else {
                r.calculated_value = og_reading ? Number(og_reading.calculated_value || 0) : 0;
            }
        }

        if (previous_reading) {
            const diffTime = Math.abs(new Date(r.reading_date) - new Date(previous_reading.reading_date));
            r.consumption_days = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        } else {
            r.consumption_days = og_reading ? Number(og_reading.consumption_days || 0) : 0;
        }
        // console.log("calculated value: ", r.calculated_value);
        if (r.calculated_value < 0) {
            r.calculated_value = 0;
        }
        r.real_calculated_value = r.calculated_value


        /* console.log("\n\nchecking if reading is unmodified");
        console.log(og_reading.calculated_value == r.calculated_value)
        console.log(`og calculated value: ${og_reading.calculated_value} new calculated value: ${r.calculated_value}`)
        console.log(og_reading.leak_value == r.leak_value)
        console.log(`og leak value: ${og_reading.leak_value} new leak value: ${r.leak_value}`)
        console.log(og_reading.consumption_days == r.consumption_days)
        console.log(`og consumption days: ${og_reading.consumption_days} new consumption days: ${r.consumption_days}`)
        console.log(og_reading.reading_value == r.reading_value)
        console.log(`og reading value: ${og_reading.reading_value} new reading value: ${r.reading_value}`)
        console.log((og_reading.estimated_used == r.estimated_used || ((og_reading.estimated_used == null || og_reading.estimated_used == 0) && r.estimated_used == null)))
        console.log(`og estimated used: ${og_reading.estimated_used} new estimated used: ${r.estimated_used}`)
        console.log(og_reading.meter.id == r.meter_id)
        console.log(`og meter id: ${og_reading.meter.id} new meter id: ${r.meter_id}`) */
        if (
            og_reading &&
            og_reading.calculated_value == r.calculated_value &&
            og_reading.leak_value == r.leak_value &&
            og_reading.consumption_days == r.consumption_days &&
            og_reading.reading_date == r.reading_date &&
            og_reading.reading_value == r.reading_value &&
            (og_reading.estimated_used == r.estimated_used || ((og_reading.estimated_used == null || og_reading.estimated_used == 0) && r.estimated_used == null)) &&
            og_reading.meter.id == r.meter_id &&
            (!og_reading.is_estimated || (og_reading.is_estimated && readingsToKeepEstimated.value.includes(og_reading.id)))
        ) {
            if (!unmodified_readings.value.includes(r.id)) {
                unmodified_readings.value.push(r.id);
                r.origin = og_reading.origin;
            }
        } else {
            if (unmodified_readings.value.includes(r.id)) {
                r.origin = t('common.modification');
            }
        
            unmodified_readings.value = unmodified_readings.value.filter(id => id !== r.id);
        }

        let next_reading = findClosestNextReading(activeTimeline, r);
        let previous_previous_reading = null
        if (previous_reading) {
            previous_previous_reading = findClosestPreviousReading(activeTimeline, previous_reading);
            if (!previous_previous_reading) {
                previous_previous_reading = findClosestPreviousReading(readings.value, previous_reading);
            }
        }

        if (!r.is_control) checkPeriodData(r, previous_reading, previous_readings, next_reading, previous_previous_reading);
        // console.log("total estimated bag", total_estimated_bag.value);
        if (r.is_estimated) {
            r.estimated_used = 0;
            if (readingsToKeepEstimated.value.includes(r.id)) {
                // if (previous_reading && (previous_reading.reading_value != r.reading_value || previous_reading.reading_date != r.calculated_value)) {
                //     console.log("previous reading is not unmodified", previous_reading);
                // }
                r.reading_value = pairedReadings.value.find(p => p.modified?.id === r.id)?.original?.reading_value || 0;
                r.calculated_value = pairedReadings.value.find(p => p.modified?.id === r.id)?.original?.calculated_value || 0;
                r.reading_date = pairedReadings.value.find(p => p.modified?.id === r.id)?.original?.reading_date || null;
                r.leak_value = pairedReadings.value.find(p => p.modified?.id === r.id)?.original?.leak_value || null;
            } else {
                r.reading_value = previous_reading?.reading_value || 0;
            }

            if (!isApplyingPersistedDraft.value && !maintainEstimatedBag.value) {
                total_estimated_bag.value = Number(total_estimated_bag.value || 0) + Number(r.calculated_value || 0);
            }
            if (!next_reading) {
                lastNewReadingIsEstimated.value = r.reading_date;
            }
        } else {
            if (og_reading && og_reading.is_estimated && !maintainEstimatedBag.value) {
                // console.log("removing estimated reading from total estimated bag", og_reading.calculated_value);
                // console.log("total estimated bag", total_estimated_bag.value);
                total_estimated_bag.value = Number(total_estimated_bag.value || 0) - Number(og_reading.calculated_value || 0);
                if (total_estimated_bag.value < 0) {
                    total_estimated_bag.value = 0;
                }
            }
        }
        if (r.estimated_used && r.estimated_used > r.calculated_value) {
            r.estimated_used = r.calculated_value;
        }
    });
    lastNewReadingReal.value = new_readings.value.filter(r => !r.is_estimated && !r.is_control && !r.is_close).sort((a, b) => b.reading_date.localeCompare(a.reading_date))[0]?.reading_date;
    if (!lastNewReadingReal.value || lastNewReadingReal.value == undefined) {
        lastNewReadingReal.value = readings.value.filter(r => !r.is_estimated && !r.is_control && !r.is_close).sort((a, b) => b.reading_date.localeCompare(a.reading_date))[0]?.reading_date;
    }
    maintainEstimatedBag.value = false;
    // console.log("total estimated bag", total_estimated_bag.value);
    // console.log("new_readings", new_readings.value);
    await emitChange()
    lastReading.value = new_readings.value.filter(r => !r.is_control && !r.is_close && r.pending_billing).sort((a, b) => b.reading_date.localeCompare(a.reading_date))[0];
    // console.log("lastReading", lastReading.value);
    const originalLastReading = readings.value.find(r => r.id === lastReading.value?.id);
    if (lastReading.value && originalLastReading) {
        const shouldAvoidEstimatedBagForLastReading = hasPendingBilling.value &&
            !!lastReading.value &&
            originalLastReading?.is_estimated &&
            !lastReading.value.is_estimated
        if (shouldAvoidEstimatedBagForLastReading) {
            toggleKeepEstimatedReading(lastReading.value, true);
        }
    }


    recalculating.value = false;
}

const pairedReadings = computed(() => {
    const originalPairs = readings.value.map((original) => {
        const modified = new_readings.value.find(
            (r) => r.id === original.id,
        );

        return {
            original,
            modified: modified || null,
        };
    });

    const newOnlyPairs = new_readings.value
        .filter((r) => r.is_new)
        .map((modified) => ({
            original: null,
            modified,
        }));

    return [...originalPairs, ...newOnlyPairs].sort((a, b) =>
        compareReadingsDesc(a.modified || a.original, b.modified || b.original),
    );
});

// Readings just switched to control stay visible so the change can be undone.
const isControlPair = (pair) => {
    const reading = pair.modified || pair.original;
    return !!reading?.is_control && !readingsToPassToControl.value.includes(reading.id);
};

const controlReadingsCount = computed(() => pairedReadings.value.filter(isControlPair).length);

const visiblePairedReadings = computed(() =>
    showControlReadings.value
        ? pairedReadings.value
        : pairedReadings.value.filter(pair => !isControlPair(pair)),
);


const checkContractDate = (reading) => {
    wrongReadingDate.value = '';
    if (reading && reading.reading_date) {
        if (addedIsEstimated.value && reading.reading_date < lastNewReadingReal.value) {
            reading.reading_date = format(new Date(lastNewReadingReal.value), 'yyyy-MM-dd').toString();
            wrongReadingDate.value = 'warning_reading_before_estimated';
        } else {
            if (reading.reading_date < contractCreatedAt.value) {
                reading.reading_date = format(new Date(contractCreatedAt.value), 'yyyy-MM-dd').toString();
                wrongReadingDate.value = 'warning_reading_before_contract';
            } else {
                if (
                    (readings.value.some(r => r.reading_date === reading.reading_date && (r.meter?.id || r.meter_id) === reading.meter_id && !r.is_control) ||
                        new_readings.value.some(r => r.reading_date === reading.reading_date && (r.meter_id || r.meter?.id) === reading.meter_id && !r.is_control)) &&
                    !addedIsControl.value
                ) {
                    wrongReadingDate.value = 'warning_reading_duplicate';
                    reading.reading_date = null;
                }
            }
        }
    } else {
        wrongReadingDate.value = 'warning_reading_unallowed_to_estimated';
    }
    return wrongReadingDate.value == '';
}

const scheduleCheckContractDate = (reading) => {
    const existingTimeout = contractDateCheckTimeouts.get(reading);
    if (existingTimeout) {
        clearTimeout(existingTimeout);
    }

    const timeoutId = setTimeout(() => {
        checkContractDate(reading);
        contractDateCheckTimeouts.delete(reading);
    }, 300);

    contractDateCheckTimeouts.set(reading, timeoutId);
}

onBeforeUnmount(() => {
    contractDateCheckTimeouts.forEach((timeoutId) => clearTimeout(timeoutId));
    contractDateCheckTimeouts.clear();
});

const changesLog = computed(() => {
    let logLines = [];
    new_readings.value.forEach(modified => {
        const original = initialReadings.value.find(r => r.id === modified.id);
        if (original) {
            let changes = [];
            if (original.is_control !== modified.is_control) {
                const actionStr = modified.is_control ? "Marcada com a lectura de control" : "Desmarcada com a lectura de control";
                changes.push(`${actionStr} (${t('common.previous') || 'Anterior'}: ${original.reading_value}, ${t('common.current') || 'Nou'}: ${modified.reading_value})`);
            } else if (parseInt(original.reading_value) !== parseInt(modified.reading_value)) {
                changes.push(`${t('reading')}: ${parseInt(original.reading_value)} -> ${parseInt(modified.reading_value)}`);
            }

            if (original.reading_date !== modified.reading_date) {
                changes.push(`${t('billing_block.reading_date')}: ${original.reading_date} -> ${modified.reading_date}`);
            }

            if (parseInt(original.leak_value || 0) !== parseInt(modified.leak_value || 0)) {
                const leakAction = !original.leak_value ? "S'ha afegit fuita" : t('billing_block.leak');
                changes.push(`${leakAction}: ${original.leak_value || 0} -> ${modified.leak_value || 0}`);
            }

            if (changes.length > 0) {
                logLines.push(`${t('reading')} ${modified.id} (${modified.reading_date}): ${changes.join(', ')}`);
            }
        } else if (modified.is_new) {
            let typeStr = t('billing_block.manual_reading');
            if (modified.is_estimated) typeStr = t('billing_block.estimated');
            if (modified.is_control) typeStr = t('billing_block.control_reading');

            let details = `${t('reading')}: ${modified.reading_value}`;
            if (modified.leak_value) {
                details += `, ${t('billing_block.leak')}: ${modified.leak_value}`;
            }
            logLines.push(`${t('billing_block.new_reading')} (${modified.reading_date}) [${typeStr}]: ${details}`);
        }
    });

    readingsToDelete.value.forEach(id => {
        const original = initialReadings.value.find(r => r.id === id);
        if (original) {
            logLines.push(`${t('common.manually_deleted')}: ${t('reading')} ${id} (${original.reading_date})`);
        }
    });

    if (logLines.length > 0) {
        const dateStr = new Date().toLocaleString();
        return `--- ${dateStr} ---\n` + logLines.join('\n');
    }
    return "";
});

const showDialogNewReadings = () => {
    showAddingReadingDialog.value = !showAddingReadingDialog.value;
    addedReadings.value = [];
    addedIsClose.value = false;
    addedIsControl.value = false;
    addedIsInitial.value = pairedReadings.value.length === 0;
    wrongReadingDate.value = '';
    if (showAddingReadingDialog.value) {
        addedReadings.value.push({
            reading_date: pairedReadings.value.length === 0 ? format(new Date(contractCreatedAt.value), 'yyyy-MM-dd').toString() : null,
            reading_value: pairedReadings.value.length === 0 ? meterLastReadingValue.value : null,
            leak_value: null,
            meter_id: props.current_meter_id,
            origin: t('common.manual'),
            is_close: false,
            is_new: true,
            is_control: false,
            is_estimated: lastNewReadingIsEstimated.value != null,
            is_initial: pairedReadings.value.length === 0,
            estimated_used: null,
            block_estimate_correction: false,
        })
    }
}

const controlCloseReading = () => {
    if (addedIsClose.value) {
        addedIsControl.value = false;
        const firstReading = addedReadings.value[0];
        addedReadings.value.push({
            reading_date: firstReading.reading_date,
            reading_value: null,
            leak_value: null,
            meter_id: props.current_meter_id,
            origin: t('common.manual'),
            is_close: true,
            is_new: true,
            is_control: false,
            calculated_value: 0,
            consumption_days: 0,
            estimated_used: null,
            block_estimate_correction: false,
        })
    } else {
        addedReadings.value = addedReadings.value.filter(r => !r.is_close);
    }
}

const estimateNewReading = async () => {
    addedIsEstimated.value = true;
    try {
        let addedDate = addedReadings.value[0]?.reading_date;
        if (addedDate == undefined || addedDate == '') addedDate = null
        if (!addedDate) {
            const baseDateStr = lastNewReadingReal.value;
            const baseDate = new Date(baseDateStr + "T00:00:00");
            baseDate.setDate(baseDate.getDate() + period_data?.period_days ? period_data?.period_days : 90);
            const year = baseDate.getFullYear();
            const month = String(baseDate.getMonth() + 1).padStart(2, '0');
            const day = String(baseDate.getDate()).padStart(2, '0');
            addedDate = `${year}-${month}-${day}`;
        }

        const response = await $ReadingApiService.estimateReading(
            { supply_points: [props.supply_point_id], reading_date: addedDate, dry: true }
        );

        if (response) {
            const addedEstimatedReading = response.readings[0]
            if (addedEstimatedReading) {
                addedReadings.value = []
                addedReadings.value.push({
                    reading_date: addedEstimatedReading.reading_date,
                    reading_value: addedEstimatedReading.reading_value,
                    calculated_value: addedEstimatedReading.calculated_value,
                    leak_value: null,
                    meter_id: props.current_meter_id,
                    is_close: false,
                    is_new: true,
                    is_control: false,
                    origin: t('billing_block.estimated'),
                    is_estimated: addedEstimatedReading.is_estimated,
                    is_initial: false,
                    estimated_used: null,
                    block_estimate_correction: false,
                })
                if (!addedEstimatedReading.is_estimated) {
                    addedIsEstimated.value = false;
                }
                await addReadingsToList();
            } else {
                checkContractDate(addedEstimatedReading);
                //showDialogNewReadings();
            }
        }
    } catch (error) {
        console.error(error);
    } finally {
        //showDialogNewReadings();
    }
}

const addReadingsToList = async () => {
    for (const reading of addedReadings.value) {
        if (!checkContractDate(reading)) return;
    }
    try {

        const readingsToAdd = addedReadings.value.map((reading) => {
            const isControlReading = !!addedIsControl.value;
            const isEstimatedReading = !!addedIsEstimated.value;
            return {
                ...reading,
                id: getNextTempReadingId(),
                is_new: true,
                is_control: isControlReading,
                use_previous_reading: false,
                previous_reading_id: null,
                previous_reading_source: null,
                previous_reading_option_key: null,
                calculated_value: isControlReading ? 0 : (reading.calculated_value || 0),
                real_calculated_value: isControlReading ? 0 : (reading.real_calculated_value || reading.calculated_value || 0),
                consumption_days: isControlReading ? 0 : (reading.consumption_days || 0),
                estimated_used: null,
                origin: reading.origin || t('common.manual'),
                within_period: false,
                is_close: false,
                is_estimated: isEstimatedReading,
                is_initial: pairedReadings.value.length === 0,
                estimated_used: null,
                block_estimate_correction: false,
                add_to_all: false,
            };
        });
        new_readings.value.push(...readingsToAdd);
        readingsToAdd
            .filter(r => !r.is_control)
            .forEach((r) => applyInsertedReadingLinks(r));
        new_readings.value.sort(compareReadingsDesc);
        await recalculateNewReadingsConsumption(false, false, true);
    } catch (error) {
        console.error(error);
    } finally {
        showDialogNewReadings();
    }
    // console.log("new_readings", new_readings.value);
}

const checkPeriodData = (reading, previous_reading, previous_readings, next_reading, previous_previous_reading) => {
    reading.within_period = false;
    if (!period_data.value || period_data.value?.period_days == null || !period_data.value?.period_days) return;
    if (reading.is_initial) return;
    if (reading.is_control) return;
    if (reading.is_close) return;
    if (isTerminationReading(reading)) return;
    if (!previous_reading) return;
    try {
        if (previous_readings.length > 0 && previous_readings.filter(r => !r.is_initial).filter(r => !r.is_control).length > 0) {
            if (!previous_previous_reading?.is_initial && !previous_reading.is_close && !reading.is_close && !(previous_previous_reading && previous_previous_reading.is_close && !previous_reading.invoice)) {
                if (reading.consumption_days < period_data.value?.period_days && (((period_data.value?.period_days - reading.consumption_days) / (period_data.value?.period_days * 2)) * 100) > period_data.value?.limit) {
                    reading.within_period = true;
                }
            }
        }
        if (next_reading && !isTerminationReading(next_reading) && next_reading.consumption_days &&
            next_reading.consumption_days < period_data.value?.period_days &&
            (((period_data.value?.period_days - next_reading.consumption_days) / (period_data.value?.period_days * 2)) * 100) > period_data.value?.limit &&
            !previous_previous_reading?.is_initial && !previous_reading.is_close && !next_reading.is_close) {
            // console.log("next_reading", next_reading);
            reading.within_period = true;
        }
    } catch (error) {
        console.error(error);
    }
}

const controlAddedIsClose = () => {
    addedIsControl.value = false;
    if (addedIsClose.value) {
        const og_added_reading = addedReadings.value[0];
        og_added_reading.meter_id = null;
        addedReadings.value.push({
            reading_date: og_added_reading.reading_date,
            reading_value: og_added_reading.reading_value,
            origin: og_added_reading.origin,
            leak_value: null,
            meter_id: props.current_meter_id,
            is_close: true,
            is_new: true,
            is_control: false,
            calculated_value: 0,
            consumption_days: 0,
            estimated_used: null,
            block_estimate_correction: false,
        })
    } else {
        addedReadings.value = addedReadings.value.filter(r => !r.is_close);
    }
}

const emitChange = async () => {
    if (isApplyingPersistedDraft.value) return;
    // console.log("emitChange");
    // console.log("new_readings", new_readings.value);

    await emit('changed',
        new_readings.value.filter(r => !readingsToDelete.value.includes(r.id)),
        new_readings.value.filter(r => !readingsToDelete.value.includes(r.id)).map(r => r.id),
        total_estimated_bag.value,
        readingsToDelete.value,
        changesLog.value
    )
}

const firstModifiedIndex = computed(() =>
    pairedReadings.value.findIndex((p) => p.modified !== null),
);

const latestNewReading = computed(() =>
    new_readings.value.length > 0 ? new_readings.value[0] : null,
);

const hasMultipleContracts = computed(() => contracts.value.length > 1);
const showAllContracts = ref(false);
const previewContracts = computed(() => contracts.value.slice(0, 3));
const hiddenContractsCount = computed(() => Math.max(contracts.value.length - previewContracts.value.length, 0));
const isApplyingPersistedDraft = ref(false);

const applyPersistedDraft = () => {
    if (isApplyingPersistedDraft.value) return;
    isApplyingPersistedDraft.value = true;

    const draft = props.persisted_draft;
    if (!draft) {
        total_estimated_bag.value = Number(sp_estimated_bag.value?.total_consumption || 0);
        isApplyingPersistedDraft.value = false;
        return;
    }

    new_readings.value = Array.isArray(draft.new_readings)
        ? JSON.parse(JSON.stringify(draft.new_readings))
        : [];
    readingsToDelete.value = Array.isArray(draft.readings_to_delete)
        ? [...draft.readings_to_delete]
        : [];
    restoreDeletedExistingReadings();
    total_estimated_bag.value = Number(draft.total_estimated_bag ?? sp_estimated_bag.value?.total_consumption ?? 0);

    recalculateNewReadingsConsumption(true);
    isApplyingPersistedDraft.value = false;
};

watch(total_estimated_bag, (newVal) => {
    if (recalculating.value) return;
    if (isApplyingPersistedDraft.value) return;
    maintainEstimatedBag.value = true;
    emitChange();
});

onMounted(async () => {
    await getData();
    applyPersistedDraft();
});

watch(() => props.supply_point_id, (newVal) => {
    getData().then(() => {
        applyPersistedDraft();
    });
});

watch(() => props.persisted_draft, () => {
    applyPersistedDraft();
});

watch(() => props.estimated_bag, (newVal) => {
    sp_estimated_bag.value = newVal;
    if (!props.persisted_draft) {
        total_estimated_bag.value = Number(newVal?.total_consumption || 0);
    }
});

</script>
<template>
    <div class="min-h-[200px]">
        <div v-if="loading">
            <AppLoading :text="$t('common.loading')" />
        </div>
        <div v-else>
            <Teleport v-if="showAddingReadingDialog" to="body">
                <div @click="requestsFound = false"
                    class="fixed inset-0 text-sm flex items-center justify-center bg-black bg-opacity-50 z-30">
                    <div v-if="showAddingReadingDialog"
                        class="w-2/4 h-fit bg-white z-50 fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 rounded-md shadow-md">
                        <div class="flex justify-between items-center p-4">
                            <h2 class="text-xl font-semibold">{{ $t('billing_block.add_reading') }}</h2>
                            <button @click="showAddingReadingDialog = false" class="hover:text-slate-700 p-2">
                                <Icon name="fa6-solid:xmark" />
                            </button>
                        </div>
                        <div class="px-4 pb-4">
                            <div class="mb-4">
                                <div class="flex items-center gap-x-2 mb-4">
                                    <div v-if="pairedReadings.length > 0" class="flex items-center gap-3 px-3">
                                        <input type="checkbox" id="is_reading_estimate" v-model="addedIsEstimated"
                                            class="w-4 h-4 text-primary border-slate-300 rounded"
                                            :disabled="lastNewReadingIsEstimated != null || addedIsControl" />
                                        <label for="is_reading_estimate"
                                            class="text-sm font-medium text-slate-700 cursor-pointer">
                                            {{ $t('billing_block.estimated_reading') }}
                                        </label>
                                    </div>
                                    <div v-if="pairedReadings.length > 0" class="flex items-center gap-3 px-3">
                                        <input type="checkbox" id="is_meter_change" v-model="addedIsControl"
                                            class="w-4 h-4 text-primary border-slate-300 rounded"
                                            :disabled="addedIsClose || addedIsEstimated" />
                                        <label for="is_meter_change"
                                            class="text-sm font-medium text-slate-700 cursor-pointer">
                                            {{ $t('billing_block.control_reading') }}
                                        </label>
                                    </div>
                                    <div v-else class="flex items-center gap-3 px-3">
                                        <input type="checkbox" id="is_reading_initial" v-model="addedIsInitial"
                                            class="w-4 h-4 text-primary border-slate-300 rounded" :disabled="true" />
                                        <label for="is_reading_initial"
                                            class="text-sm font-medium text-slate-700 cursor-pointer">
                                            {{ $t('billing_block.initial_reading') }}
                                        </label>
                                    </div>
                                    <!-- <div v-if="meters.length > 1" class="flex items-center gap-3 p-3">
                                        <input type="checkbox" id="is_meter_change" v-model="addedIsClose"
                                            class="w-4 h-4 text-primary border-slate-300 rounded"
                                            @change="controlAddedIsClose"/>
                                        <label for="is_meter_change"
                                            class="text-sm font-medium text-slate-700 cursor-pointer">
                                            {{ $t('billing_block.change_meter') }}
                                        </label>
                                    </div> -->
                                </div>
                                <div v-if="wrongReadingDate && wrongReadingDate !== ''"
                                    class="text-yellow-500 text-xs font-bold uppercase">
                                    {{ t(`warning_block.${wrongReadingDate}`) }}
                                </div>
                                <div class="w-full">
                                    <div v-for="reading in addedReadings" :key="reading.id"
                                        class="grid grid-cols-3 gap-2 my-1 p-1" :class="{
                                            'bg-red-50 rounded': reading.is_close,
                                        }">
                                        <div>
                                            <span class="inline-flex items-center gap-x-1 text-xs text-slate-500">
                                                <Icon name="fa6-solid:calendar"
                                                    class="h-3.5 w-3.5 text-slate-400 shrink-0" />
                                                <span class="font-medium text-slate-500">{{
                                                    $t('billing_block.reading_date')
                                                }}</span>
                                            </span>
                                            <input type="date" v-model="reading.reading_date" class="input"
                                                :disabled="reading.is_close || reading.is_initial" />
                                        </div>
                                        <div>
                                            <span class="inline-flex items-center gap-1.5 pb-1 text-xs text-slate-500">
                                                <Icon name="my-icon:meter-icon-black"
                                                    class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                <span class="font-medium text-slate-500">{{ $t('reading') }}</span>
                                            </span>
                                            <input type="number" v-model="reading.reading_value" class="input" />
                                        </div>

                                        <div>
                                            <label
                                                class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                                                {{ $t('meter') }}
                                            </label>
                                            <v-select class="block w-full custom-select" v-model="reading.meter_id"
                                                :options="meters" :loading="loadingMeterIds"
                                                :disabled="meters.length == 1" :get-option-label="formatMeterOption"
                                                :reduce="(option) => option.id" />
                                        </div>
                                    </div>
                                </div>

                            </div>
                            <div class="flex justify-end gap-x-2">
                                <button v-if="pairedReadings.length > 0"
                                    class="button-default flex items-center gap-x-2" @click="estimateNewReading">
                                    <Icon name="fa6-solid:scale-unbalanced" class="h-3.5 w-3.5 shrink-0" />
                                    <span>
                                        {{ t('billing_block.estimate') }}
                                    </span>
                                </button>
                                <button class="button-primary flex items-center gap-x-2" :disabled="!allowToAdd"
                                    @click="addReadingsToList">
                                    <Icon name="fa6-solid:angles-down" class="h-3.5 w-3.5 shrink-0" />
                                    <span>
                                        {{ t('common.add') }}
                                    </span>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </Teleport>
            <!-- <div v-if="pairedReadings.length === 0"
                class="my-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                <p>
                    {{ $t('billing_block.no_readings_to_change') }}
                </p>
            </div> -->
            <div>
                <div class="flex justify-between items-start">
                    <div class="my-2 flex flex-col items-start gap-2">
                        <div v-if="period_data?.period_name || period_data?.period_days"
                            class="inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-500">
                            <Icon name="fa6-solid:circle-info" class="h-3.5 w-3.5 shrink-0 text-slate-400" />
                            <span>
                                {{ $t('billing_block.billing_period') }}:
                                <span v-if="period_data?.period_name" class="font-medium text-slate-600">{{
                                    t(`date.${period_data.period_name}`) }} </span>
                                <span v-if="period_data?.period_days && !period_data?.period_name"
                                    class="font-medium text-slate-600">
                                    {{ period_data.period_days }} {{ $t('date.days') }}
                                </span>
                            </span>
                        </div>

                        <div v-if="hasMultipleContracts"
                            class="relative inline-flex flex-wrap items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs text-slate-500">
                            <Icon name="fa6-solid:file-contract" class="h-3.5 w-3.5 shrink-0 text-slate-400" />
                            <span class="font-medium text-slate-600">{{ $t('contracts') }}:</span>
                            <span v-for="contract in previewContracts" :key="contract.id"
                                class="rounded bg-white px-1.5 py-0.5 font-semibold text-slate-700">
                                {{ contract.token }}
                            </span>
                            <button v-if="hiddenContractsCount > 0" type="button"
                                class="rounded bg-slate-200 px-1.5 py-0.5 font-semibold text-slate-700 transition-colors hover:bg-slate-300"
                                :class="{ 'bg-slate-300': showAllContracts }"
                                @click="showAllContracts = !showAllContracts">
                                +{{ hiddenContractsCount }}
                            </button>
                            <div v-if="showAllContracts"
                                class="absolute left-0 top-full z-10 mt-1 w-72 rounded-md border border-slate-200 bg-white p-2 shadow-lg">
                                <div class="max-h-32 overflow-y-auto">
                                    <div v-for="contract in contracts" :key="`all-${contract.id}`"
                                        class="rounded px-2 py-1 font-semibold text-slate-700 hover:bg-slate-50 truncate">
                                        {{ contract.token }} - {{ contract.holder }}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="flex flex-col gap-2 items-end">
                        <!-- <div v-if="sp_estimated_bag.total_consumption > 0" class="flex items-center gap-2 my-2"> -->
                        <div class="mt-2 flex items-center gap-x-2">
                            <!-- <button v-if="pairedReadings.filter(p => p.modified).length > 0"
                                @click="selectReading(null)" class="button-default-xs flex items-center gap-x-2">
                                <Icon name="fa6-solid:xmark" class="h-3.5 w-3.5 text-slate-500 shrink-0" />
                                {{ $t('common.deselect') }}
                            </button> -->
                            <button class="button-default-xs flex items-center gap-x-2" @click="showDialogNewReadings">
                                <Icon name="fa6-solid:plus" class="h-3.5 w-3.5 text-slate-500 shrink-0" />
                                {{ $t('billing_block.add_reading') }}
                            </button>
                        </div>
                        <div v-if="sp_estimated_bag" class="flex items-center gap-2 text-sm">
                            <span class="text-slate-500">{{ $t('billing_block.consumption_bag') }}</span>
                            <span class="text-slate-500">{{ parseInt(sp_estimated_bag.total_consumption) }} m3</span>
                            &rarr;
                            <div class="max-w-24">
                                <input type="number" v-model.number="total_estimated_bag"
                                    class="block w-full py-1 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm disabled:bg-slate-100 disabled:text-slate-400"
                                    style="max-width: fit-content;" />
                            </div>
                        </div>

                    </div>
                </div>
                <div class="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 my-1">
                    <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <p v-if="pairedReadings.length > 0" class="text-sm text-slate-500 my-2">
                            {{ $t('billing_block.select_reading_to_change') }}
                        </p>
                        <button v-if="pairedReadings.filter(p => p.modified).length > 0" @click="selectReading(null)"
                            class="border border-slate-300 h-6 w-6 flex items-center justify-center rounded-full shrink-0">
                            <Icon name="fa6-solid:arrow-rotate-left" class="h-3 w-3 text-slate-500" />
                        </button>
                        <label
                            class="inline-flex shrink-0 items-center gap-1.5 text-sm text-slate-600 cursor-pointer select-none">
                            <input type="checkbox" v-model="showControlReadings"
                                class="h-3.5 w-3.5 rounded border-slate-300 text-sky-600 focus:ring-sky-500" />
                            <span>{{ $t('billing_block.show_control_readings') }}<template
                                    v-if="controlReadingsCount > 0"> ({{ controlReadingsCount }})</template></span>
                        </label>
                    </div>
                    <div class="flex flex-wrap items-center gap-x-2">
                        <div class="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                            <span class="text-slate-500 text-sm">{{ $t('common.actions') }}</span>
                            <div
                                class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2 py-1">
                                <Icon name="fa6-solid:hand-holding-droplet"
                                    class="h-3.5 w-3.5 text-slate-500 shrink-0" />
                                <span class="font-medium">
                                    {{ $t('billing_block.use_estimated_bag') }}
                                </span>
                            </div>
                            <div
                                class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2 py-1">
                                <Icon name="fa6-solid:eye-dropper" class="h-3.5 w-3.5 text-slate-500 shrink-0" />
                                <span class="font-medium">
                                    {{ $t('billing_block.keep_estimated') }}
                                </span>
                            </div>
                            <div
                                class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2 py-1">
                                <Icon name="fa6-solid:eye" class="h-3.5 w-3.5 text-slate-500 shrink-0" />
                                <span class="font-medium">
                                    {{ $t('billing_block.control_reading') }}
                                </span>
                            </div>
                            <div
                                class="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 px-2 py-1">
                                <Icon name="fa6-solid:trash-can" class="h-3.5 w-3.5 text-slate-500 shrink-0" />
                                <span class="font-medium">
                                    {{ $t('common.delete') }}
                                </span>
                            </div>
                        </div>
                    </div>

                </div>

                <div class="overflow-y-auto border-t border-slate-200 pt-1"
                    :style="{ maxHeight: 'calc(100vh - 450px)', minHeight: 'calc(100vh - 450px)' }">
                    <div v-if="hasPendingBilling"
                        class="my-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800 font-semibold">
                        <p>
                            {{ $t('warning_block.warning_last_reading_pending_billing') }}
                        </p>
                    </div>
                    <div v-if="visiblePairedReadings.length === 0"
                        class="my-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                        <p>
                            {{ $t('billing_block.no_readings_to_change') }}
                        </p>
                    </div>



                    <div class="space-y-2">
                        <template v-for="(pair, index) in visiblePairedReadings"
                            :key="pair.original?.id || `new-${pair.modified?.id}`">
                            <!-- Arrow row: visual connector from last unselected reading → to new readings -->


                            <div
                                class="grid grid-cols-1 gap-2 md:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)] items-start">
                                <button v-if="pair.original" type="button" @click="selectReading(pair.original)"
                                    class="reading-card group relative h-fit w-full self-start overflow-hidden text-left rounded-lg border border-slate-200 px-2.5 py-2 shadow-sm transition-all hover:border-sky-300 hover:shadow-md"
                                    :class="{
                                        'bg-sky-50': pair.modified,
                                        'opacity-50': pair.original.is_control || pair.original.is_initial,
                                        'bg-green-50': pair.original.is_initial,
                                        'bg-orange-50': pair.original.is_close,
                                    }" :disabled="pair.original.is_initial">
                                    <!-- <span v-if="pair.original.is_estimated"
                                    class="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-semibold uppercase tracking-[0.35em] text-amber-500/35 md:text-xs">
                                    {{ $t('billing_block.estimated_reading') }}
                                </span> -->
                                    <div
                                        class="grid grid-cols-2 gap-x-2.5 gap-y-1 text-xs md:grid-cols-3 xl:grid-cols-4">
                                        <div>
                                            <span class="inline-flex items-center gap-1.5 py-1 text-xs text-slate-500">
                                                <Icon name="fa6-solid:calendar"
                                                    class="h-3.5 w-3.5 text-slate-400 shrink-0" />
                                                <span class="font-medium text-slate-500">{{
                                                    $t('billing_block.reading_date')
                                                }}</span>
                                            </span>
                                            <p class="text-[12px] font-medium text-slate-800 tabular-nums">
                                                {{ formatDate(pair.original.reading_date) }}</p>
                                        </div>
                                        <div>
                                            <span class="inline-flex items-center gap-1.5 py-1 text-xs text-slate-500">
                                                <Icon name="my-icon:meter-icon-black"
                                                    class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                <span class="font-medium text-slate-500">{{ $t('reading') }}</span>
                                            </span>
                                            <p class="text-[12px] text-slate-800 font-medium tabular-nums">
                                                {{ parseInt(pair.original.reading_value) }}
                                                <!-- <span v-if="pair.original?.is_estimated > 0"
                                                class="inline-flex items-center gap-1 py-1 text-[11px] font-medium text-amber-600">
                                                <Icon name="fa6-solid:eye-dropper"
                                                    class="h-3.5 w-3.5 shrink-0 text-amber-500" />
                                                {{ $t('billing_block.estimated_reading') }}

                                            </span> -->
                                            </p>
                                        </div>
                                        <div>
                                            <span class="inline-flex items-center gap-1.5 py-1 text-xs text-slate-500">
                                                <Icon name="fa6-solid:droplet-slash"
                                                    class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                <span class="font-medium text-slate-500">{{ $t('billing_block.leak')
                                                }}</span>
                                            </span>
                                            <p class="text-[12px] text-slate-800 font-medium tabular-nums">
                                                {{ parseInt(pair.original.leak_value || 0) }}
                                            </p>
                                        </div>
                                        <div>
                                            <span class="inline-flex items-center gap-1.5 py-1 text-xs text-slate-500">
                                                <Icon name="fa6-solid:droplet"
                                                    class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                <span class="font-medium text-slate-500">{{
                                                    $t('billing_block.consumption')
                                                }}</span>
                                            </span>
                                            <p class="text-[12px] text-slate-800 font-medium tabular-nums">
                                                {{ parseInt(pair.original.calculated_value) }}
                                                <span v-if="pair.original?.estimated_used > 0" class="text-yellow-600">
                                                    - {{ pair.original?.estimated_used || 0 }}
                                                </span>
                                            </p>
                                        </div>
                                        <!-- <div>
                                        <span class="inline-flex items-center gap-1.5 py-1 text-xs text-slate-500">
                                            <Icon name="fa6-solid:clock" class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                            <span class="font-medium text-slate-500">{{
                                                $t('billing_block.consumption_days')
                                                }}</span>
                                        </span>
                                        <p class="text-[12px] text-slate-800 font-medium tabular-nums">
                                            {{ parseInt(pair.original.consumption_days) }}
                                        </p>
                                    </div> -->
                                        <div v-if="!pair.original.is_control && !pair.original.is_initial">
                                            <span class="inline-flex items-center gap-1.5 py-1 text-xs text-slate-500">
                                                <Icon name="fa6-solid:clock"
                                                    class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                <span class="font-medium text-slate-500">{{
                                                    $t('meter')
                                                }}</span>
                                            </span>
                                            <p class="text-[12px] text-slate-800 font-medium tabular-nums">
                                                {{formatMeterOption(meters.find(m => m.id === pair.original.meter.id))}}
                                            </p>
                                        </div>
                                        <div v-if="pair.original.batch && !pair.original.is_control && !pair.original.is_initial"
                                            class="col-span-2">
                                            <span class="inline-flex items-center gap-1.5 py-1 text-xs text-slate-500">
                                                <Icon name="fa6-solid:clipboard-list"
                                                    class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                <span class="font-medium text-slate-500">{{
                                                    $t('readingbatch')
                                                }}</span>
                                            </span>
                                            <p class="text-[12px] text-slate-800 font-medium tabular-nums">
                                                <span>{{ pair.original.batch?.name }}</span>
                                                <span class="text-slate-400 text-xs">
                                                    ({{ formatDate(pair.original.batch?.processed_at) }})
                                                </span>
                                            </p>
                                        </div>
                                        <div v-if="pair.original.is_control" class="flex items-end justify-end">
                                            <span
                                                class="inline-flex items-center justify-end gap-1 text-[11px] font-medium text-sky-600">
                                                <Icon name="fa6-solid:eye" class="h-3.5 w-3.5 shrink-0 text-sky-500" />
                                                <span>
                                                    {{ $t('billing_block.control_reading') }}
                                                </span>
                                            </span>
                                        </div>
                                        <div v-if="pair.original.is_initial" class="flex items-end justify-end">
                                            <span
                                                class="inline-flex items-center justify-end gap-1 text-[11px] font-medium text-green-600">
                                                <Icon name="fa6-solid:flag"
                                                    class="h-3.5 w-3.5 shrink-0 text-green-500" />
                                                <span>
                                                    {{ $t('billing_block.initial_reading') }}
                                                </span>
                                            </span>
                                        </div>
                                        <div v-if="pair.original.is_estimated" class="flex items-end justify-end">
                                            <span
                                                class="inline-flex items-center justify-end gap-1 text-[11px] font-medium text-amber-600">
                                                <Icon name="fa6-solid:eye-dropper"
                                                    class="h-3.5 w-3.5 shrink-0 text-amber-500" />
                                                <span>
                                                    {{ $t('billing_block.estimated_reading') }}
                                                </span>
                                            </span>
                                        </div>
                                    </div>
                                </button>
                                <div v-else
                                    class="h-full min-h-[64px] w-full rounded-lg border border-dashed border-green-200 bg-green-50/50 px-3 py-2 flex items-center justify-end">
                                    <div class="grid grid-cols-2 gap-2">
                                        <span v-if="hasMultipleContracts"
                                            class="flex items-center gap-x-2 text-xs font-semibold uppercase tracking-wide text-green-600">
                                            <input type="checkbox" v-model="pair.modified.add_to_all"
                                                class="w-4 h-4 text-primary border-slate-300 rounded">
                                            <label for="add_to_all"
                                                class="text-xs font-semibold uppercase tracking-wide text-green-600">
                                                {{ $t('billing_block.add_to_all') }}
                                            </label>
                                        </span>
                                        <span v-else></span>

                                        <span
                                            class="flex items-center justify-end gap-x-2 text-xs font-semibold uppercase tracking-wide text-green-600">
                                            {{ pair.modified?.is_control ? t('billing_block.new_control_reading') :
                                                t('billing_block.new_reading') }}
                                            <Icon name="fa6-solid:right-long"
                                                class="h-3.5 w-3.5 shrink-0 text-green-500" />
                                        </span>
                                    </div>
                                </div>

                                <div v-if="pair.modified"
                                    class="reading-card group relative h-fit w-full self-start overflow-visible text-left rounded-lg border px-2.5 py-2 shadow-sm transition-all hover:border-sky-300 hover:shadow-md"
                                    :class="{
                                        'opacity-50 border-red-200 bg-red-50': readingsToDelete.includes(pair.modified.id),
                                        'bg-slate-50': unmodified_readings.includes(pair.modified.id),
                                        'bg-yellow-50': pair.modified.is_initial,
                                        'bg-orange-50': pair.modified.is_close,
                                        'border-red-200': pair.modified.within_period,
                                        'bg-sky-50 opacity-60': pair.modified.is_control,
                                        'border-slate-200': !readingsToDelete.includes(pair.modified.id) && !pair.modified.within_period
                                    }">

                                    <div class="absolute top-1 flex gap-1" :class="{
                                        'right-14': !readingsToKeepEstimated.includes(pair.modified.id),
                                        'right-2': readingsToKeepEstimated.includes(pair.modified.id),
                                    }">
                                        <button v-if="pair.original && pair.original.is_estimated &&
                                            !readingsToDelete.includes(pair.modified.id) &&
                                            !readingsToPassToControl.includes(pair.modified.id) &&
                                            !isPendingBillingLastReading(pair.modified)"
                                            @click="toggleKeepEstimatedReading(pair.modified)"
                                            class="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-red-500 transition-colors"
                                            :title="readingsToKeepEstimated.includes(pair.modified.id) ? $t('common.restore') : $t('billing_block.keep_estimated')">
                                            <Icon
                                                :name="readingsToKeepEstimated.includes(pair.modified.id) ? 'fa6-solid:rotate-left' : 'fa6-solid:eye-dropper'" />
                                        </button>
                                    </div>

                                    <div v-if="!readingsToPassToControl.includes(pair.modified.id) &&
                                        !readingsToDelete.includes(pair.modified.id) &&
                                        !readingsToKeepEstimated.includes(pair.modified.id) &&
                                        total_estimated_bag > 0 &&
                                        !pair.modified.is_estimated &&
                                        !unmodified_readings.includes(pair.modified.id) &&
                                        !isPendingBillingLastReading(pair.modified) &&
                                        !isPendingBillingPreviousReading(pair.modified)"
                                        class="absolute top-1 flex gap-1 right-20">
                                        <button
                                            v-if="pair.original && !pair.original.is_control && !readingsToDelete.includes(pair.modified.id)"
                                            @click="toggleAvoidUseEstimatedBagReading(pair.modified)"
                                            class="p-1 hover:bg-slate-100 rounded hover:text-red-500 transition-colors"
                                            :class="{
                                                'text-red-500 hover:text-red-600': readingsToAvoidUseEstimatedBag.includes(pair.modified.id),
                                                'text-slate-400 hover:text-slate-500': !readingsToAvoidUseEstimatedBag.includes(pair.modified.id),
                                            }"
                                            :title="readingsToAvoidUseEstimatedBag.includes(pair.modified.id) ? $t('common.restore') : $t('billing_block.use_estimated_bag')">
                                            <Icon
                                                :name="readingsToAvoidUseEstimatedBag.includes(pair.modified.id) ? 'fa6-solid:xmark' : 'fa6-solid:hand-holding-droplet'" />
                                        </button>
                                    </div>

                                    <div v-if="!readingsToKeepEstimated.includes(pair.modified.id) &&
                                        !isPendingBillingLastReading(pair.modified) &&
                                        !isPendingBillingPreviousReading(pair.modified)"
                                        class="absolute top-1 flex gap-1" :class="{
                                            'right-8': !readingsToPassToControl.includes(pair.modified.id),
                                            'right-2': readingsToPassToControl.includes(pair.modified.id),
                                        }">
                                        <button
                                            v-if="pair.original && !pair.original.is_control && !readingsToDelete.includes(pair.modified.id)"
                                            @click="togglePassToControlReading(pair.modified)"
                                            class="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-red-500 transition-colors"
                                            :title="readingsToPassToControl.includes(pair.modified.id) ? $t('common.restore') : $t('billing_block.short_control_reading')">
                                            <Icon
                                                :name="readingsToPassToControl.includes(pair.modified.id) ? 'fa6-solid:rotate-left' : 'fa6-solid:eye'" />
                                        </button>
                                    </div>
                                    <div v-if="!readingsToPassToControl.includes(pair.modified.id) &&
                                        !readingsToKeepEstimated.includes(pair.modified.id) &&
                                        !isPendingBillingLastReading(pair.modified) &&
                                        !isPendingBillingPreviousReading(pair.modified)"
                                        class="absolute top-1 right-2 flex gap-1">
                                        <button @click="toggleDeleteReading(pair.modified.id)"
                                            class="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-red-500 transition-colors"
                                            :title="readingsToDelete.includes(pair.modified.id) ? $t('common.restore') : $t('common.delete')">
                                            <Icon
                                                :name="readingsToDelete.includes(pair.modified.id) ? 'fa6-solid:rotate-left' : 'fa6-solid:trash-can'" />
                                        </button>
                                    </div>
                                    <div>
                                        <div v-if="readingsToDelete.includes(pair.modified.id)" class="w-full mb-1">
                                            <span class="text-red-500 text-xs font-bold uppercase">
                                                {{ $t('common.to_delete') }}</span>
                                        </div>
                                        <div v-if="
                                            (
                                                unmodified_readings.includes(pair.modified.id) ||
                                                pair.modified.within_period ||
                                                readingsToPassToControl.includes(pair.modified.id)
                                            ) &&
                                            !readingsToDelete.includes(pair.modified.id)" class="border-b pb-1 mb-1"
                                            :class="{
                                                'border-slate-200': unmodified_readings.includes(pair.modified.id),
                                                'border-red-200': pair.modified.within_period,
                                            }">
                                            <p v-if="unmodified_readings.includes(pair.modified.id) && !readingsToPassToControl.includes(pair.modified.id)"
                                                class="text-slate-500 text-xs font-bold uppercase">
                                                {{ $t('informative_block.info_unmodified_reading') }}
                                            </p>
                                            <p v-if="pair.modified.within_period"
                                                class="text-red-500 text-xs font-bold uppercase">
                                                {{ $t('informative_block.info_within_period') }}
                                            </p>
                                            <p v-if="readingsToPassToControl.includes(pair.modified.id)"
                                                class="text-sky-500 text-xs font-bold uppercase">
                                                {{ $t('informative_block.info_pass_to_control') }}
                                            </p>
                                            <p v-if="unmodified_readings.includes(pair.modified.id)"
                                                class="text-slate-500 text-xs">
                                                {{ $t('informative_block.info_unmodified_reading_changes') }}
                                            </p>
                                            <p v-if="pair.modified.within_period" class="text-red-500 text-xs">
                                                {{ $t('informative_block.info_within_period_unallow') }}
                                            </p>

                                        </div>
                                        <div class="flex items-start gap-2 grid grid-cols-4 mr-5">

                                            <div>
                                                <span class="inline-flex items-center gap-x-1 text-xs text-slate-500">
                                                    <Icon name="fa6-solid:calendar"
                                                        class="h-3.5 w-3.5 text-slate-400 shrink-0" />
                                                    <span class="font-medium text-slate-500">{{
                                                        $t('billing_block.reading_date')
                                                    }}</span>
                                                </span>
                                                <input type="date" v-model="pair.modified.reading_date" class="input"
                                                    :disabled="readingsToDelete.includes(pair.modified.id) ||
                                                        pair.modified.is_initial ||
                                                        (pair.original && pair.original.is_control && pair.modified.is_control) ||
                                                        readingsToKeepEstimated.includes(pair.modified.id) ||
                                                        isPendingBillingLastReading(pair.modified) ||
                                                        isPendingBillingPreviousReading(pair.modified)"
                                                    @change="recalculateNewReadingsConsumption(true)" />
                                            </div>
                                            <div>
                                                <span
                                                    class="inline-flex items-center gap-1.5 pb-1 text-xs text-slate-500">
                                                    <Icon name="my-icon:meter-icon-black"
                                                        class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                    <span class="font-medium text-slate-500 truncate">{{ $t('reading')
                                                        }}</span>
                                                </span>
                                                <input type="number" v-model="pair.modified.reading_value" class="input"
                                                    :disabled="readingsToDelete.includes(pair.modified.id) ||
                                                        (pair.original && pair.original.is_control && pair.modified.is_control) ||
                                                        (pair.modified.is_estimated) ||
                                                        isPendingBillingLastReading(pair.modified) ||
                                                        isPendingBillingPreviousReading(pair.modified)"
                                                    @input="recalculateNewReadingsConsumption(false)" />
                                            </div>
                                            <div :class="{
                                                'text-red-500': !allowSave && pair.modified.leak_value && pair.modified.leak_value > (pair.modified.calculated_value - Number(pair.modified.estimated_used || 0))
                                            }">
                                                <span
                                                    class="inline-flex items-center gap-1.5 pb-1 text-xs text-slate-500">
                                                    <Icon name="fa6-solid:droplet-slash"
                                                        class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                    <span class="font-medium text-slate-500 truncate">{{
                                                        $t('billing_block.leak')
                                                        }}</span>
                                                </span>
                                                <input type="number" v-model="pair.modified.leak_value" class="input"
                                                    :disabled="readingsToDelete.includes(pair.modified.id) ||
                                                        pair.modified.is_initial ||
                                                        (pair.original && pair.original.is_control && pair.modified.is_control) ||
                                                        readingsToKeepEstimated.includes(pair.modified.id) ||
                                                        isPendingBillingLastReading(pair.modified)"
                                                    @input="recalculateNewReadingsConsumption(true)" />
                                            </div>
                                            <div>
                                                <span
                                                    class="inline-flex items-center gap-1.5 pb-1 text-xs text-slate-500">
                                                    <Icon name="fa6-solid:droplet"
                                                        class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                    <span class="font-medium text-slate-500 truncate">{{
                                                        $t('billing_block.consumption')
                                                    }}</span>
                                                </span>
                                                <div class="flex items-center gap-2">
                                                    <input type="number" v-model="pair.modified.calculated_value"
                                                        class="input"
                                                        :disabled="readingsToDelete.includes(pair.modified.id) ||
                                                            pair.modified.is_initial ||
                                                            (pair.original && pair.original.is_control && pair.modified.is_control) ||
                                                            readingsToKeepEstimated.includes(pair.modified.id) ||
                                                            (lastReading && lastReading.id === pair.modified.id && contracts.some(c => c.pending_billing))"
                                                        @input="recalculateNewReadingsConsumption(true)" />
                                                    <!-- <div class="flex flex-col">
                                                    <span class="text-[11px] text-slate-400 whitespace-nowrap">
                                                        {{ $t('billing_block.real_consumption') }}
                                                    </span>
                                                    <span class="text-[11px] text-slate-400 whitespace-nowrap">
                                                        {{ (Number(pair.modified.calculated_value) || 0) -
                                                            (Number(pair.modified.leak_value) || 0) }}
                                                    </span>
                                                </div> -->
                                                </div>
                                                <div class="pt-1" v-if="
                                                    ((Number(pair.modified.calculated_value) || 0) - (Number(pair.modified.leak_value) || 0)) != Number(pair.modified.calculated_value) ||
                                                    ((Number(pair.modified.estimated_used) || 0) > 0)">
                                                    <span
                                                        class="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                                                        <span class="font-medium truncate">{{
                                                            $t('billing_block.real_consumption')
                                                        }}</span>
                                                        <span class="font-semibold text-slate-800 tabular-nums">
                                                            {{ (Number(pair.modified.calculated_value) || 0) -
                                                                (Number(pair.modified.leak_value) || 0) -
                                                                (Number(pair.modified.estimated_used) || 0) }}
                                                        </span>
                                                    </span>
                                                </div>
                                            </div>

                                            <div class="flex h-full min-w-0 flex-col justify-end">
                                                <label class="flex items-center gap-2 cursor-pointer" :class="{
                                                    'opacity-60': readingsToDelete.includes(pair.modified.id) ||
                                                        pair.modified.is_initial ||
                                                        (pair.original && pair.original.is_control && pair.modified.is_control) ||
                                                        readingsToKeepEstimated.includes(pair.modified.id) ||
                                                        isPendingBillingLastReading(pair.modified),
                                                }">
                                                    <span
                                                        class="inline-flex min-w-0 items-center gap-1.5 text-[11px] leading-snug text-slate-500">
                                                        <span class="font-medium text-slate-500">{{
                                                            $t('billing_block.block_estimated_correction') }}</span>
                                                    </span>
                                                    <input type="checkbox"
                                                        v-model="pair.modified.block_estimate_correction"
                                                        class="h-4 w-4 shrink-0 cursor-pointer rounded-md border-slate-300 text-sky-600 focus:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-60"
                                                        :disabled="readingsToDelete.includes(pair.modified.id) ||
                                                            pair.modified.is_initial ||
                                                            (pair.original && pair.original.is_control && pair.modified.is_control) ||
                                                            readingsToKeepEstimated.includes(pair.modified.id) ||
                                                            isPendingBillingLastReading(pair.modified)" />
                                                </label>
                                            </div>
                                            <div class="mt-2">
                                                <span
                                                    class="inline-flex items-center gap-1.5 pb-1 text-xs text-slate-500 truncate">
                                                    <Icon name="fa6-solid:pen-to-square"
                                                        class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                    <span class="font-medium text-slate-500 truncate">{{
                                                        $t('billing_block.estimated_correction') }}</span>
                                                </span>
                                                <input type="number" v-model="pair.modified.estimated_used" :class="{
                                                    'line-through text-red-600': pair.modified.block_estimate_correction,
                                                    'text-red-500': !allowSave && pair.modified.estimated_used && pair.modified.estimated_used > (pair.modified.calculated_value - Number(pair.modified.leak_value || 0))
                                                }" class="input" :disabled="readingsToDelete.includes(pair.modified.id) ||
                                                    pair.modified.is_initial ||
                                                    (pair.original && pair.original.is_control && pair.modified.is_control) ||
                                                    readingsToKeepEstimated.includes(pair.modified.id) ||
                                                    isPendingBillingLastReading(pair.modified) ||
                                                    pair.modified.block_estimate_correction"
                                                    @input="recalculateNewReadingsConsumption(false)" />
                                            </div>
                                            <div class="mt-2">
                                                <span
                                                    class="inline-flex items-center gap-1.5 pb-1 text-xs text-slate-500">
                                                    <Icon name="fa6-solid:map-pin"
                                                        class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                    <span class="font-medium text-slate-500 truncate">{{
                                                        $t('common.origin') }}</span>
                                                </span>
                                                <input type="text" v-model="pair.modified.origin" class="input"
                                                    :disabled="readingsToDelete.includes(pair.modified.id) ||
                                                        pair.modified.is_initial ||
                                                        isPendingBillingLastReading(pair.modified)"
                                                    @input="recalculateNewReadingsConsumption(false)" />
                                            </div>

                                            <div v-if="pair.modified.is_estimated"
                                                class="flex items-end justify-end text-xs h-full">
                                                <span
                                                    class="inline-flex items-center justify-end gap-1 font-medium text-amber-600">
                                                    <Icon name="fa6-solid:eye-dropper"
                                                        class="h-2.5 w-2.5 shrink-0 text-amber-500" />
                                                    <span>
                                                        {{ $t('billing_block.estimated_reading') }}
                                                    </span>
                                                </span>
                                            </div>

                                            <!-- <div>
                                            <span class="inline-flex items-center gap-1.5 pb-2 text-xs text-slate-500">
                                                <Icon name="fa6-solid:clock"
                                                    class="h-3.5 w-3.5 text-sky-500 shrink-0" />
                                                <span class="font-medium text-slate-500">{{
                                                    $t('billing_block.consumption_days')
                                                }}</span>
                                            </span>
                                            <input type="number" v-model="pair.modified.consumption_days"
                                                class="input max-w-24"
                                                :disabled="readingsToDelete.includes(pair.modified.id)"
                                                @input="recalculateNewReadingsConsumption(false)" />
                                        </div> -->
                                        </div>
                                    </div>
                                    <details v-if="!pair.modified.is_control && !pair.modified.is_initial"
                                        class="mt-1.5 border-t border-slate-200 pt-1.5 group">
                                        <summary
                                            class="flex items-center justify-between gap-2 cursor-pointer text-xs font-medium uppercase tracking-wide text-slate-500">
                                            <span class="flex items-center gap-x-1">
                                                <Icon name="fa6-solid:chevron-down"
                                                    class="h-3 w-3 shrink-0 text-slate-400 transition-all duration-300 group-open:rotate-180" />
                                                {{ $t('common.additional_values') }}
                                            </span>

                                            <span class="min-w-0">
                                                <span
                                                    class="text-[11px] normal-case tracking-normal text-slate-400 truncate">
                                                    {{ $t('billing_block.previous_reading') }}:
                                                    {{
                                                        formatDate(pair.modified.previous_reading_option_key?.includes('|')
                                                            ? pair.modified.previous_reading_option_key.split('|')[1] :
                                                            pair.modified.previous_reading_option_key) }}
                                                    <template v-if="getPreviousReadingLinkedSummary(pair.modified)">
                                                        · {{ getPreviousReadingLinkedSummary(pair.modified) }}
                                                    </template>
                                                    · {{ pair.modified.consumption_days }}
                                                    {{ t('billing_block.consumption_days') }}
                                                </span>
                                            </span>
                                        </summary>
                                        <div class="mt-1.5 grid grid-cols-2 gap-1.5">
                                            <div v-if="meters.length > 1" class="p-1.5">
                                                <label
                                                    class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                                                    {{ $t('meter') }}
                                                </label>
                                                <v-select class="block w-full custom-select"
                                                    v-model="pair.modified.meter_id" :options="meters"
                                                    :loading="loadingMeterIds" :get-option-label="formatMeterOption"
                                                    :reduce="(option) => option.id" @update:model-value="emitChange"
                                                    :disabled="readingsToDelete.includes(pair.modified.id)" />
                                            </div>
                                            <div class="p-1.5">
                                                <label
                                                    class="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                                                    {{ $t('readingbatch') }}
                                                </label>
                                                <v-select class="block w-full custom-select"
                                                    v-model="pair.modified.batch_id" :options="batches"
                                                    :loading="loadingBatches" :get-option-label="formatBatchOption"
                                                    :reduce="(option) => option.id" @update:model-value="emitChange"
                                                    :disabled="readingsToDelete.includes(pair.modified.id)" />
                                            </div>
                                        </div>
                                    </details>
                                </div>
                            </div>
                            <div v-if="pair.original && new_readings.length > 0 && pair.original.id === selectedReading?.id"
                                class="grid grid-cols-1 gap-2 md:grid-cols-2 items-stretch min-h-[3rem]">
                                <div class="flex flex-col justify-center items-end pr-2">
                                    <span class="text-slate-500 text-xs font-medium">
                                        {{ visiblePairedReadings[index - 1]?.original?.reading_date ?? '' }}</span>
                                    <span class="text-slate-400 text-xs">({{ $t('billing_block.reading_date') }})</span>
                                </div>
                                <div class="flex items-center gap-3 pl-0 py-2">
                                    <svg class="h-8 w-24 shrink-0 text-sky-500" viewBox="0 0 96 32" fill="none"
                                        stroke="currentColor" stroke-width="2.5" stroke-linecap="round"
                                        stroke-linejoin="round" aria-hidden="true">
                                        <path d="M0 16h76M72 10l6 6-6 6" />
                                    </svg>
                                    <span class="text-sm text-slate-600">
                                        {{ $t('billing_block.readings_continue_from_to', {
                                            from: visiblePairedReadings[index -
                                                1]?.original?.reading_date ?? '', to: latestNewReading?.reading_date ?? ''
                                        }) }}
                                    </span>
                                </div>
                            </div>
                        </template>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>