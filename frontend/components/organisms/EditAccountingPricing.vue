<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import H1Region from '../atoms/H1Region.vue';
import { useToast } from 'vue-toastification';
import { checkPermission } from '~/middleware/permission';

const { t } = useI18n();
const toast = useToast();
const objectPermissions = ref(null);
const {
    $AccountingPricingApiService,
    $AccountingAdditionalLineApiService,
    $AccountingConceptApiService,
    $AccountingTypeApiService,
    $AccountingCostCenterApiService,
    $PriceRateApiService,
    $ProductApiService,
    $LineItemTypeApiService,
    $PriceIntervalStretchApiService,
    $PriceVariableIntervalStretchApiService,
    $ExploitationApiService,
    $ConfiglistApiService,
    $AddressApiService,
} = useNuxtApp();

const props = defineProps({
    id: {
        type: Number,
        default: null,
    },
});

const emit = defineEmits(['close', 'changed']);

const loading = ref(false);
const loadingData = ref(false);
const loadingConcepts = ref(false);
const loadingRelations = ref(false);
const saving = ref(false);
const attemptedSave = ref(false);
/** 'relations' = category & selections; 'values' = token/name assignment */
const formStep = ref('relations');

const categories = ref([
    { token: 'invoice', name: t('invoice') },
    { token: 'lineitem', name: t('pricing_block.line_items') },
    { token: 'payment', name: t('payments') },
]);
const selectAddTaxes = ref(false);
const selectAddSubtotal = ref(false);
const selectedCategory = ref(null);

const accountingTypes = ref([]);
const accountingConcepts = ref([]);
const exploitations = ref([]);
const paymentTypes = ref([]);
const products = ref([]);
const priceRates = ref([]);
const lineItemTypes = ref([]);
const priceIntervals = ref([]);
const priceVariables = ref([]);
const selectedForeignIban = ref(false);
const selectedNationalIban = ref(false);
const selectedOutgoingPayments = ref(false);
const selectedIncomingPayments = ref(false);

/** Invoice category: exclusive choice (not a customizable config list). */
const INVOICE_CATEGORIES = [
    { token: 'normal', nameKey: 'pricing_block.accounting_pricing_invoice_category_normal' },
    { token: 'endowment', nameKey: 'pricing_block.accounting_pricing_invoice_category_endowment' },
    { token: 'irrecuperable', nameKey: 'pricing_block.accounting_pricing_invoice_category_irrecuperable' },
];
const selectedInvoiceCategory = ref('normal');
const selectedPaymentCategory = ref('normal');
const origins = ref([]);
const selectedOrigins = ref([]);
const loadingOrigins = ref(false);

const contractTypes = ref([]);
const selectedContractTypes = ref([]);
const loadingContractTypes = ref(false);
/** When endowment/irrecuperable: subtract previously declared normal invoices into this pricing. */
const undeclarePrevious = ref(false);

/** IBAN nationality and movement direction only apply to these payment methods. */
const IBAN_PAYMENT_TYPE_TOKENS = ['DIRECT_DEBIT', 'BANK_TRANSFER'];
/** Payment origin only applies to this payment method. */
const BANK_PAYMENT_TOKEN = 'BANK_PAYMENT';
const PAYMENT_ORIGIN_OPTIONS = [
    { token: 'box_office', nameKey: 'billing_block.box_office' },
    { token: 'post_office', nameKey: 'billing_block.post_office' },
];

/** Form-level defaults applied to every saved object (overridable per assignment row). */
const token = ref('');
const tokenReturn = ref('');
const name = ref('');
const declaredAs = ref('');
/** Default for group_values; when true, matching rows merge into one record on save. */
const groupValues = ref(true);
/** Payment only. Backend splits generated lines by each available payment type. */
const separateByType = ref(false);
/** Invoice only. Shared pricing, one generated line per invoice origin. */
const separateByOrigin = ref(false);
/** BANK_PAYMENT only. null handles every origin; a token handles just that one. */
const selectedPaymentOrigin = ref(null);
/** Payment only. Grouped BANK_PAYMENT lines are summed per movement origin. */
const separateByPaymentOrigin = ref(false);
const is_default = ref(false);
const is_active = ref(true);
const selectedExploitation = ref(null);
const selectedCompany = ref(null);
const companies = ref([]);
const banks = ref([]);
const selectedBanks = ref([]);
const loadingBanks = ref(false);
const selectedAccountingConcept = ref(null);
/** Optional singular cost center — lineitem & payment (not invoice). */
const selectedCostCenter = ref(null);
const costCenters = ref([]);
const loadingCostCenters = ref(false);

const selectedPaymentTypes = ref([]);
const selectedProducts = ref([]);
const selectedPriceRates = ref([]);
const selectedLineItemTypes = ref([]);
const selectedPriceIntervals = ref([]);
const selectedPriceVariables = ref([]);

/** Map keyed by `${kind}:${id}` → { useDefault, token, tokenReturn, name, declaredAs, costCenter, groupValues } */
const valueAssignments = ref({});
/** Map keyed by `${kind}:${id}` → { id, token, tokenReturn, name, declaredAs } for rows already saved. */
const existingAssignments = ref({});
const loadingExisting = ref(false);
/** When invoice / no per-row assignments: an existing record covers the selection. */
const existingSelection = ref(null);

/** Extra declaration lines attached to this accounting pricing (edit mode). */
const additionalLines = ref([]);
const loadingAdditionalLines = ref(false);
const savingAdditionalLine = ref(false);
const showAdditionalLinePanel = ref(false);
const additionalLineAttemptedSave = ref(false);
const additionalLineConcepts = ref([]);
const loadingAdditionalLineConcepts = ref(false);
const additionalLineForm = ref({
    id: null,
    token: '',
    tokenReturn: '',
    name: '',
    declaredAs: '',
    accountingConcept: null,
    isNegative: false,
});

const showExploitation = computed(() => exploitations.value.length > 1);
const isEditing = computed(() => !!props.id);
/** Snapshot: loaded record went deeper than products, so those children stay editable. */
const loadedHasProductChildren = ref(false);
const canEditProductChildren = computed(
    () => !isEditing.value || loadedHasProductChildren.value,
);

const showsCostCenter = computed(
    () => selectedCategory.value === 'lineitem' || selectedCategory.value === 'payment',
);

const assignmentKey = (kind, id) => `${kind}:${String(id)}`;

/** Deepest relation field → assignment kind (used to map find-existing results). */
const EXISTING_RELATION_PRIORITY = [
    ['price_variables', 'price_variable'],
    ['price_intervals', 'price_interval'],
    ['line_item_types', 'line_item_type'],
    ['price_rates', 'price_rate'],
    ['products', 'product'],
    ['payment_types', 'payment_type'],
    ['origins', 'origin'],
    ['contract_types', 'contract_type'],
];

const relationIdsOf = (items) =>
    (items || [])
        .map((item) => (item && typeof item === 'object' ? item.id ?? item.code : item))
        .filter((id) => id !== undefined && id !== null && id !== '');

/** Map find-existing records → `{ [assignmentKey]: { id, token, tokenReturn, name, declaredAs } }`. */
const mapExistingRecordsToKeys = (records) => {
    const map = {};
    (records || []).forEach((record) => {
        const meta = {
            id: record.id,
            token: record.token || '',
            tokenReturn: record.token_return || '',
            name: record.name || '',
            declaredAs: record.declared_as || '',
        };

        // Preferred flat shape: { kind, value_id }
        const flatId = record.value_id ?? record.relation_id ?? null;
        if (record.kind && flatId != null) {
            map[assignmentKey(record.kind, flatId)] = meta;
            return;
        }

        for (const [field, kind] of EXISTING_RELATION_PRIORITY) {
            const ids = relationIdsOf(record[field]);
            if (!ids.length) continue;
            ids.forEach((id) => {
                map[assignmentKey(kind, id)] = meta;
            });
            return;
        }
    });
    return map;
};

const conceptOptions = computed(() =>
    accountingConcepts.value.map((c) => ({
        ...c,
        label: `${c.token || '—'} · ${c.name}`,
        code: c.id,
    })),
);

const additionalLineConceptOptions = computed(() =>
    additionalLineConcepts.value.map((c) => ({
        ...c,
        label: `${c.token || '—'} · ${c.name}`,
        code: c.id,
    })),
);

const activeAdditionalLines = computed(() =>
    (additionalLines.value || []).filter((line) => line.is_active !== false),
);

const resetAdditionalLineForm = () => {
    additionalLineForm.value = {
        id: null,
        token: '',
        tokenReturn: '',
        name: '',
        declaredAs: '',
        accountingConcept: null,
        isNegative: false,
    };
    additionalLineAttemptedSave.value = false;
};

const mapAdditionalLineConceptOption = (concept) => {
    if (!concept) return null;
    return {
        ...concept,
        code: concept.id,
        label: `${concept.token || '—'} · ${concept.name}`,
    };
};

const loadAdditionalLineConcepts = async () => {
    loadingAdditionalLineConcepts.value = true;
    try {
        const response = await $AccountingConceptApiService.getAll('', 1, null, false);
        additionalLineConcepts.value = response.results || [];
    } catch (error) {
        console.error(error);
        additionalLineConcepts.value = [];
    } finally {
        loadingAdditionalLineConcepts.value = false;
    }
};

const loadAdditionalLines = async () => {
    if (!props.id) {
        additionalLines.value = [];
        return;
    }
    loadingAdditionalLines.value = true;
    try {
        const response = await $AccountingAdditionalLineApiService.getAll(props.id, true);
        additionalLines.value = response.results || [];
    } catch (error) {
        console.error(error);
        // Keep nested lines from getDetail when the list endpoint is unavailable.
    } finally {
        loadingAdditionalLines.value = false;
    }
};

const openAdditionalLinePanel = async (line = null) => {
    if (!props.id) {
        toast.info(t('pricing_block.accounting_pricing_additional_lines_save_first'));
        return;
    }
    if (!additionalLineConcepts.value.length) {
        await loadAdditionalLineConcepts();
    }
    if (line) {
        additionalLineForm.value = {
            id: line.id,
            token: line.token || '',
            tokenReturn: line.token_return || '',
            name: line.name || '',
            declaredAs: line.declared_as || '',
            accountingConcept: mapAdditionalLineConceptOption(line.accounting_concept),
            isNegative: !!line.is_negative,
        };
    } else {
        resetAdditionalLineForm();
    }
    additionalLineAttemptedSave.value = false;
    showAdditionalLinePanel.value = true;
};

const closeAdditionalLinePanel = () => {
    showAdditionalLinePanel.value = false;
    resetAdditionalLineForm();
};

const canSaveAdditionalLine = computed(() => {
    const form = additionalLineForm.value;
    return !!(
        (form.token || '').trim() &&
        (form.name || '').trim() &&
        (form.accountingConcept?.code ?? form.accountingConcept?.id)
    );
});

const saveAdditionalLine = async () => {
    additionalLineAttemptedSave.value = true;
    if (!props.id || !canSaveAdditionalLine.value) return;

    savingAdditionalLine.value = true;
    try {
        const form = additionalLineForm.value;
        await $AccountingAdditionalLineApiService.save({
            id: form.id || null,
            accounting_pricing_id: props.id,
            accounting_concept_id: form.accountingConcept?.code ?? form.accountingConcept?.id,
            token: (form.token || '').trim(),
            token_return: optionalText(form.tokenReturn),
            name: (form.name || '').trim(),
            declared_as: optionalText(form.declaredAs),
            is_negative: !!form.isNegative,
            is_active: true,
        });
        closeAdditionalLinePanel();
        await loadAdditionalLines();
        toast.success(t('common.correct_save'));
    } catch (error) {
        console.error(error);
        toast.error(t('common.error'));
    } finally {
        savingAdditionalLine.value = false;
    }
};

const deactivateAdditionalLine = async (line) => {
    if (!line?.id) return;
    try {
        await $AccountingAdditionalLineApiService.doDelete({ id: line.id });
        await loadAdditionalLines();
        toast.success(t('common.deactivated'));
    } catch (error) {
        console.error(error);
        toast.error(t('common.error'));
    }
};

const itemLabel = (item) =>
    item?.label || item?.name || String(item?.code ?? item?.id ?? '');

const kindLabel = (kind) => {
    const map = {
        payment_type: t('payment_types'),
        product: t('product'),
        price_rate: t('price_rate'),
        line_item_type: t('line_item'),
        price_interval: t('pricing_block.price_interval'),
        price_variable: t('pricing_block.variable_price'),
        origin: t('common.origins'),
        contract_type: t('common.usage_type'),
    };
    return map[kind] || kind;
};

const unselectedByCode = (all, selected) => {
    const selectedIds = new Set((selected || []).map((item) => item.code ?? item.id));
    return (all || []).filter((item) => !selectedIds.has(item.code ?? item.id));
};

const unselectedPriceRates = computed(() =>
    unselectedByCode(priceRates.value, selectedPriceRates.value),
);

const unselectedLineItemTypes = computed(() =>
    unselectedByCode(lineItemTypes.value, selectedLineItemTypes.value),
);

/**
 * Levels that receive token+name rows.
 * Products only appear when no deeper cascade is selected.
 * Price rates / line items / intervals / variables each get their own rows when selected.
 */
const summarizeAssignmentRows = (rows) => {
    let keepingDefault = 0;
    let hasCustom = 0;
    let isEmpty = 0;
    let alreadyExists = 0;

    (rows || []).forEach((row) => {
        if (row.alreadyExists) {
            alreadyExists += 1;
            return;
        }
        if (row.useDefault) {
            keepingDefault += 1;
            return;
        }
        const filled =
            !!(row.customToken || '').trim() && !!(row.customName || '').trim();
        if (filled) hasCustom += 1;
        else isEmpty += 1;
    });

    return {
        keepingDefault,
        hasCustom,
        isEmpty,
        alreadyExists,
        total: (rows || []).length,
    };
};

const valueAssignmentGroups = computed(() => {
    const groups = [];

    const toRows = (kind, items, rowHintFn = null) =>
        (items || []).map((item) => {
            const key = assignmentKey(kind, item.code ?? item.id);
            const assignment = valueAssignments.value[key] || {
                useDefault: true,
                token: '',
                tokenReturn: '',
                name: '',
                declaredAs: '',
                costCenter: null,
                groupValues: true,
            };
            return {
                key,
                kind,
                kindLabel: kindLabel(kind),
                item,
                label: itemLabel(item),
                hint: rowHintFn ? rowHintFn(item) : null,
                useDefault: assignment.useDefault,
                customToken: assignment.token,
                customTokenReturn: assignment.tokenReturn,
                customName: assignment.name,
                customDeclaredAs: assignment.declaredAs,
                customCostCenter: assignment.costCenter || null,
                customGroupValues:
                    assignment.groupValues === undefined
                        ? true
                        : !!assignment.groupValues,
                alreadyExists: !!existingAssignments.value[key],
                existing: existingAssignments.value[key] || null,
            };
        });

    const pushGroup = (kind, title, rows) => {
        if (!rows.length) return;
        groups.push({
            kind,
            title,
            rows,
            summary: summarizeAssignmentRows(rows),
        });
    };

    if (selectedCategory.value === 'payment' && selectedPaymentTypes.value.length) {
        pushGroup(
            'payment_type',
            t('payment_types'),
            toRows('payment_type', selectedPaymentTypes.value),
        );
        return groups;
    }

    if (
        selectedCategory.value === 'invoice' &&
        selectedInvoiceCategory.value === 'normal' &&
        selectedOrigins.value.length
    ) {
        pushGroup(
            'origin',
            t('common.origins'),
            toRows('origin', selectedOrigins.value),
        );
        return groups;
    }

    if (
        selectedCategory.value === 'invoice' &&
        selectedInvoiceCategory.value === 'normal' &&
        selectedContractTypes.value.length
    ) {
        pushGroup(
            'contract_type',
            t('common.usage_type'),
            toRows('contract_type', selectedContractTypes.value),
        );
        return groups;
    }

    if (selectedCategory.value !== 'lineitem') return groups;

    const hasDeeperThanProduct =
        selectedPriceRates.value.length > 0 ||
        selectedLineItemTypes.value.length > 0 ||
        selectedPriceIntervals.value.length > 0 ||
        selectedPriceVariables.value.length > 0;

    if (selectedProducts.value.length && !hasDeeperThanProduct) {
        pushGroup(
            'product',
            t('common.products'),
            toRows('product', selectedProducts.value),
        );
        return groups;
    }

    if (selectedPriceRates.value.length) {
        pushGroup(
            'price_rate',
            t('common.price_rates'),
            toRows('price_rate', selectedPriceRates.value, (rate) => {
                const childCount = selectedLineItemTypes.value.filter(
                    (lit) => String(lit.price_rate_id) === String(rate.code ?? rate.id),
                ).length;
                if (childCount > 0) {
                    return t('pricing_block.accounting_pricing_parent_with_overrides_hint');
                }
                return t('pricing_block.accounting_pricing_parent_covers_children_hint');
            }),
        );
    }

    if (selectedLineItemTypes.value.length) {
        const hasDeeper =
            selectedPriceIntervals.value.length > 0 ||
            selectedPriceVariables.value.length > 0;
        pushGroup(
            'line_item_type',
            t('pricing_block.line_items'),
            toRows('line_item_type', selectedLineItemTypes.value, () =>
                hasDeeper
                    ? t('pricing_block.accounting_pricing_parent_with_overrides_hint')
                    : null,
            ),
        );
    }

    if (selectedPriceIntervals.value.length) {
        pushGroup(
            'price_interval',
            t('pricing_block.price_interval'),
            toRows('price_interval', selectedPriceIntervals.value),
        );
    }

    if (selectedPriceVariables.value.length) {
        pushGroup(
            'price_variable',
            t('pricing_block.variable_price'),
            toRows('price_variable', selectedPriceVariables.value),
        );
    }

    return groups;
});

