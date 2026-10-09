# Aqua360 - Programa d'Abonats (Customers)

## Requeriments
* Python 3.10.12 o 3.10.14
* Django 5.0.8

## Nou espai Ubuntu
* Instal·lar PostgreSQL: `sudo apt update` + `sudo apt install postgresql postgresql-contrib`
* Instal·lar Python3: `sudo add-apt-repository ppa:deadsnakes/ppa` + `sudo apt update` + `sudo apt install python3.10 python3.10-venv python3-pip python3-dev`
* Instal·lar build-essential: `sudo apt update` + `sudo apt install build-essential`

## Nou espai 
* Creem i editem les variables d'entorn: `$ cp .env.example .env` + editem
* Connectem al postgres i creem la base de dades que haguem definit, per exemple, `avsis_customers`
* Creem en entorn virtual python: `$ python3 -m venv env`
* Activar l'entorn virtual: `source env/bin/activate`
* Instal·lar les dependències `pip install -r requirements.ubuntu.txt`
* Migrar la base de dades `(env)$ python manage.py migrate` (Crearà les taules)
* Crear un superusuari: `(env)$ python manage.py createsuperuser`
* Carregar taules mestres inicials: `(env)$ python manage.py loaddata initial_data/ca/*.json`
* Comprovar que funciona: `(env)$ python3 manage.py runserver 0.0.0.0:8000`  i accedir a `/admin/`

## Dev
* `(env)$ python3 manage.py runserver `
* `(env)$ python3 manage.py runserver 0.0.0.0:8000`
* _(opcional test)_ `(env)$ python manage.py test --settings=customers.settings_test`

## Generar esquemes db
* Assegurar que `django_extensions` està instal·lat, hauria d'estar al requirements.in
* Instal·lar graphviz `sudo apt-get install graphviz`
* Generar .dot `python manage.py graph_models -o graph_models.dot`
* Si es vol generar el gràfic de només una app (service, coredata, billing...) generar el .dot de la seguent manera: `python manage.py graph_models {app_name} -o app_models.dot`
* Convertir a png `dot -Tpng models.dot -o models.png`
* Convertir a svg `dot -Tsvg models.dot -o models.svg`
* Convertir a pdf `dot -Tpdf models.dot -o models.pdf`

## Deploy

* Llençar `mina (ruby)` per servidors externs:
  * `$ mina [server] setup `
  * `$ mina [server] deploy `
* Per servidor propi, es pot mantenir el django obert amb un servei `gunicorn` i configurar nginx:
```
server {
    listen 81;
    server_name server_name;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        alias /var/www/customers/current/staticfiles/;
    }

    location /media/ {
        alias /var/www/customers/current/staticfiles/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/customers_base_backend.sock;
    }

    error_log /var/log/nginx/customers-backend-error.log;
    access_log /var/log/nginx/customers-backend-access.log;
}

```

* Consultar el repositori `aqua360-customers-deploy` per receptes d'`Ansible`.


# Documentació


# Django Export (dump) data

* Taules mestres:
```
python manage.py dumpdata coredata.ConfigProject > initial_data/ca/coredata.ConfigProject.json
python manage.py dumpdata coredata.StreetNumberType > initial_data/ca/coredata.StreetNumberType.json
python manage.py dumpdata coredata.CNAE > initial_data/ca/coredata.CNAE.json

python manage.py dumpdata service.SupplyPointStatus > initial_data/ca/service.SupplyPointStatus.json
python manage.py dumpdata service.SupplyPointType > initial_data/ca/service.SupplyPointType.json
python manage.py dumpdata service.SupplyPointPlacement > initial_data/ca/service.SupplyPointPlacement.json
python manage.py dumpdata service.SupplyPointSupplyType > initial_data/ca/service.SupplyPointSupplyType.json
python manage.py dumpdata service.SupplyPointSource > initial_data/ca/service.SupplyPointSource.json

python manage.py dumpdata service.MeterCaliber > initial_data/ca/service.MeterCaliber.json
python manage.py dumpdata service.MeterStatus > initial_data/ca/service.MeterStatus.json

python manage.py dumpdata service.ClusterStatus > initial_data/ca/service.ClusterStatus.json
python manage.py dumpdata service.ClusterNozzleType > initial_data/ca/service.ClusterNozzleType.json
python manage.py dumpdata service.ClusterNozzleStatus > initial_data/ca/service.ClusterNozzleStatus.json

python manage.py dumpdata service.ConnectionStatus > initial_data/ca/service.ConnectionStatus.json
python manage.py dumpdata service.ConnectionType > initial_data/ca/service.ConnectionType.json
python manage.py dumpdata service.ConnectionInstallationType > initial_data/ca/service.ConnectionInstallationType.json
python manage.py dumpdata service.ConnectionUseType > initial_data/ca/service.ConnectionUseType.json
python manage.py dumpdata service.ConnectionMaterial > initial_data/ca/service.ConnectionMaterial.json
python manage.py dumpdata service.ConnectionDiameter > initial_data/ca/service.ConnectionDiameter.json
python manage.py dumpdata service.ConnectionValveType > initial_data/ca/service.ConnectionValveType.json
python manage.py dumpdata service.ConnectionRequestStatus > initial_data/ca/service.ConnectionRequestStatus.json

python manage.py dumpdata service.SupplyCutStatus > initial_data/ca/service.SupplyCutStatus.json

python manage.py dumpdata billing.InvoiceTemplate > initial_data/ca/billing.InvoiceTemplate.json
python manage.py dumpdata billing.Message > initial_data/ca/billing.Message.json
```

* Staging fixtures:
```
python manage.py dumpdata coredata > coredata/fixtures/staging/coredata.json
python manage.py dumpdata service > service/fixtures/staging/service.json
python manage.py dumpdata contract > contract/fixtures/staging/contract.json
python manage.py dumpdata order > order/fixtures/staging/order.json
python manage.py dumpdata pricing > pricing/fixtures/staging/pricing.json
python manage.py dumpdata billing > billing/fixtures/staging/billing.json
python manage.py dumpdata coredata service contract order pricing billing fraud notification > importexport/fixtures/all_data.json
```


# Commands

* Imports inicials:
```
python3 manage.py import_exploitations prometeo/exploitation.csv
python3 manage.py import_connections prometeo/connections.csv
python3 manage.py import_clusters prometeo/clusters.csv
python3 manage.py import_supply_points prometeo/supply_points.csv
python3 manage.py import_meters prometeo/meters.csv
python3 manage.py import_cnae prometeo/cnae.csv
python3 manage.py import_banks prometeo/banks.csv
python3 manage.py import_persons prometeo/persons.csv
python3 manage.py import_person_banks prometeo/person_bank.csv
python3 manage.py import_person_contact prometeo/person_contact.csv
python3 manage.py import_contracts prometeo/contracts.csv
python3 manage.py import_contract_requests prometeo/contract_requests.csv
python3 manage.py import_contract_price_rates prometeo/contract_price_rates.csv
python3 manage.py import_bails prometeo/bails.csv
```

* Reset de la base de dades i incorporar DB de joc de proves:
```
prometeo/reset_db.sh
python3 manage.py test --settings=customers.settings_test
```

* Per el funcionament del processat de lectures i comprovació de variables expirades fa falta instalar redis i executar aquestes comandes:
```
sudo apt-get install redis-server 
sudo apt install python-celery-common
sudo service redis-server start
celery -A customers worker --loglevel=info
celery -A customers beat --loglevel=info
```

* Per la validació de signatures PDFs, instalar poppler-utils
```
sudo apt install poppler-utils
```
* test per staging action
