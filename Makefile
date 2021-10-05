
ROOT_DIR ?= /
BIN_DIR ?= $(ROOT_DIR)/usr/local/bin
BIN_FILE ?= $(BIN_DIR)/bot.py
SYSTEMD_DIR ?= $(ROOT_DIR)/etc/systemd/system
CONFIG_DIR ?= $(ROOT_DIR)/etc/bot
PYTHON ?= /usr/bin/python3


.PHONY: install systemd lint run .install-copy .install-system

default: lint run

clean:
	rm -f .target-*

install: .target-system .target-copy .target-systemd

.target-system:
	useradd --system discord-bot
	$(PYTHON) -m pip install --upgrade discord.py
	mkdir -p $(BIN_DIR) $(SYSTEMD_DIR) $(CONFIG_DIR)
	touch $@

.target-copy:
	cp bot.py bot.py.temp
	/usr/bin/sed -i s:CONFIG_DIR:$(CONFIG_DIR): bot.py.temp
	mv bot.py.temp $(BIN_DIR)/bot.py
	cp bot.service $(SYSTEMD_DIR)/
	cp bot.conf $(CONFIG_DIR)/
	touch $@

systemd: .target-systemd

.target-systemd:
	systemctl daemon-reload
	systemctl enable bot.service
	systemctl start bot.service
	touch $@

lint:
	find -name *.py -exec pylint {} +

run:
	$(PYTHON) $(BIN_FILE)
