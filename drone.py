import argparse
import configparser
import evdev
import json
import os
import pyudev
import queue
import requests
import sys
import tkinter as tk
import threading
import time
import xml.etree.ElementTree as ET
from evdev import InputDevice, list_devices, categorize, ecodes
from pynput import keyboard
last_pressed = None
last_volume = None
subtitle_track = None
audio_track = None
video_track = None
aspect_ratio = None
hostname = os.environ.get('HOST')
port = os.environ.get('PORT',80)
drone = os.environ.get('DRONE')
font_name = os.environ.get('FONT','Arial')
font_color = os.environ.get('COLOR','yellow')
font_bg = os.environ.get('BG', 'blue')
font_size = os.environ.get('SIZE', 30)
x_pos = os.environ.get('X_POS', '300')
y_pos = os.environ.get('Y_POS', '60')

# VLC HTTP API URL and authentication info
vlc_host = os.environ.get('VLCHOST','localhost')
vlc_port = os.environ.get('VLCPORT','8008')
password = os.environ.get('VLCPASS','pass')  # If VLC is password-protected
auth = ('', password)

# VLC API endpoint for status
vlc_url = f"http://{vlc_host}:{vlc_port}/requests/status.json"

class OverlayApp:
    def __init__(self, duration, initial_text, update_queue):
        self.duration = duration
        self.update_queue = update_queue
        self.root = tk.Tk()
        self.text_var = tk.StringVar(value=initial_text)
        self.label = tk.Label(self.root, textvariable=self.text_var, font=(font_name, font_size), fg=font_color, bg=font_bg)
        self.label.pack()
        self.root.attributes('-topmost', True)
        self.root.overrideredirect(True)  # Remove window borders and title bar
        self.root.wm_attributes("-alpha", 0.4)  # Set transparency
        self.root.geometry(f"+{x_pos}+{y_pos}")  # Positioning

        # Start the overlay and check for updates
        self.root.after(500, self.check_updates)  # Check for updates every 100 ms
        self.root.after(self.duration * 1000, self.root.destroy)  # Close after duration
        self.root.mainloop()

    def check_updates(self):
        try:
            while True:  # Check all items in the queue
                txt = self.update_queue.get(timeout=0.5)
                self.update_text(txt)
                time.sleep(0.01)
        except queue.Empty:
            pass  # No updates in the queue
        finally:
            self.root.after(500, self.check_updates)  # Schedule next check

    def update_text(self, text):
        # Replace the current text with the new number pressed
        if self.text_var.get() != text:
            self.text_var.set(text)
        
    def get_current_text(self):
        # Get the current text from the overlay
        return self.text_var.get()

def load_devices_from_config(config_file):
    config = configparser.ConfigParser()
    config.read(config_file)
    devices = {}
    # Load selected devices from config
    for device_name, device_path in config['Devices'].items():
        devices[device_name] = device_path
    return devices

def on_key_event(key,devices):
    # Stop the listener as soon as any key is pressed
    global grabbed_devices
    reconnect_devices(grabbed_devices)
    return False  # Returning False stops the listener
    
def wait_for_keypress_old():
    # Start the listener, it will stop when a key is pressed
    devices = set(evdev.list_devices())
    with keyboard.Listener(on_press=lambda key: on_key_event(key, devices)) as listener:
        listener.join()  # Block until the listener stops

def http_request(command,data):
    url = f"http://{hostname}:{port}/{command}"
    print(url)
    print(data)
    response = requests.post(url, data=data)
    print(f"Status code: {response.status_code}")

def overlay_text(update_queue, text):
    global overlay_thread
    if len(text) > 37:
        text = f"{text[:37]}..."
    if overlay_thread.is_alive():
        #print(overlay_thread)
        update_queue.put(text)  # Put the number in the queue to be processed by the overlay app
    else:
        overlay_thread = threading.Thread(target=OverlayApp, args=(args.time, text, update_queue))
        overlay_thread.start()

