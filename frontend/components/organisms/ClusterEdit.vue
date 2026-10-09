<script setup>
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import _ from 'lodash';
import { useToast } from 'vue-toastification';
import AppLoading from '~/components/atoms/AppLoading.vue';
import FastSupplyPointEdit from './FastSupplyPointEdit.vue';
import Draggable from 'vuedraggable';
import ButtonSeleccio from '~/components/atoms/ButtonSeleccio.vue';
import ClusterNozzleEdit from '~/components/organisms/ClusterNozzleEdit.vue';
import AddRoute from '~/components/molecules/AddRoute.vue';

const { t } = useI18n();
const route = useRoute();
const { $ClusterApiService, $ClusterNozzleApiService, $ConfiglistApiService, $ConnectionApiService, $AddressHelper, $SupplyPointApiService, $ConfigProjectApiService } = useNuxtApp();
const emits = defineEmits(['saved']);
const toast = useToast();

const props = defineProps({
  id: {
    type: String,
    default: null,
    required: false
  },
  connection: {
    type: Object,
    required: false,
  },
  allowNavigation: {
    type: Boolean,
    default: true
  }
});

const isLoading = ref(true);
const saving = ref(false);

const attemptedSave = ref(false);

const selected_nozzle = ref(null);
const cluster = ref(null);
const clusterToken = ref(null);
const clusterIsPotable = ref(true);
const clusterButlleti = ref('');
const clusterUsageDestination = ref('');
const clusterCadastral = ref('');
const clusterAddressExtra = ref('');

const showDefaultValues = ref(false);
const showOverflow = ref(false);
const defaultNozzleValues = ref({ position: 0 });

const clusterReportFile = ref(null);
const clusterReportFileUploaded = ref(null);
const clusterReportFileDelete = ref(false);

const connectionDiameters = ref([]);
const clusterNozzleStatus = ref([]);
const clusterNozzleTypes = ref([]);
const clusterNbNozzles = ref(1); // Default to 1 nozzle

const selected_positions = ref([])
const selected_connection = ref(null); // Default to 1 nozzle
const selected_route = ref(null)
const selected_route_token = ref(null)

const showRegion = ref(false);
const isSubRegionOpen = ref(false);
const editingConnection = ref(false);
const editingOptions = ref(false);
const editingRoute = ref(false);
const editingSupplyPoint = ref(false);
const viewingSupplyPoint = ref(false);
const viewingMeter = ref(false);
const viewingMeterId = ref(null);
const editingSupplyPointMode = ref('options');

const nozzlesBD = ref([]);
const nozzles = ref([]);
const supplyPointCutStatusToken = ref(null);

const useConnectionAddress = ref(true);
const address_data = ref({});
const addressFormRef = ref(null);

// Si s'ha escrit una adreça pròpia (no la de la connexió), es desa el carrer i el número
// abans de fer-los servir: així un carrer nou es crea en lloc de bloquejar el desat per no
// tenir id. L'endpoint busca abans de crear, de manera que no genera duplicats.
const ensureOwnAddressSaved = async () => {
  if (useConnectionAddress.value) return true;
  if (!addressFormRef.value) return false;
  const response = await addressFormRef.value.persistAddress();
  return !!response;
}
const addressEntity = ref({});


const type = ref(null);
const supply_type = ref(null);
const source = ref(null);
const placement = ref(null);

const types = ref([]);
const supply_types = ref([]);
const sources = ref([]);
const placements = ref([]);

const showDialog = ref(false);
const canClose = ref(false);

const groundFloor = ref(false);
const numberOfBetweenFloors = ref(0);
const numberOfFloors = ref(0);
const numberOfDoors = ref(0);

// The backend marks the supply point with the status set in
// 'supply_point_status_cut_token' when it has an active supply cut.
const loadSupplyPointCutStatusToken = async () => {
  try {
    supplyPointCutStatusToken.value = await $ConfigProjectApiService.get('supply_point_status_cut_token');
  } catch (err) {
    supplyPointCutStatusToken.value = null;
  }
}

const hasActiveCut = (nozzle) => {
  if (!supplyPointCutStatusToken.value) return false;
  return nozzle.supplyPoint?.status_token === supplyPointCutStatusToken.value;
}

const loadFromDetail = async (data) => {

  addressEntity.value = data;

  cluster.value = data;
  clusterToken.value = data.token;
  clusterIsPotable.value = data.is_potable;
  clusterButlleti.value = data.butlleti;
  clusterUsageDestination.value = data.usage_destination;
  clusterAddressExtra.value = data.address_extra || '';
  clusterNbNozzles.value = data.nb_nozzles;
  nozzlesBD.value = [...data.nozzles];
  nozzles.value = [...data.nozzles];

  selected_connection.value = data.connection;
  clusterReportFileUploaded.value = data.report_file;

  if (data.address_street) {
    addressEntity.value = data;
    useConnectionAddress.value = false;
  }

  if (data.address_street && selected_connection.value && selected_connection.value.address_street && data.address_street.id == selected_connection.value.address_street.id) {
    addressEntity.value = selected_connection.value;
    useConnectionAddress.value = true
  }

  if (selected_connection.value == null) {
    useConnectionAddress.value = false;
  }

  nozzles.value.forEach(nozzle => {
    if (nozzle.supply_points && nozzle.supply_points.length > 0) {
      const sp = nozzle.supply_points[0];
      nozzle.supplyPoint = sp;
    }
  });

  clusterNbNozzles.value = nozzles.value.length;

  isLoading.value = false;
}

const createEmpty = () => {
  cluster.value = null;
  clusterToken.value = _.random(500000, 999999);
  clusterIsPotable.value = true;
  clusterButlleti.value = null;
  clusterUsageDestination.value = null;
  clusterUsageDestination.value = null;
  clusterAddressExtra.value = null;
  clusterNbNozzles.value = 1;
  clusterCadastral.value = null;
  nozzlesBD.value = [
    {
      position: 1,
      diameter: selected_connection.value?.diameter?.name || cluster.value?.connection?.diameter?.name,
      status: clusterNozzleStatus.value[1]?.id,
      type: clusterNozzleTypes.value[0]?.id,
      supplyPoint: {
        address: {
          floor: null,
          door: null,
          stair: null,
          building: null,
        },
        type: types.value[0]?.code,
        supply_type: supply_types.value[0]?.code,
        source: sources.value[0]?.code,
        placement: placements.value[0]?.code,
        token: _.random(100000, 999999)
      }
    }
  ]
  nozzles.value = nozzlesBD.value;
  isLoading.value = false;
}

const handleUpdateAddressData = async (updatedValue) => {
  address_data.value = updatedValue;
};

const fetchConfigData = async (entity, targetArray) => {
  try {
    const data = await $ConfiglistApiService.getAll('service/' + entity);
    targetArray.value = data.results;
  } catch (error) {
    console.error(`Error fetching ${entity}:`, error);
  }
}



const getSelectData = async (entity, targetArray, targetValue) => {
  let data = await $ConfiglistApiService.getAll('service/' + entity);
  data.results?.forEach(item => {
    targetArray.value.push({
      code: item.id,
      label: item.name || item.token
    })
  });
  if (targetArray.value.length > 0) {
    targetValue.value = targetArray.value[0];
  }
}

const connectionClicked = (connection) => {
  if (connection != selected_connection.value) {
    selected_connection.value = connection;
    if (useConnectionAddress.value) {
      addressEntity.value = connection;
    }
  }
  else {
    selected_connection.value = null;
    if (useConnectionAddress.value) {
      addressEntity.value = {};
    }
  }
  setTimeout(() => {
    closeAllRegions();
  }, 200)
}

