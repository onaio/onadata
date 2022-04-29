# -*- coding: utf-8 -*-
"""
QR code utility function.
"""
from base64 import b64encode
from elaphe import barcode
from io import BytesIO


# pylint: disable=too-many-arguments
def generate_qrcode(
    message,
    stream=None,
    eclevel="M",
    margin=10,
    data_mode="8bits",
    image_format="PNG",
    scale=2.5,
):
    """Generate a QRCode, settings options and output."""

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
