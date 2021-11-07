#/bin/bash

[[ -e /the-lone-dancer ]] || git clone https://github.com/michael-je/the-lone-dancer.git /the-lone-dancer
cd /the-lone-dancer

if [[ ! -f .env ]]
then
	cp .env.example .env
	token=""
	echo "Paste your discord token here: "
	read -s token
	sed -i "s/DISCORD_TOKEN.*/DISCORD_TOKEN=$token/" .env
fi

podman build . -t the-lone-dancer

cp the-lone-dancer*.service /etc/systemd/system/
cp the-lone-dancer*.timer /etc/systemd/system/
chmod +x update.sh
cp update.sh /usr/local/bin/the-lone-dancer-update.sh
systemctl daemon-reload
systemctl enable the-lone-dancer.service
systemctl enable --now the-lone-dancer-update.timer
systemctl start the-lone-dancer-update.service
