<script setup>
import { useI18n } from 'vue-i18n';
import FieldDetail from '~/components/atoms/FieldDetail.vue';
import LogoField from '~/components/atoms/LogoField.vue';

const { t } = useI18n();

const props = defineProps({
    id: Number, // ID de l'element
    data: Object
});

</script>

<template>
    <div>

        <div role="row" class="grid grid-cols-2 mt-2">
            <div>
                <LogoField :label='$t("common.name")' :name="data.name" :logo="data?.logo" />
            </div>
            <div :class="{ 'flex items-center': data?.logo }">
                <FieldDetail :class="{ 'flex items-center': data?.logo }" :label='$t("service_block.vat")' :value=data.vat>
                </FieldDetail>
            </div>
        </div>
        <div role="row" class="grid grid-cols-2">
            <FieldDetail :label='$t("service_block.alias")' :value=data.alias></FieldDetail>
            <FieldDetail :label='$t("common.regime")' :value="data.type? data.type.name : '-'"></FieldDetail>
        </div>
        <div role="row" class="grid grid-cols-2">
            <FieldDetail :label='$t("service_block.supply_code")' :value="data.supply_code || '-'"></FieldDetail>
        </div>
        <div role="row" class="grid grid-cols-2">
            <FieldDetail :label='$t("address_block.address")' :value=data.address_complete></FieldDetail>
            <FieldDetail :label='$t("address_block.locality")' :value='data.address?.postal_code + " " + data.address?.city?.name'>
            </FieldDetail>
        </div>
        <div role="row" class="grid grid-cols-2">
            <FieldDetail :label='$t("common.tlf")' :value=data.phone>
                <a :href="'tel:' + data.phone" class="text-sky-500 underline hover:no-underline">{{ data.phone }}</a>
            </FieldDetail>
            <FieldDetail :label='$t("common.tlf")+"(2)"' :value=data.phone_2>
                <a :href="'tel:' + data.phone_2" class="text-sky-500 underline hover:no-underline">{{ data.phone_2 }}</a>
            </FieldDetail>
        </div>
        <div role="row" class="grid grid-cols-2">
            <FieldDetail :label='$t("common.email")' :value=data.email>
                <a :href="'mailto:' + data.email" class="text-sky-500 underline hover:no-underline">{{ data.email }}</a>
            </FieldDetail>
        </div>

        <hr class="my-2" />

        <div role="row" class="grid grid-cols-2">
            <FieldDetail :label='$t("common.contact")' :value=data.contact_name></FieldDetail>
            <FieldDetail :label='$t("common.tlf")' :value=data.contact_phone>
                <a :href="'tel:' + data.contact_phone" class="text-sky-500 underline hover:no-underline">{{ data.contact_phone }}</a>
            </FieldDetail>
        </div>
        <div role="row" class="grid grid-cols-2">
            <FieldDetail :label='$t("common.email")' :value=data.contact_email>
                <a :href="'mailto:' + data.contact_email" class="text-sky-500 underline hover:no-underline">{{ data.contact_email }}</a></FieldDetail>
        </div>
        <hr class="my-2" />
        <!-- <div v-if="data?.company_banks?.length > 0">
            <details class="mb-5 mt-2 py-2 rounded-lg  text-sm">
                <summary class="cursor-pointer text-base border-b rounded border-slate-200 text-slate-400">{{ $t('Comptes bancaris') }}</summary>
                <div v-for="bank in data?.company_banks" :key="bank.id"
                    class="space-y-1 rounded-lg border border-slate-200 bg-sky-50 p-2 my-2">
                    <div role="row" class="">
                        <FieldDetail :label='$t("Banc")' :value="bank.bank?.name ? bank.bank?.name : bank.bank?.token">
                        </FieldDetail>
                        <FieldDetail :label='$t("IBAN")'>
                            <AtomsIBAN :value="bank.iban"></AtomsIBAN>
                        </FieldDetail>
                        <FieldDetail :label='$t("SWIFT")' :value="bank.swift"></FieldDetail>
                    </div>
                    <div role="row" class="grid grid-cols-2">
                        <FieldDetail :label='$t("Ident. SEPA")'
                            :value="bank.sepa_cred_identifier ? bank.sepa_cred_identifier : '-'"></FieldDetail>
                        <FieldDetail :label='$t("És SEPA?")' :value="bank.is_sepa ? 'Sí' : 'No'"></FieldDetail>
                    </div>
                </div>
            </details>
            
        </div> -->
    </div>
</template>
