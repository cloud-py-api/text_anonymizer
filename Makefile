# SPDX-FileCopyrightText: 2026 Nextcloud GmbH and Nextcloud contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

.DEFAULT_GOAL := help

APP_ID := text_anonymizer
APP_NAME := TextAnonymizer
APP_VERSION := 0.1.0
# Routes mirror appinfo/info.xml. access_level: 0 = PUBLIC, 1 = USER, 2 = ADMIN.
route = {"url":"$(1)","verb":"$(2)","access_level":$(3),"headers_to_exclude":[],"bruteforce_protection":[]}
ROUTES := [$(call route,^/redact_file$$,POST,1),$(call route,^/img/icon\\.svg$$,GET,1)]
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
	@echo "  run31             installs $(APP_NAME) for Nextcloud 31"
	@echo "  run32             installs $(APP_NAME) for Nextcloud 32"
	@echo "  run33             installs $(APP_NAME) for Nextcloud 33"
	@echo "  run34             installs $(APP_NAME) for Nextcloud 34"
	@echo "  run35             installs $(APP_NAME) for Nextcloud 35"
	@echo "  run36             installs $(APP_NAME) for Nextcloud 36"
	@echo "  run               installs $(APP_NAME) for Nextcloud Latest"
	@echo " "
	@echo "  > Commands for manual registration of ExApp($(APP_NAME) should be running!):"
	@echo " "
	@echo "  register31        performs registration of running $(APP_NAME) into the 'manual_install' deploy daemon."
	@echo "  register32        performs registration of running $(APP_NAME) into the 'manual_install' deploy daemon."
	@echo "  register33        performs registration of running $(APP_NAME) into the 'manual_install' deploy daemon."
	@echo "  register34        performs registration of running $(APP_NAME) into the 'manual_install' deploy daemon."
	@echo "  register35        performs registration of running $(APP_NAME) into the 'manual_install' deploy daemon."
	@echo "  register36        performs registration of running $(APP_NAME) into the 'manual_install' deploy daemon."
	@echo "  register          performs registration of running $(APP_NAME) into the 'manual_install' deploy daemon."


.PHONY: build-push
build-push:
    # docker login ghcr.io
	DOCKER_BUILDKIT=1 docker buildx build --push --platform linux/arm64/v8,linux/amd64 --tag ghcr.io/nextcloud/$(APP_ID):latest .

.PHONY: run31
run31:
	docker exec master-stable31-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable31-1 sudo -u www-data php occ app_api:app:register $(APP_ID) \
		--info-xml https://raw.githubusercontent.com/nextcloud/$(APP_ID)/main/appinfo/info.xml

.PHONY: run32
run32:
	docker exec master-stable32-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable32-1 sudo -u www-data php occ app_api:app:register $(APP_ID) \
		--info-xml https://raw.githubusercontent.com/nextcloud/$(APP_ID)/main/appinfo/info.xml

.PHONY: run33
run33:
	docker exec master-stable33-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable33-1 sudo -u www-data php occ app_api:app:register $(APP_ID) \
		--info-xml https://raw.githubusercontent.com/nextcloud/$(APP_ID)/main/appinfo/info.xml

.PHONY: run34
run34:
	docker exec master-stable34-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable34-1 sudo -u www-data php occ app_api:app:register $(APP_ID) \
		--info-xml https://raw.githubusercontent.com/nextcloud/$(APP_ID)/main/appinfo/info.xml

.PHONY: run35
run35:
	docker exec master-stable35-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable35-1 sudo -u www-data php occ app_api:app:register $(APP_ID) \
		--info-xml https://raw.githubusercontent.com/nextcloud/$(APP_ID)/main/appinfo/info.xml

.PHONY: run36
run36:
	docker exec master-stable36-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable36-1 sudo -u www-data php occ app_api:app:register $(APP_ID) \
		--info-xml https://raw.githubusercontent.com/nextcloud/$(APP_ID)/main/appinfo/info.xml

.PHONY: run
run:
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:register $(APP_ID) \
		--info-xml https://raw.githubusercontent.com/nextcloud/$(APP_ID)/main/appinfo/info.xml

.PHONY: register31
register31:
	docker exec master-stable31-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable31-1 sudo -u www-data php occ app_api:app:register $(APP_ID) manual_install --json-info $(JSON_INFO) --wait-finish

.PHONY: register32
register32:
	docker exec master-stable32-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable32-1 sudo -u www-data php occ app_api:app:register $(APP_ID) manual_install --json-info $(JSON_INFO) --wait-finish

.PHONY: register33
register33:
	docker exec master-stable33-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable33-1 sudo -u www-data php occ app_api:app:register $(APP_ID) manual_install --json-info $(JSON_INFO) --wait-finish

.PHONY: register34
register34:
	docker exec master-stable34-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable34-1 sudo -u www-data php occ app_api:app:register $(APP_ID) manual_install --json-info $(JSON_INFO) --wait-finish

.PHONY: register35
register35:
	docker exec master-stable35-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable35-1 sudo -u www-data php occ app_api:app:register $(APP_ID) manual_install --json-info $(JSON_INFO) --wait-finish

.PHONY: register36
register36:
	docker exec master-stable36-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-stable36-1 sudo -u www-data php occ app_api:app:register $(APP_ID) manual_install --json-info $(JSON_INFO) --wait-finish

.PHONY: register
register:
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:unregister $(APP_ID) --silent --force || true
	docker exec master-nextcloud-1 sudo -u www-data php occ app_api:app:register $(APP_ID) manual_install --json-info $(JSON_INFO) --wait-finish
