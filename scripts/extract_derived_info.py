import csv
import sys
import json
import random
import warnings
from collections import defaultdict
from fractions import Fraction
from itertools import groupby
from operator import itemgetter
from pathlib import Path

import yaml
import humanize
import networkx as nx
import matplotlib.pyplot as plt
from tqdm import tqdm

# TODO: decide filtering mechanics, currently just filtering based on tdata, but previously valid objects are also filtered out
SEP = "::"
WORLD_INSTANCE_ID = 0
NPC_ID_OFFSET = 1
MOB_ID_OFFSET = 10000
MOB_GROUP_ID_OFFSET = 20000
TILE_WIDTH = 51200
ITEM_TYPES = [
    "Weapon",
    "Body",
    "Legs",
    "Shoes",
    "Hat",
    "Glasses",
    "Backpack",
    "General",
    "None",
    "CRATE",
    "Vehicle",
]
WEAPON_TYPES = [
    "None",
    "Melee",
    "Pistol",
    "Shattergun",
    "Rifle",
    "Rocket",
    "Thrown",
]
WEAPON_RANGES = [
    "None",
    "Short",
    "Medium",
    "Medium",
    "Medium",
    "Long",
    "Medium",
]
ITEM_TABLES = [
    "m_pWeaponItemTable",
    "m_pShirtsItemTable",
    "m_pPantsItemTable",
    "m_pShoesItemTable",
    "m_pHatItemTable",
    "m_pGlassItemTable",
    "m_pBackItemTable",
    "m_pGeneralItemTable",
    "",
    "m_pChestItemTable",
    "m_pVehicleItemTable",
]
ITEM_ICON_PREFIXES = [
    "wpnicon",
    "cosicon",
    "cosicon",
    "cosicon",
    "cosicon",
    "cosicon",
    "cosicon",
    "generalitemicon",
    "error",
    "generalitemicon",
    "vehicle",
]
NPC_ICON_PREFIXES = [
    "error",
    "error",
    "error",
    "error",
    "npcicon",
    "error",
    "error",
    "error",
    "mobicon",
    "error",
    "hnpcicon",
]
RARITIES = [
    "Any",
    "Common",
    "Uncommon",
    "Rare",
    "Ultra Rare",
    "Amazing!",
]
GENDERS = [
    "Any",
    "Male",
    "Female",
]
INT_KEY_MAP = {
    "Racing": "EPID",
    "NanoCapsules": "Nano",
    "CodeItems": "Code",
}
INT_LOWER_BOUND_MAP = {
    "Crates": 0,
}
FK_MAP_NAMES = {
    "Rewards": "Crates",
}
FOREIGN_KEY_MAP = {
    "CrateDropTypes": [
        "CrateIDs",
    ],
    "MobDrops": [
        "CrateDropChanceID",
        "CrateDropTypeID",
        "MiscDropChanceID",
        "MiscDropTypeID",
    ],
    "Events": [
        "MobDropID",
    ],
    "Mobs": [
        "MobDropID",
    ],
    "ItemSets": [
        "ItemReferenceIDs",
    ],
    "Crates": [
        "ItemSetID",
        "RarityWeightID",
    ],
    "Racing": [
        "Rewards",
    ],
    "NanoCapsules": [
        "CrateID",
    ],
    "CodeItems": [
        "ItemReferenceIDs",
    ],
}
NPC_TYPES = {
    0: "Monster",
    1: "Normal",
    2: "Vendor",
    3: "Quest",
    4: "VendorQuest",
    5: "Warp",
    6: "Defense",
    7: "NanoCreateMachine",
    8: "NanoTuneMachine",
    9: "NanoManager",
    10: "Xcom",
    11: "IXcom",
    12: "Bank",
    13: "StartEcom",
    14: "EndEcom",
    15: "SCAMPER",
    16: "MonkeySkyway",
    17: "RXcom",
    18: "Guide1",
    19: "Guide2",
    20: "Guide3",
    21: "Guide4",
    22: "Guide5",
    23: "GuideStarter",
    24: "Offer",
    25: "NoReaction",
    26: "Combi",
    27: "Enchant",
    100: "Invisible",
    101: "InvisibleWarp",
    105: "InvisibleNoClick",
    110: "NonCheck",
    111: "Location",
}
MISSION_TYPES = [
    "None",
    "Guide",
    "Nano",
    "Normal",
]
MISSION_TASK_TYPES = [
    "None",
    "Talk",
    "GoToLocation",
    "UseItems",
    "Delivery",
    "Defeat",
    "EscortDefense",
]
MISSION_DIFFICULTY_TYPES = [
    "Easy",
    "Normal",
    "Hard",
]
MISSION_GUIDE_TYPES = [
    "None",
    "Edd",
    "Dexter",
    "Mojo Jojo",
    "Ben",
    "Computress",
]
MISSION_MESSAGE_TYPES = {
    2: "PopUp",
    4: "Email",
    6: "PopUpAndEmail",
}
NANO_MOB_TYPES = [
    "Adaptium",
    "Blastons",
    "Cosmix",
]
EVENT_TYPES = {
    0: "None",
    1: "Knishmas",
    2: "Halloween",
    3: "Easter",
}
TRANSPORTATION_MOVE_TYPES = [
    "None",
    "SCAMPER",
    "MonkeySkyway",
    "Slider",
]
SOURCE_TYPE_ID_FIELD_MAP = {
    "CodeItem": "Code",
    "Vendor": "NPCTypeID",
    "Egg": "EggTypeID",
    "Racing": "InstanceID",
    "Mob": "MobTypeID",
    "Event": "EventID",
    "MissionReward": "MissionID",
    "MissionRewardCrate": "MissionID",
}
SOURCE_TYPE_NAME_FIELD_MAP = {
    "Vendor": "NPCName",
    "Egg": "EggName",
    "Racing": "InstanceName",
    "Mob": "MobName",
    "Event": "EventName",
    "MissionReward": "MissionName",
    "MissionRewardCrate": "MissionName",
}


def patch(base_obj: dict, patch_obj: dict) -> None:
    for key, value in patch_obj.items():
        if key[0] == "!":
            base_obj[key[1:]] = value
            continue

        if key in base_obj:
            if value is None:
                del base_obj[key]
            elif not isinstance(value, (dict, list)):
                base_obj[key] = value
            elif isinstance(value, list):
                base_obj[key].extend(value)
            else:
                patch(base_obj[key], value)
        else:
            base_obj[key] = value


def get_patched(server_data_dir: Path, name: str, patch_names: list[str]) -> dict:
    with open(server_data_dir / f"{name}.json") as r:
        base_obj = json.load(r)

    for patch_name in patch_names:
        patch_path = server_data_dir / "patch" / patch_name / f"{name}.json"

        if patch_path.is_file():
            with open(patch_path) as r:
                patch_obj = json.load(r)

            patch(base_obj, patch_obj)

    return base_obj


def mapify_drops(drops: dict[str, dict[str, dict]]) -> dict[str, dict[int | str, dict]]:
    drop_maps = {}

    for key in drops:
        real_key = INT_KEY_MAP.get(key, key[:-1] + "ID")
        drop_maps[key] = {obj[real_key]: obj for obj in drops[key].values()}

    return drop_maps


def locate_coordinates(area_info: dict, x: int, y: int) -> dict:
    for area_obj_list in area_info.values():
        for area_obj in area_obj_list:
            if (area_obj["X"] <= x <= area_obj["X"] + area_obj["Width"] and
                area_obj["Y"] <= y <= area_obj["Y"] + area_obj["Height"]):
                return area_obj
    return {"AreaName": "Unknown", "ZoneName": "Unknown"}


def to_area_tag(area_obj: dict) -> str:
    return "{AreaName} - {ZoneName}".format(**area_obj)


def construct_drop_directory_data(sources: dict[str, dict], server_data_dir: Path, patch_names: list[str]) -> None:
    sources["mobs"] = get_patched(server_data_dir, "mobs", patch_names)
    sources["drops"] = get_patched(server_data_dir, "drops", patch_names)
    sources["eggs"] = get_patched(server_data_dir, "eggs", patch_names)
    sources["npcs"] = get_patched(server_data_dir, "NPCs", patch_names)
    sources["paths"] = get_patched(server_data_dir, "paths", patch_names)

    sources["drops_map"] = mapify_drops(sources["drops"])
    sources["references"] = defaultdict(set)

    for alt_key, alt_dict in sources["drops_map"].items():
        lowest_id = INT_LOWER_BOUND_MAP.get(alt_key, -1)

        for int_key, data in alt_dict.items():
            for fk_type in FOREIGN_KEY_MAP.get(alt_key, []):
                fk_list = (
                    [data[fk_type]]
                    if isinstance(data[fk_type], int)
                    else data[fk_type]
                )

                for fk_id in fk_list:
                    if fk_id <= lowest_id:
                        continue

                    fk_main_key = FK_MAP_NAMES.get(
                        fk_type, fk_type.split("ID")[0] + "s"
                    )
                    sources["references"][(fk_main_key, fk_id)].add(
                        (alt_key, int_key)
                    )


def construct_area_data(sources: dict) -> None:
    sources["area_info"] = defaultdict(list)

    for region_obj in sources["areas"]:
        area_str = "{DongName} - {ZoneName}".format(**region_obj)

        sources["area_info"][area_str].append({
            "X": int(region_obj["Area"]["x"] * 100),
            "Y": int(region_obj["Area"]["y"] * 100),
            "Width": int(region_obj["Area"]["width"] * 100),
            "Height": int(region_obj["Area"]["height"] * 100),
            "AreaName": region_obj["DongName"],
            "ZoneName": region_obj["ZoneName"],
            "NPCTypes": {},
            "MobTypes": {},
            "EggTypes": {},
            "NPCs": {},
            "Mobs": {},
            "Eggs": {},
            "Vendors": {},
            "InstanceWarps": {},
            "Transportation": {},
            "InfectedZone": None,
        })


def construct_item_info_data(sources: dict[str, dict]) -> None:
    sources["item_info"] = {}

    for i, item_table in enumerate(ITEM_TABLES):
        if i == 8:
            continue

        item_table_obj = sources["xdt"][item_table]
        item_data_list = item_table_obj["m_pItemData"]
        item_string_list = item_table_obj["m_pItemStringData"]
        item_icon_list = item_table_obj["m_pItemIconData"]

        for obj in item_data_list[1:]:
            item_id = obj["m_iItemNumber"]
            weapon_type_id = obj.get("m_iTargetMode", 0)
            str_id = f"{i:02d}{SEP}{item_id:04d}"
            icon_id = obj["m_iIcon"]
            icon_obj = item_icon_list[icon_id] if icon_id < len(item_icon_list) else None
            str_obj = item_string_list[obj["m_iItemName"]]
            name = str_obj["m_strName"]
            comment_key = "m_iComment" if i != 9 else "m_iChestDesc"
            description = item_string_list[obj[comment_key]]["m_strComment"]

            if i in [7, 9]:
                rarity_id = 1
                gender_id = 0
                required_level = 0
                single_damage = 0
                multi_damage = 0
                fire_initial_time = 0
                fire_deliver_time = 0
                fire_delay_time = 0
                fire_duration_time = 0
                range_value = 0
                angle_value = 0
                number_of_targets = 0
                defense = 0
                vehicle_class = 0
            else:
                rarity_id = obj["m_iRarity"]
                gender_id = obj["m_iReqSex"]
                required_level = obj["m_iMinReqLev"]
                single_damage = obj["m_iPointRat"]
                multi_damage = obj["m_iGroupRat"]
                fire_initial_time = obj["m_iInitalTime"] * 0.1
                fire_deliver_time = obj["m_iDeliverTime"] * 0.1
                fire_delay_time = obj["m_iDelayTime"] * 0.1
                fire_duration_time = obj["m_iDurationTime"] * 0.1
                range_value = obj["m_iAtkRange"]
                angle_value = obj["m_iAtkAngle"]
                number_of_targets = obj["m_iTargetNumber"]
                defense = obj["m_iDefenseRat"]
                vehicle_class = obj["m_iUp_runSpeed"]

            content_level = required_level

            if i == 9:
                description = str_obj["m_strComment"]

                try:
                    content_level = int(name.split("Lv")[0])
                except:
                    pass

            sources["item_info"][str_id] = {
                "ID": str_id,
                "ItemID": item_id,
                "TypeID": i,
                "Type": ITEM_TYPES[i],
                "WeaponTypeID": weapon_type_id,
                "WeaponType": WEAPON_TYPES[weapon_type_id],
                "DisplayType": ITEM_TYPES[i] if i > 0 else WEAPON_TYPES[weapon_type_id],
                "Tradeable": obj["m_iTradeAble"] == 1,
                "Sellable": obj["m_iSellAble"] == 1,
                "ItemPrice": obj["m_iItemPrice"],
                "ItemSellPrice": obj["m_iItemSellPrice"],
                "MaxStack": obj["m_iStackNumber"],
                "RarityID": rarity_id,
                "Rarity": RARITIES[rarity_id],
                "GenderID": gender_id,
                "Gender": GENDERS[gender_id],
                "RequiredLevel": required_level,
                "ContentLevel": content_level,
                "SingleDamage": single_damage,
                "MultiDamage": multi_damage,
                "FireInitialTime": fire_initial_time,
                "FireDeliverTime": fire_deliver_time,
                "FireDelayTime": fire_delay_time,
                "FireDurationTime": fire_duration_time,
                "RateOfFire": 1 / fire_delay_time if fire_delay_time > 0 else 0.0,
                "RangeValue": range_value,
                "Range": WEAPON_RANGES[weapon_type_id],
                "ConeAngle": angle_value,
                "NumberOfTargets": number_of_targets,
                "Defense": defense,
                "VehicleClass": vehicle_class,
                "Name": name,
                "Description": description,
                "Icon": f"icons/{ITEM_ICON_PREFIXES[i]}_{icon_obj['m_iIconNumber']:02d}.png" if icon_obj else "icons/error_00.png",
            }


