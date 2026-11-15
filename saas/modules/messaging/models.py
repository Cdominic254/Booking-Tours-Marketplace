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


class ChatConversation(db.Model):
    """One live-chat thread between a visitor and the support team.

    The visitor owns the thread through an unguessable ``token`` kept in
    localStorage, so a thread survives a dropped session cookie. Unread
    counters are stored per side instead of deriving them from messages so
    the inbox can show a badge without loading every thread.
    """

    __tablename__ = 'chat_conversation'

    OPEN = 'open'
    CLOSED = 'closed'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(160), nullable=True)
    page = db.Column(db.String(160), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=OPEN)
    staff_unread = db.Column(db.Integer, nullable=False, default=0)
    visitor_unread = db.Column(db.Integer, nullable=False, default=0)
    message_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_message_at = db.Column(db.DateTime, nullable=True)

    def last_message(self):
        return ChatMessage.query.filter_by(conversation_id=self.id).order_by(ChatMessage.id.desc()).first()

    def to_dict(self, *, include_preview=True):
        data = {
            'id': self.id,
            'name': self.name or '',
            'email': self.email or '',
            'page': self.page or '',
            'status': self.status,
            'staff_unread': self.staff_unread,
            'visitor_unread': self.visitor_unread,
            'message_count': self.message_count,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
            'last_message_at': self.last_message_at.isoformat() + 'Z' if self.last_message_at else None,
        }
        if include_preview:
            latest = self.last_message()
            data['preview'] = latest.body[:120] if latest else ''
            data['preview_sender'] = latest.sender if latest else ''
        return data


class ChatMessage(db.Model):
    """A single bubble in a live-chat thread."""

    __tablename__ = 'chat_message'

    VISITOR = 'visitor'
    STAFF = 'staff'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('chat_conversation.id'), nullable=False, index=True)
    sender = db.Column(db.String(20), nullable=False, default=VISITOR)
    author = db.Column(db.String(100), nullable=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'sender': self.sender,
            'author': self.author or '',
            'body': self.body,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }
