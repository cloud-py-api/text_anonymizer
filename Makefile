# SPDX-FileCopyrightText: 2026 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

.DEFAULT_GOAL := help

APP_ID := text_anonymizer
APP_NAME := TextAnonymizer
APP_VERSION := 0.1.0
# Routes mirror appinfo/info.xml. access_level: 0 = PUBLIC, 1 = USER, 2 = ADMIN.
route = {"url":"$(1)","verb":"$(2)","access_level":$(3),"headers_to_exclude":[],"bruteforce_protection":[]}
ROUTES := [$(call route,^/public$$,GET,0),$(call route,^/user$$,GET,1),$(call route,^/admin$$,GET,2),$(call route,^/$$,GET,1),$(call route,^/ws$$,GET,1),$(call route,^/redact_file$$,POST,1)]
JSON_INFO := '{"id":"$(APP_ID)","name":"$(APP_NAME)","daemon_config_name":"manual_install","version":"$(APP_VERSION)","secret":"12345","port":9040,"routes":$(ROUTES)}'


.PHONY: help
help:
	@echo "  Welcome to $(APP_NAME) $(APP_VERSION)!"
	@echo " "
	@echo "  Please use \`make <target>\` where <target> is one of"
	@echo " "
	@echo "  build-push        builds CPU images and uploads them to ghcr.io"
	@echo " "
	@echo "  > Next commands are only for the dev environment with nextcloud-docker-dev!"
	@echo "  > They must be run from the host you are developing on, not in a Nextcloud container!"
	@echo " "
	@echo "  run30             installs $(APP_NAME) for Nextcloud 30"
	@echo "  run31             installs $(APP_NAME) for Nextcloud 31"
	@echo "  run               installs $(APP_NAME) for Nextcloud Latest"
	@echo " "
	@echo "  > Commands for manual registration of ExApp($(APP_NAME) should be running!):"
	@echo " "
	@echo "  register30        performs registration of running $(APP_NAME) into the 'manual_install' deploy daemon."
	@echo "  register31        performs registration of running $(APP_NAME) into the 'manual_install' deploy daemon."
	@echo "  register          performs registration of running $(APP_NAME) into the 'manual_install' deploy daemon."


.PHONY: build-push
build-push:
    # docker login ghcr.io
	DOCKER_BUILDKIT=1 docker buildx build --push --platform linux/arm64/v8,linux/amd64 --tag ghcr.io/nextcloud/app-skeleton-python:latest .

.PHONY: run30
run29:
	docker exec master-stable30-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable30-1 sudo -u www-data php occ app_api:app:register $(APP_ID) \
		--info-xml https://raw.githubusercontent.com/nextcloud/$(APP_ID)/main/appinfo/info.xml

.PHONY: run31
run30:
	docker exec master-stable31-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable31-1 sudo -u www-data php occ app_api:app:register $(APP_ID) \
		--info-xml https://raw.githubusercontent.com/nextcloud/$(APP_ID)/main/appinfo/info.xml

.PHONY: run
run:
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:register $(APP_ID) \
		--info-xml https://raw.githubusercontent.com/nextcloud/$(APP_ID)/main/appinfo/info.xml

.PHONY: register30
register30:
	docker exec master-stable30-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable30-1 sudo -u www-data php occ app_api:app:register $(APP_ID) manual_install --json-info $(JSON_INFO) --wait-finish

.PHONY: register31
register31:
	docker exec master-stable31-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable31-1 sudo -u www-data php occ app_api:app:register $(APP_ID) manual_install --json-info $(JSON_INFO) --wait-finish

.PHONY: register
register:
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:register $(APP_ID) manual_install --json-info $(JSON_INFO) --wait-finish
