<script setup>
import H1Region from '../atoms/H1Region.vue';
import FieldDetail from '../atoms/FieldDetail.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
    id: Number,
});

const { $CommunicationApiService, $PersonApiService, $ConfiglistApiService } = useNuxtApp();
const emit = defineEmits(['changed']);

const loading = ref(false);
const loadingPerson = ref(false);
const saving = ref(false);
const error = ref(null);
const communication = ref(null);

const new_address = ref(null);
const new_address_id = ref(null);
const new_email = ref(null);
const new_email_id = ref(null);
const new_phone = ref(null);
const new_phone_id = ref(null);
const selected_message_types = ref([]);
const new_accounting_office = ref(null);
const new_managing_body = ref(null);
const new_processing_unit = ref(null);

const message_types = ref([]);
const person_addresses = ref([]);
const person_emails = ref([]);
const person_phones = ref([]);

const getData = async () => {
    loading.value = true;
    error.value = null;
    try {
        const response = await $CommunicationApiService.getDetail(props.id);
        communication.value = response;
        new_address.value = response.used_address;
        new_email.value = response.used_email;
        new_phone.value = response.used_phones;
        new_accounting_office.value = response.accounting_office;
        new_managing_body.value = response.managing_body;
        new_processing_unit.value = response.processing_unit;
    } catch (error) {
        console.error(error);
        error.value = error;
    } finally {
        loading.value = false;
    }
}

const getPersonData = async () => {
    loadingPerson.value = true;
    try {
        const person_id = communication.value.person?.id
        const response = await $PersonApiService.getDetail(person_id);
        const data = await $ConfiglistApiService.getAll('communication/message-type');
        data.results.forEach((item) => {
            message_types.value.push({
                value: item.id,
                label: item.name
            });
        });

        selected_message_types.value = communication.value.types.map((item) =>item.id);

        if (response) {
            // ADRESSES
            if (!person_addresses.value) {
                person_addresses.value = [];
                person_emails.value = [];
                person_phones.value = [];
            }
            if (response.addresses && response.addresses.length > 0) {
                response.addresses.forEach((response_address) => {

                    person_addresses.value.push({
                        value: response_address.id,
                        label: response_address.address_complete
                    });
                });
            } else if (response.addresses && response.addresses.length == 0) {
                // Only add "no address" option if the array is still empty (not already populated)
                if (person_addresses.value.length === 0) {
                    person_addresses.value.push({
                        value: "",
                        label: `(${t("address_block.no_address")})`
                    });
                }
            }
            // CONTACTS
            if (response.contacts && response.contacts.length > 0) {
                response.contacts.forEach((response_contact) => {
                    if (response_contact.email) {
                        person_emails.value.push({
                            value: response_contact.id,
                            label: response_contact.email
                        });
                    }
                    if (response_contact.phone) {
                        person_phones.value.push({
                            value: response_contact.id,
                            label: response_contact.phone
                        });
                    }
                });
            } else if (response.contacts && response.contacts.length == 0) {
                person_emails.value.push({
                    value: "",
                    label: `(${t("common.no_email")})`
                });
                person_phones.value.push({
                    value: "",
                    label: `(${t("common.no_tlf")})`
                });
            }
        }


    } catch (error) {
        console.error(error);
        error.value = error;
    } finally {
        loadingPerson.value = false;
    }
}

const save = async () => {
    if (!confirm(t("confirmation_text_block.confirm_modify"))) return;
    saving.value = true;
    try {
        console.log("selected_message_types.value");
        console.log(selected_message_types.value);

        let save_data = {
            id: props.id,
            used_address: new_address.value,
            used_phones: new_phone.value,
            used_email: new_email.value,
            types: Object.values(selected_message_types.value),
            accounting_office: new_accounting_office.value,
            managing_body: new_managing_body.value,
            processing_unit: new_processing_unit.value,
        }
        const result = await $CommunicationApiService.save(save_data);
        if (result) {
            emit('changed');
        }
    } catch (error) {
        console.error(error);
        error.value = error;
    } finally {
        saving.value = false;
    }
}

watch(selected_message_types, async (newVal) => {
    console.log("selected_message_types");
    console.log(newVal);
});

onMounted(async () => {
    await getData();
    await getPersonData();
})

watch(new_address_id, async (newVal) => {
    if (!newVal) {
        new_address.value = null;
        return;
    }

    const selectedAddress = person_addresses.value.find((address) => address.value === newVal);
    new_address.value = selectedAddress ? selectedAddress.label : null;
});

watch(new_phone_id, async (newVal) => {
    if (!newVal) {
        new_phone.value = null;
        return;
    }

    const selectedPhone = person_phones.value.find((phone) => phone.value === newVal);
    new_phone.value = selectedPhone ? selectedPhone.label : null;
});

watch(new_email_id, async (newVal) => {
    if (!newVal) {
        new_email.value = null;
        return;
    }

    const selectedEmail = person_emails.value.find((email) => email.value === newVal);
    new_email.value = selectedEmail ? selectedEmail.label : null;
});

</script>

