from sqlalchemy import JSON, TypeDecorator


class OrderedMetadataJSON(TypeDecorator):
    """Expose a mapping; store pairs because MySQL JSON objects reorder keys."""

    impl = JSON(none_as_null=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else list(value.items())

    def process_result_value(self, value, dialect):
        return None if value is None else dict(value)