def keypress_listener_evdev(overlay_app, update_queue, devices):
    global last_pressed
    global overlay_thread
    """Listen for number key presses from the remote using evdev."""
    remote_devices = {}
    
    # Initialize InputDevice for each device in the config
    connection = False
    while connection is False:
        for device_name, device_path in devices.items():
            try:
                remote_device = InputDevice(device_path)
                remote_devices[device_name] = remote_device
                print(f"Using device: {device_name} at {device_path}")
                connection = True
            except Exception as e:
                print(f"Failed to open device {device_name} at {device_path}: {e}")
        if connection is False:
            keycode = wait_for_keypress()
        else:
            time.sleep(1)
    # Grab the devices to capture keypresses exclusively
    for device in remote_devices.values():
        device.grab()

    try:
        # Listen for events from all remote devices
        while True:
            for device in remote_devices.values():
                try:
                    for event in device.read():  # Attempt to read events
                        if event.type == ecodes.EV_KEY:  # Handle only key events
                            key_event = categorize(event)
                            if key_event.keystate == key_event.key_down:
                                keycode = key_event.keycode
                                print(keycode)
                                # Check if the key is a number
                                if keycode.startswith('KEY_'):
                                    if keycode.split('_')[-1].isdigit():  
                                        
                                        if last_pressed is not None:
                                            if last_pressed[-1] == "-":
                                                number_pressed = f"{last_pressed[0]}{int(keycode[-1])}"
                                                
                                                last_pressed = None
                                            else:
                                                number_pressed = f"{int(keycode[-1])}-"
                                                last_pressed = number_pressed
                                        else:
                                            number_pressed = f"{int(keycode[-1])}-"
                                            last_pressed = number_pressed

                                        overlay_text(update_queue, number_pressed)
                                            
                                        if last_pressed is None:
                                            http_request("start_beehive",f"{number_pressed},{drone}")
                                            time.sleep(2)
                                            response = requests.get(f"http://{hostname}:{port}/live")
                                            try:
                                                if response.status_code == 200:
                                                    data = response.json()
                                                    for device, live_data in data.items():
                                                        if device == drone:
                                                            #display_text = f"{int(live_data['channel']):02}   {live_data['title'].upper()}"
                                                            display_text = f"{int(number_pressed):02}   {live_data['title'].upper()}"
                                                else:
                                                    display_text = f"ERROR {response.status_code}"
                                            except requests.exceptions.RequestException as e:
                                                initial_text = f"ERROR {e}"
                                            overlay_text(update_queue, display_text)

                                    elif keycode == keymap['stop']:
                                        http_request("stop_beehive",drone)
                                    elif keycode == keymap['ch_up'] or keycode == keymap['ch_down']:
                                        response = requests.get(f"http://{hostname}:{port}/live")
                                        if response.status_code == 200:
                                            data = response.json()
                                            for device, live_data in data.items():
                                                if device == drone:
                                                    current_channel = int(live_data.get('channel'))
                                                    if keycode == keymap['ch_up']:
                                                        next_channel = current_channel+1
                                                    elif keycode == keymap['ch_down']:
                                                        next_channel = abs(current_channel-1)
                                                    
                                                    overlay_text(update_queue, f"{int(next_channel):02}")

                                                    http_request("start_beehive",f"{next_channel},{drone}")
                                                    time.sleep(2)
                                                    response = requests.get(f"http://{hostname}:{port}/live")

                                                    if response.status_code == 200:
                                                        data = response.json()
                                                        for device, live_data in data.items():
                                                            if device == drone:
                                                                display_text = f"{int(live_data['channel']):02}   {live_data['title'].upper()}"
                                                    else:
                                                        display_text = f"ERROR {response.status_code}"
                                                    overlay_text(update_queue, display_text)
                                    elif keycode == keymap['vol_up'] or keycode == keymap['vol_down']:
                                        # Get current volume
                                        response = requests.get(vlc_url, auth=auth)
                                        if response.status_code == 200:
                                            xml_data = response.content
                                            root = ET.fromstring(xml_data)
                                            
                                            # Find the volume element in the XML and print it
                                            volume = root.find('volume')
                                            if volume is not None:
                                                current_volume = int(volume.text)
                                            if keycode == keymap['vol_up']:
                                                new_volume = current_volume + 5
                                            elif keycode == keymap['vol_down']:
                                                new_volume = current_volume - 5
                                            set_volume_url = f"http://{vlc_host}:{vlc_port}/requests/status.xml?command=volume&val={new_volume}"
                                            vol_response = requests.get(set_volume_url, auth=auth)

                                            if vol_response.status_code == 200:
                                                overlay_text(update_queue, f"Vol. {round(new_volume/512*100)}%")
                except BlockingIOError:
                    # If the resource is temporarily unavailable, continue to the next device
                    continue
                except OSError as e:
                    print(f"ERROR: {e}")
                    connection = False
                    for device_name, device_path in devices.items():
                        try:
                            remote_device = InputDevice(device_path)
                            remote_devices[device_name] = remote_device
                            print(f"Using device: {device_name} at {device_path}")
                            connection = True
                        except Exception as e:
                            print(f"Failed to open device {device_name} at {device_path}: {e}")
                    if connection is False:
                        keycode = wait_for_keypress()
                    else:
                        time.sleep(1)
                    continue
            time.sleep(0.01)
    finally:
        # Release the devices when done
        for device in remote_devices.values():
            try:
                device.ungrab()
            except OSError:
                pass

