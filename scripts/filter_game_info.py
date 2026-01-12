import sys
import json
import shutil
import traceback
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Optional

import yaml
from tqdm import tqdm

USE_EXCLUDED_IDS = "<excluded_ids>"
USE_INDEX = "<index>"
USE_TYPE = "<type>"
USE_TYPE_ID = "<type_id>"
ITEM_CATEGORY = "item"


class FilterFuncs:
    @staticmethod
    def area_include(source: list[dict], set_of_xywh: set[tuple[int, int, int, int]]) -> list[bool]:
        # or logic over multiple areas
        # include if completely inside any area
        include_source = [False] * len(source)

        for x, y, w, h in set_of_xywh:
            include_source = [
                (
                    truth or
                    (
                        x <= d["Area"]["x"] and
                        y <= d["Area"]["y"] and
                        x + w >= d["Area"]["x"] + d["Area"]["width"] and
                        y + h >= d["Area"]["y"] + d["Area"]["height"]
                    )
                )
                for truth, d in zip(include_source, source)
            ]

        return include_source


class MapFuncs:
    @staticmethod
    def nano_icon_file(source: list[dict]) -> list[list[str]]:
        return [[f"icons/nanoicon_{d['m_iIconNumber']:02d}.png"] for d in source]

    @staticmethod
    def skill_icon_file(source: list[dict]) -> list[list[str]]:
        return [[f"icons/skillicon_{d['m_iIconNumber']:02d}.png"] for d in source]

    @staticmethod
    def npc_icon_file(source: list[dict]) -> list[list[str]]:
        prefix_table = {
            4: "npcicon",
            8: "mobicon",
            10: "hnpcicon",
        }

        return [
            [f"icons/{prefix_table.get(d['m_iIconType'])}_{d['m_iIconNumber']:02d}.png"]
            for d in source
        ]

    @staticmethod
    def trans_icon_file(source: list[dict]) -> list[list[str]]:
        return [[f"icons/transport_{d['m_iIconNumber']:02d}.png"] for d in source]

    @staticmethod
    def item_icon_file(source: list[dict]) -> list[list[str]]:
        prefix_table = {
            0: "wpnicon",
            1: "cosicon",
            2: "cosicon",
            3: "cosicon",
            4: "cosicon",
            5: "cosicon",
            6: "cosicon",
            7: "generalitemicon",
            9: "generalitemicon",
            10: "vehicle",
            11: "mobicon",
            12: "vehicle",
        }

        return [
            [f"icons/{prefix_table.get(d['m_iIconType'])}_{d['m_iIconNumber']:02d}.png"]
            for d in source
        ]


class ExcludeFuncs:
    @staticmethod
    def icon_dir(context: dict, exclude_ids: set[str]) -> None:
        for icon_file in exclude_ids:
            icon_file_path = Path(context["out_dir"]) / icon_file

            if icon_file_path.is_file():
                icon_file_path.unlink()


def split_get(d: dict, config: str) -> Any:
    dc = d

    try:
        for key in config.split("."):
            if key:
                conv = int if isinstance(dc, list) else str
                dc = dc[conv(key)]
    except:
        return None

    return dc


def resolve_from_context(context: dict, config: str | list) -> list:
    if isinstance(config, list):
        return config

    union_pieces = [pc.strip() for pc in config.split("+")]
    result = []

    for piece in union_pieces:
        if piece in context:
            if isinstance(context[piece], list):
                result.extend(context[piece])
            else:
                result.append(context[piece])
        else:
            try:
                possible_list = eval(piece)
                if isinstance(possible_list, list):
                    result.extend(possible_list)
            except:
                pass

    return result


def resolve_template_string(context: dict, template_string: str) -> str:
    template_context_keys = {k for k in context if k.startswith("<") and k.endswith(">")}

    for key in template_context_keys:
        if key in template_string:
            template_string = template_string.replace(key, str(context[key]))

    return template_string


def filter_from_config(config: str, list_of_ids: list[Any]) -> Callable[[list[dict]], list[bool]]:
    set_of_ids = {(tuple(idx) if isinstance(idx, list) else idx) for idx in list_of_ids}

    def getter(i: int, d: dict) -> list[Any]:
        if config == USE_INDEX:
            return [i]

        val = split_get(d, config)
        return val if isinstance(val, list) else [val]

    def filter_func(l_d: list[dict]) -> list[bool]:
        if config.startswith("<") and config.endswith(">") and config != USE_INDEX:
            return getattr(FilterFuncs, config[1:-1])(l_d, set_of_ids)

        # include if inside ids
        return [any(v in set_of_ids for v in getter(i, d)) for i, d in enumerate(l_d)]

    return filter_func