const handleUpdateNozzle = (nozzle) => {
  nozzles.value.forEach((n, index) => {
    if (n.position === nozzle.position) {
      const updatedNozzle = { ...n };

      if (nozzle.field === "diameter") {
        updatedNozzle.diameter = nozzle.diameter;
      }
      else if (nozzle.field === "status") {
        updatedNozzle.status = { id: nozzle.status };
      }
      else if (nozzle.field === "type") {
        updatedNozzle.type = { id: nozzle.type };
      }
      else if (nozzle.field === "nozzle-col") {
        updatedNozzle.col = nozzle.col;
      }
      else if (nozzle.field === "nozzle-row") {
        updatedNozzle.row = nozzle.row;
      }
      else if (nozzle.field === "destination") {
        updatedNozzle.destination = nozzle.destination;
        updatedNozzle.destinationObject = nozzle.destinationObject;
        if (!updatedNozzle.supplyPoint) {
          updatedNozzle.supplyPoint = {};
        }
        updatedNozzle.supplyPoint = {
          ...updatedNozzle.supplyPoint,
          address: {
            ...(updatedNozzle.supplyPoint?.address || {}),
            ...nozzle.destinationObject
          }
        };
      }

      nozzles.value.splice(index, 1, updatedNozzle);
    }
  });
};

const handleUpdateDefaults = (defaults) => {
  
  defaultNozzleValues.value = {
    ...defaultNozzleValues.value,
    position: 0,
    field: defaults.field
  };

  if (defaults.field === "diameter") {
    defaultNozzleValues.value.diameter = defaults.diameter;
  }
  else if (defaults.field === "status") {
    defaultNozzleValues.value.status = { id: defaults.status };
  }
  else if (defaults.field === "type") {
    defaultNozzleValues.value.type = { id: defaults.type };
  }
  else if (defaults.field === "nozzle-col") {
    defaultNozzleValues.value.col = defaults.col;
  }
  else if (defaults.field === "nozzle-row") {
    defaultNozzleValues.value.row = defaults.row;
  }
  else if (defaults.field === "destination") {
    defaultNozzleValues.value.destination = defaults.destination;
    defaultNozzleValues.value.destinationObject = defaults.destinationObject;
    defaultNozzleValues.value.supplyPoint = {
      ...defaultNozzleValues.value.supplyPoint,
      address: {
        ...(defaultNozzleValues.value.supplyPoint?.address || {}),
        ...Object.fromEntries(
          Object.entries(defaults.destinationObject || {}).filter(([_, value]) => value !== '')
        )
      }
    };
  }

  nozzles.value = nozzles.value.map(n => {
    const updatedNozzle = { ...n };
    
    if (defaults.field === "diameter") {
      updatedNozzle.diameter = defaults.diameter;
    }
    else if (defaults.field === "status") {
      updatedNozzle.status = { id: defaults.status };
    }
    else if (defaults.field === "type") {
      updatedNozzle.type = { id: defaults.type };
    }
    else if (defaults.field === "nozzle-col") {
      updatedNozzle.col = defaults.col;
    }
    else if (defaults.field === "nozzle-row") {
      updatedNozzle.row = defaults.row;
    }
    else if (defaults.field === "destination") {
      updatedNozzle.supplyPoint = {
        ...(updatedNozzle.supplyPoint || {}),
        address: {
          ...(updatedNozzle.supplyPoint?.address || {}),
          ...Object.fromEntries(
            Object.entries(defaults.destinationObject || {}).filter(([_, value]) => value !== '')
          )
        }
      };

      updatedNozzle.destination = updateDestination(updatedNozzle.supplyPoint?.address);
    }
    
    return updatedNozzle;
  });
};

const updateDestination = (address) => {
  let strResponse = address.floor || "0";

  if (address.door) {
    strResponse += '-' + address.door;
  }
  if (address.stair) {
    strResponse += '-' + address.stair;
  }
  if (address.building) {
    strResponse += '-' + address.building;
  }

  return strResponse;
};

const updateSelected = (e) => {
  if (e.entity == 'type') {
    type.value = e.id;
  }
  else if (e.entity == 'source') {
    source.value = e.id;
  }
  else if (e.entity == 'placement') {
    placement.value = e.id;
  }
  else if (e.entity == 'supply_type') {
    supply_type.value = e.id;
  }

  nozzles.value.forEach((n, index) => {
    const updatedNozzle = {
      ...n
    };
    updatedNozzle.supplyPoint ? true : updatedNozzle.supplyPoint = {}
    if (updatedNozzle.supplyPoint) {
      updatedNozzle.supplyPoint[e.entity] = e.id.code;
    }
    nozzles.value.splice(index, 1, updatedNozzle);
  });

}

const handleReportFileChange = (file) => {
  clusterReportFile.value = file;
};

const handleReportFileDelete = () => {
  clusterReportFileDelete.value = true;
};

const isValid = () => {
  if (!selected_connection.value || selected_connection.value.address_street_number == null) {
    return false
  }
  return true;
}

