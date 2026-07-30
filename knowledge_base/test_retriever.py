"""MSDSRetriever 单元测试。

可直接运行：
    cd knowledge_base
    python test_retriever.py

无需外部依赖，仅使用 Python 标准库。
"""

from __future__ import annotations

import os
import sys

# 允许直接在本目录下运行：把父目录加入 sys.path 以便 `from knowledge_base import ...`
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PARENT_DIR = os.path.dirname(_THIS_DIR)
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from knowledge_base import MSDSRetriever  # noqa: E402


def _print_header(title: str) -> None:
    print(f"\n===== {title} =====")


def test_retrieve_hcl_exact() -> None:
    """验证 retrieve('盐酸') 返回正确 MSDS。"""
    _print_header("测试 1: retrieve('盐酸') 精确匹配")
    retriever = MSDSRetriever()
    results = retriever.retrieve("盐酸")
    assert results, "期望至少返回 1 条结果，但返回空列表"
    top = results[0]
    assert top["name"] == "盐酸", f"期望 name == '盐酸'，实际为 {top['name']!r}"
    assert top["id"] == "msds_001", f"期望 id == 'msds_001'，实际为 {top['id']!r}"
    assert top["hazard_level"] == "高", f"期望 hazard_level == '高'，实际为 {top['hazard_level']!r}"
    # 必备字段都存在
    for field in [
        "aliases", "category", "common_products", "toxicity", "flammability",
        "corrosivity", "allergy", "environment",
        "first_aid_ingestion", "first_aid_skin", "first_aid_eye", "first_aid_inhalation",
        "storage", "green_alternatives",
    ]:
        assert field in top, f"返回记录缺少必备字段: {field}"
    print(f"  ✓ 命中：id={top['id']}, name={top['name']}, hazard_level={top['hazard_level']}")


def test_retrieve_via_common_product() -> None:
    """验证 retrieve('洁厕灵') 能通过 common_products 匹配到盐酸。"""
    _print_header("测试 2: retrieve('洁厕灵') 经 common_products 匹配盐酸")
    retriever = MSDSRetriever()
    results = retriever.retrieve("洁厕灵")
    assert results, "期望通过 common_products 匹配到盐酸，但返回空列表"
    top = results[0]
    assert top["name"] == "盐酸", f"期望匹配到盐酸，实际匹配到 {top['name']!r}"
    assert "洁厕灵" in top.get("common_products", []), \
        f"期望盐酸的 common_products 含 '洁厕灵'，实际为 {top.get('common_products')}"
    print(f"  ✓ 命中：{top['name']}（{top['id']}）的 common_products 含 '洁厕灵'")


def test_retrieve_84_matches_naclo() -> None:
    """验证 retrieve('84') 能匹配到次氯酸钠。"""
    _print_header("测试 3: retrieve('84') 匹配次氯酸钠")
    retriever = MSDSRetriever()
    results = retriever.retrieve("84")
    assert results, "期望匹配到次氯酸钠，但返回空列表"
    top = results[0]
    assert top["name"] == "次氯酸钠", f"期望匹配到次氯酸钠，实际匹配到 {top['name']!r}"
    # 确认其 common_products 含有 "84消毒液"
    has_84 = any("84" in p for p in top.get("common_products", []))
    assert has_84, f"期望次氯酸钠的 common_products 含 '84消毒液'，实际为 {top.get('common_products')}"
    print(f"  ✓ 命中：{top['name']}（{top['id']}），common_products 含 84 系列")


def test_retrieve_no_match_returns_empty() -> None:
    """验证 retrieve('对氯苯二甲酸') 在没匹配时返回空列表或最相似项。

    根据任务说明允许两种行为之一。本检索器默认 retrieve 不做模糊回退，
    因此对于不存在的化学品名应返回空列表；同时验证 retrieve_with_fuzzy 可给出最相似项。
    """
    _print_header("测试 4: retrieve('对氯苯二甲酸') 无精确/子串匹配的处理")
    retriever = MSDSRetriever()
    results = retriever.retrieve("对氯苯二甲酸")
    # 允许：要么空列表，要么返回最相似项
    if results:
        # 若返回非空，则应是合理的相关项（不报错）
        print(f"  ℹ 返回最相似项：{results[0]['name']}（{results[0]['id']}）")
    else:
        print("  ℹ 返回空列表（无精确/子串匹配）")

    # 额外：模糊检索应能给出一个最相似项（应对氯间二甲苯酚相关）
    fuzzy = retriever.retrieve_with_fuzzy("对氯苯二甲酸", top_k=1)
    if fuzzy:
        print(f"  ✓ retrieve_with_fuzzy 返回最相似项：{fuzzy[0]['name']}（{fuzzy[0]['id']}）")
    else:
        # 模糊检索阈值未命中也可接受
        print("  ℹ retrieve_with_fuzzy 也未给出相似项（阈值过滤）")


def test_list_all_count() -> None:
    """验证 list_all() 返回 >= 50 条。"""
    _print_header("测试 5: list_all() 返回 >= 50 条")
    retriever = MSDSRetriever()
    all_items = retriever.list_all()
    assert len(all_items) >= 50, f"期望 >= 50 条，实际 {len(all_items)} 条"
    print(f"  ✓ 共返回 {len(all_items)} 条 MSDS 记录")

    # 顺便校验所有条目都带 id 且唯一
    ids = [item["id"] for item in all_items]
    assert len(set(ids)) == len(ids), "存在重复 id"
    print(f"  ✓ 所有 id 唯一（{len(ids)} 条）")

    # 校验类别覆盖
    categories = {item["category"] for item in all_items}
    expected_categories = {"清洁剂", "消毒剂", "农药", "药品", "化妆品", "其他"}
    missing = expected_categories - categories
    assert not missing, f"缺少类别: {missing}，实际覆盖: {categories}"
    print(f"  ✓ 覆盖类别: {sorted(categories)}")


def test_get_by_id() -> None:
    """额外测试 get_by_id。"""
    _print_header("额外测试: get_by_id('msds_001')")
    retriever = MSDSRetriever()
    item = retriever.get_by_id("msds_001")
    assert item is not None, "get_by_id('msds_001') 返回 None"
    assert item["name"] == "盐酸", f"期望 name == '盐酸'，实际 {item['name']!r}"
    print(f"  ✓ get_by_id('msds_001') -> {item['name']}")

    # 不存在的 id
    assert retriever.get_by_id("not_exist") is None
    print("  ✓ get_by_id('not_exist') -> None")


def test_alias_match() -> None:
    """额外测试别名精确匹配。"""
    _print_header("额外测试: 别名精确匹配 retrieve('DDVP')")
    retriever = MSDSRetriever()
    results = retriever.retrieve("DDVP")
    assert results, "期望通过别名 DDVP 匹配到敌敌畏"
    assert results[0]["name"] == "敌敌畏", f"期望匹配到敌敌畏，实际 {results[0]['name']!r}"
    print(f"  ✓ 'DDVP' -> {results[0]['name']}（{results[0]['id']}）")


def main() -> int:
    tests = [
        test_retrieve_hcl_exact,
        test_retrieve_via_common_product,
        test_retrieve_84_matches_naclo,
        test_retrieve_no_match_returns_empty,
        test_list_all_count,
        test_get_by_id,
        test_alias_match,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"  ✗ 失败：{t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  ✗ 出错：{t.__name__}: {type(e).__name__}: {e}")

    print("\n===== 总结 =====")
    total = len(tests)
    print(f"通过 {total - failed}/{total} 项测试")
    if failed:
        print("存在失败项！")
        return 1
    print("全部测试通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
