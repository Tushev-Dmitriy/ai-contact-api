"""Product metrics aggregate queries."""

from datetime import UTC, datetime, time

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.contact_request import (
    ContactRequest,
    EmailStatus,
    ProviderStatus,
)
from app.schemas.metrics import ContactMetrics


class MetricsRepository:
    """Read non-personal aggregate contact statistics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_contact_metrics(self) -> ContactMetrics:
        """Calculate required metrics with server-side aggregates."""
        today_start = datetime.combine(datetime.now(UTC).date(), time.min, UTC)
        total_requests = await self.session.scalar(
            select(func.count()).select_from(ContactRequest)
        )
        requests_today = await self.session.scalar(
            select(func.count())
            .select_from(ContactRequest)
            .where(ContactRequest.created_at >= today_start)
        )
        category_rows = (
            await self.session.execute(
                select(ContactRequest.category, func.count())
                .where(ContactRequest.category.is_not(None))
                .group_by(ContactRequest.category)
            )
        ).all()
        sentiment_rows = (
            await self.session.execute(
                select(ContactRequest.sentiment, func.count())
                .where(ContactRequest.sentiment.is_not(None))
                .group_by(ContactRequest.sentiment)
            )
        ).all()
        email_failures = await self.session.scalar(
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ContactRequest.owner_email_status == EmailStatus.FAILED,
                                1,
                            ),
                            else_=0,
                        )
                        + case(
                            (ContactRequest.user_email_status == EmailStatus.FAILED, 1),
                            else_=0,
                        )
                    ),
                    0,
                )
            )
        )
        ai_fallback_count = await self.session.scalar(
            select(func.count())
            .select_from(ContactRequest)
            .where(ContactRequest.ai_provider_status == ProviderStatus.UNAVAILABLE)
        )

        return ContactMetrics(
            total_requests=int(total_requests or 0),
            requests_today=int(requests_today or 0),
            categories={
                category.value: int(count)
                for category, count in category_rows
                if category is not None
            },
            sentiment={
                sentiment.value: int(count)
                for sentiment, count in sentiment_rows
                if sentiment is not None
            },
            email_failures=int(email_failures or 0),
            ai_fallback_count=int(ai_fallback_count or 0),
        )
