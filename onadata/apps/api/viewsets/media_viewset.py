from django.conf import settings
from django.http import Http404
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

from rest_framework import viewsets
from onadata.apps.logger.models import Attachment
from onadata.libs.utils.image_tools import image_url


class MediaViewSet(viewsets.ViewSet):
    """A view to redirect to actual attachments url"""

    def retrieve(self, request, pk=None):
        """
        Redirect to final atrtachment url

        param pk: the attachment id
        query param filename: the filename of the associated attachment is
            required and has to match
        query param suffix: (optional) - specify small | medium | large to
            retuurn resized images.

        return HttpResponseRedirect: redirects to final image url
        """
        try:
            int(pk)
        except ValueError:
            raise Http404()
        else:
            filename = request.QUERY_PARAMS.get('filename')
            attachments = Attachment.objects.all()
            obj = get_object_or_404(attachments, pk=pk)

            if obj.media_file.name != filename:
                raise Http404()

            url = None

            if obj.mimetype.startswith('image'):
                suffix = request.QUERY_PARAMS.get('suffix')

                if suffix and suffix not in settings.THUMB_CONF.keys():
                    raise Http404()

                if suffix and suffix in settings.THUMB_CONF.keys():
                    url = image_url(obj, suffix)

            if not url:
                url = obj.media_file.url

            return HttpResponseRedirect(url)

        raise Http404()