# Function to grab all available input devices
def grab_all_devices():
    grabbed_devices = {}
    devices = [InputDevice(path) for path in list_devices()]
    
    for device in devices:
        try:
            device.grab()  # Attempt to grab the device for exclusive access
            grabbed_devices[device.path] = device
            print(f"Grabbed device: {device.name} at {device.path}")
        except Exception as e:
            print(f"Failed to grab device {device.name} at {device.path}: {e}")
    
    return grabbed_devices

# Function to release all grabbed devices
def ungrab_all_devices(grabbed_devices):
    for device in grabbed_devices.values():
        try:
            device.ungrab()
            print(f"Released device: {device.name} at {device.path}")
        except OSError as e:
            print(f"Failed to release device {device.name} at {device.path}: {e}")

# Function to reconnect devices if they become available again
def reconnect_devices(x=False):
    global grabbed_devices
    available_devices = list_devices()
    
    for device_path in available_devices:
        if device_path not in grabbed_devices:
            try:
                new_device = InputDevice(device_path)
                new_device.grab()
                grabbed_devices[device_path] = new_device
                print(f"Connected and grabbed device: {new_device.name} at {new_device.path}")
            except Exception as e:
                print(f"Failed to reconnect device at {device_path}: {e}")
                pass

def detect_new_devices():
    global grabbed_devices
    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem='input')  # Watch only input devices (keyboards, mice, etc.)

    print("Monitoring input devices...")
    for device in iter(monitor.poll, None):  # This is a blocking call that waits for events
        if device.action == 'add':  # Event is triggered when a new device is added
            print(f"New device added")
            break
    # Handle new device
    ungrab_all_devices(grabbed_devices)
    grabbed_devices = grab_all_devices()
    reconnect_devices()

# Function to start the monitoring thread
def start_device_monitor():
    device_thread = threading.Thread(target=detect_new_devices)
    device_thread.daemon = True  # Ensures the thread exits when the main program ends
    device_thread.start()

def wait_for_keypress():
    global grabbed_devices
    go = True
    while go is True:
        delete_devices = []
        reconnect_devices()
        for path, device in grabbed_devices.items():
            try:
                for event in device.read():
                    if event.type == ecodes.EV_KEY:
                        print(f"Key press detected on {device.name}: {categorize(event)}")
                        key_event = categorize(event)
                        on_key_event(key_event, grabbed_devices)
                        
                        if key_event.keystate == key_event.key_down:
                            keycode = key_event.keycode
                            print(keycode)
                            return keycode
            except BlockingIOError:
                continue  # No data available, continue polling
            except OSError:
                print(f"Device disconnected: {device.name}")
                delete_devices.append(path)  # Remove disconnected device
        for deldev in delete_devices:
            #print(grabbed_devices)
            del grabbed_devices[deldev]
            delete_devices.remove(deldev)

        time.sleep(1)  # Reduce CPU usage

