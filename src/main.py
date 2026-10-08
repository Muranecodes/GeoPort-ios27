import locale
import math
import os
import queue
import re
import sys
import time
try:
    import pyuac
except ImportError:
    if sys.platform == 'win32':
        raise
    pyuac = None
import psutil
import signal
import socket
import random
import asyncio
import argparse
import requests
import threading
import webbrowser
import subprocess
import pycountry
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from urllib3.exceptions import InsecureRequestWarning, ConnectionError
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
from contextlib import asynccontextmanager

from pymobiledevice3.usbmux import list_devices
from pymobiledevice3.cli.mounter import auto_mount
from pymobiledevice3.lockdown import create_using_usbmux, create_using_tcp, get_mobdev2_lockdowns
from pymobiledevice3.services.amfi import AmfiService
from pymobiledevice3.exceptions import DeviceHasPasscodeSetError, NoDeviceConnectedError
from pymobiledevice3.services.dvt.dvt_secure_socket_proxy import DvtSecureSocketProxyService
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
from pymobiledevice3.remote.utils import stop_remoted_if_required, resume_remoted_if_required, get_rsds
from pymobiledevice3.remote.tunnel_service import create_core_device_tunnel_service_using_rsd, get_remote_pairing_tunnel_services, start_tunnel, create_core_device_tunnel_service_using_remotepairing, get_core_device_tunnel_services, CoreDeviceTunnelProxy
#from pymobiledevice3.cli.remote import install_driver_if_required
from pymobiledevice3.osu.os_utils import get_os_utils
from pymobiledevice3.bonjour import DEFAULT_BONJOUR_TIMEOUT, browse_mobdev2
from pymobiledevice3.pair_records import get_local_pairing_record, get_remote_pairing_record_filename, get_preferred_pair_record
from pymobiledevice3.common import get_home_folder
try:
    from pymobiledevice3.cli.remote import cli_install_wetest_drivers
except ImportError:
    cli_install_wetest_drivers = None

from pymobiledevice3.lockdown import LockdownClient
from pymobiledevice3.lockdown_service_provider import LockdownServiceProvider
from pymobiledevice3.remote.common import TunnelProtocol
from modern_location_client import ModernLocationController
from geometry import (
    calculate_step,
    get_bearing_for_direction,
    calculate_bearing,
    calculate_polyline_distance,
    interpolate_polyline,
    validate_speed,
)
from location_sink import LocationSink, DvtLocationSink, MockLocationSink
from navigation_engine import NavigationController

#========= Arg Parser ========
# Parse command-line arguments
parser = argparse.ArgumentParser()
parser.add_argument('--no-browser', action='store_true', help='Skip auto opening the browser')
parser.add_argument('--port', type=int, help='Specify port number to listen on for web browser requests')
parser.add_argument('--wifihost', type=str, help='Specify the wifi IP address to connect to')
parser.add_argument('--udid', type=str, help='Specify the device udid to target')
args, _ = parser.parse_known_args()
#========= Arg Parser ========

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
OSUTILS = get_os_utils()


import logging


# Get or create a logger instance named "GeoPort"
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# Create a logger named "GeoPort"
logger = logging.getLogger("GeoPort")
logging.getLogger("urllib3").setLevel(logging.WARNING)

logging.getLogger('werkzeug').disabled = True
#log.disabled = True

app = Flask(__name__)

# Define constants
# Get the home directory of the current user
home_dir = os.path.expanduser("~")
is_windows = sys.platform == 'win32'
base_directory = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(sys.argv[0])))
flask_port = 54321
api_url = "https://projectzerothree.info/api.php?format=json"
api_data = None
user_locale = None
location = None
rsd_data = None
rsd_host = None
rsd_port = None
rsd_data_map = {}
wifi_address = None
wifihost = args.wifihost
wifi_port = None
connection_type = None
udid = None
lockdown = None
ios_version = None
pair_record = None
error_message = None
sudo_message = ""
captured_output = None
GITHUB_REPO = 'Muranecodes/GeoPort-ios27'
CURRENT_VERSION_FILE = 'CURRENT_VERSION'
APP_VERSION_NUMBER = "2.3.3"
APP_VERSION_TYPE = "fuel"
terminate_tunnel_thread = False
location_stop_event = None
timeout = DEFAULT_BONJOUR_TIMEOUT
bundled_bridge = (Path(sys.executable).resolve().parents[1] / 'Resources' /
                  'modern-location-bridge') if getattr(sys, 'frozen', False) else None
modern_location = ModernLocationController(
    python_executable=os.environ.get('GEOPORT_MODERN_PMD3_PYTHON'),
    bridge_executable=os.environ.get('GEOPORT_MODERN_BRIDGE_EXECUTABLE') or
    (str(bundled_bridge) if bundled_bridge and bundled_bridge.is_file() else None),
)

# Get the current platform using sys.platform
current_platform = sys.platform

# Map the platform names to standard values
platform = {
    'win32': 'Windows',
    'linux': 'Linux',
    'darwin': 'MacOS',
}.get(current_platform, 'Unknown')

# Check if running as sudo
if current_platform == "darwin" and not modern_location.enabled:
    if os.geteuid() != 0:
        logger.error("*********************** WARNING ***********************")
        logger.error("Not running as Sudo, this probably isn't going to work")
        logger.error("*********************** WARNING ***********************")
        sudo_message = "Not running as Sudo, this probably isn't going to work"
    else:
        logger.info("Running as Sudo")
        sudo_message = ""



def fetch_api_data(api_url):
    global api_data
    try:
        api_data = requests.get(api_url, verify=False).json()
        return api_data
    except requests.exceptions.RequestException as e:
        logger.error(f"Error: {e}")
        logger.error(f"API is unreachable or there was an error during the request")
        logger.error("Sorry - Fuel data is not available")
        return None
    except ConnectionError as e:
        logger.error("Error: Name resolution failed.")
        logger.error("Please check your internet connection or the correctness of the API URL.")
        logger.error("Sorry - Fuel data is not available")
        logger.error(f"Details: {e}")
        return None

def create_geoport_folder():
    # Define the path to the GeoPort folder
    geoport_folder = os.path.join(home_dir, 'GeoPort')

    # Check if the GeoPort folder exists, create it if not
    if not os.path.exists(geoport_folder):
        os.makedirs(geoport_folder)
        logger.info(f"GeoPort Home: {geoport_folder}")
        logger.info("GeoPort folder created successfully")

    # Set permissions for the GeoPort folder
    if current_platform == 'win32':
        # Windows permissions (read/write for everyone)
        os.system(f"icacls {geoport_folder} /grant Everyone:(OI)(CI)F")
        logger.info("Permissions set for GeoPort folder on Windows")
    else:  # Linux and MacOS
        # POSIX permissions (read/write for everyone)
        os.chmod(geoport_folder, 0o777)
        logger.info("Permissions set for GeoPort folder on MacOS")



# Define the function to be executed in the thread
def run_tunnel(service_provider):

    try:
        asyncio.run(start_quic_tunnel(service_provider))

        logger.info("run_tun completed")
        sys.exit(0)

    except Exception as e:
        error_message = str(e)

        # Handle the exception, such as logging it or returning an error response
        with app.app_context():
            return jsonify({'error': error_message})

    #return

