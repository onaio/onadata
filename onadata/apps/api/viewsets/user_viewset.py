from django.contrib.auth.models import User
from django.db.models import Q
from rest_framework import permissions
from rest_framework.viewsets import ReadOnlyModelViewSet

from onadata.libs.serializers.user_serializer import UserSerializer


class UserViewSet(ReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    lookup_field = 'username'
    permission_classes = [permissions.DjangoModelPermissions, ]

    def get_queryset(self):
        user = self.request.user
        if user.is_anonymous():
            user = User.objects.get(pk=-1)
        return User.objects.filter(
            Q(pk__in=user.userprofile_set.values('user')) | Q(pk=user.pk))
