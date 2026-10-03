# IntruBot

[VERSIÓN EN ESPAÑOL](README.md) | **ENGLISH VERSION**

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

Keep track of the devices that connect to your network.

- ✅ Telegram alert when a new device connects, with IP, MAC, vendor and hostname
- ✅ Devices identified by their MAC: a DHCP IP change is no longer mistaken for an intruder
- ✅ Detection of private MACs (the random addresses phones and laptops use)
- ✅ Network status panel and on-demand scans
- ✅ Device list with status (🟢 connected / ⚪ disconnected), last seen and first detection
- ✅ Rename and forget devices with buttons, no IPs typed by hand
- ✅ Silent first scan: registers your network without one alert per device
- ✅ ARP sweep of the whole network in seconds
- ✅ Ranges, CIDR networks and single addresses in `IP_RANGE`
- ✅ Several networks or VLANs in a single bot, each with its own name and alerts that can be muted per network
- ✅ Alert when scanning stops working (and when it recovers)
- ✅ Multi-architecture image compatible with Raspberry Pi, NAS and standard servers
- ✅ Language support (Spanish, English)

Looking for it on [![](https://badgen.net/badge/icon/docker?icon=docker&label)](https://hub.docker.com/r/dgongut/intrubot)?

## Create your Telegram bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram and send `/newbot`. Follow the instructions (a name and a username ending in `bot`).
2. BotFather will give you the bot token. Keep it: it goes in the `TELEGRAM_TOKEN` variable.
3. To find out your own chat ID (needed for `TELEGRAM_ADMIN`), talk to [@MissRose_bot](https://t.me/MissRose_bot) and send `/id`.
4. *(Optional)* If you are going to use the bot in a group, add it, make it an administrator and get the group chat ID the same way; that value goes in `TELEGRAM_GROUP`.
5. *(Optional)* To give the bot its official icon, download the high resolution image [here](https://raw.githubusercontent.com/dgongut/pictures/main/IntruBot/IntruBot.png) and send it to [@BotFather](https://t.me/BotFather) with the `/setuserpic` option.

## Available commands

| Command | Description |
|---|---|
| `/start` | Status panel of the network (or of each network): known and connected devices, last and next scan |
| `/list` | Known devices. With several networks, you pick the network first (or all of them). Tap a device to see its details, rename it or forget it |
| `/scan` | Scan the network right now |
| `/help` | Command list |
| `/version` | Show the current version |
| `/donate` `/donors` | Donate to the developer / donors list |

## How it works

Every `HOURS_BETWEEN_SCANS` hours the bot sends an ARP request to every watched address (`IP_RANGE`, or each network in `NETWORKS`). Every IPv4 device on the local network has to answer ARP (even behind a firewall that ignores ping), and the answer carries its MAC, which is what identifies it.

When a network is only reachable through the router (or the interface the routing table points to does not exist), ARP cannot reach it and the bot falls back to ping, as 1.x did. See [Requirement: an interface on each VLAN](#requirement-an-interface-on-each-vlan).

- The **first scan** registers the connected devices without reporting each one and sends you a summary. That is the moment to name them.
- From then on, every device with a new MAC triggers an alert with buttons to **rename** it or see its **details**.
- When more than 5 new devices show up in one scan, you get a single summary instead of one message each.
- **Forgetting** a device removes it from the list: if it is still connected, it is reported as new on the next scan.

> [!NOTE]
> Many phones and laptops use a **private** (random) MAC for each Wi-Fi network. The bot labels them *(private)*: their vendor cannot be known and, if the device decides to change it, it shows up as a new one.

## Docker Compose variables

| KEY  | REQUIRED | VALUE |
|:------------- |:---------------:| :-------------|
|TELEGRAM_TOKEN |✅| Bot token |
|TELEGRAM_ADMIN |✅| Administrator ChatId (you can get it by talking to the [Rose](https://t.me/MissRose_bot) bot and typing /id). Accepts several administrators separated by commas, for example 12345,54431,55944 |
|TELEGRAM_GROUP |❌| Group ChatId. If the bot is going to be part of a group, the chatId of that group is required. The bot must be an administrator of the group |
|TELEGRAM_THREAD |❌| Topic thread within a supergroup; numeric value (2,3,4..). Default 1. Used together with TELEGRAM_GROUP |
|TZ |✅| Timezone (for example Europe/Madrid) |
|IP_RANGE |✅*| Addresses to watch. Accepts ranges (`192.168.1.1-192.168.1.254`), networks (`192.168.1.0/24`) and single addresses, separated by commas. Up to 65536 addresses |
|NETWORKS |✅*| Instead of `IP_RANGE`, to watch several networks or VLANs: `name=range[@interface]` entries separated by `;`. For example `Home=192.168.1.0/24; IoT=192.168.20.0/24@eth0.20`. See [Several networks or VLANs](#several-networks-or-vlans) |
|HOURS_BETWEEN_SCANS |❌| Hours between scans; decimals allowed (0.5 = 30 minutes). At least one minute. Default 1 |
|NETWORK_INTERFACE |❌| Network interface to scan `IP_RANGE` through (for example `eth0`). Default: the one routing those addresses. With `NETWORKS`, use `@interface` on each network |
|LANGUAGE |❌| Language, ES / EN. Default ES (Spanish) |

\* Either `IP_RANGE` or `NETWORKS` is required. When both are set, `NETWORKS` wins.

## Docker Compose example

```yaml
services:
    intrubot:
        environment:
            - TELEGRAM_TOKEN=
            - TELEGRAM_ADMIN=
            - TZ=Europe/Madrid
            - IP_RANGE=192.168.1.0/24
            #- NETWORKS=Home=192.168.1.0/24; IoT=192.168.20.0/24 # Instead of IP_RANGE, for several networks
            #- TELEGRAM_GROUP=
            #- TELEGRAM_THREAD=1
            #- HOURS_BETWEEN_SCANS=1
            #- NETWORK_INTERFACE=
            #- LANGUAGE=EN
        volumes:
            - /path/to/store/the/data:/app/data # CHANGE THE LEFT PART
        image: dgongut/intrubot:latest
        container_name: intrubot
        restart: always
        network_mode: host
```

## Notes

- `network_mode: host` is **required** (or `macvlan` networks, see [Several networks or VLANs](#several-networks-or-vlans)): ARP scanning only works when the container sees the local network directly. On Docker's bridge network it would only see other containers.
- Scanning uses raw sockets (the `NET_RAW` capability), which Docker grants by default. If you removed it with `cap_drop`, add it back with `cap_add: [NET_RAW]`.
- The device list is stored in `/app/data/devices.json`, so map that volume to keep it when the container is recreated.
- The image ships a `HEALTHCHECK`: the container turns *unhealthy* when the bot stops talking to Telegram.

## Several networks or VLANs

A single bot can watch several networks at once. Use `NETWORKS` instead of `IP_RANGE`, with one `name=range` entry per network separated by `;` and, optionally, `@interface`:

```yaml
- NETWORKS=Home=192.168.1.0/24; IoT=192.168.20.0/24@eth0.20; Guests=192.168.30.0/24
```

- Each network's range accepts the same as `IP_RANGE`: ranges, CIDR networks and single addresses separated by commas. An address cannot be in two networks, and all of them together cannot exceed 65536 addresses.
- Without `@interface`, the bot scans each address through the interface the routing table points to. Set `@interface` when that VLAN leg has no IP of its own on the machine.
- All networks are scanned at the same time, so adding networks barely makes the scan longer.

### Requirement: an interface on each VLAN

ARP **does not cross routers**. When nobody answers ARP on a network and, according to the routing table, it is only reachable through the router, the bot pings its addresses instead. It works without touching anything, within limits:

- No MAC comes back across the router, so those devices are identified by their IP: if DHCP gives one a new IP, it is reported as new. Their vendor is unknown too.
- Devices that ignore ping (sleeping phones, firewalled machines) are not seen.
- If nobody on that network answers ping either, the bot warns you that it cannot see it.

To see everything, with MACs, the container needs an interface inside that network. Once it has one, the devices it knew by IP switch to their MAC, keeping their names and without being reported again. There are two ways to give it those interfaces:

**1. `network_mode: host` and one subinterface per VLAN on the machine.** The switch port the server is plugged into must carry those VLANs tagged (trunk mode). On Linux, for example, for VLAN 20:

```bash
ip link add link eth0 name eth0.20 type vlan id 20
ip addr add 192.168.20.5/24 dev eth0.20
ip link set eth0.20 up
```

This does not survive a reboot: make it persistent with your system's network tool (netplan, `/etc/network/interfaces`, NetworkManager…). On Unraid, enabling VLANs in *Settings → Network Settings* is enough: it creates `br0.20` and the like.

**2. One Docker `macvlan` network per VLAN**, without `network_mode: host` and without touching the machine. Docker creates the `eth0.20` subinterface if it does not exist. Give the container an IP outside your DHCP range:

```yaml
services:
    intrubot:
        environment:
            - TELEGRAM_TOKEN=
            - TELEGRAM_ADMIN=
            - TZ=Europe/Madrid
            - NETWORKS=Home=192.168.1.0/24; IoT=192.168.20.0/24
        volumes:
            - /path/to/store/the/data:/app/data
        image: dgongut/intrubot:latest
        container_name: intrubot
        restart: always
        networks:
            home:
                ipv4_address: 192.168.1.250
            iot:
                ipv4_address: 192.168.20.250

networks:
    home:
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
> With `macvlan` the machine running Docker cannot be reached from its own containers (a macvlan limitation), so that machine will not show up in the list.

### How several networks look in the bot

- The `/start` panel shows each network with its known and connected devices, and flags the ones whose last scan failed.
- `/list` starts by asking which network you want to see, or all of them.
- Alerts and device details show their network.
- **🔔 Alerts per network** (in the panel) mutes or unmutes the new device alerts of each network. Handy for the guest network, usually a parade of private MACs. A muted network is still scanned and its devices stay in the list. The setting is stored in `/app/data`.
- The same device on two networks counts as two: routers usually answer with the same MAC on every VLAN, and your laptop suddenly showing up on the IoT network is something you want to know.
- If you rename a network in `NETWORKS`, or switch from `IP_RANGE` to `NETWORKS`, each device moves to the network holding its IP, keeping its name and without being reported again.

### Upgrading from 1.x

2.0 is a full rewrite. Keep the same `/app/data` volume and the bot migrates your `known_devices.json` by itself (renaming it to `known_devices.json.bak`):

- Devices it already knew are **not** reported as new, and they get back the name you gave them as soon as they show up in a scan.
- The `/delete`, `/deleteall` and `/rename` commands are gone: everything is done with buttons from `/list`.
- **`tty: true` is no longer needed.** Up to 1.x the compose carried it so the bot's logs showed up in `docker logs`; from 2.0 the image writes them straight away without it. You can remove it, or leave it: it does no harm.
- `IP_RANGE` and `HOURS_BETWEEN_SCANS` work as before. `IP_RANGE` now also accepts CIDR networks and several comma separated entries, and if you have several VLANs you can move to `NETWORKS`.

## Developers only

### Running local code

To run it locally and try code changes, rename `.env-example` to `.env` and fill in the values it needs.
Use a `TELEGRAM_TOKEN` and `TELEGRAM_ADMIN` that are valid and different from your normal deployment.

Start it (the code reloads by itself on save thanks to `watchmedo`):

```bash
docker compose -f docker-compose.local.yaml up -d --build --force-recreate
```

Stop it:

```bash
docker compose -f docker-compose.local.yaml down --rmi all
```
