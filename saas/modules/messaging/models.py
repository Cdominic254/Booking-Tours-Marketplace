from datetime import datetime

from saas.extensions import db


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    email_sent = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'subject': self.subject,
            'message': self.message,
            'timestamp': self.timestamp.isoformat() + 'Z' if self.timestamp else None,
            'email_sent': self.email_sent,
        }


class NewsletterSubscriber(db.Model):
    """Addresses collected by the newsletter signup forms.

    One row per email address; unsubscribing keeps the row but flips
    ``is_active`` so an address is never collected twice.
    """

    __tablename__ = 'newsletter_subscriber'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(160), unique=True, nullable=False)
    source = db.Column(db.String(40), nullable=False, default='website')
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'source': self.source,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }
