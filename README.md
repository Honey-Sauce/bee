# Broadcast Emulation Engine
A multi-channel, multi-receiver automated media solution utilizing open source technologies to simulate the experience of broadcast television. Highly configurable with a web interface and channel guide, BEE allows the user to recreate the feeling of broadcast television using a local media library with Kodi-compliant NFO files.

## Getting Started
Before installing BEE, you should first prepare your media libraries. BEE is set up to use Kodi-compliant NFO files for metadata, however Kodi is not required for operation. Instead, you can use TinyMediaManager to download metadata and geneate NFO files and thumbnails for movies and television shows. Interstitial libraries will be managed by BEE itself, and similarly formatted NFO files will be created alongside those files. Ensure the library directories are shared to your network and have a root path in common (for example ```/libraries```).

*Set up your Drone hardware* in advance and connect each one to a display device. Drone devices must use VLC player with the HTTP API enabled and have the library common root path mounted in the OS. The web interface can generate systemctl .service files for each Drone, so if you are setting up your Drone in a Linux environment (on a Raspberry Pi for example), ensure that VLC is installed and use the generated .service file at a later step. 

*Install dependencies*. If you are not using a preconfigured docker container, install python and the requirements.txt dependencies in the environment running BEE and ensure the environment has network access to the library common root path. 

*Copy BEE files to desired path*. Copy all of the BEE operational files into a path in the python environment and configure web_app.py and hivemind.py to launch at boot. This will be your graphical interface for all necessary operations of BEE.

*Configure Settings*. Set the library paths and other user configured settings on the Settings page in the web interface.

*Generate Channels*. On the Channels page, use either preconfigured or user-generated templates to spin up new channels. If the number of channels generated is less than the minimum set in the settings, the remaining channels will be generated when hivemind does its daily tasks after midnight.

*Set up Drones*. Navigate to the Drones page and create a new entry for each device. Once each Drone has been added, you may geneate and download a .service file for VLC. This can be used to configure systemctl to launch VLC at boot

*Set up external controls*. If you have a remote control or other client-connected input device that you would like to use to operate BEE, download the remote.service file from the Drone page and copy that file and drone.py to the connected client device. Set up drone.py to launch at boot using the downloaded remote.service file.
