"""Repository layer for analytics and reporting database operations."""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy import select, func, text, case, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.common.models_db import (
    Call,
    Person,
    Task,
    Offer,
    Agent,
    DialogueTurn,
    CallSummary,
)


class AnalyticsRepository:
    """Repository for analytics data aggregation and reporting."""
    
    @staticmethod
    async def get_kpi_metrics(db: AsyncSession, days_back: int = 7) -> Dict:
        """Get key performance indicators for the dashboard."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        prev_cutoff_date = datetime.utcnow() - timedelta(days=days_back * 2)
        
        # Current period query
        current_query = select(
            func.count(Call.id).label('total_calls'),
            func.avg(Call.duration_sec).label('avg_duration_sec'),
            func.avg(Call.sentiment_score).label('avg_sentiment_score'),
            func.count(case((Call.resolution.isnot(None), 1))).label('resolved_calls'),
        ).where(Call.created_at >= cutoff_date)
        
        # Previous period query for comparison
        prev_query = select(
            func.count(Call.id).label('prev_total_calls'),
            func.avg(Call.duration_sec).label('prev_avg_duration_sec'),
            func.avg(Call.sentiment_score).label('prev_avg_sentiment_score'),
        ).where(
            and_(
                Call.created_at >= prev_cutoff_date,
                Call.created_at < cutoff_date
            )
        )
        
        # Execute queries
        current_result = await db.execute(current_query)
        prev_result = await db.execute(prev_query)
        
        current_row = current_result.fetchone()
        prev_row = prev_result.fetchone()
        
        # Calculate percentages and trends
        total_calls = current_row.total_calls or 0
        avg_duration_sec = current_row.avg_duration_sec or 0
        avg_sentiment_score = current_row.avg_sentiment_score or 0
        resolved_calls = current_row.resolved_calls or 0
        
        prev_total_calls = prev_row.prev_total_calls or 0
        prev_avg_duration_sec = prev_row.prev_avg_duration_sec or 0
        prev_avg_sentiment_score = prev_row.prev_avg_sentiment_score or 0
        
        # Calculate trends
        calls_trend = ((total_calls - prev_total_calls) / prev_total_calls * 100) if prev_total_calls > 0 else 0
        duration_trend = ((prev_avg_duration_sec - avg_duration_sec) / prev_avg_duration_sec * 100) if prev_avg_duration_sec > 0 else 0
        sentiment_trend = ((avg_sentiment_score - prev_avg_sentiment_score)) if prev_avg_sentiment_score else 0
        
        resolution_rate = (resolved_calls / total_calls * 100) if total_calls > 0 else 0
        
        return {
            'total_calls': total_calls,
            'avg_duration_sec': avg_duration_sec,
            'avg_sentiment_score': avg_sentiment_score,
            'resolution_rate': resolution_rate,
            'calls_trend': round(calls_trend, 1),
            'duration_trend': round(duration_trend, 1),
            'sentiment_trend': round(sentiment_trend, 1),
        }
    
    @staticmethod
    async def get_daily_call_volume(db: AsyncSession, days_back: int = 30) -> List[Dict]:
        """Get daily call volume trend data."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        query = select(
            func.date(Call.created_at).label('date'),
            func.count(Call.id).label('call_count')
        ).where(
            Call.created_at >= cutoff_date
        ).group_by(
            func.date(Call.created_at)
        ).order_by(
            func.date(Call.created_at)
        )
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        return [{'date': str(row.date), 'count': row.call_count} for row in rows]
    
    @staticmethod
    async def get_hourly_call_distribution(db: AsyncSession, days_back: int = 30) -> List[Dict]:
        """Get hourly call distribution (peak hours analysis)."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        query = select(
            func.extract('hour', Call.created_at).label('hour'),
            func.count(Call.id).label('call_count')
        ).where(
            Call.created_at >= cutoff_date
        ).group_by(
            func.extract('hour', Call.created_at)
        ).order_by(
            func.extract('hour', Call.created_at)
        )
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        return [{'hour': int(row.hour), 'count': row.call_count} for row in rows]
    
    @staticmethod
    async def get_sentiment_distribution(db: AsyncSession, days_back: int = 30) -> List[Dict]:
        """Get sentiment analysis distribution."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        query = select(
            Call.sentiment_label,
            func.count(Call.id).label('count')
        ).where(
            and_(
                Call.created_at >= cutoff_date,
                Call.sentiment_label.isnot(None)
            )
        ).group_by(
            Call.sentiment_label
        )
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        # Map sentiment labels to display names and colors
        sentiment_mapping = {
            'positive': {'label': 'Positive', 'color': '#059669'},
            'neutral': {'label': 'Neutral', 'color': '#d97706'},
            'negative': {'label': 'Negative', 'color': '#dc2626'}
        }
        
        return [
            {
                'label': sentiment_mapping.get(row.sentiment_label, {}).get('label', row.sentiment_label),
                'count': row.count,
                'color': sentiment_mapping.get(row.sentiment_label, {}).get('color', '#6b7280')
            }
            for row in rows if row.sentiment_label
        ]
    
    @staticmethod
    async def get_call_categories(db: AsyncSession, days_back: int = 30) -> List[Dict]:
        """Get call category/topic distribution."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        # For now, we'll categorize by sentiment as placeholder
        # In future, this could use intent classification or topic modeling
        query = select(
            Call.sentiment_label.label('category'),
            func.count(Call.id).label('count')
        ).where(
            and_(
                Call.created_at >= cutoff_date,
                Call.sentiment_label.isnot(None)
            )
        ).group_by(
            Call.sentiment_label
        )
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        category_mapping = {
            'positive': 'Product Inquiry',
            'neutral': 'General Inquiry', 
            'negative': 'Technical Support'
        }
        
        return [
            {
                'label': category_mapping.get(row.category, row.category),
                'count': row.count,
                'color': '#4f46e5' if row.category == 'positive' else '#8b5cf6' if row.category == 'negative' else '#3b82f6'
            }
            for row in rows if row.category
        ]
    
    @staticmethod
    async def get_resolution_time_buckets(db: AsyncSession, days_back: int = 30) -> List[Dict]:
        """Get call resolution time distribution buckets."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        # Define time buckets in seconds
        buckets = [
            ('< 2 min', 0, 120),
            ('2-5 min', 120, 300),
            ('5-10 min', 300, 600),
            ('10-15 min', 600, 900),
            ('> 15 min', 900, 999999)
        ]
        
        results = []
        for label, min_sec, max_sec in buckets:
            query = select(func.count(Call.id)).where(
                and_(
                    Call.created_at >= cutoff_date,
                    Call.duration_sec >= min_sec,
                    Call.duration_sec < max_sec
                )
            )
            result = await db.execute(query)
            count = result.scalar() or 0
            results.append({'label': label, 'count': count})
        
        return results
    
    @staticmethod
    async def get_top_performing_agents(db: AsyncSession, limit: int = 10, days_back: int = 30) -> List[Dict]:
        """Get top performing agents by call volume and resolution rate."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        query = select(
            Call.agent_id,
            func.count(Call.id).label('total_calls'),
            func.avg(Call.sentiment_score).label('avg_sentiment'),
            func.avg(Call.duration_sec).label('avg_duration')
        ).where(
            and_(
                Call.created_at >= cutoff_date,
                Call.agent_id.isnot(None)
            )
        ).group_by(
            Call.agent_id
        ).order_by(
            func.count(Call.id).desc()
        ).limit(limit)
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        agents_data = []
        for row in rows:
            # Calculate resolution-like metric (calls with positive sentiment)
            resolution_query = select(func.count(Call.id)).where(
                and_(
                    Call.agent_id == row.agent_id,
                    Call.sentiment_label == 'positive',
                    Call.created_at >= cutoff_date
                )
            )
            resolution_result = await db.execute(resolution_query)
            resolved_count = resolution_result.scalar() or 0
            
            resolution_rate = (resolved_count / row.total_calls * 100) if row.total_calls > 0 else 0
            
            agents_data.append({
                'agent_id': row.agent_id,
                'name': f'Agent {row.agent_id}',
                'initials': row.agent_id[:2].upper() if row.agent_id else 'AG',
                'total_calls': row.total_calls,
                'avg_sentiment': round(row.avg_sentiment or 0, 2),
                'avg_duration': int(row.avg_duration or 0),
                'resolution_rate': round(resolution_rate, 1)
            })
        
        return agents_data
    
    @staticmethod
    async def get_common_topics(db: AsyncSession, days_back: int = 30) -> List[Dict]:
        """Get common call topics/categories."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        # For now, derive topics from sentiment and basic categorization
        # Future enhancement: use LLM-extracted intents/entities
        
        topics = [
            {'label': 'Product Inquiries', 'field': 'positive'},
            {'label': 'Technical Support', 'field': 'negative'},
            {'label': 'Billing Questions', 'field': None},
            {'label': 'General Inquiry', 'field': 'neutral'},
            {'label': 'Account Setup', 'field': None}
        ]
        
        results = []
        for topic in topics:
            if topic['field']:
                query = select(func.count(Call.id)).where(
                    and_(
                        Call.created_at >= cutoff_date,
                        Call.sentiment_label == topic['field']
                    )
                )
            else:
                # Placeholder for other categories
                query = select(func.count(Call.id)).where(
                    Call.created_at >= cutoff_date
                ).limit(100)  # Sample approximation
                
            result = await db.execute(query)
            count = result.scalar() or 0
            results.append({'label': topic['label'], 'count': count})
        
        return results
    
    @staticmethod
    async def get_customer_ratings_distribution(db: AsyncSession, days_back: int = 30) -> List[Dict]:
        """Get customer satisfaction ratings distribution (1-5 stars)."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        # Map sentiment scores to star ratings (this is approximate)
        # Positive (~0.7-1.0) -> 4-5 stars
        # Neutral (~0.4-0.7) -> 3-4 stars  
        # Negative (~0.0-0.4) -> 1-3 stars
        
        ratings = []
        for rating in [5, 4, 3, 2, 1]:
            if rating >= 4:  # High ratings
                sentiment_condition = Call.sentiment_label == 'positive'
            elif rating >= 3:  # Medium ratings
                sentiment_condition = Call.sentiment_label == 'neutral'
            else:  # Low ratings
                sentiment_condition = Call.sentiment_label == 'negative'
                
            query = select(func.count(Call.id)).where(
                and_(
                    Call.created_at >= cutoff_date,
                    sentiment_condition
                )
            )
            result = await db.execute(query)
            count = result.scalar() or 0
            ratings.append({'rating': rating, 'count': count, 'percentage': 0})  # Percentage calculated later
        
        # Calculate percentages
        total = sum(r['count'] for r in ratings)
        if total > 0:
            for r in ratings:
                r['percentage'] = round((r['count'] / total) * 100, 1)
        
        return ratings
    
    @staticmethod
    async def get_operational_metrics(db: AsyncSession, days_back: int = 30) -> Dict:
        """Get key operational metrics."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        # Service Level (calls answered within target time)
        # Using 5 minutes as target for this example
        target_seconds = 300
        service_level_query = select(
            func.count(case((Call.duration_sec <= target_seconds, 1))).label('within_target'),
            func.count(Call.id).label('total')
        ).where(Call.created_at >= cutoff_date)
        
        service_result = await db.execute(service_level_query)
        service_row = service_result.fetchone()
        
        service_level = (service_row.within_target / service_row.total * 100) if service_row.total > 0 else 0
        
        # Occupancy Rate (approximate - would need agent login/logout data)
        # For now, using a placeholder calculation
        occupancy_rate = min(85, max(60, service_level * 0.8))  # Correlated approximation
        
        # Call Abandonment Rate (calls that didn't complete)
        # Using status field - assuming 'failed' or similar indicates abandonment
        abandonment_query = select(
            func.count(case((Call.status == 'failed', 1))).label('abandoned'),
            func.count(Call.id).label('total')
        ).where(Call.created_at >= cutoff_date)
        
        abandon_result = await db.execute(abandonment_query)
        abandon_row = abandon_result.fetchone()
        
        abandonment_rate = (abandon_row.abandoned / abandon_row.total * 100) if abandon_row.total > 0 else 2.3  # Default fallback
        
        return {
            'service_level': round(service_level, 1),
            'occupancy_rate': round(occupancy_rate, 1),
            'abandonment_rate': round(abandonment_rate, 1)
        }