const assignmentRows = computed(() =>
    valueAssignmentGroups.value.flatMap((group) => group.rows),
);

const hasAssignmentRows = computed(() => assignmentRows.value.length > 0);

const hasSavableAssignments = computed(() => {
    if (isEditing.value) return true;
    if (hasAssignmentRows.value) {
        return assignmentRows.value.some((row) => !row.alreadyExists);
    }
    return !existingSelection.value;
});

/** Relations required before showing default token/name. */
const paymentTypeTokenById = computed(() => {
    const map = new Map();
    paymentTypes.value.forEach((item) => {
        const id = item?.code ?? item?.id;
        if (id == null || !item?.token) return;
        map.set(String(id), item.token);
    });
    return map;
});

const selectionIncludesIbanPayment = (paymentTypeIds) =>
    (paymentTypeIds || []).some((id) =>
        IBAN_PAYMENT_TYPE_TOKENS.includes(paymentTypeTokenById.value.get(String(id))),
    );

const showsIbanPaymentScope = computed(
    () =>
        selectedCategory.value === 'payment' &&
        selectedPaymentTypes.value.some((item) =>
            IBAN_PAYMENT_TYPE_TOKENS.includes(item?.token),
        ),
);

/**
 * A checked IBAN type and a checked direction together claim that combination.
 * Anything not under a checked option goes to the default pricing
 * (all four flags false, or the first one found).
 * Omitted (non direct-debit / bank-transfer) is sent as false.
 */
const ibanPaymentScopePayload = (paymentTypeIds = null) => {
    const ids = paymentTypeIds ?? idsOf(selectedPaymentTypes.value);
    const active =
        selectedCategory.value === 'payment' && selectionIncludesIbanPayment(ids);
    return {
        foreign_iban: active && selectedForeignIban.value,
        national_iban: active && selectedNationalIban.value,
        outgoing_payments: active && selectedOutgoingPayments.value,
        incoming_payments: active && selectedIncomingPayments.value,
    };
};

const selectionIncludesBankPayment = (paymentTypeIds) =>
    (paymentTypeIds || []).some(
        (id) => paymentTypeTokenById.value.get(String(id)) === BANK_PAYMENT_TOKEN,
    );

const selectionIsOnlyBankPayment = (paymentTypeIds) => {
    const ids = paymentTypeIds || [];
    return (
        ids.length > 0 &&
        ids.every((id) => paymentTypeTokenById.value.get(String(id)) === BANK_PAYMENT_TOKEN)
    );
};

const showsBankPaymentOrigin = computed(
    () =>
        selectedCategory.value === 'payment' &&
        selectedPaymentTypes.value.some((item) => item?.token === BANK_PAYMENT_TOKEN),
);

const bankPaymentOriginExclusive = computed(
    () =>
        selectedPaymentTypes.value.length > 0 &&
        selectedPaymentTypes.value.every((item) => item?.token === BANK_PAYMENT_TOKEN),
);

const paymentOriginOptions = computed(() =>
    PAYMENT_ORIGIN_OPTIONS.map((item) => ({
        token: item.token,
        name: t(item.nameKey),
    })),
);

const paymentOriginHint = computed(() => {
    if (!bankPaymentOriginExclusive.value) {
        return t('pricing_block.accounting_pricing_payment_origin_mixed_hint');
    }
    if (
        selectedPaymentOrigin.value === 'box_office' ||
        selectedPaymentOrigin.value === 'post_office'
    ) {
        return t('pricing_block.accounting_pricing_payment_origin_only_hint');
    }
    return t('pricing_block.accounting_pricing_payment_origin_all_hint');
});

/**
 * A single origin is sent only when BANK_PAYMENT is the sole payment type.
 * Grouped lines can still split bank payments by origin when other types are selected.
 */
const bankPaymentOriginPayload = (paymentTypeIds = null, grouped = null) => {
    const ids = paymentTypeIds ?? idsOf(selectedPaymentTypes.value);
    const linesGrouped = grouped === null || grouped === undefined ? groupValues.value : !!grouped;
    const active = selectedCategory.value === 'payment';
    const onlyBank = active && selectionIsOnlyBankPayment(ids);
    const includesBank = active && selectionIncludesBankPayment(ids);
    return {
        payment_origin: onlyBank ? selectedPaymentOrigin.value || null : null,
        separate_by_payment_origin:
            includesBank && linesGrouped ? !!separateByPaymentOrigin.value : false,
    };
};

const selectPaymentOrigin = (origin) => {
    if (origin && !bankPaymentOriginExclusive.value) return;
    selectedPaymentOrigin.value = origin || null;
};

const resetIbanPaymentScope = () => {
    selectedForeignIban.value = false;
    selectedNationalIban.value = false;
    selectedOutgoingPayments.value = false;
    selectedIncomingPayments.value = false;
};

const applyIbanPaymentScope = (response) => {
    selectedForeignIban.value = response?.foreign_iban === true;
    selectedNationalIban.value = response?.national_iban === true;
    selectedOutgoingPayments.value = response?.outgoing_payments === true;
    selectedIncomingPayments.value = response?.incoming_payments === true;
};

const showsInvoiceOrigins = computed(
    () =>
        selectedCategory.value === 'invoice' &&
        selectedInvoiceCategory.value === 'normal',
);

const showsInvoiceContractTypes = computed(
    () =>
        selectedCategory.value === 'invoice' &&
        selectedInvoiceCategory.value === 'normal',
);

const showsUndeclarePrevious = computed(
    () =>
        selectedCategory.value === 'invoice' &&
        (selectedInvoiceCategory.value === 'endowment' ||
            selectedInvoiceCategory.value === 'irrecuperable'),
);

const invoiceCategoryOptions = computed(() =>
    INVOICE_CATEGORIES.map((item) => ({
        token: item.token,
        name: t(item.nameKey),
    })),
);

const invoiceCategoryHint = computed(() => {
    if (selectedInvoiceCategory.value === 'normal') {
        return t('pricing_block.accounting_pricing_invoice_category_normal_hint');
    }
    if (selectedInvoiceCategory.value === 'endowment') {
        return t('pricing_block.accounting_pricing_invoice_category_endowment_hint');
    }
    return t('pricing_block.accounting_pricing_invoice_category_irrecuperable_hint');
});

const undeclarePreviousHint = computed(() => {
    if (selectedInvoiceCategory.value === 'irrecuperable') {
        return t('pricing_block.accounting_pricing_undeclare_previous_irrecuperable_hint');
    }
    return t('pricing_block.accounting_pricing_undeclare_previous_endowment_hint');
});

const resetInvoiceScope = () => {
    selectedInvoiceCategory.value = 'normal';
    selectedOrigins.value = [];
    selectedContractTypes.value = [];
    undeclarePrevious.value = false;
    separateByOrigin.value = false;
};

const resetPaymentScope = () => {
    selectedPaymentCategory.value = 'normal';
    separateByType.value = false;
    selectedPaymentOrigin.value = null;
    separateByPaymentOrigin.value = false;
};

const selectInvoiceCategory = (token) => {
    if (isEditing.value) return;
    if (selectedInvoiceCategory.value === token) return;
    selectedInvoiceCategory.value = token;
    if (token === 'normal') {
        undeclarePrevious.value = false;
    } else {
        selectedOrigins.value = [];
        selectedContractTypes.value = [];
        valueAssignments.value = {};
        clearExistingLookup();
    }
};

/**
 * Invoice scope flags sent with every invoice accounting pricing.
 * Origins and contract types only apply to normal; undeclare_previous only to endowment/irrecuperable.
 */
const invoiceScopePayload = () => {
    if (selectedCategory.value !== 'invoice') {
        return {
            invoice_category: null,
            undeclare_previous: false,
        };
    }
    const category = selectedInvoiceCategory.value || 'normal';
    return {
        invoice_category: category,
        undeclare_previous:
            (category === 'endowment' || category === 'irrecuperable') &&
            undeclarePrevious.value,
    };
};

const applyInvoiceScope = (response) => {
    const category = response?.invoice_category || 'normal';
    selectedInvoiceCategory.value = INVOICE_CATEGORIES.some((c) => c.token === category)
        ? category
        : 'normal';
    undeclarePrevious.value =
        (selectedInvoiceCategory.value === 'endowment' ||
            selectedInvoiceCategory.value === 'irrecuperable') &&
        response?.undeclare_previous === true;
    separateByOrigin.value = response?.separate_by_origin === true;
};

const paymentCategoryOptions = computed(() =>
    INVOICE_CATEGORIES.map((item) => ({
        token: item.token,
        name: t(item.nameKey),
    })),
);

const paymentCategoryHint = computed(() => {
    if (selectedPaymentCategory.value === 'normal') {
        return t('pricing_block.accounting_pricing_payment_category_normal_hint');
    }
    if (selectedPaymentCategory.value === 'endowment') {
        return t('pricing_block.accounting_pricing_payment_category_endowment_hint');
    }
    return t('pricing_block.accounting_pricing_payment_category_irrecuperable_hint');
});

const selectPaymentCategory = (token) => {
    if (isEditing.value) return;
    if (selectedPaymentCategory.value === token) return;
    selectedPaymentCategory.value = token;
};

/**
 * Payment category is an exclusive choice, same tokens as invoice.
 * Sent only as an extra field; the rest of the payment payload stays unchanged.
 */
const paymentScopePayload = () => {
    if (selectedCategory.value !== 'payment') {
        return { invoice_category: null };
    }
    return {
        invoice_category: selectedPaymentCategory.value || 'normal',
    };
};

const applyPaymentScope = (response) => {
    const category = response?.invoice_category || 'normal';
    selectedPaymentCategory.value = INVOICE_CATEGORIES.some((c) => c.token === category)
        ? category
        : 'normal';
    separateByType.value = response?.separate_by_type === true;
    separateByPaymentOrigin.value = response?.separate_by_payment_origin === true;
    selectedPaymentOrigin.value =
        response?.payment_origin === 'box_office' || response?.payment_origin === 'post_office'
            ? response.payment_origin
            : null;
    if (!bankPaymentOriginExclusive.value) {
        selectedPaymentOrigin.value = null;
    }
};

const ibanScopeHint = computed(() => {
    const foreign = selectedForeignIban.value;
    const national = selectedNationalIban.value;
    if (!foreign && !national) {
        return t('pricing_block.accounting_pricing_iban_default_hint');
    }
    if (foreign && national) {
        return t('pricing_block.accounting_pricing_iban_both_hint');
    }
    if (foreign) return t('pricing_block.accounting_pricing_iban_foreign_hint');
    return t('pricing_block.accounting_pricing_iban_national_hint');
});

const movementScopeHint = computed(() => {
    const outgoing = selectedOutgoingPayments.value;
    const incoming = selectedIncomingPayments.value;
    if (!outgoing && !incoming) {
        return t('pricing_block.accounting_pricing_movement_default_hint');
    }
    if (outgoing && incoming) {
        return t('pricing_block.accounting_pricing_movement_both_hint');
    }
    if (incoming) return t('pricing_block.accounting_pricing_movement_incoming_hint');
    return t('pricing_block.accounting_pricing_movement_outgoing_hint');
});

const relationsReady = computed(() => {
    if (!selectedCategory.value || !selectedAccountingConcept.value) return false;
    if (selectedCategory.value === 'invoice') return !!selectedInvoiceCategory.value;
    if (selectedCategory.value === 'payment') {
        return selectedPaymentTypes.value.length > 0 && !!selectedPaymentCategory.value;
    }
    if (selectedCategory.value === 'lineitem') return selectedProducts.value.length > 0;
    return false;
});

const canGoToValuesStep = computed(() => relationsReady.value);

const clearExistingLookup = () => {
    existingAssignments.value = {};
    existingSelection.value = null;
};

const exploitationIdForSave = () => {
    if (selectedExploitation.value?.code != null) return selectedExploitation.value.code;
    try {
        return localStorage.getItem('exploitation') || null;
    } catch (error) {
        return null;
    }
};

const buildFindExistingPayload = () => ({
    exploitation: exploitationIdForSave(),
    company: selectedCompany.value?.code ?? null,
    accounting_concept: selectedAccountingConcept.value?.code ?? null,
    category: selectedCategory.value,
    ...buildRelationPayload(),
    ...ibanPaymentScopePayload(),
    ...bankPaymentOriginPayload(),
    ...invoiceScopePayload(),
    ...paymentScopePayload(),
});

const loadExistingAssignments = async () => {
    loadingExisting.value = true;
    clearExistingLookup();
    try {
        const response = await $AccountingPricingApiService.findExisting(
            buildFindExistingPayload(),
        );

        // Ignore the record currently being edited so its token/name stay writable.
        const results = (response.results || []).filter(
            (record) => !props.id || String(record.id) !== String(props.id),
        );

        const byKey = mapExistingRecordsToKeys(results);
        existingAssignments.value = byKey;

        if (!isEditing.value && !Object.keys(byKey).length && results.length) {
            const first = results[0];
            existingSelection.value = {
                id: first.id,
                token: first.token || '',
                tokenReturn: first.token_return || '',
                name: first.name || '',
                declaredAs: first.declared_as || '',
            };
        }
    } catch (error) {
        console.error(error);
        clearExistingLookup();
        toast.error(t('common.error'));
    } finally {
        loadingExisting.value = false;
    }
};

const goToValuesStep = async () => {
    attemptedSave.value = true;
    if (!canGoToValuesStep.value) {
        toast.error(t('common.required_fields'));
        return;
    }
    ensureAssignments();
    applyCompanyFromExploitation();
    attemptedSave.value = false;
    formStep.value = 'values';
    await loadExistingAssignments();
};

const goToRelationsStep = () => {
    formStep.value = 'relations';
    attemptedSave.value = false;
    clearExistingLookup();
};

const lineitemCascadeLevel = computed(() => {
    if (selectedCategory.value !== 'lineitem') return null;
    if (selectedPriceVariables.value.length || selectedPriceIntervals.value.length) {
        return 'leaf';
    }
    if (selectedLineItemTypes.value.length) return 'line_item_type';
    if (selectedPriceRates.value.length) return 'price_rate';
    if (selectedProducts.value.length) return 'product';
    return null;
});

const showLineitemCascadeHint = computed(
    () => selectedCategory.value === 'lineitem' && !!selectedAccountingConcept.value,
);

const showStoppedAtLevelHint = computed(() => {
    if (!showLineitemCascadeHint.value || !canEditProductChildren.value) return false;
    const level = lineitemCascadeLevel.value;
    if (level === 'product') return true;
    if (level === 'price_rate' && !selectedLineItemTypes.value.length) return true;
    if (
        level === 'line_item_type' &&
        !selectedPriceIntervals.value.length &&
        !selectedPriceVariables.value.length &&
        (priceIntervals.value.length > 0 || priceVariables.value.length > 0)
    ) {
        return true;
    }
    return false;
});

const showPartialPriceRatesHint = computed(
    () =>
        selectedCategory.value === 'lineitem' &&
        selectedProducts.value.length > 0 &&
        priceRates.value.length > 0 &&
        selectedPriceRates.value.length > 0 &&
        unselectedPriceRates.value.length > 0,
);

