#/bin/bash
# Set up the bot on the system as a container with auto-updates
# from GitHub and automatic container rebuilding and restarting.
# This script should be run interactively when setting up the bot
# on a new system.

[[ -e /the-lone-dancer ]] || git clone https://github.com/michael-je/the-lone-dancer.git /the-lone-dancer
cd /the-lone-dancer
mkdir /the-lone-dancer/.container

if [[ ! -f .env ]]
then
	cp .env.example .env
	token=""
	echo "Paste your discord token here: "
	read -s token
	sed -i "s/DISCORD_TOKEN.*/DISCORD_TOKEN=$token/" .env
fi

if [[ $(grep the-lone-dancer /etc/passwd) ]]
then
	echo User the-lone-dancer already exists
else
	useradd the-lone-dancer
	loginctl enable-linger the-lone-dancer
fi

sudo -u the-lone-dancer podman build . -t the-lone-dancer

cp the-lone-dancer*.service /etc/systemd/system/
cp the-lone-dancer*.timer /etc/systemd/system/
chmod +x update.sh
cp update.sh /usr/local/bin/the-lone-dancer-update.sh
systemctl daemon-reload
systemctl enable the-lone-dancer.service
systemctl enable --now the-lone-dancer-update.timer
systemctl start the-lone-dancer-update.service