def map_from_config(config: str) -> Callable[[list[dict]], list[list[Any]]]:
    def getter(i: int, d: dict) -> list[Any]:
        if config == USE_INDEX:
            return [i]

        val = split_get(d, config)
        return val if isinstance(val, list) else [val]

    def map_func(l_d: list[dict]) -> list[list[Any]]:
        if config.startswith("<") and config.endswith(">") and config != USE_INDEX:
            return getattr(MapFuncs, config[1:-1])(l_d)

        return [getter(i, d) for i, d in enumerate(l_d)]

    return map_func


def operator_take_from(context: dict, all_sources: dict, from_config: str) -> Optional[list[dict]]:
    return resolve_from_context(context, from_config) or split_get(all_sources, resolve_template_string(context, from_config))


def operator_filter(context: dict, source: Optional[list[dict]], filter_config: list[dict]) -> list[bool]:
    if source is None:
        return []

    # and logic over multiple filters
    include_source = [True] * len(source)

    for filter_cfg in filter_config:
        by_config = filter_cfg["by"]
        values_config = filter_cfg["values"]

        list_of_ids = resolve_from_context(context, values_config)
        by_func = filter_from_config(by_config, list_of_ids)
        by_source = by_func(source)

        # and logic over multiple filters
        include_source = [
            truth and next_truth
            for truth, next_truth in zip(include_source, by_source)
        ]

    return include_source


def operator_map_to_unused_ids(source: Optional[list[dict]], include_source: list[bool], map_config: list[dict]) -> set[Any]:
    if source is None:
        return set()

    global_ids = set()

    for map_cfg in map_config:
        usages = defaultdict(set)

        val_getter = map_from_config(map_cfg["key"])
        register_usages_by = map_cfg.get("register_usages_by")

        erase_id_lists = val_getter(source)
        included_usage_id_set = set()

        if register_usages_by:
            usage_key_getter = map_from_config(register_usages_by)
            usage_id_lists = usage_key_getter(source)

            for erase_ids, usage_ids, include in zip(erase_id_lists, usage_id_lists, include_source):
                if include:
                    included_usage_id_set.update(usage_ids)

                for erase_id in erase_ids:
                    usages[erase_id].update(usage_ids)

        current_ids = {
            erase_id
            for erase_ids, include in zip(erase_id_lists, include_source)
            for erase_id in erase_ids
            # make sure that there isn't a usage that is not included
            if include and (erase_id not in usages or included_usage_id_set.issuperset(usages[erase_id]))
        }

        global_ids.update(current_ids)

    return global_ids


def operator_ids(context: dict, all_sources: dict, ids_config: dict) -> set[Any]:
    from_config = ids_config["from"]
    filter_config = ids_config["filter"]
    map_config = ids_config["map"]

    source = operator_take_from(context, all_sources, from_config)
    include_source = operator_filter(context, source, filter_config)
    return operator_map_to_unused_ids(source, include_source, map_config)


def operator_exclude(context: dict, all_sources: dict, exclude_config: dict, exclude_ids: set[Any]) -> None:
    from_config = exclude_config["from"]
    is_xdt_mode = from_config.startswith("xdt")

    if from_config.startswith("<") and from_config.endswith(">"):
        getattr(ExcludeFuncs, from_config[1:-1])(context, exclude_ids)
        return

    source = operator_take_from(context, all_sources, from_config)

    if source is None:
        return

    matching_config = exclude_config["matching"]
    val_getter = map_from_config(matching_config)
    val_lists = val_getter(source)

    new_source = []
    index_repeat = 0
    dummy_obj = source[0]

    for val_list, d in zip(val_lists, source):
        # if xdt mode, only nonzero and nonempty values are included
        if not any(v in exclude_ids for v in val_list):
            if matching_config == USE_INDEX and is_xdt_mode:
                new_source.extend([dummy_obj] * index_repeat)
                index_repeat = 0

            new_source.append(d)
        elif matching_config == USE_INDEX and is_xdt_mode:
            index_repeat += 1

    source.clear()
    source.extend(new_source)


def operator_step(context: dict, all_sources: dict, modified_sources: dict, step_name: str, step_config: dict, how_config: dict, extras_ids: set[Any]) -> None:
    if "run_steps" in step_config:
        copied_steps = deepcopy(how_config[step_config["run_steps"]])

        if "override" in step_config:
            for key, value in step_config["override"].items():
                copied_steps[key].update(value)

        for copied_step_name, copied_step_config in copied_steps.items():
            old_trace = context["trace"]
            context["trace"] = f"{old_trace}.{copied_step_name}"
            operator_step(context, all_sources, modified_sources, copied_step_name, copied_step_config, how_config, extras_ids)
            context["trace"] = old_trace
    else:
        ids_config = step_config["ids"]
        exclude_config = step_config["exclude"]
        skip_extras = step_config.get("skip_extras", False)

        old_trace = context["trace"]
        context["trace"] = f"{old_trace}.ids"
        exclude_ids = operator_ids(context, all_sources, ids_config)
        if skip_extras:
            # do not exclude ids specified in the extras config
            exclude_ids = exclude_ids - extras_ids
        context[f"{step_name}.ids"] = list(exclude_ids)

        context["trace"] = f"{old_trace}.exclude"
        operator_exclude(context, modified_sources, exclude_config, exclude_ids)
        context["trace"] = old_trace