# Define a function to start the tunnel thread
def start_tunnel_thread(service_provider):
    global terminate_tunnel_thread  # Declare the global variable
    terminate_tunnel_thread = False  # Set the value of the global variable
    thread = threading.Thread(target=run_tunnel, args=(service_provider,))
    thread.start()
    return

async def start_quic_tunnel(service_provider: RemoteServiceDiscoveryService) -> None:

    logger.warning("Start USB QUIC tunnel")

    global terminate_tunnel_thread
    stop_remoted_if_required()
    #install_driver_if_required()

    # if sys.platform == 'win32':
    #     logger.info("Windows System - Driver Check Required")
    #     if version_check(ios_version):
    #         logger.warning("Installing WeTest Driver - QUIC Tunnel")
    #         cli_install_wetest_drivers()

    service = await create_core_device_tunnel_service_using_rsd(service_provider, autopair=True)

    async with service.start_quic_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f"QUIC Address: {tunnel_result.address}")
        logger.info(f"QUIC Port: {tunnel_result.port}")
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)


        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)


# Define the function to be executed in the thread
def run_tcp_tunnel(service_provider):

    try:
        asyncio.run(start_tcp_tunnel(service_provider))

        logger.info("run_tun completed")
        sys.exit(0)

    except Exception as e:
        error_message = str(e)

        # Handle the exception, such as logging it or returning an error response
        with app.app_context():
            return jsonify({'error': error_message})

    #return

# Define a function to start the tunnel thread
def start_tcp_tunnel_thread(service_provider):
    global terminate_tunnel_thread  # Declare the global variable
    terminate_tunnel_thread = False  # Set the value of the global variable
    thread = threading.Thread(target=run_tcp_tunnel, args=(service_provider,))
    thread.start()
    return

async def start_tcp_tunnel(service_provider: CoreDeviceTunnelProxy) -> None:

    logger.warning("Start USB TCP tunnel")

    global terminate_tunnel_thread
    stop_remoted_if_required()
    #install_driver_if_required()

    #service = await create_core_device_tunnel_service_using_rsd(service_provider, autopair=True)

    lockdown = create_using_usbmux(udid, autopair=True)
    #print("Lockdown for Windows: ", lockdown)
    service = CoreDeviceTunnelProxy(lockdown)
    #asyncio.run(tunnel_task(service, secrets=None, protocol=TunnelProtocol.TCP), debug=True)
    async with service.start_tcp_tunnel() as tunnel_result:
        logger.info(f"TCP Address: {tunnel_result.address}")
        logger.info(f"TCP Port: {tunnel_result.port}")
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)

        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)





def is_major_version_17_or_greater(version_string):
    # Check if the major version in the given version string is 17 or greater.
    try:
        major_version = int(version_string.split('.')[0])
        return major_version >= 17
    except (ValueError, IndexError):
        # Handle invalid version string or missing major version
        return False

def is_major_version_less_than_16(version_string):
    # Check if the major version in the given version string is 17 or greater.
    try:
        major_version = int(version_string.split('.')[0])
        return major_version < 16
    except (ValueError, IndexError):
        # Handle invalid version string or missing major version
        logger.error(f"Error: {ValueError}, {IndexError}")
        return False


def version_check(version_string):
    try:
        # Split the version string into major and minor version parts
        version_parts = version_string.split('.')

        # Extract the major and minor version parts
        major_version = int(version_parts[0])
        minor_version = int(version_parts[1]) if len(version_parts) > 1 else 0

        # Check if the version string satisfies the condition
        if major_version == 17 and 0 <= minor_version <= 3:
            if sys.platform == 'win32':
                logger.info("Checking Windows Driver requirement")
                logger.info("Driver is required")
            return True
        else:
            if sys.platform == 'win32':
                logger.info("Driver is not required")
                return False
            logger.info("MacOS - pass")
            return False



    except (ValueError, IndexError) as e:
        logger.error(f"Driver check error: {e}")
        # Handle invalid version string or missing major/minor version
        return False

def get_user_country():
    global user_locale
    try:
        # Attempt to get the user's country using locale and pycountry
        user_locale, _ = locale.getlocale()

        if user_locale is None:
            logger.warning("User locale is None. Defaulting to IP geolocation service.")
            return get_country_from_ip()

        country_code = user_locale.split('_')[-1]
        country = pycountry.countries.get(alpha_2=country_code)
        country_name = country.name if country else None

        # If country_name is None, try IP geolocation service as a fallback
        if country_name is None:
            logger.warning("Failed to retrieve country name using locale. Using IP geolocation service.")
            return get_country_from_ip()
        else:
            return country_name

    except Exception as e:
        logger.error(f"Error getting user country: {e}")
        return None


def get_country_from_ip():
    try:
        response = requests.get("http://ip-api.com/json/")
        if response.status_code == 200:
            data = response.json()
            country_name = data.get("country")
            if country_name:
                return country_name
            else:
                logger.warning("Failed to retrieve country name from IP geolocation service.")
        else:
            logger.error(f"Error: Unable to retrieve data. Status code: {response.status_code}")
            logger.warning("Setting to default country")
            country_name = "Spain"
        return country_name
    except Exception as e:
        logger.error(f"Error getting country from IP geolocation service: {e}")
        country_name = "Spain"
        return country_name
def get_devices_with_retry(max_attempts=10):
    if sys.platform == 'win32':
        logger.info(f"iOS Version: {ios_version}")
        if version_check(ios_version):
            logger.info("Windows Driver Install Required")
            if cli_install_wetest_drivers is None:
                raise RuntimeError("Bundled pymobiledevice3 does not support driver installation")
            cli_install_wetest_drivers()
    for attempt in range(1, max_attempts + 1):
        try:
            devices = asyncio.run(get_rsds(timeout))
            #dev1 = asyncio.run(get_rsds(timeout))
            #devices = asyncio.run(get_core_device_tunnel_services(timeout))
            #print("devices: ", devices)
            #print("dev1: ", dev1)
            if devices:
                return devices  # Return devices if the list is not empty
            else:
                logger.warning(f"Attempt {attempt}: No devices found")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Error occurred - {e}")
        time.sleep(1)  # Add a delay between attempts if needed
    raise RuntimeError("No devices found after multiple attempts.\n Ensure you are running GeoPort as sudo / Administrator")


def get_wifi_with_retry(max_attempts=10):
    global udid, wifi_address, wifi_port

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info("Discovering Wifi Devices - This may take a while...")
            devices = asyncio.run(get_remote_pairing_tunnel_services(timeout))
            #devices = get_remote_pairing_tunnel_services(timeout)



            if devices:
                if udid:
                    for device in devices:
                        if device.remote_identifier == udid:
                            logger.info(f"Device found with udid: {udid}.")
                            wifi_address = device.hostname
                            wifi_port = device.port
                            return device
                else:
                    return devices
            else:
                logger.warning(f"Attempt {attempt}: No devices found")
        except Exception as e:
            logger.warning(f"Attempt {attempt}: Error occurred - {e}")

        # Add a delay between attempts
        time.sleep(1)

    raise RuntimeError("No devices found after multiple attempts. Please see the FAQ.")