const showPartialLineItemsHint = computed(
    () =>
        selectedCategory.value === 'lineitem' &&
        lineItemTypes.value.length > 0 &&
        selectedLineItemTypes.value.length > 0 &&
        unselectedLineItemTypes.value.length > 0,
);

/** Saved line items can exist without price rates (scoped save omits parent levels). */
const showLineItemTypesSection = computed(
    () => selectedPriceRates.value.length > 0 || selectedLineItemTypes.value.length > 0,
);

const showPriceIntervalsSection = computed(
    () =>
        selectedPriceIntervals.value.length > 0 ||
        (selectedLineItemTypes.value.length > 0 && priceIntervals.value.length > 0),
);

const showPriceVariablesSection = computed(
    () =>
        selectedPriceVariables.value.length > 0 ||
        (selectedLineItemTypes.value.length > 0 && priceVariables.value.length > 0),
);

const ensureAssignments = () => {
    const next = { ...valueAssignments.value };
    const validKeys = new Set();
    assignmentRows.value.forEach((row) => {
        validKeys.add(row.key);
        if (!next[row.key]) {
            next[row.key] = {
                useDefault: true,
                token: '',
                tokenReturn: '',
                name: '',
                declaredAs: '',
                costCenter: null,
                groupValues: true,
            };
        }
    });
    Object.keys(next).forEach((key) => {
        if (!validKeys.has(key)) delete next[key];
    });
    valueAssignments.value = next;
};

const setAssignmentUseDefault = (key, useDefault) => {
    valueAssignments.value = {
        ...valueAssignments.value,
        [key]: {
            ...(valueAssignments.value[key] || {
                token: '',
                tokenReturn: '',
                name: '',
                declaredAs: '',
                costCenter: null,
                groupValues: true,
            }),
            useDefault,
            token: useDefault ? '' : valueAssignments.value[key]?.token || '',
            tokenReturn: useDefault ? '' : valueAssignments.value[key]?.tokenReturn || '',
            name: useDefault ? '' : valueAssignments.value[key]?.name || '',
            declaredAs: useDefault ? '' : valueAssignments.value[key]?.declaredAs || '',
            costCenter: useDefault ? null : valueAssignments.value[key]?.costCenter || null,
            groupValues: useDefault
                ? true
                : (valueAssignments.value[key]?.groupValues ?? groupValues.value),
        },
    };
};

const setAssignmentToken = (key, value) => {
    valueAssignments.value = {
        ...valueAssignments.value,
        [key]: {
            ...(valueAssignments.value[key] || {
                useDefault: false,
                tokenReturn: '',
                name: '',
                declaredAs: '',
                costCenter: null,
                groupValues: true,
            }),
            useDefault: false,
            token: value,
        },
    };
};

const setAssignmentTokenReturn = (key, value) => {
    valueAssignments.value = {
        ...valueAssignments.value,
        [key]: {
            ...(valueAssignments.value[key] || {
                useDefault: false,
                token: '',
                name: '',
                declaredAs: '',
                costCenter: null,
                groupValues: true,
            }),
            useDefault: false,
            tokenReturn: value,
        },
    };
};

const setAssignmentName = (key, value) => {
    valueAssignments.value = {
        ...valueAssignments.value,
        [key]: {
            ...(valueAssignments.value[key] || {
                useDefault: false,
                token: '',
                tokenReturn: '',
                declaredAs: '',
                costCenter: null,
                groupValues: true,
            }),
            useDefault: false,
            name: value,
        },
    };
};

const setAssignmentDeclaredAs = (key, value) => {
    valueAssignments.value = {
        ...valueAssignments.value,
        [key]: {
            ...(valueAssignments.value[key] || {
                useDefault: false,
                token: '',
                tokenReturn: '',
                name: '',
                costCenter: null,
                groupValues: true,
            }),
            useDefault: false,
            declaredAs: value,
        },
    };
};

const setAssignmentCostCenter = (key, value) => {
    valueAssignments.value = {
        ...valueAssignments.value,
        [key]: {
            ...(valueAssignments.value[key] || {
                useDefault: false,
                token: '',
                tokenReturn: '',
                name: '',
                declaredAs: '',
                groupValues: true,
            }),
            useDefault: false,
            costCenter: value || null,
        },
    };
};

const setAssignmentGroupValues = (key, value) => {
    valueAssignments.value = {
        ...valueAssignments.value,
        [key]: {
            ...(valueAssignments.value[key] || {
                useDefault: false,
                token: '',
                tokenReturn: '',
                name: '',
                declaredAs: '',
                costCenter: null,
            }),
            useDefault: false,
            groupValues: !!value,
        },
    };
};

const clearCategoryRelations = () => {
    selectedAccountingConcept.value = null;
    selectedPaymentTypes.value = [];
    selectedBanks.value = [];
    selectedProducts.value = [];
    selectedPriceRates.value = [];
    selectedLineItemTypes.value = [];
    selectedPriceIntervals.value = [];
    selectedPriceVariables.value = [];
    selectedCostCenter.value = null;
    priceRates.value = [];
    lineItemTypes.value = [];
    priceIntervals.value = [];
    priceVariables.value = [];
    valueAssignments.value = {};
    groupValues.value = true;
    resetIbanPaymentScope();
    resetInvoiceScope();
    resetPaymentScope();
    clearExistingLookup();
};

const selectCategory = async (categoryToken) => {
    if (isEditing.value) return;
    if (selectedCategory.value === categoryToken) return;
    selectedCategory.value = categoryToken;
    selectAddTaxes.value = false;
    selectAddSubtotal.value = false;
    formStep.value = 'relations';
    clearCategoryRelations();
    await getAccountingConcepts();
};

const toSelectOption = (item, labelFn) => ({
    ...item,
    code: item.id,
    label: labelFn ? labelFn(item) : item.name || item.token || String(item.id),
});

const optionId = (item) => String(item?.code ?? item?.id);

const mapLineItemTypeOption = (item) => {
    const rateName = item?.billing_range?.price_rate?.name;
    return {
        ...toSelectOption(item, (i) =>
            rateName ? `${rateName} · ${i.name}` : i.name || i.token || String(i.id),
        ),
        price_interval: item.price_interval || null,
        price_variable: item.price_variable || null,
        price_rate_id: item?.billing_range?.price_rate?.id || item.price_rate_id || null,
        billing_range_id: item?.billing_range?.id || item.billing_range_id || null,
    };
};

const mapStretchOption = (item) => ({
    ...toSelectOption(item, (i) => i.token || i.name || String(i.id)),
    line_item_type_id: item?.line_item_type?.id || item?.line_item_type_id || null,
});

/** Keep saved relations visible even when the parent cascade level was not persisted. */
const hydrateRelationSelection = (options, savedItems, mapFn) => {
    const merged = [...(options || [])];
    const ids = new Set(merged.map(optionId));
    (savedItems || []).forEach((item) => {
        if (item?.id == null || ids.has(String(item.id))) return;
        ids.add(String(item.id));
        merged.push(mapFn(item));
    });
    const selectedIds = new Set((savedItems || []).map((item) => String(item.id)));
    return {
        options: merged,
        selected: merged.filter((item) => selectedIds.has(optionId(item))),
    };
};

const loadExploitations = async () => {
    const response = await $ExploitationApiService.getData();
    let list = Array.isArray(response.results) ? response.results : [];
    try {
        const exploitation_id = localStorage.getItem('exploitation');
        if (exploitation_id) {
            const filtered = list.filter((e) => String(e.id) === String(exploitation_id));
            if (filtered.length) list = filtered;
        }
    } catch (error) {
        console.error(error);
    }
    exploitations.value = list.map((e) =>
        toSelectOption(e, (item) => `${item.token}${item.name ? ` · ${item.name}` : ''}`),
    );
    if (exploitations.value.length === 1) {
        selectedExploitation.value = exploitations.value[0];
    }
};

const companyIdOf = (source) => {
    if (source == null) return null;
    if (typeof source === 'object') return source.id ?? source.code ?? null;
    return source;
};

const applyCompanyFromExploitation = ({ overwrite = false } = {}) => {
    if (!overwrite && selectedCompany.value) return;

    const companyId = companyIdOf(selectedExploitation.value?.company);
    if (companyId != null) {
        const option = companies.value.find((c) => String(c.code) === String(companyId));
        if (option) {
            selectedCompany.value = option;
            return;
        }
    }

    if (!selectedCompany.value && companies.value.length === 1) {
        selectedCompany.value = companies.value[0];
    }
};

const loadCompanies = async () => {
    try {
        const response = await $ExploitationApiService.getCompanies();
        const list = Array.isArray(response.results) ? response.results : [];
        companies.value = list.map((c) =>
            toSelectOption(c, (item) => {
                if (item.alias && item.name && item.alias !== item.name) {
                    return `${item.alias} · ${item.name}`;
                }
                return item.alias || item.name || String(item.id);
            }),
        );
        applyCompanyFromExploitation();
    } catch (error) {
        console.error(error);
        companies.value = [];
    }
};

const mapCostCenterOption = (item) =>
    toSelectOption(item, (i) => `${i.token || '—'} · ${i.name || ''}`.trim());

const costCenterIdOf = (option) => {
    if (option == null) return null;
    if (typeof option === 'object') return option.code ?? option.id ?? null;
    return option;
};

const hydrateSelectedCostCenter = (response) => {
    if (!showsCostCenter.value) {
        selectedCostCenter.value = null;
        return;
    }

    const savedCostCenter =
        response?.accounting_cost_center ?? response?.cost_center ?? null;
    const savedCostCenterId =
        savedCostCenter != null && typeof savedCostCenter === 'object'
            ? savedCostCenter.id
            : savedCostCenter;

    if (savedCostCenterId != null) {
        selectedCostCenter.value =
            costCenters.value.find(
                (c) => String(c.code ?? c.id) === String(savedCostCenterId),
            ) ||
            (typeof savedCostCenter === 'object'
                ? mapCostCenterOption(savedCostCenter)
                : null);
        return;
    }

    selectedCostCenter.value = null;
};

const loadCostCenters = async () => {
    loadingCostCenters.value = true;
    try {
        const response = await $AccountingCostCenterApiService.getAll();
        const list = Array.isArray(response) ? response : (response?.results ?? []);
        costCenters.value = list.map(mapCostCenterOption);
    } catch (error) {
        console.error(error);
        costCenters.value = [];
    } finally {
        loadingCostCenters.value = false;
    }
};

const getAccountingTypes = async () => {
    try {
        const response = await $AccountingTypeApiService.getAll();
        accountingTypes.value = response.results || [];
    } catch (error) {
        console.error(error);
    }
};

const getAccountingConcepts = async () => {
    if (!selectedCategory.value) {
        accountingConcepts.value = [];
        return;
    }

    loadingConcepts.value = true;
    try {
        const response = await $AccountingConceptApiService.getAll(
            '', 1, null, false,
            selectedCategory.value, selectedExploitation.value?.code || null,
            selectAddTaxes.value || selectAddSubtotal.value ? selectAddTaxes.value : null,
            selectAddTaxes.value || selectAddSubtotal.value ? selectAddSubtotal.value : null,
        );
        accountingConcepts.value = response.results;

        if (selectedAccountingConcept.value) {
            const stillValid = accountingConcepts.value.some(
                (c) => c.id === selectedAccountingConcept.value.code,
            );
            if (!stillValid && !isEditing.value) selectedAccountingConcept.value = null;
        }
    } catch (error) {
        console.error(error);
        accountingConcepts.value = [];
    } finally {
        loadingConcepts.value = false;
    }
};

const getPaymentTypes = async () => {
    try {
        const response = await $ConfiglistApiService.getAll('contract/contract-payment-type');
        paymentTypes.value = (response.results || [])
            .filter((item) => item.token !== 'BALANCE')
            .map((item) => toSelectOption(item, (i) => `${i.token || ''} · ${i.name}`));
    } catch (error) {
        console.error(error);
        paymentTypes.value = [];
    }
};

const bankOptionLabel = (item) => {
    const token = item?.token || '';
    const name = item?.name || '';
    if (name && token) return `${name} - ${token}`;
    return name || token || String(item?.id ?? '');
};

const bankListFromResponse = (response) => {
    if (Array.isArray(response)) return response;
    if (Array.isArray(response?.results)) return response.results;
    return [];
};

const loadBanks = async () => {
    loadingBanks.value = true;
    try {
        const collected = [];
        let page = 1;
        let hasNext = true;
        while (hasNext && page <= 50) {
            const response = await $AddressApiService.getBanks(page);
            collected.push(...bankListFromResponse(response));
            hasNext = !Array.isArray(response) && !!response?.next;
            page += 1;
        }
        banks.value = collected
            .filter((bank) => bank && (bank.id != null || bank.token || bank.name))
            .map((bank) => toSelectOption(bank, bankOptionLabel));
    } catch (error) {
        console.error(error);
        banks.value = [];
    } finally {
        loadingBanks.value = false;
    }
};

const getProducts = async () => {
    try {
        const exploitationId = selectedExploitation.value?.code ?? null;
        const response = await $ProductApiService.getAll(
            '', [], 1, null, false, null, [], true, exploitationId,
        );
        const list = Array.isArray(response) ? response : response?.results ?? [];
        products.value = list.map((item) =>
            toSelectOption(
                item,
                (i) =>
                    `${i.name}${i.exploitation?.name ? ` (${i.exploitation.name})` : ''}`,
            ),
        );
    } catch (error) {
        console.error(error);
        products.value = [];
    }
};

const getPriceRatesForProducts = async () => {
    priceRates.value = [];
    selectedPriceRates.value = [];
    selectedLineItemTypes.value = [];
    selectedPriceIntervals.value = [];
    selectedPriceVariables.value = [];
    lineItemTypes.value = [];
    priceIntervals.value = [];
    priceVariables.value = [];

    if (!selectedProducts.value.length) return;

    loadingRelations.value = true;
    try {
        const productIds = selectedProducts.value.map((p) => p.code).join(',');
        const result = await $PriceRateApiService.getAll(
            '',
            [],
            1,
            null,
            false,
            productIds,
            null,
            false,
            selectedExploitation.value?.code ?? null,
        );
        priceRates.value = (result.results || []).map((item) => ({
            ...toSelectOption(item, (i) => `${i.product?.name || ''} · ${i.name}`),
            br_id: item?.billing_range_active?.id || null,
            product_id: item?.product?.id || null,
        }));
    } catch (error) {
        console.error(error);
    } finally {
        loadingRelations.value = false;
    }
};

const getLineItemTypesForRates = async (sourceRates = null) => {
    lineItemTypes.value = [];
    selectedLineItemTypes.value = [];
    selectedPriceIntervals.value = [];
    selectedPriceVariables.value = [];
    priceIntervals.value = [];
    priceVariables.value = [];

    const rates = sourceRates || selectedPriceRates.value;
    if (!rates.length) return;

    loadingRelations.value = true;
    try {
        const brIds = rates
            .map((rate) => rate.br_id)
            .filter(Boolean)
            .join(',');
        if (!brIds) return;

        const result = await $LineItemTypeApiService.getAll(
            '',
            [],
            1,
            null,
            false,
            brIds,
        );
        lineItemTypes.value = (result.results || []).map(mapLineItemTypeOption);
    } catch (error) {
        console.error(error);
    } finally {
        loadingRelations.value = false;
    }
};

const getIntervalsAndVariables = async () => {
    priceIntervals.value = [];
    priceVariables.value = [];
    selectedPriceIntervals.value = [];
    selectedPriceVariables.value = [];

    if (!selectedLineItemTypes.value.length) return;

    loadingRelations.value = true;
    try {
        const lineItemTypeIds = selectedLineItemTypes.value
            .map((item) => item.code)
            .join(',');

        const [intervalsResponse, variablesResponse] = await Promise.all([
            $PriceIntervalStretchApiService.getAll('', [], 1, null, false, null, lineItemTypeIds),
            $PriceVariableIntervalStretchApiService.getAll('', [], 1, null, false, null, lineItemTypeIds),
        ]);

        priceIntervals.value = (intervalsResponse.results || []).map(mapStretchOption);
        priceVariables.value = (variablesResponse.results || []).map(mapStretchOption);
    } catch (error) {
        console.error(error);
    } finally {
        loadingRelations.value = false;
    }
};

const onProductsChange = async (value) => {
    if (isEditing.value) return;
    selectedProducts.value = value || [];
    await getPriceRatesForProducts();
    ensureAssignments();
};

const onPriceRatesChange = async (value) => {
    if (!canEditProductChildren.value) return;
    selectedPriceRates.value = value || [];
    await getLineItemTypesForRates();
    ensureAssignments();
};

