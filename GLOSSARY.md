# GeoPort Domain Model

GeoPort is an iOS location simulation and spoofing workbench supporting developer tunnel protocols, automated pedestrian navigation, and manual real-time steering.

## Language

**Device iOS Version**:
The operating system version reported by a connected Apple device (e.g., iOS 17.4, iOS 27.0). Used by hardware communication layers to negotiate DVT tunnels, RSD (Remote Service Discovery), and Developer Mode requirements.
_Avoid_: App version, software version, GeoPort version

**App Version**:
The release version number of the GeoPort software package itself (e.g., 2.3.3). Deprecated from UI display and update checking.
_Avoid_: iOS version, system version

**Location Simulation**:
The act of injecting spoofed GPS latitude and longitude coordinates into an iOS device via developer debug services (DVT / pymobiledevice3).
_Avoid_: Mocking, fake GPS, teleport (when referring to continuous movement)

**Auto Navigation**:
Automated step-by-step movement along real pedestrian roads at a configured speed, interpolated at 1Hz by a server-side background worker.
_Avoid_: Playback, teleport, route replay

**Manual Steering**:
Real-time user-controlled directional movement using keyboard inputs (WASD / arrow keys) advancing coordinates at the currently selected speed.
_Avoid_: Joystick mode, key walking

**Fuel Mode**:
A deprecated legacy subsystem that scraped Australian fuel prices and positioned simulated GPS coordinates at gas stations. Slated for complete removal.
_Avoid_: Fuel prices, fuel data
