import os
from typing import List

from django.core.management.base import BaseCommand
from django.utils.translation import gettext as _

from onadata.apps.logger.xform_instance_parser import clean_and_parse_xml


def _traverse_child_nodes_and_delete_column(xml_obj, column: str) -> None:
    childNodes = xml_obj.childNodes
    for elem in childNodes:
        if elem.nodeName in column:
            xml_obj.removeChild(elem)
        if hasattr(elem, "childNodes"):
            _traverse_child_nodes_and_delete_column(elem, column)


def remove_columns_from_xml(xml: str, columns: List[str]) -> str:
    xml_obj = clean_and_parse_xml(xml).documentElement
    for column in columns:
        _traverse_child_nodes_and_delete_column(xml_obj, column)
    return xml_obj.toxml()


class Command(BaseCommand):
    help = _("Delete specific columns from submission " "XMLs pulled by ODK Briefcase.")

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            "-i",
            dest="in_dir",
            help="Path to instances directory to pull submission XMLs from.",
        )
        parser.add_argument(
            "--output",
            "-o",
            default="replaced-submissions",
            dest="out_dir",
            help="Path to directory to output modified submission XMLs",
        )
        parser.add_argument(
            "--columns",
            "-c",
            dest="columns",
            help="Comma separated list of columns to remove from the XMLs",
        )
        parser.add_argument(
            "--overwrite",
            "-f",
            default=False,
            dest="overwrite",
            action="store_true",
            help="Whether to overwrite the original submission",
        )

    def handle(self, *args, **options):
        columns: List[str] = options.get("columns").split(",")
        in_dir: str = options.get("in_dir")
        out_dir: str = options.get("out_dir")
        overwrite: bool = options.get("overwrite")

        submission_folders = [
            xml_file for xml_file in os.listdir(in_dir) if xml_file.startswith("uuid")
        ]
        total_files = len(submission_folders)
        modified_files = 0

        if not os.path.exists(out_dir):
            os.makedirs(out_dir)

        for count, submission_folder in enumerate(submission_folders, start=1):
            self.stdout.write(
                f"Modifying {submission_folder}. " f"Progress {count}/{total_files}"
            )
            data = None

            with open(f"{in_dir}/{submission_folder}/submission.xml", "r") as in_file:
                data = in_file.read().replace("\n", "")
                data = remove_columns_from_xml(data, columns)
                in_file.close()

            remove_columns_from_xml(data, columns)

            if not overwrite:
                os.makedirs(f"{out_dir}/{submission_folder}")

                with open(
                    f"{out_dir}/{submission_folder}/submission.xml", "w"
                ) as out_file:
                    out_file.write(data)
                    out_file.close()
            else:
                with open(
                    f"{in_dir}/{submission_folder}/submission.xml", "r+"
                ) as out_file:
                    out_file.truncate(0)
                    out_file.write(data)
                    out_file.close()

            modified_files += 1

        self.stdout.write(f"Operation completed. Modified {modified_files} files.")
