# Changelog

## v2.0.1

### 🐛 Correcciones

- **El bot no detectaba ningún dispositivo en algunos servidores.** Descartaba las direcciones que, según la tabla de rutas que lee scapy, solo eran alcanzables a través del router. Pero scapy solo lee las tablas `local` y `main`: en equipos con rutas en otras tablas (rutas por políticas), la propia red local parecía estar detrás del router y no se escaneaba. Ahora las rutas solo sirven para elegir la interfaz, y una red solo se da por inalcanzable si no responde nadie.
- **Ya no se escanea la propia IP del servidor**, que nunca responde a su propio ARP.

### 🔧 Cambios

- **Fuera `tty: true`** de los docker-compose y del README: la imagen ya escribe los logs al momento sin él. Si lo tienes puesto no molesta.

## v2.0.0

Reescritura completa del bot. Mantén el mismo volumen `/app/data` y la actualización es automática (ver [Migración desde 1.x](#migración-desde-1x)).

### ✨ Novedades

- **Varias redes o VLAN en un solo bot** con la nueva variable `NETWORKS` (`Casa=192.168.1.0/24; IoT=192.168.20.0/24@eth0.20`). Todas las redes se escanean a la vez, cada una por su interfaz.
- **Avisos por red**: cada red puede silenciarse desde el panel. Sigue escaneándose y sus dispositivos siguen en la lista, pero no avisa de los nuevos.
- **Botones en todo el bot**: panel de estado en `/start`, lista paginada de dispositivos y ficha de cada uno con opciones para renombrar u olvidar. Ya no hace falta escribir IPs a mano.
- **Ficha de dispositivo** con IP, MAC, fabricante, hostname, estado (🟢 conectado / ⚪ desconectado), última vez visto y fecha de la primera detección.
- **Avisos de dispositivo nuevo** con fabricante y hostname, y botones para ponerle nombre o ver sus detalles. Si aparecen más de 5 a la vez se envía un único resumen.
- **Detección de MAC privadas** (las direcciones aleatorias de móviles y portátiles), marcadas como *(privada)*.
- **Primer escaneo silencioso**: registra la red y envía un resumen en lugar de un aviso por cada dispositivo.
- **Nuevo comando `/scan`** y botón «Escanear ahora» para escanear al momento.
- **`IP_RANGE` más flexible**: además de rangos (`192.168.1.1-192.168.1.254`) acepta redes CIDR (`192.168.1.0/24`) y direcciones sueltas, separadas por comas.
- **Nueva variable `NETWORK_INTERFACE`** para elegir la interfaz por la que escanear `IP_RANGE`.
- **Nuevos comandos `/help` y `/donors`.**
- **Avisos de errores de escaneo** (sin permisos, interfaz inexistente, red solo accesible a través del router), una sola vez y no en cada escaneo, y aviso cuando el escaneo vuelve a funcionar.
- **`HEALTHCHECK` en la imagen**: el contenedor aparece como *unhealthy* si el bot deja de hablar con Telegram.
- **README en inglés** (`README.en.md`).

### 🔧 Cambios

- **Los dispositivos se identifican por su MAC y no por su IP.** Antes, cuando el DHCP daba a un dispositivo nuevo la IP de uno conocido, el nuevo pasaba desapercibido, y un dispositivo conocido que cambiaba de IP se avisaba como nuevo.
- **Escaneo mucho más rápido**: un barrido ARP de toda la red (unos segundos para un /24) en lugar de ARP y ping dirección por dirección (varios minutos).
- **Mensajes en HTML** en lugar de Markdown: los nombres con caracteres especiales ya no rompen los mensajes, y no hace falta modificar los nombres de los dispositivos.
- **Envío de mensajes con cola y reintentos**, respetando los límites de Telegram.
- **Mensajes de error claros al arrancar** si alguna variable está mal configurada.
- **Imagen actualizada** a Alpine 3.24, pyTelegramBotAPI 4.37.0 y scapy 2.7.0. Las dependencias se fijan en `requirements.txt`.
- **La lista de dispositivos se guarda en `/app/data/devices.json`** con escritura atómica. Si el fichero está dañado, se aparta en lugar de sobrescribirse.
- **`HOURS_BETWEEN_SCANS` debe ser de al menos un minuto** (0.02).

### 🐛 Correcciones

- `/delete` con una IP desconocida provocaba un error y no respondía.
- Las direcciones ya conocidas no se volvían a escanear, así que nunca se detectaba un cambio de dispositivo en esa IP.
- La resolución de nombres de host podía bloquear el escaneo durante mucho tiempo.
- El bot respondía a comandos dirigidos a otros bots del grupo (`/list@OtroBot`).
- Los logs no aparecían en `docker logs` sin `tty`.

### 🗑️ Eliminado

- Los comandos `/delete`, `/deleteall` y `/rename`: ahora se hace todo con botones desde `/list`.
- La variable `TELEGRAM_NOTIFICATION_CHANNEL`, que no se usaba.

### Migración desde 1.x

- **Volumen:** mantén el mismo volumen `/app/data`. Al arrancar, el bot importa `known_devices.json` y lo renombra a `known_devices.json.bak`.
- **Dispositivos ya conocidos:** no se avisan como nuevos y recuperan el nombre que les pusiste en cuanto aparecen en un escaneo.
- **`network_mode: host`:** sigue siendo imprescindible, o bien redes `macvlan` si quieres varias VLAN (ver el README).
