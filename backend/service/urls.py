from django.urls import include, path
from rest_framework import routers

from documentmanager.views_export.generic_export_view import GenericExportView

from service.views.company_config_email_view import CompanyConfigEmailViewSet
from service.views.company_type_view import CompanyTypeViewSet
from service.views.supply_point_view import (
    SupplyPointChangeAddressView, 
    SupplyPointDeactivateView,
    SupplyPointActivateView
)

from service.views.close_connection_request_view import CloseConnectionRequestViewSet
from service.views.supply_point_get_by_street_view import SupplyPointGetByStreetView

from service.views.company_view import CompanyViewSet
from service.views.company_bank_view import CompanyBankViewSet
from service.views.company_bank_routing_view import CompanyBankRoutingViewSet
from service.views.company_config_view import CompanyConfigViewSet
from service.views.exploitation_view import ExploitationViewSet
from service.views.exploitation_site_view import ExploitationSiteViewSet
from service.views.property_view import PropertyViewSet
from service.views.dma_view import DMAViewSet
from service.views.tank_view import TankViewSet
from service.views.connection_view import ConnectionViewSet
from service.views.connection_status_view import ConnectionStatusViewSet
from service.views.connection_type_view import ConnectionTypeViewSet
from service.views.connection_installation_type_view import ConnectionInstallationTypeViewSet
from service.views.connection_use_type_view import ConnectionUseTypeViewSet
from service.views.connection_valve_type_view import ConnectionValveTypeViewSet
from service.views.connection_material_view import ConnectionMaterialViewSet
from service.views.connection_diameter_view import ConnectionDiameterViewSet
from service.views.connection_observation_view import ConnectionObservationViewSet
from service.views.connection_request_view import ConnectionRequestViewSet
from service.views.connection_request_status_view import ConnectionRequestStatusViewSet
from service.views.connection_request_observation_view import ConnectionRequestObservationViewSet
from service.views.cluster_view import ClusterViewSet
from service.views.cluster_nozzle_view import ClusterNozzleViewSet
from service.views.cluster_observation_view import ClusterObservationViewSet
from service.views.supply_point_view import SupplyPointViewSet
from service.views.meter_view import MeterViewSet
from service.views.meter_manufacturer_view import MeterManufacturerViewSet
from service.views.meter_model_view import MeterModelViewSet
from service.views.supply_cut_view import SupplyCutViewSet
from service.views.supply_cut_observation_view import SupplyCutObservationViewSet
from service.views.supply_cut_status_view import SupplyCutStatusViewSet
from service.views.supply_cut_cause_view import SupplyCutCauseViewSet
from service.views.supply_point_status_view import SupplyPointStatusViewSet
from service.views.supply_point_type_view import SupplyPointTypeViewSet
from service.views.supply_point_source_view import SupplyPointSourceViewSet
from service.views.supply_point_supply_type_view import SupplyPointSupplyTypeViewSet
from service.views.supply_point_placement_view import SupplyPointPlacementViewSet
from service.views.supply_point_observation_view import SupplyPointObservationViewSet
from service.views.meter_status_view import MeterStatusViewSet
from service.views.meter_caliber_view import MeterCaliberViewSet
from service.views.cluster_status_view import ClusterStatusViewSet
from service.views.cluster_nozzle_status_view import ClusterNozzleStatusViewSet
from service.views.cluster_nozzle_type_view import ClusterNozzleTypeViewSet
from service.views.route_view import RouteViewSet
from service.views.route_zone_view import RouteZoneViewSet
from service.views.route_position_view import RoutePositionViewSet
from service.views.meter_export_view import MeterExportViewSet
from service.views.meter_lookup_view import MeterLookupViewSet
from service.views.connection_documentation_type_view import ConnectionDocumentationTypeViewSet
from service.views.cluster_documentation_type_view import ClusterDocumentationTypeViewSet

router = routers.DefaultRouter()
router.register(r'company', CompanyViewSet)
router.register(r'company-type', CompanyTypeViewSet)
router.register(r'company-bank', CompanyBankViewSet)
router.register(r'company-bank-routing', CompanyBankRoutingViewSet)
router.register(r'company-config', CompanyConfigViewSet)
router.register(r'company-config-email', CompanyConfigEmailViewSet)
router.register(r'exploitation', ExploitationViewSet)
router.register(r'exploitation-site', ExploitationSiteViewSet)

router.register(r'property', PropertyViewSet)
router.register(r'dma', DMAViewSet)
router.register(r'tank', TankViewSet)