def get_key_event(devices, blocking=False):
    return wait_for_keypress()
    while True:
        if blocking is True:
            print("Waiting for keypress")
            keycode = wait_for_keypress()
        for device in list(devices.values()):
            try:
                for event in device.read():  # Attempt to read events
                    if event.type == ecodes.EV_KEY:  # Handle only key events
                        key_event = categorize(event)
                        if key_event.keystate == key_event.key_down:
                            keycode = key_event.keycode
                            print(keycode)
                            return keycode
            except BlockingIOError as e:
                # If the resource is temporarily unavailable, continue to the next device
                #print("BlockingIOError",e,end='\r')
                time.sleep(0.05)
                continue
            except OSError as e:
                # Handle device disconnection
                #print(f"Device {device.name} at {device.path} disconnected: {e}")
                try:
                    device.ungrab()
                except:
                    pass
                del devices[device.path]  # Remove disconnected device from the list
                keycode = wait_for_keypress()
                time.sleep(0.05)
    time.sleep(0.01)
    
def element_to_dict(element):
    """Recursively convert an XML element and its children into a dictionary."""
    result = {}

    # If the element has children, process them
    if list(element):
        # Create a dict for the children
        for child in element:
            child_dict = element_to_dict(child)
            if child.tag not in result:
                result[child.tag] = child_dict
            else:
                # If the tag already exists, store it as a list of elements
                if isinstance(result[child.tag], list):
                    result[child.tag].append(child_dict)
                else:
                    result[child.tag] = [result[child.tag], child_dict]
    else:
        # If the element has no children, just get its text
        result = element.text
            
