from dataclasses import dataclass, field
from typing import Any

@dataclass
class GeekExpect:
    locationName: str
    positionName: str
    industryDesc: str
    salaryDesc: str
    industryExpect: bool
    positionTagName: str | None

@dataclass
class GeekWorkExp:
    # Historical fields (optionalized)
    workId: int | None = None
    startYearMonStr: str | None = None
    endYearMonStr: str | None = None
    company: str | None = None
    positionName: str | None = None
    positionTitle: str | None = None
    department: str | None = None
    responsibility: str | None = None
    workPerformance: str | None = None
    workEmphasisList: list[str] | None = None
    # New payload fields
    workYearDesc: str | None = None

@dataclass
class GeekProjExp:
    # Historical fields (optionalized)
    projectId: int | None = None
    descriptionHighlightList: list[str] | None = None
    performanceHighlightList: list[str] | None = None
    name: str | None = None
    url: str | None = None
    roleName: str | None = None
    description: str | None = None
    performance: str | None = None
    orderNum: int | None = None
    startDate: str | None = None
    endDate: str | None = None
    startYearMonStr: str | None = None
    endYearMonStr: str | None = None
    # New payload fields
    startDateDesc: str | None = None
    endDateDesc: str | None = None
    workYearDesc: str | None = None

@dataclass
class GeekEduExp:
    # Historical fields (optionalized)
    courseDesc: str | None = None
    startYearStr: str | None = None
    endYearStr: str | None = None
    badge: str | None = None
    school: str | None = None
    major: str | None = None
    degreeName: str | None = None
    eduType: int | None = None
    tags: list[str] | None = None
    eduDescription: str | None = None
    majorRankingDesc: str | None = None
    thesisTitle: str | None = None
    thesisDesc: str | None = None
    # New payload fields
    startDateDesc: str | None = None
    endDateDesc: str | None = None
    degree: int | None = None

@dataclass
class GeekBaseInfo:
    # New payload fields
    preChatTips: Any | None = None
    blur: int | None = None
    userId: int | None = None
    encryptGeekId: str | None = None
    geekSource: int | None = None
    name: str | None = None
    gender: int | None = None
    activeTimeDesc: str | None = None
    tiny: str | None = None
    large: str | None = None
    otdUser: bool | None = None
    # Historical fields
    age: int | None = None
    userDescription: str | None = None
    ageDesc: str | None = None
    workYearDesc: str | None = None
    degreeCategory: str | None = None
    userDesc: str | None = None
    applyStatusContent: str | None = None

@dataclass
class ShowExpectPosition:
    expectId: int | None = None
    encryptExpId: str | None = None  # alias from payload
    encryptExpectId: str | None = None  # normalized alias

@dataclass
class BossTalentData:
    # Core blocks (geekBaseInfo is required)
    geekBaseInfo: GeekBaseInfo
    
    # Present only after persistence
    searchKeyword: str | None = None
    # Core blocks (optional)
    geekExpectList: list[GeekExpect] | None = None
    geekWorkExpList: list[GeekWorkExp] | None = None
    geekProjExpList: list[GeekProjExp] | None = None
    geekEduExpList: list[GeekEduExp] | None = None
    highestEduExp: GeekEduExp | None = None
    # Media / flags
    multiGeekVideoResume4BossVO: Any | None = None
    enshrineGeek: bool | None = None
    supportInterested: bool | None = None
    alreadyInterested: bool | None = None
    geekStatus: int | None = None
    # Expect IDs (two possible shapes)
    expectId: int | None = None
    encryptExpectId: str | None = None
    showExpectPosition: ShowExpectPosition | None = None
    # Encryption IDs (two possible shapes)
    encryptGeekId: str | None = None
    encryptJobId: str | None = None
    encryptJid: str | None = None  # alias from payload
    encryptBossId: str | None = None
    # Misc legacy collections
    geekSocialList: list[Any] | None = None
    geekVolunteerExpList: list[Any] | None = None
    geekDzDoneWorkList: list[Any] | None = None
    geekCertificationList: list[Any] | None = None
    geekDoneWorkList: list[Any] | None = None
    highlightWords: list[str] | None = None
    certList: list[Any] | None = None
    geekDesignWorksList: list[Any] | None = None
    geekDesignWorksGather: list[Any] | None = None
    geekPersonalImageList: list[Any] | None = None
    geekDeliciousFoodImageList: list[Any] | None = None
    geekPersonalLabelList: list[Any] | None = None
    geekPostExpList: list[Any] | None = None
    geekHandicappedInfo: Any | None = None
    geekTrainingExpList: list[Any] | None = None
    geekHonorList: list[Any] | None = None
    geekCustomInterestConfig: Any | None = None
    geekJobHuntGroupMemberList: list[Any] | None = None
    geekClubExpList: list[Any] | None = None
    professionalSkill: str | None = None
    overseasTraitOptions: Any | None = None
    resumeSummary: str | None = None
    
    # 支持额外的任意字段
    extra_fields: dict[str, Any] = field(default_factory=dict)
    
    def __setattr__(self, name: str, value: Any) -> None:
        # 如果字段不在定义的属性中，存储到extra_fields
        if name not in self.__annotations__ and name != 'extra_fields':
            self.extra_fields[name] = value
        else:
            super().__setattr__(name, value)
    
    def __getattr__(self, name: str) -> Any:
        # 尝试从extra_fields获取未定义的属性
        if 'extra_fields' in self.__dict__ and name in self.extra_fields:
            return self.extra_fields[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")