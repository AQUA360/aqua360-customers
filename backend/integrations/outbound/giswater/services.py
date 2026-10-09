from .client import GiswaterClient


def fetch_connecs():
    client = GiswaterClient()
    return client.get_list(
        schema="ws",
        table_name="ve_connec",
    )

def fetch_mincut_causes():
    client = GiswaterClient()
    return client.get_list(
        schema="ws",
        table_name="om_typevalue",
        filter_fields={
            "typevalue": {
                "value": "mincut_cause",
                "filterSign": "="
            }
        }
    )

def fetch_mincut_states():
    client = GiswaterClient()
    return client.get_list(
        schema="ws",
        table_name="om_typevalue",
        filter_fields={
            "typevalue": {
                "value": "mincut_state",
                "filterSign": "="
            }
        }
    )

def fetch_om_mincuts():
    client = GiswaterClient()
    return client.get_mincuts( schema="ws" )
    
def fetch_om_mincut_connecs(mincut_id: int):
    client = GiswaterClient()
    return client.get_list(
        schema="ws",
        table_name="om_mincut_connec",
        filter_fields={
            "result_id": {
                "value": mincut_id,
                "filterSign": "="
            }
        }
    )