
## LLISTAT PER CONSIDERAR
 - Translation config Added But other apps that makes notification need translation .
 - For reciving message form gmao need to run command "run_gmao_consumer.py" is a listner so it could be systemd process too.
 - The run_gmaoconsumer managment commend needs some type of health check to be able to restart it if it fails.
 - Have in account that now i18n is installed  , on reuquest header pass the Accepts-Language = ?? to recive errors massaged translated too.

## Added order status
    },
    {
        "model": "order.orderstatus",
        "pk": 7,
        "fields": {
            "created_at": "2024-11-20T09:37:56.949Z",
            "updated_at": "2024-11-20T09:38:08.577Z",
            "token": "-5",
            "name": "Enviada",
            "color": "pink",
            "position": 5,
            "is_default": false
        }
    },
    {
        "model": "order.orderstatus",
        "pk": 8,
        "fields": {
            "created_at": "2024-11-20T09:37:56.949Z",
            "updated_at": "2024-11-20T09:38:08.577Z",
            "token": "5",
            "name": "En Curs",
            "color": "blue",
            "position": 6,
            "is_default": false
        }
    }

## Added config project for order status token
        },
    {
        "model": "coredata.configproject",
        "pk": 182,
        "fields": {
            "created_at": "2025-01-27T13:51:11.717Z",
            "updated_at": "2025-01-28T08:46:33.381Z",
            "token": "sent_order_status_token",
            "name": "Token Of OrderStatus of Sent Order",
            "value": "-5",
            "file": null
        }
    },
    {
        "model": "coredata.configproject",
        "pk": 183,
        "fields": {
            "created_at": "2025-01-27T13:51:11.717Z",
            "updated_at": "2025-01-28T08:46:33.381Z",
            "token": "for_validate_order_status_token",
            "name": "Token Of OrderStatus of For Validate Order",
            "value": "2",
            "file": null
        }
    },
    {
        "model": "coredata.configproject",
        "pk": 184,
        "fields": {
            "created_at": "2025-01-27T13:51:11.717Z",
            "updated_at": "2025-01-28T08:46:33.381Z",
            "token": "gmao_integration_order_status_map",
            "name": "Json map of GMAO integration order status",
            "value": "{\"pending\":\"1\",\"in_progress\":\"5\",\"completed\":\"5\",\"finalized\":\"2\",\"cancelled\":\"-1\"}",
            "file": null
        }
    }
## Added order priorities
[
  {
    "id": "1",
    "created_at": "2025-12-19 08:30:36.051251+00",
    "updated_at": "2026-02-12 12:28:17.292405+00",
    "token": "4",
    "name": "Alta",
    "color": "red",
    "position": null,
    "is_default": false
  },
  {
    "id": "3",
    "created_at": "2025-12-19 08:30:48.020698+00",
    "updated_at": "2026-02-12 12:28:25.342321+00",
    "token": "2",
    "name": "Baixa",
    "color": "green",
    "position": null,
    "is_default": true
  },
  {
    "id": "2",
    "created_at": "2025-12-19 08:30:44.737091+00",
    "updated_at": "2026-02-12 12:28:27.216964+00",
    "token": "3",
    "name": "Mitjana",
    "color": "yellow",
    "position": null,
    "is_default": false
  }
]