# -*- coding: utf-8 -*-
import json
import re

from pathlib import Path
from pymongo import MongoClient

from myagent.resume_renderer import render_resume_from_dict,compile_tex

from myagent.models.agent_resume import (
    EntriesSection,
    Entry,
    Metadata,
    Resume,
    SkillGroup,
    SkillsSection,
    SummarySection,
    resume_to_dict,
)
from myagent.models.boss import *

mongodb_uri = "mongodb+srv://maimai:WL0Qd1PZt9bJzsbH@cluster0.xts2azl.mongodb.net/"
database_name = "boss"
collection_name = "talants"  # Note: This is the actual collection name (with typo)


def clean_html_tags(text: str | None) -> str | None:
    """Remove HTML tags from text."""
    if not text:
        return text
    # Remove all HTML tags
    return re.sub(r"<[^>]+>", "", text)


def split_into_bullets(text: str | None) -> list[str]:
    """
    Split text into bullet points based on newlines.
    Handles \n, \r\n, and \r as separators.
    Removes empty lines and leading/trailing whitespace.
    Also handles bullet markers like ●, •, -, etc.
    """
    if not text:
        return []

    # Split by various newline characters
    lines = re.split(r"[\r\n]+", text)

    bullets = []
    for line in lines:
        # Strip whitespace
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Remove common bullet markers at the start
        line = re.sub(r"^[●•\-\*]\s*", "", line)

        # Skip if still empty after removing markers
        if line:
            bullets.append(line)

    return bullets


