from django.urls import include, path
from rest_framework import routers

from documentmanager.views_export.generic_export_view import GenericExportView

from coredata.views.config_project_view import ConfigProjectViewSet
from coredata.views.deploy_info_view import DeployInfoView
from coredata.views.identification_type_view import IdentificationTypeViewSet
from coredata.views.person_contact_view import PersonContactViewSet
from coredata.views.person_piggy_bank_movement_view import PersonPiggyBankMovementViewSet
from coredata.views.person_piggy_bank_view import PersonPiggyBankViewSet
from coredata.views.person_view import PersonAddressViewSet, PersonViewSet, PersonByTokenViewSet
from coredata.views.address_view import AddressViewSet
from coredata.views.partial_address_view import PartialAddressViewSet
from coredata.views.street_view import StreetViewSet, StreetTypeViewSet
from coredata.views.city_view import CityViewSet, ProvinceCitiesViewSet
from coredata.views.province_view import ProvinceViewSet
from coredata.views.country_view import CountryViewSet
from coredata.views.cnae_view import CnaeViewSet
from coredata.views.bank_view import BankViewSet
from coredata.views.person_bank_view import PersonBankViewSet
from coredata.views.person_cnae_serializer import PersonCnaeViewSet
from coredata.views.street_number_view import StreetNumberViewSet
from coredata.views.person_deliquency_view import PersonDeliquencyViewSet
from coredata.views.person_observation_view import PersonObservationViewSet
from coredata.views.main_permission_view import MainPermissionViewSet
from coredata.views.call_register_view import CallRegisterViewSet
from coredata.views.return_reason_view import ReturnReasonViewSet

router = routers.DefaultRouter()
router.register(r'person', PersonViewSet)
router.register(r'address', AddressViewSet)
router.register(r'person-address', PersonAddressViewSet)
router.register(r'person-bank', PersonBankViewSet)
router.register(r'person-contact', PersonContactViewSet)
router.register(r'person-cnae', PersonCnaeViewSet)
router.register(r'person-deliquency', PersonDeliquencyViewSet)
router.register(r'person-observation', PersonObservationViewSet)
router.register(r'street', StreetViewSet)
router.register(r'street-type', StreetTypeViewSet)
router.register(r'street-number', StreetNumberViewSet)
router.register(r'city', CityViewSet)
router.register(r'province', ProvinceViewSet)
router.register(r'country', CountryViewSet)
router.register(r'config-project', ConfigProjectViewSet)
router.register(r'main-permission', MainPermissionViewSet)
router.register(r'cnae', CnaeViewSet)
router.register(r'bank', BankViewSet)
router.register(r'call-register', CallRegisterViewSet)
router.register(r'identification-type', IdentificationTypeViewSet)
router.register(r'return-reason', ReturnReasonViewSet)
router.register(r'person-piggy-bank', PersonPiggyBankViewSet)
router.register(r'person-piggy-bank-movement', PersonPiggyBankMovementViewSet)

urlpatterns = [
    # Han d'anar abans d'`include(router.urls)`: el router registra `<recurs>/<pk>/`
    # amb un patró de pk genèric que, si es col·loca abans, capturaria "export" com a pk.
    path('person/export/', GenericExportView.as_view(entity='person'), name='person-export'),
    path('street/export/', GenericExportView.as_view(entity='street'), name='street-export'),
    path('deploy-info/', DeployInfoView.as_view(), name='deploy-info'),
    path('', include(router.urls)),
    path('province/<int:id>/cities/', ProvinceCitiesViewSet.as_view({'get': 'list'}), name='province-cities'),
    path('person/token/<str:token>/', PersonByTokenViewSet.as_view({'get': 'retrieve'}), name='user-by-token'),
    path('partial-address/', PartialAddressViewSet.as_view(http_method_names=['post']), name='create-partial-address')
]