def construct_npc_mob_info_data(sources: dict[str, dict]) -> None:
    sources["npc_type_info"] = {}
    sources["mob_type_info"] = {}
    sources["npc_mob_type_info"] = {}
    sources["npc_info"] = defaultdict(dict)
    sources["mob_info"] = defaultdict(dict)
    sources["npc_mob_info"] = defaultdict(dict)

    vendor_table_obj = sources["xdt"]["m_pVendorTable"]
    vendor_item_list = vendor_table_obj["m_pItemData"]

    npc_table_obj = sources["xdt"]["m_pNpcTable"]
    npc_data_list = npc_table_obj["m_pNpcData"]
    npc_string_list = npc_table_obj["m_pNpcStringData"]
    npc_icon_list = npc_table_obj["m_pNpcIconData"]
    npc_barker_list = npc_table_obj["m_pNpcBarkerData"]
    npc_service_list = npc_table_obj["m_pNpcServiceData"]

    skill_table_obj = sources["xdt"]["m_pSkillTable"]
    skill_data_list = skill_table_obj["m_pSkillData"]
    skill_string_list = skill_table_obj["m_pSkillStringData"]
    skill_icon_list = skill_table_obj["m_pSkillIconData"]

    mission_table_obj = sources["xdt"]["m_pMissionTable"]
    mission_data_list = mission_table_obj["m_pMissionData"]
    mission_string_list = mission_table_obj["m_pMissionStringData"]

    vendor_item_map = defaultdict(list)

    for vendor_item_obj in vendor_item_list[1:]:
        npc_type_id = vendor_item_obj["m_iNpcNumber"]
        item_str_id = f"{vendor_item_obj['m_iItemType']:02d}{SEP}{vendor_item_obj['m_iitemID']:04d}"

        if item_str_id not in sources["item_info"]:
            continue

        item_info_obj = sources["item_info"][item_str_id]

        vendor_item_map[npc_type_id].append({
            "ItemInfo": item_info_obj,
            "NPCTypeID": npc_type_id,
            "SortNumber": vendor_item_obj["m_iSortNumber"],
            "BuyPrice": item_info_obj.get("ItemPrice", vendor_item_obj["m_iSellCost"]),
        })

    for npc_type_id, npc_data in enumerate(npc_data_list):
        if npc_type_id == 0:
            continue

        npc_name_obj = npc_string_list[npc_data["m_iNpcName"]]
        npc_name = npc_name_obj["m_strName"]
        npc_comment_obj = npc_string_list[npc_data["m_iComment"]]
        npc_comment = npc_comment_obj["m_strComment"]

        mob_icon_obj = npc_icon_list[npc_data["m_iIcon1"]]
        npc_icon_type = max(0, mob_icon_obj["m_iIconType"]) % len(NPC_ICON_PREFIXES)
        npc_icon_number = mob_icon_obj["m_iIconNumber"]
        icon_name = f"icons/{NPC_ICON_PREFIXES[npc_icon_type]}_{npc_icon_number:02d}.png"

        barker_obj = npc_barker_list[npc_data["m_iBarkerNumber"]]

        eruption_skill_obj = skill_data_list[npc_data["m_iMegaType"]]
        corruption_skill_obj = skill_data_list[npc_data["m_iCorruptionType"]]
        active_skill_obj = skill_data_list[npc_data["m_iActiveSkill1"]]
        support_skill_obj = skill_data_list[npc_data["m_iSupportSkill"]]
        passive_skill_obj = skill_data_list[npc_data["m_iPassiveBuff"]]

        npc_info_dict = {
            "ID": npc_type_id,
            "Name": npc_name,
            "Comment": npc_comment,
            "Icon": icon_name,
            "CategoryID": npc_data["m_iNpcType"],
            "Category": NPC_TYPES.get(npc_data["m_iNpcType"], "Unknown"),
            "Height": npc_data["m_iHeight"],
            "Scale": npc_data["m_fScale"],
        }

        if npc_data["m_iNpcType"] == 0:
            sources["mob_type_info"][npc_type_id] = {
                **npc_info_dict,
                "Level": npc_data["m_iNpcLevel"],
                "ColorTypeID": npc_data["m_iNpcStyle"],
                "ColorType": NANO_MOB_TYPES[npc_data["m_iNpcStyle"]],
                "StandardHP": npc_data["m_iHP"],
                "RespawnSeconds": npc_data["m_iRegenTime"] * 0.1,
                "RespawnTime": humanize.precisedelta(npc_data["m_iRegenTime"] * 0.1),
                "WalkSpeed": npc_data["m_iWalkSpeed"],
                "RunSpeed": npc_data["m_iRunSpeed"],
                "SightRange": npc_data["m_iSightRange"],
                "IdleRange": npc_data["m_iIdleRange"],
                "CombatRange": npc_data["m_iCombatRange"],
                "AttackRange": npc_data["m_iAtkRange"],
                "Radius": npc_data["m_iRadius"],
                "Power": npc_data["m_iPower"],
                "AttackPower": 450 + npc_data["m_iPower"],
                "Accuracy": npc_data["m_iAccuracy"],
                "Protection": npc_data["m_iProtection"],
                "FireInitialTime": npc_data["m_iInitalTime"],
                "FireDeliverTime": npc_data["m_iDeliverTime"],
                "FireDelayTime": npc_data["m_iDelayTime"],
                "FireDurationTime": npc_data["m_iDurationTime"],
                "EruptionTypeID": npc_data["m_iMegaType"],
                "EruptionTypeProb": npc_data["m_iMegaTypeProb"],
                "EruptionRange": eruption_skill_obj["m_iEffectRange"],
                "EruptionArea": eruption_skill_obj["m_iEffectArea"],
                "CorruptionTypeID": npc_data["m_iCorruptionType"],
                "CorruptionTypeProb": npc_data["m_iCorruptionTypeProb"],
                "CorruptionRange": corruption_skill_obj["m_iEffectRange"],
                "CorruptionAngle": corruption_skill_obj["m_iEffectAngle"],
                "ActiveSkillID": npc_data["m_iActiveSkill1"],
                "ActiveSkillProb": npc_data["m_iActiveSkill1Prob"],
                "ActiveSkillRange": active_skill_obj["m_iEffectRange"],
                "ActiveSkillAngle": active_skill_obj["m_iEffectAngle"],
                "ActiveSkillArea": active_skill_obj["m_iEffectArea"],
                "ActiveSkill": skill_string_list[active_skill_obj["m_iSkillNumber"]]["m_strName"],
                "ActiveSkillIcon": f"icons/skillicon_{skill_icon_list[active_skill_obj['m_iIcon']]['m_iIconNumber']:02d}.png",
                "SupportSkillID": npc_data["m_iSupportSkill"],
                "SupportSkillRange": support_skill_obj["m_iEffectRange"],
                "SupportSkill": skill_string_list[support_skill_obj["m_iSkillNumber"]]["m_strName"],
                "SupportSkillIcon": f"icons/skillicon_{skill_icon_list[support_skill_obj['m_iIcon']]['m_iIconNumber']:02d}.png",
                "PassiveBuffID": npc_data["m_iPassiveBuff"],
                "PassiveBuff": skill_string_list[passive_skill_obj["m_iSkillNumber"]]["m_strName"],
                "PassiveBuffIcon": f"icons/skillicon_{skill_icon_list[passive_skill_obj['m_iIcon']]['m_iIconNumber']:02d}.png",
            }
            sources["npc_mob_type_info"][npc_type_id] = sources["mob_type_info"][npc_type_id]
        else:
            sources["npc_type_info"][npc_type_id] = {
                **npc_info_dict,
                "VendorItems": vendor_item_map.get(npc_type_id, []),
                "HNPCTypeID": npc_data["m_iHNpcNum"],
                "BarkerNumber": npc_data["m_iBarkerNumber"],
                "Barkers": [
                    barker_obj["m_strName"],
                    barker_obj["m_strComment"],
                    barker_obj["m_strComment1"],
                    barker_obj["m_strComment2"],
                ],
                "BarkerType": npc_data["m_iBarkerType"],
                "MissionBarkers": (
                    {}
                    if npc_data["m_iBarkerType"] not in range(1, 5)
                    else {
                        f"{mission_obj['m_iHMissionID']:04d}{SEP}{mission_string_list[mission_obj['m_iHMissionName']]['m_pstrNameString']}": mission_string_list[mission_barker_id]["m_pstrNameString"]
                        for mission_obj in mission_data_list
                        if (mission_barker_id := mission_obj["m_iHBarkerTextID"][npc_data["m_iBarkerType"] - 1]) > 0
                    }
                ),
                "ServiceNumber": npc_data["m_iServiceNumber"],
                "ServiceString": npc_service_list[npc_data["m_iServiceNumber"]]["m_strService"],
            }
            sources["npc_mob_type_info"][npc_type_id] = sources["npc_type_info"][npc_type_id]

    for npc_str_key, npc_obj in sources["npcs"]["NPCs"].items():
        npc_id = int(npc_str_key) + NPC_ID_OFFSET
        npc_type_id = npc_obj["iNPCType"]

        if npc_type_id not in sources["npc_type_info"]:
            continue

        sources["npc_info"][npc_type_id][str(npc_id)] = {
            "ID": str(npc_id),
            "TypeID": npc_type_id,
            "TypeName": sources["npc_type_info"][npc_type_id]["Name"],
            "TypeIcon": sources["npc_type_info"][npc_type_id]["Icon"],
            "X": npc_obj["iX"],
            "Y": npc_obj["iY"],
            "Z": npc_obj["iZ"],
            "Angle": npc_obj["iAngle"],
            "InstanceID": npc_obj.get("iMapNum", 0),
            "AreaZone": to_area_tag(locate_coordinates(sources["area_info"], npc_obj["iX"], npc_obj["iY"])),
        }
        sources["npc_mob_info"][npc_type_id][str(npc_id)] = sources["npc_info"][npc_type_id][str(npc_id)]

    for mob_category in ["mobs", "groups"]:
        offset = MOB_ID_OFFSET if mob_category == "mobs" else MOB_GROUP_ID_OFFSET

        for mob_str_key, mob_obj in sources["mobs"][mob_category].items():
            mob_id = int(mob_str_key) + offset
            mob_type_id = mob_obj["iNPCType"]

            if mob_type_id not in sources["mob_type_info"]:
                continue

            sources["mob_info"][mob_type_id][str(mob_id)] = {
                "ID": str(mob_id),
                "TypeID": mob_type_id,
                "TypeName": sources["mob_type_info"][mob_type_id]["Name"],
                "TypeIcon": sources["mob_type_info"][mob_type_id]["Icon"],
                "FollowsMobID": "",
                "HP": mob_obj.get("iHP", sources["mob_type_info"][mob_type_id]["StandardHP"]),
                "X": mob_obj["iX"],
                "Y": mob_obj["iY"],
                "Z": mob_obj["iZ"],
                "Angle": mob_obj["iAngle"],
                "InstanceID": mob_obj.get("iMapNum", 0),
                "AreaZone": to_area_tag(locate_coordinates(sources["area_info"], mob_obj["iX"], mob_obj["iY"])),
            }
            sources["npc_mob_info"][mob_type_id][str(mob_id)] = sources["mob_info"][mob_type_id][str(mob_id)]

            if "aFollowers" not in mob_obj:
                continue

            for i, follower_obj in enumerate(mob_obj["aFollowers"]):
                follower_mob_type_id = follower_obj["iNPCType"]

                if follower_mob_type_id not in sources["mob_type_info"]:
                    continue

                str_follower_id = f"{mob_id}:follower_{i + 1}"
                sources["mob_info"][follower_mob_type_id][str_follower_id] = {
                    "ID": str_follower_id,
                    "TypeID": follower_mob_type_id,
                    "TypeName": sources["mob_type_info"][follower_mob_type_id]["Name"],
                    "TypeIcon": sources["mob_type_info"][follower_mob_type_id]["Icon"],
                    "FollowsMobID": mob_id,
                    "HP": follower_obj.get("iHP", sources["mob_type_info"][follower_mob_type_id]["StandardHP"]),
                    "X": mob_obj["iX"] + follower_obj["iOffsetX"],
                    "Y": mob_obj["iY"] + follower_obj["iOffsetY"],
                    "Z": mob_obj["iZ"],
                    "Angle": mob_obj["iAngle"],
                    "InstanceID": mob_obj.get("iMapNum", 0),
                    "AreaZone": to_area_tag(locate_coordinates(sources["area_info"], mob_obj["iX"], mob_obj["iY"])),
                }
                sources["npc_mob_info"][follower_mob_type_id][str_follower_id] = sources["mob_info"][follower_mob_type_id][str_follower_id]


def construct_egg_data(sources: dict[str, dict]) -> None:
    sources["egg_type_info"] = {}
    sources["egg_info"] = defaultdict(dict)

    egg_data_dict = sources["eggs"]
    egg_type_data_obj = egg_data_dict["EggTypes"]
    egg_data_obj = egg_data_dict["Eggs"]

    egg_string_data_list = sources["xdt"]["m_pShinyTable"]["m_pShinyStringData"]

    skill_table_obj = sources["xdt"]["m_pSkillTable"]
    skill_data_list = skill_table_obj["m_pSkillData"]
    skill_string_list = skill_table_obj["m_pSkillStringData"]
    skill_icon_list = skill_table_obj["m_pSkillIconData"]
    for egg_type_obj in egg_type_data_obj.values():
        egg_type_id = egg_type_obj["Id"]
        egg_type_string_obj = egg_string_data_list[egg_type_id]
        egg_effect_id = egg_type_obj["EffectId"]
        egg_skill_obj = skill_data_list[egg_effect_id]
        egg_crate_id = egg_type_obj["DropCrateId"]
        egg_crate_item_str_id = f"09{SEP}{egg_crate_id:04d}"

        sources["egg_type_info"][egg_type_id] = {
            "ID": egg_type_id,
            "Name": egg_type_string_obj["m_strName"],
            "Comment": egg_type_string_obj["m_strComment"],
            "ExtraComment": egg_type_string_obj["m_strComment1"],
            "CrateID": egg_crate_id,
            "CrateItemID": egg_crate_item_str_id,
            "Crate": sources["item_info"].get(egg_crate_item_str_id),
            "EffectID": egg_effect_id,
            "Effect": skill_string_list[egg_effect_id]["m_strName"],
            "EffectIcon": f"icons/skillicon_{skill_icon_list[egg_skill_obj['m_iIcon']]['m_iIconNumber']:02d}.png",
            "EffectDuration": egg_type_obj["Duration"],
            "RespawnSeconds": egg_type_obj["Regen"],
            "RespawnTime": humanize.precisedelta(egg_type_obj["Regen"]),
        }

    for egg_str_key, egg_obj in egg_data_obj.items():
        egg_id = int(egg_str_key)
        egg_type_id = egg_obj["iType"]

        if egg_type_id not in sources["egg_type_info"]:
            continue

        sources["egg_info"][egg_type_id][str(egg_id)] = {
            "ID": str(egg_id),
            "TypeID": egg_type_id,
            "TypeName": sources["egg_type_info"][egg_type_id]["Name"],
            "TypeComment": sources["egg_type_info"][egg_type_id]["Comment"],
            "TypeExtraComment": sources["egg_type_info"][egg_type_id]["ExtraComment"],
            "X": egg_obj["iX"],
            "Y": egg_obj["iY"],
            "Z": egg_obj["iZ"],
            "InstanceID": egg_obj.get("iMapNum", 0),
            "AreaZone": to_area_tag(locate_coordinates(sources["area_info"], egg_obj["iX"], egg_obj["iY"])),
        }