def convert_boss_talent_to_resume(talent: BossTalentData) -> Resume:
    """Convert BossTalentData to Resume format."""
    base = talent.geekBaseInfo

    # 解析姓名
    full_name = base.name or "Unknown"
    name_parts = full_name.split()
    if len(name_parts) >= 2:
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:])
    else:
        # 如果只有一个名字，将其作为 first_name，last_name 设为 "-"
        first_name = full_name
        last_name = "-"

    # 创建Metadata
    # 从期望职位中获取position信息
    position = None
    if talent.geekExpectList and len(talent.geekExpectList) > 0:
        position = talent.geekExpectList[0].positionName

    metadata = Metadata(
        first_name=first_name,
        last_name=last_name,
        position=position,
        mobile=None,  # Boss数据中没有直接的手机号
        email=None,  # Boss数据中没有直接的邮箱
    )

    # 添加额外的metadata字段
    if base.ageDesc:
        metadata.age = base.ageDesc
    if base.workYearDesc:
        metadata.work_experience = base.workYearDesc
    if base.degreeCategory:
        metadata.education_level = base.degreeCategory
    if base.activeTimeDesc:
        metadata.active_time = base.activeTimeDesc
    if base.gender is not None:
        metadata.gender = (
            "男" if base.gender == 1 else "女" if base.gender == 0 else "未知"
        )

    # 创建Resume
    resume = Resume(source="boss_zhipin", metadata=metadata)

    # 添加Summary section (使用resumeSummary或userDesc)
    summary_bullets = []
    if talent.resumeSummary:
        summary_bullets.append(talent.resumeSummary)
    elif base.userDesc:
        summary_bullets.append(base.userDesc)
    elif base.userDescription:
        summary_bullets.append(base.userDescription)

    # 添加期望职位信息到summary
    if talent.geekExpectList:
        expect_lines = []
        for exp in talent.geekExpectList[:3]:  # 最多3个
            expect_lines.append(
                f"期望职位: {exp.positionName} @ {exp.locationName}, {exp.salaryDesc}"
            )
        if expect_lines:
            summary_bullets.extend(expect_lines)

    if summary_bullets:
        summary_section = SummarySection(
            id="summary", title="Summary", bullets=summary_bullets
        )
        resume.add_section(summary_section)

    # 添加Skills section (如果有professionalSkill)
    if talent.professionalSkill:
        skills_section = SkillsSection(
            id="skills",
            title="Skills",
            groups=[
                SkillGroup(
                    category="Professional Skills", items=[talent.professionalSkill]
                )
            ],
        )
        resume.add_section(skills_section)

    # 添加Experience section
    if talent.geekWorkExpList and len(talent.geekWorkExpList) > 0:
        entries = []
        for work in talent.geekWorkExpList:
            bullets = []
            # Split responsibility by newlines
            if work.responsibility:
                bullets.extend(split_into_bullets(work.responsibility))
            # Split work performance by newlines
            if work.workPerformance:
                bullets.extend(split_into_bullets(work.workPerformance))

            # 构建period
            period_parts = []
            if work.startYearMonStr:
                period_parts.append(work.startYearMonStr)
            if work.endYearMonStr:
                period_parts.append(work.endYearMonStr)
            elif work.workYearDesc:
                if period_parts:
                    period_parts.append(work.workYearDesc)

            period = " - ".join(period_parts) if period_parts else work.workYearDesc

            entry = Entry(
                title=work.positionName or work.positionTitle or "职位",
                organization=work.company or "公司",
                location=None,  # Boss数据中没有location
                period=period,
                bullets=bullets,
            )
            entries.append(entry)

        if entries:
            experience_section = EntriesSection(
                id="experience", title="Professional Experience", entries=entries
            )
            resume.add_section(experience_section)

    # 添加Projects section
    if talent.geekProjExpList and len(talent.geekProjExpList) > 0:
        entries = []
        for proj in talent.geekProjExpList:
            bullets = []
            # Split description by newlines
            if proj.description:
                desc_bullets = split_into_bullets(proj.description)
                # If there are multiple bullets, don't add "描述:" prefix
                if len(desc_bullets) > 1:
                    bullets.extend(desc_bullets)
                else:
                    bullets.extend([f"描述: {b}" for b in desc_bullets])
            # Split performance by newlines
            if proj.performance:
                perf_bullets = split_into_bullets(proj.performance)
                # If there are multiple bullets, don't add "成果:" prefix
                if len(perf_bullets) > 1:
                    bullets.extend(perf_bullets)
                else:
                    bullets.extend([f"成果: {b}" for b in perf_bullets])

            # 构建period
            period_parts = []
            if proj.startDateDesc or proj.startYearMonStr:
                period_parts.append(proj.startDateDesc or proj.startYearMonStr)
            if proj.endDateDesc or proj.endYearMonStr:
                period_parts.append(proj.endDateDesc or proj.endYearMonStr)

            period = " - ".join(period_parts) if period_parts else proj.workYearDesc

            entry = Entry(
                title=proj.roleName or "角色",
                organization=proj.name or "项目",
                location=None,
                period=period,
                bullets=bullets,
            )
            entries.append(entry)

        if entries:
            projects_section = EntriesSection(
                id="projects", title="Projects", entries=entries
            )
            resume.add_section(projects_section)

    # 添加Education section
    if talent.geekEduExpList and len(talent.geekEduExpList) > 0:
        entries = []
        for edu in talent.geekEduExpList:
            bullets = []
            if edu.major:
                bullets.append(f"专业: {edu.major}")
            # Split education description by newlines
            if edu.eduDescription:
                bullets.extend(split_into_bullets(edu.eduDescription))

            # 构建period
            period_parts = []
            if edu.startDateDesc or edu.startYearStr:
                period_parts.append(edu.startDateDesc or edu.startYearStr)
            if edu.endDateDesc or edu.endYearStr:
                period_parts.append(edu.endDateDesc or edu.endYearStr)

            period = " - ".join(period_parts) if period_parts else None

            entry = Entry(
                title=edu.degreeName or "学历",
                organization=edu.school or "学校",
                location=None,
                period=period,
                bullets=bullets,
            )
            entries.append(entry)

        if entries:
            education_section = EntriesSection(
                id="education", title="Education", entries=entries
            )
            resume.add_section(education_section)

    return resume


