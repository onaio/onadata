"""Shared DataView fixtures for model tests."""

from onadata.apps.logger.models.data_view import DataView
from onadata.apps.logger.models.project import Project
from onadata.apps.logger.models.xform import XForm


def create_cross_project_dataview(
    project,
    xform,
    *,
    foreign_project_name="Foreign project",
    dataview_name="Cross-project DataView",
):
    """Create a DataView that publishes a form into another project."""
    foreign_project = Project.objects.create(
        name=foreign_project_name,
        organization=project.organization,
        created_by=project.created_by,
        metadata={},
    )
    foreign_xform = XForm.objects.create(
        xml=xform.xml,
        json=xform.json,
        user=xform.user,
        project=foreign_project,
    )
    return DataView.objects.create(
        name=dataview_name,
        xform=foreign_xform,
        project=project,
        matches_parent=True,
        columns=[],
    )
