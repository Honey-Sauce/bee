# 🐝 Broadcast Emulation Engine 🐝
Take back control of your media! The Broadcast Emulation Engine puts you in the driver's seat, allowing you to create, manage, schedule and automate multiple mixed-media channels containing tv, movies, music videos and interstitial content. Flip channels to your heart's content or set a single channel and let it run. No more time spent navigating menus looking for something to watch. 

BEE is a multi-channel, multi-receiver automated media solution utilizing open source technologies to simulate the experience of broadcast television. Highly configurable with a web interface and channel guide, BEE allows the user to recreate the feeling of broadcast television using a local media library with Kodi-compliant NFO files.

Setup of this application requires a base knowledge of setting up network shares, python environments and docker containers. 

## Getting Started
Before installing BEE, first prepare your media libraries. BEE is set up to use Kodi-compliant NFO files for metadata, however Kodi is not required for operation. Instead, you can use [TinyMediaManager](https://www.tinymediamanager.org/) to download metadata and geneate NFO files and thumbnails for movies and television shows. Interstitial libraries will be managed by BEE itself, and similarly formatted NFO files will be created alongside those files. Ensure the library directories are shared to your network and have a mounted root path in common (for example if shows and movies are in `/libraries/shows` and `/libraries/movies/` then the root path is `/libraries`).

🐝 **Set up your Drone hardware** in advance and connect each one to a display device. Drone devices must use VLC player with the HTTP API enabled and have the library root path mounted in the OS. The web interface can generate systemctl .service files for each Drone, so if you are setting up your Drone in a Linux environment (on a Raspberry Pi for example), ensure that VLC is installed, the media library network shares are mounted, and use the generated .service file at a later step. 

🐝 **Copy BEE files to desired path**. Copy all of the BEE operational files into a directory on the host machine. 

🐝 **Set up Docker instance**. If you are going to run BEE from a Docker instance, get started by navigating to the directory containing the BEE files and run these commands:

* `docker build -t bee .`
* `docker run -v "$(pwd)":/bee -v [MEDIA LIBRARY ROOT PATH]:/libraries -d bee`

Replace `[MEDIA LIBRARY ROOT PATH]` with the directory path to the root location of your media library. This will install dependencies from requirements.txt and start the web user interface. Once this is complete, skip down to the Configure Settings step.

🐝 **Install dependencies**. If you are not using a preconfigured docker container, install python and the requirements.txt dependencies in the environment running BEE and ensure the environment has network access to the library common root path. 

🐝 **Connect to the Web Interface with your browser**. Enter `[hostname or IP]:5000` into your browser address bar. Use the hostname or IP for the machine hosting the docker container. The default port is 5000. This can be altered by changing the value of the associated variable in config.ini, but you will also need to modify the port number in the `bee` docker file to expose the port from the container to your network.

![image](https://github.com/user-attachments/assets/c568c915-19b9-4c07-b9f4-f4ff2546be39)

🐝 **Configure Settings**. Set the library paths and other user configured settings on the Settings page in the web interface. Enter a TMDB API key in the associated field to use the Fresh Honey tool to get current trailers based on TMDB data.

![image](https://github.com/user-attachments/assets/c5aded16-27dc-43b2-adf2-1bbc1d4e305f)

🐝 **Generate Channels**. On the Channels page, use either preconfigured or user-generated templates to spin up new channels. If the number of channels generated is less than the minimum set in the settings, the remaining channels will be generated when hivemind does its daily tasks after midnight. 

![image](https://github.com/user-attachments/assets/bf03d726-e027-4037-8c3e-7d8d735abe91)

![image](https://github.com/user-attachments/assets/590b3fe2-cbd7-4d81-be0d-d26588e6734b)

🐝 **Set up Drones**. Navigate to the Drones page and create a new entry for each playback device. Once each Drone has been added, you may geneate and download a .service file for VLC. This can be used to configure systemctl to launch VLC at boot on the Drone hardware.

![image](https://github.com/user-attachments/assets/50f7734a-852c-4e14-9bad-eb6b7a1f003b)

🐝 **Set up external controls**. If you have a remote control or other client-connected input device that you would like to use to operate BEE, download the remote.service file from the Drone page and copy that file and drone.py to the connected client device. Set up drone.py to launch at boot using the downloaded remote.service file. On first launch, the script will prompt the user to use the input device to map button presses to BEE and VLC actions. 