def parse_geek_base_info(data: dict) -> GeekBaseInfo:
    """Parse geekBaseInfo from MongoDB document."""
    if not data:
        return GeekBaseInfo()

    return GeekBaseInfo(
        preChatTips=data.get("preChatTips"),
        blur=data.get("blur"),
        userId=data.get("userId"),
        encryptGeekId=clean_html_tags(data.get("encryptGeekId")),
        geekSource=data.get("geekSource"),
        name=clean_html_tags(data.get("name")),
        gender=data.get("gender"),
        activeTimeDesc=clean_html_tags(data.get("activeTimeDesc")),
        tiny=data.get("tiny"),
        large=data.get("large"),
        otdUser=data.get("otdUser"),
        age=data.get("age"),
        userDescription=clean_html_tags(data.get("userDescription")),
        ageDesc=clean_html_tags(data.get("ageDesc")),
        workYearDesc=clean_html_tags(data.get("workYearDesc")),
        degreeCategory=clean_html_tags(data.get("degreeCategory")),
        userDesc=clean_html_tags(data.get("userDesc")),
        applyStatusContent=clean_html_tags(data.get("applyStatusContent")),
    )


def parse_geek_expect_list(data: list) -> list[GeekExpect]:
    """Parse geekExpectList from MongoDB document."""
    if not data:
        return []

    result = []
    for item in data:
        result.append(
            GeekExpect(
                locationName=clean_html_tags(item.get("locationName", "")),
                positionName=clean_html_tags(item.get("positionName", "")),
                industryDesc=clean_html_tags(item.get("industryDesc", "")),
                salaryDesc=clean_html_tags(item.get("salaryDesc", "")),
                industryExpect=item.get("industryExpect", False),
                positionTagName=clean_html_tags(item.get("positionTagName")),
            )
        )
    return result


def parse_geek_work_exp_list(data: list) -> list[GeekWorkExp]:
    """Parse geekWorkExpList from MongoDB document."""
    if not data:
        return []

    result = []
    for item in data:
        result.append(
            GeekWorkExp(
                workId=item.get("workId"),
                startYearMonStr=clean_html_tags(item.get("startYearMonStr")),
                endYearMonStr=clean_html_tags(item.get("endYearMonStr")),
                company=clean_html_tags(item.get("company")),
                positionName=clean_html_tags(item.get("positionName")),
                positionTitle=clean_html_tags(item.get("positionTitle")),
                department=clean_html_tags(item.get("department")),
                responsibility=clean_html_tags(item.get("responsibility")),
                workPerformance=clean_html_tags(item.get("workPerformance")),
                workEmphasisList=item.get("workEmphasisList"),
                workYearDesc=clean_html_tags(item.get("workYearDesc")),
            )
        )
    return result


def parse_geek_proj_exp_list(data: list) -> list[GeekProjExp]:
    """Parse geekProjExpList from MongoDB document."""
    if not data:
        return []

    result = []
    for item in data:
        result.append(
            GeekProjExp(
                projectId=item.get("projectId"),
                descriptionHighlightList=item.get("descriptionHighlightList"),
                performanceHighlightList=item.get("performanceHighlightList"),
                name=clean_html_tags(item.get("name")),
                url=clean_html_tags(item.get("url")),
                roleName=clean_html_tags(item.get("roleName")),
                description=clean_html_tags(item.get("description")),
                performance=clean_html_tags(item.get("performance")),
                orderNum=item.get("orderNum"),
                startDate=item.get("startDate"),
                endDate=item.get("endDate"),
                startYearMonStr=clean_html_tags(item.get("startYearMonStr")),
                endYearMonStr=clean_html_tags(item.get("endYearMonStr")),
                startDateDesc=clean_html_tags(item.get("startDateDesc")),
                endDateDesc=clean_html_tags(item.get("endDateDesc")),
                workYearDesc=clean_html_tags(item.get("workYearDesc")),
            )
        )
    return result


