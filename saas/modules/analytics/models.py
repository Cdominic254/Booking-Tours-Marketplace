from datetime import datetime

from saas.extensions import db


class AnalyticsEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visitor_key = db.Column(db.String(64), nullable=False, index=True)
    source = db.Column(db.String(120), nullable=False, default='unattributed')
    page = db.Column(db.String(160), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)