@app.route('/stop_tunnel', methods=['POST'])
def stop_tunnel_thread():
    global terminate_tunnel_thread
    logger.info("stop tunnel thread")
    # Set the terminate flag to True to stop the thread
    terminate_tunnel_thread = True
    return jsonify("Tunnel stopped")

@app.route('/api/data/<fuel_type>')
def get_fuel_type_data(fuel_type):
    selected_fuel_region = request.args.get('region', 'All')

    if api_data is None:
        logger.error("API Data is none, Fuel data is not available")
        return jsonify({}), 500  # Return an empty response with status code 500 (Internal Server Error)

    all_region_data = next(
        (region['prices'] for region in api_data['regions'] if region['region'] == selected_fuel_region), [])

    selected_data = next((entry for entry in all_region_data if entry['type'] == fuel_type), None)

    return jsonify(selected_data)


@app.route('/api/fuel_types')
def get_fuel_types():
    selected_fuel_region = request.args.get('region', 'All')

    if api_data is None:
        logger.error("API Data is none, sorry - Fuel data is not available")
        return jsonify({}), 500  # Return an empty response with status code 500 (Internal Server Error)

    all_region_data = next(
        (region['prices'] for region in api_data['regions'] if region['region'] == selected_fuel_region), [])

    fuel_types = set(entry['type'] for entry in all_region_data)

    return jsonify(list(fuel_types))


@app.route('/update_location', methods=['POST'])
def update_location():
    # Use 'request' to get the JSON data from the client
    data = request.get_json()

    # Convert latitude and longitude to float values
    lat = float(data['lat'])
    lng = float(data['lng'])

    global location
    location = f"{lat} {lng}"
    return 'Location updated successfully'

def check_pair_record(udid):
    global pair_record
    logger.info(f"Connection Type: {connection_type}")
    logger.info("Enable Developer Mode")

    home = get_home_folder()
    logger.info(f"Pair Record Home: {home}")

    filename = get_remote_pairing_record_filename(udid)
    logger.info(f"Pair Record File: {filename}")

    # pair_record = get_local_pairing_record(filename, home)
    pair_record = get_preferred_pair_record(udid, home)
    #logger.info(f"Pair Record: {pair_record}")
    return pair_record

def check_developer_mode(udid, connection_type):
    try:

        logger.warning(f"Check Developer Mode")

        lockdown = create_using_usbmux(udid, connection_type=connection_type, autopair=True)

        result = lockdown.developer_mode_status
        logger.info(f"Developer Mode Check result:  {result}")

        # Check if developer mode is enabled
        if result:
            logger.info("Developer Mode is true")
            return True
        else:
            logger.warning("Developer Mode is false")
            return False

    except subprocess.CalledProcessError as e:
        return False


def enable_developer_mode(udid, connection_type):
    check_pair_record(udid)


    logger.info(f"Connection Type: {connection_type}")
    logger.info("Enable Developer Mode")

    home = get_home_folder()
    logger.info(f"Pair Record Home: {home}")
    #
    # filename = get_remote_pairing_record_filename(udid)
    # logger.info(f"Pair Record File: {filename}")
    #
    # pair_record = get_local_pairing_record(filename, home)
    # logger.info(f"Pair Record: {pair_record}")
    if connection_type == "Network":
        if pair_record is None:
            logger.error("Network: No Pair Record Found. Please use a USB cable first to create a pair record")
            return False, "No Pair Record Found. Please use a USB cable first to create a pair record"
    else:
        logger.error("No Pair Record Found. USB cable detected. Creating a pair record")
        pass
        #return False, "No Pair Record Found. Please use a USB cable first to create a pair record"

    lockdown = create_using_usbmux(
        udid,
        connection_type=connection_type,
        autopair=True,
        pairing_records_cache_folder=home)


    try:

        AmfiService(lockdown).enable_developer_mode()
        logger.info("Enable complete, mount developer image...")
        mount_developer_image()

    except DeviceHasPasscodeSetError:
        error_message = "Error: Device has a passcode set\n \n Please temporarily remove the passcode and run GeoPort again to enable Developer Mode \n \n Go to \"Settings - Face ID & Passcode\"\n"
        logger.error(f"{error_message}")
        return False, error_message

    # except Exception as e:  # Catch any other exception
    #     logger.error(f"An error occurred: {str(e)}")
    #     return False, f"An error occurred: {str(e)}"

    return True, None




@app.route('/enable_developer_mode', methods=['POST'])
def enable_developer_mode_route():
    try:
        global udid
        data = request.get_json()

        # Extract the udid from the request
        udid = data.get('udid', None)

        success, error_message = enable_developer_mode(udid, connection_type)

        if success:
            # Return a success response with any additional data needed
            return jsonify({'success': True, 'udid': udid})
        else:
            return jsonify({'error': error_message})

    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message})



@app.route('/connect_device', methods=['POST'])
def connect_device():
    global udid, connection_type, ios_version, rsd_data, rsd_host, rsd_port, wifi_address

    data = request.get_json()
    logger.info(f"Connect Device Data: {data}")

    # Extract the udid from the request
    udid = data.get('udid', None)
    ios_version = data.get('ios_version')

    connection_type = data.get('connType')



    if udid in rsd_data_map:
        if connection_type in rsd_data_map[udid]:
            logger.info(f"Connect_Device Map - Looking for {udid} in {connection_type}")
            rsd_data = rsd_data_map[udid][connection_type]

            rsd_host = rsd_data['host']
            rsd_port = rsd_data['port']

            logger.info(f"RSD in udid mapping is: {rsd_data}")
            logger.info("RSD already created. Reusing connection")
            logger.info(f"RSD Data: {rsd_data}")
            if modern_location.enabled and ios_version and ios_version.startswith('27.'):
                return jsonify({'rsd_data': [rsd_host, rsd_port]})
            return jsonify({'rsd_data': rsd_data})

        # If no matching entry found for the udid and desired connection type
        logger.info(f"No matching RSD entry found for udid: {udid} and connection type: {connection_type}")


    # Check if developer mode is enabled, and enable it if not
    #logger.info("Must be iOS17")
    if not check_developer_mode(udid, connection_type):
        # Display modal to inform the user and give options
        return jsonify({'developer_mode_required': 'True'})

    if modern_location.enabled and str(data.get('ios_version', '')).startswith('27.'):
        if connection_type != 'USB':
            return jsonify({'error': 'iOS 27 bridge requires USB'}), 400
        ios_version = data['ios_version']
        rsd_host, rsd_port = 'modern-dvt', 'auto'
        rsd_data = [rsd_host, rsd_port]
        rsd_data_map.setdefault(udid, {})[connection_type] = {
            'host': rsd_host, 'port': rsd_port}
        return jsonify({'rsd_data': rsd_data})

    if connection_type == "USB":
        return connect_usb(data)

    elif connection_type == "Network":
        check_pair_record(udid)

        if pair_record is None:
            logger.error("No Pair Record Found. Please use a USB Cable to create one")
            return jsonify({"Error": "No Pair Record Found"})
        result = connect_wifi(data)
        #result = await connect_wifi(data)
        #return await connect_wifi(data)
        return result

    elif connection_type == "Manual":
        check_pair_record(udid)

        if pair_record is None:
            logger.error("No Pair Record Found. Please use a USB Cable to create one")
            return jsonify({"Error": "No Pair Record Found"})
        result = connect_wifi(data)
        # result = await connect_wifi(data)
        # return await connect_wifi(data)
        return result
    else:
        logger.error("Error: No matching connection type")
        return jsonify({"Error": "No matching connection type"})