def parse_geek_edu_exp_list(data: list) -> list[GeekEduExp]:
    """Parse geekEduExpList from MongoDB document."""
    if not data:
        return []

    result = []
    for item in data:
        result.append(
            GeekEduExp(
                courseDesc=clean_html_tags(item.get("courseDesc")),
                startYearStr=clean_html_tags(item.get("startYearStr")),
                endYearStr=clean_html_tags(item.get("endYearStr")),
                badge=clean_html_tags(item.get("badge")),
                school=clean_html_tags(item.get("school")),
                major=clean_html_tags(item.get("major")),
                degreeName=clean_html_tags(item.get("degreeName")),
                eduType=item.get("eduType"),
                tags=item.get("tags"),
                eduDescription=clean_html_tags(item.get("eduDescription")),
                majorRankingDesc=clean_html_tags(item.get("majorRankingDesc")),
                thesisTitle=clean_html_tags(item.get("thesisTitle")),
                thesisDesc=clean_html_tags(item.get("thesisDesc")),
                startDateDesc=clean_html_tags(item.get("startDateDesc")),
                endDateDesc=clean_html_tags(item.get("endDateDesc")),
                degree=item.get("degree"),
            )
        )
    return result


def parse_geek_edu_exp(data: dict) -> GeekEduExp | None:
    """Parse single GeekEduExp from MongoDB document."""
    if not data:
        return None

    return GeekEduExp(
        courseDesc=clean_html_tags(data.get("courseDesc")),
        startYearStr=clean_html_tags(data.get("startYearStr")),
        endYearStr=clean_html_tags(data.get("endYearStr")),
        badge=clean_html_tags(data.get("badge")),
        school=clean_html_tags(data.get("school")),
        major=clean_html_tags(data.get("major")),
        degreeName=clean_html_tags(data.get("degreeName")),
        eduType=data.get("eduType"),
        tags=data.get("tags"),
        eduDescription=clean_html_tags(data.get("eduDescription")),
        majorRankingDesc=clean_html_tags(data.get("majorRankingDesc")),
        thesisTitle=clean_html_tags(data.get("thesisTitle")),
        thesisDesc=clean_html_tags(data.get("thesisDesc")),
        startDateDesc=clean_html_tags(data.get("startDateDesc")),
        endDateDesc=clean_html_tags(data.get("endDateDesc")),
        degree=data.get("degree"),
    )


def parse_show_expect_position(data: dict) -> ShowExpectPosition | None:
    """Parse showExpectPosition from MongoDB document."""
    if not data:
        return None

    return ShowExpectPosition(
        expectId=data.get("expectId"),
        encryptExpId=data.get("encryptExpId"),
        encryptExpectId=data.get("encryptExpectId"),
    )


