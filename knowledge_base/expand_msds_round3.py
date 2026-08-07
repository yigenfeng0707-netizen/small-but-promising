"""
MSDS 知识库第三轮扩充：从 191 条扩充至 210+ 条。

运行方式：
    python knowledge_base/expand_msds_round3.py
"""
from __future__ import annotations

import json
import os
from collections import Counter

# 第三轮新增记录（25 条）
NEW_ENTRIES = [
    {"name": "柠檬烯", "onyms": ["Limonene", "柑橘精油成分", "d-柠檬烯"], "category": "清洁剂", "common_products": ["柑橘清洁剂", "天然溶剂"], "hazard_level": "低", "toxicity": "低毒，天然溶剂", "flammability": "易燃", "corrosivity": "无腐蚀", "allergy": "少数人可致皮炎", "environment": "可生物降解", "first_aid_ingestion": "饮清水稀释", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗10分钟", "first_aid_inhalation": "移至通风处", "storage": "避火储存", "green_alternatives": ["本身是天然成分"]},
    {"name": "芳樟醇", "onyms": ["Linalool", "精油成分"], "category": "化妆品", "common_products": ["香水", "护肤品", "洗发水"], "hazard_level": "低", "toxicity": "低毒", "flammability": "可燃", "corrosivity": "无腐蚀", "allergy": "少数人可致皮炎", "environment": "可生物降解", "first_aid_ingestion": "无需处理", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗", "first_aid_inhalation": "移至通风处", "storage": "密封储存", "green_alternatives": ["天然成分"]},
    {"name": "乙酸乙酯", "onyms": ["Ethyl acetate", "醋酸乙酯"], "category": "清洁剂", "common_products": ["洗甲水", "溶剂", "去胶剂"], "hazard_level": "低", "toxicity": "低毒，高浓度致中枢抑制", "flammability": "极易燃", "corrosivity": "无腐蚀", "allergy": "罕见", "environment": "可生物降解", "first_aid_ingestion": "勿催吐，就医", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗15分钟", "first_aid_inhalation": "移至通风处", "storage": "避火密封储存", "green_alternatives": ["水基溶剂"]},
    {"name": "乙二醇单丁醚", "onyms": ["Butyl cellosolve", "EGBE"], "category": "清洁剂", "common_products": ["玻璃水", "清洁剂", "涂料"], "hazard_level": "中", "toxicity": "中等毒性，刺激皮肤和呼吸道", "flammability": "可燃", "corrosivity": "低腐蚀", "allergy": "可致皮炎", "environment": "可生物降解", "first_aid_ingestion": "饮牛奶就医", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗15分钟", "first_aid_inhalation": "移至通风处", "storage": "阴凉密封储存", "green_alternatives": ["水基溶剂"]},
    {"name": "六偏磷酸钠", "onyms": ["SHMP", "磷酸钠聚合物"], "category": "清洁剂", "common_products": ["洗衣粉助洗剂", "水处理"], "hazard_level": "低", "toxicity": "低毒", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "罕见", "environment": "导致水体富营养化", "first_aid_ingestion": "饮清水稀释", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗", "first_aid_inhalation": "移至通风处", "storage": "干燥密封储存", "green_alternatives": ["沸石助洗剂"]},
    {"name": "4A 沸石", "onyms": ["4A Zeolite", "分子筛"], "category": "清洁剂", "common_products": ["无磷洗衣粉助洗剂", "水处理"], "hazard_level": "低", "toxicity": "低毒", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "罕见", "environment": "环境友好", "first_aid_ingestion": "无需处理", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗", "first_aid_inhalation": "移至通风处", "storage": "干燥密封储存", "green_alternatives": ["本身是绿色助洗剂"]},
    {"name": "蛋白酶", "onyms": ["Protease", "生物酶"], "category": "清洁剂", "common_products": ["加酶洗衣粉", "生物清洁剂"], "hazard_level": "低", "toxicity": "低毒，吸入致过敏", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "可致呼吸道过敏", "environment": "可生物降解", "first_aid_ingestion": "饮清水稀释", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗10分钟", "first_aid_inhalation": "移至通风处", "storage": "干燥储存", "green_alternatives": ["本身是绿色成分"]},
    {"name": "淀粉酶", "onyms": ["Amylase", "生物酶"], "category": "清洁剂", "common_products": ["加酶洗衣粉", "餐具清洁剂"], "hazard_level": "低", "toxicity": "低毒，吸入致过敏", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "可致呼吸道过敏", "environment": "可生物降解", "first_aid_ingestion": "饮清水稀释", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗10分钟", "first_aid_inhalation": "移至通风处", "storage": "干燥储存", "green_alternatives": ["本身是绿色成分"]},
    {"name": "脂肪酶", "onyms": ["Lipase", "生物酶"], "category": "清洁剂", "common_products": ["加酶洗衣粉", "厨房清洁剂"], "hazard_level": "低", "toxicity": "低毒，吸入致过敏", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "可致呼吸道过敏", "environment": "可生物降解", "first_aid_ingestion": "饮清水稀释", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗10分钟", "first_aid_inhalation": "移至通风处", "storage": "干燥储存", "green_alternatives": ["本身是绿色成分"]},
    {"name": "过一硫酸氢钾", "onyms": ["Potassium monopersulfate", "MPS"], "category": "消毒剂", "common_products": ["泳池消毒", "口腔消毒剂"], "hazard_level": "中", "toxicity": "中等毒性，强氧化性", "flammability": "不燃，但强氧化助燃", "corrosivity": "中等腐蚀", "allergy": "可致皮炎", "environment": "对水生生物有毒", "first_aid_ingestion": "饮牛奶就医", "first_aid_skin": "清水冲洗15分钟", "first_aid_eye": "清水冲洗15分钟就医", "first_aid_inhalation": "移至通风处", "storage": "密封干燥储存", "green_alternatives": ["紫外消毒"]},
    {"name": "复合季铵盐", "onyms": ["Dual quaternary ammonium", "复合单双链季铵盐"], "category": "消毒剂", "common_products": ["消毒喷雾", "环境消毒"], "hazard_level": "中", "toxicity": "中等毒性", "flammability": "不燃", "corrosivity": "低腐蚀", "allergy": "可致皮炎", "environment": "对水生生物有毒", "first_aid_ingestion": "饮牛奶就医", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗15分钟", "first_aid_inhalation": "移至通风处", "storage": "密封储存", "green_alternatives": ["高温消毒"]},
    {"name": "聚六亚甲基双胍", "onyms": ["PHMB", "聚己缩胍", "Polyhexamethylene biguanide"], "category": "消毒剂", "common_products": ["隐形眼镜护理液", "泳池消毒"], "hazard_level": "低", "toxicity": "低毒", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "少数人可致刺激", "environment": "对水生生物有一定影响", "first_aid_ingestion": "饮清水稀释", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗15分钟", "first_aid_inhalation": "移至通风处", "storage": "密封储存", "green_alternatives": ["本身即低毒消毒"]},
    {"name": "楝树油", "onyms": ["Neem oil", "印楝油", "苦楝油"], "category": "农药", "common_products": ["天然驱蚊剂", "植物源杀虫"], "hazard_level": "低", "toxicity": "低毒，植物源", "flammability": "可燃", "corrosivity": "低腐蚀", "allergy": "罕见", "environment": "环境友好", "first_aid_ingestion": "催吐就医", "first_aid_skin": "肥皂水冲洗", "first_aid_eye": "清水冲洗", "first_aid_inhalation": "移至通风处", "storage": "密封储存", "green_alternatives": ["本身是绿色农药"]},
    {"name": "氰戊菊酯", "onyms": ["Fenvalerate", "中西菊酯"], "category": "农药", "common_products": ["农业杀虫剂", "蚊香"], "hazard_level": "中", "toxicity": "中等毒性，拟除虫菊酯", "flammability": "可燃", "corrosivity": "低腐蚀", "allergy": "可致皮肤刺激", "environment": "对蜜蜂和水生生物剧毒", "first_aid_ingestion": "催吐就医", "first_aid_skin": "肥皂水冲洗", "first_aid_eye": "清水冲洗15分钟", "first_aid_inhalation": "移至通风处", "storage": "密封储存，远离蜜蜂", "green_alternatives": ["Bt 制剂"]},
    {"name": "炔螨特", "onyms": ["Propargite", "克螨特"], "category": "农药", "common_products": ["杀螨剂", "果树杀螨"], "hazard_level": "中", "toxicity": "中等毒性", "flammability": "可燃", "corrosivity": "低腐蚀", "allergy": "可致皮炎", "environment": "对水生生物有毒", "first_aid_ingestion": "催吐就医", "first_aid_skin": "肥皂水冲洗", "first_aid_eye": "清水冲洗15分钟", "first_aid_inhalation": "移至通风处", "storage": "密封储存", "green_alternatives": ["矿物油"]},
    {"name": "枯草芽孢杆菌制剂", "onyms": ["Bacillus subtilis", "生物农药"], "category": "农药", "common_products": ["生物杀菌剂", "有机农业"], "hazard_level": "低", "toxicity": "极低毒", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "罕见", "environment": "环境友好", "first_aid_ingestion": "无需处理", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗", "first_aid_inhalation": "移至通风处", "storage": "避光储存", "green_alternatives": ["本身是生物农药"]},
    {"name": "阿维菌素（兽药）", "onyms": ["Abamectin", "阿福丁", "虫克星"], "category": "药品", "common_products": ["宠物驱虫药", "兽药驱虫"], "hazard_level": "中", "toxicity": "中等毒性，注意剂量", "flammability": "可燃", "corrosivity": "低腐蚀", "allergy": "可致皮炎", "environment": "对水生生物和蜜蜂高毒", "first_aid_ingestion": "催吐就医", "first_aid_skin": "肥皂水冲洗", "first_aid_eye": "清水冲洗15分钟", "first_aid_inhalation": "移至通风处", "storage": "密封储存，远离鱼缸", "green_alternatives": ["按说明使用"]},
    {"name": "甲硝唑", "onyms": ["Metronidazole", "灭滴灵"], "category": "药品", "common_products": ["甲硝唑片", "牙科用药", "妇科用药"], "hazard_level": "低", "toxicity": "低毒，孕妇禁用", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "少数人可致皮疹", "environment": "诱导耐药", "first_aid_ingestion": "对症处理", "first_aid_skin": "无需处理", "first_aid_eye": "清水冲洗", "first_aid_inhalation": "无吸入风险", "storage": "避光密封储存", "green_alternatives": ["对症治疗"]},
    {"name": "克霉唑", "onyms": ["Clotrimazole", "抗真菌药"], "category": "药品", "common_products": ["克霉唑乳膏", "达克宁替代"], "hazard_level": "低", "toxicity": "低毒，外用安全", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "可致局部刺激", "environment": "常规使用无显著危害", "first_aid_ingestion": "就医", "first_aid_skin": "无需处理", "first_aid_eye": "清水冲洗", "first_aid_inhalation": "无需处理", "storage": "密封储存", "green_alternatives": ["茶树精油"]},
    {"name": "三氯新（TCS）", "onyms": ["Triclosan", "三氯生", "玉洁新DP300"], "category": "化妆品", "common_products": ["抗菌皂", "牙膏", "洗手液"], "hazard_level": "中", "toxicity": "中等毒性，内分泌干扰嫌疑", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "可致接触性皮炎", "environment": "持久污染，影响水生生物", "first_aid_ingestion": "饮清水稀释", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗10分钟", "first_aid_inhalation": "移至通风处", "storage": "密封储存", "green_alternatives": ["普通肥皂"]},
    {"name": "燕麦提取物", "onyms": ["Oat extract", "胶体燕麦", "Avena sativa"], "category": "化妆品", "common_products": ["舒缓面霜", "湿疹护理"], "hazard_level": "低", "toxicity": "极低毒", "flammability": "不燃", "corrosivity": "无腐蚀", "allergy": "罕见", "environment": "环境友好", "first_aid_ingestion": "无需处理", "first_aid_skin": "无需处理", "first_aid_eye": "清水冲洗", "first_aid_inhalation": "无需处理", "storage": "密封储存", "green_alternatives": ["天然成分"]},
    {"name": "聚山梨醇酯", "onyms": ["Polysorbate", "吐温", "Tween"], "category": "化妆品", "common_products": ["乳化剂", "护肤品", "洗发水"], "hazard_level": "低", "toxicity": "低毒", "flammability": "可燃", "corrosivity": "无腐蚀", "allergy": "罕见", "environment": "可生物降解", "first_aid_ingestion": "无需处理", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗", "first_aid_inhalation": "移至通风处", "storage": "常温储存", "green_alternatives": ["天然乳化剂"]},
    {"name": "茚三酮", "onyms": ["Ninhydrin", "水合茚三酮"], "category": "其他", "common_products": ["指纹显现", "氨基酸检测"], "hazard_level": "中", "toxicity": "中等毒性，刺激皮肤", "flammability": "可燃", "corrosivity": "低腐蚀", "allergy": "可致皮炎", "environment": "对水生生物有害", "first_aid_ingestion": "饮牛奶就医", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗15分钟", "first_aid_inhalation": "移至通风处", "storage": "避光密封储存", "green_alternatives": ["无"]},
    {"name": "氟化物", "onyms": ["Fluoride", "氟化钠", "Sodium fluoride"], "category": "其他", "common_products": ["含氟牙膏", "饮用水加氟"], "hazard_level": "中", "toxicity": "中等毒性，过量致氟斑牙和氟骨症", "flammability": "不燃", "corrosivity": "低腐蚀", "allergy": "罕见", "environment": "高浓度影响水生生物", "first_aid_ingestion": "过量饮牛奶补钙，就医", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗15分钟", "first_aid_inhalation": "移至通风处", "storage": "密封储存", "green_alternatives": ["适量使用"]},
    {"name": "硫酸铝", "onyms": ["Alum", "明矾", "Aluminum sulfate"], "category": "其他", "common_products": ["净水剂", "食品添加剂"], "hazard_level": "低", "toxicity": "低毒，铝摄入争议", "flammability": "不燃", "corrosivity": "低腐蚀", "allergy": "罕见", "environment": "铝离子污染", "first_aid_ingestion": "饮清水稀释", "first_aid_skin": "清水冲洗", "first_aid_eye": "清水冲洗", "first_aid_inhalation": "移至通风处", "storage": "密封储存", "green_alternatives": ["无铝添加剂"]},
]


def main() -> None:
    """主函数：加载、扩充、去重、保存。"""
    data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "msds_data.json")
    if not os.path.exists(data_path):
        data_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "knowledge_base", "msds_data.json")

    with open(data_path, "r", encoding="utf-8") as f:
        existing_data: list[dict] = json.load(f)

    existing_names = {item.get("name", "").strip() for item in existing_data if item.get("name")}
    print(f"现有条目: {len(existing_data)} 条")
    print(f"准备新增: {len(NEW_ENTRIES)} 条")

    # 过滤重复
    new_entries_filtered = []
    for entry in NEW_ENTRIES:
        name = entry.get("name", "").strip()
        if name and name not in existing_names:
            entry["id"] = f"msds_{len(existing_data) + len(new_entries_filtered) + 1:03d}"
            new_entries_filtered.append(entry)
            existing_names.add(name)

    print(f"去重后新增: {len(new_entries_filtered)} 条")

    # 合并
    expanded_data = existing_data + new_entries_filtered

    # 保存
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(expanded_data, f, ensure_ascii=False, indent=2)

    print(f"扩充后总数: {len(expanded_data)} 条")

    # 统计
    categories = Counter(item.get("category", "未知") for item in expanded_data)
    print("\n类别分布:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} 条")

    hazard_levels = Counter(item.get("hazard_level", "未知") for item in expanded_data)
    print("\n危险等级分布:")
    for level, count in sorted(hazard_levels.items()):
        print(f"  {level}: {count} 条")


if __name__ == "__main__":
    main()
