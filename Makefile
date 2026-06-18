# PandaDoc Automation Makefile

include makes/py.mk
include makes/docker.mk

.PHONY: help
help: py/help docker/help

.PHONY: lint
lint: py/lint
