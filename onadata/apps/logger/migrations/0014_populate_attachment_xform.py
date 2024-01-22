# Generated by Django 4.2.11 on 2024-04-22 06:42

from django.db import migrations


def populate_attachment_xform(apps, schema_editor):
    """Populate xform field for Attachments"""
    Attachment = apps.get_model("logger", "Attachment")
    queryset = Attachment.objects.filter(xform__isnull=True).values(
        "pk", "instance__xform", "instance__user"
    )
    count = queryset.count()
    print("Start populating attachment xform...")
    print(f"Found {count} records")

    for attachment in queryset.iterator(chunk_size=100):
        # We do not want to trigger Model.save or any signal
        # Queryset.update is a workaround to achieve this.
        # Model.save and the post/pre signals may contain
        # some side-effects which we are not interested in
        Attachment.objects.filter(pk=attachment["pk"]).update(
            xform=attachment["instance__xform"],
            user=attachment["instance__user"],
        )
        count -= 1
        print(f"{count} remaining")

    print("Done populating attachment xform!")


class Migration(migrations.Migration):

    dependencies = [
        ("logger", "0013_add_xform_to_logger_attachment"),
    ]

    operations = [migrations.RunPython(populate_attachment_xform)]