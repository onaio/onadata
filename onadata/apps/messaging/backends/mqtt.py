# -*- coding: utf-8 -*-
"""
Messaging notification backend for MQTT
"""
from __future__ import unicode_literals

import json
import ssl

import paho.mqtt.publish as publish

from onadata.apps.messaging.backends.base import BaseBackend
from onadata.apps.messaging.constants import PROJECT, USER, XFORM


def get_target_metadata(target_obj):
    """
    Gets the metadata of a Target object
    """
    target_obj_type = target_obj._meta.model_name
    metadata = dict(id=target_obj.pk)
    if target_obj_type == PROJECT:
        metadata['name'] = target_obj.name
    elif target_obj_type == XFORM:
        metadata['name'] = target_obj.title
        metadata['form_id'] = target_obj.id_string
    elif target_obj_type == USER:
        metadata['name'] = target_obj.get_full_name()
    return metadata


def get_payload(instance):
    """
    Constructs the message payload
    """

    payload = {
        'id': instance.id,
        'time': instance.timestamp.isoformat(),
        'payload': {
            'author': {
                'username': instance.actor.username,
                'real_name': instance.actor.get_full_name()
            },
            'context': {
                'type': instance.target._meta.model_name,
                'metadata': get_target_metadata(instance.target)
            },
            'message': instance.description
        }
    }

    return json.dumps(payload)


class MQTTBackend(BaseBackend):
    """
    Notification backend for MQTT
    """

    def __init__(self, options=None):
        super(MQTTBackend, self).__init__()
        if not options:
            raise Exception("MQTT Backend expects configuration options.")

        self.host = options.get('HOST')
        if not self.host:
            raise Exception("An MQTT host is required.")
        self.port = options.get('PORT')
        self.cert_info = None
        secure = options.get('SECURE', False)
        if secure:
            if options.get('CA_CERT_FILE') is None:
                raise Exception("The Certificate Authority certificate file "
                                "is required.")
            self.cert_info = dict(
                ca_certs=options.get('CA_CERT_FILE'),
                certfile=options.get('CERT_FILE'),
                keyfile=options.get('KEY_FILE'),
                tls_version=ssl.PROTOCOL_TLSv1_2,
                cert_reqs=ssl.CERT_NONE)

        self.qos = options.get('QOS', 0)
        self.retain = options.get('RETAIN', False)
        self.topic_base = options.get('TOPIC_BASE', 'onadata')

    def get_topic(self, instance):
        """
        Constructs the message topic

        For sending messages it should look like:
            /onadata/forms/[pk or uuid]/messages/publish
            /onadata/projects/[pk or uuid]/messages/publish
            /onadata/users/[pk or uuid]/messages/publish
        """
        kwargs = {
            'target_id': instance.target_object_id,
            'target_name': instance.target._meta.model_name,
            'topic_base': self.topic_base
        }
        return (
            '/{topic_base}/{target_name}/{target_id}/messages/publish'.format(
                **kwargs))

    def send(self, instance):
        """
        Sends the message to appropriate MQTT topic(s)
        """
        topic = self.get_topic(instance)
        payload = get_payload(instance)
        # send it

        return publish.single(topic, payload=payload, hostname=self.host,
                              port=self.port, tls=self.cert_info, qos=self.qos,
                              retain=self.retain)