// Funció per guardar el cluster
const saveCluster = async () => {
  // Forcem el blur de l'input actiu perquè es propagui (@change) qualsevol valor
  // acabat d'escriure (p. ex. pis/porta) abans de llegir l'estat de les boquilles.
  if (document.activeElement instanceof HTMLElement) {
    document.activeElement.blur();
  }

  attemptedSave.value = true;
  if (!isValid()) {
    return;
  }

  saving.value = true;

  if (!(await ensureOwnAddressSaved())) {
    saving.value = false;
    return;
  }

  const data = {
    connection: props.connection ? props.connection.id : cluster.value?.connection?.id,
    token: clusterToken.value,
    is_potable: clusterIsPotable.value,
    butlleti: clusterButlleti.value,
    usage_destination: clusterUsageDestination.value,
    address_extra: clusterAddressExtra.value,
    nb_nozzles: nozzles.value.length,
    nozzles: nozzles.value,
    report_file: clusterReportFile.value,
    is_active: true,
  };

  if (clusterCadastral.value) {
    data.property_cadastral = clusterCadastral.value;
  }

  if (selected_route.value) {
    data.route = selected_route.value.id;
  }
  if (clusterReportFileDelete.value) {
    data.report_file_delete = true;
  }

  if (cluster.value && cluster.value.id) {
    data.id = cluster.value.id;
  }

  if (useConnectionAddress.value) {

    console.log(selected_connection.value)

    data.address_city_id = selected_connection.value?.address_city?.id;
    data.address_postal_code_id = selected_connection.value?.address_postal_code?.id;

    data.address_street_id = selected_connection.value?.address_street?.id;
    data.address_street_name = selected_connection.value?.address_street?.name;
    data.address_street_type_id = selected_connection.value?.address_street?.type?.id;
    data.address_street_type_abbreviation = selected_connection.value?.address_street?.type?.abbreviation;
    data.address_street_number_id = selected_connection.value?.address_street_number?.id;
    data.address_street_number_number = selected_connection.value?.address_street_number?.number;
    data.address_street_number_number_end = selected_connection.value?.address_street_number?.number_end;
    data.address_street_number_number_suffix = selected_connection.value?.address_street_number?.number_suffix;
    data.address_street_number_number_end_suffix = selected_connection.value?.address_street_number?.number_end_suffix;
    data.address_street_number_type = selected_connection.value?.address_street_number?.number_type?.type;

  }
  else if (address_data.value != null) {

    console.log(address_data.value)

    data.address_city_id = address_data.value?.city?.code;
    data.address_postal_code_id = address_data.value?.cp?.code;

    data.address_street_id = address_data.value?.streetId;
    data.address_street_name = address_data.value?.street_name;
    data.address_street_type_id = address_data.value?.street_type?.code;
    data.address_street_type_abbreviation = address_data.value?.street_type?.label;
    data.address_street_number_id = address_data.value?.streetNumberId;
    data.address_street_number_number = address_data.value?.streetNumberNumber;
    data.address_street_number_number_end = address_data.value?.streetNumberEnd;
    data.address_street_number_number_suffix = address_data.value?.streetNumberSuffix;
    data.address_street_number_number_end_suffix = address_data.value?.streetNumberEndSuffix;
    data.address_street_number_type = address_data.value?.streetNumberType;
  }

  data.connection = selected_connection.value?.id || null;

  console.log("data",data)

  // Validació de dades, que si no després és un merder fort
  if (data.address_street_id == null) {
    // retornem un toast de error
    toast.error(t('address_block.error_required_street'));
    saving.value = false;
    return;
  }
  if (data.address_city_id == null) {
    toast.error(t('address_block.error_required_municipality'));
    saving.value = false;
    return;
  }
  // if (data.address_postal_code_id == null) {
  //   toast.error(t('address_block.error_required_postal_code'));
  //   saving.value = false;
  //   return;
  // }
  if (data.address_street_name == null) {
    toast.error(t('address_block.error_required_street'));
    saving.value = false;
    return;
  }
  if (data.address_street_type_id == null) {
    toast.error(t('address_block.error_required_street_type'));
    saving.value = false;
    return;
  }

  try {
    const response = await $ClusterApiService.save(data);
    console.log("0. response cluster data", response)
    
    let street = response.address_street
    if (street) {
      delete street.type_abbreviation
      delete street.type_name
    }
    for (const nozzle of nozzles.value) {
      // mirem si existeix a nozzlesBD

      console.log("1. nozzle.value.map",nozzle, nozzle.position)
      const index = nozzlesBD.value.findIndex((n) => n.id == nozzle.id);
      console.log("2. index",index)
      const nozzleBD = nozzlesBD.value[index];

      if (nozzle.supply_poins && nozzle.supplyPoints.length > 0 && !nozzle.supplyPoint) {
        console.log("3. nozzle.supplyPoints",nozzle.supplyPoints)
        nozzle.supplyPoint = nozzle.supplyPoints[0];
      }

      if (!nozzle.supplyPoint) nozzle.supplyPoint = { address: {} }

      console.log("4. nozzle.destinationObject",nozzle.destinationObject)
      nozzle.supplyPoint.address = {
        building: nozzle.destinationObject?.building || nozzle.supplyPoint.address?.building,
        door: nozzle.destinationObject?.door || nozzle.supplyPoint.address?.door,
        stair: nozzle.destinationObject?.stair || nozzle.supplyPoint.address?.stair,
        floor: nozzle.destinationObject?.floor || nozzle.supplyPoint.address?.floor,
        address_extra: nozzle.destinationObject?.address_extra || nozzle.supplyPoint.address?.address_extra,
        street: {
          ...response.address_street,
          street_id: response.address_street?.id,
        },
        street_number: {
          ...response.address_street_number,
          street_number_id: response.address_street_number?.id,
        },
        city: response.address_city?.id,
        province: response.address_city?.province.id,
        country: response.address_city?.province.country.id,
        postal_code: response.address_postal_code?.code,
      }

      // Si la boquilla encara no té cap punt de subministrament vinculat, el creem
      // automàticament amb l'adreça de la bateria/boquilla que acabem de calcular.
      if (!nozzle.supplyPoint.id) {
        try {
          const spData = {
            connection_id: selected_connection.value?.id,
            token: _.random(100000, 999999).toString(),
            type: nozzle.supplyPoint.type || type.value?.code || (types.value.length > 0 ? types.value[0].code : null),
            source: nozzle.supplyPoint.source || source.value?.code || (sources.value.length > 0 ? sources.value[0].code : null),
            placement_id: nozzle.supplyPoint.placement || placement.value?.code || (placements.value.length > 0 ? placements.value[0].code : null),
            supply_type: nozzle.supplyPoint.supply_type || supply_type.value?.code || (supply_types.value.length > 0 ? supply_types.value[0].code : null),
            address_data: nozzle.supplyPoint.address,
            is_active: true,
          };
          nozzle.supplyPoint = await $SupplyPointApiService.save(spData);
        } catch (error) {
          console.error('Error creant automàticament el punt de subministrament de la boquilla', nozzle.position, error);
          toast.error(t('common.error_save'));
        }
      }

      if (nozzle.type?.id) nozzle.type = nozzle.type.id;
      if (nozzle.status?.id) {
        nozzle.status = nozzle.status.id;
      }
      else {
        nozzle.status = clusterNozzleStatus.value[0]?.id;
      }

      delete nozzle.supply_points;
      console.log("6. nozzle",nozzle)

      let data = {
        ...nozzle,
        cluster: response.id,
        token: clusterToken.value + '/' + nozzle.position,
        id: nozzleBD?.id
      }
      console.log("7. data",data)

      if (nozzle?.supplyPoint?.id) {
        data.supply_point_id = nozzle?.supplyPoint?.id;
      }
      delete data.supplyPoint;
      // si existeix, actualitzem, si no creem
      await $ClusterNozzleApiService.save(data);
    } // end for nozzles

    // Eliminem els nozzles (si sobren) després de restructurar (editar)
    if (nozzlesBD.value.length > nozzles.value.length) {
      console.log("8. nozzlesBD.value.length > nozzles.value.length",nozzlesBD.value.length, nozzles.value.length)
      for (let i = nozzles.value.length; i < nozzlesBD.value.length; i++) {
        $ClusterNozzleApiService.doDelete(nozzlesBD.value[i]);
      }

      // reduim l'array per igualar amb el nou nombre de nozzles
      nozzlesBD.value.splice(nozzles.value.length);
    }
    console.log("9. nozzlesBD.value",nozzlesBD.value)

    emits('saved', response);

    if (props.allowNavigation) {
      return navigateTo('/service/clusters/')
    }

  } catch (error) {
    console.error(error);
  } finally {
    saving.value = false;
  }
};

const onRouteSelected = async (item) => {
  selected_route.value = item;
  selected_route_token.value = item.token
  //emitChange();
  closeAllRegions();
};

const deleteCluster = async () => {
  if (confirm(t('Estàs segur que vols eliminar aquesta bateria?'))) {
    await $ClusterApiService.deleteCluster(props.id);
    return navigateTo('/service/clusters/')
  }
}

const openEditNozzle = (nozzle) => {
  closeAllRegions();
  selected_nozzle.value = nozzle;
  showRegion.value = true;
  editingOptions.value = true;
};

const openRegion = (region) => {
  closeAllRegions();

  if (region == 'connection') {
    editingConnection.value = true;
  }
  if (region == 'route') {
    editingRoute.value = true;
  }
  showRegion.value = true;
};

const toggleRegion = (force) => {
  showRegion.value = force !== undefined ? force : !showRegion.value;
  if (showRegion.value == false) {
    isSubRegionOpen.value = false;
  }
}

const closeAllRegions = () => {
  // tanquem tots els components
  editingConnection.value = false;
  editingOptions.value = false;
  editingRoute.value = false;
  editingSupplyPoint.value = false;
  viewingSupplyPoint.value = false;
  viewingMeter.value = false;
  // tanquem region
  showRegion.value = false;
};

const onAddSupplyPoint = (nozzle) => {
  closeAllRegions();
  selected_nozzle.value = nozzle;
  editingSupplyPointMode.value = 'options';
  editingSupplyPoint.value = true;
  showRegion.value = true;
};