const onLineItemTypesChange = async (value) => {
    if (!canEditProductChildren.value) return;
    selectedLineItemTypes.value = value || [];
    await getIntervalsAndVariables();
    ensureAssignments();
};

const onPaymentTypesChange = (value) => {
    selectedPaymentTypes.value = value || [];
    const onlyBank =
        selectedPaymentTypes.value.length > 0 &&
        selectedPaymentTypes.value.every((item) => item?.token === BANK_PAYMENT_TOKEN);
    if (!onlyBank) selectedPaymentOrigin.value = null;
    if (!selectedPaymentTypes.value.some((item) => item?.token === BANK_PAYMENT_TOKEN)) {
        separateByPaymentOrigin.value = false;
    }
    ensureAssignments();
};

const onBanksChange = (value) => {
    selectedBanks.value = value || [];
};

const selectAllBanks = () => {
    onBanksChange([...banks.value]);
};

const onPriceIntervalsChange = (value) => {
    if (!canEditProductChildren.value) return;
    selectedPriceIntervals.value = value || [];
    ensureAssignments();
};

const onPriceVariablesChange = (value) => {
    if (!canEditProductChildren.value) return;
    selectedPriceVariables.value = value || [];
    ensureAssignments();
};

const onOriginsChange = (value) => {
    selectedOrigins.value = value || [];
    ensureAssignments();
};

const selectAllOrigins = () => {
    onOriginsChange([...origins.value]);
};

const onContractTypesChange = (value) => {
    selectedContractTypes.value = value || [];
    ensureAssignments();
};

const selectAllContractTypes = () => {
    onContractTypesChange([...contractTypes.value]);
};

const loadContractTypes = async () => {
    loadingContractTypes.value = true;
    try {
        const list = [];
        let page = 1;
        let hasNext = true;
        while (hasNext && page <= 50) {
            const response = await $ConfiglistApiService.getAll(
                'contract/contract-use-type',
                page,
            );
            list.push(...(response?.results || []));
            hasNext = !!response?.next;
            page += 1;
        }
        contractTypes.value = list.map((item) => toSelectOption(item));
    } catch (error) {
        console.error(error);
        contractTypes.value = [];
    } finally {
        loadingContractTypes.value = false;
    }
};

const loadOrigins = async () => {
    loadingOrigins.value = true;
    try {
        const response = await $ProductApiService.getOrigins();
        const list = Array.isArray(response?.results)
            ? response.results
            : Array.isArray(response)
                ? response
                : [];
        origins.value = list.map((item) => toSelectOption(item));
    } catch (error) {
        console.error(error);
        origins.value = [];
    } finally {
        loadingOrigins.value = false;
    }
};

const selectAllPaymentTypes = () => {
    onPaymentTypesChange([...paymentTypes.value]);
};

const selectAllProducts = async () => {
    await onProductsChange([...products.value]);
};

const selectAllPriceRates = async () => {
    await onPriceRatesChange([...priceRates.value]);
};

const selectAllLineItemTypes = async () => {
    await onLineItemTypesChange([...lineItemTypes.value]);
};

const selectAllPriceIntervals = () => {
    onPriceIntervalsChange([...priceIntervals.value]);
};

const selectAllPriceVariables = () => {
    onPriceVariablesChange([...priceVariables.value]);
};

const mapRelatedOptions = (items) =>
    (items || []).map((item) => toSelectOption(item));

const getAccountingPricingData = async () => {
    if (!props.id) return;
    loadingData.value = true;
    loadedHasProductChildren.value = false;
    try {
        const response = await $AccountingPricingApiService.getDetail(props.id);
        token.value = response.token || '';
        tokenReturn.value = response.token_return || '';
        name.value = response.name || '';
        declaredAs.value = response.declared_as || '';
        is_default.value = !!response.is_default;
        is_active.value = response.is_active !== false;
        groupValues.value = response.grouped_lines !== false;

        if (response.exploitation?.id) {
            selectedExploitation.value =
                exploitations.value.find(
                    (e) => String(e.code) === String(response.exploitation.id),
                ) ||
                toSelectOption(
                    response.exploitation,
                    (i) => `${i.token}${i.name ? ` · ${i.name}` : ''}`,
                );
        }

        if (response.company?.id) {
            selectedCompany.value =
                companies.value.find(
                    (c) => String(c.code) === String(response.company.id),
                ) ||
                toSelectOption(
                    response.company,
                    (i) => {
                        if (i.alias && i.name && i.alias !== i.name) {
                            return `${i.alias} · ${i.name}`;
                        }
                        return i.alias || i.name || String(i.id);
                    },
                );
        }

        selectedCategory.value = response.accounting_concept?.category || null;
        if (response.accounting_concept) {
            selectAddTaxes.value = !!response.accounting_concept.type?.add_taxes;
            selectAddSubtotal.value = !!response.accounting_concept.type?.add_subtotals;
            await getAccountingConcepts();

            const concept =
                accountingConcepts.value.find(
                    (c) => c.id === response.accounting_concept.id,
                ) || response.accounting_concept;
            selectedAccountingConcept.value = {
                ...concept,
                code: concept.id,
                label: `${concept.token || '—'} · ${concept.name}`,
            };
        }

        if (selectedCategory.value === 'invoice') {
            applyInvoiceScope(response);
            if (showsInvoiceOrigins.value) {
                const savedOrigins = response.origins || [];
                const hydratedOrigins = hydrateRelationSelection(
                    origins.value,
                    savedOrigins,
                    (item) => toSelectOption(item),
                );
                origins.value = hydratedOrigins.options;
                selectedOrigins.value = hydratedOrigins.selected;

                const savedContractTypes = response.contract_types || [];
                const hydratedContractTypes = hydrateRelationSelection(
                    contractTypes.value,
                    savedContractTypes,
                    (item) => toSelectOption(item),
                );
                contractTypes.value = hydratedContractTypes.options;
                selectedContractTypes.value = hydratedContractTypes.selected;
            }
        }

        if (selectedCategory.value === 'payment') {
            selectedPaymentTypes.value = mapRelatedOptions(response.payment_types);
            const savedBanks = (response.banks || []).map((item) =>
                item && typeof item === 'object' ? item : { id: item },
            );
            const hydratedBanks = hydrateRelationSelection(
                banks.value,
                savedBanks,
                (item) => toSelectOption(item, bankOptionLabel),
            );
            banks.value = hydratedBanks.options;
            selectedBanks.value = hydratedBanks.selected;
            selectedPaymentCategory.value = response.invoice_category || "normal";
            applyIbanPaymentScope(response);
            applyPaymentScope(response);
            hydrateSelectedCostCenter(response);
        }

        if (selectedCategory.value === 'lineitem') {
            hydrateSelectedCostCenter(response);

            selectedProducts.value = mapRelatedOptions(response.products);
            if (selectedProducts.value.length) {
                await getPriceRatesForProducts();
                const rateIds = new Set((response.price_rates || []).map((r) => r.id));
                selectedPriceRates.value = priceRates.value.filter((r) =>
                    rateIds.has(r.code),
                );

                const savedLineItems = response.line_item_types || [];
                const savedIntervals = response.price_intervals || [];
                const savedVariables = response.price_variables || [];

                if (selectedPriceRates.value.length || savedLineItems.length) {
                    const ratesForLineItems = selectedPriceRates.value.length
                        ? selectedPriceRates.value
                        : priceRates.value;
                    if (ratesForLineItems.length) {
                        await getLineItemTypesForRates(ratesForLineItems);
                    }
                    const hydratedLineItems = hydrateRelationSelection(
                        lineItemTypes.value,
                        savedLineItems,
                        mapLineItemTypeOption,
                    );
                    lineItemTypes.value = hydratedLineItems.options;
                    selectedLineItemTypes.value = hydratedLineItems.selected;
                }

                if (selectedLineItemTypes.value.length) {
                    await getIntervalsAndVariables();
                }

                const hydratedIntervals = hydrateRelationSelection(
                    priceIntervals.value,
                    savedIntervals,
                    mapStretchOption,
                );
                priceIntervals.value = hydratedIntervals.options;
                selectedPriceIntervals.value = hydratedIntervals.selected;

                const hydratedVariables = hydrateRelationSelection(
                    priceVariables.value,
                    savedVariables,
                    mapStretchOption,
                );
                priceVariables.value = hydratedVariables.options;
                selectedPriceVariables.value = hydratedVariables.selected;
            }
            loadedHasProductChildren.value =
                selectedProducts.value.length > 0 &&
                (selectedPriceRates.value.length > 0 ||
                    selectedLineItemTypes.value.length > 0 ||
                    selectedPriceIntervals.value.length > 0 ||
                    selectedPriceVariables.value.length > 0);
        }

        ensureAssignments();
        // Edit mode opens on values step (token/name); relations stay available via back.
        formStep.value = 'values';
        await loadExistingAssignments();
        additionalLines.value = (response.aditional_lines || []).filter(
            (line) => line.is_active !== false,
        );
        await loadAdditionalLines();
    } catch (error) {
        console.error(error);
        toast.error(t('common.error'));
    } finally {
        loadingData.value = false;
    }
};

const getData = async () => {
    loading.value = true;
    try {
        await loadExploitations();
        await loadCompanies();
        await getAccountingTypes();
        await getPaymentTypes();
        await loadBanks();
        await loadCostCenters();
        await getProducts();
        await loadOrigins();
        await loadContractTypes();
        await getAccountingPricingData();
    } catch (error) {
        console.error(error);
    } finally {
        loading.value = false;
    }
};

const idsOf = (items) => (items || []).map((item) => item.code ?? item.id);

const emptyRelationPayload = () => ({
    payment_types: [],
    products: [],
    price_rates: [],
    line_item_types: [],
    price_intervals: [],
    price_variables: [],
    banks: [],
    origins: [],
    contract_types: [],
});

const optionalText = (value) => {
    const text = (value || '').trim();
    return text || null;
};

const buildBasePayload = () => ({
    id: props.id || null,
    token: (token.value || '').trim(),
    token_return: optionalText(tokenReturn.value),
    name: (name.value || '').trim(),
    declared_as: optionalText(declaredAs.value),
    is_default: is_default.value,
    is_active: is_active.value,
    group_values: groupValues.value,
    separate_by_type: selectedCategory.value === 'payment' && groupValues.value ? !!separateByType.value : false,
    separate_by_origin: selectedCategory.value === 'invoice' && groupValues.value ? !!separateByOrigin.value : false,
    ...bankPaymentOriginPayload(),
    exploitation: exploitationIdForSave(),
    company: selectedCompany.value?.code ?? null,
    banks: selectedCategory.value === 'payment' ? idsOf(selectedBanks.value) : [],
    accounting_concept: selectedAccountingConcept.value?.code ?? null,
    category: selectedCategory.value,
    cost_center: showsCostCenter.value
        ? costCenterIdOf(selectedCostCenter.value)
        : null,
    ...invoiceScopePayload(),
    ...paymentScopePayload(),
});

/** Full selection payload (edit / invoice / no per-value rows). */
const buildRelationPayload = () => {
    const payload = emptyRelationPayload();

    if (selectedCategory.value === 'invoice') {
        if (showsInvoiceOrigins.value) {
            payload.origins = idsOf(selectedOrigins.value);
        }
        if (showsInvoiceContractTypes.value) {
            payload.contract_types = idsOf(selectedContractTypes.value);
        }
        return payload;
    }

    if (selectedCategory.value === 'payment') {
        payload.payment_types = idsOf(selectedPaymentTypes.value);
        payload.banks = idsOf(selectedBanks.value);
        return payload;
    }

    payload.products = idsOf(selectedProducts.value);
    payload.price_rates = idsOf(selectedPriceRates.value);
    payload.line_item_types = idsOf(selectedLineItemTypes.value);
    payload.price_intervals = idsOf(selectedPriceIntervals.value);
    payload.price_variables = idsOf(selectedPriceVariables.value);
    return payload;
};

/**
 * One entry scoped to a single cascade value.
 * Deeper levels keep products (and payment types) but leave sibling/parent
 * relation arrays empty so each level is saved as its own accounting pricing.
 */
const buildScopedRelationPayload = (kind, item) => {
    const payload = emptyRelationPayload();
    const id = item.code ?? item.id;

    if (kind === 'payment_type') {
        payload.payment_types = [id];
        payload.banks = idsOf(selectedBanks.value);
        return payload;
    }

    if (kind === 'origin') {
        payload.origins = [id];
        payload.contract_types = idsOf(selectedContractTypes.value);
        return payload;
    }

    if (kind === 'contract_type') {
        payload.contract_types = [id];
        payload.origins = idsOf(selectedOrigins.value);
        return payload;
    }

    if (kind === 'product') {
        payload.products = [id];
        return payload;
    }

    const productIds = item.product_id
        ? [item.product_id]
        : idsOf(selectedProducts.value);

    if (kind === 'price_rate') {
        payload.products = productIds;
        payload.price_rates = [id];
        return payload;
    }

    if (kind === 'line_item_type') {
        const rateId = item.price_rate_id;
        const parentRate = rateId
            ? selectedPriceRates.value.find(
                (rate) => String(rate.code ?? rate.id) === String(rateId),
            )
            : null;
        payload.products = parentRate?.product_id
            ? [parentRate.product_id]
            : productIds;
        payload.line_item_types = [id];
        return payload;
    }

    if (kind === 'price_interval' || kind === 'price_variable') {
        const litId = item.line_item_type_id;
        const parentLit = litId
            ? selectedLineItemTypes.value.find(
                (lit) => String(lit.code ?? lit.id) === String(litId),
            )
            : null;
        const rateId = parentLit?.price_rate_id || null;
        const parentRate = rateId
            ? selectedPriceRates.value.find(
                (rate) => String(rate.code ?? rate.id) === String(rateId),
            )
            : null;

        payload.products = parentRate?.product_id
            ? [parentRate.product_id]
            : productIds;

        if (kind === 'price_interval') payload.price_intervals = [id];
        else payload.price_variables = [id];
        return payload;
    }

    return payload;
};

const resolveRowToken = (row) =>
    row.useDefault ? token.value.trim() : (row.customToken || '').trim();

const resolveRowTokenReturn = (row) =>
    optionalText(row.useDefault ? tokenReturn.value : row.customTokenReturn);

const resolveRowName = (row) =>
    row.useDefault ? name.value.trim() : (row.customName || '').trim();

const resolveRowDeclaredAs = (row) =>
    optionalText(row.useDefault ? declaredAs.value : row.customDeclaredAs);

const resolveRowCostCenter = (row) => {
    if (!showsCostCenter.value) return null;
    return row.useDefault
        ? selectedCostCenter.value
        : (row.customCostCenter || null);
};

const resolveRowGroupValues = (row) =>
    row.useDefault ? groupValues.value : !!row.customGroupValues;

const RELATION_FIELDS = [
    'payment_types',
    'products',
    'price_rates',
    'line_item_types',
    'price_intervals',
    'price_variables',
    'banks',
    'origins',
    'contract_types',
];

const mergeIds = (a, b) => [...new Set([...(a || []), ...(b || [])])];

/**
 * Build save entries from assignment rows.
 * Rows with group_values true sharing kind + token + name + cost center merge
 * into one payload entry; rows with group_values false are each saved alone.
 */
