"""Official undergraduate college options for member identity fields.

The names and scope are documented in docs/jlu-colleges.md. Codes are stable
internal identifiers; display names can follow official university naming.
"""

from typing import TypedDict


class CollegeOption(TypedDict):
    code: str
    name: str


COLLEGES: tuple[CollegeOption, ...] = (
    {"code": "philosophy-sociology", "name": "哲学社会学院"},
    {"code": "literature-journalism", "name": "文学院（含新闻与传播学院）"},
    {"code": "archaeology", "name": "考古学院"},
    {"code": "art", "name": "艺术学院"},
    {"code": "physical-education", "name": "体育学院"},
    {"code": "foreign-languages-culture", "name": "外国语言文化学院"},
    {"code": "business-management", "name": "商学与管理学院"},
    {"code": "law", "name": "法学院"},
    {"code": "public-diplomacy", "name": "公共外交学院"},
    {"code": "marxism", "name": "马克思主义学院"},
    {"code": "public-administration", "name": "行政学院"},
    {"code": "economics", "name": "经济学院"},
    {"code": "chemistry", "name": "化学学院"},
    {"code": "life-sciences", "name": "生命科学学院"},
    {"code": "mathematics", "name": "数学学院"},
    {"code": "physics", "name": "物理学院"},
    {"code": "mechanical-aerospace", "name": "机械与航空航天工程学院"},
    {"code": "transport", "name": "交通学院"},
    {"code": "automotive", "name": "汽车工程学院"},
    {"code": "bio-agricultural-engineering", "name": "生物与农业工程学院"},
    {"code": "materials-science-engineering", "name": "材料科学与工程学院"},
    {"code": "electronic-science-engineering", "name": "电子科学与工程学院"},
    {"code": "integrated-circuits", "name": "集成电路学院"},
    {"code": "communications-engineering", "name": "通信工程学院"},
    {"code": "computer-science-technology", "name": "计算机科学与技术学院"},
    {"code": "software", "name": "软件学院"},
    {"code": "earth-sciences", "name": "地球科学学院"},
    {"code": "earth-exploration", "name": "地球探测科学与技术学院"},
    {"code": "construction-engineering", "name": "建设工程学院"},
    {"code": "new-energy-environment", "name": "新能源与环境学院"},
    {"code": "instrumentation-electrical", "name": "仪器科学与电气工程学院"},
    {"code": "public-health", "name": "公共卫生学院"},
    {"code": "bethune-first-clinical-medicine", "name": "白求恩第一临床医学院"},
    {"code": "basic-medical-sciences", "name": "基础医学院"},
    {"code": "bethune-stomatology", "name": "白求恩口腔医学院"},
    {"code": "pharmacy", "name": "药学院"},
    {"code": "nursing", "name": "护理学院"},
    {"code": "veterinary-medicine", "name": "动物医学学院"},
    {"code": "plant-sciences", "name": "植物科学学院"},
    {"code": "animal-sciences", "name": "动物科学学院"},
    {"code": "food-science-engineering", "name": "食品科学与工程学院"},
    {"code": "artificial-intelligence", "name": "人工智能学院"},
    {"code": "history-culture", "name": "历史文化学院"},
    {"code": "northeast-asia", "name": "东北亚学院"},
    {"code": "bionic-science-engineering", "name": "仿生科学与工程学院"},
)

COLLEGE_CODES = frozenset(option["code"] for option in COLLEGES)
COLLEGE_BY_CODE = {option["code"]: option for option in COLLEGES}


def is_college_code(value: str) -> bool:
    return value in COLLEGE_CODES
