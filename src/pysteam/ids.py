"""SteamID packing and parsing without legacy namespace dependencies."""

from __future__ import annotations

import re
from dataclasses import dataclass

STEAMID64_BASE = 0x0110000100000000
_STEAM2 = re.compile(r"^STEAM_([0-5]):([01]):([0-9]+)$")
_STEAM3 = re.compile(r"^\[([A-Za-z]):([0-5]):([0-9]+)(?::([0-9]+))?\]$")
_TYPE_BY_LETTER = {
    "I": 0,
    "U": 1,
    "M": 2,
    "G": 3,
    "A": 4,
    "P": 5,
    "C": 6,
    "g": 7,
    "T": 8,
    "L": 8,
    "c": 8,
    "a": 10,
}


@dataclass(frozen=True, slots=True)
class SteamID:
    value: int

    def __post_init__(self) -> None:
        if not 0 <= self.value <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("SteamID must be an unsigned 64-bit integer")

    @classmethod
    def from_account_id(cls, account_id: int, *, universe: int = 1, instance: int = 1) -> SteamID:
        if (
            not 0 <= account_id <= 0xFFFFFFFF
            or not 0 <= universe <= 0xFF
            or not 0 <= instance <= 0xFFFFF
        ):
            raise ValueError("SteamID component out of range")
        return cls((universe << 56) | (1 << 52) | (instance << 32) | account_id)

    @classmethod
    def parse(cls, text: str | int) -> SteamID:
        if isinstance(text, int):
            return cls(text)
        if text.isdecimal():
            return cls(int(text))
        if match := _STEAM2.fullmatch(text):
            universe, parity, half = map(int, match.groups())
            return cls.from_account_id(2 * half + parity, universe=universe or 1)
        if match := _STEAM3.fullmatch(text):
            letter, universe_text, account_text, instance_text = match.groups()
            if letter not in _TYPE_BY_LETTER:
                raise ValueError("unknown SteamID account type")
            universe, account = int(universe_text), int(account_text)
            instance = int(instance_text) if instance_text is not None else 1
            if account > 0xFFFFFFFF or instance > 0xFFFFF:
                raise ValueError("SteamID component out of range")
            return cls(
                (universe << 56) | (_TYPE_BY_LETTER[letter] << 52) | (instance << 32) | account
            )
        raise ValueError("unrecognized SteamID format")

    @property
    def account_id(self) -> int:
        return self.value & 0xFFFFFFFF

    @property
    def instance(self) -> int:
        return (self.value >> 32) & 0xFFFFF

    @property
    def account_type(self) -> int:
        return (self.value >> 52) & 0xF

    @property
    def universe(self) -> int:
        return (self.value >> 56) & 0xFF

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)
