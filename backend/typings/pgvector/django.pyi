from typing import Any
from django.db.models.fields import Field

class VectorField(Field):
    def __init__(self, dimensions: int, *args: Any, **kwargs: Any) -> None: ...
