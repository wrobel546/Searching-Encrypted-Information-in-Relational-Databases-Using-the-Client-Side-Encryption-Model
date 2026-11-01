from dataclasses import dataclass


@dataclass
class Contact:
    id: int
    surname: str
    email: str