import csv
import shutil
import sys
import time
import zipfile
from collections import defaultdict
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

import gspread
import requests
import yaml
from tqdm import tqdm

T = TypeVar("T")
GOOGLE_FOLDER_ID = "1LhYdMCUjOmiTGFwnJ4o8WGM2C2ZSyZq3"
MAX_CELL_SIZE = 50000
MAX_COL_SIZE_PX = 1000


def exponential_backoff(func: Callable[..., T]) -> Callable[..., T]:
    @wraps(func)
    def wrapper(*args, **kwargs):
        for i in range(5):
            try:
                result = func(*args, **kwargs)
                return result
            except (gspread.exceptions.APIError, requests.exceptions.ConnectionError):
                # wait 64 seconds and double every attempt to avoid rate limiting
                time.sleep(2 ** (i + 6))
                continue
        raise RuntimeError(f"Failed to execute {func.__name__} after 5 attempts.")
    return wrapper


def to_sheet_name(csv_file_name: str) -> str:
    return csv_file_name.replace("_", " ").title()


def to_csv_file_name(sheet_name: str) -> str:
    return sheet_name.replace(" ", "_").lower()


def make_extracted_root_dir(artifacts_dir: Path) -> Path:
    extracted_root_dir = artifacts_dir.parent / f"{artifacts_dir.name}_extracted"
    extracted_root_dir.mkdir(parents=True, exist_ok=True)

    zip_files = list(artifacts_dir.glob("*.zip"))
    for zip_file in tqdm(zip_files, desc="Extracting"):
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            extracted_dir = extracted_root_dir / zip_file.stem
            extracted_dir.mkdir(parents=True, exist_ok=True)
            zip_ref.extractall(extracted_dir)

    return extracted_root_dir


def get_local_csv_map(extracted_root_dir: Path) -> dict[str, dict[str, str]]:
    csv_map = defaultdict(dict)

    for extract_dir in extracted_root_dir.iterdir():
        if not extract_dir.is_dir():
            continue

        info_dir = extract_dir / "info"
        if not info_dir.is_dir():
            continue

        for csv_file in info_dir.glob("*.csv"):
            build_name = extract_dir.stem.split("_")[0]
            csv_map[csv_file.stem][build_name] = extract_dir.stem

    return csv_map


@exponential_backoff
def get_google_sheets_csv_map(gc: gspread.Client) -> dict[str, dict[str, str]]:
    gcloud_csv_map = defaultdict(dict)

    spreadsheets: list[gspread.Spreadsheet] = gc.openall()
    for spreadsheet in spreadsheets:
        for worksheet in spreadsheet.worksheets():
            if "_" not in worksheet.title:
                continue

            build_name = worksheet.title.split("_")[0]
            csv_file_name = to_csv_file_name(spreadsheet.title)
            gcloud_csv_map[csv_file_name][build_name] = worksheet.title

    return gcloud_csv_map


def get_diff_map(
    local_csv_map: dict[str, dict[str, str]],
    google_sheets_csv_map: dict[str, dict[str, str]],
) -> dict[str, dict[str, list[Optional[str]]]]:
    diff_map = {}

    for csv_file_name, build_revision_map in local_csv_map.items():
        if csv_file_name not in google_sheets_csv_map:
            diff_map[csv_file_name] = {
                build: [None, revision_name]
                for build, revision_name in build_revision_map.items()
            }
            continue

        diff_build_revision_map = {}
        google_build_revision_map = google_sheets_csv_map[csv_file_name]

        for build, revision_name in build_revision_map.items():
            google_revision_name = google_build_revision_map.get(build)

            if google_revision_name is None:
                diff_build_revision_map[build] = [None, revision_name]
            elif google_revision_name != revision_name:
                diff_build_revision_map[build] = [google_revision_name, revision_name]

        if diff_build_revision_map:
            diff_map[csv_file_name] = diff_build_revision_map

    return diff_map


def print_diff_map(diff_map: dict[str, dict[str, list[Optional[str]]]]) -> None:
    print("Updating:")
    print(yaml.dump(
        {
            csv_name: [
                f"{revs[0]} -> {revs[1]}"
                for revs in build_revision_map.values()
            ]
            for csv_name, build_revision_map in diff_map.items()
        },
        indent=2,
        default_flow_style=False,
    ))


def read_data_from_csv(csv_path: Path) -> tuple[list[list[str]], int, int]:
    with open(csv_path, "r") as f:
        csv_reader = csv.reader(f)
        csv_content = list(csv_reader)

    row_count = len(csv_content)
    col_count = len(csv_content[0]) if csv_content else 1

    for i in range(row_count):
        for j in range(col_count):
            cell_value = csv_content[i][j]
            if len(cell_value) > MAX_CELL_SIZE:
                csv_content[i][j] = f"{cell_value[:(MAX_CELL_SIZE - 13)]}...{cell_value[-10:]}"

    return csv_content, row_count, col_count


def fetch_column_metadata(spreadsheet: gspread.Spreadsheet) -> dict[str, Any]:
    # Construct fields parameter to limit response size
    params = {
        "fields": (
            "sheets(properties(sheetId,title),"
            "data(columnMetadata(pixelSize)))"
        )
    }
    response = spreadsheet.client.request(
        "GET",
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet.id}",
        params=params,
    )
    return response.json()["sheets"]


