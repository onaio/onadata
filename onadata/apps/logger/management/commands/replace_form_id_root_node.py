"""
Management command used to replace the root node of an Instance when
the root node is the XForm ID
Example usage:
    python manage.py replace_form_id_root_node -c -i 1,2,3
"""
import re
from hashlib import sha256

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.translation import gettext as _

from onadata.apps.logger.models import Instance
from onadata.apps.logger.models.instance import InstanceHistory


def replace_form_id_with_correct_root_node(
        inst_id: int, root: str = None, commit: bool = False) -> str:
    inst: Instance = Instance.objects.get(id=inst_id, deleted_at__isnull=True)
    initial_xml = inst.xml
    form_id = re.escape(inst.xform.id_string)
    if not root:
        root = inst.xform.survey.name

    opening_tag_regex = f"<{form_id}"
    closing_tag_regex = f"</{form_id}>"
    edited_xml = re.sub(opening_tag_regex, f'<{root}', initial_xml)
    edited_xml = re.sub(closing_tag_regex, f'</{root}>', edited_xml)

    if commit:
        last_edited = timezone.now()
        history = InstanceHistory.objects.create(
            xml=initial_xml,
            checksum=inst.checksum,
            xform_instance=inst,
        )
        inst.last_edited = last_edited
        inst.checksum = sha256(edited_xml.encode('utf-8')).hexdigest()
        inst.xml = edited_xml
        inst.save()
        return f"Modified Instance ID {inst.id} - History object {history.id}"
    else:
        return edited_xml


class Command(BaseCommand):
    help = _("Replaces form ID String with 'data' for an instances root node")

    def add_arguments(self, parser):
        parser.add_argument(
            '--instance-ids',
            '-i',
            dest='instance_ids',
            help='Comma-separated list of instance ids.'
        )
        parser.add_argument(
            '--commit-changes',
            '-c',
            action='store_true',
            dest='commit',
            default=False,
            help='Save XML changes'
        )
        parser.add_argument(
            '--root-node',
            '-r',
            dest='root',
            default=None,
            help='Default root node name to replace the form ID with'
        )

    def handle(self, *args, **options):
        instance_ids = options.get('instance_ids').split(',')
        commit = options.get('commit')
        root = options.get('root')

        if not instance_ids:
            raise CommandError('No instance id provided.')

        for inst_id in instance_ids:
            try:
                msg = replace_form_id_with_correct_root_node(
                    inst_id, root=root, commit=commit)
            except Instance.DoesNotExist:
                msg = f"Instance with ID {inst_id} does not exist"

            self.stdout.write(msg)
