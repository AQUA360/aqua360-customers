"""Backend de PostgreSQL per a les proves.

Si la variable d'entorn TEST_SCHEMA_FILE apunta a un abocament SQL, la base de
test es restaura des d'aquest fitxer en comptes d'aplicar tot l'històric de
migracions. Sense la variable, el comportament és el de Django.
"""
