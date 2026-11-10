from app import clock
from app.api import App

PASSWORD = "correct-horse-1"


def make_app():
    clock.reset()
    return App()


def signup(app, email="ada@example.com", password=PASSWORD):
    status, body = app.handle("POST", "/register", {"email": email, "password": password})
    assert status == 201, body
    status, body = app.handle("POST", "/login", {"email": email, "password": password})
    assert status == 200, body
    return body["token"]