def parse_boss_talent_data(doc: dict) -> BossTalentData:
    """Parse MongoDB document into BossTalentData object."""
    # Extract geekDetail object (where most data resides)
    geek_detail = doc.get("geekDetail", {})
    if not geek_detail:
        geek_detail = {}

    # Parse geekBaseInfo (required field)
    geek_base_info = parse_geek_base_info(geek_detail.get("geekBaseInfo", {}))

    # Create BossTalentData with all fields
    talent = BossTalentData(
        geekBaseInfo=geek_base_info,
        searchKeyword=doc.get("searchKeyword"),
        geekExpectList=parse_geek_expect_list(geek_detail.get("geekExpectList")),
        geekWorkExpList=parse_geek_work_exp_list(geek_detail.get("geekWorkExpList")),
        geekProjExpList=parse_geek_proj_exp_list(geek_detail.get("geekProjExpList")),
        geekEduExpList=parse_geek_edu_exp_list(geek_detail.get("geekEduExpList")),
        highestEduExp=parse_geek_edu_exp(geek_detail.get("highestEduExp")),
        multiGeekVideoResume4BossVO=doc.get("multiGeekVideoResume4BossVO"),
        enshrineGeek=doc.get("enshrineGeek"),
        supportInterested=doc.get("supportInterested"),
        alreadyInterested=doc.get("alreadyInterested"),
        geekStatus=doc.get("geekStatus"),
        expectId=doc.get("expectId"),
        encryptExpectId=doc.get("encryptExpectId"),
        showExpectPosition=parse_show_expect_position(doc.get("showExpectPosition")),
        encryptGeekId=doc.get("encryptGeekId"),
        encryptJobId=doc.get("encryptJobId"),
        encryptJid=doc.get("encryptJid"),
        encryptBossId=doc.get("encryptBossId"),
        geekSocialList=geek_detail.get("geekSocialList"),
        geekVolunteerExpList=geek_detail.get("geekVolunteerExpList"),
        geekDzDoneWorkList=geek_detail.get("geekDzDoneWorkList"),
        geekCertificationList=geek_detail.get("geekCertificationList"),
        geekDoneWorkList=geek_detail.get("geekDoneWorkList"),
        highlightWords=geek_detail.get("highlightWords"),
        certList=geek_detail.get("certList"),
        geekDesignWorksList=geek_detail.get("geekDesignWorksList"),
        geekDesignWorksGather=geek_detail.get("geekDesignWorksGather"),
        geekPersonalImageList=geek_detail.get("geekPersonalImageList"),
        geekDeliciousFoodImageList=geek_detail.get("geekDeliciousFoodImageList"),
        geekPersonalLabelList=geek_detail.get("geekPersonalLabelList"),
        geekPostExpList=geek_detail.get("geekPostExpList"),
        geekHandicappedInfo=geek_detail.get("geekHandicappedInfo"),
        geekTrainingExpList=geek_detail.get("geekTrainingExpList"),
        geekHonorList=geek_detail.get("geekHonorList"),
        geekCustomInterestConfig=geek_detail.get("geekCustomInterestConfig"),
        geekJobHuntGroupMemberList=geek_detail.get("geekJobHuntGroupMemberList"),
        geekClubExpList=geek_detail.get("geekClubExpList"),
        professionalSkill=geek_detail.get("professionalSkill"),
        overseasTraitOptions=geek_detail.get("overseasTraitOptions"),
        resumeSummary=geek_detail.get("resumeSummary"),
    )

    # Store any extra fields not defined in the dataclass
    defined_fields = set(BossTalentData.__annotations__.keys())
    for key, value in doc.items():
        if key not in defined_fields and key != "_id" and key != "geekDetail":
            talent.extra_fields[key] = value

    return talent


def print_talent_summary(talent: BossTalentData, index: int):
    """Print a summary of a talent's resume."""
    print(f"\n{'=' * 80}")
    print(f"简历 #{index + 1}")
    print(f"{'=' * 80}")

    # Basic info
    base = talent.geekBaseInfo
    print(f"\n基本信息:")
    print(f"  姓名: {base.name or 'N/A'}")
    print(f"  年龄: {base.ageDesc or base.age or 'N/A'}")
    print(
        f"  性别: {'男' if base.gender == 1 else '女' if base.gender == 0 else 'N/A'}"
    )
    print(f"  工作年限: {base.workYearDesc or 'N/A'}")
    print(f"  学历: {base.degreeCategory or 'N/A'}")
    print(f"  活跃时间: {base.activeTimeDesc or 'N/A'}")

    # Expectations
    if talent.geekExpectList:
        print(f"\n期望职位:")
        for exp in talent.geekExpectList[:3]:  # Show max 3
            print(f"  - {exp.positionName} @ {exp.locationName}")
            print(f"    期望薪资: {exp.salaryDesc}")
            print(f"    行业: {exp.industryDesc}")

    # Education
    if talent.highestEduExp:
        edu = talent.highestEduExp
        print(f"\n最高学历:")
        print(f"  学校: {edu.school or 'N/A'}")
        print(f"  专业: {edu.major or 'N/A'}")
        print(f"  学历: {edu.degreeName or 'N/A'}")
        print(
            f"  时间: {edu.startDateDesc or edu.startYearStr or ''} - {edu.endDateDesc or edu.endYearStr or ''}"
        )

    # Work experience
    if talent.geekWorkExpList:
        print(f"\n工作经历 (共{len(talent.geekWorkExpList)}段):")
        for i, work in enumerate(talent.geekWorkExpList[:3], 1):  # Show max 3
            print(
                f"  [{i}] {work.company or 'N/A'} - {work.positionName or work.positionTitle or 'N/A'}"
            )
            print(
                f"      时间: {work.startYearMonStr or ''} - {work.endYearMonStr or work.workYearDesc or ''}"
            )
            if work.responsibility:
                print(f"      职责: {work.responsibility[:100]}...")

    # Project experience
    if talent.geekProjExpList:
        print(f"\n项目经历 (共{len(talent.geekProjExpList)}个):")
        for i, proj in enumerate(talent.geekProjExpList[:2], 1):  # Show max 2
            print(f"  [{i}] {proj.name or 'N/A'}")
            print(f"      角色: {proj.roleName or 'N/A'}")
            print(
                f"      时间: {proj.startDateDesc or proj.startYearMonStr or ''} - {proj.endDateDesc or proj.endYearMonStr or ''}"
            )

    # Resume summary
    if talent.resumeSummary:
        print(f"\n简历总结:")
        print(f"  {talent.resumeSummary[:200]}...")

    print(f"\n{'=' * 80}\n")


