<script setup>
import { ref, onMounted } from 'vue';
import { add, format } from 'date-fns';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import BankReturnSetup from './BankReturnSetup.vue';

const { t } = useI18n()
const router = useRouter()
const toast = useToast();
const objectPermissions = ref(null);
const emit = defineEmits(['refresh']);
const { $PaymentApiService } = useNuxtApp();

const currentStep = ref(0);

const loading = ref(true);
const update_save = ref(false);
const docExists = ref(false);

const showRegion = ref(false);
const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
}

const clickFinalize = async () => {
  try {
    if (confirm(t("confirmation_text_block.confirm_exit"))) {
      router.push('/billing/invoice');
    }
  }
  catch (error) {
    console.error(error);
  }
}



onMounted(async () => {
  objectPermissions.value = await checkPermission($PaymentApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  loading.value = false;
});


const save = async () => {
  if (docExists.value) {
    if (!confirm(t("confirmation_text_block.confirm_save_existing_document"))) return;
  } else {
    if (!confirm(t("confirmation_text_block.confirm_apply"))) return;
  }

  update_save.value = !update_save.value;
} 
</script>

<template>
  <div class="text-base">


    <!-- Contingut del Pas Actual -->
    <div v-if="loading">
      <div class="border border-gray-300 rounded-b bg-white p-3">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else class="border border-gray-300 rounded-b p-3 bg-white">
      <div class="mb-6">
        <BankReturnSetup :save_data="update_save" @doc_exists="docExists" />
      </div>
      <hr />
      <!-- Botons de navegació -->
      <div class="flex justify-between mt-4">
        <div class="flex justify-end mt-4">
          <div class="flex gap-3">
            <button @click="clickFinalize" class="button-default">
              {{ $t('common.exit') }}
            </button>
            <button @click="save" class="button-secondary">
              {{ $t('common.save') }}
            </button>
          </div>
        </div>
      </div><!-- end contingut botons -->

    </div><!--end contingut pas actual -->

    <!-- Regió Dreta per l'edició/creació de ContractRequestEdit -->
    <div role="region" id="right_page"
      class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white w-1/2 z-20"
      :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion }">
      <div id="region_nav" class="mb-3 px-3">
        <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
          <Icon name="fa6-solid:angles-right" class="text-slate-500" />
        </button>
      </div>
      <div class="px-10">

      </div>
    </div>
  </div>
</template>