// Obre la fitxa del punt de subministrament dins la mateixa pantalla, sense
// haver d'anar a una pestanya nova.
const onShowSupplyPointRegion = (nozzle) => {
  if (!nozzle?.supplyPoint?.id) return;
  closeAllRegions();
  selected_nozzle.value = nozzle;
  viewingSupplyPoint.value = true;
  showRegion.value = true;
};

// Fitxa del comptador del punt de subministrament, també dins la mateixa pantalla.
const onShowMeterRegion = (nozzle) => {
  const sp = nozzle?.supplyPoint;
  const meterId = sp?.meter_id || sp?.meter?.id || null;
  if (!meterId) return;
  closeAllRegions();
  selected_nozzle.value = nozzle;
  viewingMeterId.value = meterId;
  viewingMeter.value = true;
  showRegion.value = true;
};

const onEditSupplyPoint = (nozzle) => {
  closeAllRegions();
  selected_nozzle.value = nozzle;
  editingSupplyPointMode.value = 'options';
  editingSupplyPoint.value = true;
  showRegion.value = true;
};

const onSupplyPointSelected = async (supplyPoint) => {
  if (selected_nozzle.value) {
    // si el punt de subministrament ja estava vinculat a una altra posició, el desvinculem d'allà (localment)
    nozzles.value.forEach((n, i) => {
      if (n.position !== selected_nozzle.value.position && n.supplyPoint?.id === supplyPoint?.id) {
        nozzles.value.splice(i, 1, { ...n, supplyPoint: null });
      }
    });
    const index = nozzles.value.findIndex(n => n.position === selected_nozzle.value.position);
    if (index !== -1) {
      const updatedNozzle = { ...nozzles.value[index], supplyPoint };
      nozzles.value.splice(index, 1, updatedNozzle);

      // si la boquilla ja existeix a BD, guardem el vincle immediatament
      if (updatedNozzle.id) {
        try {
          await $ClusterNozzleApiService.save({
            id: updatedNozzle.id,
            cluster: cluster.value?.id,
            token: updatedNozzle.token,
            position: updatedNozzle.position,
            status: updatedNozzle.status?.id ?? updatedNozzle.status,
            type: updatedNozzle.type?.id ?? updatedNozzle.type,
            diameter: updatedNozzle.diameter,
            destination: updatedNozzle.destination,
            col: updatedNozzle.col,
            row: updatedNozzle.row,
            supply_point_id: supplyPoint.id,
          });
          toast.success(t('common.saved_successfully'));
        } catch (error) {
          console.error('Error vinculant el punt de subministrament:', error);
          toast.error(t('common.error_save'));
        }
      }
    }
  }
  closeAllRegions();
};

const onSupplyPointCreated = async (supplyPoint) => {
  if (selected_nozzle.value) {
    const index = nozzles.value.findIndex(n => n.position === selected_nozzle.value.position);
    if (index !== -1) {
      const updatedNozzle = { ...nozzles.value[index], supplyPoint };
      nozzles.value.splice(index, 1, updatedNozzle);

      // Si la boquilla ja existeix a BD, vinculem el punt de subministrament acabat de crear/editar immediatament
      if (updatedNozzle.id) {
        try {
          await $ClusterNozzleApiService.save({
            id: updatedNozzle.id,
            cluster: cluster.value?.id,
            token: updatedNozzle.token,
            position: updatedNozzle.position,
            status: updatedNozzle.status?.id ?? updatedNozzle.status,
            type: updatedNozzle.type?.id ?? updatedNozzle.type,
            diameter: updatedNozzle.diameter,
            destination: updateDestination(supplyPoint.address || {}),
            col: updatedNozzle.col,
            row: updatedNozzle.row,
            supply_point_id: supplyPoint.id,
          });
          toast.success(t('common.saved_successfully'));
        } catch (error) {
          console.error('Error vinculant el punt de subministrament amb la bateria:', error);
          toast.error(t('common.error_save'));
        }
      }
    }
  }
  closeAllRegions();
};

const unlinkSupplyPoint = () => {
  if (selected_nozzle.value) {
    const index = nozzles.value.findIndex(n => n.position === selected_nozzle.value.position);
    if (index !== -1) {
      const updatedNozzle = { ...nozzles.value[index], supplyPoint: null };
      nozzles.value.splice(index, 1, updatedNozzle);
    }
  }
  closeAllRegions();
};

const createNewLocalSupplyPoint = async () => {
  // Forcem el blur de l'input actiu perquè es propagui (@change) qualsevol valor
  // acabat d'escriure (p. ex. pis/porta) abans de llegir l'estat de la boquilla.
  if (document.activeElement instanceof HTMLElement) {
    document.activeElement.blur();
  }

  if (!selected_nozzle.value) return;

  const index = nozzles.value.findIndex(n => n.position === selected_nozzle.value.position);
  if (index === -1) return;

  const nozzle = nozzles.value[index];

  if (!(await ensureOwnAddressSaved())) return;

  // Construïm l'adreça a partir de la connexió o les dades introduïdes al formulari
  // Seguim el mateix format que FastSupplyPointEdit.vue / SupplyPointRegion.vue
  let address = null;
  if (useConnectionAddress.value && selected_connection.value) {
    const conn = selected_connection.value;

    if (!conn.address_street) {
      toast.error(t('address_block.error_required_street'));
      return;
    }

    address = {
      building: nozzle.destinationObject?.building || nozzle.supplyPoint?.address?.building || null,
      door: nozzle.destinationObject?.door || nozzle.supplyPoint?.address?.door || null,
      stair: nozzle.destinationObject?.stair || nozzle.supplyPoint?.address?.stair || null,
      floor: nozzle.destinationObject?.floor || nozzle.supplyPoint?.address?.floor || null,
      address_extra: nozzle.destinationObject?.address_extra || nozzle.supplyPoint?.address?.address_extra || null,
      street: {
        street_id: conn.address_street?.id,
        id: conn.address_street?.id,
        name: conn.address_street?.name,
        type_name: conn.address_street?.type?.name || '-',
        type_abbreviation: conn.address_street?.type?.abbreviation,
        type: conn.address_street?.type || null,
      },
      street_number: {
        street_number_id: conn.address_street_number?.id || null,
        id: conn.address_street_number?.id || null,
        number: conn.address_street_number?.number || null,
        number_end: conn.address_street_number?.number_end || null,
        number_suffix: conn.address_street_number?.number_suffix || null,
        number_end_suffix: conn.address_street_number?.number_end_suffix || null,
        number_type: conn.address_street_number?.number_type || null,
      },
      city: conn.address_city?.id,
      province: conn.address_city?.province?.id,
      country: conn.address_city?.province?.country?.id,
      postal_code: conn.address_postal_code?.code,
    };
  } else if (address_data.value && address_data.value.streetId) {
    
    address = {
      building: nozzle.destinationObject?.building || nozzle.supplyPoint?.address?.building || null,
      door: nozzle.destinationObject?.door || nozzle.supplyPoint?.address?.door || null,
      stair: nozzle.destinationObject?.stair || nozzle.supplyPoint?.address?.stair || null,
      floor: nozzle.destinationObject?.floor || nozzle.supplyPoint?.address?.floor || null,
      address_extra: nozzle.destinationObject?.address_extra || nozzle.supplyPoint?.address?.address_extra || null,
      street: {
        street_id: address_data.value.streetId,
        name: address_data.value.street_name,
        type_name: address_data.value.street_type?.label || '-',
        type_id: address_data.value.street_type?.code,
      },
      street_number: {
        street_number_id: address_data.value.streetNumberId || null,
        number: address_data.value.streetNumberNumber || null,
      },
      city: address_data.value.city?.code,
      province: address_data?.value?.province?.code || null,
      country: null,
      postal_code: address_data.value.cp?.code,
    };
  }

  if (!address) {
    toast.error(t('address_block.error_required_street'));
    return;
  }

  const spData = {
    connection_id: selected_connection.value?.id,
    token: _.random(100000, 999999).toString(),
    type: type.value?.code || (types.value.length > 0 ? types.value[0].code : null),
    source: source.value?.code || (sources.value.length > 0 ? sources.value[0].code : null),
    placement_id: placement.value?.code || (placements.value.length > 0 ? placements.value[0].code : null),
    supply_type: supply_type.value?.code || (supply_types.value.length > 0 ? supply_types.value[0].code : null),
    address_data: address,
    is_active: true,
  };

  try {
    const response = await $SupplyPointApiService.save(spData);
    const updatedNozzle = { ...nozzle, supplyPoint: response };
    nozzles.value.splice(index, 1, updatedNozzle);

    // Si la boquilla ja existeix a BD, vinculem el punt de subministrament acabat de crear immediatament
    if (updatedNozzle.id) {
      try {
        await $ClusterNozzleApiService.save({
          id: updatedNozzle.id,
          cluster: cluster.value?.id,
          token: updatedNozzle.token,
          position: updatedNozzle.position,
          status: updatedNozzle.status?.id ?? updatedNozzle.status,
          type: updatedNozzle.type?.id ?? updatedNozzle.type,
          diameter: updatedNozzle.diameter,
          destination: updateDestination(address),
          col: updatedNozzle.col,
          row: updatedNozzle.row,
          supply_point_id: response.id,
        });
      } catch (error) {
        console.error('Error vinculant el punt de subministrament amb la bateria:', error);
        toast.error(t('common.error_save'));
      }
    }

    toast.success(t('common.saved_successfully'));
  } catch (error) {
    console.error('Error creant el punt de subministrament:', error);
    toast.error(t('common.error_save'));
  }

  closeAllRegions();
};

