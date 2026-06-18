.EXPORT_ALL_VARIABLES:

.PHONY: docker/help
docker/help:
	@echo "Docker targets:"
	@echo "  docker/build     - Build image"
	@echo "  docker/up        - Start services"
	@echo "  docker/down      - Stop services"
	@echo "  docker/services  - List available services"
	@echo "  docker/logs      - Follow service logs"
	@echo

.PHONY: docker/build
docker/build:
	@docker build \
		--tag=obsidian-mcp \
		--file=docker/Dockerfile \
		--build-arg BUILD_RELEASE=dev \
		--load \
		$(options) \
		.

.PHONY: docker/up
docker/up:
	docker compose up --remove-orphans -d $(options)
	docker compose ps

.PHONY: docker/down
docker/down:
	docker compose down $(options)

.PHONY: docker/services
docker/services:
	docker compose config --services

.PHONY: docker/logs
docker/logs:
	docker compose logs --follow $(options)
