# Messaging

Adds support to create and view messages.  Messages can be sent to:

1. **Users**: this is a message that is sent from one user to another user.
2. **XForms**:  this is a message that is sent from one user to all the users that have at least `view` permissions on an XForm.  This may be used to communicate with data enumerators, send notifications about an XForm, etc.
3. **Projects**:  this is a message that is sent from one user to all the users that have at least `view` permissions on a Project.  This may be used when you wan tto send a notification to all the members of a project.

Once created, messages are stored in the database and can be retrieved via the API described below.  Additionally, messages are also sent to their recipients via a number of 'backends'.  MQTT is the only backend that is supported at this time.

## API Endpoints

### POST /api/messaging

Create a new message, requires an `xform`, a `project`, or a `user` and the `message`.

```console
curl -X POST -H "Content-Type:application/json" -d '{"target_type": "xform", "target_id": "1337", "message": "Hello, World!"}' https://api.ona.io/api/v1/messaging
```

### GET /api/messaging

Returns an empty list, will return a list of messages given `target_type` and `target_id` query parameters. The `target_type` has `xform` or `project` or `user` as the value and `target_id` is the target identifier.

```console
curl -X GET https://api.ona.io/api/v1/messaging?target_type=xform&target_id=1337
```

#### Grouping activity counts

Passing one or more `group_by` parameters returns activity counts instead of
individual messages, grouped by the requested dimension(s). The supported
dimensions are `user`, `verb` and a time bucket (one of `hour`, `day`, `week`,
`month` or `year`); repeat the parameter to combine them. At most one time
bucket may be combined per request. The same `target_type`/`target_id` (and
optional `user`) filters apply. Any other `group_by` value, or more than one
time bucket, returns `400`. Each row always carries `count`,
`earliest_timestamp` and `latest_timestamp`, and rows are ordered by most recent
activity first and paginated. All timestamps are rendered in UTC.

- `group_by=verb` — counts per verb (aggregated across users).
- `group_by=user` — counts per user (aggregated across verbs).
- `group_by=user&group_by=verb` — counts per `(user, verb)`.
- `group_by=day` — counts per UTC day (aggregated across users and verbs).
- `group_by=day&group_by=user&group_by=verb` — counts per `(day, user, verb)`.

```console
curl -X GET "https://api.ona.io/api/v1/messaging?target_type=xform&target_id=1337&group_by=day&group_by=user&group_by=verb"
```

```json
[
    {
        "period_start": "2026-06-12T00:00:00Z",
        "user": "joe",
        "verb": "export_created",
        "count": 3,
        "earliest_timestamp": "2026-06-12T08:15:00Z",
        "latest_timestamp": "2026-06-12T12:00:00Z"
    },
    {
        "period_start": "2025-10-03T00:00:00Z",
        "user": "joe",
        "verb": "submission_created",
        "count": 14,
        "earliest_timestamp": "2025-10-03T06:22:00Z",
        "latest_timestamp": "2025-10-03T10:04:00Z"
    }
]
```

Only the requested dimensions appear in each row (e.g. `group_by=verb` omits
`user`, and `period_start` is present only when a time bucket is requested).
When `user` is a grouping dimension, it is `null` if the actor id no longer
resolves to a user. Time bucket boundaries are computed in UTC; a client can
render an event range by merging adjacent buckets using `earliest_timestamp`
and `latest_timestamp`.

### GET /api/messaging/[pk]

Returns a specific message with matching pk.

```console
curl -X GET https://api.ona.io/api/v1/messaging/1337
```

### DELETE /api/messaging/[pk]

Deletes a specific message with matching pk.

```console
curl -X DELETE https://api.ona.io/api/v1/messaging/1337
```

## Messaging Backends

### MQTT

One of the backends that is supported is [MQTT](http://mqtt.org/).

#### Settings

To activate the MQTT backend, you need to add this to your Django settings file.

```python

NOTIFICATION_BACKENDS = {
    'mqtt': {
        'BACKEND': 'onadata.apps.messaging.backends.mqtt.MQTTBackend',
        'OPTIONS': {
            'HOST': 'localhost',  # the MQTT host
            'PORT': 1883,  # the MQTT port
            'QOS': 0,  # the MQTT QoS level
            'RETAIN': False,  # MQTT retain messages option
            'TOPIC_BASE': 'onadata',  # the topic root
            'SECURE': False,  # whether to attempt a secure connection
            'CA_CERT_FILE': 'path to Certificate Authority certificate files',
            'CERT_FILE': 'file path to PEM encoded client certificate',
            'KEY_FILE': 'file path to PEM encoded client private key'
        }
    },
}

```

#### Topics

Topics for sending messages are constructed like so:

##### Users

```text
/[topic root]/user/[pk]/messages/publish
```

##### Forms

```text
/[topic root]/xform/[pk]/messages/publish
```

##### Projects

```text
/[topic root]/project/[pk]/messages/publish
```

These are the topics that an MQTT client would subscribe to in order to receive messages for that particular user/xform/project.


#### Payloads

MQTT payloads are as such:

##### Users

```json
{
    "payload": {
        "message": "I love oov",
        "context": {
            "type": "user",
            "metadata": {
                "id": 1337,
                "name": "John Doe",
            }
        },
        "author": {
            "username": "Bob",
            "real_name": "Bob Smith"
        }
    },
    "id": 3,
    "time": "2018-03-27T08:14:51.136675+00:00"
}
```

##### Forms

```json
{
    "payload": {
        "message": "I love oov",
        "context": {
            "type": "xform",
            "metadata": {
                "id": 1337,
                "name": "Form Name",
                "form_id": "Form_ID"
            }
        },
        "author": {
            "username": "Bob",
            "real_name": "Bob Smith"
        }
    },
    "id": 3,
    "time": "2018-03-27T08:14:51.136675+00:00"
}
```

##### Projects

```json
{
    "payload": {
        "message": "I love oov",
        "context": {
            "type": "project",
            "metadata": {
                "id": 1337,
                "name": "Project Name",
            }
        },
        "author": {
            "username": "Bob",
            "real_name": "Bob Smith"
        }
    },
    "id": 3,
    "time": "2018-03-27T08:14:51.136675+00:00"
}
```
