from typing import TypeVar, Type

from pydantic import BaseModel

T = TypeVar("T")


class CheckSimilarity:
    ignore_fields = None

    def check_if_similar(self, source: T, target: T) -> bool:
        class_type: Type[BaseModel] = type(source)
        for field in class_type.model_fields:
            if self.ignore_fields is not None and field in self.ignore_fields:
                continue
            source_val = getattr(source, field)
            target_val = getattr(target, field)
            if source_val != target_val:
                return False
        return True