def construct_mission_data(sources: dict[str, dict]) -> None:
    sources["mission_info"] = {}

    mission_table_obj = sources["xdt"]["m_pMissionTable"]
    mission_data_list = mission_table_obj["m_pMissionData"]
    mission_task_groupped_list = {
        mission_id: list(task_iter)
        for mission_id, task_iter in groupby(
            sorted(mission_data_list[1:], key=itemgetter("m_iHMissionID", "m_iHTaskID")),
            key=itemgetter("m_iHMissionID"),
        )
    }
    mission_task_dict = {obj["m_iHTaskID"]: obj for obj in mission_data_list}
    mission_string_list = mission_table_obj["m_pMissionStringData"]
    mission_journal_data_list = mission_table_obj["m_pJournalData"]
    mission_reward_data_list = mission_table_obj["m_pRewardData"]

    npc_table_obj = sources["xdt"]["m_pNpcTable"]
    npc_data_list = npc_table_obj["m_pNpcData"]
    npc_string_list = npc_table_obj["m_pNpcStringData"]

    warp_name_data_list = sources["xdt"]["m_pInstanceTable"]["m_pWarpNameData"]

    nano_table_obj = sources["xdt"]["m_pNanoTable"]
    nano_data_list = nano_table_obj["m_pNanoData"]
    nano_string_list = nano_table_obj["m_pNanoStringData"]

    quest_item_table_obj = sources["xdt"]["m_pQuestItemTable"]
    quest_item_data_list = quest_item_table_obj["m_pItemData"]
    quest_item_string_list = quest_item_table_obj["m_pItemStringData"]

    for mission_id, task_list in mission_task_groupped_list.items():
        mission_obj = task_list[0]
        task_required_nano_id = mission_obj["m_iCSTRReqNano"][0]
        task_required_nano_obj = nano_data_list[task_required_nano_id]
        task_end_nano_id = mission_obj["m_iSTNanoID"]
        task_end_nano_obj = nano_data_list[task_end_nano_id]
        task_journal_npc_id = mission_obj["m_iHJournalNPCID"]

        if task_journal_npc_id in sources["npc_mob_type_info"]:
            task_journal_npc_obj = sources["npc_mob_type_info"][task_journal_npc_id]
            task_journal_npc_name = task_journal_npc_obj["Name"]
            task_journal_npc_icon = task_journal_npc_obj["Icon"]

        mission_info_obj = {
            "ID": mission_id,
            "TypeID": mission_obj["m_iHMissionType"],
            "Type": MISSION_TYPES[mission_obj["m_iHMissionType"]],
            "Name": mission_string_list[mission_obj["m_iHMissionName"]]["m_pstrNameString"].replace("\n", " "),
            "DifficultyID": mission_obj["m_iHDifficultyType"],
            "Difficulty": MISSION_DIFFICULTY_TYPES[mission_obj["m_iHDifficultyType"]],
            "MissionStartNPCID": 0,
            "MissionStartNPCName": "",
            "MissionStartNPCIcon": "",
            "MissionEndNPCID": 0,
            "MissionEndNPCName": "",
            "MissionEndNPCIcon": "",
            "MissionJournalNPCID": task_journal_npc_id,
            "MissionJournalNPCName": task_journal_npc_name,
            "MissionJournalNPCIcon": task_journal_npc_icon,
            "Level": mission_obj["m_iCTRReqLvMin"],
            "RequiredNanoID": task_required_nano_id,
            "RequiredNano": (
                "{m_strName} - {m_strComment1}".format(**nano_string_list[task_required_nano_obj["m_iNanoName"]])
                if task_required_nano_id > 0
                else "None"
            ),
            "RequiredGuideID": mission_obj["m_iCSTReqGuide"],
            "RequiredGuide": MISSION_GUIDE_TYPES[mission_obj["m_iCSTReqGuide"]],
            "RequiredMissionIDs": mission_obj["m_iCSTReqMission"],
            "RequiredMissions": {
                m_id: mission_string_list[mission_task_groupped_list[m_id][0]["m_iHMissionName"]]["m_pstrNameString"].replace("\n", " ")
                for m_id in mission_obj["m_iCSTReqMission"]
                if m_id > 0
            },
            "Barkers": {},
            "Tasks": {},
            "Rewards": {
                "Items": [],
                "ItemSelectionNeeded": False,
                "FM": 0,
                "Taros": 0,
                "NanoRewardID": task_end_nano_id,
                "NanoReward": (
                    "{m_strName} - {m_strComment1}".format(**nano_string_list[task_end_nano_obj["m_iNanoName"]])
                    if task_end_nano_id > 0
                    else "None"
                ),
            },
        }
        sources["mission_info"][mission_id] = mission_info_obj

        for task_obj in task_list:
            task_id = task_obj["m_iHTaskID"]
            task_type_id = task_obj["m_iHTaskType"]
            current_objective_id = task_obj["m_iHCurrentObjective"]
            task_start_npc_id = task_obj["m_iHNPCID"]
            task_end_npc_id = task_obj["m_iHTerminatorNPCID"]
            task_barker_id_list = task_obj["m_iHBarkerTextID"]
            task_escort_npc_id = task_obj["m_iCSUDEFNPCID"]
            task_waypoint_npc_id = task_obj["m_iSTGrantWayPoint"]
            task_start_journal_id = task_obj["m_iSTJournalIDAdd"]
            task_end_journal_id = task_obj["m_iSUJournaliDAdd"]
            task_fail_journal_id = task_obj["m_iFJournalIDAdd"]
            task_end_outgoing_task_id = task_obj["m_iSUOutgoingTask"]
            task_fail_outgoing_task_id = task_obj["m_iFOutgoingTask"]
            task_start_send_npc_id = task_obj["m_iSTMessageSendNPC"]
            task_end_send_npc_id = task_obj["m_iSUMessageSendNPC"]
            task_fail_send_npc_id = task_obj["m_iFMessageSendNPC"]
            task_start_dialog_bubble_npc_id = task_obj["m_iSTDialogBubbleNPCID"]
            task_end_dialog_bubble_npc_id = task_obj["m_iSUDialogBubbleNPCID"]
            task_fail_dialog_bubble_npc_id = task_obj["m_iFDialogBubbleNPCID"]
            task_reward_id = task_obj["m_iSUReward"]
            task_end_outgoing_task_obj = mission_task_dict[task_end_outgoing_task_id] if task_end_outgoing_task_id in mission_task_dict else mission_task_dict[0]
            task_fail_outgoing_task_obj = mission_task_dict[task_fail_outgoing_task_id] if task_fail_outgoing_task_id in mission_task_dict else mission_task_dict[0]
            task_start_journal_obj = mission_journal_data_list[task_start_journal_id] if task_start_journal_id < len(mission_journal_data_list) else mission_journal_data_list[0]
            task_end_journal_obj = mission_journal_data_list[task_end_journal_id] if task_end_journal_id < len(mission_journal_data_list) else mission_journal_data_list[0]
            task_fail_journal_obj = mission_journal_data_list[task_fail_journal_id] if task_fail_journal_id < len(mission_journal_data_list) else mission_journal_data_list[0]

            if task_start_npc_id > 0:
                mission_info_obj["MissionStartNPCID"] = task_start_npc_id
                task_start_npc_obj = sources["npc_mob_type_info"][task_start_npc_id]
                mission_info_obj["MissionStartNPCName"] = task_start_npc_obj["Name"]
                mission_info_obj["MissionStartNPCIcon"] = task_start_npc_obj["Icon"]

            if task_end_npc_id > 0:
                mission_info_obj["MissionEndNPCID"] = task_end_npc_id
                task_end_npc_obj = sources["npc_mob_type_info"][task_end_npc_id]
                mission_info_obj["MissionEndNPCName"] = task_end_npc_obj["Name"]
                mission_info_obj["MissionEndNPCIcon"] = task_end_npc_obj["Icon"]

            if task_reward_id > 0:
                task_reward_obj = mission_reward_data_list[task_reward_id]
                mission_info_obj["Rewards"]["Taros"] = task_reward_obj["m_iCash"]
                mission_info_obj["Rewards"]["FM"] = task_reward_obj["m_iFusionMatter"]
                mission_info_obj["Rewards"]["Items"] = [
                    sources["item_info"][f"{item_type:02d}{SEP}{item_id:04d}"]
                    for item_type, item_id in zip(
                        task_reward_obj["m_iMissionRewarItemType"],
                        task_reward_obj["m_iMissionRewardItemID"],
                    )
                    if item_id > 0
                ]
                mission_info_obj["Rewards"]["ItemSelectionNeeded"] = task_reward_obj["m_iBox1Choice"] > 0

            mission_info_obj["Barkers"] = {
                f"{npc_obj['m_iNpcNumber']:04d}{SEP}{npc_string_list[npc_name_id]['m_strName']}": mission_string_list[barker_string_id]["m_pstrNameString"]
                for npc_obj in npc_data_list
                if (
                    (npc_name_id := npc_obj["m_iNpcName"]) > 0
                    and npc_obj["m_iBarkerType"] in range(1, 5)
                    and (barker_string_id := task_barker_id_list[npc_obj["m_iBarkerType"] - 1]) > 0
                )
            }

            mission_info_obj["Tasks"][task_id] = {
                "ID": task_id,
                "TypeID": task_type_id,
                "Type": MISSION_TASK_TYPES[task_type_id],
                "CurrentObjectiveID": current_objective_id,
                "CurrentObjective": mission_string_list[current_objective_id]["m_pstrNameString"],
                "RequiredInstanceID": mission_obj["m_iRequireInstanceID"],
                "RequiredInstance": warp_name_data_list[mission_obj["m_iRequireInstanceID"]]["m_pstrNameString"],
                "TimeLimitSeconds": mission_obj["m_iSTGrantTimer"],
                "TimeLimit": humanize.precisedelta(mission_obj["m_iSTGrantTimer"]),
                "EscortNPCID": task_escort_npc_id,
                "EscortNPCName": sources["npc_mob_type_info"][task_escort_npc_id]["Name"] if task_escort_npc_id in sources["npc_mob_type_info"] else "",
                "EscortNPCIcon": sources["npc_mob_type_info"][task_escort_npc_id]["Icon"] if task_escort_npc_id in sources["npc_mob_type_info"] else "",
                "WaypointNPCID": task_waypoint_npc_id,
                "WaypointNPCName": sources["npc_mob_type_info"][task_waypoint_npc_id]["Name"] if task_waypoint_npc_id in sources["npc_mob_type_info"] else "",
                "WaypointNPCIcon": sources["npc_mob_type_info"][task_waypoint_npc_id]["Icon"] if task_waypoint_npc_id in sources["npc_mob_type_info"] else "",
                "MessageOnStart": {
                    "TypeID": mission_obj["m_iSTMessageType"],
                    "Type": MISSION_MESSAGE_TYPES.get(mission_obj["m_iSTMessageType"], "None"),
                    "Text": mission_string_list[mission_obj["m_iSTMessageTextID"]]["m_pstrNameString"],
                    "SendNPCID": task_start_send_npc_id,
                    "SendNPCName": sources["npc_mob_type_info"][task_start_send_npc_id]["Name"] if task_start_send_npc_id in sources["npc_mob_type_info"] else "",
                    "SendNPCIcon": sources["npc_mob_type_info"][task_start_send_npc_id]["Icon"] if task_start_send_npc_id in sources["npc_mob_type_info"] else "",
                    "DialogBubble": mission_string_list[mission_obj["m_iSTDialogBubble"]]["m_pstrNameString"],
                    "DialogBubbleNPCID": task_start_dialog_bubble_npc_id,
                    "DialogBubbleNPCName": sources["npc_mob_type_info"][task_start_dialog_bubble_npc_id]["Name"] if task_start_dialog_bubble_npc_id in sources["npc_mob_type_info"] else "",
                    "DialogBubbleNPCIcon": sources["npc_mob_type_info"][task_start_dialog_bubble_npc_id]["Icon"] if task_start_dialog_bubble_npc_id in sources["npc_mob_type_info"] else "",
                    "JournalMissionSummary": mission_string_list[task_start_journal_obj["m_iMissionSummary"]]["m_pstrNameString"],
                    "JournalDetailedMissionDescription": mission_string_list[task_start_journal_obj["m_iDetaileMissionDesc"]]["m_pstrNameString"],
                    "JournalMissionCompleteSummary": mission_string_list[task_start_journal_obj["m_iMissionCompleteSummary"]]["m_pstrNameString"],
                    "JournalDetailedMissionCompleteDescription": mission_string_list[task_start_journal_obj["m_iDetaileMissionCompleteSummary"]]["m_pstrNameString"],
                    "JournalDetailedTaskDescription": mission_string_list[task_start_journal_obj["m_iDetailedTaskDesc"]]["m_pstrNameString"],
                },
                "MessageOnEnd": {
                    "TypeID": mission_obj["m_iSUMessageType"],
                    "Type": MISSION_MESSAGE_TYPES.get(mission_obj["m_iSUMessageType"], "None"),
                    "Text": mission_string_list[mission_obj["m_iSUMessagetextID"]]["m_pstrNameString"],
                    "SendNPCID": task_end_send_npc_id,
                    "SendNPCName": sources["npc_mob_type_info"][task_end_send_npc_id]["Name"] if task_end_send_npc_id in sources["npc_mob_type_info"] else "",
                    "SendNPCIcon": sources["npc_mob_type_info"][task_end_send_npc_id]["Icon"] if task_end_send_npc_id in sources["npc_mob_type_info"] else "",
                    "DialogBubble": mission_string_list[mission_obj["m_iSUDialogBubble"]]["m_pstrNameString"],
                    "DialogBubbleNPCID": task_end_dialog_bubble_npc_id,
                    "DialogBubbleNPCName": sources["npc_mob_type_info"][task_end_dialog_bubble_npc_id]["Name"] if task_end_dialog_bubble_npc_id in sources["npc_mob_type_info"] else "",
                    "DialogBubbleNPCIcon": sources["npc_mob_type_info"][task_end_dialog_bubble_npc_id]["Icon"] if task_end_dialog_bubble_npc_id in sources["npc_mob_type_info"] else "",
                    "JournalMissionSummary": mission_string_list[task_end_journal_obj["m_iMissionSummary"]]["m_pstrNameString"],
                    "JournalDetailedMissionDescription": mission_string_list[task_end_journal_obj["m_iDetaileMissionDesc"]]["m_pstrNameString"],
                    "JournalMissionCompleteSummary": mission_string_list[task_end_journal_obj["m_iMissionCompleteSummary"]]["m_pstrNameString"],
                    "JournalDetailedMissionCompleteDescription": mission_string_list[task_end_journal_obj["m_iDetaileMissionCompleteSummary"]]["m_pstrNameString"],
                    "JournalDetailedTaskDescription": mission_string_list[task_end_journal_obj["m_iDetailedTaskDesc"]]["m_pstrNameString"],
                },
                "MessageOnFail": {
                    "TypeID": mission_obj["m_iFMessageType"],
                    "Type": MISSION_MESSAGE_TYPES.get(mission_obj["m_iFMessageType"], "None"),
                    "Text": mission_string_list[mission_obj["m_iFMessageTextID"]]["m_pstrNameString"],
                    "SendNPCID": task_fail_send_npc_id,
                    "SendNPCName": sources["npc_mob_type_info"][task_fail_send_npc_id]["Name"] if task_fail_send_npc_id in sources["npc_mob_type_info"] else "",
                    "SendNPCIcon": sources["npc_mob_type_info"][task_fail_send_npc_id]["Icon"] if task_fail_send_npc_id in sources["npc_mob_type_info"] else "",
                    "DialogBubble": mission_string_list[mission_obj["m_iFDialogBubble"]]["m_pstrNameString"],
                    "DialogBubbleNPCID": task_fail_dialog_bubble_npc_id,
                    "DialogBubbleNPCName": sources["npc_mob_type_info"][task_fail_dialog_bubble_npc_id]["Name"] if task_fail_dialog_bubble_npc_id in sources["npc_mob_type_info"] else "",
                    "DialogBubbleNPCIcon": sources["npc_mob_type_info"][task_fail_dialog_bubble_npc_id]["Icon"] if task_fail_dialog_bubble_npc_id in sources["npc_mob_type_info"] else "",
                    "JournalMissionSummary": mission_string_list[task_fail_journal_obj["m_iMissionSummary"]]["m_pstrNameString"],
                    "JournalDetailedMissionDescription": mission_string_list[task_fail_journal_obj["m_iDetaileMissionDesc"]]["m_pstrNameString"],
                    "JournalMissionCompleteSummary": mission_string_list[task_fail_journal_obj["m_iMissionCompleteSummary"]]["m_pstrNameString"],
                    "JournalDetailedMissionCompleteDescription": mission_string_list[task_fail_journal_obj["m_iDetaileMissionCompleteSummary"]]["m_pstrNameString"],
                    "JournalDetailedTaskDescription": mission_string_list[task_fail_journal_obj["m_iDetailedTaskDesc"]]["m_pstrNameString"],
                },
                "OnEndNextTaskID": task_end_outgoing_task_id,
                "OnEndTaskObjective": mission_string_list[task_end_outgoing_task_obj["m_iHCurrentObjective"]]["m_pstrNameString"],
                "OnFailNextTaskID": task_fail_outgoing_task_id,
                "OnFailTaskObjective": mission_string_list[task_fail_outgoing_task_obj["m_iHCurrentObjective"]]["m_pstrNameString"],
                "QuestItemMonsterRequirements": {
                    f"{mob_type_id:04d}{SEP}{npc_string_list[mob_type_id]['m_strName']}": {
                        "KillCount": num_to_kill,
                        "QuestItemID": item_id,
                        "QuestItem": quest_item_string_list[quest_item_data_list[item_id]["m_iItemName"]]["m_strName"],
                        "QuestItemNeededCount": item_num_needed,
                        "QuestItemDropPercent": item_drop_percent,
                    }
                    for mob_type_id, num_to_kill, item_id, item_num_needed, item_drop_percent in zip(
                        mission_obj["m_iCSUEnemyID"],
                        mission_obj["m_iCSUNumToKill"],
                        mission_obj["m_iCSUItemID"],
                        mission_obj["m_iCSUItemNumNeeded"],
                        mission_obj["m_iSTItemDropRate"],
                    )
                    if mob_type_id > 0
                },
                "QuestItemChangeOnStart": {
                    f"{item_id:04d}{SEP}{quest_item_string_list[quest_item_data_list[item_id]['m_iItemName']]['m_strName']}": item_num_needed
                    for item_id, item_num_needed in zip(
                        mission_obj["m_iSTItemID"],
                        mission_obj["m_iSTItemNumNeeded"],
                    )
                    if item_id > 0 and item_id < len(quest_item_data_list)
                },
                "QuestItemChangeOnEnd": {
                    f"{item_id:04d}{SEP}{quest_item_string_list[quest_item_data_list[item_id]['m_iItemName']]['m_strName']}": item_num_needed
                    for item_id, item_num_needed in zip(
                        mission_obj["m_iSUItem"],
                        mission_obj["m_iSUInstancename"],
                    )
                    if item_id > 0 and item_id < len(quest_item_data_list)
                },
                "QuestItemChangeOnFail": {
                    f"{item_id:04d}{SEP}{quest_item_string_list[quest_item_data_list[item_id]['m_iItemName']]['m_strName']}": item_num_needed
                    for item_id, item_num_needed in zip(
                        mission_obj["m_iFItemID"],
                        mission_obj["m_iFItemNumNeeded"],
                    )
                    if item_id > 0 and item_id < len(quest_item_data_list)
                },
                "QuestItemsDeleted": [
                    f"{item_id:04d}{SEP}{quest_item_string_list[quest_item_data_list[item_id]['m_iItemName']]['m_strName']}"
                    for item_id in mission_obj["m_iDelItemID"]
                    if item_id > 0 and item_id < len(quest_item_data_list)
                ],
                "GuideEmails": {
                    guide_name: mission_string_list[email_id]["m_pstrNameString"]
                    for guide_name, email_id in zip(MISSION_GUIDE_TYPES[1:], mission_obj["m_iMentorEmailID"])
                    if email_id > 0
                },
            }


