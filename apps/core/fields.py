import json

from encrypted_fields.fields import EncryptedTextField


class EncryptedJSONField(EncryptedTextField):
    """JSON field with Fernet encryption at rest.

    Stores JSON-serialized data encrypted via django-fernet-encrypted-fields.
    """

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        value = super().from_db_value(value, expression, connection)
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return value

    def get_prep_value(self, value):
        if value is None:
            return value
        return super().get_prep_value(json.dumps(value, ensure_ascii=False))

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return json.dumps(value, ensure_ascii=False) if value is not None else ''
