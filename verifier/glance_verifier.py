# Copyright (c) 2012 - Rackspace Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
import json

import os
import sys
import uuid
from verifier.base_verifier import Verifier


POSSIBLE_TOPDIR = os.path.normpath(os.path.join(os.path.abspath(sys.argv[0]),
os.pardir, os.pardir))
if os.path.exists(os.path.join(POSSIBLE_TOPDIR, 'stacktach')):
    sys.path.insert(0, POSSIBLE_TOPDIR)

from stacktach import models
from verifier import FieldMismatch
from verifier import VerificationException
from verifier import base_verifier
from verifier import NullFieldException
from verifier import NotFound
from stacktach import datetime_to_decimal as dt
import datetime
from stacktach import stacklog, message_service
LOG = stacklog.get_logger('verifier')


def _verify_field_mismatch(exists, usage):
    if not base_verifier._verify_date_field(
            usage.created_at, exists.created_at, same_second=True):
        raise FieldMismatch('created_at', exists.created_at,
                            usage.created_at)

    if usage.owner != exists.owner:
        raise FieldMismatch('owner', exists.owner,
                            usage.owner)

    if usage.size != exists.size:
        raise FieldMismatch('size', exists.size,
                            usage.size)


def _verify_validity(exist):
    fields = {exist.size: 'image_size', exist.created_at: 'created_at',
              exist.uuid: 'uuid', exist.owner: 'owner'}
    for (field_value, field_name) in fields.items():
        if field_value is None:
            raise NullFieldException(field_name, exist.id)
    base_verifier._is_like_uuid('uuid', exist.uuid, exist.id)
    base_verifier._is_like_date('created_at', exist.created_at, exist.id)
    base_verifier._is_long('size', exist.size, exist.id)
    base_verifier._is_hex_owner_id('owner', exist.owner, exist.id)


def _verify_for_usage(exist, usage=None):
    usage_type = "ImageUsage"
    if not usage and exist.usage:
        usage = exist.usage
    elif not usage:
        usages = models.ImageUsage.objects.filter(uuid=exist.uuid)
        usage_count = usages.count()
        if usage_count == 0:
            query = {'uuid': exist.uuid}
            raise NotFound(usage_type, query)
        usage = usages[0]
    _verify_field_mismatch(exist, usage)


def _verify_for_delete(exist, delete=None):
    delete_type = "ImageDelete"
    if not delete and exist.delete:
        # We know we have a delete and we have it's id
        delete = exist.delete
    elif not delete:
        if exist.deleted_at:
            # We received this exists before the delete, go find it
            deletes = models.ImageDeletes.find(uuid=exist.uuid)
            if deletes.count() == 1:
                delete = deletes[0]
            else:
                query = {
                    'instance': exist.instance,
                    'launched_at': exist.launched_at
                }
                raise NotFound(delete_type, query)
        else:
            # We don't know if this is supposed to have a delete or not.
            # Thus, we need to check if we have a delete for this instance.
            # We need to be careful though, since we could be verifying an
            # exist event that we got before the delete. So, we restrict the
            # search to only deletes before this exist's audit period ended.
            # If we find any, we fail validation
            deleted_at_max = dt.dt_from_decimal(exist.audit_period_ending)
            deletes = models.ImageDeletes.find(
                exist.uuid, deleted_at_max)
            if deletes.count() > 0:
                reason = 'Found %ss for non-delete exist' % delete_type
                raise VerificationException(reason)

    if delete:
        if not base_verifier._verify_date_field(
                delete.created_at, exist.created_at, same_second=True):
            raise FieldMismatch('created_at', exist.created_at,
                                delete.created_at)

        if not base_verifier._verify_date_field(
                delete.deleted_at, exist.deleted_at, same_second=True):
            raise FieldMismatch('deleted_at', exist.deleted_at,
                                delete.deleted_at)


def _verify(exist):
    verified = False
    try:
        _verify_for_usage(exist)
        _verify_for_delete(exist)
        _verify_validity(exist)

        verified = True
        exist.mark_verified()
    except Exception, e:
        exist.mark_failed(reason=e.__class__.__name__)
        LOG.exception("glance: %s" % e)

    return verified, exist


class GlanceVerifier(Verifier):
    def __init__(self, config, pool=None):
        super(GlanceVerifier, self).__init__(config, pool=pool)

    def verify_for_range(self, ending_max, callback=None):
        exists = models.ImageExists.find(
            ending_max=ending_max, status=models.ImageExists.PENDING)
        count = exists.count()
        added = 0
        update_interval = datetime.timedelta(seconds=30)
        next_update = datetime.datetime.utcnow() + update_interval
        LOG.info("glance: Adding %s exists to queue." % count)
        while added < count:
            for exist in exists[0:1000]:
                exist.status = models.ImageExists.VERIFYING
                exist.save()
                result = self.pool.apply_async(_verify, args=(exist,),
                                               callback=callback)
                self.results.append(result)
                added += 1
                if datetime.datetime.utcnow() > next_update:
                    values = ((added,) + self.clean_results())
                    msg = "glance: N: %s, P: %s, S: %s, E: %s" % values
                    LOG.info(msg)
                    next_update = datetime.datetime.utcnow() + update_interval
        return count

    def send_verified_notification(self, exist, connection, exchange,
                                   routing_keys=None):
        body = exist.raw.json
        json_body = json.loads(body)
        json_body[1]['event_type'] = 'image.exists.verified.old'
        json_body[1]['original_message_id'] = json_body[1]['message_id']
        json_body[1]['message_id'] = str(uuid.uuid4())
        if routing_keys is None:
            message_service.send_notification(json_body[1], json_body[0],
                                              connection, exchange)
        else:
            for key in routing_keys:
                message_service.send_notification(json_body[1], key,
                                                  connection, exchange)

    def exchange(self):
        return 'glance'