def process_key_events(keymap):
    global last_pressed
    global last_volume
    global subtitle_track
    global audio_track
    global video_track
    global aspect_ratio
    global grabbed_devices
    max_channels = os.environ.get('MAX_CHANNELS','999')
    DESIRED_DIGITS = len(max_channels)
    digit_buffer = []  # To store the pressed digits
    while True:
        reconnect_devices(grabbed_devices)
        keycode = get_key_event(grabbed_devices)
        # Check if the key is a number
        
        if keycode is not None:
            if isinstance(keycode, str):
                if keycode.split('_')[-1].isdigit():  
                    # Add the digit to the buffer
                    digit_buffer.append(keycode.split('_')[-1])

                    # Combine the current digits into a partial number
                    partial_number = ''.join(digit_buffer)

                    while len(partial_number) < DESIRED_DIGITS:
                        partial_number += "-"
                    overlay_text(update_queue, partial_number)
                    # If the buffer has the desired number of digits, process them
                    if len(digit_buffer) == DESIRED_DIGITS:
                        # Clear the buffer for the next input
                        digit_buffer = []
                        number_pressed = partial_number
                        http_request("start_beehive",f"{number_pressed},{drone}")
                        time.sleep(4)
                        response = requests.get(f"http://{hostname}:{port}/live")
                        try:
                            if response.status_code == 200:
                                data = response.json()
                                for device, live_data in data.items():
                                    if device == drone:
                                        #display_text = f"{int(live_data['channel']):02}   {live_data['title'].upper()}"
                                        display_text = f"{int(number_pressed):02}   {live_data['title'].upper()}"
                            else:
                                display_text = f"ERROR {response.status_code}"
                        except requests.exceptions.RequestException as e:
                            initial_text = f"ERROR {e}"
                        overlay_text(update_queue, display_text)

            if keycode == keymap['stop']:
                http_request("stop_beehive",drone)
            elif keycode == keymap['ch_up'] or keycode == keymap['ch_down']:
                response = requests.get(f"http://{hostname}:{port}/live")
                if response.status_code == 200:
                    data = response.json()
                    for device, live_data in data.items():
                        if device == drone:
                            current_channel = int(live_data.get('channel'))
                            if keycode == keymap['ch_up']:
                                next_channel = current_channel+1
                            elif keycode == keymap['ch_down']:
                                next_channel = abs(current_channel-1)
                            
                            overlay_text(update_queue, f"{int(next_channel):02}")

                            http_request("start_beehive",f"{next_channel},{drone}")
                            time.sleep(2)
                            response = requests.get(f"http://{hostname}:{port}/live")

                            if response.status_code == 200:
                                data = response.json()
                                for device, live_data in data.items():
                                    if device == drone:
                                        display_text = f"{int(live_data['channel']):02}   {live_data['title'].upper()}"
                            else:
                                display_text = f"ERROR {response.status_code}"
                            overlay_text(update_queue, display_text)
            elif keycode == keymap['vol_up'] or keycode == keymap['vol_down']:
                # Get current volume
                response = requests.get(vlc_url, auth=auth)
                if response.status_code == 200:
                    root = json.loads(response.content.decode('utf-8'))
                    #xml_data = response.content
                    #root = ET.fromstring(xml_data)
                    
                    # Find the volume element in the XML and print it
                    volume = root.get('volume')
                    if volume is not None:
                        current_volume = volume
                    if keycode == keymap['vol_up']:
                        new_volume = current_volume + 5
                    elif keycode == keymap['vol_down']:
                        new_volume = current_volume - 5
                    set_volume_url = f"http://{vlc_host}:{vlc_port}/requests/status.xml?command=volume&val={new_volume}"
                    vol_response = requests.get(set_volume_url, auth=auth)

                    if vol_response.status_code == 200:
                        overlay_text(update_queue, f"Vol. {round(new_volume/512*100)}%")
            elif keycode == keymap['mute']:
                # Get current volume
                response = requests.get(vlc_url, auth=auth)
                if response.status_code == 200:
                    root = json.loads(response.content.decode('utf-8'))
                    #xml_data = response.content
                    #root = ET.fromstring(xml_data)
                    
                    # Find the volume element in the XML and print it
                    volume = root.get('volume')
                    if volume is not None:
                        current_volume = volume
                    if current_volume != 0:
                        new_volume = 0
                        last_volume = current_volume
                    else:
                        new_volume = last_volume
                    set_volume_url = f"http://{vlc_host}:{vlc_port}/requests/status.xml?command=volume&val={new_volume}"
                    vol_response = requests.get(set_volume_url, auth=auth)

                    if vol_response.status_code == 200:
                        if new_volume != 0:
                            overlay_text(update_queue, f"Vol. {round(new_volume/512*100)}%")
                        else:
                            overlay_text(update_queue, f"MUTE")
            elif keycode == keymap['cycle_sub_lang']:
                response = requests.get(vlc_url, auth=auth)
                if response.status_code == 200:
                    root = json.loads(response.content.decode('utf-8'))
                    #xml_data = response.content
                    #root = ET.fromstring(xml_data)
                    
                    information = root.get('information')
                    if information is not None:
                        #information = element_to_dict(information_element)
                        #print(json.dumps(information,indent=4))
                        category = information.get('category')
                        subtitle_tracks = ["-1"]
                        if category is not None:
                            #print(json.dumps(category,indent=4))
                            for c, c_data in category.items():
                                if "stream" in c.lower() and c_data.get("Type") == "Subtitle":
                                    subtitle_tracks.append(c.split(" ")[1])
                        if len(subtitle_tracks) <= 1:
                            overlay_text(update_queue, f"Subtitles Not Available")
                        else:
                            if subtitle_track is None:
                                subtitle_track = subtitle_tracks[0]
                            else:
                                current_index = subtitle_tracks.index(subtitle_track)
                                if subtitle_tracks[current_index] == subtitle_tracks[-1]:
                                    subtitle_track = subtitle_tracks[0]
                                else:
                                    subtitle_track = subtitle_tracks[current_index+1]
                            if subtitle_track is not None:
                                set_url = f"http://{vlc_host}:{vlc_port}/requests/status.json?command=subtitle_track&val={subtitle_track}"
                                if subtitle_track == "-1":
                                    language = "Off"
                                else:
                                    language = information['category'][f"Stream {subtitle_track}"].get('Language', 'On') +' '+ information['category'][f"Stream {subtitle_track}"].get('Description', '')
                            else:
                                set_url = f"http://{vlc_host}:{vlc_port}/requests/status.json?command=subtitle_track&val=-1"
                                language = "Off"
                            sub_response = requests.get(set_url, auth=auth)

                            if sub_response.status_code == 200:
                                overlay_text(update_queue, f"Subtitles {language}")
            elif keycode == keymap['cycle_audio_track']:
                response = requests.get(vlc_url, auth=auth)
                if response.status_code == 200:
                    root = json.loads(response.content.decode('utf-8'))
                    
                    information = root.get('information')
                    if information is not None:
                        category = information.get('category')
                        audio_tracks = []
                        if category is not None:
                            for c, c_data in category.items():
                                if "stream" in c.lower() and c_data.get("Type") == "Audio":
                                    audio_tracks.append(c.split(" ")[1])
                        if len(audio_tracks) <= 1:
                            overlay_text(update_queue, f"Audio Select Not Available")
                        else:
                            if audio_track is None:
                                audio_track = audio_tracks[0]
                            else:
                                current_index = audio_tracks.index(audio_track)
                                if audio_tracks[current_index] == audio_tracks[-1]:
                                    audio_track = audio_tracks[0]
                                else:
                                    audio_track = audio_tracks[current_index+1]
                            set_url = f"http://{vlc_host}:{vlc_port}/requests/status.xml?command=audio_track&val={audio_track}"
                            if audio_track is not None:
                                language = information['category'][f"Stream {audio_track}"].get('Language', None) +' '+ information['category'][f"Stream {audio_track}"].get('Description', '')
                            else:
                                language = "Select Not Available"
                            sub_response = requests.get(set_url, auth=auth)

                            if sub_response.status_code == 200:
                                overlay_text(update_queue, f"Audio {language}")
            elif keycode == keymap['cycle_video_track']:
                response = requests.get(vlc_url, auth=auth)
                if response.status_code == 200:
                    root = json.loads(response.content.decode('utf-8'))
                    
                    information = root.get('information')
                    if information is not None:
                        category = information.get('category')
                        video_tracks = []
                        if category is not None:
                            for c, c_data in category.items():
                                if "stream" in c.lower() and c_data.get("Type") == "Video":
                                    video_tracks.append(c.split(" ")[1])
                        if len(video_tracks) <= 1:
                            overlay_text(update_queue, f"Video Select Not Available")
                        else:
                            if video_track is None:
                                video_track = video_tracks[0]
                            else:
                                current_index = video_tracks.index(video_track)
                                if video_tracks[current_index] == video_tracks[-1]:
                                    video_track = video_tracks[0]
                                else:
                                    video_track = video_tracks[current_index+1]
                            set_url = f"http://{vlc_host}:{vlc_port}/requests/status.xml?command=video_track&val={video_track}"
                            if video_track is not None:
                                language = information['category'][f"Stream {video_track}"].get('Language', None)
                            else:
                                language = "Select Not Available"
                            sub_response = requests.get(set_url, auth=auth)

                            if sub_response.status_code == 200:
                                overlay_text(update_queue, f"Video {language}")
            elif keycode == keymap['cycle_aspect_ratio']:
                response = requests.get(vlc_url, auth=auth)
                if response.status_code == 200:
                    root = json.loads(response.content.decode('utf-8'))
                    aspect_ratios = ['default','1:1','4:3','5:4','16:9','16:10','221:100','235:100','239:100']
                    if aspect_ratio is None:
                        aspect_ratio = root.get('aspectratio')
                    else:
                        current_index = aspect_ratios.index(aspect_ratio)
                        if aspect_ratios[current_index] == aspect_ratios[-1]:
                            aspect_ratio = aspect_ratios[0]
                        else:
                            aspect_ratio = aspect_ratios[current_index+1]
                    set_url = f"http://{vlc_host}:{vlc_port}/requests/status.xml?command=aspectratio&val={aspect_ratio}"
                    sub_response = requests.get(set_url, auth=auth)

                    if sub_response.status_code == 200:
                        overlay_text(update_queue, f"Aspect Ratio {aspect_ratio}")
            elif keycode == keymap['display']:
                response = requests.get(f"http://{hostname}:{port}/live")
                display_text = ''
                try:
                    if response.status_code == 200:
                        data = response.json()
                        for device, live_data in data.items():
                            if device == drone:
                                display_text = f"{int(live_data['channel']):02}   {live_data['title'].upper()}"
                    else:
                        display_text = f"ERROR {response.status_code}"
                except requests.exceptions.RequestException as e:
                    display_text = f"ERROR {e}"
                overlay_text(update_queue, display_text)
        time.sleep(0.01)

