"""Write OutputRow objects to a CSV that matches the required schema exactly.

QUOTE_ALL mirrors the dataset's own quoting and keeps justifications that contain
commas, semicolons, or non-ASCII text inside a single field.
"""

from __future__ import annotations

import csv

import config


def write_output_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(config.OUTPUT_COLUMNS),
                                quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_dict() if hasattr(row, "to_csv_dict") else row)
    return path


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))
