#/bin/bash
# Remove the bot as set up by setup.sh if you don't want it on your system
# anymore.

systemctl disable --now the-lone-dancer-update.timer
systemctl disable --now the-lone-dancer-update.service
systemctl disable --now the-lone-dancer.service
rm /etc/systemd/system/the-lone-dancer*
systemctl daemon-reload
userdel --force the-lone-dancer
rm -r /etc/the-lone-dancer
rm -r /var/cache/the-lone-dancer
