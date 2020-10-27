Сервис обновления токена авторизации ufanet для сервера cctv Shinobi
====================================================================

- скопировать файл настроек u2s-config.sample.yaml в u2s-config.yaml
- внести в файл u2s-config.yaml данные авторизации ufanet (ufanet.user, ufanet.password)
- внести в файл u2s-config.yaml данные url, токена авторизации shinobi и идентификатор группы мониторов (shinobi.cctv_url, shinobi.api_key, shinobi.group_key)
- выполнить docker-compose up