const buildSaveEntries = () => {
    if (!hasAssignmentRows.value) {
        if (!isEditing.value && existingSelection.value) {
            return [];
        }
        return [
            {
                token: token.value.trim(),
                token_return: optionalText(tokenReturn.value),
                name: name.value.trim(),
                declared_as: optionalText(declaredAs.value),
                is_default: is_default.value,
                group_values: groupValues.value,
                cost_center: showsCostCenter.value
                    ? costCenterIdOf(selectedCostCenter.value)
                    : null,
                ...buildRelationPayload(),
            },
        ];
    }

    const editableRows = assignmentRows.value.filter((row) => !row.alreadyExists);
    const entries = [];
    const groups = new Map();

    editableRows.forEach((row) => {
        const resolvedToken = resolveRowToken(row);
        const resolvedTokenReturn = resolveRowTokenReturn(row);
        const resolvedName = resolveRowName(row);
        const resolvedDeclaredAs = resolveRowDeclaredAs(row);
        const resolvedCostCenterId = costCenterIdOf(resolveRowCostCenter(row));
        const resolvedGroupValues = resolveRowGroupValues(row);
        const scoped = buildScopedRelationPayload(row.kind, row.item);

        if (!resolvedGroupValues) {
            entries.push({
                token: resolvedToken,
                token_return: resolvedTokenReturn,
                name: resolvedName,
                declared_as: resolvedDeclaredAs,
                is_default: row.useDefault ? is_default.value : false,
                group_values: false,
                cost_center: resolvedCostCenterId,
                ...scoped,
            });
            return;
        }

        const groupKey = `${row.kind}||${resolvedToken}||${resolvedTokenReturn || ''}||${resolvedName}||${resolvedDeclaredAs || ''}||${resolvedCostCenterId ?? ''}`;

        if (!groups.has(groupKey)) {
            groups.set(groupKey, {
                token: resolvedToken,
                token_return: resolvedTokenReturn,
                name: resolvedName,
                declared_as: resolvedDeclaredAs,
                is_default: row.useDefault ? is_default.value : false,
                group_values: true,
                cost_center: resolvedCostCenterId,
                ...emptyRelationPayload(),
            });
        }

        const entry = groups.get(groupKey);
        RELATION_FIELDS.forEach((field) => {
            entry[field] = mergeIds(entry[field], scoped[field]);
        });
    });

    entries.push(...groups.values());
    if (entries.length) return entries;

    if (isEditing.value) {
        return [
            {
                token: token.value.trim(),
                token_return: optionalText(tokenReturn.value),
                name: name.value.trim(),
                declared_as: optionalText(declaredAs.value),
                is_default: is_default.value,
                group_values: groupValues.value,
                cost_center: showsCostCenter.value
                    ? costCenterIdOf(selectedCostCenter.value)
                    : null,
                ...buildRelationPayload(),
            },
        ];
    }

    return [];
};

const isValid = () => {
    if (showExploitation.value && !selectedExploitation.value) return false;
    if (!selectedCompany.value) return false;
    if (!selectedCategory.value) return false;
    if (!selectedAccountingConcept.value) return false;

    if (selectedCategory.value === 'payment') {
        if (!selectedPaymentTypes.value.length) return false;
        if (!selectedPaymentCategory.value) return false;
    }

    if (selectedCategory.value === 'lineitem') {
        if (!selectedProducts.value.length) return false;
    }

    if (selectedCategory.value === 'invoice') {
        if (!selectedInvoiceCategory.value) return false;
    }

    if (!hasSavableAssignments.value) return true;

    if (!token.value?.trim()) return false;
    if (!name.value?.trim()) return false;

    if (hasAssignmentRows.value) {
        for (const row of assignmentRows.value) {
            if (row.alreadyExists || row.useDefault) continue;
            if (!(row.customToken || '').trim()) return false;
            if (!(row.customName || '').trim()) return false;
        }
    }

    return true;
};

const save = async () => {
    if (formStep.value !== 'values') {
        await goToValuesStep();
        return;
    }

    attemptedSave.value = true;
    if (!isValid()) {
        toast.error(t('common.required_fields'));
        return;
    }

    if (!hasSavableAssignments.value) {
        toast.error(t('pricing_block.accounting_pricing_nothing_to_save'));
        return;
    }

    saving.value = true;
    try {
        const entries = buildSaveEntries();
        if (!entries.length) {
            toast.error(t('pricing_block.accounting_pricing_nothing_to_save'));
            return;
        }

        const base = buildBasePayload();
        const defaultToken = token.value.trim();
        const defaultTokenReturn = optionalText(tokenReturn.value);
        const defaultName = name.value.trim();
        const defaultDeclaredAs = optionalText(declaredAs.value);
        let updateIndex = isEditing.value
            ? entries.findIndex(
                (entry) =>
                    entry.token === defaultToken &&
                    (entry.token_return || null) === defaultTokenReturn &&
                    entry.name === defaultName &&
                    (entry.declared_as || null) === defaultDeclaredAs,
            )
            : -1;
        if (isEditing.value && updateIndex < 0) updateIndex = 0;

        const payloads = entries.map((entry, index) => {
            const payload = {
                ...base,
                token: entry.token,
                token_return: entry.token_return ?? base.token_return,
                name: entry.name || base.name,
                declared_as: entry.declared_as ?? base.declared_as,
                is_default: entry.is_default,
                grouped_lines: entry.grouped_lines,
                separate_by_type: selectedCategory.value === 'payment' && groupValues.value ? !!separateByType.value : false,
                separate_by_origin: selectedCategory.value === 'invoice' && !!entry.group_values ? !!separateByOrigin.value : false,
                ...bankPaymentOriginPayload(entry.payment_types, entry.group_values),
                cost_center: showsCostCenter.value
                    ? (entry.cost_center ?? null)
                    : null,
                payment_types: entry.payment_types,
                products: entry.products,
                price_rates: entry.price_rates,
                line_item_types: entry.line_item_types,
                price_intervals: entry.price_intervals,
                price_variables: entry.price_variables,
                origins: entry.origins || [],
                contract_types: entry.contract_types || [],
                banks: selectedCategory.value === 'payment'
                    ? idsOf(selectedBanks.value)
                    : (entry.banks || []),
                ...ibanPaymentScopePayload(entry.payment_types),
                ...invoiceScopePayload(),
                ...paymentScopePayload(),
            };

            if (isEditing.value && index === updateIndex) {
                payload.id = props.id;
            } else {
                delete payload.id;
            }

            return payload;
        });
        // console.log("payloads");
        // console.log(payloads);
        // return;

        await $AccountingPricingApiService.bulkSave({ items: payloads });

        emit('changed');
        emit('close');
    } catch (error) {
        console.error(error);
        toast.error(t('common.error'));
    } finally {
        saving.value = false;
    }
};

watch(
    [
        selectedPaymentTypes,
        selectedProducts,
        selectedPriceRates,
        selectedLineItemTypes,
        selectedPriceIntervals,
        selectedPriceVariables,
        selectedOrigins,
        selectedContractTypes,
    ],
    () => ensureAssignments(),
    { deep: true },
);

watch([selectAddTaxes, selectAddSubtotal], async () => {
    if (!selectedCategory.value || isEditing.value) return;
    await getAccountingConcepts();
});

watch(selectedExploitation, async () => {
    if (formStep.value === 'values') {
        applyCompanyFromExploitation({ overwrite: true });
        return;
    }
    applyCompanyFromExploitation();
    if (isEditing.value || loadingData.value) return;
    if (selectedCategory.value) {
        await getAccountingConcepts();
    }
    if (selectedCategory.value === 'lineitem') {
        await getProducts();
        selectedProducts.value = [];
        await getPriceRatesForProducts();
    }
});

watch(
    [
        selectedCompany,
        selectedExploitation,
        selectedBanks,
        selectedForeignIban,
        selectedNationalIban,
        selectedOutgoingPayments,
        selectedIncomingPayments,
        selectedInvoiceCategory,
        selectedPaymentCategory,
        selectedOrigins,
        selectedContractTypes,
        undeclarePrevious,
    ],
    async () => {
        if (formStep.value !== 'values' || loadingData.value) return;
        await loadExistingAssignments();
    },
    { deep: true },
);

onMounted(async () => {
    objectPermissions.value = await checkPermission($PriceRateApiService);
    if (!objectPermissions.value.can_change) {
        toast.error(t('common.no_permissions'));
        emit('close');
        return;
    }
    await getData();
});
</script>

