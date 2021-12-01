#!/bin/bash
# Fetch GitHub updates and apply them.
# Rebuild the container using updates, but only if there were any updates.
# This script can be run manually with the -f switch or as a systemd service.
# This script will be run as root from the systemd update service.

WORKDIR=/var/cache/the-lone-dancer
CONF_DIR=/etc/the-lone-dancer
ENV_FILE=$CONF_DIR/.env

cd $WORKDIR

if [[ $(sudo -u the-lone-dancer git pull) != 'Already up to date.' || $1 == '-f' ]]
then
	echo "Git repo has been updated... Rebuilding container"
	systemctl stop the-lone-dancer.service
	if sudo -u the-lone-dancer podman ps -a | grep the-lone-dancer >/dev/null
	then
		sudo -u the-lone-dancer podman rm the-lone-dancer
	fi
	sudo -u the-lone-dancer podman build . -t the-lone-dancer
	sudo -u the-lone-dancer podman create --name the-lone-dancer --env-file $ENV_FILE -ti the-lone-dancer
	systemctl start the-lone-dancer.service
else
	echo "Repository already up to date. No need to update bot."
fi
