import __builtin__
setattr(__builtin__, '_', lambda x: x)
import datetime
import os
import sys

from oslo.config import cfg
CONF = cfg.CONF
CONF.config_file = "/etc/nova/nova.conf"

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print "Proper Usage: python 012_usage_seed.py [period_length] [sql_connection]"
        sys.exit(1)
    CONF.sql_connection = sys.argv[2]

from nova.compute import task_states
from nova.context import RequestContext
from nova.db import api as novadb

POSSIBLE_TOPDIR = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
                                                os.pardir, os.pardir))
if os.path.exists(os.path.join(POSSIBLE_TOPDIR, 'stacktach')):
    sys.path.insert(0, POSSIBLE_TOPDIR)

from stacktach import datetime_to_decimal as dt
from stacktach import models


# start yanked from reports/nova_usage_audit.py
def get_previous_period(time, period_length):
    if period_length == 'day':
        last_period = time - datetime.timedelta(days=1)
        start = datetime.datetime(year=last_period.year,
                                  month=last_period.month,
                                  day=last_period.day)
        end = datetime.datetime(year=time.year,
                                month=time.month,
                                day=time.day)
        return start, end
    elif period_length == 'hour':
        last_period = time - datetime.timedelta(hours=1)
        start = datetime.datetime(year=last_period.year,
                                  month=last_period.month,
                                  day=last_period.day,
                                  hour=last_period.hour)
        end = datetime.datetime(year=time.year,
                                month=time.month,
                                day=time.day,
                                hour=time.hour)
        return start, end
# end yanked from reports/nova_usage_audit.py


def _usage_for_instance(instance, task=None):
    usage = {
        'instance': instance['uuid'],
        'tenant': instance['project_id'],
        'launched_at': dt.dt_to_decimal(instance.get('launched_at')),
        'instance_type_id': instance.get('instance_type_id'),
    }
    if task is not None:
        usage['task'] = task
    return usage


def _delete_for_instance(instance):
    delete = {
        'instance': instance['uuid'],
        'launched_at': dt.dt_to_decimal(instance.get('launched_at')),
        'deleted_at': dt.dt_to_decimal(instance.get('deleted_at')),
    }
    return delete


def get_active_instances(context, period_length):
    start, end = get_previous_period(datetime.datetime.utcnow(), period_length)
    return novadb.instance_get_active_by_window_joined(context, begin=start)


def get_action_for_instance(context, instance_uuid, action_name):
    actions = novadb.actions_get(context, instance_uuid)
    for action in actions:
        if action['action'] == action_name:
            return action


def get_deleted_instances():
    pass


rebuild_tasks = [task_states.REBUILDING,
                 task_states.REBUILD_BLOCK_DEVICE_MAPPING,
                 task_states.REBUILD_SPAWNING]

resize_tasks = [task_states.RESIZE_PREP,
                task_states.RESIZE_MIGRATING,
                task_states.RESIZE_MIGRATED,
                task_states.RESIZE_FINISH]

resize_revert_tasks = [task_states.RESIZE_REVERTING]

rescue_tasks = [task_states.RESCUING]

in_flight_tasks = (rebuild_tasks + resize_tasks +
                   resize_revert_tasks + rescue_tasks)


def seed(period_length):
    usages = []
    building_usages = []
    in_flight_usages = []
    deletes = []

    context = RequestContext(1, 1, is_admin=True)

    active_instances = get_active_instances(context, period_length)

    for instance in active_instances:
        vm_state = instance['vm_state']
        task_state = instance['task_state']

        if vm_state == 'building':
            building_usages.append(_usage_for_instance(instance))
            if instance['deleted'] != 0:
                # Just in case...
                deletes.append(_delete_for_instance(instance))
        else:
            if task_state in in_flight_tasks:
                in_flight_usages.append(_usage_for_instance(instance,
                                                            task=task_state))
                if instance['deleted'] != 0:
                    # Just in case...
                    deletes.append(_delete_for_instance(instance))
            else:
                usages.append(_usage_for_instance(instance))
                if instance['deleted'] != 0:
                    deletes.append(_delete_for_instance(instance))

    for usage in building_usages:
        action = get_action_for_instance(context, usage['instance'], 'create')
        usage['request_id'] = action['request_id']

    for usage in in_flight_usages:
        instance = usage['instance']
        if usage['task'] in rebuild_tasks:
            action = get_action_for_instance(context, instance, 'rebuild')
            usage['request_id'] = action['request_id']
        elif usage['task'] in resize_tasks:
            action = get_action_for_instance(context, instance, 'resize')
            usage['request_id'] = action['request_id']
        elif usage['task'] in resize_revert_tasks:
            action = get_action_for_instance(context, instance, 'resizeRevert')
            usage['request_id'] = action['request_id']
        elif usage['task'] in rescue_tasks:
            action = get_action_for_instance(context, instance, 'rescue')
            usage['request_id'] = action['request_id']
        del usage['task']

    active_InstanceUsages = map(models.InstanceUsage, usages)
    models.InstanceUsage.objects.bulk_create(active_InstanceUsages,
                                             batch_size=100)

    building_InstanceUsages = map(models.InstanceUsage, building_usages)
    models.InstanceUsage.objects.bulk_create(building_InstanceUsages,
                                             batch_size=100)

    in_flight_InstanceUsages = map(models.InstanceUsage, in_flight_usages)
    models.InstanceUsage.objects.bulk_create(in_flight_InstanceUsages,
                                             batch_size=100)

    all_InstanceDeletes = map(models.InstanceDeletes, deletes)
    models.InstanceDeletes.objects.bulk_create(all_InstanceDeletes,
                                               batch_size=100)

    return (len(usages), len(building_usages),
            len(in_flight_usages), len(deletes))

if __name__ == '__main__':
    msg = ("Seeded system with: \n"
           "%s Active Instances \n"
           "%s Building Instances \n"
           "%s In Flight Instances \n"
           "%s Deleted Instances \n")
    print msg % seed(sys.argv[1])
