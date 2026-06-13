from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, extract
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, date
from pathlib import Path
import tempfile
import logging

from app.database.connection import get_db
from app.database.models import PatientVisit, User
from app.services.tokens import get_current_user
from app.services.direct_ingestion import ingest_csv_directly

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class MetricOption(BaseModel):
    """Available metric for analytics queries"""
    field: str
    label: str
    type: str  # "categorical", "numeric", "date"
    aggregations: List[str]  # ["count", "sum", "avg", "min", "max"]


class AnalyticsQueryRequest(BaseModel):
    """Request for analytics data"""
    time_period: str  # "week", "month", "quarter", "ytd"
    primary_metric: str
    secondary_metric: Optional[str] = None
    start_date: Optional[str] = None  # ISO format
    end_date: Optional[str] = None


class AnalyticsDataPoint(BaseModel):
    """Single data point in analytics response"""
    label: str
    value: float
    count: int = 0
    secondary_label: Optional[str] = None


class AnalyticsResponse(BaseModel):
    """Analytics query response"""
    success: bool
    data: List[AnalyticsDataPoint]
    chart_type: str  # "bar", "line", "pie", "stacked_bar"
    primary_metric: str
    secondary_metric: Optional[str] = None
    time_period: str
    date_range: Dict[str, str]


