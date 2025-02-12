# 🐝 Broadcast Emulation Engine 🐝
*Brought to you by the Honey Sauce Collective*

Take back control of your media! The Broadcast Emulation Engine puts you in the driver's seat, allowing you to create, manage, schedule and automate channels containing tv shows, movies, music videos and interstitial content simulating the look and feel of broadcast television with your own media library. Flip channels to your heart's content or set a single channel and let it run in the background. No more time spent navigating menus looking for something to watch or being locked into binge watching a single show for hours on end. 

BEE is a multi-channel, multi-receiver automated media solution utilizing open source technologies to simulate the experience of broadcast television. Highly configurable with a web interface and channel guide, BEE allows the user to recreate the feeling of broadcast television using a local media library with Kodi-compliant NFO files.

## BEE Dynamic Scheduling Features 🐝
* Channel Templates: User configurable settings to guide channel generation and rescheduling. These templates break each day into six blocks and allows filtering based on genre, content rating or decade and with options to determine how time blocks are scheduled.
* Variable Start Times: When a selected movie or TV episode runs over the next scheduled start time, BEE will first attempt to delay the start. If the end time reaches the scheduled start of the next time slot, it will be pre-empted, starting after the end of the previous item, but "already in progress". If the remaining time to play the item is too short relative to its full length, BEE will skip the entry instead.
* Smart TV Show Scheduling: TV shows can be specific or random and episodes can be set to run sequentially, at random, or to rerun the last sequential episode. When the last sequential episode has run, there are options to repeat the show, or to schedule a different show in the time slot.
* Random Movie Scheduling: Movies are scheduled at random within guidelines set in the channel template and each entry can be limited by duration or metadata. Link Mode allows movies to be selected based on similar metadata to a previously scheduled movie. This has a Kevin Bacon effect with the selected metadata, connecting movies together by actor, director, year, studio, TMDB tag and more.
* Music Video Block Scheduling: In addition to movies and tv shows, BEE allows for music video blocks to be scheduled using the defined music video library. Music video selections can be guided by decade or tag and can optionally utilize the same link mode technology that connects movies together.
* Interstitial Controls: Adjustable values that guide the selection of interstitial videos (commercials, station id, etc).
* Fresh Honey: A feature of BEE that uses yt-dlp technology and the TMDB API to get fresh trailers to use as interstitials.

## Getting Started 🐝
**Setup of this application requires a base knowledge of setting up network shares, python environments and docker containers.**