def check_rsd_data():
    max_attempts = 30
    attempts = 0
    while attempts < max_attempts:
        if rsd_host is not None and rsd_port is not None:
            return True  # Data is available
        time.sleep(1)
        attempts += 1
    return False  # Data is still None after all attempts

def connect_usb(data):
    try:
        global udid, connection_type
        global ios_version
        global rsd_data, rsd_host, rsd_port

        logger.info(f"USB data: {data}")

        # Extract the udid from the request
        udid = data.get('udid', None)
        ios_version = data.get('ios_version')
        #ios_version = "17.0"
        connection_type = data.get('connType')
        rsd_host = None
        rsd_port = None

        if ios_version is not None and is_major_version_17_or_greater(ios_version):
            logger.info("iOS 17+ detected")


            logger.info(f"iOS Version: {ios_version}")
            if version_check(ios_version):
                if sys.platform == 'win32':
                    logger.warning("iOS is between 17.0 and 17.3.1, WHY?")
                    logger.warning("You should upgrade to 17.4+")
                    logger.error("We need to install a 3rd party driver for these versions")
                    logger.error("which may stop working at any time")
                    try:
                        devices = get_devices_with_retry()
                        logger.info(f"Devices: {devices}")
                        rsd = [device for device in devices if device.udid == udid]
                        if len(rsd) > 0:
                            rsd = rsd[0]
                        start_tunnel_thread(rsd)

                    except RuntimeError as e:
                        error_message = str(e)
                        logger.error(f"Error: {error_message}")
                        return jsonify({'error': 'No Devices Found'})
                else:
                    logger.warning("ios <17.4 on non-windows")
                    try:
                        devices = get_devices_with_retry()
                        logger.info(f"Devices: {devices}")
                        rsd = [device for device in devices if device.udid == udid]
                        if len(rsd) > 0:
                            rsd = rsd[0]
                        start_tunnel_thread(rsd)

                    except RuntimeError as e:
                        error_message = str(e)
                        logger.error(f"Error: {error_message}")
                        return jsonify({'error': 'No Devices Found'})

            else:
                global lockdown
                lockdown = create_using_usbmux(udid, autopair=True)
                logger.info(f"Create Lockdown {lockdown}")
                start_tcp_tunnel_thread(lockdown)


            #time.sleep(3)
            if not check_rsd_data():
                logger.error("RSD Data is None, Perhaps the tunnel isn't established")
            else:
                rsd_data = rsd_host, rsd_port
                logger.info(f"RSD Data: {rsd_data}")

            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}
            logger.info(f"Device Connection Map: {rsd_data_map}")
            return jsonify({'rsd_data': rsd_data})

        elif ios_version is not None and not is_major_version_17_or_greater(ios_version):
            rsd_data = ios_version, udid
            logger.info(f"RSD Data: {rsd_data}")

            # # Check if developer mode is enabled, and enable it if not
            # if not check_developer_mode(udid, connection_type):
            #     # Display modal to inform the user and give options
            #     return jsonify({'developer_mode_required': 'True'})

            # create LockdownServiceProvider
            #global lockdown
            lockdown = create_using_usbmux(udid, autopair=True)
            logger.info(f"Lockdown client = {lockdown}")
            #rsd_data = rsd_host, rsd_port
            rsd_host, rsd_port = rsd_data

            #rsd_data_map[udid] = rsd_data
            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}

            return jsonify({'message': 'iOS version less than 17', 'rsd_data': rsd_data})

        else:
            # Invalid ios_version
            return jsonify({'error': 'No iOS version present'})
    finally:
        logger.warning("Connect Device function completed")

def connect_wifi(data):
    try:
        global udid, wifi_address, connection_type, wifi_port
        global ios_version
        global rsd_data, rsd_host, rsd_port

        logger.info(f"Wifi data: {data}")

        # Extract the udid from the request
        udid = data.get('udid', None)
        ios_version = data.get('ios_version')
        #ios_version = "17.3.1"
        #wifi_address = data.get('wifiAddress')
        #logger.error(f"wifi address: {wifi_address}")
        connection_type = data.get('connType')

        if ios_version is not None and is_major_version_17_or_greater(ios_version):
            logger.info("iOS 17+ detected")

            if version_check(ios_version):
                try:
                    devices = get_wifi_with_retry()
                    #devices = "blah"
                    logger.info(f"Connect Wifi Devices: {devices}")
                    logger.info(f"Wifi Address:  {wifi_address}")
                except RuntimeError as e:
                    error_message = str(e)
                    logger.error(f"Error: {error_message}")
                    return jsonify({'error': 'No Devices Found'})


            rsd_host = None
            rsd_port = None

            # Run tun(devices) as a background task
            #asyncio.create_task(tun(devices))
            #await tun(devices)
            #start_wifi_tunnel_thread(devices)
            start_wifi_tunnel_thread()

            if not check_rsd_data():
                logger.error("RSD Data is None, Perhaps the tunnel isn't established")
            else:
                rsd_data = rsd_host, rsd_port
                logger.info(f"RSD Data: {rsd_data}")

            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}
            logger.info(f"Device Connection Map: {rsd_data_map}")
            return jsonify({'rsd_data': rsd_data})

        elif ios_version is not None and not is_major_version_17_or_greater(ios_version):
            rsd_data = ios_version, udid
            logger.info(f"RSD Data: {rsd_data}")

            # create LockdownServiceProvider
            global lockdown
            lockdown = create_using_usbmux(udid, connection_type=connection_type, autopair=True)
            #lockdown = create_using_tcp(wifi_address, udid)
            logger.info(f"Lockdown client = {lockdown}")

            rsd_data_map.setdefault(udid, {})[connection_type] = {"host": rsd_host, "port": rsd_port}

            return jsonify({'message': 'iOS version less than 17', 'rsd_data': rsd_data})

        else:
            # Invalid ios_version
            return jsonify({'error': 'No iOS version present'})
    finally:
        logger.warning("Connect Device function completed")




