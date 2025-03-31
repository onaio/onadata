# -*- coding: utf-8 -*-
"""
QR code utility function.
"""
from io import BytesIO
from base64 import b64encode
from elaphe import barcode


# pylint: disable=too-many-arguments, too-many-positional-arguments
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
        options={"version": 9, "eclevel": eclevel},
        margin=margin,
        data_mode=data_mode,
        scale=scale,
    )

    img.save(stream, image_format)

    datauri = f"data:image/png;base64,{b64encode(stream.getvalue()).decode('utf-8')}"
    stream.close()

    return datauri