def run_all_steps(global_context: dict, all_sources: dict, all_config: dict) -> dict[str, Any]:
    exclude_config = all_config["exclude"]
    how_config = all_config["how"]
    extras_config = all_config["extras"]

    type_to_id = {
        "Weapon": 0,
        "Shirts": 1,
        "Pants": 2,
        "Shoes": 3,
        "Hat": 4,
        "Glass": 5,
        "Back": 6,
        "General": 7,
        "Chest": 9,
        "Vehicle": 10,
    }
    exclude_keys_to_extras = {
        "npc": ["extra_npcs", "extra_mobs"],
        "shiny": ["extra_eggs"],
    }

    modified_sources = deepcopy(all_sources)

    for exclude_key, excluded_ids in exclude_config.items():
        how_key = exclude_key
        extras_ids = {
            extras_id
            for key in exclude_keys_to_extras.get(exclude_key, [])
            for extras_id, extras_dict in extras_config.get(key, {}).items()
            if extras_dict["event_name"] in ["None", global_context["active_event"]]
        }
        context = {
            **global_context,
            USE_EXCLUDED_IDS: excluded_ids,
        }

        if exclude_key.endswith(ITEM_CATEGORY):
            how_key = USE_TYPE + ITEM_CATEGORY
            type_name = exclude_key[:-len(ITEM_CATEGORY)].title()
            context.update({
                USE_TYPE: type_name,
                USE_TYPE_ID: [type_to_id[type_name]],
            })

        for step_name, step_config in how_config[how_key].items():
            context["trace"] = f"{exclude_key}.{step_name}"
            try:
                operator_step(context, all_sources, modified_sources, step_name, step_config, how_config, extras_ids)
            except Exception as e:
                print(f"\nError in step {context['trace']}: {e}\n")
                traceback.print_exc()
            context["trace"] = exclude_key

    return modified_sources


def filter_game_info(config_how_path: Path, config_exclude_path: Path, config_extras_path: Path, in_dir: Path, out_dir: Path, active_event: str):
    shutil.copytree(in_dir, out_dir)

    out_areas_path = out_dir / "areas.json"
    out_xdt_path = out_dir / "xdt.json"

    if not config_how_path.is_file() or not config_exclude_path.is_file():
        return

    all_config = {}

    with open(config_how_path, "r") as f:
        all_config["how"] = yaml.safe_load(f)

    with open(config_exclude_path, "r") as f:
        all_config["exclude"] = yaml.safe_load(f)

    all_config["extras"] = {}
    if config_extras_path.is_file():
        with open(config_extras_path, "r") as f:
            all_config["extras"] = yaml.safe_load(f)

    with open(out_areas_path, "r") as f:
        in_areas = json.load(f)

    with open(out_xdt_path, "r") as f:
        in_xdt = json.load(f)

    global_context = {
        "out_dir": str(out_dir),
        "trace": "",
        "active_event": active_event,
    }
    all_sources = {
        "areas": in_areas,
        "xdt": in_xdt,
    }
    modified_sources = run_all_steps(global_context, all_sources, all_config)

    with open(out_areas_path, "w") as f:
        json.dump(modified_sources["areas"], f, indent=4)

    with open(out_xdt_path, "w") as f:
        json.dump(modified_sources["xdt"], f, indent=4)


def main(config_root: Path, in_root: Path, out_root: Path):
    in_dirs = [p for p in in_root.iterdir() if p.is_dir()]
    out_root.mkdir(parents=True, exist_ok=True)

    config_exclude_how_path = config_root / "how-exclude.yml"
    config_build_path = config_root / "build-config.yml"

    with open(config_build_path, "r") as f:
        config_build = yaml.safe_load(f)["config"]

    for in_dir in tqdm(in_dirs):
        out_dir = out_root / in_dir.name
        active_event = config_build[in_dir.name].get("active_event", "None")
        config_exclude_path = config_root / f"exclude-{in_dir.name}.yml"
        config_extras_path = config_root / f"extras-{in_dir.name}.yml"
        filter_game_info(config_exclude_how_path, config_exclude_path, config_extras_path, in_dir, out_dir, active_event)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python filter_game_info.py <config_root> <in_root> <out_root>")
        sys.exit(1)

    main(*map(Path, sys.argv[1:]))
