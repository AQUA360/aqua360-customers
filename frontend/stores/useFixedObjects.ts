import {defineStore} from 'pinia'

export const useFixedObjectsStore = defineStore('fixedObjects', {
  state: () => ({
    currentPinnedContractId: null as number | null,
    currentPinnedContract: null,
  }),
  actions: {
    setCurrentPinnedContractId(id: number) {
      this.currentPinnedContractId = id;
    },
    setCurrentPinnedContract(contract: any) {
      this.currentPinnedContract = contract;
    },
    clearCurrentPinnedContract() {
      this.currentPinnedContractId = null;
      this.currentPinnedContract = null;
    }
  }
});

