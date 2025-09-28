# Simple Makefile for Docker commands

.PHONY: help setup up down logs restart build shell clean

setup:
	@../setup.sh --docker

help:
	@echo "SentientResearchAgent Docker Commands"
	@echo "===================================="
	@echo "make setup    - Run Docker setup"
	@echo "make up       - Start all services"
	@echo "make down     - Stop all services"
	@echo "make logs     - View logs"
	@echo "make restart  - Restart services"
	@echo "make build    - Rebuild images"
	@echo "make shell    - Open backend shell"
	@echo "make clean    - Stop and remove everything"

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

restart:
	docker compose restart

build:
	docker compose build

shell:
	docker compose exec backend bash

clean:
	docker compose down -v --remove-orphans