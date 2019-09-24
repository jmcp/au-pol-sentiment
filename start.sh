#!/bin/bash

# Simple script to start up both uwsgi and nginx inside a container

# hack-n-slash to get this to work
egrep -v "^pidfile|^socket"  /usr/share/uwsgi/conf/default.ini > /tmp/default.ini

/usr/bin/uwsgi --emperor-pidfile /tmp/uwsgi.pid \
	       --ini /tmp/default.ini \
	       --yaml /etc/uwsgi/apps-enabled/wsgi.yaml \
	       --gid www-data --uid www-data  &

sleep 5

/usr/sbin/nginx 

