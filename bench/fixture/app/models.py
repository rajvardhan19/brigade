from dataclasses import dataclass, field


@dataclass
class User:
    id: int
    email: str
    password_hash: str
    salt: str
    created_at: float


@dataclass
class Note:
    id: int
    owner_id: int
    title: str
    body: str = ""
    tags: list = field(default_factory=list)
    created_at: float = 0.0
    updated_at: float = 0.0


@dataclass
class Session:
    token: str
    user_id: int
    created_at: float
