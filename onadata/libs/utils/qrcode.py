# -*- coding: utf-8 -*-
"""
QR code utility function.
"""
import json
import zlib
import segno

from io import BytesIO
from base64 import b64encode
from elaphe import barcode

from onadata.apps.api.models.odk_token import ODKToken


# pylint: disable=too-many-arguments
def generate_qrcode(message):
    """Generate a QRCode, settings options and output."""
    stream = None
    eclevel = "M"
    margin = 10
    data_mode = "8bits"
    image_format = "PNG"
    scale = 2.5

    if stream is None:
        stream = BytesIO()

    if isinstance(message, str):
        message = message.encode()

    img = barcode(
        "qrcode",
        message,
        options=dict(version=9, eclevel=eclevel),
        margin=margin,
        data_mode=data_mode,
        scale=scale,
    )

    img.save(stream, image_format)

    datauri = f"data:image/png;base64,{b64encode(stream.getvalue()).decode('utf-8')}"
    stream.close()

    return datauri


def generate_odk_qrcode(request, view=None, id=None):
    """Generate ODK settings QRCode image uri"""
    server_url = f"{request.scheme}://{request.get_host()}"
    token = None
    if request.user:
        queryset = ODKToken.objects.filter(
            user=request.user, status=ODKToken.ACTIVE)
        if queryset.count() > 0:
            q = queryset.first()
            token = q.raw_key.decode('utf-8')

    if view and id:
        server_url = f"{request.scheme}://{request.get_host()}/{view}/{id}",

    odk_settings_obj = {
            "general": {
                "server_url": server_url,
                "username": f"{request.user.username}",
                "password": token,
                "constraint_behavior": "on_finalize",
                "autosend": "wifi_and_cellular"
            },
            "admin": {
                "send_finalized": True,
                "get_blank": True
            }
    }
    stream = BytesIO()
    qr_data = b64encode(
        zlib.compress(json.dumps(odk_settings_obj).encode("utf-8")))
    code = segno.make(qr_data, micro=False)
    code.save(stream, scale=5, kind='png')
    base46_str = b64encode(stream.getvalue()).decode('utf-8')
    datauri = f"data:image/png;base64,{base46_str}"
    stream.close()
    return datauri