<template>
    <div>
        <H1Region class="mb-3">{{ $t('common.modify') }} {{ $t('communication') }}</H1Region>
        <div v-if="loading" class="flex justify-center items-center">
            <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
            <span class="ml-2">{{ $t('common.loading') }}...</span>

        </div>
        <div v-else-if="error" class="flex justify-center items-center">
            <p>{{ error.message }}</p>
            <button @click="getData" class="underline text-sky-500 hover:no-underline">{{ $t('common.load_again')
                }}</button>
        </div>
        <div v-else-if="communication">
            <div class="space-y-5">
                <div class="mb-2 max-w-lg">
                    <label class="block text-sm font-medium text-slate-500 mb-2">
                        {{ t('common.type') }}</label>
                    <!--<input type="text" v-model="meter_manufacturer" class="input" />-->
                    <v-select multiple :disabled="loadingPerson" :options="message_types" label="label" track-by="id" :reduce="option => option.value"
                        class="w-full custom-select" v-model="selected_message_types" :close-on-select="false" />
                </div>
                <section class="rounded-xl border border-slate-200 bg-white/70 p-4 ">
                    <div class="mb-3 flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">
                                {{ $t('common.address') }}
                            </p>
                            <p class="text-sm text-slate-500">
                                {{ $t('common.select') }} {{ $t('common.or') }} {{ $t('common.add').toLowerCase() }}
                                {{ $t('common.address').toLowerCase() }}
                            </p>
                        </div>
                        <Icon name="ph:map-pin-duotone" class="text-2xl text-slate-400" />
                    </div>
                    <div class="grid gap-3 text-slate-600 md:grid-cols-[minmax(0,1fr),240px]">
                        <input type="text" v-model="new_address" class="input h-11 rounded-lg border-slate-300 text-sm"
                            :placeholder="$t('customer_service_block.select_address')" aria-label="Address input" />
                        <select v-model="new_address_id" :disabled="loadingPerson"
                            class="h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:border-slate-500 focus:outline-none"
                            id="contact_address">
                            <option value="" selected="selected">--{{ $t('customer_service_block.select_address') }}
                            </option>
                            <option v-for="address in person_addresses" :value="address.value" :key="address.value">
                                {{ address.label }}
                            </option>
                        </select>
                    </div>
                </section>

                <section class="rounded-xl border border-slate-200 bg-white/70 p-4 ">
                    <div class="mb-3 flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">
                                {{ $t('common.tlf') }}
                            </p>
                            <p class="text-sm text-slate-500">
                                {{ $t('common.select') }} {{ $t('common.or') }} {{ $t('common.tlf').toLowerCase() }}
                            </p>
                        </div>
                        <Icon name="ph:phone-call-duotone" class="text-2xl text-slate-400" />
                    </div>
                    <div class="grid gap-3 text-slate-600 md:grid-cols-[minmax(0,1fr),240px]">
                        <input type="text" v-model="new_phone" class="input h-11 rounded-lg border-slate-300 text-sm"
                            :placeholder="$t('customer_service_block.select_phone')" aria-label="Phone input" />
                        <select v-model="new_phone_id" :disabled="loadingPerson"
                            class="h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:border-slate-500 focus:outline-none"
                            id="contact_phone">
                            <option value="" selected="selected">--{{ $t('customer_service_block.select_phone') }}
                            </option>
                            <option v-for="phone in person_phones" :value="phone.value" :key="phone.value">
                                {{ phone.label }}
                            </option>
                        </select>
                    </div>
                </section>

                <section class="rounded-xl border border-slate-200 bg-white/70 p-4 ">
                    <div class="mb-3 flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">
                                {{ $t('common.email_long') }}
                            </p>
                            <p class="text-sm text-slate-500">
                                {{ $t('common.select') }} {{ $t('common.or') }} {{ $t('common.email_long').toLowerCase()
                                }}
                            </p>
                        </div>
                        <Icon name="ph:envelope-duotone" class="text-2xl text-slate-400" />
                    </div>
                    <div class="grid gap-3 text-slate-600 md:grid-cols-[minmax(0,1fr),240px]">
                        <input type="text" v-model="new_email" class="input h-11 rounded-lg border-slate-300 text-sm"
                            :placeholder="$t('customer_service_block.select_email')" aria-label="Email input" />
                        <select v-model="new_email_id" :disabled="loadingPerson"
                            class="h-11 w-full rounded-lg border border-slate-300 bg-white px-3 text-sm text-slate-700 focus:border-slate-500 focus:outline-none"
                            id="contact_email">
                            <option value="" selected="selected">--{{ $t('customer_service_block.select_email') }}
                            </option>
                            <option v-for="email in person_emails" :value="email.value" :key="email.value">
                                {{ email.label }}
                            </option>
                        </select>
                    </div>
                </section>
                <section v-if="communication.invoices.length > 0" class="rounded-xl border border-slate-200 bg-white/70 p-4 ">
                    <div class="mb-3 flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold uppercase tracking-wide text-slate-400">
                                {{ $t('common.electronic_invoice') }}
                            </p>
                        </div>
                        <Icon name="fa6-solid:file-invoice" class="text-2xl text-slate-400" />
                    </div>
                    <div class="grid gap-3 text-slate-600 grid-cols-2">
                        <input type="text" v-model="new_accounting_office" class="input h-11 rounded-lg border-slate-300 text-sm"
                            :placeholder="$t('billing_block.short_accounting_office')" aria-label="Email input" />
                        <input type="text" v-model="new_managing_body" class="input h-11 rounded-lg border-slate-300 text-sm"
                            :placeholder="$t('billing_block.short_managing_body')" aria-label="Email input" />
                        <input type="text" v-model="new_processing_unit" class="input h-11 rounded-lg border-slate-300 text-sm"
                            :placeholder="$t('billing_block.short_processing_unit')" aria-label="Email input" />
                    </div>
                </section>
            </div>
        </div>
        <hr class="mb-2 col-span-3" />
        <div class="col-span-3 flex flex-row-reverse mt-4">
            <button @click="save" :disabled="saving" class="button-primary">
                <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'"
                    :class="saving ? 'animate-spin' : ''" />
                &nbsp; {{
                    saving ? $t('common.loading') : $t('common.save') }}
            </button>
        </div>
    </div>
</template>