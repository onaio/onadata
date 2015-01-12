from onadata.libs.permissions import ROLES


class ShareTeamProject(object):
    def __init__(self, team, project, role, remove=False):
        self.team = team
        self.project = project
        self.role = role
        self.remove = remove

    def save(self, **kwargs):
        if self.remove:
            return self.remove_team()

        role = ROLES.get(self.role)

        if role and self.team and self.project:
            role.add(self.team, self.project)

    def remove_team(self):
        role = ROLES.get(self.role)

        if role and self.team and self.project:
            role._remove_obj_permissions(self.team, self.project)