async def start_wifi_tcp_tunnel() -> None:

    logger.warning(f"Start Wifi TCP Tunnel")

    global terminate_tunnel_thread
    stop_remoted_if_required()
    #install_driver_if_required()

    # if sys.platform == 'win32':
    #     if is_driver_required:
    #         logger.warning("Installing WeTest Driver")
    #         cli_install_wetest_drivers()

    #service = await create_core_device_tunnel_service_using_remotepairing(udid, wifi_address, wifi_port)
    lockdown = create_using_usbmux(udid)
    service = CoreDeviceTunnelProxy(lockdown)

    async with service.start_tcp_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f'Identifier: {service.remote_identifier}')
        logger.info(f'Interface: {tunnel_result.interface}')
        logger.info(f'RSD Address: {tunnel_result.address}')
        logger.info(f'RSD Port: {tunnel_result.port}')
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)


        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)

async def start_wifi_quic_tunnel() -> None:

    logger.warning(f"Start Wifi QUIC Tunnel")

    global terminate_tunnel_thread
    stop_remoted_if_required()
    #install_driver_if_required()

    # if sys.platform == 'win32':
    #     if is_driver_required:
    #         logger.warning("Installing WeTest Driver")
    #         cli_install_wetest_drivers()
    #get_wifi_with_retry()
    service = await create_core_device_tunnel_service_using_remotepairing(udid, wifi_address, wifi_port)
    # lockdown = create_using_usbmux(udid)
    # service = CoreDeviceTunnelProxy(lockdown)

    async with service.start_quic_tunnel() as tunnel_result:
        resume_remoted_if_required()

        logger.info(f'Identifier: {service.remote_identifier}')
        logger.info(f'Interface: {tunnel_result.interface}')
        logger.info(f'RSD Address: {tunnel_result.address}')
        logger.info(f'RSD Port: {tunnel_result.port}')
        global rsd_port
        global rsd_host
        rsd_host = tunnel_result.address

        rsd_port = str(tunnel_result.port)


        while True:
            if terminate_tunnel_thread is True:
                return
            # wait user input while the asyncio tasks execute
            await asyncio.sleep(.5)

# Define a function to start the tunnel thread
def start_wifi_tunnel_thread():
    global terminate_tunnel_thread
    terminate_tunnel_thread = False  # Set the value of the global variable
    thread = threading.Thread(target=run_wifi_tunnel)
    thread.start()
    return

# Entry point for running the tunnel async function
def run_wifi_tunnel():
    try:
        if version_check(ios_version):
            asyncio.run(start_wifi_quic_tunnel())
        #TODO: or win32 / 17.0-17.3 special tunnel

        else:
            asyncio.run(start_wifi_tcp_tunnel())
        #await tun(devices)
    except Exception as e:
        logger.error(f"Error in run_wifi_tunnel: {e}")


@app.route('/mount_developer_image', methods=['POST'])
def mount_developer_image():
    try:

        global lockdown
        lockdown = create_using_usbmux(udid, autopair=True)
        logger.info(f"mount lockdown: {lockdown}")

        auto_mount(lockdown)

        return 'Developer image mounted successfully'
    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message})

async def set_location_thread(latitude, longitude, coord_queue, report_success, stop_event):
    try:
        global rsd_host, rsd_port, udid, ios_version, connection_type

        if udid in rsd_data_map:
            if connection_type in rsd_data_map[udid]:
                rsd_data = rsd_data_map[udid][connection_type]
                rsd_host = rsd_data['host']
                rsd_port = rsd_data['port']

                logger.info(f"RSD in udid mapping is: {rsd_data}")
                logger.info("RSD already created. Reusing connection")
                logger.info(f"RSD Data: {rsd_data}")


                if ios_version is not None and is_major_version_17_or_greater(ios_version):
                    if not rsd_host or not rsd_port:
                        raise RuntimeError("RSD tunnel is not ready")
                    async with RemoteServiceDiscoveryService((rsd_host, rsd_port)) as sp_rsd:
                        with DvtSecureSocketProxyService(sp_rsd) as dvt:
                            LocationSimulation(dvt).set(latitude, longitude)
                            report_success()
                            logger.warning("LocationSimulation accepted the set call")
                            while not stop_event.is_set():
                                try:
                                    item = coord_queue.get_nowait()
                                except queue.Empty:
                                    item = None
                                if item is not None:
                                    coords, ack_queue = item
                                    try:
                                        LocationSimulation(dvt).set(coords[0], coords[1])
                                        logger.debug("Persistent DVT streamed location to (%s, %s)", coords[0], coords[1])
                                        if ack_queue is not None:
                                            ack_queue.put_nowait(None)
                                    except Exception as exc:
                                        logger.exception("Error in persistent DVT stream update")
                                        if ack_queue is not None:
                                            ack_queue.put_nowait(exc)
                                        raise
                                await asyncio.sleep(0.05)


                elif ios_version is not None and not is_major_version_17_or_greater(ios_version):
                    with DvtSecureSocketProxyService(lockdown=lockdown) as dvt:
                        LocationSimulation(dvt).clear()
                        LocationSimulation(dvt).set(latitude, longitude)
                        report_success()
                        logger.warning("LocationSimulation accepted the set call")
                        while not stop_event.is_set():
                            try:
                                item = coord_queue.get_nowait()
                            except queue.Empty:
                                item = None
                            if item is not None:
                                coords, ack_queue = item
                                try:
                                    LocationSimulation(dvt).set(coords[0], coords[1])
                                    logger.debug("Persistent DVT streamed location to (%s, %s)", coords[0], coords[1])
                                    if ack_queue is not None:
                                        ack_queue.put_nowait(None)
                                except Exception as exc:
                                    logger.exception("Error in persistent DVT stream update")
                                    if ack_queue is not None:
                                        ack_queue.put_nowait(exc)
                                    raise
                            await asyncio.sleep(0.05)
                else:
                    raise RuntimeError("Device iOS version is unavailable")

                await asyncio.sleep(1)  # Adjust sleep time according to your requirements
            else:
                raise RuntimeError("Selected connection has no RSD session")
        else:
            raise RuntimeError("Selected device has no RSD session")

    except asyncio.CancelledError:
        raise
    except ConnectionResetError as cre:
        if "[Errno 54] Connection reset by peer" in str(cre):
            logger.error("The Set Location buffer is full. Try to 'Stop Location' to clear old connections")
        raise
    except Exception as e:
        logger.exception("Error setting location")
        raise


_dvt_thread = None
_dvt_coord_queue = None


# Function to start or stream to the set_location_thread
def start_set_location_thread(latitude, longitude):
    global location_stop_event, _dvt_thread, _dvt_coord_queue
    # Reuse active persistent DVT session if healthy
    if (
        _dvt_thread is not None
        and _dvt_thread.is_alive()
        and location_stop_event is not None
        and not location_stop_event.is_set()
        and _dvt_coord_queue is not None
    ):
        ack = queue.Queue(maxsize=1)
        _dvt_coord_queue.put(((latitude, longitude), ack))
        try:
            failure = ack.get(timeout=5.0)
            if failure is None:
                return
            logger.warning("Active DVT session coordinate update failed: %s; restarting session", failure)
        except queue.Empty:
            logger.warning("Active DVT session update timed out; restarting session")

    # Stop existing threads
    stop_set_location_thread()
    stop_event = threading.Event()
    location_stop_event = stop_event
    _dvt_coord_queue = queue.Queue()
    result = queue.Queue(maxsize=1)

    # The HTTP request waits until the actual DVT call completes or fails.
    async def run_async_function():
        await set_location_thread(
            latitude,
            longitude,
            _dvt_coord_queue,
            lambda: result.put_nowait(None),
            stop_event,
        )

    # Create a new thread and start it
    def run_location_worker():
        try:
            asyncio.run(run_async_function())
        except Exception as exc:
            if result.empty():
                result.put_nowait(exc)
        finally:
            global _dvt_coord_queue
            _dvt_coord_queue = None

    location_thread = threading.Thread(target=run_location_worker, daemon=True)
    _dvt_thread = location_thread
    location_thread.start()

    try:
        failure = result.get(timeout=30)
    except queue.Empty as exc:
        stop_event.set()
        raise TimeoutError("LocationSimulation did not respond within 30 seconds") from exc
    if failure is not None:
        raise failure


