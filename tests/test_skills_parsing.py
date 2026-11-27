"""Tests for skills-line item splitting in resume_input_parser."""

from resume_platform.resume_input_parser import parse_skills_markdown


def parse_skill_items(line: str) -> list[str]:
    """Items of the single skills group parsed from one markdown line."""
    section: dict = {}
    parse_skills_markdown(f"## Skills\n{line}", section, "v1", "skills")
    [group] = section["groups"]
    return group["items"]


def test_skills_split_respects_parentheses():
    line = "Languages: C/C++ (primary, exceptional depth), Python, Rust, Java, SQL"
    result = parse_skill_items(line)
    assert result == [
        "C/C++ (primary, exceptional depth)",
        "Python",
        "Rust",
        "Java",
        "SQL",
    ]


def test_skills_split_nested_parens():
    line = "Tools: gdb (with plugins, e.g. peda), CMake"
    assert parse_skill_items(line) == ["gdb (with plugins, e.g. peda)", "CMake"]


def test_skills_split_no_parens_unaffected():
    line = "Languages: C++, Python, Rust"
    assert parse_skill_items(line) == ["C++", "Python", "Rust"]


def test_skills_split_truly_nested_parens():
    line = "Build: CMake (generators (ninja, make), presets), Bazel"
    assert parse_skill_items(line) == [
        "CMake (generators (ninja, make), presets)",
        "Bazel",
    ]


def test_skills_split_brackets_and_braces():
    line = "Data: numpy[array, matrix], pandas"
    assert parse_skill_items(line) == ["numpy[array, matrix]", "pandas"]


def test_skills_split_semicolon_is_still_a_delimiter():
    line = "Languages: C++; Python, Rust"
    assert parse_skill_items(line) == ["C++", "Python", "Rust"]


def test_skills_split_semicolon_inside_parens_protected():
    line = "Languages: C++ (C++11; C++17), Python"
    assert parse_skill_items(line) == ["C++ (C++11; C++17)", "Python"]


def test_skills_split_unbalanced_parens_falls_back_to_flat_split():
    """Unbalanced delimiters are treated as literal text, not as a nesting region.

    Without the fallback, a stray "(" would swallow every following comma and
    collapse the whole line into a single item.
    """
    line = "Languages: C/C++ (primary, Python, Rust"
    assert parse_skill_items(line) == ["C/C++ (primary", "Python", "Rust"]


def test_skills_split_strips_bullet_marker_and_bold():
    assert parse_skill_items("- **Languages**: **C++**, Python") == ["C++", "Python"]


def test_line_without_category_is_a_category_without_items():
    section: dict = {}
    parse_skills_markdown("## Skills\n- **Leadership**", section, "v1", "skills")
    assert section["groups"] == [{"category": "Leadership", "items": []}]


def test_parse_skills_markdown_preserves_parenthesized_commas():
    markdown = (
        "# Skills\n"
        "- Languages: C/C++ (primary, exceptional depth), Python, Rust\n"
        "- Tools: gdb (with plugins, e.g. peda), CMake\n"
    )
    section = {}
    parse_skills_markdown(markdown, section, "v1", "skills")

    assert section["title"] == "Skills"
    assert section["groups"] == [
        {
            "category": "Languages",
            "items": ["C/C++ (primary, exceptional depth)", "Python", "Rust"],
        },
        {
            "category": "Tools",
            "items": ["gdb (with plugins, e.g. peda)", "CMake"],
        },
    ]