def construct_instance_data(sources: dict[str, dict]) -> None:
    sources["instance_info"] = {}
    sources["instance_warp_info"] = {}

    instance_table_obj = sources["xdt"]["m_pInstanceTable"]
    instance_data_list = instance_table_obj["m_pInstanceData"]
    warp_data_list = instance_table_obj["m_pWarpData"]
    warp_name_data_list = instance_table_obj["m_pWarpNameData"]

    mission_table_obj = sources["xdt"]["m_pMissionTable"]
    mission_data_list = mission_table_obj["m_pMissionData"]
    mission_string_list = mission_table_obj["m_pMissionStringData"]
    mission_task_dict = {obj["m_iHTaskID"]: obj for obj in mission_data_list}

    for warp_data_obj in warp_data_list[1:]:
        warp_id = warp_data_obj["m_iWarpNumber"]
        entry_instance_id = warp_data_obj["m_iToMapNum"]
        warp_npc_id = warp_data_obj["m_iNpcNumber"]
        warp_task_id = warp_data_obj["m_iLimit_TaskID"]
        warp_task_obj = mission_task_dict[warp_task_id] if warp_task_id in mission_task_dict else mission_task_dict[0]
        use_item_type = warp_data_obj["m_iLimit_UseItemType"]
        use_item_id = warp_data_obj["m_iLimit_UseItemID"]
        item_str_id = f"{use_item_type:02d}{SEP}{use_item_id:04d}"

        sources["instance_warp_info"][warp_id] = {
            "ID": warp_id,
            "EntryInstanceID": entry_instance_id,
            "EntryInstance": warp_name_data_list[entry_instance_id]["m_pstrNameString"] if entry_instance_id < len(warp_name_data_list) else "",
            "WarpPrice": warp_data_obj["m_iCost"],
            "ToX": warp_data_obj["m_iToX"],
            "ToY": warp_data_obj["m_iToY"],
            "ToZ": warp_data_obj["m_iToZ"],
            "ToAreaZone": to_area_tag(locate_coordinates(sources["area_info"], warp_data_obj["m_iToX"], warp_data_obj["m_iToY"])),
            "NPCID": warp_npc_id,
            "NPCType": sources["npc_type_info"][warp_npc_id] if warp_npc_id > 0 else None,
            "NPCs": sources["npc_info"][warp_npc_id] if warp_npc_id > 0 else None,
            "RequiredTaskID": warp_task_id,
            "RequiredTaskObjective": mission_string_list[warp_task_obj["m_iHCurrentObjective"]]["m_pstrNameString"],
            "RequiredMissionID": warp_task_obj["m_iHMissionID"],
            "RequiredMission": mission_string_list[warp_task_obj["m_iHMissionName"]]["m_pstrNameString"],
            "RequiredMinLevel": warp_data_obj["m_iLimit_Level"],
            "RequiredItemType": use_item_type,
            "RequiredItemID": use_item_id,
            "RequiredItem": sources["item_info"].get(item_str_id),
        }

    for instance_data_obj in instance_data_list[1:]:
        instance_id = instance_data_obj["m_iInstanceNameID"]

        sources["instance_info"][instance_id] = {
            "ID": instance_id,
            "Name": warp_name_data_list[instance_id]["m_pstrNameString"] if instance_id < len(warp_name_data_list) else "",
            "ZoneX": instance_data_obj["m_iZoneX"],
            "ZoneY": instance_data_obj["m_iZoneY"],
            "AreaZone": to_area_tag(
                locate_coordinates(
                    sources["area_info"],
                    instance_data_obj["m_iZoneX"] * TILE_WIDTH + TILE_WIDTH // 2,
                    instance_data_obj["m_iZoneY"] * TILE_WIDTH + TILE_WIDTH // 2,
                )
            ),
            "EPID": instance_data_obj["m_iIsEP"],
            "EPMaxScore": instance_data_obj["m_ScoreMax"],
            "EntryWarps": {
                warp_id: warp_data_obj
                for warp_id, warp_data_obj in sources["instance_warp_info"].items()
                if warp_data_obj["EntryInstanceID"] == instance_id
            },
        }


def construct_nano_data(sources: dict) -> None:
    sources["nano_info"] = {}
    sources["nano_power_info"] = {}

    nano_table_obj = sources["xdt"]["m_pNanoTable"]
    nano_data_list = nano_table_obj["m_pNanoData"]
    nano_string_list = nano_table_obj["m_pNanoStringData"]
    nano_icon_list = nano_table_obj["m_pNanoIconData"]
    nano_tune_list = nano_table_obj["m_pNanoTuneData"]
    nano_tune_string_list = nano_table_obj["m_pNanoTuneStringData"]
    nano_tune_icon_list = nano_table_obj["m_pNanoTuneIconData"]

    skill_table_obj = sources["xdt"]["m_pSkillTable"]
    skill_data_list = skill_table_obj["m_pSkillData"]
    skill_string_list = skill_table_obj["m_pSkillStringData"]
    skill_icon_list = skill_table_obj["m_pSkillIconData"]

    for nano_tune_obj in nano_tune_list[1:]:
        tune_id = nano_tune_obj["m_iTuneNumber"]
        nano_tune_name = nano_tune_string_list[nano_tune_obj["m_iTuneName"]]["m_strName"]
        nano_tune_type_name = nano_tune_string_list[nano_tune_obj["m_iTuneName"]]["m_strComment1"]
        nano_tune_comment = nano_tune_string_list[nano_tune_obj["m_iComment"]]["m_strComment"]
        item_str_id = f"07{SEP}{nano_tune_obj['m_iReqItemID']:04d}"
        skill_id = nano_tune_obj["m_iSkillID"]
        skill_obj = skill_data_list[skill_id]

        sources["nano_power_info"][tune_id] = {
            "ID": tune_id,
            "Name": nano_tune_name,
            "TypeName": nano_tune_type_name,
            "Comment": nano_tune_comment,
            "Icon": f"icons/skillicon_{nano_tune_icon_list[skill_obj['m_iIcon']]['m_iIconNumber']:02d}.png",
            "PowerItemID": nano_tune_obj["m_iReqItemID"],
            "PowerItem": sources["item_info"][item_str_id],
            "PowerItemCount": nano_tune_obj["m_iReqItemCount"],
            "SkillID": skill_id,
            "SkillName": skill_string_list[skill_id]["m_strName"],
            "SkillRange": skill_obj["m_iEffectRange"],
            "SkillAngle": skill_obj["m_iEffectAngle"],
            "SkillArea": skill_obj["m_iEffectArea"],
            "SkillCoolTime": skill_obj["m_iCoolTime"],
            "SkillTargetNumber": skill_obj["m_iTargetNumber"],
            "SkillIcon": f"icons/skillicon_{skill_icon_list[skill_obj['m_iIcon']]['m_iIconNumber']:02d}.png",
        }

    for nano_data_obj in nano_data_list[1:]:
        nano_id = nano_data_obj["m_iNanoNumber"]
        nano_name_obj = nano_string_list[nano_data_obj["m_iNanoName"]]

        sources["nano_info"][nano_id] = {
            "ID": nano_id,
            "Name": nano_name_obj["m_strName"],
            "Comment": nano_name_obj["m_strComment"],
            "NanoTypeID": nano_data_obj["m_iStyle"],
            "NanoType": NANO_MOB_TYPES[nano_data_obj["m_iStyle"]],
            "NanoPowers": {
                tune_id: sources["nano_power_info"][tune_id]
                for tune_id in nano_data_obj["m_iTune"]
                if tune_id > 0
            },
            "NanoIcon": f"icons/nanoicon_{nano_icon_list[nano_data_obj['m_iIcon1']]['m_iIconNumber']:02d}.png",
        }


def construct_vendor_data(sources: dict) -> None:
    sources["vendor_info"] = {}

    vendor_item_data_list = sources["xdt"]["m_pVendorTable"]["m_pItemData"]
    vendor_groupped_list = {
        vendor_id: list(vendor_iter)
        for vendor_id, vendor_iter in groupby(
            sorted(vendor_item_data_list[1:], key=itemgetter("m_iNpcNumber", "m_iSortNumber")),
            key=itemgetter("m_iNpcNumber"),
        )
    }

    for vendor_id, vendor_item_data_group in vendor_groupped_list.items():
        sources["vendor_info"][vendor_id] = {
            "NPCID": vendor_id,
            # too much redundant information here, just NPCs are enough
            # "NPCType": sources["npc_type_info"][vendor_id] if vendor_id > 0 else None,
            "NPCs": sources["npc_info"][vendor_id] if vendor_id > 0 else None,
            "Items": {},
        }

        for vendor_item_obj in vendor_item_data_group:
            item_id = vendor_item_obj["m_iitemID"]
            item_type_id = vendor_item_obj["m_iItemType"]
            item_str_id = f"{item_type_id:02d}{SEP}{item_id:04d}"

            if item_str_id not in sources["item_info"]:
                continue

            item_info_obj = sources["item_info"][item_str_id]

            sources["vendor_info"][vendor_id]["Items"][item_str_id] = {
                "ItemTypeID": item_type_id,
                "ItemType": ITEM_TYPES[item_type_id],
                "ItemID": item_id,
                "Item": item_info_obj,
                "Price": item_info_obj.get("ItemPrice", vendor_item_obj["m_iSellCost"]),
                "SortNumber": vendor_item_obj["m_iSortNumber"],
            }


def construct_ep_instance_data(sources: dict) -> None:
    sources["infected_zone_info"] = {}

    for instance_obj in sources["instance_info"].values():
        epid = instance_obj["EPID"]

        if epid == 0:
            continue

        racing_obj = sources["drops_map"]["Racing"][epid]

        sources["infected_zone_info"][epid] = {
            "ID": epid,
            "Name": instance_obj["Name"],
            "ZoneX": instance_obj["ZoneX"],
            "ZoneY": instance_obj["ZoneY"],
            "AreaZone": instance_obj["AreaZone"],
            "OriginalScoreCap": instance_obj["EPMaxScore"],
            "ScoreCap": racing_obj["ScoreCap"],
            "TimeLimitSeconds": racing_obj["TimeLimit"],
            "TimeLimit": humanize.precisedelta(racing_obj["TimeLimit"]),
            "TotalPods": racing_obj["TotalPods"],
            "ScaleFactor": racing_obj["ScaleFactor"],
            "PodFactor": racing_obj["PodFactor"],
            "TimeFactor": racing_obj["TimeFactor"],
            "ScoreFunction": "min({ScoreCap}, floor(exp({ScaleFactor} + {PodFactor} * PodsCollected / {TotalPods} - {TimeFactor} * TimeElapsedSeconds / {TimeLimit})))".format(
                **racing_obj,
            ),
            "FMRewardFunction": "floor((1 + exp({ScaleFactor} - 1) * {PodFactor} * PodsCollected) / {TotalPods})".format(
                **racing_obj,
            ),
            "StarsToItemRewards": {
                5 - i: {
                    "ItemTypeID": 9,
                    "ItemID": item_id,
                    "Item": sources["item_info"][f"09{SEP}{item_id:04d}"],
                    "RankScore": rank_score,
                }
                for i, (rank_score, item_id) in enumerate(zip(racing_obj["RankScores"], racing_obj["Rewards"]))
                if item_id > 0
            },
            "EntryWarps": instance_obj["EntryWarps"],
        }


def construct_code_item_data(sources: dict) -> None:
    sources["code_item_info"] = {}

    item_references = sources["drops_map"]["ItemReferences"]
    code_items = sources["drops_map"].get("CodeItems", {})

    for code_item_obj in code_items.values():
        code = code_item_obj["Code"]
        sources["code_item_info"][code] = {
            "Code": code,
            "Items": {},
        }

        for item_reference_id in code_item_obj["ItemReferenceIDs"]:
            item_reference_obj = item_references[item_reference_id]
            item_id = item_reference_obj["ItemID"]
            item_type_id = item_reference_obj["Type"]
            item_str_id = f"{item_type_id:02d}{SEP}{item_id:04d}"

            if item_str_id not in sources["item_info"]:
                continue

            sources["code_item_info"][code]["Items"][item_str_id] = sources["item_info"][item_str_id]


