import scapy.all as scapy
import telebot
import time
import json
import os
import sys
import threading
import socket
from datetime import datetime
from config import *
from ipaddress import ip_address

VERSION = "0.9.0"

def debug(message):
    print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - DEBUG: {message}')

def error(message):
    print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - ERROR: {message}')

def warning(message):
    print(f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - WARNING: {message}')

def load_locale(locale):
    with open(f"/app/locale/{locale}.json", "r", encoding="utf-8") as file:
        return json.load(file)

def get_text(key, *args):
    messages = load_locale(LANGUAGE.lower())
    if key in messages:
        translated_text = messages[key]
    else:
        messages_en = load_locale("en")
        if key in messages_en:
            warning(f"key ['{key}'] is not in locale {LANGUAGE}")
            translated_text = messages_en[key]
        else:
            error(f"key ['{key}'] is not in locale {LANGUAGE} or EN")
            return f"key ['{key}'] is not in locale {LANGUAGE} or EN"

    for i, arg in enumerate(args, start=1):
        placeholder = f"${i}"
        translated_text = translated_text.replace(placeholder, str(arg))

    return translated_text

# Comprobación inicial de variables
if "abc" == TELEGRAM_TOKEN:
    error(get_text("error_bot_token"))
    sys.exit(1)

if "abc" == TELEGRAM_ADMIN:
    error(get_text("error_bot_telegram_admin"))
    sys.exit(1)

if str(ANONYMOUS_USER_ID) in str(TELEGRAM_ADMIN).split(','):
    error(get_text("error_bot_telegram_admin_anonymous"))
    sys.exit(1)

if "abc" == TELEGRAM_GROUP:
    if len(str(TELEGRAM_ADMIN).split(',')) > 1:
        error(get_text("error_multiple_admin_only_with_group"))
        sys.exit(1)
    TELEGRAM_GROUP = TELEGRAM_ADMIN

try:
    TELEGRAM_THREAD = int(TELEGRAM_THREAD)
except:
    error(get_text("error_bot_telegram_thread", TELEGRAM_THREAD))
    sys.exit(1)

if "abc" == IP_RANGE:
    error(get_text("error_ip_range"))
    sys.exit(1)

# Inicializa el bot de Telegram
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Función para cargar dispositivos conocidos desde un archivo JSON
def load_known_devices():
    if os.path.exists(FULL_KNOWN_DEVICES_PATH):
        with open(FULL_KNOWN_DEVICES_PATH, 'r') as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    return data  # Retorna el diccionario IP -> Nombre
                else:
                    error("El archivo JSON no tiene el formato correcto.")
            except json.JSONDecodeError:
                error("Error al decodificar el archivo JSON.")
    return {}

# Cargamos los dispositivos conocidos al iniciar el script
known_devices = load_known_devices()

def save_known_devices():
    with open(FULL_KNOWN_DEVICES_PATH, 'w') as f:
        json.dump(known_devices, f, indent=4, sort_keys=False)

# Función para obtener el nombre del dispositivo a partir de su IP
def get_device_name(ip):
    try:
        device_name = socket.gethostbyaddr(ip)
        return device_name[0]  # Devuelve el nombre de host
    except socket.herror:
        return get_text("unknown")  # No se pudo obtener el nombre de host

# Función para escanear una IP
def scan_ip(ip):
    global known_devices
    arp_request = scapy.ARP(pdst=str(ip))
    broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
    arp_request_broadcast = broadcast / arp_request
    answered_list = scapy.srp(arp_request_broadcast, timeout=1, verbose=False)[0]

    for element in answered_list:
        device_ip = element[1].psrc

        # Obtener el nombre del dispositivo
        device_name = get_device_name(device_ip)
        if device_name == device_ip:
            device_name = get_text("unknown")

        device_name = sanitize_name(device_name)
        # Si es un dispositivo nuevo, envía una notificación
        if device_ip not in known_devices:
            known_devices[device_ip] = device_name
            known_devices = dict(sorted(
                known_devices.items(),
                key=lambda item: int(ip_address(item[0])) # Ordenamos los valores antes de guardarlos
            ))
            if device_name == get_text("unknown"):
                send_message(message=get_text("new_device_detected_without_name", device_ip))
            else:
                send_message(message=get_text("new_device_detected", device_ip, device_name))
            save_known_devices()  # Guardamos el nuevo dispositivo en el archivo JSON

# Función para dividir el rango de IPs y escanear cada una
def scan_network(ip_range):
    try:
        # Dividir el rango por el guion
        start_ip_str, end_ip_str = ip_range.split('-')

        # Convertir las direcciones IP a objetos ip_address
        start_ip = ip_address(start_ip_str)
        end_ip = ip_address(end_ip_str)

        # Iteramos sobre cada IP en el rango
        for ip in range(int(start_ip), int(end_ip) + 1):
            scan_ip(ip_address(ip))
    except ValueError as e:
        error(f"Error al procesar el rango de IPs: {e}")

@bot.message_handler(commands=["start", "list", "deleteall", "delete", "rename", "version", "donate"])
def command_controller(message):
    userId = message.from_user.id
    comando = message.text.split(' ', 1)[0]
    
    # Verificación de administrador
    if not is_admin(userId):
        warning(get_text("warning_not_admin", userId, message.from_user.username))
        send_message(chat_id=userId, message=get_text("user_not_admin"))
        return

    # Comando /start
    if comando in ('/start', f'/start@{bot.get_me().username}'):
        texto_inicial = get_text("menu")
        send_message(message=texto_inicial)

    # Comando /list
    elif comando in ('/list', f'/list@{bot.get_me().username}'):
        if known_devices:
            device_list = "\n".join(
                [f" · `{ip}` | `{name}`" if name != get_text("unknown") else f" · `{ip}`" for ip, name in known_devices.items()]
            )
            send_message(message=get_text("known_devices", device_list))
        else:
            send_message(message=get_text("not_known_devices"))

    # Comando /deleteall
    elif comando in ('/deleteall', f'/deleteall@{bot.get_me().username}'):
        known_devices.clear()
        save_known_devices()  # Guardamos la lista vacía en el archivo JSON
        send_message(message=get_text("known_devices_deleted"))

    # Comando /delete
    elif comando in ('/delete', f'/delete@{bot.get_me().username}'):
        try:
            # Extraer la IP a borrar del mensaje
            ip_to_remove = message.text.split()[1]
            if ip_to_remove in known_devices:
                del known_devices[ip_to_remove]
                save_known_devices()
                send_message(message=get_text("device_deleted", ip_to_remove))
            else:
                send_message(message=get_text("unknown_device", ip_to_rename))
        except IndexError:
            send_message(message=get_text("error_delete_not_valid_ip"))

    # Comando /rename
    elif comando in ('/rename', f'/rename@{bot.get_me().username}'):
        debug("rename")
        try:
            # Extraer la IP y el nuevo nombre del mensaje
            _, ip_to_rename, new_name = message.text.split(maxsplit=2)
            debug(ip_to_rename)
            debug(new_name)

            # Validar que el nombre no contenga comillas ni llaves
            if '"' in new_name or '{' in new_name or '}' in new_name:
                raise ValueError

            # Verificar que la IP existe en el mapa de dispositivos conocidos
            if ip_to_rename in known_devices:
                # Actualizar el nombre en el mapa
                known_devices[ip_to_rename] = new_name

                # Guardar los cambios en el archivo JSON
                save_known_devices()

                # Confirmar que el cambio se realizó correctamente
                send_message(message=get_text("device_renamed", ip_to_rename, new_name))
            else:
                send_message(message=get_text("unknown_device", ip_to_rename))

        except ValueError:
            # Si el número de argumentos no es correcto, se devuelve un mensaje de error
            send_message(message=get_text("error_rename_invalid_format"))

    # Comando /version
    elif comando in ('/version', f'/version@{bot.get_me().username}'):
        version = get_text("version", VERSION)
        send_message(message=version)

    # Comando /donate
    elif comando in ('/donate', f'/donate@{bot.get_me().username}'):
        donate = get_text("donate")
        send_message(message=donate)

# Monitorea la red continuamente en un ciclo separado
def monitor_network():    
    while True:
        try:
            scan_network(IP_RANGE)
        except Exception as e:
            error(get_text("error_scanning_network", e))
        time.sleep(60)  # Escanea la red cada 60 segundos

def sanitize_name(text):
    special_chars = {
        '_': ' ', '-': ' ', '{': ' ', '}': ' ', '\"': ' '
    }
    for char, replacement in special_chars.items():
        text = text.replace(char, replacement)
    return text

def send_message(chat_id=TELEGRAM_GROUP, message=None, reply_markup=None, parse_mode="markdown", disable_web_page_preview=True):
    try:
        if TELEGRAM_THREAD == 1:
            return bot.send_message(chat_id, message, parse_mode=parse_mode, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
        else:
            return bot.send_message(chat_id, message, parse_mode=parse_mode, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview, message_thread_id=TELEGRAM_THREAD)
    except Exception as e:
        error(get_text("error_sending_message", chat_id, message, e))
        pass

def is_admin(userId):
    return str(userId) in str(TELEGRAM_ADMIN).split(',')

if __name__ == '__main__':
    debug(get_text("debug_starting_bot", VERSION))
    network_thread = threading.Thread(target=monitor_network)
    network_thread.start()
    bot.set_my_commands([
        telebot.types.BotCommand("/start", get_text("menu_start")),
        telebot.types.BotCommand("/list", get_text("menu_list")),
        telebot.types.BotCommand("/delete", get_text("menu_delete")),
        telebot.types.BotCommand("/deleteall", get_text("menu_deleteall")),
        telebot.types.BotCommand("/rename", get_text("menu_rename")),
        telebot.types.BotCommand("/version", get_text("menu_version")),
        telebot.types.BotCommand("/donate", get_text("menu_donate"))
        ])
    starting_message = f"🫡 *IntruBot\n🟢 {get_text('active')}*"
    starting_message += f"\n_⚙️ v{VERSION}_"
    send_message(message=starting_message)
    bot.infinity_polling(timeout=60)