from django.contrib import admin
from .models import ConnectionRequest, Exploitation, ExploitationSite, Connection, Cluster, Route, RouteZone, SupplyPoint, Meter, ClusterNozzle, Property, Company, CompanyBank, SupplyCut, MeterManufacturer, MeterModel, ConnectionStatus, CompanyConfig, SupplyPointPlacement

@admin.register(Exploitation)
class ExploitationAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name',)

@admin.register(ExploitationSite)
class ExploitationSiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'url', 'position', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('token', 'name')

@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'exploitation')
    list_filter = ('created_at', 'updated_at', 'exploitation')
    search_fields = ('token',)

@admin.register(SupplyPointPlacement)
class SupplyPointPlacementAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(ConnectionRequest)
class ConnectionRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at')

@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ('id','token', 'created_at', 'updated_at', 'connection')
    list_filter = ('created_at', 'updated_at', 'connection')
    search_fields = ('token',)

@admin.register(SupplyPoint)
class SupplyPointAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'created_at', 'updated_at', 'cluster_nozzle', 'connection')
    list_filter = ('created_at', 'updated_at', 'connection')
    search_fields = ('token',)

@admin.register(Meter)
class MeterAdmin(admin.ModelAdmin):
    list_display = ('id', 'code', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('code',)

@admin.register(MeterManufacturer)
class MeterManufacturerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name',)

@admin.register(MeterModel)
class MeterModelAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'manufacturer', 'created_at')
    list_filter = ('created_at', 'manufacturer')
    search_fields = ('name', 'manufacturer')

@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'route_zone', 'created_at', 'updated_at')
    list_filter = ()
    search_fields = ('token',)

@admin.register(RouteZone)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'created_at', 'updated_at')
    list_filter = ()
    search_fields = ('token',)


@admin.register(ClusterNozzle)
class ClusterNozzleAdmin(admin.ModelAdmin):
    list_display = ('id',  'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('code',)

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    
@admin.register(CompanyBank)
class CompanyBankAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'company', 'bank', 'country', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(SupplyCut)
class SupplyCutAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'token', 'source', 'status',
        'date_start', 'date_end', 'exec_start', 'exec_end',
        'requires_review', 'cause_raw', 'state_raw',
        'created_at', 'updated_at',
    )
    list_filter = ('source', 'status', 'requires_review', 'created_at', 'updated_at')
    search_fields = ('token',)
    
@admin.register(ConnectionStatus)
class ConnectionStatusAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'name', 'color', 'position', 'is_default', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)

@admin.register(CompanyConfig)
class CompanyConfigAdmin(admin.ModelAdmin):
    list_display = ('id', 'token')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('token',)