def construct_transportation_data(sources: dict) -> None:
    sources["transportation_path_info"] = {}
    sources["transportation_info"] = {}

    skyway_paths = {route_obj["iRouteID"]: route_obj for route_obj in sources["paths"]["skyway"].values()}
    slider_paths = sources["paths"]["slider"]

    transportation_table_obj = sources["xdt"]["m_pTransportationTable"]
    transportation_data_list = transportation_table_obj["m_pTransportationData"]
    transportation_warp_location_list = transportation_table_obj["m_pTransportationWarpLocation"]
    transportation_warp_string_list = transportation_table_obj["m_pTransportationWarpString"]
    transportation_broomstick_location_list = transportation_table_obj["m_pBroomstickLocation"]
    transportation_broomstick_string_list = transportation_table_obj["m_pBroomstickString"]
    transportation_icon_data_list = transportation_table_obj["m_pTransIcon"]

    for transportation_data_obj in transportation_data_list[1:]:
        vehicle_id = transportation_data_obj["m_iVehicleID"]
        vehicle_npc_id = transportation_data_obj["m_iNPCID"]
        vehicle_move_type_id = transportation_data_obj["m_iMoveType"]
        vehicle_move_type = TRANSPORTATION_MOVE_TYPES[vehicle_move_type_id]
        vehicle_start_location_id = transportation_data_obj["m_iStartLocation"]
        vehicle_end_location_id = transportation_data_obj["m_iEndLocation"]
        vehicle_route_id = transportation_data_obj["m_iRouteNum"]
        vehicle_route_points = []
        vehicle_speed = transportation_data_obj["m_iSpeed"]

        if vehicle_move_type_id == 1:
            vehicle_start_location_obj = transportation_warp_location_list[vehicle_start_location_id]
            vehicle_end_location_obj = transportation_warp_location_list[vehicle_end_location_id]
            vehicle_start_location_name = transportation_warp_string_list[vehicle_start_location_id]["m_pstrLocationName"]
            vehicle_end_location_name = transportation_warp_string_list[vehicle_end_location_id]["m_pstrLocationName"]
            vehicle_start_area_zone = to_area_tag(
                locate_coordinates(
                    sources["area_info"],
                    vehicle_start_location_obj["m_iXpos"],
                    vehicle_start_location_obj["m_iYpos"],
                )
            )
            vehicle_end_area_zone = to_area_tag(
                locate_coordinates(
                    sources["area_info"],
                    vehicle_end_location_obj["m_iXpos"],
                    vehicle_end_location_obj["m_iYpos"],
                )
            )
        else:
            vehicle_start_location_obj = transportation_broomstick_location_list[vehicle_start_location_id]
            vehicle_end_location_obj = transportation_broomstick_location_list[vehicle_end_location_id]
            vehicle_start_location_name = transportation_broomstick_string_list[vehicle_start_location_id]["m_pstrLocationName"]
            vehicle_end_location_name = transportation_broomstick_string_list[vehicle_end_location_id]["m_pstrLocationName"]
            vehicle_start_area_zone = to_area_tag(
                locate_coordinates(
                    sources["area_info"],
                    vehicle_start_location_obj["m_iXpos"],
                    vehicle_start_location_obj["m_iYpos"],
                )
            )
            vehicle_end_area_zone = to_area_tag(
                locate_coordinates(
                    sources["area_info"],
                    vehicle_end_location_obj["m_iXpos"],
                    vehicle_end_location_obj["m_iYpos"],
                )
            )

            if vehicle_move_type_id == 2:
                path_obj = skyway_paths[vehicle_route_id]
                vehicle_speed = path_obj["iMonkeySpeed"]
                vehicle_route_points = (
                    [
                        {
                            "IsStopPoint": True,
                            "X": vehicle_start_location_obj["m_iXpos"],
                            "Y": vehicle_start_location_obj["m_iYpos"],
                            "Z": vehicle_start_location_obj["m_iZpos"],
                            "AreaZone": vehicle_start_area_zone,
                        }
                    ]
                    + [
                        {
                            "IsStopPoint": False,
                            "X": pt["iX"],
                            "Y": pt["iY"],
                            "Z": pt["iZ"],
                            "AreaZone": to_area_tag(
                                locate_coordinates(
                                    sources["area_info"],
                                    pt["iX"],
                                    pt["iY"],
                                )
                            ),
                        }
                        for pt in path_obj["aPoints"]
                    ]
                    + [
                        {
                            "IsStopPoint": True,
                            "X": vehicle_end_location_obj["m_iXpos"],
                            "Y": vehicle_end_location_obj["m_iYpos"],
                            "Z": vehicle_end_location_obj["m_iZpos"],
                            "AreaZone": vehicle_end_area_zone,
                        }
                    ]
                )
            else:
                vehicle_route_points = [
                    {
                        "IsStopPoint": pt["bStop"],
                        "X": pt["iX"],
                        "Y": pt["iY"],
                        "Z": pt["iZ"],
                        "AreaZone": to_area_tag(
                            locate_coordinates(
                                sources["area_info"],
                                pt["iX"],
                                pt["iY"],
                            )
                        ),
                    }
                    for pt in slider_paths.values()
                ]

        vehicle_start_location_icon_id = transportation_icon_data_list[vehicle_start_location_obj["m_iIcon"]]["m_iIconNumber"]
        vehicle_end_location_icon_id = transportation_icon_data_list[vehicle_end_location_obj["m_iIcon"]]["m_iIconNumber"]

        sources["transportation_path_info"][vehicle_id] = {
            "ID": vehicle_id,
            "NPCID": vehicle_npc_id,
            "NPCType": sources["npc_mob_type_info"][vehicle_npc_id] if vehicle_npc_id > 0 else None,
            "NPCs": sources["npc_mob_info"][vehicle_npc_id] if vehicle_npc_id > 0 else None,
            "MoveTypeID": vehicle_move_type_id,
            "MoveType": vehicle_move_type,
            "Cost": transportation_data_obj["m_iCost"],
            "SpeedClass": vehicle_speed,
            "RouteID": vehicle_route_id,
            "Route": vehicle_route_points,
            "StartLocation": {
                "ID": vehicle_start_location_id,
                "Name": vehicle_start_location_name,
                "Icon": f"icons/transport_{vehicle_start_location_icon_id:02d}.png",
                "X": vehicle_start_location_obj["m_iXpos"],
                "Y": vehicle_start_location_obj["m_iYpos"],
                "Z": vehicle_start_location_obj["m_iZpos"],
                "AreaZone": vehicle_start_area_zone,
            },
            "EndLocation": {
                "ID": vehicle_end_location_id,
                "Name": vehicle_end_location_name,
                "Icon": f"icons/transport_{vehicle_end_location_icon_id:02d}.png",
                "X": vehicle_end_location_obj["m_iXpos"],
                "Y": vehicle_end_location_obj["m_iYpos"],
                "Z": vehicle_end_location_obj["m_iZpos"],
                "AreaZone": vehicle_end_area_zone,
            },
        }

    npc_groupped_transportation_dict = {
        npc_id: list(npc_iter)
        for npc_id, npc_iter in groupby(
            sorted(sources["transportation_path_info"].values(), key=itemgetter("NPCID")),
            key=itemgetter("NPCID"),
        )
    }

    for npc_id, npc_transportation_list in npc_groupped_transportation_dict.items():
        sources["transportation_info"][npc_id] = {
            "NPCID": npc_id,
            "NPCType": sources["npc_mob_type_info"][npc_id] if npc_id > 0 else None,
            "NPCs": sources["npc_mob_info"][npc_id] if npc_id > 0 else None,
            "MoveTypeID": npc_transportation_list[0]["MoveTypeID"],
            "MoveType": npc_transportation_list[0]["MoveType"],
            "StartLocation": npc_transportation_list[0]["StartLocation"],
            "Transportations": {
                tp_obj["EndLocation"]["ID"]: {
                    **tp_obj["EndLocation"],
                    "Cost": tp_obj["Cost"],
                    "SpeedClass": tp_obj["SpeedClass"],
                    "RouteID": tp_obj["RouteID"],
                    "Route": tp_obj["Route"],
                }
                for tp_obj in npc_transportation_list
            },
        }


def construct_combination_data(sources: dict) -> None:
    sources["combination_info"] = {}

    combining_data_list = sources["xdt"]["m_pCombiningTable"]["m_pCombiningData"]

    for combination_obj in combining_data_list[1:]:
        level_gap = combination_obj["m_iLevelGap"]

        sources["combination_info"][level_gap] = {
            "LevelGap": level_gap,
            "SameRarity": combination_obj["m_fSameGrade"],
            "OneRarityDiff": combination_obj["m_fOneGrade"],
            "TwoRarityDiff": combination_obj["m_fTwoGrade"],
            "ThreeRarityDiff": combination_obj["m_fThreeGrade"],
            "LooksItemPriceMultiplier": combination_obj["m_iLookConstant"],
            "StatsItemPriceMultiplier": combination_obj["m_iStatConstant"],
        }


def construct_egg_instance_region_grouped_data(sources: dict) -> None:
    sources["egg_instance_region_grouped_info"] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for egg_obj_dict in sources["egg_info"].values():
        for egg_obj in egg_obj_dict.values():
            area_tag = egg_obj["AreaZone"]
            egg_id = egg_obj["TypeID"]
            instance_id = egg_obj["InstanceID"]
            sources["egg_instance_region_grouped_info"][egg_id][instance_id][area_tag].append(egg_obj)


def construct_npc_instance_region_grouped_data(sources: dict) -> None:
    sources["npc_instance_region_grouped_info"] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for npc_obj_dict in sources["npc_info"].values():
        for npc_obj in npc_obj_dict.values():
            area_tag = npc_obj["AreaZone"]
            npc_id = npc_obj["TypeID"]
            instance_id = npc_obj["InstanceID"]
            sources["npc_instance_region_grouped_info"][npc_id][instance_id][area_tag].append(npc_obj)


def construct_mob_instance_region_grouped_data(sources: dict) -> None:
    sources["mob_instance_region_grouped_info"] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for mob_obj_dict in sources["mob_info"].values():
        for mob_obj in mob_obj_dict.values():
            area_tag = mob_obj["AreaZone"]
            mob_id = mob_obj["TypeID"]
            instance_id = mob_obj["InstanceID"]
            sources["mob_instance_region_grouped_info"][mob_id][instance_id][area_tag].append(mob_obj)


def construct_code_item_source_data(sources: dict) -> None:
    sources["code_item_source_info"] = defaultdict(list)

    for code_item_obj in sources["code_item_info"].values():
        for item_str_id in code_item_obj["Items"]:
            sources["code_item_source_info"][item_str_id].append({"Code": code_item_obj["Code"]})


def construct_vendor_source_data(sources: dict) -> None:
    sources["vendor_source_info"] = defaultdict(list)

    for vendor_obj in sources["vendor_info"].values():
        vendor_id = vendor_obj["NPCID"]

        if vendor_id not in sources["npc_type_info"]:
            continue

        vendor_npc_type = sources["npc_type_info"][vendor_id]

        for instance_id, area_dict in sources["npc_instance_region_grouped_info"][vendor_id].items():
            for area_tag, npc_list in area_dict.items():
                for npc_obj in npc_list:
                    for item_str_id, vendor_item_obj in vendor_obj["Items"].items():
                        sources["vendor_source_info"][item_str_id].append({
                            "NPCID": npc_obj["ID"],
                            "NPCTypeID": vendor_id,
                            "NPCName": vendor_npc_type["Name"],
                            "NPCIcon": vendor_npc_type["Icon"],
                            "X": npc_obj["X"],
                            "Y": npc_obj["Y"],
                            "Z": npc_obj["Z"],
                            "InstanceID": instance_id,
                            "AreaZone": area_tag,
                            "Price": vendor_item_obj["Price"],
                        })


def construct_racing_source_data(sources: dict) -> None:
    sources["racing_source_info"] = defaultdict(list)

    for ep_obj in sources["infected_zone_info"].values():
        for star_count, reward_obj in ep_obj["StarsToItemRewards"].items():
            crate_id = reward_obj["ItemID"]

            for warp_obj in ep_obj["EntryWarps"].values():
                warp_npc_id = warp_obj["NPCID"]
                warp_npc_type = sources["npc_type_info"][warp_npc_id]
                instance_region_groups = sources["npc_instance_region_grouped_info"][warp_npc_id]

                if WORLD_INSTANCE_ID not in instance_region_groups:
                    continue

                for area_tag, npc_list in instance_region_groups[WORLD_INSTANCE_ID].items():
                    for npc_obj in npc_list:
                        sources["racing_source_info"][crate_id].append({
                            "NPCID": npc_obj["ID"],
                            "NPCTypeID": warp_npc_id,
                            "NPCName": warp_npc_type["Name"],
                            "NPCIcon": warp_npc_type["Icon"],
                            "X": npc_obj["X"],
                            "Y": npc_obj["Y"],
                            "Z": npc_obj["Z"],
                            "NPCInstanceID": WORLD_INSTANCE_ID,
                            "NPCInstanceName": "World",
                            "InstanceID": ep_obj["ID"],
                            "InstanceName": ep_obj["Name"],
                            "AreaZone": area_tag,
                            "RequiredStars": star_count,
                            "RequiredScore": reward_obj["RankScore"],
                        })