router.register(r'connection', ConnectionViewSet)
router.register(r'connection-status', ConnectionStatusViewSet)
router.register(r'connection-type', ConnectionTypeViewSet)
router.register(r'connection-installation-type', ConnectionInstallationTypeViewSet)
router.register(r'connection-use-type', ConnectionUseTypeViewSet)
router.register(r'connection-valve-type', ConnectionValveTypeViewSet)
router.register(r'connection-material', ConnectionMaterialViewSet)
router.register(r'connection-diameter', ConnectionDiameterViewSet)
router.register(r'connection-observation', ConnectionObservationViewSet)
router.register(r'connection-documentation-type', ConnectionDocumentationTypeViewSet)
router.register(r'cluster-documentation-type', ClusterDocumentationTypeViewSet)

router.register(r'connection-request', ConnectionRequestViewSet)
router.register(r'connection-request-status', ConnectionRequestStatusViewSet)
router.register(r'connection-request-observation', ConnectionRequestObservationViewSet)

router.register(r'cluster', ClusterViewSet)
router.register(r'cluster-nozzle', ClusterNozzleViewSet, basename='clusternozzle')
router.register(r'cluster-observation', ClusterObservationViewSet)

router.register(r'supply-point', SupplyPointViewSet, basename='supplypoint')
router.register(r'meter', MeterViewSet)
router.register(r'meter-manufacturer', MeterManufacturerViewSet)
router.register(r'meter-model', MeterModelViewSet)

router.register(r'supply-cut', SupplyCutViewSet)
router.register(r'supply-cut-observation', SupplyCutObservationViewSet)
router.register(r'supply-cut-status', SupplyCutStatusViewSet)
router.register(r'supply-cut-cause', SupplyCutCauseViewSet)

router.register(r'supply-point-status', SupplyPointStatusViewSet)
router.register(r'supply-point-type', SupplyPointTypeViewSet)
router.register(r'supply-point-source', SupplyPointSourceViewSet)
router.register(r'supply-point-supply-type', SupplyPointSupplyTypeViewSet)
router.register(r'supply-point-placement', SupplyPointPlacementViewSet)
router.register(r'supply-point-observation', SupplyPointObservationViewSet)

router.register(r'meter-status', MeterStatusViewSet)
router.register(r'meter-caliber', MeterCaliberViewSet)

router.register(r'cluster-status', ClusterStatusViewSet)

router.register(r'cluster-nozzle-status', ClusterNozzleStatusViewSet)
router.register(r'cluster-nozzle-type', ClusterNozzleTypeViewSet)

router.register(r'route', RouteViewSet)
router.register(r'route-zone', RouteZoneViewSet)
router.register(r'route-position', RoutePositionViewSet)

urlpatterns = [
    # Rutes específiques abans del router (evita que `meter/<pk>/` capturi "lookup-by-codes")
    path(
        'meter/lookup-by-codes/csv/',
        MeterLookupViewSet.as_view({'post': 'lookup_by_codes_csv'}),
        name='meter-lookup-by-codes-csv',
    ),
    path(
        'meter/lookup-by-codes/',
        MeterLookupViewSet.as_view({'post': 'lookup_by_codes'}),
        name='meter-lookup-by-codes',
    ),
    path('meter/export/csv/', MeterExportViewSet.as_view({'get': 'export_csv'}), name='meter-csv-export'),
    # Han d'anar abans d'`include(router.urls)`: el router registra `<recurs>/<pk>/`
    # amb un patró de pk genèric que, si es col·loca abans, capturaria "export" com a pk.
    path('supply-point/export/', GenericExportView.as_view(entity='supply_point'), name='supply-point-export'),
    path('property/export/', GenericExportView.as_view(entity='property'), name='property-export'),
    path('meter/export/', GenericExportView.as_view(entity='meter'), name='meter-export'),
    path('cluster/export/', GenericExportView.as_view(entity='cluster'), name='cluster-export'),
    path('connection/export/', GenericExportView.as_view(entity='connection'), name='connection-export'),
    path('connection-request/export/', GenericExportView.as_view(entity='connection_request'), name='connection-request-export'),
    path('exploitation/export/', GenericExportView.as_view(entity='exploitation'), name='exploitation-export'),
    path('', include(router.urls)),
    path('supply-point/<int:id>/activate', SupplyPointActivateView.as_view(), name='supply-point-activate'),
    path('supply-point/<int:id>/deactivate', SupplyPointDeactivateView.as_view(), name='supply-point-deactivate'),
    path('supply-point/<int:id>/change-address', SupplyPointChangeAddressView.as_view(), name='supply-point-change-address'),
    path('supply-point/get-by-street', SupplyPointGetByStreetView.as_view(http_method_names=['post']), name='supply-point-get-by-street'),
    path('connection-request/close/<int:id>', CloseConnectionRequestViewSet.as_view(http_method_names=['put']), name='close-connection-request'),
]
