# IntruBot
[![](https://badgen.net/badge/icon/github?icon=github&label)](https://github.com/dgongut/intrubot)
[![](https://badgen.net/badge/icon/docker?icon=docker&label)](https://hub.docker.com/r/dgongut/intrubot)
[![Docker Pulls](https://badgen.net/docker/pulls/dgongut/intrubot?icon=docker&label=pulls)](https://hub.docker.com/r/dgongut/intrubot/)
[![Docker Stars](https://badgen.net/docker/stars/dgongut/intrubot?icon=docker&label=stars)](https://hub.docker.com/r/dgongut/intrubot/)
[![Docker Image Size](https://badgen.net/docker/size/dgongut/intrubot?icon=docker&label=image%20size)](https://hub.docker.com/r/dgongut/intrubot/)
![Github stars](https://badgen.net/github/stars/dgongut/intrubot?icon=github&label=stars)
![Github forks](https://badgen.net/github/forks/dgongut/intrubot?icon=github&label=forks)
![Github last-commit](https://img.shields.io/github/last-commit/dgongut/intrubot)
![Github last-commit](https://badgen.net/github/license/dgongut/intrubot)
![alt text](https://github.com/dgongut/pictures/blob/main/intrubot/mockup.png)

Lleva el control de los dispositivos que se conectan a tu red.

- ✅ Listar dispositivos detectados
- ✅ Notificaciones si un nuevo dispositivo se conecta a tu red
- ✅ Renombrar dispositivos
- ✅ Soporte de idiomas (Spanish, English)

¿Lo buscas en [![](https://badgen.net/badge/icon/docker?icon=docker&label)](https://hub.docker.com/r/dgongut/intrubot)?

🖼️ Si deseas establecerle el icono al bot de telegram, te dejo [aquí](https://raw.githubusercontent.com/dgongut/pictures/main/intrubot/intrubot.png) el icono en alta resolución. Solo tienes que descargarlo y mandárselo al @BotFather en la opción de BotPic.

## Configuración en config.py

| CLAVE  | OBLIGATORIO | VALOR |
|:------------- |:---------------:| :-------------|
|TELEGRAM_TOKEN |✅| Token del bot |
|TELEGRAM_ADMIN |✅| ChatId del administrador (se puede obtener hablándole al bot Rose escribiendo /id). Admite múltiples administradores separados por comas. Por ejemplo 12345,54431,55944 |
|TELEGRAM_GROUP |❌| ChatId del grupo. Si este bot va a formar parte de un grupo, es necesario especificar el chatId de dicho grupo. Es necesario que el bot sea administrador del grupo |
|TELEGRAM_THREAD |❌| Thread del tema dentro de un supergrupo; valor numérico (2,3,4..). Por defecto 1. Se utiliza en conjunción con la variable TELEGRAM_GROUP |
|TZ |✅| Timezone (Por ejemplo Europe/Madrid) |
|IP_RANGE |✅| Rango de IPs a detectar. Por ejemplo 192.168.1.1-192.168.1.255 | 
|LANGUAGE |❌| Idioma, puede ser ES / EN / NL / DE. Por defecto es ES (Spanish) |

### Anotaciones
Será necesario mapear un volumen para almacenar lo que el bot escribe en /app/data

### Ejemplo de Docker-Compose para su ejecución normal

```yaml
version: '3.3'
services:
    intrubot:
        environment:
            - TELEGRAM_TOKEN=
            - TELEGRAM_ADMIN=
            - TZ=Europe/Madrid
            - IP_RANGE=
            #- TELEGRAM_GROUP=
            #- TELEGRAM_THREAD=1
            #- LANGUAGE=ES
        volumes:
            - /ruta/para/guardar/las/programaciones:/app/data # CAMBIAR LA PARTE IZQUIERDA
        image: dgongut/intrubot:latest
        container_name: intrubot
        restart: always
        network_mode: host
        tty: true
```

---

## Solo para desarrolladores - Ejecución con código local


Para su ejecución en local y probar nuevos cambios de código, se necesita renombrar el fichero `.env-example` a `.env` con los valores necesarios para su ejecución.
Es necesario establecer un `TELEGRAM_TOKEN` y un `TELEGRAM_ADMIN` correctos y diferentes al de la ejecución normal.

La estructura de carpetas debe quedar:

```
intrubot/
    ├── .env
    ├── LICENSE
    ├── README.md
    ├── config.py
    ├── intrubot.py
    ├── Dockerfile_local
    ├── docker-compose.yaml
    └── locale
        ├── en.json
        ├── es.json
        └── nl.json
```

Para levantarlo habría que ejecutar en esa ruta: `docker compose up -d`

Para detenerlo y probar nuevos cambios habría que ejecutar en esa ruta: `docker compose down --rmi`