def construct_mob_event_source_data(sources: dict) -> None:
    sources["mob_source_info"] = defaultdict(list)
    sources["event_source_info"] = defaultdict(list)

    crate_map = sources["drops_map"]["Crates"]
    references = sources["references"]

    for crate_id in crate_map:
        cdt_refs = []

        for cdt_name, cdt_id in references.get(("Crates", crate_id), set()):
            if cdt_name != "CrateDropTypes":
                continue

            cdt_refs.append(cdt_id)

        md_refs = []

        for cdt_id in cdt_refs:
            for md_name, md_id in references.get(("CrateDropTypes", cdt_id), set()):
                if md_name != "MobDrops":
                    continue

                md_refs.append(md_id)

        mob_event_refs = []

        for md_id in md_refs:
            for mob_event_name, mob_event_id in references.get(("MobDrops", md_id), set()):
                if mob_event_name in ["Mobs", "Events"]:
                    mob_event_refs.append((mob_event_name, mob_event_id, md_id))

        for mob_event_name, mob_event_id, md_id in mob_event_refs:
            mob_drop = sources["drops_map"]["MobDrops"][md_id]
            mdt = sources["drops_map"]["MiscDropTypes"][mob_drop["MiscDropTypeID"]]
            mdc = sources["drops_map"]["MiscDropChances"][mob_drop["MiscDropChanceID"]]
            cdt = sources["drops_map"]["CrateDropTypes"][mob_drop["CrateDropTypeID"]]
            cdc = sources["drops_map"]["CrateDropChances"][mob_drop["CrateDropChanceID"]]

            total_drop_chance = 0
            relevant_drop_chance = 0
            for listed_crate_id, listed_crate_chance in zip(cdt["CrateIDs"], cdc["CrateTypeDropWeights"]):
                if listed_crate_id == crate_id:
                    relevant_drop_chance += listed_crate_chance
                total_drop_chance += listed_crate_chance

            potion_probability = Fraction(mdc["PotionDropChance"], mdc["PotionDropChanceTotal"])
            boost_probability = Fraction(mdc["BoostDropChance"], mdc["BoostDropChanceTotal"])
            taro_probability = Fraction(mdc["TaroDropChance"], mdc["TaroDropChanceTotal"])
            fm_probability = Fraction(mdc["FMDropChance"], mdc["FMDropChanceTotal"])
            probability = Fraction(cdc["DropChance"], cdc["DropChanceTotal"]) * Fraction(relevant_drop_chance, total_drop_chance)

            drops_info = {
                "PotionReward": mdt["PotionAmount"],
                "BoostReward": mdt["BoostAmount"],
                "TaroReward": mdt["TaroAmount"],
                "FMReward": mdt["FMAmount"],
                "PotionOdds": str(potion_probability),
                "BoostOdds": str(boost_probability),
                "TaroOdds": str(taro_probability),
                "FMOdds": str(fm_probability),
                "Odds": str(probability),
                "PotionProbability": float(potion_probability),
                "BoostProbability": float(boost_probability),
                "TaroProbability": float(taro_probability),
                "FMProbability": float(fm_probability),
                "Probability": float(probability),
            }

            if mob_event_name == "Mobs":
                if mob_event_id not in sources["mob_type_info"]:
                    continue

                mob_type = sources["mob_type_info"][mob_event_id]

                for instance_id, area_dict in sources["mob_instance_region_grouped_info"][mob_event_id].items():
                    for area_tag, mob_list in area_dict.items():
                        sources["mob_source_info"][crate_id].append({
                            "MobTypeID": mob_event_id,
                            "MobName": mob_type["Name"],
                            "MobIcon": mob_type["Icon"],
                            # this is a good +130MB on the source json file, we can't afford it
                            # just look it up if you want from mob_info
                            # "Locations": [
                            #     {
                            #         "MobID": mob_obj["ID"],
                            #         "X": mob_obj["X"],
                            #         "Y": mob_obj["Y"],
                            #         "Z": mob_obj["Z"],
                            #         "HP": mob_obj["HP"],
                            #     }
                            #     for mob_obj in mob_list
                            # ],
                            "LocationLimits": {
                                "MinX": min(mob_obj["X"] for mob_obj in mob_list),
                                "MinY": min(mob_obj["Y"] for mob_obj in mob_list),
                                "MaxX": max(mob_obj["X"] for mob_obj in mob_list),
                                "MaxY": max(mob_obj["Y"] for mob_obj in mob_list),
                                "MinZ": min(mob_obj["Z"] for mob_obj in mob_list),
                                "MaxZ": max(mob_obj["Z"] for mob_obj in mob_list),
                            },
                            "InstanceID": instance_id,
                            "AreaZone": area_tag,
                            **drops_info,
                        })
            else:
                sources["event_source_info"][crate_id].append({
                    "EventID": mob_event_id,
                    "EventName": EVENT_TYPES.get(mob_event_id, "Custom Event"),
                    **drops_info,
                })


def construct_mission_reward_source_data(sources: dict) -> None:
    sources["mission_reward_source_info"] = defaultdict(list)

    for mission_obj in sources["mission_info"].values():
        mission_start_npc_id = mission_obj["MissionStartNPCID"]

        if mission_start_npc_id not in sources["npc_mob_type_info"]:
            continue

        mission_start_npc_type = sources["npc_mob_type_info"][mission_start_npc_id]

        for instance_id, area_dict in sources["npc_instance_region_grouped_info"][mission_start_npc_id].items():
            for area_tag, npc_list in area_dict.items():
                for npc_obj in npc_list:
                    for reward_item in mission_obj["Rewards"]["Items"]:
                        sources["mission_reward_source_info"][reward_item["ID"]].append({
                            "NPCID": npc_obj["ID"],
                            "NPCTypeID": mission_start_npc_id,
                            "NPCName": mission_start_npc_type["Name"],
                            "NPCIcon": mission_start_npc_type["Icon"],
                            "X": npc_obj["X"],
                            "Y": npc_obj["Y"],
                            "Z": npc_obj["Z"],
                            "InstanceID": instance_id,
                            "AreaZone": area_tag,
                            "MissionItemRewardSelectionNeeded": mission_obj["Rewards"]["ItemSelectionNeeded"],
                            "MissionTaroReward": mission_obj["Rewards"]["Taros"],
                            "MissionFMReward": mission_obj["Rewards"]["FM"],
                            "MissionID": mission_obj["ID"],
                            "MissionName": mission_obj["Name"],
                            "MissionType": mission_obj["Type"],
                            "MissionDifficulty": mission_obj["Difficulty"],
                            "MissionLevel": mission_obj["Level"],
                            "MissionPrerequisites": mission_obj["RequiredMissions"],
                        })


def construct_egg_source_data(sources: dict) -> None:
    sources["egg_source_info"] = defaultdict(list)

    for egg_type_id, egg_type in sources["egg_type_info"].items():
        for instance_id, area_dict in sources["egg_instance_region_grouped_info"][egg_type_id].items():
            for area_tag, egg_list in area_dict.items():
                for egg_obj in egg_list:
                    sources["egg_source_info"][egg_type["CrateID"]].append({
                        "EggID": egg_obj["ID"],
                        "EggTypeID": egg_type_id,
                        "EggName": egg_type["Name"],
                        "EggComment": egg_type["Comment"],
                        "EggExtraComment": egg_type["ExtraComment"],
                        "X": egg_obj["X"],
                        "Y": egg_obj["Y"],
                        "Z": egg_obj["Z"],
                        "InstanceID": instance_id,
                        "AreaZone": area_tag,
                    })


def construct_crate_content_source_data(sources: dict) -> None:
    sources["crate_content_source_info"] = defaultdict(list)

    item_ref_to_str_id = {
        ir_id: "{Type:02d}{sep}{ItemID:04d}".format(**ir, sep=SEP)
        for ir_id, ir in sources["drops_map"]["ItemReferences"].items()
    }
    real_gender_map = {
        ir_id: sources["item_info"].get(item_str_id, {}).get("GenderID", 0)
        for ir_id, item_str_id in item_ref_to_str_id.items()
    }
    real_rarity_map = {
        ir_id: sources["item_info"].get(item_str_id, {}).get("RarityID", 0)
        for ir_id, item_str_id in item_ref_to_str_id.items()
    }
    itemset_views = {
        is_id: {
            gender_id: {
                rarity_id: {
                    ir_id: (
                        itemset["AlterItemWeightMap"].get(str(ir_id), itemset["DefaultItemWeight"])
                        if (
                            (itemset["IgnoreGender"] or itemset["AlterGenderMap"].get(str(ir_id), real_gender_map[ir_id]) in [0, gender_id])
                            and (itemset["IgnoreRarity"] or itemset["AlterRarityMap"].get(str(ir_id), real_rarity_map[ir_id]) in [0, rarity_id])
                        )
                        else 0
                    )
                    for ir_id in itemset["ItemReferenceIDs"]
                }
                for rarity_id in range(1, 5)
            }
            for gender_id in range(1, 3)
        }
        for is_id, itemset in sources["drops_map"]["ItemSets"].items()
    }

    for crate_id, crate_obj in sources["drops_map"]["Crates"].items():
        itemset_obj = sources["drops_map"]["ItemSets"][crate_obj["ItemSetID"]]
        rarity_weights_obj = sources["drops_map"]["RarityWeights"][crate_obj["RarityWeightID"]]

        itemset_view = itemset_views[itemset_obj["ItemSetID"]]
        boy_rarity_weights = itemset_view[GENDERS.index("Male")]
        girl_rarity_weights = itemset_view[GENDERS.index("Female")]

        boy_probabilities = defaultdict(Fraction)
        girl_probabilities = defaultdict(Fraction)

        total_weight = sum([
            weight
            for rarity_id, weight in zip(range(1, 5), rarity_weights_obj["Weights"])
            if sum(boy_rarity_weights[rarity_id].values()) > 0 or sum(girl_rarity_weights[rarity_id].values()) > 0
        ])

        for rarity_id, weight in zip(range(1, 5), rarity_weights_obj["Weights"]):
            rarity_probability = Fraction(weight, total_weight) if total_weight > 0 else Fraction(0)
            boy_rarity_ir_weights = boy_rarity_weights[rarity_id]
            girl_rarity_ir_weights = girl_rarity_weights[rarity_id]
            sum_boy_rarity_ir_weights = max(1, sum(boy_rarity_ir_weights.values()))
            sum_girl_rarity_ir_weights = max(1, sum(girl_rarity_ir_weights.values()))

            for ir_id in itemset_obj["ItemReferenceIDs"]:
                boy_probabilities[ir_id] += rarity_probability * Fraction(boy_rarity_ir_weights[ir_id], sum_boy_rarity_ir_weights)
                girl_probabilities[ir_id] += rarity_probability * Fraction(girl_rarity_ir_weights[ir_id], sum_girl_rarity_ir_weights)

        for ir_id in itemset_obj["ItemReferenceIDs"]:
            item_str_id = item_ref_to_str_id[ir_id]

            sources["crate_content_source_info"][item_str_id].append({
                "ContainingCrateID": crate_id,
                "BoyOdds": str(boy_probabilities[ir_id]),
                "GirlOdds": str(girl_probabilities[ir_id]),
                "BoyProbability": float(boy_probabilities[ir_id]),
                "GirlProbability": float(girl_probabilities[ir_id]),
            })


def construct_crate_source_data(sources: dict) -> None:
    sources["crate_source_info"] = defaultdict(list)

    for item_str_id, item_obj in sources["item_info"].items():
        if item_obj["TypeID"] != 9:
            continue

        crate_id = item_obj["ItemID"]

        # code item source
        for code_item_obj in sources["code_item_source_info"].get(item_str_id, []):
            sources["crate_source_info"][crate_id].append({
                "SourceType": "CodeItem",
                "Source": code_item_obj,
            })

        # vendor npc crate source
        for vendor_obj in sources["vendor_source_info"].get(item_str_id, []):
            sources["crate_source_info"][crate_id].append({
                "SourceType": "Vendor",
                "Source": vendor_obj,
                "SourcePrice": vendor_obj["Price"],
            })

        # egg crate source
        for egg_obj in sources["egg_source_info"].get(crate_id, []):
            sources["crate_source_info"][crate_id].append({
                "SourceType": "Egg",
                "Source": egg_obj,
            })

        # racing crate source
        for racing_obj in sources["racing_source_info"].get(crate_id, []):
            sources["crate_source_info"][crate_id].append({
                "SourceType": "Racing",
                "Source": racing_obj,
                "SourceStars": racing_obj["RequiredStars"],
                "SourceMinScore": racing_obj["RequiredScore"],
            })

        # mob crate source
        for mob_obj in sources["mob_source_info"].get(crate_id, []):
            sources["crate_source_info"][crate_id].append({
                "SourceType": "Mob",
                "Source": mob_obj,
                "SourceBoyOdds": mob_obj["Odds"],
                "SourceGirlOdds": mob_obj["Odds"],
                "SourceBoyProbability": mob_obj["Probability"],
                "SourceGirlProbability": mob_obj["Probability"],
            })

        # event crate source
        for event_obj in sources["event_source_info"].get(crate_id, []):
            sources["crate_source_info"][crate_id].append({
                "SourceType": "Event",
                "Source": event_obj,
                "SourceBoyOdds": event_obj["Odds"],
                "SourceGirlOdds": event_obj["Odds"],
                "SourceBoyProbability": event_obj["Probability"],
                "SourceGirlProbability": event_obj["Probability"],
            })

        # mission reward crate source
        for mission_reward_obj in sources["mission_reward_source_info"].get(item_str_id, []):
            sources["crate_source_info"][crate_id].append({
                "SourceType": "MissionReward",
                "Source": mission_reward_obj,
            })


def construct_item_source_data(sources: dict) -> None:
    sources["item_source_info"] = defaultdict(list)

    for item_str_id, item_obj in sources["item_info"].items():
        item_name = item_obj["Name"]
        item_tag = f"{item_str_id}{SEP}{item_name}"

        # code item source
        for code_item_obj in sources["code_item_source_info"].get(item_str_id, []):
            sources["item_source_info"][item_tag].append({
                "SourceType": "CodeItem",
                "Source": code_item_obj,
            })

        # vendor npc crate source
        for vendor_obj in sources["vendor_source_info"].get(item_str_id, []):
            sources["item_source_info"][item_tag].append({
                "SourceType": "Vendor",
                "Source": vendor_obj,
                "SourcePrice": vendor_obj["Price"],
            })

        # mission reward crate source
        for mission_reward_obj in sources["mission_reward_source_info"].get(item_str_id, []):
            sources["item_source_info"][item_tag].append({
                "SourceType": "MissionReward",
                "Source": mission_reward_obj,
            })

        # crate content source
        def source_recurse(str_id: str) -> list[dict]:
            crate_content_objs = sources["crate_content_source_info"].get(str_id, [])

            if not crate_content_objs:
                type_id, item_id = map(int, str_id.split(SEP))
                return sources["crate_source_info"].get(item_id, []) if type_id == 9 else []

            crate_sources = []

            for crate_content_obj in crate_content_objs:
                containing_crate_id = crate_content_obj["ContainingCrateID"]
                containing_crate_str_id = f"09{SEP}{containing_crate_id:04d}"
                boy_probability = Fraction(crate_content_obj["BoyOdds"])
                girl_probability = Fraction(crate_content_obj["GirlOdds"])

                for crate_source_obj in source_recurse(containing_crate_str_id):
                    source_type = crate_source_obj["SourceType"]

                    source_result = {
                        "SourceType": source_type if source_type != "MissionReward" else "MissionRewardCrate",
                        "Source": crate_source_obj["Source"],
                        "SourceBoyOdds": str(boy_probability * Fraction(crate_source_obj.get("SourceBoyOdds", 1.0))),
                        "SourceGirlOdds": str(girl_probability * Fraction(crate_source_obj.get("SourceGirlOdds", 1.0))),
                        "SourceBoyProbability": float(boy_probability) * crate_source_obj.get("SourceBoyProbability", 1.0),
                        "SourceGirlProbability": float(girl_probability) * crate_source_obj.get("SourceGirlProbability", 1.0),
                    }

                    if source_type == "Vendor":
                        source_result["SourcePrice"] = crate_source_obj["SourcePrice"]

                    if source_type == "Racing":
                        source_result["SourceStars"] = crate_source_obj["SourceStars"]
                        source_result["SourceMinScore"] = crate_source_obj["SourceMinScore"]

                    crate_sources.append(source_result)

            return crate_sources

        def source_merge_key(source_obj: dict) -> tuple[int, ...]:
            if source_obj["SourceType"] != "Mob":
                return (0, 0, 0, 0, 0, 0, 0)

            return (
                source_obj["Source"]["MobTypeID"],
                source_obj["Source"]["InstanceID"],
                source_obj["Source"]["LocationLimits"]["MinX"],
                source_obj["Source"]["LocationLimits"]["MinY"],
                source_obj["Source"]["LocationLimits"]["MinZ"],
                source_obj["Source"]["LocationLimits"]["MaxX"],
                source_obj["Source"]["LocationLimits"]["MaxY"],
                source_obj["Source"]["LocationLimits"]["MaxZ"],
            )

        if (recursed_sources := source_recurse(item_str_id)):
            mob_id_location_groupped_sources = {
                mob_id_location: list(source_iter)
                for mob_id_location, source_iter in groupby(
                    sorted(recursed_sources, key=source_merge_key),
                    key=source_merge_key,
                )
            }

            for mob_id_location, source_list in mob_id_location_groupped_sources.items():
                if mob_id_location[0] == 0 or len(source_list) < 2:
                    sources["item_source_info"][item_tag].extend(source_list)
                    continue

                merged_source = {
                    "SourceType": "Mob",
                    "Source": source_list[0]["Source"],
                    "SourceBoyOdds": str(sum(Fraction(source_obj["SourceBoyOdds"]) for source_obj in source_list)),
                    "SourceGirlOdds": str(sum(Fraction(source_obj["SourceGirlOdds"]) for source_obj in source_list)),
                    "SourceBoyProbability": sum(source_obj["SourceBoyProbability"] for source_obj in source_list),
                    "SourceGirlProbability": sum(source_obj["SourceGirlProbability"] for source_obj in source_list),
                }

                sources["item_source_info"][item_tag].append(merged_source)


