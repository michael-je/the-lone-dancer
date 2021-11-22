#!/bin/bash

cd /the-lone-dancer

if [[ $(git pull) != 'Already up to date.' || $1 == '-f' ]]
then
	echo "Git repo has been updated... Rebuilding container"
	if [[ -n $(podman ps -a | grep the-lone-dancer ) ]]
	then
		podman stop the-lone-dancer
		podman rm the-lone-dancer
	fi
	podman build . -t the-lone-dancer
	podman create --name the-lone-dancer --env-file .env -ti the-lone-dancer
	systemctl start the-lone-dancer.service
else
	echo "Repository already up to date. No need to update bot."
fi