# Function to stop the location thread
def stop_set_location_thread():
    global location_stop_event, _dvt_thread, _dvt_coord_queue
    if location_stop_event is not None:
        location_stop_event.set()
        location_stop_event = None
    if _dvt_thread is not None and _dvt_thread.is_alive():
        if threading.current_thread() != _dvt_thread:
            _dvt_thread.join(timeout=1.0)
        _dvt_thread = None
    _dvt_coord_queue = None


def dispatch_dvt_location(latitude: float, longitude: float):
    global ios_version, udid, lockdown
    if ios_version is not None and is_major_version_17_or_greater(ios_version):
        if modern_location.enabled and ios_version.startswith('27.'):
            modern_location.set(udid, latitude, longitude)
            return
        start_set_location_thread(latitude, longitude)
    elif ios_version is not None and not is_major_version_17_or_greater(ios_version):
        mount_developer_image()
        start_set_location_thread(latitude, longitude)
    else:
        raise RuntimeError("No iOS version present")


current_location_sink: LocationSink = DvtLocationSink(
    dispatch_fn=dispatch_dvt_location,
    clear_fn=stop_set_location_thread,
)


def set_location_sink(sink: LocationSink) -> None:
    global current_location_sink
    current_location_sink = sink
    app.config["LOCATION_SINK"] = sink


def get_location_sink() -> LocationSink:
    return app.config.get("LOCATION_SINK", current_location_sink)


def _on_nav_location_update(lat: float, lng: float) -> None:
    global location
    location = f"{lat} {lng}"


navigation_controller = NavigationController(
    sink_provider=get_location_sink,
    on_location_update=_on_nav_location_update,
)
app.navigation_controller = navigation_controller


def get_navigation_controller() -> NavigationController:
    ctrl = getattr(app, "navigation_controller", None)
    if ctrl is not None:
        return ctrl
    global navigation_controller
    if navigation_controller is not None:
        navigation_controller.speed_kmh = current_speed_kmh
        app.navigation_controller = navigation_controller
        return navigation_controller
    navigation_controller = NavigationController(
        sink_provider=get_location_sink,
        on_location_update=_on_nav_location_update,
    )
    navigation_controller.speed_kmh = current_speed_kmh
    app.navigation_controller = navigation_controller
    return navigation_controller


current_speed_kmh: float = 5.0


def set_current_speed(speed: float) -> None:
    global current_speed_kmh
    speed_float = validate_speed(speed)
    current_speed_kmh = speed_float
    app.config["CURRENT_SPEED_KMH"] = speed_float
    ctrl = getattr(app, "navigation_controller", None)
    if ctrl is None and "navigation_controller" in globals():
        ctrl = globals()["navigation_controller"]
    if ctrl is not None:
        if hasattr(ctrl, "speed_kmh"):
            ctrl.speed_kmh = speed_float
        if hasattr(ctrl, "update_speed"):
            try:
                ctrl.update_speed(speed_float)
            except Exception:
                pass


def get_current_speed() -> float:
    global current_speed_kmh
    if hasattr(app, "navigation_controller") and getattr(app, "navigation_controller", None):
        controller = getattr(app, "navigation_controller")
        if hasattr(controller, "speed_kmh"):
            return float(controller.speed_kmh)
    return app.config.get("CURRENT_SPEED_KMH", current_speed_kmh)


@app.route('/update_speed', methods=['POST'])
def update_speed():
    try:
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({'error': 'Invalid or missing JSON body'}), 400

        if 'speed_kmh' not in data:
            return jsonify({'error': "Missing 'speed_kmh' parameter"}), 400

        try:
            speed_kmh = validate_speed(data.get('speed_kmh'))
        except (ValueError, TypeError) as exc:
            return jsonify({'error': str(exc)}), 400

        set_current_speed(speed_kmh)

        ctrl = getattr(app, "navigation_controller", None)
        updated_duration = 0.0
        if ctrl is not None and getattr(ctrl, 'active', False):
            updated_duration = getattr(ctrl, 'remaining_time_s', 0.0)

        resp = {
            'status': 'updated',
            'speed_kmh': speed_kmh,
            'updated_duration_s': updated_duration,
        }

        return jsonify(resp), 200

    except Exception as e:
        logger.exception("Error during /update_speed")
        return jsonify({'error': str(e)}), 500


@app.route('/start_navigation', methods=['POST'])
def start_navigation():
    try:
        data = request.get_json(silent=True)
        if not data or not isinstance(data, dict):
            return jsonify({'error': 'Invalid or missing JSON body'}), 400

        waypoints = data.get('waypoints')
        if not waypoints:
            return jsonify({'error': "Missing 'waypoints' parameter"}), 400

        if not isinstance(waypoints, list) or len(waypoints) < 2:
            return jsonify({'error': "'waypoints' must contain at least 2 coordinate pairs"}), 400

        speed_kmh = data.get('speed_kmh')
        if speed_kmh is None:
            speed_kmh = get_current_speed()
        else:
            try:
                speed_kmh = validate_speed(speed_kmh)
            except (ValueError, TypeError) as exc:
                return jsonify({'error': str(exc)}), 400

        ctrl = get_navigation_controller()
        result = ctrl.start(waypoints, speed_kmh)
        return jsonify(result), 200

    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        logger.exception("Error during /start_navigation")
        return jsonify({'error': str(e)}), 500


@app.route('/stop_navigation', methods=['POST'])
def stop_navigation():
    try:
        ctrl = get_navigation_controller()
        coords = ctrl.stop()
        return jsonify({
            'status': 'stopped',
            'current_location': coords
        }), 200
    except Exception as e:
        logger.exception("Error during /stop_navigation")
        return jsonify({'error': str(e)}), 500


@app.route('/pause_navigation', methods=['POST'])
def pause_navigation():
    try:
        ctrl = get_navigation_controller()
        ctrl.pause()
        return jsonify({'status': 'paused'}), 200
    except Exception as e:
        logger.exception("Error during /pause_navigation")
        return jsonify({'error': str(e)}), 500


@app.route('/resume_navigation', methods=['POST'])
def resume_navigation():
    try:
        ctrl = get_navigation_controller()
        ctrl.resume()
        return jsonify({'status': 'resumed'}), 200
    except Exception as e:
        logger.exception("Error during /resume_navigation")
        return jsonify({'error': str(e)}), 500


