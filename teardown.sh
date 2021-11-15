#/bin/bash

systemctl disable --now the-lone-dancer-update.timer
systemctl disable --now the-lone-dancer-update.service
systemctl disable --now the-lone-dancer.service
rm /etc/systemd/system/the-lone-dancer*
systemctl daemon-reload
userdel --force the-lone-dancer
rm -r /the-lone-dancer