def main():
    """Main function to read and display resumes from MongoDB."""
    # Connect to MongoDB
    print(f"连接到 MongoDB: {database_name}.{collection_name}")
    client = MongoClient(mongodb_uri)
    db = client[database_name]

    # List all collections in the database
    collections = db.list_collection_names()
    print(f"数据库中的集合: {collections}\n")

    collection = db[collection_name]

    # Get total count
    total_count = collection.count_documents({})
    print(f"{collection_name} 集合中共有 {total_count} 条简历记录\n")

    # Fetch 3 resumes
    resumes = []
    print("正在读取前3条简历...\n")
    for i, doc in enumerate(collection.find().limit(3), 1):
        try:
            # Print first document structure for debugging
            if i == 1:
                print("第一条文档的键:", list(doc.keys()))
                if "geekDetail" in doc and doc["geekDetail"]:
                    print("geekDetail 的键:", list(doc["geekDetail"].keys()))
                    if "geekBaseInfo" in doc["geekDetail"]:
                        print(
                            "geekDetail.geekBaseInfo 的键:",
                            list(doc["geekDetail"]["geekBaseInfo"].keys())
                            if doc["geekDetail"]["geekBaseInfo"]
                            else "None",
                        )
                print()

            talent = parse_boss_talent_data(doc)
            resumes.append(talent)
        except Exception as e:
            print(f"解析简历 #{i} 失败: {e}")
            import traceback

            traceback.print_exc()
            continue

    # Print summaries
    print(f"\n成功加载 {len(resumes)} 条简历\n")
    for i, talent in enumerate(resumes):
        print_talent_summary(talent, i)

    # Convert to Resume format and output
    print("\n" + "=" * 80)
    print("转换为 Resume 格式")
    print("=" * 80 + "\n")

    for i, talent in enumerate(resumes):
        print(f"\n{'=' * 80}")
        print(f"Resume #{i + 1} (转换后)")
        print(f"{'=' * 80}\n")

        try:
            resume = convert_boss_talent_to_resume(talent)

            # 验证resume
            is_valid = resume.validate()
            print(f"Resume 验证: {'通过' if is_valid else '失败'}\n")

            # 转换为JSON并输出
            resume_dict = resume_to_dict(resume)
            latex_resume = render_resume_from_dict(resume_dict)  # 渲染以确保无误

            # Ensure output directory exists and write the .tex file under repo root
            # Use a repository-root-relative path so running the script from any CWD works
            repo_root = Path(__file__).resolve().parents[2]
            out_dir = repo_root / "samples"
            out_dir.mkdir(parents=True, exist_ok=True)
            tex_path = out_dir / f"resume_{i + 1}.tex"
            tex_path.write_text(latex_resume, encoding="utf-8")
            compile_tex(tex_path)
            resume_json = json.dumps(resume_dict, ensure_ascii=False, indent=2)
            print(resume_json)
            print()

        except Exception as e:
            print(f"转换失败: {e}")
            import traceback

            traceback.print_exc()

    # Close connection
    client.close()
    print("\n" + "=" * 80)
    print("MongoDB 连接已关闭")
    print("=" * 80)


if __name__ == "__main__":
    main()