const changeSupplyOptions = (options) => {
  let nozzle = nozzles.value.find(n => n.position == options.position);

  if (nozzle.supplyPoint == null) {
    nozzle.supplyPoint = {
      address: {
        floor: null,
        door: null,
        stair: null,
        building: null,
      },
      token: _.random(100000, 999999)
    }
  }

  nozzle.supplyPoint.type = options.type;
  nozzle.supplyPoint.supply_type = options.supply_type;
  nozzle.supplyPoint.source = options.source;
  nozzle.supplyPoint.placement = options.placement;
  closeAllRegions();
};

const getConnection = async (id) => {
  const connection = await $ConnectionApiService.getDetail(id);
  selected_connection.value = connection;
  useConnectionAddress.value = true;
  addressEntity.value = connection;

  nozzles.value.forEach((n, index) => {
    const updatedNozzle = {
      ...n,
      diameter: connection.diameter,
    };
    nozzles.value.splice(index, 1, updatedNozzle);
  });

  defaultNozzleValues.value = {
    ...defaultNozzleValues.value,
    diameter: connection.diameter?.name,
  };
}

onMounted(async () => {
  loadSupplyPointCutStatusToken();
  await fetchConfigData('cluster-nozzle-status', clusterNozzleStatus);
  await fetchConfigData('cluster-nozzle-type', clusterNozzleTypes);
  await fetchConfigData('connection-diameter', connectionDiameters);
  await getSelectData('supply-point-type', types, type);
  await getSelectData('supply-point-supply-type', supply_types, supply_type);
  await getSelectData('supply-point-source', sources, source);
  await getSelectData('supply-point-placement', placements, placement);
  // Si tenim un cluster, carreguem les dades
  if (route.query.connection) {
    await getConnection(route.query.connection)
  }
  if (props.connection) {
    await getConnection(props.connection.id)
  }
  if (props.id) {
    $ClusterApiService.getDetail(props.id).then((data) => {
      loadFromDetail(data);
    });
  } else {
    createEmpty();
  }
});

watch(showDialog, (val) => {
  if (!val) {
    canClose.value = false;
  }
});

watch(useConnectionAddress, (newVal) => {
  if (newVal) {
    addressEntity.value = selected_connection.value;
  }
  else {
    addressEntity.value = {};
  }
});

const onDraggableEnd = () => {
  nozzles.value.forEach((element, index) => {
    element.position = index + 1;
  });
}

const addNozzle = () => {
  clusterNbNozzles.value += 1;
}

const generateNozzles = () => {

  if ((numberOfFloors.value == 0 && !groundFloor.value && numberOfBetweenFloors.value == 0) || numberOfDoors.value == 0) {
    toast.warning(t('service_block.generate_nozzles_warning'));
    return;
  }

  let num = numberOfFloors.value * numberOfDoors.value;

  if (groundFloor.value) {
    num += numberOfDoors.value;
  }

  if (numberOfBetweenFloors.value) {
    num += numberOfBetweenFloors.value * numberOfDoors.value;
  }

  nozzles.value = [];
  if (groundFloor.value) {
    for (let i = 1; i <= numberOfDoors.value; i++) {
      newNozzle(t('address_block.low_floor'), i);
    }
  }

  if (numberOfBetweenFloors.value) {
    for (let i = 1; i <= numberOfBetweenFloors.value; i++) {
      for (let j = 1; j <= numberOfDoors.value; j++) {
        newNozzle(t('address_block.between_floor') + ' ' + i, j);
      }
    }
  }

  for (let i = 1; i <= numberOfFloors.value; i++) {
    for (let j = 1; j <= numberOfDoors.value; j++) {
      newNozzle(i, j);
    }
  }

  clusterNbNozzles.value = num;
  clickOutside();
}

const handleDeleteNozzle = (nozzle) => {
  nozzles.value = nozzles.value.filter(n => n.position != nozzle.position);
  onDraggableEnd();
}

const openDialog = () => {
  if (!showDialog.value) {
    canClose.value = false;
    showDialog.value = true;
    setTimeout(() => {
      canClose.value = true;
    }, 1)
  }
}

const clickOutside = () => {
  if (canClose.value) {
    showDialog.value = false;
    canClose.value = false;
  }
}

const newNozzle = (floor, door) => {
  nozzles.value.push({
    diameter: defaultNozzleValues.value?.diameter || selected_connection.value?.diameter?.name || cluster.value?.connection?.diameter?.name,
    status: defaultNozzleValues.value?.status || clusterNozzleStatus.value[1]?.id,
    type: defaultNozzleValues.value?.type || clusterNozzleTypes.value[0]?.id,
    destination: defaultNozzleValues.value?.destination || null,
    position: nozzles.value.length > 0 ? Math.max(...nozzles.value.map(n => n.position)) + 1 : 1,
    supplyPoint: {
      address: {
        floor: floor || defaultNozzleValues.value?.floor || null,
        door: door || defaultNozzleValues.value?.door || null,
        stair: defaultNozzleValues.value?.stair || null,
        building: defaultNozzleValues.value?.building || null,
      },
      type: defaultNozzleValues.value?.type || types.value[0]?.code,
      supply_type: defaultNozzleValues.value?.supply_type || supply_types.value[0]?.code,
      source: defaultNozzleValues.value?.source || sources.value[0]?.code,
      placement: defaultNozzleValues.value?.placement || placements.value[0]?.code,
      token: _.random(100000, 999999)
    }
  });
}

