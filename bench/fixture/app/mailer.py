class Outbox:
    """Fake mail transport: records messages instead of sending them."""

    def __init__(self):
        self.sent = []

    def send(self, to, subject, body):
        self.sent.append({"to": to, "subject": subject, "body": body})
