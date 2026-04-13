from __future__ import annotations

from datetime import date
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.base import BaseSchema


class ModuleStatsItemSchema(BaseSchema):
    key: str
    label: str
    total: int = Field(ge=0)


class ModuleStatsResponseSchema(BaseSchema):
    module: str
    label: str
    total: int = Field(ge=0)
    items: list[ModuleStatsItemSchema]


class DashboardMetricSchema(BaseSchema):
    key: str
    label: str
    value: float
    unit: str | None = None
    previous: float | None = None
    delta: float | None = None
    deltaPercent: float | None = None
    status: Literal["good", "warning", "bad", "neutral"] | None = None
    trend: Literal["up", "down", "flat"] | None = None


class DashboardSeriesPointSchema(BaseSchema):
    label: str
    value: float


class DashboardChartSeriesSchema(BaseSchema):
    key: str
    label: str
    points: list[DashboardSeriesPointSchema]


class DashboardChartSchema(BaseSchema):
    key: str
    title: str
    description: str | None = None
    type: Literal["line", "bar", "stacked-bar"]
    unit: str | None = None
    series: list[DashboardChartSeriesSchema]


class DashboardBreakdownItemSchema(BaseSchema):
    key: str
    label: str
    value: float
    unit: str | None = None
    caption: str | None = None


class DashboardBreakdownSchema(BaseSchema):
    key: str
    title: str
    description: str | None = None
    items: list[DashboardBreakdownItemSchema]


class DashboardSectionSchema(BaseSchema):
    key: str
    title: str
    description: str | None = None
    metrics: list[DashboardMetricSchema]
    charts: list[DashboardChartSchema]
    breakdowns: list[DashboardBreakdownSchema]


class DashboardAnalyticsResponseSchema(BaseSchema):
    generatedAt: datetime
    currency: str = ""
    scope: "DashboardOverviewScopeSchema"
    department_dashboard: "DashboardDepartmentDashboardSchema | None" = None
    executive_dashboard: "DashboardExecutiveDashboardSchema | None" = None


class DashboardTableItemSchema(BaseSchema):
    key: str
    label: str
    value: float
    unit: str | None = None
    caption: str | None = None


class DashboardTableSchema(BaseSchema):
    key: str
    title: str
    description: str | None = None
    items: list[DashboardTableItemSchema]


class DashboardAlertSchema(BaseSchema):
    key: str
    level: Literal["info", "warning", "critical"]
    title: str
    message: str
    value: float | None = None
    unit: str | None = None


class DashboardModuleSchema(BaseSchema):
    key: str
    title: str
    description: str | None = None
    kpis: list[DashboardMetricSchema]
    charts: list[DashboardChartSchema]
    tables: list[DashboardTableSchema]
    alerts: list[DashboardAlertSchema] = Field(default_factory=list)
    healthScore: float | None = None
    healthStatus: Literal["good", "warning", "bad", "neutral"] | None = None


class DashboardDepartmentDashboardSchema(BaseSchema):
    modules: list[DashboardModuleSchema] = Field(default_factory=list)


class DashboardOverviewScopeSchema(BaseSchema):
    departmentId: str | None = None
    departmentLabel: str
    departmentModuleKey: str | None = None
    departmentPath: list[str] = Field(default_factory=list)
    startDate: date | None = None
    endDate: date | None = None


class DashboardOverviewResponseSchema(BaseSchema):
    generatedAt: datetime
    currency: str
    scope: DashboardOverviewScopeSchema
    department_dashboard: DashboardDepartmentDashboardSchema | None = None
    executive_dashboard: "DashboardExecutiveDashboardSchema | None" = None


class DashboardExecutiveDashboardSchema(BaseSchema):
    kpis: list[DashboardMetricSchema] = Field(default_factory=list)
    charts: list[DashboardChartSchema] = Field(default_factory=list)
    tables: list[DashboardTableSchema] = Field(default_factory=list)
    alerts: list[DashboardAlertSchema] = Field(default_factory=list)