def construct_source_item_data(sources: dict) -> None:
    sources["source_item_info"] = defaultdict(lambda: defaultdict(dict))

    for item_tag, source_obj_list in sources["item_source_info"].items():
        last_sep_idx = item_tag.rfind(SEP)
        item_obj = sources["item_info"][item_tag[:last_sep_idx]]

        for source_obj in source_obj_list:
            source_type_id = source_obj["SourceType"]
            source_info = source_obj["Source"]

            source_id = source_info[SOURCE_TYPE_ID_FIELD_MAP[source_type_id]]
            source_name = source_info[SOURCE_TYPE_NAME_FIELD_MAP[source_type_id]] if source_type_id != "CodeItem" else ""
            source_tag = f"{source_id}{SEP + source_name if source_name else ''}"

            sources["source_item_info"][source_type_id][source_tag][item_tag] = {
                "Item": item_obj,
                **{k: v for k, v in source_obj.items() if k not in ["SourceType", "Source"]},
            }


def fill_area_info(sources: dict) -> None:
    # add npc info
    for instanced_npc_dict in sources["npc_instance_region_grouped_info"].values():
        for region_npc_dict in instanced_npc_dict.values():
            for npc_obj_list in region_npc_dict.values():
                for npc_obj in npc_obj_list:
                    area_obj = locate_coordinates(sources["area_info"], npc_obj["X"], npc_obj["Y"])

                    if area_obj["AreaName"] == "Unknown":
                        continue

                    area_obj["NPCs"][npc_obj["ID"]] = npc_obj

                    # add npc type info
                    if npc_obj["TypeID"] not in area_obj["NPCTypes"]:
                        area_obj["NPCTypes"][npc_obj["TypeID"]] = sources["npc_type_info"][npc_obj["TypeID"]]

                    # add vendor info
                    if npc_obj["TypeID"] in sources["vendor_info"]:
                        area_obj["Vendors"][npc_obj["ID"]] = sources["vendor_info"][npc_obj["TypeID"]]

                    # add transportation info
                    if npc_obj["TypeID"] in sources["transportation_info"]:
                        area_obj["Transportation"][npc_obj["ID"]] = sources["transportation_info"][npc_obj["TypeID"]]

    # add mob info
    for instanced_mob_dict in sources["mob_instance_region_grouped_info"].values():
        for region_mob_dict in instanced_mob_dict.values():
            for mob_obj_list in region_mob_dict.values():
                for mob_obj in mob_obj_list:
                    area_obj = locate_coordinates(sources["area_info"], mob_obj["X"], mob_obj["Y"])

                    if area_obj["AreaName"] == "Unknown":
                        continue

                    area_obj["Mobs"][mob_obj["ID"]] = mob_obj

                    # add mob type info
                    if mob_obj["TypeID"] not in area_obj["MobTypes"]:
                        area_obj["MobTypes"][mob_obj["TypeID"]] = sources["mob_type_info"][mob_obj["TypeID"]]

    # add egg info
    for instanced_egg_dict in sources["egg_instance_region_grouped_info"].values():
        for region_egg_dict in instanced_egg_dict.values():
            for egg_obj_list in region_egg_dict.values():
                for egg_obj in egg_obj_list:
                    area_obj = locate_coordinates(sources["area_info"], egg_obj["X"], egg_obj["Y"])

                    if area_obj["AreaName"] == "Unknown":
                        continue

                    area_obj["Eggs"][egg_obj["ID"]] = egg_obj

                    # add egg type info
                    if egg_obj["TypeID"] not in area_obj["EggTypes"]:
                        area_obj["EggTypes"][egg_obj["TypeID"]] = sources["egg_type_info"][egg_obj["TypeID"]]

    # add instance warp info
    for instance_warp_obj in sources["instance_warp_info"].values():
        for region_npc_dict in sources["npc_instance_region_grouped_info"][instance_warp_obj["NPCID"]].values():
            for npc_obj_list in region_npc_dict.values():
                for npc_obj in npc_obj_list:
                    area_obj = locate_coordinates(sources["area_info"], npc_obj["X"], npc_obj["Y"])

                    if area_obj["AreaName"] == "Unknown":
                        continue

                    area_obj["InstanceWarps"][instance_warp_obj["ID"]] = instance_warp_obj

                    # add ep instance info
                    for ep_instance_obj in sources["infected_zone_info"].values():
                        if instance_warp_obj["ID"] in ep_instance_obj["EntryWarps"]:
                            area_obj["InfectedZone"] = ep_instance_obj


def construct_valid_id_sets(sources: dict) -> None:
    # valid mobs, npcs, eggs are those which are loaded by the server (tdata)
    sources["valid_npc_types"] = {
        obj["iNPCType"] for obj in sources["npcs"]["NPCs"].values()
    }

    sources["valid_mob_types"] = (
        {obj["iNPCType"] for obj in sources["mobs"]["mobs"].values()}
        | {obj["iNPCType"] for obj in sources["mobs"]["groups"].values()}
        | {o["iNPCType"] for obj in sources["mobs"]["groups"].values() for o in obj["aFollowers"]}
    )

    sources["valid_npc_mob_types"] = sources["valid_npc_types"] | sources["valid_mob_types"]

    sources["valid_egg_types"] = {
        obj["Id"] for obj in sources["eggs"]["EggTypes"].values()
    }

    sources["valid_npcs"] = {
        str_id
        for type_id, obj_dict in sources["npc_info"].items()
        if type_id in sources["valid_npc_types"]
        for str_id in obj_dict
    }

    sources["valid_mobs"] = {
        str_id
        for type_id, obj_list in sources["mob_info"].items()
        if type_id in sources["valid_mob_types"]
        for str_id in obj_list
    }

    sources["valid_npc_mobs"] = sources["valid_npcs"] | sources["valid_mobs"]

    sources["valid_eggs"] = {
        str_id
        for type_id, obj_list in sources["egg_info"].items()
        if type_id in sources["valid_egg_types"]
        for str_id in obj_list
    }

    # vendors whose npcs are loaded are valid
    sources["valid_vendors"] = {
        obj["NPCID"]
        for obj in sources["vendor_info"].values()
        if obj["NPCID"] in sources["valid_npc_types"]
    }

    # mission logic
    def mission_npc_valid(npc_id: int) -> bool:
        return npc_id == 0 or npc_id not in sources["npc_mob_type_info"] or npc_id in sources["valid_npc_mob_types"]

    sources["valid_missions"] = {
        obj["ID"]
        for obj in sources["mission_info"].values()
        if (
            # mission should be startable by a valid npc
            mission_npc_valid(obj["MissionStartNPCID"])
            # mission should be endable by a valid npc
            and mission_npc_valid(obj["MissionEndNPCID"])
            # mission should have valid npcs to talk to
            and all(
                mission_npc_valid(task_obj["WaypointNPCID"])
                for task_obj in obj["Tasks"].values()
                if task_obj["TypeID"] == 1
            )
            # mission should have valid npcs to escort
            and all(
                mission_npc_valid(task_obj["EscortNPCID"])
                for task_obj in obj["Tasks"].values()
                if task_obj["TypeID"] == 6
            )
        )
    }

    # instance warps are valid if their npc type is loaded and a valid mission is required if any
    sources["valid_instance_warps"] = {
        obj["ID"]
        for obj in sources["instance_warp_info"].values()
        if (
            obj["NPCID"] in sources["valid_npc_mob_types"]
            and (obj["RequiredMissionID"] == 0 or obj["RequiredMissionID"] in sources["valid_missions"])
        )
    }

    # instances are valid if any of their enrty warps are valid
    sources["valid_instances"] = {
        obj["ID"]
        for obj in sources["instance_info"].values()
        if any(warp_id in sources["valid_instance_warps"] for warp_id in obj["EntryWarps"])
    }

    # ep instances are valid if any of their enrty warps are valid
    sources["valid_infected_zones"] = {
        obj["ID"]
        for obj in sources["infected_zone_info"].values()
        if any(warp_id in sources["valid_instance_warps"] for warp_id in obj["EntryWarps"])
    }

    # transportations are valid if their npc type is loaded
    sources["valid_transportations"] = {
        obj["NPCID"]
        for obj in sources["transportation_info"].values()
        if obj["NPCID"] in sources["valid_npc_mob_types"]
    }

    # items that are valid are those that are obtainable by at least one source
    def source_valid(source_obj: dict) -> bool:
        if source_obj["SourceType"] in ["CodeItem", "Event"]:
            return True

        if source_obj["SourceType"] == "Vendor":
            return source_obj["Source"]["NPCID"] in sources["valid_vendors"]

        if source_obj["SourceType"] == "Egg":
            return source_obj["Source"]["EggTypeID"] in sources["valid_egg_types"]

        if source_obj["SourceType"] == "Racing":
            return source_obj["Source"]["InstanceID"] in sources["valid_instances"]

        if source_obj["SourceType"] == "Mob":
            return source_obj["Source"]["MobTypeID"] in sources["valid_mob_types"]

        if source_obj["SourceType"] == "MissionReward":
            return source_obj["Source"]["MissionID"] in sources["valid_missions"]

        return False

    sources["valid_items"] = {
        obj["ID"]
        for obj in sources["item_info"].values()
        if any(
            source_valid(source_obj)
            for source_obj in sources["item_source_info"].get(
                "{ID}{SEP}{Name}".format(**obj, SEP=SEP),
                [],
            )
        )
    }


def mark_valid_sources(sources: dict) -> None:
    def mark_single(dct: dict[str, dict], key: str, valids_key: str, mark_key: str = "InGame") -> None:
        dct[key] = {
            obj_id: {**obj, mark_key: obj_id in sources[valids_key]}
            for obj_id, obj in dct[key].items()
        }

    mark_single(sources, "npc_type_info", "valid_npc_types")
    mark_single(sources, "mob_type_info", "valid_mob_types")
    mark_single(sources, "egg_type_info", "valid_egg_types")
    mark_single(sources, "mission_info", "valid_missions")
    mark_single(sources, "instance_info", "valid_instances")
    mark_single(sources, "infected_zone_info", "valid_infected_zones")
    mark_single(sources, "transportation_info", "valid_transportations")
    mark_single(sources, "vendor_info", "valid_vendors")
    mark_single(sources, "item_info", "valid_items", mark_key="Obtainable")


def export_json_source_info(out_info_dir: Path, sources: dict) -> None:
    source_keys = [
        "item_info",
        "npc_type_info",
        "mob_type_info",
        "npc_info",
        "mob_info",
        "egg_type_info",
        "egg_info",
        "mission_info",
        "instance_info",
        "nano_info",
        "area_info",
        "vendor_info",
        "infected_zone_info",
        "code_item_info",
        "transportation_info",
        "combination_info",
        "item_source_info",
        "source_item_info",
    ]

    for key in source_keys:
        with open(out_info_dir / f"{key}.json", "w") as f:
            json.dump(sources[key], f, indent=4, sort_keys=True)