@exponential_backoff
def get_or_create_spreadsheet(gc: gspread.Client, csv_file_name: str) -> gspread.Spreadsheet:
    spreadsheet_name = to_sheet_name(csv_file_name)
    try:
        spreadsheet = gc.open(spreadsheet_name, folder_id=GOOGLE_FOLDER_ID)
    except gspread.exceptions.SpreadsheetNotFound:
        spreadsheet = gc.create(spreadsheet_name, folder_id=GOOGLE_FOLDER_ID)

    return spreadsheet


@exponential_backoff
def create_worksheet(spreadsheet: gspread.Spreadsheet, revision_name: str, row_count: int, col_count: int) -> gspread.Worksheet:
    worksheet = spreadsheet.add_worksheet(title=revision_name, rows=row_count, cols=col_count)
    return worksheet


@exponential_backoff
def update_worksheet(worksheet: gspread.Worksheet, csv_content: list[list[str]]) -> None:
    worksheet.update(csv_content, value_input_option="RAW")


@exponential_backoff
def resize_worksheet(worksheet: gspread.Worksheet, col_count: int) -> None:
    worksheet.columns_auto_resize(start_column_index=0, end_column_index=col_count)


@exponential_backoff
def set_basic_filter_for_worksheet(worksheet: gspread.Worksheet) -> None:
    worksheet.set_basic_filter()


@exponential_backoff
def delete_worksheet(spreadsheet: gspread.Spreadsheet, worksheet_title: str) -> None:
    try:
        worksheet = spreadsheet.worksheet(worksheet_title)
        spreadsheet.del_worksheet(worksheet)
    except gspread.exceptions.WorksheetNotFound:
        return


@exponential_backoff
def resize_long_columns(spreadsheet: gspread.Spreadsheet) -> None:
    table_metadata = fetch_column_metadata(spreadsheet)

    requests = []
    for worksheet_metadata in table_metadata:
        col_data = worksheet_metadata.get("data", [{}])[0].get("columnMetadata", [])

        for column_id, column_metadata in enumerate(col_data):
            column_width = column_metadata.get("pixelSize", 0)

            if column_width > MAX_COL_SIZE_PX:
                requests.append({
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": worksheet_metadata["properties"]["sheetId"],
                            "dimension": "COLUMNS",
                            "startIndex": column_id,
                            "endIndex": column_id + 1,
                        },
                        "properties": {
                            "pixelSize": MAX_COL_SIZE_PX
                        },
                        "fields": "pixelSize"
                    }
                })

    if requests:
        spreadsheet.batch_update({"requests": requests})


@exponential_backoff
def sort_spreadsheet_worksheets(spreadsheet: gspread.Spreadsheet) -> None:
    worksheet_titles = [(worksheet.title, worksheet) for worksheet in spreadsheet.worksheets()]
    worksheet_titles.sort(key=lambda x: x[0], reverse=True)
    spreadsheet.reorder_worksheets([w[1] for w in worksheet_titles])


def import_csv_to_sheet(spreadsheet: gspread.Spreadsheet, revision_name: str, csv_path: Path) -> None:
    csv_content, row_count, col_count = read_data_from_csv(csv_path)

    worksheet = create_worksheet(spreadsheet, revision_name, row_count, col_count)
    update_worksheet(worksheet, csv_content)
    set_basic_filter_for_worksheet(worksheet)
    resize_worksheet(worksheet, col_count)


def update_or_create_google_sheets(
    gc: gspread.Client,
    extracted_root_dir: Path,
    diff_map: dict[str, dict[str, list[Optional[str], str]]],
) -> None:
    total_sheet_updates = sum(len(build_revision_map) for build_revision_map in diff_map.values())

    if total_sheet_updates == 0:
        return

    with tqdm(total=total_sheet_updates, desc="Updating Worksheets") as counter:
        for csv_file_name, build_revision_map in diff_map.items():
            spreadsheet = get_or_create_spreadsheet(gc, csv_file_name)

            for old_revision_name, new_revision_name in build_revision_map.values():
                if old_revision_name is not None:
                    delete_worksheet(spreadsheet, old_revision_name)

                csv_path = extracted_root_dir / new_revision_name / "info" / f"{csv_file_name}.csv"
                import_csv_to_sheet(spreadsheet, new_revision_name, csv_path)
                counter.update(1)

            # Workaround for initial creation of the spreadsheet
            delete_worksheet(spreadsheet, spreadsheet.title)

            resize_long_columns(spreadsheet)
            sort_spreadsheet_worksheets(spreadsheet)


def main(google_service_account_json: Path, artifacts_dir: Path):
    gc = gspread.service_account(filename=google_service_account_json)

    extracted_root_dir = make_extracted_root_dir(artifacts_dir)

    csv_map = get_local_csv_map(extracted_root_dir)
    gcloud_csv_map = get_google_sheets_csv_map(gc)
    diff_map = get_diff_map(csv_map, gcloud_csv_map)

    print_diff_map(diff_map)

    try:
        update_or_create_google_sheets(gc, extracted_root_dir, diff_map)
    except Exception as e:
        print(f"Error updating Google Sheets: {e}")
        raise e
    finally:
        shutil.rmtree(extracted_root_dir)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python upload_csv_files.py <google_service_account_json> <artifacts_dir>")
        sys.exit(1)

    main(Path(sys.argv[1]), Path(sys.argv[2]))
