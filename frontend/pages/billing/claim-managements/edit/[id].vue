<script setup>
// path: pages/contract/contract-requests/edit/[id].vue
import { ref, onMounted } from 'vue';
import { checkPermission } from '~/middleware/permission';
import { useToast } from 'vue-toastification';
import H1 from '~/components/atoms/H1.vue';
import ContractRequestEdit from '~/components/organisms/ContractRequestEdit.vue';
import ClaimRequestManage from '~/components/organisms/ClaimRequestManage.vue';

const { t }= useI18n();
const route = useRoute()
const toast = useToast();
const { $ClaimRequestApiService } = useNuxtApp();

const id = ref(0);
const loading = ref(true);
const request = ref(null);

const downloading_document = ref(false)
const objectPermissions = ref(null);

const getData = async (showLoading = true) => {
  if (showLoading) {
    loading.value = true;
    request.value = null;
  }
  try {
    if (id.value) {
      const data = await $ClaimRequestApiService.getDetail(id.value);
      // Si ja tenim dades, actualitzem només el necessari
      if (request.value) {
        request.value = {
          ...request.value,
          ...data,
          // Mantenim les dades específiques que no volem que es sobreescriguin
          current_step: request.value.current_step
        };
      } else {
        request.value = data;
      }
    }
  } catch (error) {
    console.error('Error loading draft:', error);
  }
  if (showLoading) loading.value = false;
};

const downloadClaimLetters = async () => {
  downloading_document.value = true
  
  try {
    let response = await $ClaimRequestApiService.downloadClaimDocument(id.value);
    const blob = new Blob([response], { type: 'application/pdf' });

    const url = window.URL.createObjectURL(blob);
    //get todays date in string with the format YYYYMMDD without '-' or '_'
    
    const date = new Date();
    const today = date.getFullYear().toString() + 
                      String(date.getMonth() + 1).padStart(2, '0') + 
                      String(date.getDate()).padStart(2, '0');
    const a = document.createElement('a');
    a.href = url;
    a.download = `${request.value.step.document_type.token}${today}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error(err);
  } finally {
    downloading_document.value = false
  }
}

const downloadClaimExcel = async () => {
  downloading_document.value = true
  try {
    let response = await $ClaimRequestApiService.getClaimExcelFile(id.value);
    const utf8BOM = "\uFEFF";
    const csvData = utf8BOM + response;

    const blob = new Blob([csvData], { type: "text/csv;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;

    let filename = `${request.value.token}.csv`;
    a.download = filename;

    document.body.appendChild(a);
    a.click();

    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  } catch (err) {
    console.error(err);
  } finally {
    downloading_document.value = false
  }
};

onMounted(async () => {
  objectPermissions.value = await checkPermission($ClaimRequestApiService);
  if (!objectPermissions.value.can_change) {
    toast.error(t('common.no_permissions'));
    return navigateTo('/');
  }
  id.value = parseInt(route.params.id);
  getData();
});


</script>

<template>
  <div v-if="objectPermissions?.can_change" class="text-base px-4 max-w-full">
    <div class="flex justify-between items-center mb-3">
      <H1>{{ $t(`claim_block.claim_payments`) }}: {{ request?.token }}</H1>
    </div>
    <div v-if="loading">
      <div class="border border-gray-300 rounded-b p-4 bg-white">
        <div class="flex justify-center items-center">
          <Icon name="fa6-solid:spinner" class="animate-spin text-2xl text-slate-500" />
          <span class="ml-2">{{ $t('common.loading') }}...</span>
        </div>
      </div>
    </div>
    <div v-else>
      <ClaimRequestManage 
        :request="request" 
        @changed="(showLoading = true) => getData(showLoading)" 
        :downloading="downloading_document"
        @download-letter="downloadClaimLetters" 
        @download-excel="downloadClaimExcel"/>
    </div>
  </div>
</template>
