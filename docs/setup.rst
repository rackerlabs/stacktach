
Installing StackTach
####################

The "Hurry Up" Install Guide
****************************
#. Create a database for StackTach to use. By default, StackTach assumes MySql, but you can modify the settings.py file to others.
#. Install django and the other required libraries listed in ``./etc/pip-requires.txt`` (please let us know if any are missing)
#. Clone this repo
#. Copy and configure the config files in ``./etc`` (see below for details)
#. Create the necessary database tables (python manage.py syncdb) You don't need an administrator account since there are no user profiles used.
#. Configure OpenStack to publish Notifications back into RabbitMQ (see below)
#. Restart the OpenStack services.
#. Run the Worker to start consuming messages. (see below)
#. Run the web server (``python manage.py runserver --insecure``)
#. Point your browser to ``http://127.0.0.1:8000`` (the default server location)
#. Click on stuff, see what happens. You can't hurt anything, it's all read-only.

Of course, this is only suitable for playing around. If you want to get serious about deploying StackTach you should set up a proper webserver and database on standalone servers. There is a lot of data that gets collected by StackTach (depending on your deployment size) ... be warned. Keep an eye on DB size.

.. _stacktach-config-files:

The Config Files
****************
There are two config files for StackTach. The first one tells us where the second one is. A sample of these two files is in ``./etc/sample_*``. Create a local copy of these files and populate them with the appropriate config values as described below.

The ``sample_stacktach_config.sh`` shell script defines the necessary environment variables StackTach needs. Most of these are just information about the database (assuming MySql) but some are a little different. Copy this file and modify it for your environment. ``source`` this
``stacktach_config.sh`` shell script to set up the necessary environment variables.

``STACKTACH_INSTALL_DIR`` should point to where StackTach is running out of. In most cases this will be your repo directory, but it could be elsewhere if your going for a proper deployment.
The StackTach worker needs to know which RabbitMQ servers to listen to. This information is stored in the deployment file. ``STACKTACH_DEPLOYMENTS_FILE`` should point to this json file. To learn more about the deployments file, see further down.

Finally, ``DJANGO_SETTINGS_MODULE`` tells Django where to get its configuration from. This should point to the ``setting.py`` file. You shouldn't have to do much with the ``settings.py`` file and most of what it needs is in these environment variables.

The ``sample_stacktach_worker_config.json`` file tells StackTach where each of the RabbitMQ servers are that it needs to get events from. In most cases you'll only have one entry in this file, but for large multi-cell deployments, this file can get pretty large. It's also handy for setting up one StackTach for each developer environment.

The file is in json format and the main configuration is under the ``deployments`` key, which should contain a list of deployment dictionaries.

A blank worker config file would look like this: ::

    {"deployments": [] }

But that's not much fun. A deployment entry would look like this: ::

    {"deployments": [
         {
             "name": "east_coast.prod.cell1",
             "durable_queue": false,
             "rabbit_host": "10.0.1.1",
             "rabbit_port": 5672,
             "rabbit_userid": "rabbit",
             "rabbit_password": "rabbit",
             "rabbit_virtual_host": "/",
             "topics": {
                 "nova": [
                     {"queue": "notifications.info", "routing_key": "notifications.info"},
                     {"queue": "notifications.error", "routing_key": "notifications.error"}
                 ]
             }
         }
    ]}

where, *name* is whatever you want to call your deployment, and *rabbit_\** are the connectivity details for your rabbit server. It should be the same information in your `nova.conf` file that OpenStack is using. Note, json has no concept of comments, so using ``#``, ``//`` or ``/* */`` as a comment won't work.

By default, Nova uses ephemeral queues. If you are using durable queues, be sure to change the necessary flag here.

The topics section defines which queues to pull notifications from. You should
pull notifications from all related queues (``.error``, ``.info``, ``.warn``, etc)

You can add as many deployments as you like.


Starting the Worker
===================

Note: the worker now uses librabbitmq, be sure to install that first.

``./worker/start_workers.py`` will spawn a worker.py process for each deployment defined. Each worker will consume from a single Rabbit queue.


Configuring Nova to Generate Notifications
==========================================

In the OpenStack service you wish to have generate notifications, add the
following to its ``.conf`` file: ::

    --notification_driver=nova.openstack.common.notifier.rpc_notifier
    --notification_topics=monitor

**Note:** *This will likely change once the various project switch to ``oslo.messaging``
which uses endpoints to define the notification drivers.*

This will tell OpenStack to publish notifications to a Rabbit exchange starting with
``monitor.*`` ... this may result in ``monitor.info``, ``monitor.error``, etc.

You'll need to restart Nova once these changes are made.

If you're using `DevStack`_ you may want to set up your ``local.conf`` to include the following: ::

    [[post-config|$NOVA_CONF]]
    [DEFAULT]
    notification_driver=nova.openstack.common.notifier.rpc_notifier
    notification_topics=notifications,monitor
    notify_on_state_change=vm_and_task_state
    notify_on_any_change=True
    instance_usage_audit=True
    instance_usage_audit_period=hour

.. _DevStack: http://devstack.org/


Next Steps
==========

Once you have this working well, you should download and install ``Stacky`` and play with the command line tool.