Before installing BEE, first prepare your media libraries. BEE is set up to use Kodi-compliant NFO files for metadata, however Kodi is not required for operation. Instead, you can use [TinyMediaManager](https://www.tinymediamanager.org/) to download metadata and geneate NFO files and thumbnails for movies and television shows. Interstitial libraries will be managed by BEE itself, and similarly formatted NFO files will be created alongside those files. Ensure the library directories are shared to your network and have a mounted root path in common (for example if shows and movies are in `/library/shows` and `/library/movies/` then the root path is `/library`).

🐝 **Set up your Drone hardware** in advance and connect each one to a display device. Drones are playback devices attached to a television or other display. Drone devices must use VLC player with the HTTP API enabled and have the library root path mounted in the OS. The web interface can generate systemctl .service files for each Drone, so if you are setting up your Drone in a Linux environment (on a Raspberry Pi for example), ensure that VLC is installed, the media library network shares are mounted, and use the generated .service file at a later step. 

🐝 **Copy BEE files to desired path**. Copy all of the BEE operational files into a directory on the host machine. 

🐝 **Set up Docker instance**. If you are going to run BEE from a Docker instance, get started by navigating to the directory containing the BEE files and run these commands:

* `docker build -t bee .`
* `docker run -v "$(pwd)":/bee -v [MEDIA LIBRARY ROOT PATH]:/library -d bee`

Replace `[MEDIA LIBRARY ROOT PATH]` with the directory path to the root location of your media library. This will install dependencies from requirements.txt and start the web user interface. Once this is complete, skip down to the Configure Settings step.

🐝 **Install dependencies**. If you are not using a preconfigured docker container, install python and the requirements.txt dependencies in the environment running BEE and ensure the environment has network access to the library common root path. 

🐝 **Connect to the Web Interface with your browser**. Enter `[hostname or IP]:5000` into your browser address bar. Use the hostname or IP for the machine hosting the docker container. The default port is 5000. This can be altered by changing the value of the associated variable in config.ini, but you will also need to modify the port number in the `bee` docker file to expose the port from the container to your network.

![image](https://github.com/user-attachments/assets/c568c915-19b9-4c07-b9f4-f4ff2546be39)

🐝 **Configure Settings**. Set the library paths and other user configured settings on the Settings page in the web interface. Enter a TMDB API key in the associated field to use the Fresh Honey tool to get current trailers based on TMDB data.

![image](https://github.com/user-attachments/assets/c5aded16-27dc-43b2-adf2-1bbc1d4e305f)

🐝 **Generate Channels**. On the Channels page, use either preconfigured or user-generated templates to spin up new channels. If the number of channels generated is less than the minimum set in the settings, the remaining channels will be generated when BEE does its daily tasks after midnight. 

![image](https://github.com/user-attachments/assets/bf03d726-e027-4037-8c3e-7d8d735abe91)

![image](https://github.com/user-attachments/assets/590b3fe2-cbd7-4d81-be0d-d26588e6734b)

🐝 **Set up Drones**. Navigate to the Drones page and create a new entry for each playback device. Once each Drone has been added, you may geneate and download a .service file for VLC. This can be used to configure systemctl to launch VLC at boot on the Drone hardware.

![image](https://github.com/user-attachments/assets/948533bd-62ff-4df0-a12f-bcf7073aa49a)

🐝 **Set up external controls**. If you have a remote control or other client-connected input device that you would like to use to operate BEE, download the remote.service file from the Drone page and copy that file and drone.py to the connected client device. Set up drone.py to launch at boot using the downloaded remote.service file. On first launch, the script will prompt the user to use the input device to map button presses to BEE and VLC actions. 

## Watching TV with BEE 🐝
After channels have been generated and Drones have been set up, you will see your Drones listed at the bottom of the BEE index page and the Schedule page will show the generated channels and what content is currently scheduled. Right click on one of these channels, a dialog box will appear in which you can select a Drone. Do so and click OK and playback will start on the selected Drone momentarily. After a few seconds, the webpage will reload and you will see the Drones in playback at the top of the screen. Right click on that row to stop playback on that Drone. Alternatively, if you have set up a remote control or other input device on your Drone, you can use that the start and stop playback, as well as channel surf and control a few VLC-specific operations such as toggling subtitles and player volume.

![image](https://github.com/user-attachments/assets/3087cdd2-c6a0-4525-ba1a-82f04801ddbc)

## Using the Web Interface 🐝
From the schedule page, a click on a scheduled item will expand details at the top of the page. These details include the title and a description of the scheduled item alsong with the length, start time and channel details. The channel details are automatically generated for each channel, but can be user-defined. You can change the channel details through a link on the Channels page. Clicking on the times in the header will offset the schedule to start at the time clicked on, except for the first, which will adjust the schedule backwards. Clicking on the current time resets the schedule, and clicking on any channel details on the left will navigate to a page with the full upcoming schedule for that channel. On the schedule, TV shows are in blue, and movies in cyan or red. Movies in red indicate they have been selected through Link Mode and when viewing the entry details, it will display what other movie and metadata the movie is linked from.

![image](https://github.com/user-attachments/assets/2a877cc2-3e1f-4821-9e3f-1f75c805c113)

## Automated Tasks 🐝
Shortly after midnight each day, BEE will run a few tasks to prepare itself for the next day. The content libraries will be scanned and updated at this time. If you have added any new TV episodes or movies to your library in the last 24 hours, ensure it has been scanned with TinyMediaManager, Kodi or whatever you are using to manage the NFO file creation. Interstitial files will have their NFO files generated by BEE during the overnight scan, if they don't already exist. If it is Saturday night and Fresh Honey is enabled, it will run as directed. Daily schedules will be updated out to the number of days indicated in settings. For example, if the number is 7, the daily schedules for each channel will be generated out to seven days in the future. Finally, the next day's schedule is copied and interstitial videos are scored and slotted in between scheduled content. 

## Known Issues 🐝
* On the schedule page, blocks sometimes don't line up with their start or end times. Use the channel schedule page or click an entry to display details to validate the start or end time of a scheduled item.
* Some Drone devices plugged into 4K displays may not be capable of running video content at 4K resolution. If you encounter this issue, manually reduce the display resolution.
* When generating a new channel, only one day's schedule is created, instead of the minimum indicated in Settings. This is corrected after the overnight tasks process the new channel.

## Notes 🐝
Each broadcast "day" begins by default at 6am, but this can vary, based on block settings in each channel's template. The automated tasks are scheduled just after midnight and, depending on your hardware, can take a minute or more per channel to finalize the day's schedule. When increasing the channel load, first check the hivemind.log file for the completion time and run time of the automated tasks. Divide the run time by the number of channels to get the approximate per-channel time (Saturday excluded) and use that information to inform how many more channels you are willing to safely add to your system.

When generating channels from templates, if BEE runs out of shows to schedule, it will schedule shows already on the schedule in Random Episode mode. To prevent this from happening, other than having more shows in your library, avoid overuse of the Daily setting in the template. Weekly or Weeday/end will require fewer shows to fill out the week and allow for more variation in rescheduling.

If you encounter bugs, or other problems, please report an Issue here. If you need help getting set up, or have feature requests or other questions, join us on [Discord](https://discord.gg/EnUkAeq). 

Finally, please look over your settings carefully and enjoy! 
