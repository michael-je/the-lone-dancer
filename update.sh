#!/bin/bash

cd /the-lone-dancer
git pull
updated=$?

if [[ $(sudo git pull) != 'Already up to date.' || $1 == '-f' ]]
then
	echo "Git repo has been updated... Rebuilding container"
	[[ -n $(podman ps -a | grep the-lone-dancer ) ]] && podman rm the-lone-dancer
	#podman rmi the-lone-dancer
	podman build . -t the-lone-dancer
	podman create --name the-lone-dancer --env-file .env -ti the-lone-dancer
	systemctl start the-lone-dancer.service
fi
