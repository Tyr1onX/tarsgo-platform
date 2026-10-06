from fastapi import APIRouter

from ..college_dictionary import COLLEGES
from ..schemas import CollegeOut

router = APIRouter(prefix="/api/colleges", tags=["colleges"])


@router.get("", response_model=list[CollegeOut])
def list_colleges() -> list[CollegeOut]:
    return [CollegeOut(**option) for option in COLLEGES]
