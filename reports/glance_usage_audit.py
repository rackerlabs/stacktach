import argparse
import datetime
import json
import os
import sys

sys.path.append(os.environ.get('STACKTACH_INSTALL_DIR', '/stacktach'))
from reports import usage_audit
from stacktach import models
from stacktach import datetime_to_decimal as dt


OLD_LAUNCHES_QUERY = """
select * from stacktach_imageusage where
    created_at is not null and
    created_at < %s and
    uuid not in
        (select distinct(uuid)
            from stacktach_imagedeletes where
                deleted_at < %s);"""


def audit_usages_to_exists(exists, usages):
    # checks if all exists correspond to the given usages
    fails = []
    for (uuid, launches) in usages.items():
        if uuid not in exists:
            msg = "No exists for usage (%s)" % uuid
            fails.append(['Usage', '-', msg])
    return fails

def _get_new_launches(beginning, ending):
    filters = {
        'created_at__gte': beginning,
        'created_at__lte': ending,
    }
    return models.ImageUsage.objects.filter(**filters)

def _get_exists(beginning, ending):
    filters = {
        'audit_period_beginning': beginning,
        'audit_period_ending__gte': beginning,
        'audit_period_ending__lte': ending,
    }
    return models.ImageExists.objects.filter(**filters)

def valid_datetime(d):
    try:
        t = datetime.datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
        return t
    except Exception, e:
        raise argparse.ArgumentTypeError(
            "'%s' is not in YYYY-MM-DD HH:MM:SS format." % d)


def audit_for_period(beginning, ending):
    beginning_decimal = dt.dt_to_decimal(beginning)
    ending_decimal = dt.dt_to_decimal(ending)

    (verify_summary,
     verify_detail) = usage_audit._verifier_audit_for_day(beginning_decimal,
                                                          ending_decimal,
                                                          models.ImageExists)
    detail, new_count, old_count = _launch_audit_for_period(beginning_decimal,
                                                            ending_decimal)

    summary = {
        'verifier': verify_summary,
        'launch_summary': {
            'new_launches': new_count,
            'old_launches': old_count,
            'failures': len(detail)
        },
    }

    details = {
        'exist_fails': verify_detail,
        'launch_fails': detail,
    }

    return summary, details


def _launch_audit_for_period(beginning, ending):
    launches_dict = {}
    new_launches = _get_new_launches(beginning, ending)
    for launch in new_launches:
        uuid = launch.uuid
        l = {'id': launch.id, 'created_at': launch.created_at}
        if uuid in launches_dict:
            launches_dict[uuid].append(l)
        else:
            launches_dict[uuid] = [l, ]

    # NOTE (apmelton)
    # Django's safe substitution doesn't allow dict substitution...
    # Thus, we send it 'beginning' three    times...
    old_launches = models.ImageUsage.objects\
                         .raw(OLD_LAUNCHES_QUERY,
                              [beginning, beginning])

    old_launches_dict = {}
    for launch in old_launches:
        uuid = launch.uuid
        l = {'id': launch.id, 'created_at': launch.created_at}
        if uuid not in old_launches_dict or \
                (old_launches_dict[uuid]['created_at'] <
                 launch.created_at):
            old_launches_dict[uuid] = l

    for uuid, launch in old_launches_dict.items():
        if uuid in launches_dict:
            launches_dict[uuid].append(launch)
        else:
            launches_dict[uuid] = [launch, ]

    exists_dict = {}
    exists = _get_exists(beginning, ending)
    for exist in exists:
        uuid = exist.uuid
        e = {'id': exist.id,
             'created_at': exist.created_at,
             'deleted_at': exist.deleted_at}
        if uuid in exists_dict:
            exists_dict[uuid].append(e)
        else:
            exists_dict[uuid] = [e, ]

    launch_to_exists_fails = audit_usages_to_exists(launches_dict,
                                                       exists_dict)
    return launch_to_exists_fails, new_launches.count(), len(old_launches_dict)


def store_results(start, end, summary, details):
    values = {
        'json': make_json_report(summary, details),
        'created': dt.dt_to_decimal(datetime.datetime.utcnow()),
        'period_start': start,
        'period_end': end,
        'version': 4,
        'name': 'glance usage audit'
    }

    report = models.JsonReport(**values)
    report.save()


def make_json_report(summary, details):
    report = [{'summary': summary},
              ['Object', 'ID', 'Error Description']]
    report.extend(details['exist_fails'])
    report.extend(details['launch_fails'])
    return json.dumps(report)



if __name__ == '__main__':
    parser = argparse.ArgumentParser('StackTach Nova Usage Audit Report')
    parser.add_argument('--period_length',
                        choices=['hour', 'day'], default='day')
    parser.add_argument('--utcdatetime',
                        help="Override the end time used to generate report.",
                        type=valid_datetime, default=None)
    parser.add_argument('--store',
                        help="If set to true, report will be stored. "
                             "Otherwise, it will just be printed",
                        type=bool, default=False)
    args = parser.parse_args()

    if args.utcdatetime is not None:
        time = args.utcdatetime
    else:
        time = datetime.datetime.utcnow()

    start, end = usage_audit.get_previous_period(time, args.period_length)

    summary, details = audit_for_period(start, end)

    if not args.store:
        print make_json_report(summary, details)
    else:
        store_results(start, end, summary, details)