@router.get("/metrics", response_model=List[MetricOption])
async def get_available_metrics(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of available metrics for analytics"""

    metrics = [
        # Demographics
        MetricOption(field="gender", label="Gender", type="categorical", aggregations=["count"]),
        MetricOption(field="ethnicity", label="Ethnicity", type="categorical", aggregations=["count"]),
        MetricOption(field="race", label="Race", type="categorical", aggregations=["count"]),
        MetricOption(field="state", label="State", type="categorical", aggregations=["count"]),

        # Visit Information
        MetricOption(field="visit_date", label="Visit Date", type="date", aggregations=["count"]),
        MetricOption(field="visit_type", label="Visit Type", type="categorical", aggregations=["count"]),
        MetricOption(field="new_patient", label="New Patient", type="categorical", aggregations=["count"]),
        MetricOption(field="claim_type", label="Claim Type", type="categorical", aggregations=["count"]),

        # Financial
        MetricOption(field="total_charges", label="Total Charges", type="numeric", aggregations=["sum", "avg", "count"]),
        MetricOption(field="total_payment_received", label="Total Payment Received", type="numeric", aggregations=["sum", "avg", "count"]),
        MetricOption(field="family_income", label="Family Income", type="numeric", aggregations=["avg", "count"]),
        MetricOption(field="family_size", label="Family Size", type="numeric", aggregations=["avg", "count"]),

        # Insurance/Payer
        MetricOption(field="payor_source", label="Payor Source", type="categorical", aggregations=["count"]),
        MetricOption(field="insurance_name", label="Insurance Name", type="categorical", aggregations=["count"]),

        # Flags
        MetricOption(field="uncompensated_visit", label="Uncompensated Visit", type="categorical", aggregations=["count"]),
        MetricOption(field="location_code", label="Location Code", type="categorical", aggregations=["count"]),

        # Clinical (ICD codes treated as categorical)
        MetricOption(field="icd_1", label="Primary Diagnosis (ICD-1)", type="categorical", aggregations=["count"]),

        # Special aggregations
        MetricOption(field="patient_id", label="Unique Patients", type="categorical", aggregations=["count_distinct"]),
        MetricOption(field="record_id", label="Total Visits", type="categorical", aggregations=["count"]),
    ]

    return metrics


def calculate_date_range(time_period: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Calculate start and end dates based on time period"""
    today = date.today()

    if start_date and end_date:
        return datetime.fromisoformat(start_date).date(), datetime.fromisoformat(end_date).date()

    if time_period == "week":
        start = today - timedelta(days=7)
        end = today
    elif time_period == "month":
        start = today - timedelta(days=30)
        end = today
    elif time_period == "quarter":
        start = today - timedelta(days=90)
        end = today
    elif time_period == "ytd":
        start = date(today.year, 1, 1)
        end = today
    elif time_period == "all":
        # All time: start from very old date (e.g., year 2000)
        start = date(2000, 1, 1)
        end = today
    else:
        # Default to last 30 days
        start = today - timedelta(days=30)
        end = today

    return start, end


def determine_chart_type(primary_metric: str, secondary_metric: Optional[str], primary_type: str, secondary_type: Optional[str]) -> str:
    """Determine the best chart type based on metric types"""

    if not secondary_metric:
        # Single metric
        if primary_type == "date":
            return "line"
        elif primary_type == "categorical":
            return "bar"
        elif primary_type == "numeric":
            return "line"
    else:
        # Two metrics
        if primary_type == "date" and secondary_type == "categorical":
            return "stacked_bar"
        elif primary_type == "categorical" and secondary_type == "categorical":
            return "stacked_bar"
        elif primary_type == "categorical" and secondary_type == "numeric":
            return "bar"
        else:
            return "stacked_bar"

    return "bar"


@router.post("/query", response_model=AnalyticsResponse)
async def query_analytics(
    query: AnalyticsQueryRequest,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Query analytics data with flexible aggregations"""

    try:
        # Get user and validate
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Calculate date range
        start_date, end_date = calculate_date_range(query.time_period, query.start_date, query.end_date)

        # Get metric types for chart type determination
        metrics_map = {m.field: m for m in await get_available_metrics(user_id, db)}
        primary_type = metrics_map.get(query.primary_metric, MetricOption(field="", label="", type="categorical", aggregations=[])).type
        secondary_type = metrics_map.get(query.secondary_metric, MetricOption(field="", label="", type="categorical", aggregations=[])).type if query.secondary_metric else None

        chart_type = determine_chart_type(query.primary_metric, query.secondary_metric, primary_type, secondary_type)

        # Build base query
        base_query = db.query(PatientVisit).filter(
            and_(
                PatientVisit.tenant_id == user.tenant_id,
                PatientVisit.visit_date >= start_date,
                PatientVisit.visit_date <= end_date
            )
        )

        data_points = []

        if not query.secondary_metric:
            # Single metric aggregation
            if query.primary_metric == "patient_id":
                # Count distinct patients
                count = base_query.distinct(PatientVisit.patient_id).count()
                data_points.append(AnalyticsDataPoint(
                    label="Unique Patients",
                    value=float(count),
                    count=count
                ))
            elif query.primary_metric == "record_id":
                # Count total visits
                count = base_query.count()
                data_points.append(AnalyticsDataPoint(
                    label="Total Visits",
                    value=float(count),
                    count=count
                ))
            elif query.primary_metric == "total_charges":
                # Sum and average of charges
                result = base_query.with_entities(
                    func.sum(PatientVisit.total_charges).label("total"),
                    func.count(PatientVisit.id).label("count")
                ).first()

                total = float(result.total) if result.total else 0.0
                count = result.count if result.count else 0

                data_points.append(AnalyticsDataPoint(
                    label="Total Charges",
                    value=total,
                    count=count
                ))
            elif query.primary_metric == "total_payment_received":
                # Sum of payments
                result = base_query.with_entities(
                    func.sum(PatientVisit.total_payment_received).label("total"),
                    func.count(PatientVisit.id).label("count")
                ).first()

                total = float(result.total) if result.total else 0.0
                count = result.count if result.count else 0

                data_points.append(AnalyticsDataPoint(
                    label="Total Payments",
                    value=total,
                    count=count
                ))
            elif query.primary_metric in ["gender", "ethnicity", "race", "visit_type", "payor_source", "claim_type", "uncompensated_visit", "location_code", "new_patient"]:
                # Categorical breakdown
                field_attr = getattr(PatientVisit, query.primary_metric)
                results = base_query.with_entities(
                    field_attr,
                    func.count(PatientVisit.id).label("count")
                ).filter(field_attr.isnot(None)).group_by(field_attr).all()

                for value, count in results:
                    data_points.append(AnalyticsDataPoint(
                        label=str(value) if value else "Unknown",
                        value=float(count),
                        count=count
                    ))
            elif query.primary_metric == "visit_date":
                # Group by date
                results = base_query.with_entities(
                    PatientVisit.visit_date,
                    func.count(PatientVisit.id).label("count")
                ).group_by(PatientVisit.visit_date).order_by(PatientVisit.visit_date).all()

                for visit_date, count in results:
                    data_points.append(AnalyticsDataPoint(
                        label=visit_date.isoformat() if visit_date else "Unknown",
                        value=float(count),
                        count=count
                    ))
        else:
            # Two metric aggregation (e.g., visits by gender and payor source)
            primary_attr = getattr(PatientVisit, query.primary_metric)
            secondary_attr = getattr(PatientVisit, query.secondary_metric)

            results = base_query.with_entities(
                primary_attr,
                secondary_attr,
                func.count(PatientVisit.id).label("count")
            ).filter(
                primary_attr.isnot(None),
                secondary_attr.isnot(None)
            ).group_by(primary_attr, secondary_attr).all()

            for primary_val, secondary_val, count in results:
                data_points.append(AnalyticsDataPoint(
                    label=str(primary_val) if primary_val else "Unknown",
                    value=float(count),
                    count=count,
                    secondary_label=str(secondary_val) if secondary_val else "Unknown"
                ))

        return AnalyticsResponse(
            success=True,
            data=data_points,
            chart_type=chart_type,
            primary_metric=query.primary_metric,
            secondary_metric=query.secondary_metric,
            time_period=query.time_period,
            date_range={
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        )

    except Exception as e:
        logger.error(f"Error querying analytics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_analytics_summary(
    time_period: str = "ytd",
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get high-level analytics summary for dashboard"""

    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Calculate date range based on time period
        start_date, end_date = calculate_date_range(time_period)
        current_year = date.today().year

        base_query = db.query(PatientVisit).filter(
            and_(
                PatientVisit.tenant_id == user.tenant_id,
                PatientVisit.visit_date >= start_date,
                PatientVisit.visit_date <= end_date
            )
        )

        # Total visits
        total_visits = base_query.count()

        # Unique patients
        unique_patients = base_query.distinct(PatientVisit.patient_id).count()

        # Total charges
        charges_result = base_query.with_entities(
            func.sum(PatientVisit.total_charges).label("total")
        ).first()
        total_charges = float(charges_result.total) if charges_result.total else 0.0

        # Total payments
        payments_result = base_query.with_entities(
            func.sum(PatientVisit.total_payment_received).label("total")
        ).first()
        total_payments = float(payments_result.total) if payments_result.total else 0.0

        # Uncompensated care count
        uncompensated_count = base_query.filter(PatientVisit.uncompensated_visit == "Y").count()

        return {
            "success": True,
            "summary": {
                "total_visits": total_visits,
                "unique_patients": unique_patients,
                "total_charges": total_charges,
                "total_payments": total_payments,
                "uncompensated_visits": uncompensated_count,
                "year": current_year
            }
        }

    except Exception as e:
        logger.error(f"Error fetching analytics summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fpl-distribution")
async def get_fpl_distribution(
    time_period: str = "ytd",
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get Federal Poverty Level distribution for charity care patients"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        start_date, end_date = calculate_date_range(time_period)

        # 2024 FPL thresholds (mainland 48 states)
        FPL_BASE = 15060  # For family of 1
        FPL_PER_PERSON = 5380  # Add this for each additional person

        base_query = db.query(PatientVisit).filter(
            and_(
                PatientVisit.tenant_id == user.tenant_id,
                PatientVisit.visit_date >= start_date,
                PatientVisit.visit_date <= end_date,
                PatientVisit.family_income.isnot(None)
            )
        )

        results = base_query.with_entities(
            PatientVisit.family_income
        ).all()

        # Income distribution buckets
        income_buckets = {
            "$0-$15K": 0,
            "$15K-$30K": 0,
            "$30K-$45K": 0,
            "$45K-$60K": 0,
            "$60K-$75K": 0,
            "$75K-$100K": 0,
            ">$100K": 0
        }

        for (income,) in results:
            income = float(income)

            if income <= 15000:
                income_buckets["$0-$15K"] += 1
            elif income <= 30000:
                income_buckets["$15K-$30K"] += 1
            elif income <= 45000:
                income_buckets["$30K-$45K"] += 1
            elif income <= 60000:
                income_buckets["$45K-$60K"] += 1
            elif income <= 75000:
                income_buckets["$60K-$75K"] += 1
            elif income <= 100000:
                income_buckets["$75K-$100K"] += 1
            else:
                income_buckets[">$100K"] += 1

        data = [{"label": k, "value": v} for k, v in income_buckets.items()]

        return {
            "success": True,
            "data": data,
            "total_patients": len(results)
        }

    except Exception as e:
        logger.error(f"Error fetching FPL distribution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/charity-tiers")
async def get_charity_tiers(
    time_period: str = "ytd",
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get charity care discount tiers distribution"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        start_date, end_date = calculate_date_range(time_period)

        base_query = db.query(PatientVisit).filter(
            and_(
                PatientVisit.tenant_id == user.tenant_id,
                PatientVisit.visit_date >= start_date,
                PatientVisit.visit_date <= end_date,
                PatientVisit.total_charges.isnot(None),
                PatientVisit.total_payment_received.isnot(None)
            )
        )

        results = base_query.with_entities(
            PatientVisit.total_charges,
            PatientVisit.total_payment_received
        ).all()

        # Calculate discount tiers
        tiers = {
            "100% Discount (Free Care)": 0,
            "75-99% Discount": 0,
            "50-74% Discount": 0,
            "25-49% Discount": 0,
            "1-24% Discount": 0,
            "No Discount": 0
        }

        for charges, payment in results:
            charges = float(charges)
            payment = float(payment) if payment else 0

            if charges > 0:
                discount_pct = ((charges - payment) / charges) * 100

                if discount_pct >= 100:
                    tiers["100% Discount (Free Care)"] += 1
                elif discount_pct >= 75:
                    tiers["75-99% Discount"] += 1
                elif discount_pct >= 50:
                    tiers["50-74% Discount"] += 1
                elif discount_pct >= 25:
                    tiers["25-49% Discount"] += 1
                elif discount_pct >= 1:
                    tiers["1-24% Discount"] += 1
                else:
                    tiers["No Discount"] += 1

        data = [{"label": k, "value": v} for k, v in tiers.items() if v > 0]

        return {
            "success": True,
            "data": data,
            "total_patients": len(results)
        }

    except Exception as e:
        logger.error(f"Error fetching charity tiers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/yoy-comparison")
async def get_yoy_comparison(
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get year-over-year comparison of key metrics"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        today = date.today()
        current_year = today.year
        last_year = current_year - 1

        # Current year YTD
        current_ytd_start = date(current_year, 1, 1)
        current_ytd_end = today

        # Last year same period
        last_ytd_start = date(last_year, 1, 1)
        last_ytd_end = date(last_year, today.month, today.day)

        def get_metrics(start, end):
            base = db.query(PatientVisit).filter(
                and_(
                    PatientVisit.tenant_id == user.tenant_id,
                    PatientVisit.visit_date >= start,
                    PatientVisit.visit_date <= end
                )
            )

            total_visits = base.count()
            unique_patients = base.distinct(PatientVisit.patient_id).count()

            charges = base.with_entities(func.sum(PatientVisit.total_charges)).scalar()
            total_charges = float(charges) if charges else 0

            uncompensated = base.filter(PatientVisit.uncompensated_visit == "Y").count()

            return {
                "visits": total_visits,
                "patients": unique_patients,
                "charges": total_charges,
                "charity_care": uncompensated
            }

        current_metrics = get_metrics(current_ytd_start, current_ytd_end)
        last_year_metrics = get_metrics(last_ytd_start, last_ytd_end)

        return {
            "success": True,
            "current_year": current_year,
            "last_year": last_year,
            "current": current_metrics,
            "previous": last_year_metrics
        }

    except Exception as e:
        logger.error(f"Error fetching YoY comparison: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-diagnoses")
async def get_top_diagnoses(
    time_period: str = "ytd",
    limit: int = 10,
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get top diagnosis codes (ICD-10)"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        start_date, end_date = calculate_date_range(time_period)

        base_query = db.query(PatientVisit).filter(
            and_(
                PatientVisit.tenant_id == user.tenant_id,
                PatientVisit.visit_date >= start_date,
                PatientVisit.visit_date <= end_date,
                PatientVisit.icd_1.isnot(None)
            )
        )

        results = base_query.with_entities(
            PatientVisit.icd_1,
            func.count(PatientVisit.id).label("count")
        ).group_by(PatientVisit.icd_1).order_by(func.count(PatientVisit.id).desc()).limit(limit).all()

        data = [{"label": icd, "value": count} for icd, count in results]

        return {
            "success": True,
            "data": data,
            "total_diagnoses": len(results)
        }

    except Exception as e:
        logger.error(f"Error fetching top diagnoses: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payor-distribution")
async def get_payor_distribution(
    time_period: str = "ytd",
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get patient distribution by primary insurance/payor source"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        start_date, end_date = calculate_date_range(time_period)

        # Map payor codes to readable labels
        payor_labels = {
            "MC": "Medicaid",
            "MD": "Medicare",
            "PR": "Self-Pay",
            "UN": "Uninsured",
            "OT": "Commercial",
            "": "Unknown"
        }

        base_query = db.query(PatientVisit).filter(
            and_(
                PatientVisit.tenant_id == user.tenant_id,
                PatientVisit.visit_date >= start_date,
                PatientVisit.visit_date <= end_date
            )
        )

        results = base_query.with_entities(
            PatientVisit.payor_source,
            func.count(func.distinct(PatientVisit.patient_id)).label("count")
        ).group_by(PatientVisit.payor_source).order_by(func.count(func.distinct(PatientVisit.patient_id)).desc()).all()

        data = [
            {
                "label": payor_labels.get(payor or "", payor or "Unknown"),
                "value": count
            }
            for payor, count in results
        ]

        return {
            "success": True,
            "data": data,
            "total_patients": sum(item["value"] for item in data)
        }

    except Exception as e:
        logger.error(f"Error fetching payor distribution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/visit-trends")
async def get_visit_trends(
    time_period: str = "all",
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get monthly visit counts over time"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        start_date, end_date = calculate_date_range(time_period)

        results = db.query(
            extract('year', PatientVisit.visit_date).label('year'),
            extract('month', PatientVisit.visit_date).label('month'),
            func.count(PatientVisit.id).label('count')
        ).filter(
            and_(
                PatientVisit.tenant_id == user.tenant_id,
                PatientVisit.visit_date >= start_date,
                PatientVisit.visit_date <= end_date,
                PatientVisit.visit_date.isnot(None)
            )
        ).group_by('year', 'month').order_by('year', 'month').all()

        month_abbr = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

        data = [
            {"label": f"{month_abbr[int(month)]} {int(year)}", "value": count}
            for year, month, count in results
        ]

        return {"success": True, "data": data}

    except Exception as e:
        logger.error(f"Error fetching visit trends: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_for_analytics(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Direct CSV upload for analytics - bypasses validation
    Expects CSV with acme_health column format
    """
    try:
        # Get user to find tenant
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        logger.info(f"Direct analytics upload for user {user.email}, tenant {user.tenant_id}")

        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = Path(temp_file.name)

        # Ingest directly
        records_ingested = ingest_csv_directly(
            db=db,
            csv_path=temp_path,
            tenant_id=user.tenant_id
        )

        # Clean up temp file
        temp_path.unlink()

        logger.info(f"Direct ingestion complete: {records_ingested} records")

        return {
            "success": True,
            "records_ingested": records_ingested,
            "message": f"Successfully ingested {records_ingested} records into analytics database"
        }

    except Exception as e:
        logger.error(f"Error in direct analytics upload: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
