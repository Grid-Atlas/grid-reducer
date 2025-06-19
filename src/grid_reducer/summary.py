from typing import Type
from pydantic import BaseModel
from abc import abstractmethod, ABC


class BaseSummaryModel(BaseModel, ABC):
    @abstractmethod
    def get_summary(self) -> dict[str, str]:
        pass


class SecondaryAssetSummaryItem(BaseModel):
    asset_type: Type[BaseModel]
    removed_count: int
    aggregated_count: int


class SecondaryAssetSummary(BaseSummaryModel):
    name: str
    items: list[SecondaryAssetSummaryItem]

    def get_summary(self) -> dict[str, str]:
        summary = {self.name: {}}
        for item in self.items:
            summary[self.name][
                item.asset_type.__name__
            ] = f"{item.removed_count} removed, aggregated to {item.aggregated_count} nodes."
        return summary


class PrimaryAssetSummaryItem(BaseModel):
    asset_type: Type[BaseModel]
    merged: int
    removed: int


class PrimaryAssetSummary(BaseSummaryModel):
    name: str
    items: list[PrimaryAssetSummaryItem]

    def get_summary(self) -> dict[str, str]:
        summary = {self.name: {}}
        for item in self.items:
            summary[self.name][
                item.asset_type.__name__
            ] = f"{item.merged} merged, {item.removed} removed."
        return summary
