from onadata.libs.permissions import ROLES


class ShareTeamProject(object):
    def __init__(self, team, project, role):
        self.team = team
        self.project = project
        self.role = role

    def save(self, **kwargs):
        role = ROLES.get(self.role)

        if role and self.team and self.project:
            role.add(self.team, self.project)
