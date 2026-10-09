import re

from coredata.models import City, Country, Province


def _tokenize(value: str, prefix: str = "") -> str:
    raw = (value or "").strip().upper()
    raw = re.sub(r"[^A-Z0-9]+", "_", raw)
    raw = re.sub(r"_+", "_", raw).strip("_")
    return f"{prefix}{raw}" if prefix else raw


def resolve_country(iso_code: str):
    iso = (iso_code or "").strip().upper()
    if not iso:
        return None
    country, _ = Country.objects.get_or_create(iso_code=iso)
    return country


def resolve_province(province_name: str, country=None):
    name = (province_name or "").strip()
    if not name:
        return None
    token = _tokenize(name)
    defaults = {"name": name}
    if country:
        defaults["country"] = country
    province, _ = Province.objects.get_or_create(token=token, defaults=defaults)
    if country and province.country_id is None:
        province.country = country
        province.save(update_fields=["country"])
    return province


def resolve_city(city_name: str, province=None):
    """
    Resolve City consistently by (name, province) when province is available.
    This avoids creating duplicate city rows from name-only lookups.
    """
    name = (city_name or "").strip()
    if not name:
        return None

    if province:
        qs = City.objects.filter(name=name, province=province)
        city = qs.first()
        if city:
            return city

        # Reuse an existing legacy row with same name and no province, then attach province.
        # Only reuse it if it has no postal codes tied to a *different* province: cities with
        # the same name in different provinces (e.g. "Cervera" in Lleida and Astúries) must
        # never be merged into a single row, or postal codes end up cross-linked between them.
        orphan = City.objects.filter(name=name, province__isnull=True).first()
        if orphan:
            has_foreign_postal_codes = orphan.postal_codes.exclude(
                province=province
            ).exclude(province__isnull=True).exists()
            if not has_foreign_postal_codes:
                orphan.province = province
                if not orphan.token:
                    orphan.token = _tokenize(name, prefix="CITY_")
                orphan.save(update_fields=["province", "token"])
                return orphan

        token = _tokenize(f"{name}_{province.token}", prefix="CITY_")
        city, _ = City.objects.get_or_create(
            token=token,
            defaults={"name": name, "province": province},
        )
        if city.province_id is None:
            city.province = province
            city.save(update_fields=["province"])
        return city

    # Last resort when province is unknown: don't create duplicates by token-less name loops.
    city = City.objects.filter(name=name).first()
    if city:
        return city
    token = _tokenize(name, prefix="CITY_")
    city, _ = City.objects.get_or_create(token=token, defaults={"name": name})
    return city

