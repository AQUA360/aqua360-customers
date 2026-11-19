"""Webhooks de sortida: avisos POST a un sistema extern quan passen tràmits del Customers.

- dispatcher.py: desa l'avís a la bústia (WebhookEvent) dins la transacció de negoci.
- events.py: construeix les dades de cada avís i els punts on es criden.
- client.py: signa i fa el POST, i en deixa constància a IntegrationRequestLog.
- tasks.py: envia els pendents a poc a poc, amb reintents.
"""