def export_csv_source_info(out_info_dir: Path, sources: dict) -> None:
    def short_item_str(v: dict) -> str:
        return f"{v['ItemID']} {v['Name']} ({v['DisplayType']} Lv{v['ContentLevel']} {v['Rarity']})"

    def get_instance_area_name(v: dict) -> str:
        return sources["instance_info"].get(v.get("InstanceID", 0), {"Name": v["AreaZone"]})["Name"]

    def get_coordinate_str(v: dict) -> str:
        return f"X: {v['X']} Y: {v['Y']} Z: {v['Z']}"

    def get_location_instance_str(v: dict, include_coordinate: bool = True) -> str:
        if include_coordinate:
            return f"{get_instance_area_name(v)} {get_coordinate_str(v)}"
        return get_instance_area_name(v)

    csv_fields = {
        "item_info": {
            "Type": "Type",
            "WeaponType": "Weapon Type",
            "ItemID": "ID",
            "Name": "Name",
            "ContentLevel": "Level",
            "Rarity": "Rarity",
            "Obtainable": "Obtainable",
            "Tradeable": "Tradeable",
            "Sellable": "Vendor Sellable",
            "Range": "Range",
            "SingleDamage": "Damage",
            "MultiDamage": "Damage (Multi)",
            "Defense": "Defense",
            "VehicleClass": "Vehicle Speed",
            "ItemPrice": "Price",
            "ItemSellPrice": "Sell Price",
            "Description": "Description",
        },
        "code_item_info": {
            "Code": "Code",
            "Items": "Items",
        },
        "egg_info": {
            "ID": "ID",
            "TypeID": "Type ID",
            "TypeName": "Type",
            "InstanceID": "Instance",
            "AreaZone": "Area",
            "X": "X",
            "Y": "Y",
            "Z": "Z",
        },
        "egg_type_info": {
            "ID": "ID",
            "Name": "Type",
            "CrateID": "Crate ID",
            "Effect": "Effect",
            "InGame": "In Game",
            "EffectDuration": "Effect Duration Seconds",
            "RespawnTime": "Respawn Time",
        },
        "infected_zone_info": {
            "ID": "ID",
            "Name": "Name",
            "AreaZone": "Area",
            "ZoneX": "X Zone",
            "ZoneY": "Y Zone",
            "InGame": "In Game",
            "ScoreCap": "Score Cap",
            "TotalPods": "Total Pods",
            "TimeLimit": "Time Limit",
            "ScaleFactor": "Scale Factor",
            "PodFactor": "Pod Factor",
            "TimeFactor": "Time Factor",
            "StarsToItemRewards": "Rewards",
        },
        "instance_info": {
            "ID": "ID",
            "EPID": "Infected Zone ID",
            "Name": "Name",
            "AreaZone": "Area",
            "ZoneX": "X Zone",
            "ZoneY": "Y Zone",
            "InGame": "In Game",
        },
        "mission_info": {
            "ID": "ID",
            "Name": "Name",
            "Level": "Level",
            "Type": "Type",
            "Difficulty": "Difficulty",
            "InGame": "In Game",
            "MissionStartNPCName": "Start NPC",
            "MissionJournalNPCName": "Journal NPC",
            "MissionEndNPCName": "End NPC",
            "RequiredNano": "Required Nano",
            "RequiredGuide": "Required Guide",
            "RequiredMissions": "Required Missions",
            "Rewards": "Rewards",
            "Tasks": "Tasks",
        },
        "mob_info": {
            "ID": "ID",
            "TypeID": "Type ID",
            "TypeName": "Name",
            "FollowsMobID": "Follows",
            "InstanceID": "Instance",
            "AreaZone": "Area",
            "HP": "HP",
            "X": "X",
            "Y": "Y",
            "Z": "Z",
            "Angle": "Angle",
        },
        "mob_type_info": {
            "ID": "ID",
            "Name": "Name",
            "Level": "Level",
            "ColorType": "Color Type",
            "InGame": "In Game",
            "StandardHP": "HP",
            "Accuracy": "Accuracy",
            "Protection": "Protection",
            "Radius": "Radius",
            "ActiveSkill": "Active Skill",
            "SupportSkill": "Support Skill",
            "AttackPower": "Attack Power",
            "SightRange": "Sight Range",
            "IdleRange": "Idle Range",
            "CombatRange": "Combat Range",
            "AttackRange": "Attack Range",
            "ActiveSkillRange": "Active Skill Range",
            "CorruptionRange": "Corruption Range",
            "EruptionRange": "Eruption Range",
            "EruptionArea": "Eruption Area",
            "WalkSpeed": "Walk Speed",
            "RunSpeed": "Run Speed",
            "RespawnTime": "Respawn Time",
        },
        "nano_info": {
            "ID": "ID",
            "Name": "Name",
            "Comment": "Comment",
            "NanoType": "Type",
            "NanoPowers": "Powers",
        },
        "npc_info": {
            "ID": "ID",
            "TypeID": "Type ID",
            "TypeName": "Name",
            "InstanceID": "Instance",
            "AreaZone": "Area",
            "X": "X",
            "Y": "Y",
            "Z": "Z",
            "Angle": "Angle",
        },
        "npc_type_info": {
            "ID": "ID",
            "HNPCTypeID": "HNPC ID",
            "Name": "Name",
            "Category": "Category",
            "InGame": "In Game",
            "Comment": "Comment",
            "Barkers": "Barkers",
        },
        "transportation_info": {
            "NPCID": "NPC ID",
            "NPCType": "NPC Name",
            "MoveType": "Move Type",
            "InGame": "In Game",
            "StartLocation": "Start Location",
            "Transportations": "Destinations",
        },
        "vendor_info": {
            "NPCID": "NPC",
            "InGame": "In Game",
            "NPCs": "Locations",
            "Items": "Items",
        },
        "combination_info": {
            "LevelGap": "Level Gap",
            "SameRarity": "Same Rarity Chance %",
            "OneRarityDiff": "One Rarity Diff. Chance %",
            "TwoRarityDiff": "Two Rarity Diff. Chance %",
            "ThreeRarityDiff": "Three Rarity Diff. Chance %",
            "LooksItemPriceMultiplier": "Looks Item Price Multp.",
            "StatsItemPriceMultiplier": "Stats Item Price Multp.",
        },
    }
    converters = {
        "code_item_info": {
            "Items": lambda obj: "\n".join(map(short_item_str, obj["Items"].values())),
        },
        "egg_info": {
            "TypeName": lambda obj: f"{obj['TypeName']} ({obj['TypeComment']} {obj['TypeExtraComment']})",
            "InstanceID": get_instance_area_name,
        },
        "egg_type_info": {
            "Name": lambda obj: f"{obj['Name']} ({obj['Comment']} {obj['ExtraComment']})",
        },
        "infected_zone_info": {
            "StarsToItemRewards": lambda obj: "\n".join(
                f"{v['Item']['ItemID']} {v['Item']['Name']} {v['Item']['Description']} (Min. Score: {v['RankScore']})"
                for v in obj["StarsToItemRewards"].values()
            ),
        },
        "mission_info": {
            "RequiredMissions": lambda obj: "\n".join(f"{k} {v}" for k, v in obj["RequiredMissions"].items()),
            "Rewards": lambda obj: "\n".join(
                (
                    [f"{obj['Rewards']['NanoReward']}"]
                    if obj["Rewards"]["NanoRewardID"] > 0
                    else [f"Taros: {obj['Rewards']['Taros']} FM: {obj['Rewards']['FM']}"]
                ) +
                [
                    short_item_str(v)
                    for v in obj["Rewards"]["Items"]
                ]
            ),
            "Tasks": lambda obj: "\n".join(
                f"{v['ID']} {v['CurrentObjective']}"
                for v in obj["Tasks"].values()
            ),
        },
        "mob_info": {
            "InstanceID": get_instance_area_name,
        },
        "nano_info": {
            "NanoPowers": lambda obj: "\n".join(
                f"{k} {v['TypeName']} - {v['SkillName']} - {v['Comment']}"
                for k, v in obj["NanoPowers"].items()
            ),
        },
        "npc_info": {
            "InstanceID": get_instance_area_name,
        },
        "npc_type_info": {
            "Barkers": lambda obj: "\n".join(v for v in obj["Barkers"] if v),
        },
        "transportation_info": {
            "NPCType": lambda obj: f"{obj['NPCType']['ID']} {obj['NPCType']['Name']}" if obj["NPCType"] else "",
            "StartLocation": lambda obj: f"{obj['StartLocation']['ID']} {get_location_instance_str(obj['StartLocation'])}",
            "Transportations": lambda obj: "\n".join(
                f"{v['ID']} {get_location_instance_str(v)} (Speed: {v['SpeedClass']} Taros: {v['Cost']})"
                for v in obj["Transportations"].values()
            ),
        },
        "vendor_info": {
            "NPCID": lambda obj: f"{obj['NPCID']} {sources['npc_type_info'][obj['NPCID']]['Name']}",
            "NPCs": lambda obj: "\n".join(f"{k} {get_location_instance_str(v)}" for k, v in obj["NPCs"].items()),
            "Items": lambda obj: "\n".join(
                f"{short_item_str(v['Item'])} Taros: {v['Price']}"
                for v in obj["Items"].values()
            ),
        },
    }

    # export regular tables
    for key, field_map in csv_fields.items():
        with open(out_info_dir / f"{key}_table.csv", "w") as f:
            writer = csv.DictWriter(f, fieldnames=list(field_map.values()))
            writer.writeheader()

            for obj in sources[key].values():
                objects = list(obj.values()) if key in ["egg_info", "npc_info", "mob_info"] else [obj]

                for o in objects:
                    writer.writerow({
                        field_map[k]: converters.get(key, {}).get(k, itemgetter(k))(o)
                        for k in o
                        if k in field_map
                    })

    source_fields = {
        "SourceBoyOdds": "Odds (Boy)",
        "SourceGirlOdds": "Odds (Girl)",
        "SourcePrice": "Price",
        "SourceStars": "Stars",
        "SourceMinScore": "Min. Score",
    }
    extra_info_getters = {
        "Mob": lambda src_id, include_coordinate: "\n".join(
            ["Lv{Level} {ColorType}".format(**sources["mob_type_info"][src_id])] +
            sorted({
                get_location_instance_str({"InstanceID": instance_id, "AreaZone": area_tag}, include_coordinate=False)
                for instance_id, area_dict in sources["mob_instance_region_grouped_info"][src_id].items()
                for area_tag in area_dict
            })
        ),
        "Vendor": lambda src_id, include_coordinate: "\n".join(
            sorted({
                get_location_instance_str(v, include_coordinate)
                for v in sources["vendor_info"][src_id]["NPCs"].values()
            })
        ),
        "MissionReward": lambda src_id, include_coordinate: "\n".join(
            sorted({
                get_location_instance_str(v, include_coordinate)
                for v in sources["npc_info"].get(sources["mission_info"].get(src_id, {}).get("MissionStartNPCID", 0), {}).values()
            })
        ),
        "MissionRewardCrate": lambda src_id, include_coordinate: "\n".join(
            sorted({
                get_location_instance_str(v, include_coordinate)
                for v in sources["npc_info"].get(sources["mission_info"].get(src_id, {}).get("MissionStartNPCID", 0), {}).values()
            })
        ),
        "Egg": lambda src_id, include_coordinate: "\n".join(
            sorted({
                get_location_instance_str(v, include_coordinate)
                for v in sources["egg_info"][src_id].values()
            })
        ),
        "Racing": lambda src_id, include_coordinate: "{AreaZone}\nPods: {TotalPods} Time Limit: {TimeLimit}".format(
            **sources["infected_zone_info"][src_id]
        ),
    }

    # export source to item table
    with open(out_info_dir / "source_item_info_table.csv", "w") as f:
        writer = csv.DictWriter(f, fieldnames=["Source Type", "Source", "Source Extra Info", "Items", "Items Extra Info"])
        writer.writeheader()

        for source_type, source_items in sources["source_item_info"].items():
            for source_id, items in source_items.items():
                writer.writerow({
                    "Source Type": source_type,
                    "Source": source_id.replace(SEP, " "),
                    "Source Extra Info": (
                        extra_info_getters[source_type](int(source_id.split(SEP)[0]), include_coordinate=True)
                        if source_type in extra_info_getters
                        else ""
                    ),
                    "Items": "\n".join(short_item_str(v["Item"]) for v in items.values()),
                    "Items Extra Info": "\n".join(
                        " ".join(f"{f_v}: {v[f_k]}" for f_k, f_v in source_fields.items() if f_k in v)
                        for v in items.values()
                    ),
                })

    # export item to source table
    with open(out_info_dir / "item_source_info_table.csv", "w") as f:
        writer = csv.DictWriter(f, fieldnames=["Type", "Weapon Type", "ID", "Name", "Level", "Rarity", "Sources", "Sources Extra Info"])
        writer.writeheader()

        for item_tag, source_object_list in sources["item_source_info"].items():
            item_str_id = SEP.join(item_tag.split(SEP)[:2])
            item_obj = sources["item_info"][item_str_id]

            source_strings = []
            source_extra_info_strings = []

            for source_object in source_object_list:
                source_type = source_object["SourceType"]
                source_info = source_object["Source"]
                source_id = source_info[SOURCE_TYPE_ID_FIELD_MAP[source_type]]
                source_name = source_info.get(SOURCE_TYPE_NAME_FIELD_MAP.get(source_type), "")
                source_metadata = (
                    extra_info_getters[source_type](source_id, include_coordinate=False).replace("\n", " | ")
                    if source_type in extra_info_getters
                    else ""
                )

                source_strings.append(" ".join(v for v in [source_type, str(source_id), source_name, source_metadata] if v))
                source_extra_info_strings.append(
                    " ".join(
                        f"{f_v}: {source_object[f_k]}"
                        for f_k, f_v in source_fields.items()
                        if f_k in source_object and f_k not in ["Source", "SourceType"]
                    )
                )
                if not source_extra_info_strings[-1]:
                    source_extra_info_strings[-1] = "-"

            writer.writerow({
                "Type": item_obj["Type"],
                "Weapon Type": item_obj["WeaponType"],
                "ID": item_obj["ItemID"],
                "Name": item_obj["Name"],
                "Level": item_obj["ContentLevel"],
                "Rarity": item_obj["Rarity"],
                "Sources": "\n".join(source_strings),
                "Sources Extra Info": "\n".join(source_extra_info_strings),
            })


def export_graph_source_info(out_info_dir: Path, sources: dict) -> None:
    random.seed(2009)
    # mission dependency graph
    G = nx.DiGraph()

    for mission_data in sources["mission_info"].values():
        for required_mission_id, required_mission_name in mission_data["RequiredMissions"].items():
            required_mission_data = sources["mission_info"].get(required_mission_id, {"Level": 0})
            G.add_edge(
                f"Lv{mission_data['Level']} {mission_data['Name'].replace('\n', ' ')}{' [X]' if not mission_data['InGame'] else ''}",
                f"Lv{required_mission_data['Level']} {required_mission_name.replace('\n', ' ')}{' [X]' if not required_mission_data['InGame'] else ''}",
            )

    warnings.filterwarnings("ignore", category=UserWarning)
    plt.figure(figsize=(40, 40))
    pos = nx.nx_agraph.graphviz_layout(G, prog="neato", args="-Goverlap=false")

    subgraphs = [G.subgraph(c) for c in nx.connected_components(G.to_undirected())]
    for subgraph in subgraphs:
        c = [random.random()] * nx.number_of_nodes(subgraph)
        nx.draw(subgraph, pos, with_labels=False, arrowstyle="<-", node_size=80, node_color=c, vmin=0, vmax=1)

        valid_subgraph = subgraph.subgraph([n for n in subgraph.nodes() if "[X]" not in n])
        invalid_subgraph = subgraph.subgraph([n for n in subgraph.nodes() if "[X]" in n])
        nx.draw_networkx_labels(
            valid_subgraph,
            pos,
            font_size=10,
            bbox={"facecolor": "white", "alpha": 0.5, "edgecolor": "black"},
        )
        nx.draw_networkx_labels(
            invalid_subgraph,
            pos,
            font_size=10,
            bbox={"facecolor": "red", "alpha": 0.5, "edgecolor": "brown"},
        )

    plt.savefig(out_info_dir / "mission_dependency_graph.png")
    plt.close()
    warnings.resetwarnings()


def extract_derived_info(in_dir: Path, out_info_dir: Path, server_data_dir: Path, patch_names: list[str]):
    out_info_dir.mkdir(parents=True, exist_ok=True)

    sources = {}

    with open(in_dir / "areas.json", "r") as f:
        sources["areas"] = json.load(f)

    with open(in_dir / "xdt.json", "r") as f:
        sources["xdt"] = json.load(f)

    construct_drop_directory_data(sources, server_data_dir, patch_names)
    construct_area_data(sources)
    construct_item_info_data(sources)
    construct_npc_mob_info_data(sources)
    construct_egg_data(sources)
    construct_mission_data(sources)
    construct_instance_data(sources)
    construct_transportation_data(sources)
    construct_nano_data(sources)
    construct_vendor_data(sources)
    construct_ep_instance_data(sources)
    construct_code_item_data(sources)
    construct_combination_data(sources)
    construct_egg_instance_region_grouped_data(sources)
    construct_npc_instance_region_grouped_data(sources)
    construct_mob_instance_region_grouped_data(sources)
    construct_code_item_source_data(sources)
    construct_vendor_source_data(sources)
    construct_racing_source_data(sources)
    construct_mob_event_source_data(sources)
    construct_mission_reward_source_data(sources)
    construct_egg_source_data(sources)
    construct_crate_content_source_data(sources)
    construct_crate_source_data(sources)
    construct_item_source_data(sources)
    construct_source_item_data(sources)
    fill_area_info(sources)
    construct_valid_id_sets(sources)
    mark_valid_sources(sources)

    export_json_source_info(out_info_dir, sources)
    export_csv_source_info(out_info_dir, sources)
    export_graph_source_info(out_info_dir, sources)


def main(config_path: Path, output_root: Path, server_data_root: Path):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)["config"]

    in_dirs = [p for p in output_root.iterdir() if p.is_dir()]
    for in_dir in tqdm(in_dirs):
        server_data_config = config[in_dir.name]["server-data"]
        extract_derived_info(
            in_dir,
            in_dir / "info",
            server_data_root / server_data_config["repository"].strip("/"),
            server_data_config.get("patches", []),
        )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python extract_derived_info.py <config_path> <output_root> <server_data_root>")
        sys.exit(1)

    main(*map(Path, sys.argv[1:]))
