from app.models.slaughter.slaughter_arrival import SlaughterArrival
from app.models.slaughter.slaughter_monthly_analytics import SlaughterMonthlyAnalytics
from app.models.slaughter.slaughter_processing import SlaughterProcessing
from app.models.slaughter.slaughter_quality_check import SlaughterQualityCheck
from app.models.slaughter.slaughter_semifinished import SlaughterSemiProduct
from app.models.slaughter.slaughter_shipment import SlaughterSemiProductShipment

__all__ = [
    "SlaughterArrival",
    "SlaughterMonthlyAnalytics",
    "SlaughterProcessing",
    "SlaughterQualityCheck",
    "SlaughterSemiProduct",
    "SlaughterSemiProductShipment",
]
