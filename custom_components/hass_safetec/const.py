from .device_config import conf_pontos
from .device_config import conf_trio
from .device_config import conf_safetech
from .device_config import conf_safetech_v4
from .device_config import conf_neosoft

DOMAIN = "hass_safetec"
CONF_IP_ADDRESS = "ip_address"
CONF_DEVICE_NAME = "device_name"
CONF_MAKE = "make"
CONF_FETCH_INTERVAL = "fetch_interval"
CONF_PORT = "port"
DEFAULT_PORT = 5333

MAKES = {
    "Safetec": conf_pontos,
    "SYR Trio": conf_trio,
    "SYR SafeTech+": conf_safetech,
    "SYR SafeTech+ (Old firmware)": conf_safetech_v4,
    "SYR NeoSoft": conf_neosoft,
}
