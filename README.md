# IntruBot

**VERSIÓN EN ESPAÑOL** | [ENGLISH VERSION](README.en.md)

[![](https://badgen.net/badge/icon/github?icon=github&label)](https://github.com/dgongut/intrubot)
[![](https://badgen.net/badge/icon/docker?icon=docker&label)](https://hub.docker.com/r/dgongut/intrubot)
[![Docker Pulls](https://badgen.net/docker/pulls/dgongut/intrubot?icon=docker&label=pulls)](https://hub.docker.com/r/dgongut/intrubot/)
[![Docker Stars](https://badgen.net/docker/stars/dgongut/intrubot?icon=docker&label=stars)](https://hub.docker.com/r/dgongut/intrubot/)
[![Docker Image Size](https://badgen.net/docker/size/dgongut/intrubot?icon=docker&label=image%20size)](https://hub.docker.com/r/dgongut/intrubot/)
![Github stars](https://badgen.net/github/stars/dgongut/intrubot?icon=github&label=stars)
![Github forks](https://badgen.net/github/forks/dgongut/intrubot?icon=github&label=forks)
![Github last-commit](https://img.shields.io/github/last-commit/dgongut/intrubot)
![Github last-commit](https://badgen.net/github/license/dgongut/intrubot)

<img src="https://raw.githubusercontent.com/dgongut/pictures/main/IntruBot/IntruBot.png" width="150">

Lleva el control de los dispositivos que se conectan a tu red.

- ✅ Aviso en Telegram cuando se conecta un dispositivo nuevo, con IP, MAC, fabricante y hostname
- ✅ Dispositivos identificados por su MAC: un cambio de IP por DHCP ya no se confunde con un intruso
- ✅ Detección de MAC privadas (las direcciones aleatorias de móviles y portátiles)
- ✅ Panel con el estado de la red y escaneo bajo demanda
- ✅ Listado de dispositivos con estado (🟢 conectado / ⚪ desconectado), última vez visto y primera detección
- ✅ Renombrar y olvidar dispositivos desde botones, sin escribir IPs a mano
- ✅ Primer escaneo silencioso: registra tu red sin bombardearte con un aviso por dispositivo
- ✅ Escaneo ARP de toda la red en segundos
- ✅ Rangos, redes CIDR y direcciones sueltas en `IP_RANGE`
- ✅ Varias redes o VLAN en un solo bot, cada una con su nombre y con avisos que se pueden silenciar por red
- ✅ Aviso si el escaneo deja de funcionar (y cuando vuelve)
- ✅ Imagen multiarquitectura compatible con Raspberry Pi, NAS y servidores estándar
- ✅ Soporte de idiomas (Spanish, English)

¿Lo buscas en [![](https://badgen.net/badge/icon/docker?icon=docker&label)](https://hub.docker.com/r/dgongut/intrubot)?

## Crear tu bot de Telegram

1. Abre [@BotFather](https://t.me/BotFather) en Telegram y envía `/newbot`. Sigue las instrucciones (un nombre y un username acabado en `bot`).
2. BotFather te devolverá el token del bot. Guárdalo: irá en la variable `TELEGRAM_TOKEN`.
3. Para conocer tu propio chat ID (lo necesitas para `TELEGRAM_ADMIN`), habla con [@MissRose_bot](https://t.me/MissRose_bot) y envíale `/id`.
4. *(Opcional)* Si vas a usar el bot dentro de un grupo, añádelo, hazlo administrador y obtén el chat ID del grupo de la misma forma; ese valor irá en `TELEGRAM_GROUP`.
5. *(Opcional)* Si quieres ponerle el icono oficial al bot, descarga la imagen en alta resolución [aquí](https://raw.githubusercontent.com/dgongut/pictures/main/IntruBot/IntruBot.png) y envíasela a [@BotFather](https://t.me/BotFather) usando la opción `/setuserpic`.

## Comandos disponibles

| Comando | Descripción |
|---|---|
| `/start` | Panel con el estado de la red (o de cada red): dispositivos conocidos y conectados, último y próximo escaneo |
| `/list` | Dispositivos conocidos. Con varias redes, primero eliges la red (o todas). Pulsa en un dispositivo para ver sus detalles, renombrarlo u olvidarlo |
| `/scan` | Escanea la red ahora mismo |
| `/help` | Lista de comandos |
| `/version` | Muestra la versión actual |
| `/donate` `/donors` | Dona al desarrollador / lista de donantes |

## Cómo funciona

Cada `HOURS_BETWEEN_SCANS` horas el bot lanza una petición ARP a todas las direcciones vigiladas (`IP_RANGE`, o cada red de `NETWORKS`). Todo dispositivo IPv4 de la red local tiene que responder a ARP (aunque tenga cortafuegos y no conteste al ping), y la respuesta trae su MAC, que es lo que lo identifica.

- El **primer escaneo** registra los dispositivos conectados sin avisar de cada uno y te envía un resumen. Es el momento de ponerles nombre.
- A partir de ahí, cada dispositivo con una MAC nueva genera un aviso con botones para **renombrarlo** o ver sus **detalles**.
- Si en un escaneo aparecen más de 5 dispositivos nuevos, recibes un único resumen en lugar de un mensaje por cada uno.
- **Olvidar** un dispositivo lo quita de la lista: si sigue conectado, se avisará de él como nuevo en el siguiente escaneo.

> [!NOTE]
> Muchos móviles y portátiles usan una **MAC privada** (aleatoria) para cada red Wi-Fi. El bot las marca como *(privada)*: en ellas no se puede conocer el fabricante y, si el dispositivo decide cambiarla, aparecerá como uno nuevo.

## Configuración en las variables del Docker Compose

| CLAVE  | OBLIGATORIO | VALOR |
|:------------- |:---------------:| :-------------|
|TELEGRAM_TOKEN |✅| Token del bot |
|TELEGRAM_ADMIN |✅| ChatId del administrador (se puede obtener hablándole al bot [Rose](https://t.me/MissRose_bot) escribiendo /id). Admite múltiples administradores separados por comas. Por ejemplo 12345,54431,55944 |
|TELEGRAM_GROUP |❌| ChatId del grupo. Si este bot va a formar parte de un grupo, es necesario especificar el chatId de dicho grupo. Es necesario que el bot sea administrador del grupo |
|TELEGRAM_THREAD |❌| Thread del tema dentro de un supergrupo; valor numérico (2,3,4..). Por defecto 1. Se utiliza en conjunción con la variable TELEGRAM_GROUP |
|TZ |✅| Timezone (Por ejemplo Europe/Madrid) |
|IP_RANGE |✅*| Direcciones a vigilar. Admite rangos (`192.168.1.1-192.168.1.254`), redes (`192.168.1.0/24`) y direcciones sueltas, separados por comas. Máximo 65536 direcciones |
|NETWORKS |✅*| En lugar de `IP_RANGE`, para vigilar varias redes o VLAN: `nombre=rango[@interfaz]` separados por `;`. Por ejemplo `Casa=192.168.1.0/24; IoT=192.168.20.0/24@eth0.20`. Ver [Varias redes o VLAN](#varias-redes-o-vlan) |
|HOURS_BETWEEN_SCANS |❌| Horas entre escaneos; admite decimales (0.5 = 30 minutos). Mínimo un minuto. Por defecto 1 |
|NETWORK_INTERFACE |❌| Interfaz de red por la que escanear `IP_RANGE` (por ejemplo `eth0`). Por defecto, la que tenga la ruta hacia esas direcciones. Con `NETWORKS` se usa `@interfaz` en cada red |
|LANGUAGE |❌| Idioma, puede ser ES / EN. Por defecto ES (Spanish) |

\* Hace falta `IP_RANGE` o `NETWORKS`. Si están las dos, manda `NETWORKS`.

## Ejemplo de Docker-Compose para su ejecución normal

```yaml
services:
    intrubot:
        environment:
            - TELEGRAM_TOKEN=
            - TELEGRAM_ADMIN=
            - TZ=Europe/Madrid
            - IP_RANGE=192.168.1.0/24
            #- NETWORKS=Casa=192.168.1.0/24; IoT=192.168.20.0/24 # En lugar de IP_RANGE, para varias redes
            #- TELEGRAM_GROUP=
            #- TELEGRAM_THREAD=1
            #- HOURS_BETWEEN_SCANS=1
            #- NETWORK_INTERFACE=
            #- LANGUAGE=ES
        volumes:
            - /ruta/para/guardar/los/datos:/app/data # CAMBIAR LA PARTE IZQUIERDA
        image: dgongut/intrubot:latest
        container_name: intrubot
        restart: always
        network_mode: host
```

## Anotaciones

- `network_mode: host` es **imprescindible** (o bien redes `macvlan`, ver [Varias redes o VLAN](#varias-redes-o-vlan)): el escaneo ARP solo funciona si el contenedor ve directamente la red local. Con la red bridge de Docker solo vería otros contenedores.
- El escaneo usa sockets raw (capacidad `NET_RAW`), que Docker concede por defecto. Si la has quitado con `cap_drop`, añádela con `cap_add: [NET_RAW]`.
- La lista de dispositivos se guarda en `/app/data/devices.json`, así que hay que mapear ese volumen para no perderla al recrear el contenedor.
- La imagen incluye un `HEALTHCHECK`: el contenedor aparece como *unhealthy* si el bot deja de hablar con Telegram.

## Varias redes o VLAN

Un solo bot puede vigilar varias redes a la vez. Usa `NETWORKS` en lugar de `IP_RANGE`, con una entrada `nombre=rango` por red separadas por `;` y, opcionalmente, `@interfaz`:

```yaml
- NETWORKS=Casa=192.168.1.0/24; IoT=192.168.20.0/24@eth0.20; Invitados=192.168.30.0/24
```

- El rango de cada red admite lo mismo que `IP_RANGE`: rangos, redes CIDR y direcciones sueltas separadas por comas. Una dirección no puede estar en dos redes, y entre todas no pueden pasar de 65536 direcciones.
- Sin `@interfaz`, el bot escanea cada dirección por la interfaz que indique la tabla de rutas. Pon `@interfaz` cuando la pata de esa VLAN no tenga IP propia en el equipo.
- Todas las redes se escanean a la vez, así que añadir redes apenas alarga el escaneo.

### Requisito: una interfaz en cada VLAN

El ARP **no atraviesa routers**. El bot solo puede ver una red si el contenedor tiene una interfaz dentro de ella. Si en una red no responde nadie y, según la tabla de rutas, solo se llega a ella a través del router, el bot te avisa de que no la puede ver. Hay dos formas de darle esas interfaces:

**1. `network_mode: host` y una subinterfaz por VLAN en el equipo.** El puerto del switch al que va conectado el servidor tiene que llevar esas VLAN etiquetadas (modo trunk). En Linux, por ejemplo, para la VLAN 20:

```bash
ip link add link eth0 name eth0.20 type vlan id 20
ip addr add 192.168.20.5/24 dev eth0.20
ip link set eth0.20 up
```

Esto no sobrevive a un reinicio: hazlo persistente con la herramienta de red de tu sistema (netplan, `/etc/network/interfaces`, NetworkManager…). En Unraid basta con activar las VLAN en *Settings → Network Settings*, que crea `br0.20` y similares.

**2. Una red `macvlan` de Docker por VLAN**, sin `network_mode: host` y sin tocar el equipo. Docker crea la subinterfaz `eth0.20` si no existe. Reserva para el contenedor una IP fuera del rango de tu DHCP:

```yaml
services:
    intrubot:
        environment:
            - TELEGRAM_TOKEN=
            - TELEGRAM_ADMIN=
            - TZ=Europe/Madrid
            - NETWORKS=Casa=192.168.1.0/24; IoT=192.168.20.0/24
        volumes:
            - /ruta/para/guardar/los/datos:/app/data
        image: dgongut/intrubot:latest
        container_name: intrubot
        restart: always
        networks:
            casa:
                ipv4_address: 192.168.1.250
            iot:
                ipv4_address: 192.168.20.250

networks:
    casa:
        driver: macvlan
        driver_opts:
            parent: eth0
        ipam:
            config:
                - subnet: 192.168.1.0/24
                  gateway: 192.168.1.1
    iot:
        driver: macvlan
        driver_opts:
            parent: eth0.20
        ipam:
            config:
                - subnet: 192.168.20.0/24
```

> [!NOTE]
> Con `macvlan` el equipo que ejecuta Docker no se ve desde sus propios contenedores (es una limitación de macvlan), así que ese equipo no aparecerá en la lista.

### Cómo se ven varias redes en el bot

- El panel de `/start` muestra cada red con sus dispositivos conocidos y conectados, y avisa si su último escaneo falló.
- `/list` empieza preguntando qué red quieres ver, o todas.
- Los avisos y las fichas de los dispositivos indican su red.
- **🔔 Avisos por red** (en el panel) silencia o reactiva los avisos de dispositivos nuevos de cada red. Viene bien para la red de invitados, que suele ser un desfile de MAC privadas. Una red silenciada se sigue escaneando y sus dispositivos siguen en la lista. La preferencia se guarda en `/app/data`.
- Un mismo dispositivo en dos redes cuenta como dos: los routers suelen responder con la misma MAC en todas las VLAN, y que tu portátil aparezca de repente en la red IoT es algo que quieres saber.
- Si renombras una red en `NETWORKS`, o pasas de `IP_RANGE` a `NETWORKS`, cada dispositivo pasa a la red que contiene su IP, sin perder su nombre y sin volver a avisar de él.

### Actualizar desde la versión 1.x

La 2.0 se ha reescrito por completo. Mantén el mismo volumen `/app/data` y el bot migrará solo tu `known_devices.json` (lo renombra a `known_devices.json.bak`):

- Los dispositivos ya conocidos **no** se notificarán como nuevos y recuperan el nombre que les pusiste en cuanto aparecen en un escaneo.
- Los comandos `/delete`, `/deleteall` y `/rename` desaparecen: ahora todo se hace con botones desde `/list`.
- **`tty: true` ya no hace falta.** Hasta la 1.x el compose lo llevaba para que los logs del bot salieran en `docker logs`; desde la 2.0 la imagen los escribe al momento sin él. Puedes quitarlo, o dejarlo: no molesta.
- Las variables `IP_RANGE` y `HOURS_BETWEEN_SCANS` siguen funcionando igual. `IP_RANGE` acepta además redes CIDR y varias entradas separadas por comas, y si tienes varias VLAN puedes pasarte a `NETWORKS`.

## Solo para desarrolladores

### Ejecución con código local

Para su ejecución en local y probar nuevos cambios de código, se necesita renombrar el fichero `.env-example` a `.env` con los valores necesarios para su ejecución.
Es necesario establecer un `TELEGRAM_TOKEN` y un `TELEGRAM_ADMIN` correctos y diferentes al de la ejecución normal.

La estructura de carpetas debe quedar:

```
intrubot/
    ├── .env
    ├── intrubot.py
    ├── config.py
    ├── devices.py
    ├── scanner.py
    ├── logger.py
    ├── message_queue.py
    ├── requirements.txt
    ├── Dockerfile_local
    ├── docker-compose.local.yaml
    └── locale
        ├── en.json
        └── es.json
```

Para levantarlo (el código se recarga solo al guardar cambios gracias a `watchmedo`):

```bash
docker compose -f docker-compose.local.yaml up -d --build --force-recreate
```

Para detenerlo:

```bash
docker compose -f docker-compose.local.yaml down --rmi all
```