// Watch per actualitzar el nombre de components nozzles
watch(clusterNbNozzles, (newVal) => {

  let num = numberOfFloors.value * numberOfDoors.value;

  if (groundFloor.value) {
    num += numberOfDoors.value;
  }

  if (numberOfBetweenFloors.value) {
    num += numberOfBetweenFloors.value * numberOfDoors.value;
  }

  if (newVal != nozzles.value.length && newVal != num) {
    let diff = newVal - nozzles.value.length;
    if (diff > 0) {
      for (let i = 0; i < diff; i++) {
        newNozzle()
      }
    } else {
      nozzles.value.splice(diff, nozzles.value.length);
    }
  }
}, { immediate: true });


watch(() => props.id, (newVal) => {
  isLoading.value = true;
  if (newVal) {
    $ClusterApiService.getDetail(newVal).then((data) => {
      loadFromDetail(data);
    });
  } else {
    createEmpty()
  }
}, { immediate: true });

watch(() => showDefaultValues.value, (newVal) => {

  showOverflow.value = false;
  setTimeout(() => {
    if (newVal) {
      showOverflow.value = true;
    }
    else {
      showOverflow.value = false;
    }
  }, 300);

}, { immediate: true });

</script>

<template>
  <div class="relative">
    <div v-if="saving" class="absolute inset-0 bg-white bg-opacity-75 z-50 flex items-center justify-center">
      <AppLoading :text="t('common.saving')" />
    </div>

    <h2 class="text-xl font-semibold mb-4">{{ t('cluster') }}</h2>

    <div v-if="isLoading" class="">
      {{ $t('common.loading') + '...' }}
    </div>
    <div v-else class="form" :class="{ 'pointer-events-none': saving }">
      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label for="clusterToken" class="block text-sm font-medium text-gray-700">{{ t('common.identification') }}</label>
          <input v-model="clusterToken" type="text" id="clusterToken" name="clusterToken"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
        </div>
        <div class="mb-4">
          <label for="clusterIsPotable" class="block text-sm font-medium text-gray-700">{{ t('service_block.potable')
            }}:</label>
          <label class="flex items-center mt-2 ml-2 text-slate-700"><input v-model="clusterIsPotable" type="checkbox"
              id="clusterIsPotable" name="clusterIsPotable" />&nbsp;
            {{ t("service_block.is_potable") }}</label>
        </div>
      </div>

      <div class="row grid grid-cols-2 gap-3">

        <div class="mb-4">
          <label for="clusterReportFile" class="block text-sm font-medium text-gray-700">{{ t('service_block.bulletin') }}</label>
          <AtomsInputFile @update="handleReportFileChange" @delete="handleReportFileDelete" :name="'clusterReportFile'"
            :uploaded="clusterReportFileUploaded" />
        </div>

        <div class="mb-4">
          <label for="clusterUsageDestination" class="block text-sm font-medium text-gray-700">{{ t('service_block.usage_destination')
            }}</label>
          <input v-model="clusterUsageDestination" type="text" id="clusterUsageDestination"
            name="clusterUsageDestination"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
        </div>
      </div>

      <div class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <label for="clusterCadastral" class="block text-sm font-medium text-gray-700">{{ t('common.cadastral')
            }}</label>
          <input v-model="clusterCadastral" type="text" id="clusterCadastral" name="clusterCadastral"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
        </div>

        <div class="mb-4">
          <label for="clusterAddressExtra" class="block text-sm font-medium text-gray-700">{{ t('address_block.address_extra')
            }}</label>
          <input v-model="clusterAddressExtra" type="text" id="clusterAddressExtra" name="clusterAddressExtra"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm" />
        </div>
      </div>

      <div class="row grid grid-cols-2 gap-3">
        <div v-if="!selected_route" class="my-4">

          <ButtonSeleccio @click="openRegion('route')"
            class="block  w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
            <Icon name="fa-solid:plus" class="text-slate-500" />
            {{ $t('common.add') }} {{ $t('route') }}
          </ButtonSeleccio>
        </div>
        <div v-else class="mb-4">
          <label for="clusterRoute" class="block text-sm font-medium text-gray-700">{{ t('route')
            }}</label>
          <span id="clusterRoute" name="clusterRoute"
            class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm flex items-center justify-between group pr-7">
            <span class="text-gray-700">
              {{ selected_route_token }}
            </span>
            <button @click="openRegion('route')"
              class="flex items-center opacity-0 group-hover:opacity-100 focus:outline-none transition-opacity duration-200 ease-in-out">
              <Icon name="fa6-solid:pencil" class="text-slate-500 mr-1" />
            </button>
          </span>
        </div>
      </div>

      <div class="mb-2 col-span-2">
        <div class="field">
          <label for="connection" class="block text-sm font-medium text-slate-500 mb-2">
            {{ $t('connection') }}
          </label>
        </div>
        <div :class="{ 'mt-1': selected_connection == null }" class="text-gray-900 divide-y rounded shadow">
          <div v-if="selected_connection != null"
            class="group grid grid-cols-4 divide-x text-sm text-center leading-4 ">
            <span class="p-1 text-slate-400">
              {{ t('common.code') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('address_block.address') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('exploitation') }}
            </span>
            <span class="p-1 text-slate-400">
              {{ t('common.status') }}
            </span>
          </div>
          <div v-if="selected_connection != null"
            class="group grid grid-cols-4 divide-x text-sm text-center leading-4 ">
            <div class="p-2 text-slate-800">{{ selected_connection.token }}</div>
            <div class="p-2 text-slate-800">
              <span v-if="selected_connection.address_complete">
                {{ selected_connection.address_complete }}
              </span>
              <span v-else>
                {{ selected_connection.street }} {{ selected_connection.street_number &&
                  selected_connection.street.number != 'None' ? ', ' + selected_connection.street.number : '' }}
              </span>
            </div>
            <div class="p-2 text-slate-800">
              {{ selected_connection.exploitation?.name || selected_connection.exploitation?.token }}
            </div>
            <div class="p-2 text-slate-800 relative">
              <AtomsColorBadge :value="selected_connection.status?.name" :color="selected_connection.status?.color" />
              <button
                class="absolute cursor-pointer shadow-sm border text-sm w-6 h-6 bg-white right-1 top-1 rounded-md text-slate-600 hover:text-red-700 opacity-0 transition-all duration-300 focus:border-none focus:outline-none group-hover:opacity-100"
                @click="connectionClicked(selected_connection)">
                <Icon name="fa6-solid:trash" />
              </button>
            </div>
          </div>
          <div class="footering" v-if="selected_connection == null">
            <button @click="openRegion('connection')"
              class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300"
              :class="{'invalid': attemptedSave && address_data.streetId == null}">
              <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.assign') }} {{ $t('connection') }}
            </button>
          </div>
        </div>
      </div>

      <div>
        <hr class="mb-2" />
        <label class="flex items-center m-2 text-slate-700">
          <input :disabled="!selected_connection" v-model="useConnectionAddress" type="checkbox" id="clusterIsPotable"
            name="clusterIsPotable" />&nbsp;
          {{ t("service_block.use_connection_address") }}
          <div v-if="useConnectionAddress" class="ml-2 text-slate-600 rounded-md bg-slate-200 py-1 px-2">
            {{ $AddressHelper.getAddressString(selected_connection) }}
          </div>
        </label>

        <MoleculesAddPartialAddress v-if="!useConnectionAddress" ref="addressFormRef" :disable="useConnectionAddress"
          :data="addressEntity" :attempted_save="attemptedSave" @valueChanged="handleUpdateAddressData" />
      </div>
      <hr class="mb-2" />
      <!-- <div class="mb-4">
        <label for="clusterNbNozzles" class="block text-sm font-medium text-gray-700">{{ t('Num. Boquilles')
          }}:</label>
        <select v-model="clusterNbNozzles" id="clusterNbNozzles" name="clusterNbNozzles" :disabled="props.id != null"
          class="block w-full py-2 px-3 border border-gray-300 bg-white rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm">
          <option v-for="num in 50" :key="num" :value="num">{{ num }}</option>
        </select>
      </div> -->
      <div class="mb-2">
        <label for="clusterNbNozzles" class="text-lg font-semibold">{{ t('service_block.nozzles') }}:</label>
      </div>
      <div v-if="!props.id" class="row grid grid-cols-2 gap-3">
        <div class="mb-4">
          <button @click.stop="openDialog" class="button-default">
            <Icon name="fa6-solid:gears" class="mr-2" />
            {{ $t('common.configure') }} {{ $t('service_block.nozzles') }}
          </button>
        </div>
      </div>

      <div class="p-2 bg-slate-300 rounded-lg mb-2 transition-height duration-300"
        :class="{ 'max-h-9': !showDefaultValues, 'max-h-80': showDefaultValues, 'overflow-visible': showOverflow, 'overflow-hidden': !showOverflow }">
        <div class="flex mb-2">
          <button
            class="w-5 h-5 transition-all duration-300 ease-in-out mr-2 bg-slate-400 hover:bg-slate-500 rounded-full flex items-center justify-center text-white"
            @click="showDefaultValues = !showDefaultValues">
            <Icon name="fa6-solid:chevron-right"
              class="text-white transition-all duration-200 ease-in-out transform rotate-0"
              :class="{ 'rotate-90': showDefaultValues }" />
          </button>
          <label for="clusterNbNozzles" class="block text-sm font-medium text-gray-700">{{ t('default')
            }}</label>
        </div>
        <div> <!-- Default values zone -->
          <div class="heading grid grid-cols-[3fr,1fr,75px,75px,1fr,2fr] gap-2">
            <span class="text-slate-500 pl-1">{{t('service_block.usage_destination')}}</span>
            <span class="text-slate-500 pl-1">{{t('common.type')}}</span>
            <span class="text-slate-500 pl-1">{{t('editor_block.column')}}</span>
            <span class="text-slate-500 pl-1">{{t('editor_block.row')}}</span>
            <span class="text-slate-500 pl-1">{{t('service_block.diameter')}}</span>
            <span class="text-slate-500 pl-1">{{t('common.status')}}</span>
          </div>
          <ClusterNozzleEdit v-model:nozzle="defaultNozzleValues" :posicio="0" :statuses="clusterNozzleStatus"
            :types="clusterNozzleTypes" :diameters="connectionDiameters" @update:nozzle="handleUpdateDefaults"
            :defaultValues="true" />
          <div class="grid grid-cols-4  gap-2">
            <div class="mb-2">
              <div class="flex">
                <label for="type" class="block text-sm text-slate-500 my-1 ml-1">
                  {{ $t('supply_point') }}: {{ $t('common.type') }}</label>
              </div>
              <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="type"
                @update:modelValue="updateSelected({ entity: 'type', id: $event })" :options="types" />
            </div>
            <div class="mb-2">
              <div class="flex">
                <label for="source" class="block text-sm text-slate-500 my-1 ml-1">
                  {{ $t('service_block.supply_source') }}</label>
              </div>
              <v-select class="block w-full mr-2 required" :disabled="sources.length == 0" :model-value="source"
                @update:modelValue="updateSelected({ entity: 'source', id: $event })" :options="sources" />
            </div>
            <div class="mb-2">
              <div class="flex">
                <label for="supply_type" class="block text-sm text-slate-500 my-1 ml-1">
                  {{ $t('service_block.supply_type') }}</label>
              </div>
              <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="supply_type"
                @update:modelValue="updateSelected({ entity: 'supply_type', id: $event })" :options="supply_types" />
            </div>
            <div class="mb-2">
              <div class="flex">
                <label for="type" class="block text-sm text-slate-500 my-1 ml-1">
                  {{ $t('service_block.placement') }}</label>
              </div>
              <v-select class="block w-full mr-2 required" :disabled="types.length == 0" :model-value="placement"
                @update:modelValue="updateSelected({ entity: 'placement', id: $event })" :options="placements" />
            </div>
          </div>
        </div>
      </div>

      <div class="nozzle__list grid grid-cols-1 gap-1 mb-3">
        <div class="flex w-full">
          <div class="w-[30px]">
            <span class="text-slate-500 pl-0">{{t('common.short_position')}}</span>
          </div>
          <div class="heading grid grid-cols-[3fr,1fr,75px,75px,1fr,1fr,2fr] gap-2 w-full">
            <span class="text-slate-500 pl-1">{{t('service_block.usage_destination')}}</span>
            <span class="text-slate-500 pl-1">{{t('common.type')}}</span>
            <span class="text-slate-500 pl-1">{{t('editor_block.column')}}</span>
            <span class="text-slate-500 pl-1">{{t('editor_block.row')}}</span>
            <span class="text-slate-500 pl-1">{{t('service_block.diameter')}}</span>
            <span class="text-slate-500 pl-1">{{t('common.status')}}</span>
            <span class="text-slate-500 pl-1">{{t('supply_point')}}</span>
          </div>
        </div>

        <Draggable v-model="nozzles" itemKey="id" handle=".handle-move" class="dragArea"
          @end="onDraggableEnd" tag="div" :options="{ animation: 200 }">
          <template #item="{ element, index }">
            <div class="flex my-1 rounded" :class="{ 'bg-red-100': hasActiveCut(element) }">
              <div class="w-[50px] handle-move cursor-move pt-2">
                {{ element.position }}.
                <Icon v-if="hasActiveCut(element)" name="fa6-solid:droplet-slash" class="ml-1 text-red-600"
                  :title="t('service_block.active_supply_cut_warning')" />
              </div>
              <ClusterNozzleEdit :nozzle="element" :posicio="element.position" :statuses="clusterNozzleStatus"
              :types="clusterNozzleTypes" :diameters="connectionDiameters" @update:nozzle="handleUpdateNozzle"
              @open-edit="openEditNozzle" :showDelete="true" @delete="handleDeleteNozzle"
              @add-supply-point="onAddSupplyPoint" @edit-supply-point="onEditSupplyPoint"
              @show-supply-point-region="onShowSupplyPointRegion" @show-meter-region="onShowMeterRegion"/>
            </div>
          </template>
        </Draggable>

        <!-- <div v-for="(nozzle, index) in nozzles" :key="index">
          <ClusterNozzleEdit v-model:nozzle="nozzles[index]" :posicio="index + 1" :statuses="clusterNozzleStatus"
            :types="clusterNozzleTypes" :diameters="connectionDiameters" @update:nozzle="handleUpdateNozzle"
            @open-edit="openEditNozzle" />
        </div> -->
        <div>
          <button @click="addNozzle"
            class="display-block block w-full px-1 py-1 text-base text-slate-400 border-b hover:bg-slate-200 text-left active:bg-slate-300">
            <Icon name="fa6-solid:plus" class="text-slate-400" /> {{ $t('common.new_register') }}
          </button>
        </div>
      </div>

    </div>

    <hr class="mb-3" />

    <div class="col-span-3 flex flex-row-reverse mt-4">
      <button v-if="props.id != null" @click="deleteCluster" :disabled="saving" class="button-default mx-5">
        &nbsp; {{ $t('common.delete') }}
      </button>
      <button @click="saveCluster" :disabled="saving" class="button-primary">
        <Icon :name="saving ? 'fa6-solid:spinner' : 'fa6-solid:floppy-disk'" :class="{ 'animate-spin': saving }" />&nbsp; {{
          saving ? t('common.saving') : t('common.save') }}
      </button>
    </div>
  </div>
  
  <Transition
    enter-active-class="transition duration-300 ease-out"
    enter-from-class="transform scale-95 opacity-0"
    enter-to-class="transform scale-100 opacity-100"
    leave-active-class="transition duration-200 ease-in"
    leave-from-class="transform scale-100 opacity-100"
    leave-to-class="transform scale-95 opacity-0">
    <div v-if="showDialog" v-click-outside="clickOutside" class="w-1/4 h-50 bg-white z-50 fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 rounded-md shadow-md">
      <div class="flex justify-between items-center p-4">
        <h2 class="text-xl font-semibold">{{ $t('common.add') }} {{ $t('service_block.nozzles') }}</h2>
        <button @click="showDialog=false" class="hover:text-slate-700 p-2">
          <Icon name="fa6-solid:xmark" />
        </button>
      </div>
      <div class="p-4">
        <div class="grid grid-cols-2 gap-2 mb-4">
          <div class="flex flex-col gap-2">
            <div class="mb-4">
              <label for="groundFloor" class="text-sm text-slate-500">{{ t('address_block.low_floor_label') }}:</label>
              <label class="flex items-center mt-2 ml-2 text-slate-700"><input v-model="groundFloor" type="checkbox"
                  id="clusterIsPotable" name="clusterIsPotable" />&nbsp;
                {{ t("address_block.has_low_floor") }}</label>
            </div>
            <!-- <label for="groundFloor" class="text-sm text-slate-500">{{ $t('Planta baixa') }}</label>
            <input type="checkbox" v-model="groundFloor" class="input" /> -->
          </div>
          <div class="flex flex-col gap-2">
            <label for="numberOfBetweenFloors" class="text-sm text-slate-500">{{ $t('common.number') }} {{ $t('address_block.between_floors') }}</label>
            <input type="text" v-model="numberOfBetweenFloors" class="input" />
          </div>

          <div class="flex flex-col gap-2">
            <label for="numberOfFloors" class="text-sm text-slate-500">{{ $t('common.number') }} {{ $t('address_block.floors') }}</label>
            <input type="text" v-model="numberOfFloors" class="input" />
          </div>
          <div class="flex flex-col gap-2">
            <label for="numberOfDoors" class="text-sm text-slate-500">{{ $t('common.number') }} {{ $t('address_block.doors') }}</label>
            <input type="text" v-model="numberOfDoors" class="input" />
          </div>
        </div>
        <button class="button-primary" @click="generateNozzles">
          <Icon name="fa6-solid:plus" class="mr-2" />
          {{ $t('common.generate') }} {{ $t('service_block.nozzles') }}
        </button>
      </div>
    </div>
  </Transition>

  <div role="region" id="right_page"
    class="fixed h-full border-l border-gray-100 top-0 right-0 transition-all duration-500 ease py-2 text-base bg-white z-10"
    :class="{ 'translate-x-0': showRegion, 'translate-x-[2000px]': !showRegion, 'w-[95%]': isSubRegionOpen || !allowNavigation, 'w-1/2': !isSubRegionOpen && allowNavigation }">
    <div id="region_nav" class="mb-3 px-3">
      <button @click="toggleRegion(false)" class="px-2 py-1 text-sky-500 hover:bg-slate-200 active:bg-slate-300">
        <Icon name="fa6-solid:angles-right" class="text-slate-500" />
      </button>
    </div>
    <div class="px-10">
      <AddRoute v-if="editingRoute" :selected_items="[]" @item-clicked="onRouteSelected" />
      <MoleculesAddConnections v-if="editingConnection" :selected_items="[selected_connection]" @item-clicked="connectionClicked" :multiple="false" />
      <MoleculesSupplyPointOptions v-if="editingOptions" :nozzle="selected_nozzle" @save="changeSupplyOptions" />

      <!-- Fitxa del punt de subministrament -->
      <div v-if="viewingSupplyPoint && selected_nozzle?.supplyPoint?.id"
        class="overflow-y-auto pb-10" style="max-height: calc(100vh - 60px)">
        <OrganismsSupplyPointRegion :id="selected_nozzle.supplyPoint.id" :isSubRegion="true" />
      </div>

      <!-- Fitxa del comptador -->
      <div v-if="viewingMeter && viewingMeterId" class="overflow-y-auto pb-10" style="max-height: calc(100vh - 60px)">
        <OrganismsMeterRegion :id="viewingMeterId" :isSubRegion="true" />
      </div>

      <!-- Supply Point Management -->
      <div v-if="editingSupplyPoint">
        <!-- Back button if in sub-modes -->
        <div v-if="editingSupplyPointMode !== 'options'" class="mb-4">
          <button @click="editingSupplyPointMode = 'options'" class="flex items-center gap-1 text-sky-500 hover:text-sky-700">
            <Icon name="fa6-solid:arrow-left" class="w-4 h-4" />
            <span>{{ t('common.previous') }}</span>
          </button>
        </div>

        <!-- Options View -->
        <div v-if="editingSupplyPointMode === 'options'">
          <h2 class="text-xl font-semibold mb-4">
            {{ t('supply_point') }} - Boquilla {{ selected_nozzle?.position }}
          </h2>
          
          <div v-if="selected_nozzle?.supplyPoint?.id" class="mb-6 p-4 border border-slate-200 rounded-lg bg-slate-50">
            <h3 class="font-medium text-slate-700 mb-2">{{ t('common.assigned') }}:</h3>
            <div class="text-sm text-slate-600 mb-4">
              <p><strong>{{ t('common.identification') }}:</strong> {{ selected_nozzle.supplyPoint.token }}</p>
              <p v-if="selected_nozzle.supplyPoint.address_complete"><strong>{{ t('address_block.address') }}:</strong> {{ selected_nozzle.supplyPoint.address_complete }}</p>
            </div>
            
            <div class="flex flex-col gap-2">
              <button @click="editingSupplyPointMode = 'edit'" class="button-default flex items-center justify-center gap-2">
                <Icon name="fa6-solid:pencil" />
                <span>{{ t('common.edit') }}</span>
              </button>
              <button @click="unlinkSupplyPoint" class="button-default flex items-center justify-center gap-2 text-rose-600 border-rose-200 hover:bg-rose-50">
                <Icon name="fa6-solid:trash" />
                <span>{{ t('common.unlink') }}</span>
              </button>
            </div>
          </div>

          <div class="flex flex-col gap-3">
            <button @click="editingSupplyPointMode = 'assign'" class="button-primary flex items-center justify-center gap-2 w-full">
              <Icon name="fa6-solid:magnifying-glass" />
              <span>{{ t('common.select') }} {{ t('supply_point') }}</span>
            </button>
            <button @click="createNewLocalSupplyPoint" class="button-primary flex items-center justify-center gap-2 w-full">
              <Icon name="fa6-solid:plus" />
              <span>{{ t('common.new_register') }} {{ t('supply_point') }}</span>
            </button>
          </div>
        </div>

        <!-- Selection View -->
        <MoleculesAddSupplyPoints 
          v-if="editingSupplyPointMode === 'assign'" 
          :selected_items="selected_nozzle?.supplyPoint ? [selected_nozzle.supplyPoint] : []" 
          :multiple="false" 
          @item-clicked="onSupplyPointSelected" 
        />

        <!-- Edit View -->
        <FastSupplyPointEdit
          v-if="editingSupplyPointMode === 'edit'"
          :supply_point="selected_nozzle?.supplyPoint"
          :id="selected_nozzle?.supplyPoint?.id"
          :destination="selected_nozzle?.destinationObject || selected_nozzle?.supplyPoint?.address"
          @saved="onSupplyPointCreated"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.v-select>.vs__dropdown-menu {
  @apply z-10;
}
</style>
