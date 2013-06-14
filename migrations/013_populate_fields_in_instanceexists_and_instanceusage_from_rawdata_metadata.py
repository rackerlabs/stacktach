import os
import sys

try:
    import ujson as json
except ImportError:
    try:
        import simplejson as json
    except ImportError:
        import json

POSSIBLE_TOPDIR = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                                os.pardir, os.pardir))
if os.path.exists(os.path.join(POSSIBLE_TOPDIR, 'stacktach')):
    sys.path.insert(0, POSSIBLE_TOPDIR)

if __name__ != '__main__':
    sys.exit(1)

from stacktach import models
from stacktach.notification import MonitorNotification
from stacktach.notification import ComputeUpdateNotification

NOTIFICATIONS = {
    'monitor.info': MonitorNotification,
    'monitor.error': MonitorNotification,
    '': ComputeUpdateNotification}


def add_usage_fields():
    messages = models.RawData.objects.all().values('json', 'id')
    for message in messages:
        json_dict = json.loads(message['json'])
        routing_key = json_dict[0]
        body = json_dict[1]
        print body['_context_project_id']

        notification = NOTIFICATIONS[routing_key](body)
        print "Populating data in RawDataImageData"
        models.RawDataImageMeta.objects.create(
            raw_id=message['id'],
            os_architecture=notification.os_architecture,
            os_distro=notification.os_distro,
            os_version=notification.os_version,
            rax_options=notification.rax_options)
        print "Created record in RawDataImageMeta"

        print "Populating data in InstanceExists"
        count = models.InstanceExists.objects.filter(
            instance=notification.instance).update(
                os_architecture=notification.os_architecture,
                os_distro=notification.os_distro,
                os_version=notification.os_version,
                rax_options=notification.rax_options)
        print "Updated %s records in InstanceExists" % count

        print "Populating data in InstanceUsage"
        count = models.InstanceUsage.objects.filter(
            instance=notification.instance).update(
                os_architecture=notification.os_architecture,
                os_distro=notification.os_distro,
                os_version=notification.os_version,
                rax_options=notification.rax_options)
        print "Updated %s records in InstanceUsage" % count

add_usage_fields()