<template>
    <div v-if="objectPermissions?.can_change" class="region__content pr-4 pb-8 text-base"
        style="--accent: #0369a1; --accent-soft: #7dd3fc;">
        <!-- Page header -->
        <header class="mb-4 flex items-start justify-between gap-3">
            <div class="flex min-w-0 items-center gap-2.5">
                <span class="shrink-0 font-mono text-[11px] font-bold tracking-[0.14em]"
                    style="color: var(--accent-soft)">
                    03
                </span>
                <div class="relative flex size-9 shrink-0 items-center justify-center">
                    <span class="absolute left-0 top-0 h-2 w-2 border-l border-t border-sky-200" />
                    <span class="absolute right-0 top-0 h-2 w-2 border-r border-t border-sky-200" />
                    <span class="absolute bottom-0 left-0 h-2 w-2 border-b border-l border-sky-200" />
                    <span class="absolute bottom-0 right-0 h-2 w-2 border-b border-r border-sky-200" />
                    <Icon :name="isEditing ? 'fa6-solid:pencil' : 'fa6-solid:plus'" class="size-3.5"
                        style="color: var(--accent)" />
                </div>
                <div class="min-w-0">
                    <H1Region class="!mb-0 truncate !text-sm !font-bold !text-sky-950">
                        {{
                            props.id
                                ? t('pricing_block.edit_accounting_pricing')
                                : t('pricing_block.new_accounting_pricing')
                        }}
                    </H1Region>
                    <p class="font-mono text-[10px] tracking-widest text-slate-500">
                        {{ formStep === 'relations' ? '01' : '02' }} / 02
                    </p>
                </div>
            </div>

            <div class="flex shrink-0 flex-wrap items-center gap-1.5">
                <button type="button"
                    class="rounded-md border px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.14em] transition-colors"
                    :class="is_default
                        ? 'border-[var(--accent)] bg-[var(--accent)] text-white'
                        : 'border-[var(--accent-soft)] bg-white text-[var(--accent)] hover:bg-[var(--accent-soft)]/40'"
                    :aria-pressed="is_default" @click="is_default = !is_default">
                    {{ t('default') }}
                </button>
                <button type="button"
                    class="rounded-md border px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.14em] transition-colors"
                    :class="is_active
                        ? 'border-[var(--accent)] bg-[var(--accent)] text-white'
                        : 'border-slate-200 bg-white text-slate-500 hover:bg-slate-50'" :aria-pressed="is_active"
                    @click="is_active = !is_active">
                    {{ t('common.active') }}
                </button>
            </div>
        </header>

        <!-- Step tabs -->
        <div class="flex items-end gap-1.5 overflow-x-auto scrollbar-hide">
            <button type="button"
                class="relative shrink-0 rounded-t-md px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
                :class="formStep === 'relations'
                    ? 'border border-[var(--accent)] bg-[var(--accent)] text-white'
                    : 'border border-b-0 border-[var(--accent-soft)] bg-[var(--accent-soft)]/40 text-[var(--accent)] hover:bg-[var(--accent-soft)]'"
                :disabled="formStep === 'relations'" @click="goToRelationsStep">
                <span class="mr-1.5 font-mono text-[10px] opacity-70">01</span>
                {{ t('contract_block.category') }}
            </button>
            <button type="button"
                class="relative shrink-0 rounded-t-md px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
                :class="formStep === 'values'
                    ? 'border border-[var(--accent)] bg-[var(--accent)] text-white'
                    : canGoToValuesStep
                        ? 'border border-b-0 border-[var(--accent-soft)] bg-[var(--accent-soft)]/40 text-[var(--accent)] hover:bg-[var(--accent-soft)]'
                        : 'cursor-not-allowed border border-b-0 border-slate-200 bg-slate-50 text-slate-400'"
                :disabled="formStep === 'values' || !canGoToValuesStep" @click="goToValuesStep">
                <span class="mr-1.5 font-mono text-[10px] opacity-70">02</span>
                {{ t('pricing_block.accounting_pricing_assign_values_title') }}
            </button>
        </div>

        <div v-if="loading || loadingData" class="relative rounded-b-lg rounded-tr-lg border bg-white p-8"
            style="border-color: var(--accent-soft)">
            <span class="absolute right-0 top-0 h-11 w-1.5 rounded-bl-md rounded-tr-md"
                style="background-color: var(--accent)" />
            <div class="flex justify-center items-center">
                <AtomsAppLoading />
            </div>
        </div>

        <form v-else class="relative rounded-b-lg rounded-tr-lg border bg-white"
            style="border-color: var(--accent-soft)" @submit.prevent="save">
            <span class="absolute right-0 top-0 z-[1] h-11 w-1.5 rounded-bl-md rounded-tr-md"
                style="background-color: var(--accent)" />

            <Transition name="stage" mode="out-in">
                <!-- Stage 1: category + relations -->
                <div v-if="formStep === 'relations'" key="relations" class="flex flex-col">
                    <!-- Section: Category & concept -->
                    <section class="border-b px-4 py-4"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent)">
                        <div class="mb-3 flex items-center gap-2">
                            <span class="font-mono text-[10px] font-bold tracking-[0.14em]"
                                style="color: var(--accent-soft)">01</span>
                            <h3 class="text-[13px] font-bold text-sky-950">
                                {{ t('contract_block.category') }}
                            </h3>
                        </div>

                        <div class="mb-4 flex flex-wrap gap-1.5"
                            :class="{ 'rounded-md border border-red-300 p-2': attemptedSave && !selectedCategory }">
                            <button v-for="category in categories" :key="category.token" type="button"
                                class="rounded-md border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
                                :class="selectedCategory === category.token
                                    ? 'border-[var(--accent)] bg-[var(--accent)] text-white'
                                    : isEditing
                                        ? 'cursor-not-allowed border-[var(--accent-soft)] bg-[var(--accent-soft)]/20 text-[var(--accent)] opacity-60'
                                        : 'border-[var(--accent-soft)] bg-white text-[var(--accent)] hover:bg-[var(--accent-soft)]/40'
                                    " :disabled="isEditing" @click="selectCategory(category.token)">
                                {{ category.name }}
                            </button>
                        </div>

                        <template v-if="selectedCategory">
                            <div class="mb-3 flex flex-wrap items-center gap-3">
                                <label class="inline-flex items-center gap-2 text-[12px] text-sky-950"
                                    :class="isEditing ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'">
                                    <input v-model="selectAddTaxes" type="checkbox" class="checkbox"
                                        :disabled="isEditing" />
                                    <span>{{ t('taxes') }}</span>
                                </label>
                                <label class="inline-flex items-center gap-2 text-[12px] text-sky-950"
                                    :class="isEditing ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'">
                                    <input v-model="selectAddSubtotal" type="checkbox" class="checkbox"
                                        :disabled="isEditing" />
                                    <span>{{ t('subtotal') }}</span>
                                </label>
                            </div>
                            <p class="mb-3 text-[11px] leading-snug text-slate-500">
                                {{ t('pricing_block.accounting_concept_type_filters_hint') }}
                            </p>

                            <label
                                class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                {{ t('pricing_block.accounting_concept') }} *
                                <span v-if="loadingConcepts"
                                    class="ml-1 normal-case tracking-normal text-slate-400">…</span>
                            </label>
                            <v-select v-model="selectedAccountingConcept" :options="conceptOptions"
                                :disabled="loadingConcepts || isEditing" class="block w-full"
                                :class="{ invalid: attemptedSave && !selectedAccountingConcept }">
                                <template #no-options>
                                    {{ t('common.no_records') }}
                                </template>
                            </v-select>
                        </template>
                    </section>

                    <!-- Section: Invoice options -->
                    <section v-if="selectedCategory === 'invoice' && selectedAccountingConcept"
                        class="border-b px-4 py-4 space-y-4"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent)">
                        <div class="flex items-center gap-2">
                            <span class="font-mono text-[10px] font-bold tracking-[0.14em]"
                                style="color: var(--accent-soft)">02</span>
                            <h3 class="text-[13px] font-bold text-sky-950">
                                {{ t('pricing_block.accounting_pricing_invoice_category') }}
                            </h3>
                        </div>

                        <div>
                            <div class="flex flex-wrap gap-1.5"
                                :class="{ 'rounded-md border border-red-300 p-2': attemptedSave && !selectedInvoiceCategory }">
                                <button v-for="invoiceCategory in invoiceCategoryOptions" :key="invoiceCategory.token"
                                    type="button"
                                    class="rounded-md border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
                                    :class="selectedInvoiceCategory === invoiceCategory.token
                                        ? 'border-[var(--accent)] bg-[var(--accent)] text-white'
                                        : isEditing
                                            ? 'cursor-not-allowed border-[var(--accent-soft)] bg-[var(--accent-soft)]/20 text-[var(--accent)] opacity-60'
                                            : 'border-[var(--accent-soft)] bg-white text-[var(--accent)] hover:bg-[var(--accent-soft)]/40'
                                        " :disabled="isEditing"
                                    :aria-pressed="selectedInvoiceCategory === invoiceCategory.token"
                                    @click="selectInvoiceCategory(invoiceCategory.token)">
                                    {{ invoiceCategory.name }}
                                </button>
                            </div>
                            <p class="mt-2 text-[11px] leading-snug text-slate-500">
                                {{ invoiceCategoryHint }}
                            </p>
                        </div>

                        <div v-if="showsInvoiceOrigins">
                            <div class="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                                <label class="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('common.origins') }}
                                    <span class="font-normal normal-case tracking-normal text-slate-400">({{
                                        t('common.optional') }})</span>
                                    <span v-if="loadingOrigins" class="ml-1">…</span>
                                </label>
                                <button type="button"
                                    class="rounded-md bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-50"
                                    :disabled="!origins.length" @click="selectAllOrigins">
                                    {{ t('common.select_all') }}
                                </button>
                            </div>
                            <v-select :model-value="selectedOrigins" :options="origins" multiple class="block w-full"
                                :loading="loadingOrigins" :disabled="loadingOrigins"
                                @update:model-value="onOriginsChange">
                                <template #no-options>
                                    {{ t('common.no_records') }}
                                </template>
                            </v-select>
                            <p class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                {{ t('pricing_block.accounting_pricing_invoice_origins_hint') }}
                            </p>
                        </div>

                        <div v-if="showsInvoiceContractTypes">
                            <div class="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                                <label class="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('common.usage_type') }}
                                    <span class="font-normal normal-case tracking-normal text-slate-400">({{
                                        t('common.optional') }})</span>
                                    <span v-if="loadingContractTypes" class="ml-1">…</span>
                                </label>
                                <button type="button"
                                    class="rounded-md bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-50"
                                    :disabled="!contractTypes.length" @click="selectAllContractTypes">
                                    {{ t('common.select_all') }}
                                </button>
                            </div>
                            <v-select :model-value="selectedContractTypes" :options="contractTypes" multiple
                                class="block w-full" :loading="loadingContractTypes" :disabled="loadingContractTypes"
                                @update:model-value="onContractTypesChange">
                                <template #no-options>
                                    {{ t('common.no_records') }}
                                </template>
                            </v-select>
                            <p class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                {{ t('pricing_block.accounting_pricing_invoice_contract_types_hint') }}
                            </p>
                        </div>

                        <div v-if="showsUndeclarePrevious" class="rounded-md border px-3 py-3"
                            style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 18%, white)">
                            <label class="inline-flex cursor-pointer items-center gap-2 text-[13px] text-sky-950">
                                <input v-model="undeclarePrevious" type="checkbox" class="checkbox" />
                                <span>{{ t('pricing_block.accounting_pricing_undeclare_previous') }}</span>
                            </label>
                            <p class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                {{ undeclarePreviousHint }}
                            </p>
                        </div>
                    </section>

                    <!-- Section: Payment types -->
                    <section v-if="selectedCategory === 'payment'" class="border-b px-4 py-4"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent)">
                        <div class="mb-4">
                            <label
                                class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                {{ t('pricing_block.accounting_pricing_payment_category') }}
                            </label>
                            <div class="flex flex-wrap gap-1.5"
                                :class="{ 'rounded-md border border-red-300 p-2': attemptedSave && !selectedPaymentCategory }">
                                <button v-for="paymentCategory in paymentCategoryOptions" :key="paymentCategory.token"
                                    type="button"
                                    class="rounded-md border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
                                    :class="selectedPaymentCategory === paymentCategory.token
                                        ? 'border-[var(--accent)] bg-[var(--accent)] text-white'
                                        : isEditing
                                            ? 'cursor-not-allowed border-[var(--accent-soft)] bg-[var(--accent-soft)]/20 text-[var(--accent)] opacity-60'
                                            : 'border-[var(--accent-soft)] bg-white text-[var(--accent)] hover:bg-[var(--accent-soft)]/40'
                                        " :disabled="isEditing"
                                    :aria-pressed="selectedPaymentCategory === paymentCategory.token"
                                    @click="selectPaymentCategory(paymentCategory.token)">
                                    {{ paymentCategory.name }}
                                </button>
                            </div>
                            <p class="mt-2 text-[11px] leading-snug text-slate-500">
                                {{ paymentCategoryHint }}
                            </p>
                        </div>

                        <div class="mb-3 flex items-center justify-between gap-2">
                            <div class="flex items-center gap-2">
                                <span class="font-mono text-[10px] font-bold tracking-[0.14em]"
                                    style="color: var(--accent-soft)">02</span>
                                <h3 class="text-[13px] font-bold text-sky-950">
                                    {{ t('payment_types') }} *
                                </h3>
                            </div>
                            <button type="button"
                                class="rounded-md bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-50"
                                :disabled="!paymentTypes.length" @click="selectAllPaymentTypes">
                                {{ t('common.select_all') }}
                            </button>
                        </div>
                        <v-select :model-value="selectedPaymentTypes" :options="paymentTypes" multiple append-to-body
                            class="block w-full" :class="{ invalid: attemptedSave && !selectedPaymentTypes.length }"
                            @update:model-value="onPaymentTypesChange">
                            <template #no-options>
                                {{ t('common.no_records') }}
                            </template>
                        </v-select>

                        <div v-if="showsIbanPaymentScope" class="mt-4 space-y-3 rounded-md border px-3 py-3"
                            style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 18%, white)">
                            <div>
                                <p class="mb-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    IBAN
                                </p>
                                <div class="flex flex-wrap gap-4">
                                    <label
                                        class="inline-flex cursor-pointer items-center gap-2 text-[12px] text-sky-950">
                                        <input v-model="selectedForeignIban" type="checkbox" class="checkbox" />
                                        <span>{{ t('pricing_block.accounting_pricing_foreign_iban') }}</span>
                                    </label>
                                    <label
                                        class="inline-flex cursor-pointer items-center gap-2 text-[12px] text-sky-950">
                                        <input v-model="selectedNationalIban" type="checkbox" class="checkbox" />
                                        <span>{{ t('pricing_block.accounting_pricing_national_iban') }}</span>
                                    </label>
                                </div>
                                <p class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                    {{ ibanScopeHint }}
                                </p>
                            </div>
                            <div>
                                <p class="mb-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('payments') }}
                                </p>
                                <div class="flex flex-wrap gap-4">
                                    <label
                                        class="inline-flex cursor-pointer items-center gap-2 text-[12px] text-sky-950">
                                        <input v-model="selectedOutgoingPayments" type="checkbox" class="checkbox" />
                                        <span>{{ t('pricing_block.accounting_pricing_outgoing_payments') }}</span>
                                    </label>
                                    <label
                                        class="inline-flex cursor-pointer items-center gap-2 text-[12px] text-sky-950">
                                        <input v-model="selectedIncomingPayments" type="checkbox" class="checkbox" />
                                        <span>{{ t('pricing_block.accounting_pricing_incoming_payments') }}</span>
                                    </label>
                                </div>
                                <p class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                    {{ movementScopeHint }}
                                </p>
                            </div>
                        </div>

                        <div v-if="showsBankPaymentOrigin" class="mt-4 rounded-md border px-3 py-3"
                            style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 18%, white)">
                            <p class="mb-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                {{ t('billing_block.payment_origin') }}
                            </p>
                            <div class="flex flex-wrap gap-1.5">
                                <button type="button"
                                    class="rounded-md border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
                                    :class="!selectedPaymentOrigin
                                        ? 'border-[var(--accent)] bg-[var(--accent)] text-white'
                                        : existingSelection
                                            ? 'cursor-not-allowed border-[var(--accent-soft)] bg-[var(--accent-soft)]/20 text-[var(--accent)] opacity-60'
                                            : 'border-[var(--accent-soft)] bg-white text-[var(--accent)] hover:bg-[var(--accent-soft)]/40'"
                                    :disabled="!!existingSelection"
                                    :aria-pressed="!selectedPaymentOrigin"
                                    @click="selectPaymentOrigin(null)">
                                    {{ t('pricing_block.accounting_pricing_payment_origin_all') }}
                                </button>
                                <button v-for="origin in paymentOriginOptions" :key="origin.token" type="button"
                                    class="rounded-md border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
                                    :class="selectedPaymentOrigin === origin.token
                                        ? 'border-[var(--accent)] bg-[var(--accent)] text-white'
                                        : existingSelection || !bankPaymentOriginExclusive
                                            ? 'cursor-not-allowed border-[var(--accent-soft)] bg-[var(--accent-soft)]/20 text-[var(--accent)] opacity-60'
                                            : 'border-[var(--accent-soft)] bg-white text-[var(--accent)] hover:bg-[var(--accent-soft)]/40'"
                                    :disabled="!!existingSelection || !bankPaymentOriginExclusive"
                                    :aria-pressed="selectedPaymentOrigin === origin.token"
                                    @click="selectPaymentOrigin(origin.token)">
                                    {{ origin.name }}
                                </button>
                            </div>
                            <p class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                {{ paymentOriginHint }}
                            </p>
                        </div>
                    </section>

                    <!-- Section: Line item cascade -->
                    <section v-if="selectedCategory === 'lineitem'" class="px-4 py-4 space-y-4"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent)">
                        <div class="flex items-center gap-2">
                            <span class="font-mono text-[10px] font-bold tracking-[0.14em]"
                                style="color: var(--accent-soft)">02</span>
                            <h3 class="text-[13px] font-bold text-sky-950">
                                {{ t('pricing_block.line_items') }}
                            </h3>
                        </div>

                        <p v-if="showLineitemCascadeHint" class="text-[11px] leading-snug text-slate-500">
                            {{ t('pricing_block.accounting_pricing_lineitem_cascade_hint') }}
                            {{ t('pricing_block.accounting_pricing_unselected_keep_default_hint') }}
                        </p>

                        <div>
                            <div class="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                                <label class="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('common.products') }} *
                                </label>
                                <button type="button"
                                    class="rounded-md bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-50"
                                    :disabled="!products.length || isEditing" @click="selectAllProducts">
                                    {{ t('common.select_all') }}
                                </button>
                            </div>
                            <v-select :model-value="selectedProducts" :options="products" multiple class="block w-full"
                                :disabled="isEditing" :class="{ invalid: attemptedSave && !selectedProducts.length }"
                                @update:model-value="onProductsChange">
                                <template #no-options>
                                    {{ t('common.no_records') }}
                                </template>
                            </v-select>
                        </div>

                        <div v-if="selectedProducts.length" class="rounded-md border px-3 py-3 space-y-4"
                            style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 12%, white)">
                            <div>
                                <div class="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                                    <label class="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                        {{ t('common.price_rates') }}
                                        <span class="font-normal normal-case tracking-normal">({{ t('common.optional')
                                            }})</span>
                                        <span v-if="loadingRelations" class="ml-1">…</span>
                                    </label>
                                    <button type="button"
                                        class="rounded-md bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-50"
                                        :disabled="!priceRates.length || !canEditProductChildren"
                                        @click="selectAllPriceRates">
                                        {{ t('common.select_all') }}
                                    </button>
                                </div>
                                <v-select :model-value="selectedPriceRates" :options="priceRates" multiple
                                    :disabled="!priceRates.length || !canEditProductChildren" class="block w-full"
                                    @update:model-value="onPriceRatesChange">
                                    <template #no-options>
                                        {{ t('common.no_records') }}
                                    </template>
                                </v-select>
                                <p v-if="showStoppedAtLevelHint && lineitemCascadeLevel === 'product'"
                                    class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                    {{ t('pricing_block.accounting_pricing_stopped_at_product_hint') }}
                                </p>
                                <p v-if="showPartialPriceRatesHint"
                                    class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                    {{ t('pricing_block.accounting_pricing_partial_price_rates_hint') }}
                                </p>
                            </div>

                            <div v-if="showLineItemTypesSection">
                                <div class="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                                    <label class="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                        {{ t('pricing_block.line_items') }}
                                        <span class="font-normal normal-case tracking-normal">({{ t('common.optional')
                                            }})</span>
                                    </label>
                                    <button type="button"
                                        class="rounded-md bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-50"
                                        :disabled="!lineItemTypes.length || !canEditProductChildren"
                                        @click="selectAllLineItemTypes">
                                        {{ t('common.select_all') }}
                                    </button>
                                </div>
                                <v-select :model-value="selectedLineItemTypes" :options="lineItemTypes" multiple
                                    :disabled="!lineItemTypes.length || !canEditProductChildren" class="block w-full"
                                    @update:model-value="onLineItemTypesChange">
                                    <template #no-options>
                                        {{ t('common.no_records') }}
                                    </template>
                                </v-select>
                                <p v-if="showStoppedAtLevelHint && lineitemCascadeLevel === 'price_rate'"
                                    class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                    {{ t('pricing_block.accounting_pricing_stopped_at_price_rate_hint') }}
                                </p>
                                <p v-if="showPartialLineItemsHint"
                                    class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                    {{ t('pricing_block.accounting_pricing_partial_line_items_hint') }}
                                </p>
                            </div>

                            <div v-if="showPriceIntervalsSection">
                                <div class="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                                    <label class="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                        {{ t('pricing_block.price_interval') }}
                                        <span class="font-normal normal-case tracking-normal">({{ t('common.optional')
                                            }})</span>
                                    </label>
                                    <button type="button"
                                        class="rounded-md bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-50"
                                        :disabled="!priceIntervals.length || !canEditProductChildren"
                                        @click="selectAllPriceIntervals">
                                        {{ t('common.select_all') }}
                                    </button>
                                </div>
                                <v-select :model-value="selectedPriceIntervals" :options="priceIntervals" multiple
                                    :disabled="!canEditProductChildren" class="block w-full"
                                    @update:model-value="onPriceIntervalsChange">
                                    <template #no-options>
                                        {{ t('common.no_records') }}
                                    </template>
                                </v-select>
                            </div>

                            <div v-if="showPriceVariablesSection">
                                <div class="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                                    <label class="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                        {{ t('pricing_block.variable_price') }}
                                        <span class="font-normal normal-case tracking-normal">({{ t('common.optional')
                                            }})</span>
                                    </label>
                                    <button type="button"
                                        class="rounded-md bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-50"
                                        :disabled="!priceVariables.length || !canEditProductChildren"
                                        @click="selectAllPriceVariables">
                                        {{ t('common.select_all') }}
                                    </button>
                                </div>
                                <v-select :model-value="selectedPriceVariables" :options="priceVariables" multiple
                                    :disabled="!canEditProductChildren" class="block w-full"
                                    @update:model-value="onPriceVariablesChange">
                                    <template #no-options>
                                        {{ t('common.no_records') }}
                                    </template>
                                </v-select>
                            </div>

                            <p v-if="showStoppedAtLevelHint && lineitemCascadeLevel === 'line_item_type'"
                                class="text-[11px] leading-snug text-slate-500">
                                {{ t('pricing_block.accounting_pricing_stopped_at_line_item_hint') }}
                            </p>
                        </div>
                    </section>

                    <!-- Footer actions -->
                    <div class="flex flex-row-reverse items-center gap-2 px-4 py-3"
                        style="background-color: color-mix(in srgb, var(--accent-soft) 12%, white)">
                        <button type="button"
                            class="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 text-[11px] font-semibold text-white transition-colors hover:bg-sky-800 disabled:opacity-50"
                            :disabled="!canGoToValuesStep" @click="goToValuesStep">
                            {{ t('common.next') }}
                            <Icon name="fa6-solid:arrow-right" class="size-3" />
                        </button>
                        <!-- <button type="button"
                            class="rounded-md border border-slate-200 bg-white px-4 py-2 text-[11px] font-semibold text-slate-600 transition-colors hover:bg-slate-50"
                            @click="emit('close')">
                            {{ t('common.cancel') }}
                        </button> -->
                    </div>
                </div>

                <!-- Stage 2: default + per-value token/name -->
                <div v-else key="values" class="flex flex-col">
                    <!-- Context summary -->
                    <div class="flex items-center gap-3 border-b px-4 py-3"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent); background-color: color-mix(in srgb, var(--accent-soft) 14%, white)">
                        <button type="button"
                            class="inline-flex shrink-0 items-center gap-1.5 rounded-md border bg-white px-2.5 py-1.5 text-[11px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent-soft)]/40"
                            style="border-color: var(--accent-soft)" @click="goToRelationsStep">
                            <Icon name="fa6-solid:arrow-left" class="size-3" />
                            {{ t('common.go_back') }}
                        </button>
                        <div class="min-w-0">
                            <p class="truncate text-[13px] font-bold text-sky-950">
                                {{categories.find((c) => c.token === selectedCategory)?.name}}
                                <template v-if="selectedCategory === 'invoice' && selectedInvoiceCategory">
                                    · {{invoiceCategoryOptions.find((c) => c.token === selectedInvoiceCategory)?.name
                                    }}
                                </template>
                                <template v-if="selectedCategory === 'payment' && selectedPaymentCategory">
                                    · {{paymentCategoryOptions.find((c) => c.token === selectedPaymentCategory)?.name
                                    }}
                                </template>
                            </p>
                            <p v-if="selectedAccountingConcept"
                                class="truncate font-mono text-[10px] tracking-wide text-slate-500">
                                {{ selectedAccountingConcept.label || selectedAccountingConcept.name }}
                            </p>
                        </div>
                    </div>

                    <!-- Section: Identity -->
                    <section class="border-b px-4 py-4"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent)">
                        <div class="mb-1 flex items-center gap-2">
                            <span class="font-mono text-[10px] font-bold tracking-[0.14em]"
                                style="color: var(--accent-soft)">01</span>
                            <h3 class="text-[13px] font-bold text-sky-950">
                                {{ t('pricing_block.accounting_pricing_default_values') }}
                            </h3>
                        </div>
                        <p class="mb-3 text-[11px] leading-snug text-slate-500">
                            {{ t('pricing_block.accounting_pricing_default_values_hint') }}
                            {{ t('pricing_block.accounting_pricing_default_scope_hint') }}
                        </p>

                        <div v-if="existingSelection"
                            class="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[12px] text-amber-800">
                            {{ t('pricing_block.accounting_pricing_already_exists_will_not_save') }}
                            <span v-if="existingSelection.token || existingSelection.name" class="font-medium">
                                ({{ existingSelection.token }}
                                <template v-if="existingSelection.tokenReturn"> · {{ existingSelection.tokenReturn
                                    }}</template>
                                {{ existingSelection.token && existingSelection.name ? ' · ' : '' }}
                                {{ existingSelection.name }}
                                <template v-if="existingSelection.declaredAs"> · {{ existingSelection.declaredAs
                                    }}</template>)
                            </span>
                        </div>

                        <div class="grid gap-3 sm:grid-cols-2">
                            <div>
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('common.identificator') }} / {{ t('common.code') }} *
                                </label>
                                <input v-model="token" type="text" class="input" :disabled="!!existingSelection"
                                    :class="{ invalid: attemptedSave && !token?.trim() }" />
                            </div>

                            <div>
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('pricing_block.accounting_pricing_token_return') }}
                                    <span class="font-normal normal-case tracking-normal">({{ t('common.optional')
                                        }})</span>
                                </label>
                                <input v-model="tokenReturn" type="text" class="input" :disabled="!!existingSelection"
                                    :placeholder="t('pricing_block.accounting_pricing_token_return')" />
                                <!-- <p class="mt-1 text-[11px] leading-snug text-slate-500">
                                    {{ t('pricing_block.accounting_pricing_token_return_hint') }}
                                </p> -->
                            </div>

                            <div>
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('common.name') }} *
                                </label>
                                <input v-model="name" type="text" class="input" :disabled="!!existingSelection"
                                    :class="{ invalid: attemptedSave && !name?.trim() }" />
                            </div>

                            <div>
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('pricing_block.accounting_pricing_declared_as') }}
                                    <span class="font-normal normal-case tracking-normal">({{ t('common.optional')
                                        }})</span>
                                </label>
                                <input v-model="declaredAs" type="text" class="input" :disabled="!!existingSelection"
                                    :placeholder="t('pricing_block.accounting_pricing_declared_as')" />
                                <p class="mt-1 text-[11px] leading-snug text-slate-500">
                                    {{ t('pricing_block.accounting_pricing_declared_as_hint') }}
                                </p>
                            </div>

                            <div class="sm:col-span-2 rounded-md border px-3 py-2.5"
                                style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 14%, white)">
                                <label class="inline-flex items-center gap-2 text-[12px] text-sky-950"
                                    :class="existingSelection ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'">
                                    <input v-model="groupValues" type="checkbox" class="checkbox"
                                        :disabled="!!existingSelection" />
                                    <span>{{ t('pricing_block.accounting_pricing_group_values') }}</span>
                                </label>
                                <p class="mt-1 text-[11px] leading-snug text-slate-500">
                                    {{ t('pricing_block.accounting_pricing_group_values_hint') }}
                                </p>
                            </div>

                            <div v-if="selectedCategory === 'invoice' && groupValues"
                                class="sm:col-span-2 rounded-md border px-3 py-2.5"
                                style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 14%, white)">
                                <label class="inline-flex items-center gap-2 text-[12px] text-sky-950"
                                    :class="existingSelection ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'">
                                    <input v-model="separateByOrigin" type="checkbox" class="checkbox"
                                        :disabled="!!existingSelection" />
                                    <span>{{ t('pricing_block.accounting_pricing_separate_by_origin') }}</span>
                                </label>
                                <p class="mt-1 text-[11px] leading-snug text-slate-500">
                                    {{ t('pricing_block.accounting_pricing_separate_by_origin_hint') }}
                                </p>
                            </div>

                            <div v-if="selectedCategory === 'payment' && groupValues"
                                class="sm:col-span-2 space-y-3 rounded-md border px-3 py-2.5"
                                style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 14%, white)">
                                <div>
                                    <label class="inline-flex items-center gap-2 text-[12px] text-sky-950"
                                        :class="existingSelection ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'">
                                        <input v-model="separateByType" type="checkbox" class="checkbox"
                                            :disabled="!!existingSelection" />
                                        <span>{{ t('pricing_block.accounting_pricing_separate_by_type') }}</span>
                                    </label>
                                </div>
                                <div v-if="showsBankPaymentOrigin">
                                    <label class="inline-flex items-center gap-2 text-[12px] text-sky-950"
                                        :class="existingSelection ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'">
                                        <input v-model="separateByPaymentOrigin" type="checkbox" class="checkbox"
                                            :disabled="!!existingSelection" />
                                        <span>{{ t('pricing_block.accounting_pricing_separate_by_payment_origin') }}</span>
                                    </label>
                                    <p class="mt-1 text-[11px] leading-snug text-slate-500">
                                        {{ t('pricing_block.accounting_pricing_separate_by_payment_origin_hint') }}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </section>

                    <!-- Section: Scope (company / exploitation / cost center / banks) -->
                    <section class="border-b px-4 py-4"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent)">
                        <div class="mb-3 flex items-center gap-2">
                            <span class="font-mono text-[10px] font-bold tracking-[0.14em]"
                                style="color: var(--accent-soft)">02</span>
                            <h3 class="text-[13px] font-bold text-sky-950">
                                {{ t('common.additional_values') }}
                            </h3>
                        </div>

                        <div class="grid gap-3 sm:grid-cols-2">
                            <div v-if="showExploitation">
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('exploitation') }} *
                                </label>
                                <v-select v-model="selectedExploitation" :options="exploitations" class="block w-full"
                                    :disabled="!!existingSelection"
                                    :class="{ invalid: attemptedSave && !selectedExploitation }">
                                    <template #no-options>
                                        {{ t('common.no_records') }}
                                    </template>
                                </v-select>
                            </div>

                            <div>
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('company') }} *
                                </label>
                                <v-select v-model="selectedCompany" :options="companies"
                                    class="block w-full select-truncate" :disabled="!!existingSelection"
                                    :class="{ invalid: attemptedSave && !selectedCompany }">
                                    <template #no-options>
                                        {{ t('common.no_records') }}
                                    </template>
                                </v-select>
                            </div>

                            <div v-if="showsCostCenter">
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400 select-truncate">
                                    {{ t('pricing_block.accounting_cost_center') }}
                                    <span class="font-normal normal-case tracking-normal">({{ t('common.optional')
                                        }})</span>
                                    <span v-if="loadingCostCenters" class="ml-1">…</span>
                                </label>
                                <v-select v-model="selectedCostCenter" :options="costCenters" :clearable="true"
                                    class="block w-full" :loading="loadingCostCenters"
                                    :disabled="loadingCostCenters || !!existingSelection">
                                    <template #no-options>
                                        {{ t('common.no_records') }}
                                    </template>
                                </v-select>
                            </div>

                            <div v-if="showsIbanPaymentScope"
                                class="sm:col-span-2 space-y-3 rounded-md border px-3 py-3"
                                style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 14%, white)">
                                <div>
                                    <div class="flex flex-wrap gap-4">
                                        <label
                                            class="inline-flex cursor-pointer items-center gap-2 text-[12px] text-sky-950">
                                            <input v-model="selectedForeignIban" type="checkbox" class="checkbox" />
                                            <span>{{ t('pricing_block.accounting_pricing_foreign_iban') }}</span>
                                        </label>
                                        <label
                                            class="inline-flex cursor-pointer items-center gap-2 text-[12px] text-sky-950">
                                            <input v-model="selectedNationalIban" type="checkbox" class="checkbox" />
                                            <span>{{ t('pricing_block.accounting_pricing_national_iban') }}</span>
                                        </label>
                                    </div>
                                    <p class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                        {{ ibanScopeHint }}
                                    </p>
                                </div>
                                <div>
                                    <div class="flex flex-wrap gap-4">
                                        <label
                                            class="inline-flex cursor-pointer items-center gap-2 text-[12px] text-sky-950">
                                            <input v-model="selectedOutgoingPayments" type="checkbox"
                                                class="checkbox" />
                                            <span>{{ t('pricing_block.accounting_pricing_outgoing_payments') }}</span>
                                        </label>
                                        <label
                                            class="inline-flex cursor-pointer items-center gap-2 text-[12px] text-sky-950">
                                            <input v-model="selectedIncomingPayments" type="checkbox"
                                                class="checkbox" />
                                            <span>{{ t('pricing_block.accounting_pricing_incoming_payments') }}</span>
                                        </label>
                                    </div>
                                    <p class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                        {{ movementScopeHint }}
                                    </p>
                                </div>
                            </div>

                            <div v-if="showsBankPaymentOrigin" class="sm:col-span-2 rounded-md border px-3 py-3"
                                style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 14%, white)">
                                <p class="mb-2 text-[9px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('billing_block.payment_origin') }}
                                </p>
                                <div class="flex flex-wrap gap-1.5">
                                    <button type="button"
                                        class="rounded-md border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
                                        :class="!selectedPaymentOrigin
                                            ? 'border-[var(--accent)] bg-[var(--accent)] text-white'
                                            : existingSelection
                                                ? 'cursor-not-allowed border-[var(--accent-soft)] bg-[var(--accent-soft)]/20 text-[var(--accent)] opacity-60'
                                                : 'border-[var(--accent-soft)] bg-white text-[var(--accent)] hover:bg-[var(--accent-soft)]/40'"
                                        :disabled="!!existingSelection"
                                        :aria-pressed="!selectedPaymentOrigin"
                                        @click="selectPaymentOrigin(null)">
                                        {{ t('pricing_block.accounting_pricing_payment_origin_all') }}
                                    </button>
                                    <button v-for="origin in paymentOriginOptions" :key="`values-${origin.token}`"
                                        type="button"
                                        class="rounded-md border px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] transition-colors"
                                        :class="selectedPaymentOrigin === origin.token
                                            ? 'border-[var(--accent)] bg-[var(--accent)] text-white'
                                            : existingSelection || !bankPaymentOriginExclusive
                                                ? 'cursor-not-allowed border-[var(--accent-soft)] bg-[var(--accent-soft)]/20 text-[var(--accent)] opacity-60'
                                                : 'border-[var(--accent-soft)] bg-white text-[var(--accent)] hover:bg-[var(--accent-soft)]/40'"
                                        :disabled="!!existingSelection || !bankPaymentOriginExclusive"
                                        :aria-pressed="selectedPaymentOrigin === origin.token"
                                        @click="selectPaymentOrigin(origin.token)">
                                        {{ origin.name }}
                                    </button>
                                </div>
                                <p class="mt-1.5 text-[11px] leading-snug text-slate-500">
                                    {{ paymentOriginHint }}
                                </p>
                            </div>

                            <div v-if="showsUndeclarePrevious" class="sm:col-span-2 rounded-md border px-3 py-2.5"
                                style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 14%, white)">
                                <label class="inline-flex cursor-pointer items-center gap-2 text-[12px] text-sky-950">
                                    <input v-model="undeclarePrevious" type="checkbox" class="checkbox" />
                                    <span>{{ t('pricing_block.accounting_pricing_undeclare_previous') }}</span>
                                </label>
                                <p class="mt-1 text-[11px] leading-snug text-slate-500">
                                    {{ undeclarePreviousHint }}
                                </p>
                            </div>

                            <div v-if="selectedCategory === 'payment'" class="sm:col-span-2">
                                <div class="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                                    <label class="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                        {{ t('common.banks') }}
                                        <span class="font-normal normal-case tracking-normal">({{ t('common.optional')
                                            }})</span>
                                        <span v-if="loadingBanks" class="ml-1">…</span>
                                    </label>
                                    <button type="button"
                                        class="rounded-md bg-[var(--accent-soft)] px-2.5 py-1 text-[10px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-50"
                                        :disabled="!banks.length || !!existingSelection" @click="selectAllBanks">
                                        {{ t('common.select_all') }}
                                    </button>
                                </div>
                                <v-select :model-value="selectedBanks" :options="banks" multiple class="block w-full"
                                    :loading="loadingBanks" :disabled="loadingBanks || !!existingSelection"
                                    @update:model-value="onBanksChange">
                                    <template #no-options>
                                        {{ t('common.no_records') }}
                                    </template>
                                </v-select>
                            </div>
                        </div>
                    </section>

                    <!-- Section: Per-value assignments -->
                    <section v-if="loadingExisting" class="px-4 py-6 text-center text-[12px] text-slate-500">
                        <Icon name="fa6-solid:spinner" class="mr-1.5 animate-spin" />
                        {{ t('common.loading') }}
                    </section>

                    <section v-else-if="hasAssignmentRows" class="px-4 py-4">
                        <div class="mb-1 flex items-center gap-2">
                            <span class="font-mono text-[10px] font-bold tracking-[0.14em]"
                                style="color: var(--accent-soft)">03</span>
                            <h3 class="text-[13px] font-bold text-sky-950">
                                {{ t('pricing_block.accounting_pricing_assign_values_title') }}
                            </h3>
                        </div>
                        <p class="mb-3 text-[11px] leading-snug text-slate-500">
                            {{ t('pricing_block.accounting_pricing_assign_values_hint') }}
                        </p>

                        <div class="space-y-2">
                            <details v-for="group in valueAssignmentGroups" :key="group.kind"
                                class="group/details rounded-md border bg-white"
                                style="border-color: var(--accent-soft)"
                                v-bind="attemptedSave && group.summary.isEmpty > 0 ? { open: true } : {}">
                                <summary
                                    class="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5 outline-none transition-colors hover:bg-sky-50/60 [&::-webkit-details-marker]:hidden">
                                    <div class="min-w-0 flex-1">
                                        <div class="flex flex-wrap items-center gap-2">
                                            <span class="text-[12px] font-bold uppercase tracking-[0.1em] text-sky-950">
                                                {{ group.title }}
                                            </span>
                                            <span class="font-mono text-[10px] tracking-wider text-slate-400">
                                                {{ String(group.summary.total).padStart(2, '0') }}
                                            </span>
                                        </div>
                                        <div class="mt-1.5 flex flex-wrap gap-1.5">
                                            <span
                                                class="rounded-md bg-amber-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-amber-700">
                                                {{ t('pricing_block.accounting_pricing_group_keeping_default', {
                                                    count: group.summary.keepingDefault,
                                                }) }}
                                            </span>
                                            <span
                                                class="rounded-md px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.1em]"
                                                :class="group.summary.hasCustom
                                                    ? 'bg-[var(--accent-soft)] text-[var(--accent)]'
                                                    : 'bg-slate-100 text-slate-400'">
                                                {{ t('pricing_block.accounting_pricing_group_has_custom', {
                                                    count: group.summary.hasCustom,
                                                }) }}
                                            </span>
                                            <span
                                                class="rounded-md px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.1em]"
                                                :class="group.summary.isEmpty
                                                    ? 'bg-orange-50 text-orange-700'
                                                    : 'bg-slate-100 text-slate-400'">
                                                {{ t('pricing_block.accounting_pricing_group_is_empty', {
                                                    count: group.summary.isEmpty,
                                                }) }}
                                            </span>
                                            <span v-if="group.summary.alreadyExists"
                                                class="rounded-md bg-amber-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-amber-800">
                                                {{ t('pricing_block.accounting_pricing_group_already_exists', {
                                                    count: group.summary.alreadyExists,
                                                }) }}
                                            </span>
                                        </div>
                                    </div>
                                    <Icon name="fa6-solid:chevron-down"
                                        class="size-3 shrink-0 text-slate-400 transition-transform group-open/details:rotate-180" />
                                </summary>

                                <ul class="max-h-[50vh] divide-y overflow-y-auto border-t"
                                    style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent); --tw-divide-opacity: 1; border-top-color: color-mix(in srgb, var(--accent-soft) 50%, transparent)">
                                    <li v-for="(row, rowIndex) in group.rows" :key="row.key"
                                        class="flex items-stretch transition-colors hover:bg-sky-50/40"
                                        :class="{ 'bg-amber-50/40': row.alreadyExists }"
                                        :style="{ borderColor: 'color-mix(in srgb, var(--accent-soft) 40%, transparent)' }">
                                        <div class="flex w-10 shrink-0 items-start justify-center border-r px-1 py-3"
                                            style="border-color: color-mix(in srgb, var(--accent-soft) 40%, transparent); background-color: color-mix(in srgb, var(--accent-soft) 14%, white)">
                                            <span class="mt-0.5 font-mono text-[9px] tracking-wider text-slate-400">
                                                {{ String(rowIndex + 1).padStart(2, '0') }}
                                            </span>
                                        </div>
                                        <div class="min-w-0 flex-1 px-3 py-2.5">
                                            <div class="mb-2 min-w-0">
                                                <div class="flex flex-wrap items-center gap-1.5">
                                                    <p class="truncate text-[13px] font-bold text-sky-950">
                                                        {{ row.label }}
                                                    </p>
                                                    <span v-if="row.alreadyExists"
                                                        class="rounded-md bg-amber-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-amber-800">
                                                        {{ t('pricing_block.accounting_pricing_already_exists_tag') }}
                                                    </span>
                                                </div>
                                                <p v-if="row.hint" class="mt-0.5 text-[11px] text-slate-500">
                                                    {{ row.hint }}
                                                </p>
                                                <p v-if="row.alreadyExists" class="mt-1 text-[11px] text-amber-700">
                                                    {{
                                                        t('pricing_block.accounting_pricing_already_exists_will_not_save')
                                                    }}
                                                    <template v-if="row.existing?.token || row.existing?.name">
                                                        · {{ row.existing.token }}{{ row.existing.token &&
                                                            row.existing.name
                                                            ? ' · ' : '' }}{{ row.existing.name }}
                                                    </template>
                                                </p>
                                            </div>

                                            <div class="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                                                <label
                                                    class="inline-flex shrink-0 items-center gap-1.5 text-[11px] text-slate-600"
                                                    :class="row.alreadyExists ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'">
                                                    <input type="checkbox" class="checkbox"
                                                        :checked="row.alreadyExists ? true : row.useDefault"
                                                        :disabled="row.alreadyExists"
                                                        @change="setAssignmentUseDefault(row.key, $event.target.checked)" />
                                                    <span>{{ t('pricing_block.accounting_pricing_use_default_values')
                                                        }}</span>
                                                </label>

                                                <input type="text" class="input w-full sm:w-24"
                                                    :disabled="row.alreadyExists || row.useDefault"
                                                    :placeholder="token || t('common.code')" :value="row.alreadyExists
                                                        ? (row.existing?.token || '')
                                                        : (row.useDefault ? token : row.customToken)" :class="{
                                                            invalid:
                                                                attemptedSave &&
                                                                !row.alreadyExists &&
                                                                !row.useDefault &&
                                                                !(row.customToken || '').trim(),
                                                        }" @input="setAssignmentToken(row.key, $event.target.value)" />

                                                <input type="text" class="input w-full sm:w-28"
                                                    :disabled="row.alreadyExists || row.useDefault"
                                                    :title="t('pricing_block.accounting_pricing_token_return_hint')"
                                                    :placeholder="tokenReturn || t('pricing_block.accounting_pricing_token_return')"
                                                    :value="row.alreadyExists
                                                        ? (row.existing?.tokenReturn || '')
                                                        : (row.useDefault ? tokenReturn : row.customTokenReturn)"
                                                    @input="setAssignmentTokenReturn(row.key, $event.target.value)" />

                                                <input type="text" class="input w-full sm:flex-1 sm:min-w-[8rem]"
                                                    :disabled="row.alreadyExists || row.useDefault"
                                                    :placeholder="name || t('common.name')" :value="row.alreadyExists
                                                        ? (row.existing?.name || '')
                                                        : (row.useDefault ? name : row.customName)" :class="{
                                                            invalid:
                                                                attemptedSave &&
                                                                !row.alreadyExists &&
                                                                !row.useDefault &&
                                                                !(row.customName || '').trim(),
                                                        }" @input="setAssignmentName(row.key, $event.target.value)" />

                                                <input type="text" class="input w-full sm:flex-1 sm:min-w-[8rem]"
                                                    :disabled="row.alreadyExists || row.useDefault"
                                                    :title="t('pricing_block.accounting_pricing_declared_as_hint')"
                                                    :placeholder="declaredAs || t('pricing_block.accounting_pricing_declared_as')"
                                                    :value="row.alreadyExists
                                                        ? (row.existing?.declaredAs || '')
                                                        : (row.useDefault ? declaredAs : row.customDeclaredAs)"
                                                    @input="setAssignmentDeclaredAs(row.key, $event.target.value)" />

                                                <v-select v-if="showsCostCenter"
                                                    class="block w-full sm:min-w-[12rem] sm:flex-1" :model-value="row.alreadyExists
                                                        ? null
                                                        : (row.useDefault ? selectedCostCenter : row.customCostCenter)"
                                                    :options="costCenters" :clearable="true" append-to-body
                                                    :disabled="row.alreadyExists || row.useDefault || loadingCostCenters"
                                                    :placeholder="t('pricing_block.accounting_cost_center')"
                                                    @update:model-value="setAssignmentCostCenter(row.key, $event)">
                                                    <template #no-options>
                                                        {{ t('common.no_records') }}
                                                    </template>
                                                </v-select>

                                                <label
                                                    class="inline-flex shrink-0 items-center gap-1.5 text-[11px] text-slate-600"
                                                    :class="row.alreadyExists || row.useDefault ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'">
                                                    <input type="checkbox" class="checkbox" :checked="row.alreadyExists
                                                        ? true
                                                        : (row.useDefault ? groupValues : row.customGroupValues)"
                                                        :disabled="row.alreadyExists || row.useDefault"
                                                        @change="setAssignmentGroupValues(row.key, $event.target.checked)" />
                                                    <span>{{ t('pricing_block.accounting_pricing_group_values')
                                                    }}</span>
                                                </label>
                                            </div>
                                        </div>
                                    </li>
                                </ul>
                            </details>
                        </div>
                    </section>

                    <!-- Section: Extra declaration lines -->
                    <section class="border-t px-4 py-4"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent)">
                        <div class="mb-1 flex flex-wrap items-center justify-between gap-2">
                            <div class="min-w-0">
                                <div class="mb-1 flex items-center gap-2">
                                    <span class="font-mono text-[10px] font-bold tracking-[0.14em]"
                                        style="color: var(--accent-soft)">04</span>
                                    <h3 class="text-[13px] font-bold text-sky-950">
                                        {{ t('pricing_block.accounting_pricing_additional_lines_title') }}
                                    </h3>
                                </div>
                                <p class="text-[11px] leading-snug text-slate-500">
                                    {{ t('pricing_block.accounting_pricing_additional_lines_hint') }}
                                </p>
                            </div>
                            <button type="button"
                                class="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-[var(--accent-soft)] px-2.5 py-1.5 text-[10px] font-semibold text-[var(--accent)] transition-colors hover:bg-[var(--accent)] hover:text-white disabled:opacity-50"
                                :disabled="!isEditing || loadingAdditionalLines" @click="openAdditionalLinePanel()">
                                <Icon name="fa6-solid:plus" class="size-3" />
                                {{ t('pricing_block.accounting_pricing_additional_lines_add') }}
                            </button>
                        </div>

                        <p v-if="!isEditing" class="mt-2 text-[11px] leading-snug text-amber-700">
                            {{ t('pricing_block.accounting_pricing_additional_lines_save_first') }}
                        </p>

                        <div v-else-if="loadingAdditionalLines" class="mt-3 text-center text-[12px] text-slate-500">
                            <Icon name="fa6-solid:spinner" class="mr-1.5 animate-spin" />
                            {{ t('common.loading') }}
                        </div>

                        <ul v-else-if="activeAdditionalLines.length"
                            class="mt-3 divide-y overflow-hidden rounded-md border bg-white"
                            style="border-color: var(--accent-soft)">
                            <li v-for="line in activeAdditionalLines" :key="line.id"
                                class="flex items-start justify-between gap-3 px-3 py-2.5 transition-colors hover:bg-sky-50/40">
                                <button type="button" class="min-w-0 flex-1 text-left"
                                    @click="openAdditionalLinePanel(line)">
                                    <p class="truncate text-[13px] font-bold text-sky-950">
                                        {{ line.declared_as || line.name || '—' }}
                                    </p>
                                    <p class="mt-0.5 font-mono text-[11px] tracking-wide text-slate-500">
                                        {{ line.token || '—' }}
                                        <template v-if="line.token_return"> · 
                                            <span class="font-bold"> {{ line.token_return }} </span>
                                        </template>
                                        <template class="font-bold" v-if="line.accounting_concept">
                                            · <span class="font-bold"> {{ line.accounting_concept.token }} </span>
                                            {{ line.accounting_concept.name }}
                                        </template>
                                    </p>
                                    <span v-if="line.is_negative"
                                        class="mt-1 inline-block rounded-md bg-orange-50 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-orange-700">
                                        {{ t('pricing_block.accounting_pricing_additional_line_is_negative') }}
                                    </span>
                                </button>
                                <button type="button"
                                    class="inline-flex shrink-0 items-center justify-center rounded-md border border-transparent p-1.5 text-slate-400 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600"
                                    :title="t('common.delete')" @click="deactivateAdditionalLine(line)">
                                    <Icon name="fa6-solid:trash-can" class="size-3.5" />
                                </button>
                            </li>
                        </ul>

                        <p v-else class="mt-3 text-[12px] text-slate-500">
                            {{ t('pricing_block.accounting_pricing_additional_lines_empty') }}
                        </p>
                    </section>

                    <!-- Footer actions -->
                    <div class="flex flex-row-reverse items-center gap-2 border-t px-4 py-3"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent); background-color: color-mix(in srgb, var(--accent-soft) 12%, white)">
                        <button type="submit"
                            class="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 text-[11px] font-semibold text-white transition-colors hover:bg-sky-800 disabled:opacity-50"
                            :disabled="saving || loadingExisting">
                            <Icon :name="saving || loadingExisting ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
                                class="size-3" :class="{ 'animate-spin': saving || loadingExisting }" />
                            {{ saving || loadingExisting ? t('common.loading') : t('common.save') }}
                        </button>
                        <!-- <button type="button"
                            class="rounded-md border border-slate-200 bg-white px-4 py-2 text-[11px] font-semibold text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
                            :disabled="saving || loadingExisting" @click="emit('close')">
                            {{ t('common.cancel') }}
                        </button> -->
                    </div>
                </div>
            </Transition>
        </form>

        <Teleport to="body">
            <div v-if="showAdditionalLinePanel"
                class="fixed inset-0 z-[10000] flex items-center justify-center bg-black/50 p-4"
                style="--accent: #0369a1; --accent-soft: #7dd3fc;" @click.self="closeAdditionalLinePanel">
                <div class="w-full max-w-lg rounded-md border bg-white shadow-xl"
                    style="border-color: var(--accent-soft)" @click.stop>
                    <div class="flex items-center justify-between border-b px-4 py-3"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent); background-color: color-mix(in srgb, var(--accent-soft) 14%, white)">
                        <h3 class="text-[13px] font-bold text-sky-950">
                            {{
                                additionalLineForm.id
                                    ? t('pricing_block.accounting_pricing_additional_lines_edit')
                                    : t('pricing_block.accounting_pricing_additional_lines_add')
                            }}
                        </h3>
                        <button type="button"
                            class="rounded-md p-1 text-slate-400 transition-colors hover:bg-white hover:text-sky-950"
                            @click="closeAdditionalLinePanel">
                            <Icon name="fa6-solid:xmark" class="size-4" />
                        </button>
                    </div>

                    <div class="space-y-3 px-4 py-4">
                        <div class="grid gap-3 sm:grid-cols-2">
                            <div>
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('common.identificator') }} / {{ t('common.code') }} *
                                </label>
                                <input v-model="additionalLineForm.token" type="text" class="input"
                                    :class="{ invalid: additionalLineAttemptedSave && !additionalLineForm.token?.trim() }" />
                            </div>
                            <div>
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('pricing_block.accounting_pricing_token_return') }}
                                    <span class="font-normal normal-case tracking-normal">({{ t('common.optional')
                                        }})</span>
                                </label>
                                <input v-model="additionalLineForm.tokenReturn" type="text" class="input"
                                    :placeholder="t('pricing_block.accounting_pricing_token_return')" />
                            </div>
                            <div>
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('common.name') }} *
                                </label>
                                <input v-model="additionalLineForm.name" type="text" class="input"
                                    :class="{ invalid: additionalLineAttemptedSave && !additionalLineForm.name?.trim() }" />
                            </div>
                            <div>
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('pricing_block.accounting_pricing_declared_as') }}
                                    <span class="font-normal normal-case tracking-normal">({{ t('common.optional')
                                        }})</span>
                                </label>
                                <input v-model="additionalLineForm.declaredAs" type="text" class="input"
                                    :placeholder="t('pricing_block.accounting_pricing_declared_as')" />
                            </div>
                            <div class="sm:col-span-2">
                                <label
                                    class="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                                    {{ t('pricing_block.accounting_concept') }} *
                                    <span v-if="loadingAdditionalLineConcepts" class="ml-1">…</span>
                                </label>
                                <v-select v-model="additionalLineForm.accountingConcept"
                                    :options="additionalLineConceptOptions" class="block w-full" append-to-body
                                    :loading="loadingAdditionalLineConcepts" :disabled="loadingAdditionalLineConcepts"
                                    :class="{
                                        invalid:
                                            additionalLineAttemptedSave &&
                                            !(additionalLineForm.accountingConcept?.code ??
                                                additionalLineForm.accountingConcept?.id),
                                    }">
                                    <template #no-options>
                                        {{ t('common.no_records') }}
                                    </template>
                                </v-select>
                            </div>
                            <div class="sm:col-span-2 rounded-md border px-3 py-2.5"
                                style="border-color: var(--accent-soft); background-color: color-mix(in srgb, var(--accent-soft) 14%, white)">
                                <label class="inline-flex cursor-pointer items-center gap-2 text-[12px] text-sky-950">
                                    <input v-model="additionalLineForm.isNegative" type="checkbox" class="checkbox" />
                                    <span>{{ t('pricing_block.accounting_pricing_additional_line_is_negative') }}</span>
                                </label>
                                <p class="mt-1 text-[11px] leading-snug text-slate-500">
                                    {{ t('pricing_block.accounting_pricing_additional_line_is_negative_hint') }}
                                </p>
                            </div>
                        </div>
                    </div>

                    <div class="flex flex-row-reverse items-center gap-2 border-t px-4 py-3"
                        style="border-color: color-mix(in srgb, var(--accent-soft) 50%, transparent); background-color: color-mix(in srgb, var(--accent-soft) 12%, white)">
                        <button type="button"
                            class="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 text-[11px] font-semibold text-white transition-colors hover:bg-sky-800 disabled:opacity-50"
                            :disabled="savingAdditionalLine" @click="saveAdditionalLine">
                            <Icon :name="savingAdditionalLine ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
                                class="size-3" :class="{ 'animate-spin': savingAdditionalLine }" />
                            {{ savingAdditionalLine ? t('common.loading') : t('common.save') }}
                        </button>
                        <button type="button"
                            class="rounded-md border border-slate-200 bg-white px-4 py-2 text-[11px] font-semibold text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
                            :disabled="savingAdditionalLine" @click="closeAdditionalLinePanel">
                            {{ t('common.cancel') }}
                        </button>
                    </div>
                </div>
            </div>
        </Teleport>
    </div>
</template>

<style scoped>
.stage-enter-active,
.stage-leave-active {
    transition: opacity 0.25s ease, transform 0.35s ease;
}

.stage-enter-from {
    opacity: 0;
    transform: translateX(2rem);
}

.stage-leave-to {
    opacity: 0;
    transform: translateX(-2rem);
}

:deep(.select-truncate .vs__dropdown-toggle) {
    flex-wrap: nowrap;
}

:deep(.select-truncate .vs__selected-options) {
    flex-wrap: nowrap;
    overflow: hidden;
}

:deep(.select-truncate .vs__selected) {
    display: block;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
</style>

<style>
/* append-to-body menus sit under the Teleport overlay (z-10000) without this */
body>ul.vs__dropdown-menu {
    z-index: 10050;
}
</style>
