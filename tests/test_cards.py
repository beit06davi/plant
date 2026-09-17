from garden.cards import find_section, items, load_card, load_seed, parse_sections, split_frontmatter


def test_frontmatter_with_bom_and_crlf(tmp_path):
    p = tmp_path / "NODE.md"
    p.write_bytes("\ufeff---\r\npurpose: a\r\nserves: [G1]\r\n---\r\n## 메모\r\n- x\r\n".encode("utf-8"))
    c = load_card(p)
    assert c.error is None
    assert c.meta == {"purpose": "a", "serves": ["G1"]}
    assert items(c.sections["메모"]) == ["x"]


def test_missing_frontmatter():
    meta, body, err = split_frontmatter("# hi\n")
    assert meta == {} and err


def test_unclosed_frontmatter():
    _, _, err = split_frontmatter("---\nname: a\n")
    assert err


def test_invalid_yaml():
    _, _, err = split_frontmatter("---\nname: [a\n---\n")
    assert err and "YAML" in err


def test_non_mapping_frontmatter():
    _, _, err = split_frontmatter("---\n- a\n---\n")
    assert err


def test_sections_level2_only():
    body = "# title\nignored\n## A\nline a\n### sub\nstill a\n## B\n- b1\n* b2\n"
    s = parse_sections(body)
    assert set(s) == {"A", "B"}
    assert "still a" in s["A"]
    assert items(s["B"]) == ["b1", "b2"]


def test_find_section_prefix():
    s = {"목표 (위에 있을수록 우선)": "x", "비목표 (하지 않을 것)": "y"}
    assert find_section(s, "목표") == "x"
    assert find_section(s, "비목표") == "y"
    assert find_section(s, "없음") == ""


def test_seed_goals_in_order(tree):
    seed = load_seed(tree / "SEED.md")
    assert seed.error is None
    assert [g.id for g in seed.goals] == ["G1", "G2", "G3"]
    assert seed.goals[0].text == "이중 예약 없는 예약"
    assert seed.goals[0].measure == "동시 예약 테스트 통과"
    assert seed.goals[1].measure == ""
    assert seed.rank("G2") == 1
    assert seed.rank("G9") is None
    assert items(find_section(seed.sections, "비목표")) == ["결제"]