@app.route('/navigation_status', methods=['GET'])
def navigation_status():
    try:
        ctrl = get_navigation_controller()
        status_data = ctrl.get_status()
        if (status_data.get('current_lat') == 0.0 and status_data.get('current_lng') == 0.0) and location:
            try:
                lat_str, lng_str = location.split()
                status_data['current_lat'] = float(lat_str)
                status_data['current_lng'] = float(lng_str)
            except Exception:
                pass
        return jsonify(status_data), 200
    except Exception as e:
        logger.exception("Error during /navigation_status")
        return jsonify({'error': str(e)}), 500


@app.route('/set_location', methods=['POST'])
def set_location():
    try:
        global rsd_data, rsd_host, rsd_port
        global location
        global udid, connection_type
        global ios_version

        if location is None:
            return jsonify({'error': 'Location is not set'}), 400

        sink = get_location_sink()
        if isinstance(sink, DvtLocationSink) and ios_version is None:
            # Invalid ios_version
            return jsonify({'error': 'No iOS version present'}), 400

        # Split the location string into latitude and longitude
        latitude, longitude = map(float, location.split())
        sink.set_location(latitude, longitude)
        return 'DVT set call completed; check the phone location'

    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message}), 500


@app.route('/move_step', methods=['POST'])
def move_step():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'error': 'Invalid or missing JSON body'}), 400

        direction = data.get('direction')
        if not direction:
            return jsonify({'error': "Missing 'direction' parameter"}), 400

        try:
            get_bearing_for_direction(direction)
        except ValueError as ve:
            return jsonify({'error': str(ve)}), 400

        speed_kmh = data.get('speed_kmh')
        if speed_kmh is None:
            speed_kmh = get_current_speed()
        else:
            try:
                speed_kmh = validate_speed(speed_kmh)
            except (ValueError, TypeError) as exc:
                return jsonify({'error': str(exc)}), 400

        global location
        if 'lat' in data and 'lng' in data:
            try:
                cur_lat = float(data['lat'])
                cur_lng = float(data['lng'])
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid lat/lng provided in request'}), 400
        elif location is not None:
            try:
                cur_lat, cur_lng = map(float, location.split())
            except Exception:
                return jsonify({'error': 'Failed to parse current location'}), 400
        else:
            ctrl = get_navigation_controller()
            if ctrl is not None and getattr(ctrl, 'active', False):
                cur_lat = ctrl.current_lat
                cur_lng = ctrl.current_lng
            else:
                return jsonify({'error': 'Current location is not set'}), 400

        # Stop active auto navigation if running
        ctrl = get_navigation_controller()
        if ctrl is not None:
            try:
                ctrl.stop()
            except Exception:
                pass

        # Calculate 1-second displacement
        new_lat, new_lng, distance_meters = calculate_step(
            cur_lat, cur_lng, direction, speed_kmh, duration_seconds=1.0
        )

        # Update active location
        location = f"{new_lat} {new_lng}"

        # Dispatch to location sink
        sink = get_location_sink()
        sink.set_location(new_lat, new_lng)

        return jsonify({
            'lat': new_lat,
            'lng': new_lng,
            'distance_m': distance_meters
        }), 200

    except Exception as e:
        logger.exception("Error during /move_step")
        return jsonify({'error': str(e)}), 500


@app.route('/stop_location', methods=['POST'])
def stop_location():
    global ios_version, udid, connection_type
    try:
        stop_set_location_thread()
        if modern_location.enabled and ios_version and ios_version.startswith('27.'):
            modern_location.clear(udid)
            return 'Location cleared successfully'
        return asyncio.run(stop_legacy_location())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


async def stop_legacy_location():
    global ios_version, udid, connection_type
    try:
        global rsd_data
        global rsd_host
        global rsd_port
        global lockdown
        logger.info(f"stop set location data:  {rsd_data}")


        if udid in rsd_data_map:
            if connection_type in rsd_data_map[udid]:
                rsd_data = rsd_data_map[udid][connection_type]

                rsd_host = rsd_data['host']
                rsd_port = rsd_data['port']

            if ios_version is not None and is_major_version_17_or_greater(ios_version):
                async with RemoteServiceDiscoveryService((rsd_host, rsd_port)) as sp_rsd:
                    with DvtSecureSocketProxyService(sp_rsd) as dvt:
                        LocationSimulation(dvt).clear()
                        logger.warning("Location Cleared Successfully")
                return 'Location cleared successfully'

            elif ios_version is not None and not is_major_version_17_or_greater(ios_version):
                with DvtSecureSocketProxyService(lockdown=lockdown) as dvt:

                    LocationSimulation(dvt).clear()
                    logger.warning("Location Cleared Successfully")
                return 'Location cleared successfully'
        return 'Location cleared successfully'
    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message}), 500


def get_github_version():
    try:
        # Make a request to the GitHub API to get the content of CURRENT_VERSION file
        url = f'https://raw.githubusercontent.com/{GITHUB_REPO}/main/{CURRENT_VERSION_FILE}'
        response = requests.get(url)

        response.raise_for_status()

        # Parse the content of the file
        github_version = response.text.strip()


        return github_version
    except requests.RequestException as e:

        return None



def remove_ansi_escape_codes(text):
    ansi_escape = re.compile(r'\x1b[^m]*m')
    return ansi_escape.sub('', text)

async def get_network_devices():
# you can also query network lockdown instances using the following:
    async for ip, lockdown in get_mobdev2_lockdowns():
        print(ip, lockdown.short_info)