def generate_keymap(update_queue, devices):
    keymap = {}
    actions = {
        'vol_up': 'Volume Up',
        'vol_down': 'Volume Down',
        'ch_up': 'Channel Up',
        'ch_down': 'Channel Down',
        'mute': 'Mute',
        'last_ch': 'Last Channel',
        'stop': 'Stop Playback',
        'cycle_sub_lang': 'Cycle Subtitle Language',
        'cycle_audio_track': 'Cycle Audio Track',
        'cycle_video_track': 'Cycle Video Track',
        'cycle_aspect_ratio': 'Cycle Aspect Ratio',
        'display': 'Info Display',
    }

    for action, prompt in actions.items():
        overlay_text(update_queue, f"Press key for {prompt}")
        keycode = None
        #devices = grab_all_devices()
        reconnect_devices(devices)
        keycode = get_key_event(devices)
        keymap[action] = keycode
        overlay_text(update_queue, f"{prompt} set to {keycode}")
        time.sleep(2)  # Give the user a brief moment before the next prompt        
    overlay_text(update_queue, "Key mapping completed and saved.")
    # Save keymap to file
    with open("keymap.json", "w") as f:
        json.dump(keymap, f, indent=4)

    overlay_text(update_queue, "Key mapping saved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BEE-TV Overlay")
    response = requests.get(f"http://{hostname}:{port}/live")
    initial_text = ''
    try:
        if response.status_code == 200:
            data = response.json()
            for device, live_data in data.items():
                if device == drone:
                    initial_text = f"{int(live_data['channel']):02}   {live_data['title'].upper()}"
        else:
            initial_text = f"ERROR {response.status_code}"
    except requests.exceptions.RequestException as e:
        initial_text = f"ERROR {e}"

    parser.add_argument('time', type=int, help='Time to display the label for')
    args = parser.parse_args()

    update_queue = queue.Queue()  # Create a queue for communication between threads

    # Load devices from the config file
    #devices = load_devices_from_config('devices_config.ini')
    
    # Start the overlay in a separate thread
    overlay_thread = threading.Thread(target=OverlayApp, args=(args.time, initial_text, update_queue))
    overlay_thread.start()

    # Step 1: Grab all input devices
    grabbed_devices = grab_all_devices()

    #start_device_monitor()

    if not os.path.exists('keymap.json'):
        generate_keymap(update_queue, grabbed_devices)
        
    with open('keymap.json','r') as keymap_file:
        keymap = json.load(keymap_file)
        print(keymap)

    try:
        # Step 2: Listen for keypresses using evdev
        process_key_events(keymap)
    finally:
        # Step 3: Release all devices when done
        ungrab_all_devices(grabbed_devices)
