from django.conf import settings
from rest_framework import serializers


class TranslatableFieldMixin:
    """
    Exposes a `{translations_field_name}` field as {lang: text} on the API
    (same contract as the previous JSONField), backed underneath by an `_i18n`
    related model with one row per (parent, language) reachable via
    `instance.translations`.
    """
    translations_field_name = 'name_translations'
    translation_attr = 'name'

    def get_fields(self):
        fields = super().get_fields()
        fields[self.translations_field_name] = serializers.DictField(
            child=serializers.CharField(allow_blank=True),
            required=False,
        )
        return fields

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation[self.translations_field_name] = {
            t.language: getattr(t, self.translation_attr)
            for t in instance.translations.all()
        }
        return representation

    def validate(self, attrs):
        attrs = super().validate(attrs)
        value = attrs.get(self.translations_field_name)
        if value is not None:
            if not isinstance(value, dict):
                raise serializers.ValidationError({self.translations_field_name: "ha de ser un objecte {idioma: text}"})
            valid_languages = {lang for lang, _ in settings.LANGUAGES}
            invalid = set(value.keys()) - valid_languages
            if invalid:
                raise serializers.ValidationError({self.translations_field_name: f"Idiomes no vàlids: {invalid}"})
            attrs[self.translations_field_name] = {k: v for k, v in value.items() if v}
        return attrs

    def _apply_translations(self, instance, translations):
        existing = {t.language: t for t in instance.translations.all()}
        for lang, text in translations.items():
            obj = existing.pop(lang, None)
            if obj:
                setattr(obj, self.translation_attr, text)
                obj.save(update_fields=[self.translation_attr])
            else:
                instance.translations.create(language=lang, **{self.translation_attr: text})
        for obj in existing.values():
            obj.delete()

    def create(self, validated_data):
        translations = validated_data.pop(self.translations_field_name, None)
        instance = super().create(validated_data)
        if translations is not None:
            self._apply_translations(instance, translations)
        return instance

    def update(self, instance, validated_data):
        translations = validated_data.pop(self.translations_field_name, None)
        instance = super().update(instance, validated_data)
        if translations is not None:
            self._apply_translations(instance, translations)
        return instance


class MultiTranslatableFieldMixin:
    """
    Generalization of `TranslatableFieldMixin` for models with more than one
    translatable field, each backed by its own `_i18n` related model reachable
    via a distinct `related_name`. Configure via `translatable_fields`, e.g.:

    translatable_fields = [
        {"field_name": "invoice_footer_text_translations", "attr": "invoice_footer_text", "related_name": "invoice_footer_text_translations"},
        {"field_name": "data_protection_law_text_translations", "attr": "data_protection_law_text", "related_name": "data_protection_law_text_translations"},
    ]

    Unlike `TranslatableFieldMixin`, the concrete serializer is expected to call
    `_apply_multi_translations()` explicitly from its own `create()`/`update()`
    when those are already overridden and don't call `super()` (as is the case
    for `CompanySerializer`).
    """
    translatable_fields = []

    def get_fields(self):
        fields = super().get_fields()
        for cfg in self.translatable_fields:
            # `JSONField`, not `DictField`: serializers that also accept a file
            # upload (e.g. CompanySerializer's logo) are posted as
            # multipart/form-data, where every field arrives as a plain string
            # — including this `{lang: text}` map, which the frontend
            # JSON-encodes before appending to FormData (there's no native way
            # to send a nested object as a multipart field). `DictField` always
            # ignores a flat multipart value in favour of `parse_html_dict()`
            # (which expects sub-keys like `field[es]`), silently producing an
            # empty dict; `JSONField.get_value()` detects HTML/multipart input
            # and correctly `json.loads()`s the string instead. For plain JSON
            # request bodies (already a real dict), it works unchanged too.
            fields[cfg['field_name']] = serializers.JSONField(required=False)
        return fields

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        for cfg in self.translatable_fields:
            manager = getattr(instance, cfg['related_name'])
            representation[cfg['field_name']] = {
                t.language: getattr(t, cfg['attr']) for t in manager.all()
            }
        return representation

    def validate(self, attrs):
        attrs = super().validate(attrs)
        valid_languages = {lang for lang, _ in settings.LANGUAGES}
        for cfg in self.translatable_fields:
            field_name = cfg['field_name']
            value = attrs.get(field_name)
            if value is not None:
                if not isinstance(value, dict):
                    raise serializers.ValidationError({field_name: "ha de ser un objecte {idioma: text}"})
                invalid = set(value.keys()) - valid_languages
                if invalid:
                    raise serializers.ValidationError({field_name: f"Idiomes no vàlids: {invalid}"})
                attrs[field_name] = {k: v for k, v in value.items() if v}
        return attrs

    def pop_multi_translations(self, validated_data):
        return {
            cfg['field_name']: validated_data.pop(cfg['field_name'], None)
            for cfg in self.translatable_fields
        }

    def _apply_multi_translations(self, instance, translations_by_field):
        for cfg in self.translatable_fields:
            translations = translations_by_field.get(cfg['field_name'])
            if translations is None:
                continue
            manager = getattr(instance, cfg['related_name'])
            existing = {t.language: t for t in manager.all()}
            for lang, text in translations.items():
                obj = existing.pop(lang, None)
                if obj:
                    setattr(obj, cfg['attr'], text)
                    obj.save(update_fields=[cfg['attr']])
                else:
                    manager.create(language=lang, **{cfg['attr']: text})
            for obj in existing.values():
                obj.delete()

    def create(self, validated_data):
        popped = self.pop_multi_translations(validated_data)
        instance = super().create(validated_data)
        self._apply_multi_translations(instance, popped)
        return instance

    def update(self, instance, validated_data):
        popped = self.pop_multi_translations(validated_data)
        instance = super().update(instance, validated_data)
        self._apply_multi_translations(instance, popped)
        return instance