@app.route('/list_devices')
def py_list_devices():
    try:
        connected_devices = {}

        # Retrieve all devices
        all_devices = list_devices()
        #wifi_devices = None
        #wifi_devices = asyncio.run(get_network_devices())
        logger.info(f"\n\nRaw Devices:  {all_devices}\n")
        #logger.info(f"\n\nWifi Devices:  {wifi_devices}\n")


        if wifihost:
            udid = args.udid
            logger.warning(f"Wifi requested to {wifihost}")
            logger.warning(f"udid: {udid}")
            lockdown = create_using_tcp(hostname=wifihost, identifier=udid)

            # udid = lockdown.udid
            # print("wifi udid", udid)
            info = lockdown.short_info
            logger.warning(f"Wifi Short Info: {info}")
            # Modify the info dictionary to include wifiConState
            wifi_connection_state = lockdown.enable_wifi_connections = True
            info['wifiState'] = wifi_connection_state

            # Modify the info dictionary to include user locale
            info['userLocale'] = get_user_country()

            info['ConnectionType'] = 'Network'

            # Substitute "Network" with "Wifi" in the connection_type
            connection_type = "Manual Wifi"
            # if connection_type == "Network":
            #     connection_type = "Wifi"

            # If the serial already exists in the connected_devices dictionary
            if udid in connected_devices:
                # If the connection_type already exists under the serial, append the device to the list
                if connection_type in connected_devices[udid]:
                    connected_devices[udid][connection_type].append(info)
                # If the connection_type doesn't exist under the serial, create a new list with the device
                else:
                    connected_devices[udid][connection_type] = [info]
            # If the serial is new, create a new dictionary entry with the connection_type as a list
            else:
                connected_devices[udid] = {connection_type: [info]}






        # Iterate through all devices

        for device in all_devices:
            udid = device.serial
            connection_type = device.connection_type

            # Create lockdown and info variables
            #global lockdown
            lockdown = create_using_usbmux(udid, connection_type=connection_type, autopair=True)
            info = lockdown.short_info


            wifi_connection_state = lockdown.enable_wifi_connections

            if wifi_connection_state == False:
                logger.info("Enabling Wifi Connections")
                wifi_connection_state = lockdown.enable_wifi_connections = True
                logger.info(f"Wifi Connection State: True")

            # Modify the info dictionary to include wifiConState
            info['wifiState'] = wifi_connection_state

            # Modify the info dictionary to include user locale
            info['userLocale'] = get_user_country()

            # Substitute "Network" with "Wifi" in the connection_type
            if connection_type == "Network":
                connection_type = "Wifi"

            # If the serial already exists in the connected_devices dictionary
            if udid in connected_devices:
                # If the connection_type already exists under the serial, append the device to the list
                if connection_type in connected_devices[udid]:
                    connected_devices[udid][connection_type].append(info)
                # If the connection_type doesn't exist under the serial, create a new list with the device
                else:
                    connected_devices[udid][connection_type] = [info]
            # If the serial is new, create a new dictionary entry with the connection_type as a list
            else:
                connected_devices[udid] = {connection_type: [info]}

        logger.info(f"\n\nConnected Devices: {connected_devices}\n")

        # Check if running as sudo
        if current_platform == "darwin" and not modern_location.enabled:
            if os.geteuid() != 0:
                logger.error("*********************** WARNING ***********************")
                logger.error("Not running as Sudo, this probably isn't going to work")
                logger.error("*********************** WARNING ***********************")
        return jsonify(connected_devices)

    except ConnectionAbortedError as e:
        logger.error(f"ConnectionAbortedError occurred: {e}")
        return {"error"}

    except Exception as e:
        error_message = str(e)
        return jsonify({'error': error_message})

def clear_geoport():
    logger.info("clear any GeoPort instances")
    substring = "GeoPort"

    for process in psutil.process_iter(['pid', 'name']):
        if substring in process.info['name']:
            logger.info(f"Found process: {process.info['pid']} - {process.info['name']}")

            # Terminate the process
            process.terminate()
    else:
        logger.warning("No GeoPort found")


def clear_old_geoport():
    logger.info("clear old GeoPort instances")
    substring = "GeoPort"

    current_pid = os.getpid()

    for process in psutil.process_iter(['pid', 'name']):
        if substring in process.info['name'] and process.info['pid'] != current_pid:
            logger.info(f"Found process: {process.info['pid']} - {process.info['name']}")

            # Terminate the process
            process.terminate()


def shutdown_server():
    logger.warning("shutdown server")
    stop_location()
    stop_set_location_thread()
    stop_tunnel_thread()
    cancel_async_tasks()
    terminate_threads()


    # Terminate the current process
    clear_geoport()

    logger.error("OS Kill")
    os.kill(os.getpid(), signal.SIGINT)
    list_threads()
    terminate_threads()
    logger.error("sys exit")
    os._exit(0)


def terminate_threads():
    """
    Terminate all threads.
    """
    for thread in threading.enumerate():
        if thread != threading.main_thread():
            logger.info(f"thread: {thread}")
            terminate_flag = threading.Event()
            terminate_flag.set()
            #thread.terminate()  # Terminate the thread

def list_threads():
    """
    Terminate all threads.
    """
    for thread in threading.enumerate():
        logger.info(f"thread: {thread}")
def cancel_async_tasks():
    try:
        #loop = asyncio.get_running_loop()
        tasks = asyncio.all_tasks()
        for task in tasks:
            logger.info(f"task: {task}")
            task.cancel()
    except RuntimeError as e:
        if "no running event loop" in str(e):
            logger.error("No running event loop found.")
        else:
            raise e  # Re-raise the error if it's not related to the event loop



@app.route('/exit', methods=['POST'])
def exit_app():
    logger.warning("Exit GeoPort")
    shutdown_server()
    # Send a response to the client immediately
    response = {"success": True, "message": "Server is shutting down..."}

    return jsonify(response)


@app.route('/')
def index():
    # global error_message
    fetch_api_data(api_url)
    # Get the GitHub version
    github_version = get_github_version()
    user_locale = get_user_country()
    logger.info(f"Country: {user_locale}")
    logger.info(f"Current platform: {platform}")
    logger.info(f"App Version = {APP_VERSION_NUMBER}")
    logger.info(f"base dir =  {base_directory}")
    logger.info(f"GitHub Version = {github_version}")

    #list_devices()
    # Compare with the locally hardcoded version
    if github_version and github_version > APP_VERSION_NUMBER:
        version_message = f"Update available. New Version is {github_version}"

    elif github_version and github_version < APP_VERSION_NUMBER:
        version_message = f"Beta Testing. App version is {APP_VERSION_NUMBER} - github is {github_version}"

    else:
        version_message = None

    return render_template('map.html', version_message=version_message,
                           user_locale=user_locale, app_version_num=APP_VERSION_NUMBER,
                           app_version_type=APP_VERSION_TYPE, error_message=error_message, current_platform=platform,
                           sudo_message=sudo_message)


def open_browser():
    time.sleep(2)  # Wait for the Flask app to start
    #webbrowser.open(f'http://localhost:{chosen_port}')
    browser = webbrowser.get()
    browser.open(f'http://localhost:{chosen_port}')


def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0
    # with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    #     try:
    #         s.bind((' ', port))
    #         return False  # Port is available
    #     except OSError:
    #         return True  # Port is already in use


# Define try_bind_listener_on_free_port function
def try_bind_listener_on_free_port():
    global chosen_port
    min_port = 49215
    max_port = 65535

    # Check if --port argument is provided
    if args.port:
        chosen_port = args.port
    else:
        chosen_port = flask_port

    if is_port_in_use(chosen_port):
        chosen_port = random.randint(min_port, max_port)
    logger.info(f'Serving: http://localhost:{chosen_port}')
    return chosen_port


if __name__ == '__main__':
    #create_geoport_folder()
    if is_windows:
        try:
            import pyi_splash

            pyi_splash.update_text('UI Loaded ...')
            logger.info("clear splash")
            pyi_splash.close()
        except:
            pass
        if not pyuac.isUserAdmin():
            print("Relaunching as Admin")
            pyuac.runAsAdmin()
    #else:




    chosen_port = try_bind_listener_on_free_port()

    # Check if --no-browser flag is provided
    if not args.no_browser:
        open_browser()
    else:
        logger.info("--no-browser flag passed")
        logger.info("Running without auto-browser popup")



    #threading.Thread(target=open_browser).start()

    app.run(debug=True, use_reloader=False, port=chosen_port, host='0.0.0.0')
