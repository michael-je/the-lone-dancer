#/bin/bash
# Set up the bot on the system as a container with auto-updates
# from GitHub and automatic container rebuilding and restarting.
# This script should be run interactively when setting up the bot
# on a new system.

WORKDIR=/var/cache/the-lone-dancer
CONF_DIR=/etc/the-lone-dancer
ENV_FILE=$CONF_DIR/.env
TOKEN=""

while [[ $# -gt 0 ]]
do
	case $1 in
		--token)
			shift
			TOKEN=$1
			;;
		--token-ask)
			shift
			echo -n "Paste your discord token here: "
			read -s TOKEN
			echo ""
			;;
		-h|--help)
			echo "$0 [-h|--help] [--token TOKEN] [--token-ask]"
			exit 0
			;;
		*)
			;;
	esac
done



if ! grep the-lone-dancer /etc/passwd >/dev/null
then
	# Create user
	useradd the-lone-dancer
	loginctl enable-linger the-lone-dancer
fi

if [[ ! -d $WORKDIR ]]
then
	# Create/clone git repo
	git clone https://github.com/michael-je/the-lone-dancer.git $WORKDIR
	chown the-lone-dancer:the-lone-dancer $WORKDIR
fi
cd $WORKDIR

if [[ ! -d $CONF_DIR ]]
then
	# Create /etc/ directory
	mkdir $CONF_DIR
fi

if [[ ! -f $ENV_FILE ]]
then
	# Copy env-file
	cp .env.example .env
	sed -i "s/DISCORD_TOKEN.*/DISCORD_TOKEN=$TOKEN/" .env
fi

cp the-lone-dancer*.service /etc/systemd/system/
cp the-lone-dancer*.timer /etc/systemd/system/
chmod +x update.sh
cp update.sh /usr/local/bin/the-lone-dancer-update.sh
systemctl daemon-reload
systemctl enable the-lone-dancer.service
systemctl enable --now the-lone-dancer-update.timer
systemctl start the-lone-dancer-update.service
/usr/local/bin/the-lone-dancer-update.sh -f
