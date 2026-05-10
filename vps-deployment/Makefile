.PHONY: help init start stop restart status check-https fix-https logs deploy backup restore clean

help:
	@echo "🐳 Docker Swarm Management"
	@echo ""
	@echo "Usage: make [command]"
	@echo ""
	@echo "Commands:"
	@echo "  init               Initial full server bootstrap (/opt/scripts/init-server.sh)"
	@echo "  start              Start all services"
	@echo "  stop               Stop all services"
	@echo "  restart            Restart all services"
	@echo "  status             Show status of all services"
	@echo "  check-https        Check DNS/HTTPS/Traefik routing prerequisites"
	@echo "  fix-https          Diagnose & auto-repair Traefik routing / cert issues"
	@echo "  logs               Show logs (usage: make logs SERVICE=web)"
	@echo "  deploy             Deploy all (git pull + rebuild)"
	@echo "  backup             Backup all databases"
	@echo "  restore            Restore from backup (usage: make restore PROJECT=rent_django FILE=/path/to/backup.sql.gz)"
	@echo "  clean              Remove dangling images and volumes"
	@echo "  ps                 Show running containers"

init:
	@/opt/scripts/init-server.sh

start:
	@/opt/scripts/start-all.sh

stop:
	@/opt/scripts/stop-all.sh

restart: stop start

status:
	@/opt/scripts/status-all.sh

check-https:
	@/opt/scripts/check-https.sh

fix-https:
	@/opt/scripts/fix-https.sh

logs:
	@/opt/scripts/logs-all.sh $(SERVICE)

deploy:
	@/opt/scripts/deploy-all.sh

backup:
	@/opt/scripts/backup-all.sh

restore:
	@if [ -z "$(PROJECT)" ] || [ -z "$(FILE)" ]; then \
		echo "Usage: make restore PROJECT=project_name FILE=/path/to/backup.sql.gz"; \
	else \
		/opt/scripts/restore-project.sh $(PROJECT) $(FILE); \
	fi

clean:
	@echo "🧹 Cleaning up Docker..."
	docker image prune -a --force
	docker volume prune --force
	docker system df

ps:
	docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

.DEFAULT_GOAL := help
