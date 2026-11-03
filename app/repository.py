import secrets
import string

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Link

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 7


def generate_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def create_link(session: Session, target_url: str) -> Link:
    for _ in range(5):
        code = generate_code()
        if session.scalar(select(Link).where(Link.code == code)) is None:
            link = Link(code=code, target_url=target_url)
            session.add(link)
            session.commit()
            return link
    raise RuntimeError("could not allocate a unique code")


def get_link(session: Session, code: str) -> Link | None:
    return session.scalar(select(Link).where(Link.code == code))


def register_click(session: Session, code: str) -> None:
    session.execute(update(Link).where(Link.code == code).values(clicks=Link.clicks + 1))
    session.commit()
