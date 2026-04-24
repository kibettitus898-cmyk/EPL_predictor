from pydantic import BaseModel
from typing import Optional
from datetime import date

class MatchBase(BaseModel):
    season: str
    date: date
    home_team: str
    away_team: str
    ftr: Optional[str] = None       # H / D / A
    fthg: Optional[int] = None
    ftag: Optional[int] = None
    hthg: Optional[int] = None
    htag: Optional[int] = None
    hs: Optional[int] = None        # home shots
    as_: Optional[int] = None       # away shots (aliased)
    hst: Optional[int] = None       # home shots on target
    ast: Optional[int] = None
    hc: Optional[int] = None        # home corners
    ac: Optional[int] = None
    hy: Optional[int] = None        # home yellows
    ay: Optional[int] = None
    hr: Optional[int] = None        # home reds
    ar: Optional[int] = None
    referee: Optional[str] = None
    time_weight: Optional[float] = 1.0

class MatchCreate(MatchBase):
    pass

class MatchOut(MatchBase):
    id: int
    class Config:
        from_attributes = True
