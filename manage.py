#!/usr/bin/env python
import os, sys

if __name__ == "__main__":
#    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stacktach.settings")
#	to run stacktach properly on debian 14.04
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
