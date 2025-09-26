import ast
import collections
import configparser
import datetime
import html
import io
import importlib
import json
import math
import os
import psutil
import pycountry
import secrets
import shutil
import subprocess
import sys
import threading
import unicodedata
from datetime import timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify, send_file, send_from_directory, Response
from flask_socketio import SocketIO, emit
from pathlib import Path

#import scheduler
app = Flask(__name__)
socketio = SocketIO(app)
# Custom stream to capture print statements
class SocketIOOutput(io.StringIO):
    def __init__(self, sid):
        super().__init__()
        self.sid = sid

    def write(self, data):
        if data.strip():  # Ignore empty lines
            socketio.emit('process_output', {'data': data.strip(), 'return': False}, room=self.sid)
        super().write(data)




global_output_buffer = io.StringIO()

config_file = 'config.ini'
config = configparser.ConfigParser()
config.optionxform = str
config.read(os.path.abspath(f"./{config_file}"))
drones_file = 'drones.ini'
drones = configparser.ConfigParser()
drones.optionxform = str
drones.read(os.path.abspath(f"./{drones_file}"))

live_file = 'live.json'

script_directory = os.path.dirname(os.path.abspath(__file__))
CHANNELS_DIR='channels'
LIBRARY_DIR = 'library'
running_process_output = {}
pid_file = os.path.join(script_directory, 'live', 'process.pid')
log_file = os.path.join(script_directory, 'live', 'process.log')
os.chdir(script_directory)

client_sids = {}
@socketio.on('register')
def handle_register(data):
    client_sids[request.sid] = request.sid
    print(f"Registered client SID: {request.sid}")
    
app.secret_key = secrets.token_hex(16)
# Check if a secret key exists
if 'SECRET_KEY' not in app.config:
    # If not, generate one
    secret_key = secrets.token_hex(16)

    # Set the secret key in the app configuration
    app.config['SECRET_KEY'] = secret_key
    app.secret_key=secret_key

def update_config(config_path, config_dict):
    """
    Updates a configuration file with the specified section, option, and value.
    Creates the section if it doesn't exist.

    Args:
        config_path (str): Path to the configuration file.
        section (str): Name of the section to update.
        option (str): Option (key) to update or add.
        value (str): Value to set for the specified option.

    Returns:
        bool: True if the update is successful, False if an error occurs.
    """
    # Read the config file
    if config_path == "config.ini":
        parser = config
    elif config_path == "drones.ini":
        parser = drones
    else:
        parser = configparser.ConfigParser()
        parser.read(config_path)
    
    for section, options in config_dict.items():
        for option, value in options.items():
            try:
                # Add the section if it doesn't exist
                if not parser.has_section(section):
                    parser.add_section(section)

                # Set the option value
                parser.set(section, option, value)

                print(f"Updated {section} -> {option} = {value} in {config_path}")

            except Exception as e:
                print(f"Error updating config file: {e}")
    # Write changes back to the file
    with open(config_path, "w") as configfile:
        parser.write(configfile)

# Function to get a list of available template files
def get_template_files():
    template_dir = 'channel_templates'
    if not os.path.exists(template_dir):
        os.makedirs(template_dir)
    return [f for f in os.listdir(template_dir) if f.endswith('.json')]
template_files = get_template_files()
def get_available_channels():
    channels = []
    for dir_name in os.listdir(CHANNELS_DIR):
        channel_path = os.path.join(CHANNELS_DIR, dir_name)
        if os.path.isdir(channel_path):
            schedule_path = os.path.join(channel_path, 'schedule.json')
            if os.path.exists(schedule_path):
                channels.append(dir_name)
    return channels

# Function to load data from JSON file
def load_data(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        return data
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def read_live_file():
    """Utility function to safely read and parse the JSON file."""
    if not os.path.exists(live_file):
        return {}
    try:
        return load_data(live_file)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

shows_details = load_data(os.path.join(LIBRARY_DIR, 'shows_details.json'))
movies_details = load_data(os.path.join(LIBRARY_DIR, 'movies_details.json'))
    
# Function to save data to JSON file
def save_data(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)# Function to load data from JSON file

# Function to get a list of channels
def get_channels():
    channels_dir = 'channels'
    return [d for d in os.listdir(channels_dir) if os.path.isdir(os.path.join(channels_dir, d))]

def get_json_files():
    channels_dir = 'channels'
    json_files = []
    for channel in os.listdir(channels_dir):
        channel_path = os.path.join(channels_dir, channel)
        if os.path.isdir(channel_path):
            for file in os.listdir(channel_path):
                if file.endswith('.json'):
                    json_files.append(os.path.join(channel, file))
    return json_files

def remove_accents(input_str):
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([char for char in nfkd_form if not unicodedata.combining(char)])

def convert_language_tag(tag):
    # Convert ISO 639-1 to ISO 639-2
    if len(tag) == 2:
        lang = pycountry.languages.get(alpha_2=tag)
        return lang.alpha_3 if lang else None

    # Convert ISO 639-2 to ISO 639-1
    elif len(tag) == 3:
        lang = pycountry.languages.get(alpha_3=tag)
        return lang.alpha_2 if lang else None

    return None

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    scan = False
    titlefontsize=''
    if request.method == 'POST':
        scan_value = request.form.get('scan', 'false')
        scan = scan_value.lower() == "true"
        # Save changes to file
        request_form = {}
        for k,v in request.form.items():
            try:
                s,o = k.split('_')
                s = s.replace('-',' ')
                o = o.replace('-',' ')
            except:
                s = k.replace('-',' ')
                o = k.replace('-',' ')
            try:
                request_form[s][o] = v
            except KeyError:
                request_form[s] = {}
                request_form[s][o] = v
        #print(json.dumps(request_form,indent=4))
        try:
            update_config(config_file, request_form)
            flash(f'Changes to {config_file} saved successfully!', 'success')
        except Exception as e:
            flash(f'Error saving config file: {e}', 'error')

    html_string = '<form action="/settings" method="post">'
    try:
        # Iterate through each section
        #print(json.dumps(config.sections(),indent=4))
        for section in config.sections():
            if section.lower() == 'content' or section.lower() == 'interstitials' or section.lower() == 'fresh content settings' or section.lower() == 'scan':
                continue
            #print(f"[{section}]")  # Print the section name
            divname = section.replace(' ','-')
            html_string += f'<tr><td onclick="toggleClass(\'{divname}\',\'hide\')"class="box fullspanx yellow">{section.upper()}</td><div></tr><tbody class="hide" name="{divname}" id="{divname}"><tr>'
            # Iterate through each option in the section
            printed = False
            for o, option in enumerate(config[section]):
                #print(o+1,option)
                end_row = False
                value = config[section][option]
                #print(f"{option.upper()} = {value}")  # Print option and its value
                if section.lower() == "settings":
                    entryspan = ''
                    issmall = ''
                    if option.lower() == "minimum channels":
                        comment = "Set this value to the minimum number of channels that should exist at any time. BEE will generate up to this many channels if not enough exist."
                        istall = "tall"
                        titlefontsize = "smallfont"
                    elif option.lower() == "advance days":
                        comment = "This value is the number of days in advance the daily schedule will be generated."
                    elif option.lower() == "library mount point":
                        comment = "Define the common mount point for all library directories here"
                        istall = ""
                        titlefontsize = "extrasmallfont"
                    elif option.lower() == "language":
                        comment = "Use ISO 639 language codes here to set the default language for playback"
                        titlefontsize = ""
                    elif option.lower() == "tmdb key":
                        comment = "Enter the API Key from TMDB here"
                        titlefontsize = ""
                        istall = ''
                        issmall = ''
                        entryspan = 'trispan'
                        end_row = True
                    elif option.lower() == "web ui port":
                        comment = "Enter the desired Web UI Port"
                        titlefontsize = ""
                        istall = ''
                        issmall = ''
                        entryspan = ''
                        end_row = True                        
                elif section.lower() == 'paths' or section.lower() == 'content' or section.lower() == 'interstitials':
                    if printed is False:
                        if section.lower() == 'paths':
                            html_string += f'<td class="box blue fullspanx smallfont">Enter the paths to each indicated directory. Separate multiple paths in a single entry with a comma.</td></tr>'
                        printed = True
                    comment = ''
                    titlefontsize = "extrasmallfont"
                    istall = ''
                    issmall = ''
                    entryspan = 'trispan'                    
                    end_row = True
            
                elif section.lower() == 'interstitial weight':
                    titlefontsize = ''
                    comment = ''
                    istall = ''
                    issmall = ''
                    entryspan = ''
                    if len(option) > 7:
                        titlefontsize = "smallfont"
                    if len(option) >= 12:
                        titlefontsize = "extrasmallfont"
                    if printed is False:
                        html_string += f'<td class="box blue fullspanx smallfont">These are the default values for weight applied to matching metadata for interstitial selection.</td></tr>'
                        printed = True           
                elif section.lower() == 'fresh content types':
                    titlefontsize = ''
                    comment = ''
                    istall = ''
                    issmall = ''
                    entryspan = ''
                    if len(option) > 7:
                        titlefontsize = "smallfont"
                    if len(option) >= 12:
                        titlefontsize = "extrasmallfont"
                    if printed is False:
                        html_string += f'<td class="box blue fullspanx smallfont">Indicate what supporting content types (such as trailers) will be downloaded for upcoming and in-theater movies.</td></tr>'
                        printed = True
                elif section.lower() == 'ratelimiter':
                    titlefontsize = ''
                    comment = ''
                    istall = ''
                    issmall = ''
                    entryspan = ''
                    if len(option) > 7:
                        titlefontsize = "smallfont"
                    if len(option) >= 12:
                        titlefontsize = "extrasmallfont"
                    if option.lower() == "showscan":
                        comment = "Maximum requests per second for show scanner"
                    elif option.lower() == "musicbrainz":
                        comment = "Wait time (seconds) between Musicbrainz requests"

                elif section.lower() == "openai settings":
                    
                    titlefontsize = ''
                    comment = ''
                    istall = ''
                    issmall = ''
                    entryspan = ''
                    if len(option) > 7:
                        titlefontsize = "smallfont"
                    if len(option) >= 12:
                        titlefontsize = "extrasmallfont"
                    
                    if option.lower() == "api key": 
                        # DISCLAIMER
                        html_string += f'<td style="height:auto" class="box fullspanx red">DISCLAIMER: The use of OpenAI tools ChatGPT and Whisper within this application is ENTIRELY OPTIONAL and enabled only if the user provides an OpenAI API key. These tools are designed to assist with processing and analyzing video files, but their accuracy cannot be guaranteed and may vary depending on the input and context. Enabling these tools will incur monetary costs based on OpenAI\'s API usage rates, as specified in their terms and conditions. Users are responsible for monitoring API usage and managing associated costs.</td></tr><tr>'
                        entryspan = ""
                        istall = ""
                        end_row = True
                        issmall = "extrasmallfont"
                        comment = "Enter the API Key from OpenAI here, leave blank to disable"
                    elif option.lower() == "gpt model":
                        comment = "Choose a model from the OpenAI gpt options"
                    elif option.lower() == "vision detail level":
                        comment = "A high setting may increase accuracy but will incur a higher cost. Default: low"
                    elif option.lower() == "seconds per image":
                        comment = "Per second frequency of frames sent to chatgpt for analysis. Default: 2"
                    elif option.lower() == "chatgpt input cost":
                        comment = "Pricing data for ChatGPT usage"
                    elif option.lower() == "chatgpt output cost":
                        comment = "Costs are calculated per token"
                    elif option.lower() == "whisper cost":
                        comment = "Cost per second of audio transcription"
                    elif option.lower() == "chatgpt role" or option.lower() == "chatgpt prompt":
                        continue
                else:
                    titlefontsize = ''
                    comment = ''
                    istall = ''
                    issmall = ''
                    entryspan = ''
                    if len(option) > 7:
                        titlefontsize = "smallfont"
                    if len(option) >= 12:
                        titlefontsize = "extrasmallfont"
                    
                    
                    if len(value) > 110:
                        issmall = 'smallfont'
                        if len(value) > 624:
                            issmall = 'extrasmallfont'

                if value.lower() in ["true", "false"]:  # Check for boolean
                    value_type = "bool"
                elif value.lower() in ["low", "high"]:  # Check for binary choice
                    value_type = "bin"
                elif value.isdigit():
                    value_type = "int"  # Check for integer
                elif value.replace('.', '', 1).isdigit() and value.count('.') == 1:
                    value_type = "float"
                else:
                    value_type = "str"
                if value_type == "bool":
                    entryspan = ""
                    if value.lower() == "true":
                        true_class = ""
                        false_class = "blue"
                    elif value.lower() == "false":
                        true_class = "blue"
                        false_class = ""
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td>'
                    html_string += f'<td id={option.replace(" ","-")}-True class="box {true_class} {istall} {issmall} {entryspan}" onclick="toggleDualClass(\'{option.replace(" ","-")}-True\',\'blue\',\'{option.replace(" ","-")}-False\',\'blue\',\'{option.replace(" ","-")}\',\'True\')">True</td>'
                    html_string += f'<td id={option.replace(" ","-")}-False class="box {false_class} {istall} {issmall} {entryspan}" onclick="toggleDualClass(\'{option.replace(" ","-")}-True\',\'blue\',\'{option.replace(" ","-")}-False\',\'blue\',\'{option.replace(" ","-")}\',\'False\')">False</td>'
                    html_string += f'<td class="box blue trispan {istall}" style="text-align: start;">{comment}</td>'
                    html_string += f'<input type="hidden" id="{section.replace(" ","-")}_{option.replace(" ","-")}" name="{section.replace(" ","-")}_{option.replace(" ","-")}" value="{value}">'
                    end_row = True
                elif value_type == "bin":
                    entryspan = ""
                    if value.lower() == "low":
                        true_class = ""
                        false_class = "blue"
                    elif value.lower() == "high":
                        true_class = "blue"
                        false_class = ""
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td>'
                    html_string += f'<td id={option.replace(" ","-")}-low class="box {true_class} {istall} {issmall} {entryspan}" onclick="toggleDualClass(\'{option.replace(" ","-")}-low\',\'blue\',\'{option.replace(" ","-")}-high\',\'blue\',\'{option.replace(" ","-")}\',\'low\')">low</td>'
                    html_string += f'<td id={option.replace(" ","-")}-high class="box {false_class} {istall} {issmall} {entryspan}" onclick="toggleDualClass(\'{option.replace(" ","-")}-low\',\'blue\',\'{option.replace(" ","-")}-high\',\'blue\',\'{option.replace(" ","-")}\',\'high\')">high</td>'
                    html_string += f'<td class="box blue trispan {istall}" style="text-align: start;">{comment}</td>'
                    html_string += f'<input type="hidden" id="{section.replace(" ","-")}_{option.replace(" ","-")}" name="{section.replace(" ","-")}_{option.replace(" ","-")}" value="{value}">'
                    end_row = True
                elif value_type == "str":
                    if option.lower() in ['library mount point','language','api key','gpt model']:
                        comment_span = "fourspan"
                    elif "folders" in option.lower() or "tmdb key" == option.lower():
                        comment_span = "doublespan"

                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td><td class="box blue {istall} {issmall} {entryspan}" style="text-align: start;"><input class="boxless blue {entryspan}" type="text" id="{section.replace(" ","-")}_{option.replace(" ","-")}" name="{section.replace(" ","-")}_{option.replace(" ","-")}" value="{value}"></input></td><td class="box blue {comment_span} {istall}" style="text-align: start;">{comment}</td>'
                elif value_type == "int":
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td><td class="box blue {istall} {issmall} {entryspan}" style="text-align: start;"><input class="boxless blue {entryspan}" type="number" id="{section.replace(" ","-")}_{option.replace(" ","-")}" name="{section.replace(" ","-")}_{option.replace(" ","-")}" value="{value}"></input></td><td class="box blue fourspan {istall}" style="text-align: start;">{comment}</td>'
                elif value_type == "float":
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td><td class="box blue {istall} {issmall} {entryspan}" style="text-align: start;"><input class="boxless blue {entryspan}" type="number" step="{value.replace(value[-1],"1")}" id="{section.replace(" ","-")}_{option.replace(" ","-")}" name="{section.replace(" ","-")}_{option.replace(" ","-")}" value="{value}"></input></td><td class="box blue fourspan {istall}" style="text-align: start;">{comment}</td>'
                else:
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td><td class="box blue {istall} {issmall} {entryspan}" style="text-align: start;">{value}</td><td class="box blue fullspan {istall}" style="text-align: start;">{comment}</td>'
                if end_row is False:
                    html_string += f'</tr>'
                else:
                    html_string += '</tr>'
            html_string += '</tbody>'
        html_string += '<tr><input type="hidden" name="scan" id="scan" value=""><td class="box firstcolumn"></td><td class="box doublespan"><button class="boxless doublespan yellow" type="submit" onclick="document.getElementById(\'scan\').value=\'false\'">SAVE CHANGES</button></td><td class="box trispan"><button class="boxless trispan yellow" type="submit" onclick="document.getElementById(\'scan\').value=\'true\'">SAVE AND SCAN LIBRARY</button></td></tr></form>'
    except Exception as e:
        print(f"Error reading config file: {e}")
        flash(f'Error reading client config file: {e}', 'error')
    return render_template('settings.html', html_string=html_string, config_file=config_file,live_onload = live_load(), scanned=scanners(scan))

def scanners(scan=True):
    if scan is True:
        scanners = ["scan_movies", "scan_shows", "scan_interstitials"]
        for scanner in scanners:
            if scanner in sys.modules:
                scanner_module = importlib.reload(sys.modules[scanner])
            else:
                scanner_module = importlib.import_module(scanner)
            scanner_module.main()
    return scan

@app.route('/remoteservicegen',  methods=['GET'])
def remoteservicegen():
    
    drone = request.args.get('address')
    port = request.args.get('port')
    password = request.args.get('password')
    user = request.args.get('user')
    if not drone: 
        return "Missing required parameters: drone", 400  # Return error if missing parameters
    if not port:
        return "Missing required parameters: port", 400  # Return error if missing parameters
    if not password:
        return "Missing required parameters: password", 400  # Return error if missing parameters
    if not user or user == "None":
        user = "<USER>"

    # Debug: Print the parameters to the server logs
    print(f"drone: {drone}, port: {port}, password: {password}, user: {user}")

    # Define the content of the .service file
    service_content = f"""[Unit]
Description=BROADCAST EMULATION ENGINE REMOTE INTERFACE
[Service]
Environment=DISPLAY=:0
Environment=HOST={request.host.split(':')[0]}
Environment=PORT={request.host.split(':')[1]}
Environment=DRONE={drone}
Environment=FONT="Prevue C"
Environment=COLOR=lime
Environment=BG=black
Environment=SIZE=50
Environment=X_POS=300
Environment=Y_POS=60
Environment=VLCPORT={port}
Environment=VLCPASS={password}
ExecStart=/usr/bin/python /home/{user}/drone.py 20
Restart=always
CPUQuota=35%
[Install]
WantedBy=default.target
    """
    # Return the response with headers for download
    return Response(
        service_content,
        mimetype='text/plain',
        headers={
            'Content-Disposition': 'attachment; filename="remote.service"'
        }
    )

@app.route('/vlcservicegen',  methods=['GET'])
def vlcservicegen():
    
    port = request.args.get('port')
    password = request.args.get('password')
    
    # Define the content of the .service file
    service_content = f"""[Unit]
Description=BROADCAST EMULATION ENGINE CLIENT
[Service]
Environment=DISPLAY=:0
ExecStart=/usr/bin/vlc --intf http --no-osd --http-port {port} --fullscreen --audio-language=eng --no-spu --vout=x11 --http-password={password} --sout-keep --avcodec-hw=any --file-caching=10000 --volume-save --audio-filter=stereo --play-and-pause
Restart=always
[Install]
WantedBy=default.target
    """
    # Create a response with the content
    return Response(service_content, mimetype='text/plain')

@app.route('/drones', methods=['GET', 'POST'])
def clients():
    
    if request.method == 'POST':
        if request.form.get('action') == "save":
            # Save changes to file
            print("SAVE INITIATED")
            print(json.dumps(request.form,indent=4))
            request_form = {}
            for o,v in request.form.items():
                if o == 'client-name':
                    s = request.form[o]
                    if s == '':
                        break
                    else:
                        continue
                elif o == 'action':
                    continue
                try:
                    request_form[s][o.replace('-',' ')] = v
                except KeyError:
                    request_form[s] = {}
                    request_form[s][o.replace('-',' ')] = v
            #print(json.dumps(request_form,indent=4))
            try:
                update_config(drones_file, request_form)
                flash(f'Changes to {s} saved successfully!', 'success')
            except:
                flash('Changes not saved.', 'error')
        elif request.form.get('action') == "delete":
            print("DELETE INITIATED")
            print(json.dumps(request.form,indent=4))
            section_name = request.form['client-name']
            try:
                if drones.has_section(section_name):
                    drones.remove_section(section_name)
                    with open(drones_file, 'w') as dronesfile:
                        drones.write(dronesfile)
                    flash(f'{section_name} successfully deleted.', 'success')
                else:
                    flash(f'{s} not found in {dronesfile}.', 'error')
            except:
                flash('Changes not saved.', 'error')
        pass
    html_string = ''
    try:
        # Iterate through each section
        for section in drones.sections():
            #print(f"[{section}]")  # Print the section name
            html_string += '<form action="/drones" method="post"><tr><td class="box firstcolumn">'
            html_string += f'<td class="box fullspan">{section.upper()}</td><input type="hidden" id="client-name" name="client-name" value={section}></tr>'
            # Iterate through each option in the section
            for o, option in enumerate(drones[section]):
                istall = ''
                issmall = ''
                comment = ''
                if len(option) > 11:
                    istall = 'tall'
                value = drones[section][option]
                if option.lower() == "address":
                    comment = "Hostname or IP address"
                elif option.lower() == "port":
                    comment = "VLC HTTP Port"
                elif option.lower() == "password":
                    comment = "VLC HTTP Password"
                elif option.lower() == "library mount point":
                    comment = "Directory path of the mount point of the media library network share."
                #print(f"{option.upper()} = {value}")  # Print option and its value
                if len(value) > 110:
                    issmall = 'smallfont'
                    if len(value) > 624:
                        issmall = 'extrasmallfont'
                html_string += f'<tr><td class="box yellow firstcolumn smallfont {istall}" style="text-align: end;">{option.upper()}</td><td class="box blue {istall} {issmall} dualspan" style="text-align: start;"><input class="boxless blue dualspan" type="text" id="{option.replace(" ","-")}" name="{option.replace(" ","-")}" value="{value}"></input></td><td class="box blue fourspan {istall}" style="text-align: start;">{comment}</td></tr>'
            html_string += f'<tr><td class="box cyan firstcolumn"><button type="submit" name="action" value="save" class="boxless cyan firstcolumn">SAVE</button></td><td class="box cyan doublespan"><a href="/vlcservicegen?port={drones[section].get("Port")}&password={drones[section].get("Password")}" download="vlc.service">Generate vlc.service File</a></td><td class="box cyan doublespan"><a href="/remoteservicegen?address={drones[section].get("Address")}&port={drones[section].get("Port")}&password={drones[section].get("Password")}&user={drones[section].get("User")}" download="remote.service">Generate remote.service File</a></td><td class="box red"><button type="submit" name="action" value="delete" class="boxless red  firstcolumn">DELETE</button></td></tr></form>'

    except Exception as e:
        print(f"Error reading client config file: {e}")
        flash(f'Error reading client config file: {e}', 'error')
    return render_template('clients.html', html_string=html_string, drones_file=drones_file,live_onload = live_load())
  
@app.route('/fresh', methods=['GET', 'POST'])
def fresh_honey():
    
    fresh_file = 'fresh.ini'
    fresh = configparser.ConfigParser()
    fresh.optionxform = str
    fresh.read(os.path.abspath(f"./{fresh_file}"))
    if request.method == 'POST':
        if request.form.get('action') == "save":
            # Save changes to file
            print("SAVE INITIATED")
            request_form = {}
            print(request.form.get('Content-Type'))
            print(json.dumps(request.form,indent=4))
            client_name = request.form.get('client-name')
            if request.form.get(client_name+'_Content-Type') in ['tmdb','TMDB']:
                request_form[client_name.replace('-',' ')] = {
                    "Content Type": 'tmdb',
                    "Generate NFO": 'False',
                    "Is Music Video": 'False',
                    "Directory": '',
                    "TMDB Endpoint": '',
                    "Fresh Movies": '',
                    "Language": '',
                    "Region": '',
                    "Max Length": '0',
                    "Max Age Download": '0',
                    "Max Age Retention": '0',
                }                
            elif request.form.get(client_name+'_Content-Type') in ['url','URL']:
                request_form[client_name.replace('-',' ')] = {
                    "Content Type": 'url',
                    "Generate NFO": 'False',
                    "Is Music Video": 'False',
                    "Directory": '',
                    "Content Source": '',
                    "Max Length": '0',
                    "Max Age Download": '0',
                    "Max Age Retention": '0',
                }
            for o,v in request.form.items():
                if o == 'client-name':
                    s = request.form[o].replace('-',' ')
                    if s == '':
                        break
                    else:
                        continue
                elif o == 'action':
                    continue
                try:
                    request_form[s][o.split('_')[1].replace('-',' ')] = v
                except KeyError:
                    request_form[s] = {}
                    request_form[s][o.split('_')[1].replace('-',' ')] = v
            print(json.dumps(request_form,indent=4))
            try:
                update_config(fresh_file, request_form)
                flash(f'Changes to {s} saved successfully!', 'success')
            except:
                flash('Changes not saved.', 'error')
        elif request.form.get('action') == "new":
            # Save changes to file
            print("NEW ENTRY SAVE INITIATED")
            request_form = {}
            print(request.form.get('Content-Type'))
            print(json.dumps(request.form,indent=4))
            client_name = request.form.get('client-name')
            if request.form.get('Content-Type') in ['tmdb','TMDB']:
                request_form[client_name.replace('-',' ')] = {
                    "Content Type": 'tmdb',
                    "Generate NFO": 'False',
                    "Is Music Video": 'False',
                    "Directory": '',
                    "TMDB Endpoint": '',
                    "Fresh Movies": '',
                    "Language": '',
                    "Region": '',
                    "Max Length": '0',
                    "Max Age Download": '0',
                    "Max Age Retention": '0',
                }                
            elif request.form.get('Content-Type') in ['url','URL']:
                request_form[client_name.replace('-',' ')] = {
                    "Content Type": 'url',
                    "Generate NFO": 'False',
                    "Is Music Video": 'False',
                    "Directory": '',
                    "Content Source": '',
                    "Max Length": '0',
                    "Max Age Download": '0',
                    "Max Age Retention": '0',
                }
            for o,v in request.form.items():
                if o == 'client-name':
                    s = request.form[o].replace('-',' ')
                    if s == '':
                        break
                    else:
                        continue
                elif o == 'action':
                    continue
                elif v == '':
                    continue
                try:
                    request_form[s][o.replace('-',' ')] = v
                except KeyError:
                    continue
            print(json.dumps(request_form,indent=4))
            try:
                if client_name == "":
                    flash('Changes not saved. Client name cannot be blank', 'error')
                else:
                    update_config(fresh_file, request_form)
                    flash(f'Changes to {s} saved successfully!', 'success')
            except:
                flash('Changes not saved.', 'error')
        elif request.form.get('action') == "delete":
            print("DELETE INITIATED")
            print(json.dumps(request.form,indent=4))
            section_name = request.form['client-name']
            try:
                if fresh.has_section(section_name):
                    fresh.remove_section(section_name)
                    with open(fresh_file, 'w') as freshfile:
                        fresh.write(freshfile)
                    flash(f'{section_name} successfully deleted.', 'success')
                else:
                    flash(f'{s} not found in {freshfile}.', 'error')
            except:
                flash('Changes not saved.', 'error')
        pass
    html_string = ''
    try:
        # Iterate through each section
        for section in fresh.sections():
            #print(f"[{section}]")  # Print the section name
            html_string += f'<form action="/fresh" method="post"><tr onclick=toggleClass("{section.replace(" ","-")}","hide")>'
            html_string += f'<td class="box fullspanx">{section.upper()}</td><input type="hidden" id="client-name" name="client-name" value={section.replace(" ","-")}></tr><tbody class="hide" id="{section.replace(" ","-")}">'
            # Iterate through each option in the section
            for o, option in enumerate(fresh[section]):
                titlefontsize = ''
                comment = ''
                istall = ''
                issmall = ''
                entryspan = ''
                commentspan = 'fourspan'
                end_row = False
                if len(option) > 7:
                    titlefontsize = "smallfont"
                if len(option) >= 12:
                    titlefontsize = "extrasmallfont"
                value = fresh[section][option]
                if option.lower() == "content type":
                    comment = "TMDB or URL Source"
                    commentspan = 'trispan'
                    end_row = True
                elif option.lower() == "directory":
                    comment = "File path to download directory"
                    entryspan = 'doublespan'
                    commentspan = 'trispan'
                    end_row = True
                elif option.lower() == "content source":
                    comment = "Playlist/video page URL"
                    entryspan = "trispan"
                    commentspan = "doublespan"
                elif option.lower() == "tmdb endpoint":
                    comment = "Select now_playing, popular, top_rated or upcoming to indicate which list of movie titles to use"
                    istall = "tall"
                elif option.lower() == "fresh movies":
                    comment = "Number of fresh movies to get from TMDB"
                elif option.lower() == "language":
                    comment = "ISO 639 Language Tag"
                elif option.lower() == "region":
                    comment = "ISO 3166 Region Tag"
                elif option.lower() == "generate nfo":
                    comment = "Create NFO file with metadata (select False if downloading to a Movies or Shows library"
                    istall = "tall"
                elif option.lower() == "is music video":
                    comment = "If downloading to a Music Video library, select True to include artist/song metadata"
                    istall = "tall"
                elif option.lower() == "max length":
                    comment = "Maximum video length in minutes"
                elif option.lower() == "max age download":
                    comment = "Maximum upload age of video to download in days"
                elif option.lower() == "max age retention":
                    comment = "Maximum number of days to retain files in the above directory. Set blank or 0 to disable. WARNING: This feature will DELETE files older than the set age from the DIRECTORY set above."
                    istall = "extratall"
                else:
                    titlefontsize = ''
                    comment = ''
                    istall = ''
                    issmall = ''
                    entryspan = ''
                    commentspan = 'fourspan'

                #print(f"{option.upper()} = {value}")  # Print option and its value
                if len(value) > 110:
                    issmall = 'smallfont'
                    if len(value) > 624:
                        issmall = 'extrasmallfont'
                if value.lower() in ["true", "false"]:  # Check for boolean
                    value_type = "bool"
                elif value.lower() in ["tmdb", "url"]:  # Check for binary choice
                    value_type = "bin"
                elif value.isdigit():
                    value_type = "int"  # Check for integer
                elif value.replace('.', '', 1).isdigit() and value.count('.') == 1:
                    value_type = "float"
                else:
                    value_type = "str"
                if value_type == "bool":
                    entryspan = ""
                    commentspan = 'trispan'
                    if value.lower() == "true":
                        true_class = ""
                        false_class = "blue"
                    elif value.lower() == "false":
                        true_class = "blue"
                        false_class = ""
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td>'
                    html_string += f'<td id={section.replace(" ","-")}_{option.replace(" ","-")}-True class="box {true_class} {istall} {issmall} {entryspan}" onclick="toggleDualClass(\'{section.replace(" ","-")}_{option.replace(" ","-")}-True\',\'blue\',\'{section.replace(" ","-")}_{option.replace(" ","-")}-False\',\'blue\',\'{section.replace(" ","-")}_{option.replace(" ","-")}\',\'True\')">True</td>'
                    html_string += f'<td id={section.replace(" ","-")}_{option.replace(" ","-")}-False class="box {false_class} {istall} {issmall} {entryspan}" onclick="toggleDualClass(\'{section.replace(" ","-")}_{option.replace(" ","-")}-True\',\'blue\',\'{section.replace(" ","-")}_{option.replace(" ","-")}-False\',\'blue\',\'{section.replace(" ","-")}_{option.replace(" ","-")}\',\'False\')">False</td>'
                    html_string += f'<td class="box blue {commentspan} {istall}" style="text-align: start;">{comment}</td>'
                    html_string += f'<input type="hidden" id="{section.replace(" ","-")}_{option.replace(" ","-")}" name="{section.replace(" ","-")}_{option.replace(" ","-")}" value="{value}">'
                elif value_type == "bin":
                    entryspan = ""
                    if value.lower() == "tmdb":
                        true_class = ""
                        false_class = "blue"
                    elif value.lower() == "url":
                        true_class = "blue"
                        false_class = ""
                    commentspan = 'trispan'
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td>'
                    html_string += f'<td id={section.replace(" ","-")}_{option.replace(" ","-")}-tmdb class="box {true_class} {istall} {issmall} {entryspan}">TMDB</td>'
                    html_string += f'<td id={section.replace(" ","-")}_{option.replace(" ","-")}-url class="box {false_class} {istall} {issmall} {entryspan}">URL</td>'
                    html_string += f'<td class="box blue {commentspan} {istall}" style="text-align: start;">{comment}</td>'
                    html_string += f'<input type="hidden" id="{section.replace(" ","-")}_{option.replace(" ","-")}" name="{section.replace(" ","-")}_{option.replace(" ","-")}" value="{value}">'
                elif value_type == "str":
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td><td class="box blue {istall} {issmall} {entryspan}" style="text-align: start;"><input class="boxless blue {entryspan}" type="text" id="{section.replace(" ","-")}_{option.replace(" ","-")}" name="{section.replace(" ","-")}_{option.replace(" ","-")}" value="{value}"></input></td><td class="box blue {commentspan} {istall}" style="text-align: start;">{comment}</td>'
                elif value_type == "int":
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td><td class="box blue {istall} {issmall} {entryspan}" style="text-align: start;"><input class="boxless blue {entryspan}" type="number" id="{section.replace(" ","-")}_{option.replace(" ","-")}" name="{section.replace(" ","-")}_{option.replace(" ","-")}" value="{value}"></input></td><td class="box blue {commentspan} {istall}" style="text-align: start;">{comment}</td>'
                elif value_type == "float":
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td><td class="box blue {istall} {issmall} {entryspan}" style="text-align: start;"><input class="boxless blue {entryspan}" type="number" step="{value.replace(value[-1],"1")}" id="{section.replace(" ","-")}_{option.replace(" ","-")}" name="{section.replace(" ","-")}_{option.replace(" ","-")}" value="{value}"></input></td><td class="box blue {commentspan} {istall}" style="text-align: start;">{comment}</td>'
                else:
                    html_string += f'<td class="box yellow firstcolumn {titlefontsize} {istall}" style="text-align: end;">{option.upper()}</td><td class="box blue {istall} {issmall} {entryspan}" style="text-align: start;">{value}</td><td class="box blue {commentspan} {istall}" style="text-align: start;">{comment}</td>'
                end_row = True
                if end_row is False:
                    html_string += f'<td class="{istall} box blue"></td><td class="{istall} box blue"></td></tr>'
                else:
                    html_string += '</tr>'
            html_string += f'<tr><td class="box cyan firstcolumn"><button type="submit" name="action" value="save" class="boxless cyan firstcolumn">SAVE</button></td></td><td class="box blue fourspan"></td><td class="box red"><button type="submit" name="action" value="delete" class="boxless red  firstcolumn">DELETE</button></td></tr></tbody></form>'

    except Exception as e:
        print(f"Error reading client config file: {e}")
        flash(f'Error reading client config file: {e}', 'error')
    return render_template('fresh.html', html_string=html_string, fresh_file=fresh_file, live_onload = live_load())
    
@app.route('/get-drones', methods=['GET'])
def get_drones():
    # Extract the section names (category headings)
    section_names = drones.sections()
    
    # Return the section names as a JSON response
    return jsonify(section_names)

@app.route('/edit_json', methods=['GET', 'POST'])
def edit_json():
    json_files = get_json_files()
    if request.method == 'POST':
        selected_file = request.form.get('json_file')
        json_content = request.form.get('json_content')

        if selected_file and json_content:
            file_path = os.path.join('channels', selected_file)
            try:
                json_data = json.loads(json_content)
                save_data(file_path, json_data)
                flash('Changes saved successfully!', 'success')
            except json.JSONDecodeError:
                flash('Invalid JSON format. Please correct the errors and try again.', 'error')
        return redirect(url_for('edit_json'))

    selected_file = request.args.get('file', '')
    json_content = ''
    if selected_file:
        file_path = os.path.join('channels', selected_file)
        try:
            json_content = json.dumps(load_data(file_path), indent=2)
        except FileNotFoundError:
            flash('Selected file not found.', 'error')

    return render_template('edit_schedule.html', json_files=json_files, json_content=json_content)

@app.route('/edit_details', methods=['GET', 'POST'])
def edit_details():
    channels_directory = os.path.join(os.path.dirname(__file__), "channels")
    channels = [entry.name for entry in os.scandir(channels_directory) if entry.is_dir()]
    
    if request.method == 'POST':
        print(json.dumps(request.form,indent=4))
        channel_details = {}
        action = False
        for k,v in request.form.items():
            if k != "action":
                channel_details[k] = v
            else:
                action = v
        if action == "save":
            save_data(os.path.join(channels_directory, f"{channel_details['number_raw']}/details.json"), channel_details)
    
    details = []
    for channel in channels:
        channel_path = os.path.join(channels_directory, channel)
        JSON_FILE = os.path.join(channel_path, 'details.json')
    
        try:
            # Read the JSON file
            data = load_data(JSON_FILE)
            details.append(data)
        # Serve the JSON payload
        except FileNotFoundError:
            continue
        except json.JSONDecodeError:
            continue
    return render_template('edit_details.html', details=details, live_onload = live_load())


@app.route('/live', methods=['GET'])
def get_live():
    JSON_FILE = os.path.join(os.path.dirname(__file__), live_file)
    try:
        # Read the JSON file
        with open(JSON_FILE, 'r') as json_file:
            data = json.load(json_file)
        # Serve the JSON payload
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "JSON file not found"}), 404
    except json.JSONDecodeError:
        return jsonify({"error": "Error decoding JSON file"}), 500
    
def get_metadata_lists(data, k, min_value=4):
    """
    This function takes a dataset (either show or movie data) and returns a sorted list
    of unique key values that appear more than min_value in the dataset.
    Each entry in the returned list is a tuple with the name and its count.
    """
    # Count the occurrences of each name
    name_counts = {}

    for item in data.values():
        if k in item:
            if isinstance(item[k], list):
                for kv in item[k]:
                    if isinstance(kv, dict):
                        if 'name' in kv:
                            name = kv['name']
                        elif '#text' in kv:
                            name = kv['#text']
                    elif isinstance(kv, str):
                        name = kv
                    if name in name_counts:
                        name_counts[name] += 1
                    else:
                        name_counts[name] = 1
            elif isinstance(item[k], dict):
                if 'name' in item[k]:
                    name = item[k]['name']
                elif '#text' in item[k]:
                    name = item[k]['#text']
                if name in name_counts:
                    name_counts[name] += 1
                else:
                    name_counts[name] = 1
            elif isinstance(item[k], str):
                name = item[k]
                if name in name_counts:
                    name_counts[name] += 1
                else:
                    name_counts[name] = 1
        elif k in item.get('movie',{}):
            if isinstance(item['movie'][k], list):
                for kv in item['movie'][k]:
                    if isinstance(kv, dict):
                        if 'name' in kv:
                            name = kv['name']
                        elif '#text' in kv:
                            name = kv['#text']
                    elif isinstance(kv, str):
                        name = kv
                    if name in name_counts:
                        name_counts[name] += 1
                    else:
                        name_counts[name] = 1
            elif isinstance(item['movie'][k], str):
                name = item['movie'][k]
                if name in name_counts:
                    name_counts[name] += 1
                else:
                    name_counts[name] = 1
        if isinstance(item['files'], dict):
            for file_name, file in item['files'].items():
                if 'episode_details' in file:
                    for episode_detail in file['episode_details']:
                        if k in episode_detail:
                            if isinstance(episode_detail[k], list):
                                for kv in episode_detail[k]:
                                    if isinstance(kv, dict):
                                        if 'name' in kv.keys():
                                            data_key = 'name'
                                        elif '#text' in kv.keys():
                                            data_key = '#text'
                                        name = kv[data_key]
                                    elif isinstance(kv, str):
                                        name = kv
                                    if name in name_counts:
                                        name_counts[name] += 1
                                    else:
                                        name_counts[name] = 1
                            elif isinstance(episode_detail[k], dict):
                                if 'name' in episode_detail[k].keys():
                                    data_key = 'name'
                                elif '#text' in episode_detail[k].keys():
                                    data_key = '#text'
                                name = episode_detail[k][data_key]
                                if name in name_counts:
                                    name_counts[name] += 1
                                else:
                                    name_counts[name] = 1

    # Extract names that appear more than min_value times and create tuples (name, count)
    frequent_names = [(name, count) for name, count in name_counts.items() if count >= min_value]

    # Sort actor names by last name
    def sort_by_last_name(name_count_tuple):
        name = name_count_tuple[0]
        count = name_count_tuple[1]
        
        if k in ["actor", "director", "credits", "producer"]:
            if name.split()[-1][0].isalpha():
                last_name = name.split()[-1]
            else:
                last_name = name.split()[-2]
        else:
            last_name = name

        # Return a tuple for sorting: first element for primary sort, second element for secondary sort
        return (-count, last_name, name)

    sorted_names = sorted(frequent_names, key=sort_by_last_name)
    return sorted_names

# Helper function to round minutes to the next multiple of 15
def round_to_next_15_minutes(minutes):
    return (int(minutes) + 14) // 15 * 15

# Helper function to parse time strings and return a datetime object
def parse_time_string(time_str):
    return datetime.datetime.strptime(time_str, '%H:%M:%S')

# Helper function to convert a datetime object to a time string
def format_time_string(time_obj):
    return time_obj.strftime('%H:%M:%S')

# Function to find the first gap of at least 15 minutes
def find_first_gap(schedule, day, start_time=None):
    if day not in schedule or not schedule[day]:
        return None  # No entries for this day

    # Sort schedule times in chronological order
    sorted_times = schedule[day].keys()

    previous_end_time = None

    # If start_time is provided, convert it to a datetime object
    if start_time:
        start_time = parse_time_string(start_time)
            
    for time_str in sorted_times:
        entry_start_time = parse_time_string(time_str)

        # If a start_time is provided, skip entries that start before it
        if start_time and entry_start_time < start_time:
            continue

        entry = schedule[day][time_str]

        # Extract duration from the entry
        if 'type' in entry and entry['type']:
            entry_type = list(entry['type'].values())[0]  # The type dictionary inside entry
            if isinstance(entry_type.get('duration_minutes'), list):
                duration_minutes = entry_type['duration_minutes'][0]
            else:
                duration_minutes = entry_type['duration_minutes']
        else:
            continue  # Skip if no duration is available

        # Round the duration to the next 15 minutes
        rounded_duration = round_to_next_15_minutes(duration_minutes)

        # Calculate the end time of the current entry
        end_time = entry_start_time + timedelta(minutes=rounded_duration)

        # Check for gap after the previous entry
        if previous_end_time:
            gap_duration = (entry_start_time - previous_end_time).total_seconds() / 60
            start_plus_gap = None
            while gap_duration > 15:
                # Found a gap
                start_plus_gap = entry_start_time + timedelta(minutes=15)
            if start_plus_gap is not None:
                print(format_time_string(start_plus_gap))
                return format_time_string(start_plus_gap)

        # Update the previous end time to the current entry's end time
        previous_end_time = end_time

    return None  # No gaps found
    
@app.route('/new_entry/<channel>/', defaults={'day': None, 'time': None}, methods=['GET', 'POST'])
@app.route('/new_entry/<channel>/<day>/<time>', methods=['GET', 'POST'])
def new_entry(channel, day, time):
    schedule_path = os.path.join(CHANNELS_DIR, channel, 'schedule.json')

    # Load or create a new schedule if it doesn't exist
    if not os.path.exists(schedule_path):
        schedule = {}
    else:
        schedule = load_data(schedule_path)

    # Use placeholder values if day or time is not provided
    if day is None:
        day = 'Monday'  # Placeholder value for day
    if day not in schedule:
        schedule[day] = {}
    if time is None:
        #print(find_first_gap(schedule,day))
        time = "23:59:00" 

    # Extract unique certifications for series
    series_ratings_counts = {}
    for show in shows_details.values():
        if show['certification'] is not None:
            series_rating = show['certification'].strip()
            if ':' in series_rating:
                series_rating = series_rating.split(':')[1]
            if series_rating in series_ratings_counts:
                series_ratings_counts[series_rating] += 1
            else:
                series_ratings_counts[series_rating] = 1

    # Convert series ratings dictionary to sorted list of tuples
    series_ratings = sorted(series_ratings_counts.items())

    # Extract unique certifications for movies
    movies_ratings_counts = {}
    for movie in movies_details.values():
        if movie['certification'] is not None:
            movie_rating = movie['certification']
            if '/' in movie_rating:
                movie_rating = movie_rating.split('/')[0]
            if ':' in movie_rating:
                movie_rating = movie_rating.split(':')[1]
            if movie_rating in movies_ratings_counts:
                movies_ratings_counts[movie_rating] += 1
            else:
                movies_ratings_counts[movie_rating] = 1

    # Convert movies ratings dictionary to sorted list of tuples
    movies_ratings = sorted(movies_ratings_counts.items())


    # Extract metadata lists
    series_actor_names = get_metadata_lists(shows_details, 'actor')
    movie_actor_names = get_metadata_lists(movies_details, 'actor')

    series_director_names = get_metadata_lists(shows_details, 'director',2)
    
    movie_director_names = get_metadata_lists(movies_details, 'director',2)

    series_writer_names = get_metadata_lists(shows_details, 'credits',2)
    movie_writer_names = get_metadata_lists(movies_details, 'credits',2)
    
    movie_producer_names = get_metadata_lists(movies_details, 'producer',2)
    
    series_genre_names = get_metadata_lists(shows_details, 'genre')
    movie_genre_names = get_metadata_lists(movies_details, 'genre')

    series_studio_names = get_metadata_lists(shows_details, 'studio')
    movie_studio_names = get_metadata_lists(movies_details, 'studio')

    movie_tags_names = get_metadata_lists(movies_details, 'tag',2)
 
 
 
    # Extract unique years and their counts for series
    series_years_counts = {}
    for show in shows_details.values():
        if show['year'] is not None:
            year = int(show['year'])
            if year in series_years_counts:
                series_years_counts[year] += 1
            else:
                series_years_counts[year] = 1

    # Convert series years dictionary to sorted list of tuples
    series_years = sorted(series_years_counts.items())

    # Extract unique decades and their counts for series
    series_decades_counts = {}
    for year, count in series_years:
        decade = (year // 10) * 10
        if decade in series_decades_counts:
            series_decades_counts[decade] += count
        else:
            series_decades_counts[decade] = count

    # Convert series decades dictionary to sorted list of tuples
    series_decades = sorted(series_decades_counts.items())

    # Extract unique years and their counts for movies
    movies_years_counts = {}
    for movie in movies_details.values():
        if movie['year'] is not None:
            year = int(movie['year'])
            if year in movies_years_counts:
                movies_years_counts[year] += 1
            else:
                movies_years_counts[year] = 1

    # Convert movies years dictionary to sorted list of tuples
    movies_years = sorted(movies_years_counts.items())

    # Extract unique decades and their counts for movies
    movies_decades_counts = {}
    for year, count in movies_years:
        decade = (year // 10) * 10
        if decade in movies_decades_counts:
            movies_decades_counts[decade] += count
        else:
            movies_decades_counts[decade] = count

    # Convert movies decades dictionary to sorted list of tuples
    movies_decades = sorted(movies_decades_counts.items())



    filter_data = {
        'ratings': {
            'series': series_ratings,
            'movies': movies_ratings,
        },
        'years': {
            'series': series_years,
            'movies': movies_years,
        },
        'decades': {
            'series': series_decades,
            'movies': movies_decades,
        },
        'actor': {
            'series': series_actor_names,
            'movies': movie_actor_names,
        },
        'director': {
            'series': series_director_names,
            'movies': movie_director_names,
        },
        'writer': {
            'series': series_writer_names,
            'movies': movie_writer_names,
        },
        'producer': {
            'movies': movie_producer_names,
        },
        'genre': {
            'series': series_genre_names,
            'movies': movie_genre_names,
        },
        'studio': {
            'series': series_studio_names,
            'movies': movie_studio_names,
        },
        'tag': {
            'movies': movie_tags_names,
        }
    }



    # Initialize a new entry if it doesn't exist for the given day and time

    if time not in schedule[day]:
        entry = {}  # New empty entry
        entry['time_mode'] = 'preempt'
        entry['start_time'] = time
        entry['type'] = {
            'series': {
                'id': 0,
                'duration_minutes': 0,
                'episode_mode': 'sequential',
                'on_series_end': 'reschedule_similar'
            }
        }
        # Assign the entry to the schedule for the specified day and time
        schedule[day][time] = entry
        #save_data(schedule_path, schedule)
        flash("New schedule entry created successfully.", "success")
        return render_template('edit_entry.html', channel=channel, day=day, time=time, entry=entry, schedule=schedule, dow=['Monday'], shows_details=shows_details, movies_details=movies_details, filter_data=filter_data, template_files=get_template_files(),live_onload = live_load())

    else:
        flash("Entry already exists. Use edit entry to modify.", "error")
        return redirect(url_for('edit_entry', channel=channel, day=day, time=time, live_onload = live_load()))
    
    # Render the new entry form (re-use the edit template)
    return render_template('edit_entry.html', entry={}, is_new=True,live_onload = live_load())
   
@app.route('/delete_entry/<channel>/<day>/<time>', methods=['GET', 'POST'])
def delete_entry(channel, day, time, entry=None):
    schedule_path = os.path.join(CHANNELS_DIR, channel, 'schedule.json')
    if not os.path.exists(schedule_path):
        flash(f"Schedule for channel '{channel}' not found.", "error")
        return redirect(url_for('edit_get'))

    schedule = load_data(schedule_path)
    
    # Handle the deletion of the entry
    try:
        del schedule[day][time]
        save_data(schedule_path, schedule)
        flash("Schedule entry deleted successfully.", "success")
        return redirect(url_for(f'edit_get',channel=channel))
    except KeyError:
        flash("Could not find the entry to delete.", "error")
        return redirect(url_for(f'edit_get',channel=channel))
        
@app.route('/edit_entry/<channel>/<day>/<time>', methods=['GET', 'POST'])
def edit_entry(channel, day, time, entry=None):
    schedule_path = os.path.join(CHANNELS_DIR, channel, 'schedule.json')
    if not os.path.exists(schedule_path):
        flash(f"Schedule for channel '{channel}' not found.", "error")
        return redirect(url_for('select_channel'))

    schedule = load_data(schedule_path)
    music_videos_details = load_data(os.path.join(LIBRARY_DIR, 'music_videos_details.json'))
    try:
        entry = schedule[day][time]
        if not entry.get('start_time'):
            entry['start_time']=time
    except KeyError:
        try:
            if len(time) == 5:
                time = time+':00'
        except KeyError:
            entry = entry
        
    days_of_week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    #check other days for same entry
    dow = []
    for d in days_of_week:
        '''if d == day:
            continue'''

        # Get the schedule entry at the specific time for the current day
        day_schedule = schedule.get(d, {}).get(time, {})
        if day_schedule == entry:
            dow.append(d)
    print(dow)
    # Extract unique certifications for series
    series_ratings_counts = {}
    for show in shows_details.values():
        if show['certification'] is not None:
            series_rating = show['certification'].strip()
            if ':' in series_rating:
                series_rating = series_rating.split(':')[1]
            if series_rating in series_ratings_counts:
                series_ratings_counts[series_rating] += 1
            else:
                series_ratings_counts[series_rating] = 1

    # Convert series ratings dictionary to sorted list of tuples
    series_ratings = sorted(series_ratings_counts.items())

    # Extract unique certifications for movies
    movies_ratings_counts = {}
    for movie in movies_details.values():
        if movie['certification'] is not None:
            movie_rating = movie['certification']
            if '/' in movie_rating:
                movie_rating = movie_rating.split('/')[0]
            if ':' in movie_rating:
                movie_rating = movie_rating.split(':')[1]
            if movie_rating in movies_ratings_counts:
                movies_ratings_counts[movie_rating] += 1
            else:
                movies_ratings_counts[movie_rating] = 1

    # Convert movies ratings dictionary to sorted list of tuples
    movies_ratings = sorted(movies_ratings_counts.items())

    # Extract unique years and their counts for series
    series_years_counts = {}
    for show in shows_details.values():
        if show['year'] is not None:
            year = int(show['year'])
            if year in series_years_counts:
                series_years_counts[year] += 1
            else:
                series_years_counts[year] = 1

    # Convert series years dictionary to sorted list of tuples
    series_years = sorted(series_years_counts.items())

    # Extract unique decades and their counts for series
    series_decades_counts = {}
    for year, count in series_years:
        decade = (year // 10) * 10
        if decade in series_decades_counts:
            series_decades_counts[decade] += count
        else:
            series_decades_counts[decade] = count

    # Convert series decades dictionary to sorted list of tuples
    series_decades = sorted(series_decades_counts.items())

    # Extract unique years and their counts for movies
    movies_years_counts = {}
    for movie in movies_details.values():
        if movie['year'] is not None:
            year = int(movie['year'])
            if year in movies_years_counts:
                movies_years_counts[year] += 1
            else:
                movies_years_counts[year] = 1

    # Convert movies years dictionary to sorted list of tuples
    movies_years = sorted(movies_years_counts.items())

    # Extract unique decades and their counts for movies
    movies_decades_counts = {}
    for year, count in movies_years:
        decade = (year // 10) * 10
        if decade in movies_decades_counts:
            movies_decades_counts[decade] += count
        else:
            movies_decades_counts[decade] = count

    movies_decades = sorted(movies_decades_counts.items())

    # Extract unique years and their counts for music videos
    music_videos_years_counts = {}
    for video in music_videos_details.values():
        if video['movie'].get('year',None) is not None:
            try:
                year = int(video['movie']['year'])
            except ValueError:
                continue
            if year in music_videos_years_counts:
                music_videos_years_counts[year] += 1
            else:
                music_videos_years_counts[year] = 1

    # Convert music videos years dictionary to sorted list of tuples
    music_videos_years = sorted(music_videos_years_counts.items())

    # Extract unique decades and their counts for music videos
    music_videos_decades_counts = {}
    for year, count in music_videos_years:
        decade = (year // 10) * 10
        if decade in music_videos_decades_counts:
            music_videos_decades_counts[decade] += count
        else:
            music_videos_decades_counts[decade] = count

    # Convert movies decades dictionary to sorted list of tuples
    music_videos_decades = sorted(music_videos_decades_counts.items())

    # Extract metadata lists
    series_actor_names = get_metadata_lists(shows_details, 'actor')
    movie_actor_names = get_metadata_lists(movies_details, 'actor')

    series_director_names = get_metadata_lists(shows_details, 'director',2)
    
    movie_director_names = get_metadata_lists(movies_details, 'director',2)

    series_writer_names = get_metadata_lists(shows_details, 'credits',2)
    movie_writer_names = get_metadata_lists(movies_details, 'credits',2)
    
    movie_producer_names = get_metadata_lists(movies_details, 'producer',2)
    
    series_genre_names = get_metadata_lists(shows_details, 'genre')
    movie_genre_names = get_metadata_lists(movies_details, 'genre')

    series_studio_names = get_metadata_lists(shows_details, 'studio')
    movie_studio_names = get_metadata_lists(movies_details, 'studio')

    movie_tags_names = get_metadata_lists(movies_details, 'tag',2)
    music_videos_tags = get_metadata_lists(music_videos_details, 'tag',2)
    #print(json.dumps(music_videos_tags,indent=4))
    
    filter_data = {
        'ratings': {
            'series': series_ratings,
            'movies': movies_ratings,
        },
        'years': {
            'series': series_years,
            'movies': movies_years,
        },
        'decades': {
            'series': series_decades,
            'movies': movies_decades,
            'music_videos': music_videos_decades,
        },
        'actor': {
            'series': series_actor_names,
            'movies': movie_actor_names,
        },
        'director': {
            'series': series_director_names,
            'movies': movie_director_names,
        },
        'writer': {
            'series': series_writer_names,
            'movies': movie_writer_names,
        },
        'producer': {
            'movies': movie_producer_names,
        },
        'genre': {
            'series': series_genre_names,
            'movies': movie_genre_names,
        },
        'studio': {
            'series': series_studio_names,
            'movies': movie_studio_names,
        },
        'tag': {
            'movies': movie_tags_names,
            'music_videos': music_videos_tags,
        },
        'music_videos': {
            'decades': music_videos_decades,
            'tags': music_videos_tags,
            }
    }
    if request.method == 'POST':
        if entry is None:
            entry = {}
        if 'delete' in request.form and request.form['delete'] == 'true':
            # Handle the deletion of the entry
            try:
                del schedule[day][time]
                save_data(schedule_path, schedule)
                flash("Schedule entry deleted successfully.", "success")
                return redirect(url_for('edit_get', channel=channel, template_files=get_template_files()))
            except KeyError:
                flash("Could not find the entry to delete.", "error")
                return redirect(url_for('edit_get', channel=channel, template_files=get_template_files()))
        
        # Update entry based on form data
        print(json.dumps(request.form,indent=4))
        entry['time_mode'] = 'preempt'
        start_time = request.form['start_time']
        if len(start_time) == 5:
            start_time = start_time+':00'
        entry['start_time'] = start_time
        entry_type = request.form.get('type')
        print(f"ENTRY TYPE: [{entry_type}]")
        if entry_type == 'series':
            print(entry_type)
            if request.form['title'] != 'random':
                entry['type'] = {
                    'series': {
                        'id': request.form['title'],
                        'duration_minutes': request.form['show_duration_minutes'],
                        'episode_mode': request.form['episode_mode'],
                        'on_series_end': request.form['on_series_end']
                    }
                }
                series_dict = shows_details[request.form['title']]
                entry['title'] = series_dict['title']
                series_durations = []
                for ep in series_dict['files']:
                    
                    if series_dict['files'][ep]['episode_details']:
                        if series_dict['files'][ep]['episode_details'][0]['fileinfo']:
                            if series_dict['files'][ep]['episode_details'][0]['fileinfo']['streamdetails']:
                                if series_dict['files'][ep]['episode_details'][0]['fileinfo']['streamdetails']['video']:
                                    if series_dict['files'][ep]['episode_details'][0]['fileinfo']['streamdetails']['video']['durationinseconds']:
                                        series_durations.append(int(round(int(series_dict['files'][ep]['episode_details'][0]['fileinfo']['streamdetails']['video']['durationinseconds'])/60)))
                median_duration = sorted(series_durations)[len(series_durations) // 2] if len(series_durations) % 2 else (sorted(series_durations)[len(series_durations) // 2 - 1] + sorted(series_durations)[len(series_durations) // 2]) / 2
                    
            else:
                entry['title'] = "Random Series"
                entry['type'] = {
                    'random_series': {
                        'duration_minutes': [int(request.form['series_duration_min']),int(request.form['series_duration_max'])],
                        'time_mode': "preempt",
                        'episode_mode': request.form['episode_mode'],
                        "ratings": {
                            'allowed': request.form['allow_ratings_cell'].split(', '),
                            'forbidden': request.form['forbid_ratings_cell'].split(', ')
                            },
                        "decades": {
                            'allowed': request.form['allow_decades_cell'].split(', '),
                            'forbidden': request.form['forbid_decades_cell'].split(', ')
                            },
                        "actor": {
                            'allowed': request.form['allow_actor_cell'].split(', '),
                            'forbidden': request.form['forbid_actor_cell'].split(', ')
                            },
                        "director": {
                            'allowed': request.form['allow_director_cell'].split(', '),
                            'forbidden': request.form['forbid_director_cell'].split(', ')
                            },
                        "writer": {
                            'allowed': request.form['allow_writer_cell'].split(', '),
                            'forbidden': request.form['forbid_writer_cell'].split(', ')
                            },
                        "genre": {
                            'allowed': request.form['allow_genre_cell'].split(', '),
                            'forbidden': request.form['forbid_genre_cell'].split(', ')
                            },
                        "studio": {
                            'allowed': request.form['allow_studio_cell'].split(', '),
                            'forbidden': request.form['forbid_studio_cell'].split(', ')
                            },
                        'on_series_end': request.form['on_series_end']
                    }
                }
        elif entry_type == 'random_movie' or entry_type == 'movie':
            print(f"link_mode_select: {request.form['link_mode_select']}")
            if request.form['link_mode'] == 'disabled':
                kevin_bacon_mode = 'false'
            else:
                kevin_bacon_mode = request.form['link_mode_select']
            entry['title'] = "Random Movie"
            entry['type'] = {
                'random_movie': {
                    'duration_minutes': [int(request.form['movie_duration_min']),int(request.form['movie_duration_max'])],
                    "kevin_bacon_mode": kevin_bacon_mode,
                    "ratings": {
                        'allowed': request.form['allow_ratings_cell'].split(', '),
                        'forbidden': request.form['forbid_ratings_cell'].split(', ')
                        },
                    "decades": {
                        'allowed': request.form['allow_decades_cell'].split(', '),
                        'forbidden': request.form['forbid_decades_cell'].split(', ')
                        },
                    "actor": {
                        'allowed': request.form['allow_actor_cell'].split(', '),
                        'forbidden': request.form['forbid_actor_cell'].split(', ')
                        },
                    "director": {
                        'allowed': request.form['allow_director_cell'].split(', '),
                        'forbidden': request.form['forbid_director_cell'].split(', ')
                        },
                    "writer": {
                        'allowed': request.form['allow_writer_cell'].split(', '),
                        'forbbidden': request.form['forbid_writer_cell'].split(', ')
                        },
                    "producer": {
                        'allowed': request.form['allow_producer_cell'].split(', '),
                        'forbidden': request.form['forbid_producer_cell'].split(', ')
                        },
                    "genre": {
                        'allowed': request.form['allow_genre_cell'].split(', '),
                        'forbidden': request.form['forbid_genre_cell'].split(', ')
                        },
                    "studio": {
                        'allowed': request.form['allow_studio_cell'].split(', '),
                        'forbidden': request.form['forbid_studio_cell'].split(', ')
                        },
                    "tag": {
                        'allowed': request.form['allow_tag_cell'].split(', '),
                        'forbidden': request.form['forbid_tag_cell'].split(', ')
                        },
                        
                    }
                }
            print(f"kevin_bacon_mode: {entry['type']['random_movie']['kevin_bacon_mode']}")

            '''if request.form['title'] != 'random':
                entry['type'] = {
                    'series': {
                        'id': request.form['title'],
                        'duration_minutes': request.form['show_duration_minutes'],
                        'episode_mode': request.form['episode_mode'],
                        'on_series_end': request.form['on_series_end']
                    }
                }
                series_dict = shows_details[request.form['title']]
                entry['title'] = series_dict['title']
                series_durations = []
                for ep in series_dict['files']:
                    
                    if series_dict['files'][ep]['episode_details']:
                        if series_dict['files'][ep]['episode_details'][0]['fileinfo']:
                            if series_dict['files'][ep]['episode_details'][0]['fileinfo']['streamdetails']:
                                if series_dict['files'][ep]['episode_details'][0]['fileinfo']['streamdetails']['video']:
                                    if series_dict['files'][ep]['episode_details'][0]['fileinfo']['streamdetails']['video']['durationinseconds']:
                                        series_durations.append(int(round(int(series_dict['files'][ep]['episode_details'][0]['fileinfo']['streamdetails']['video']['durationinseconds'])/60)))
                median_duration = sorted(series_durations)[len(series_durations) // 2] if len(series_durations) % 2 else (sorted(series_durations)[len(series_durations) // 2 - 1] + sorted(series_durations)[len(series_durations) // 2]) / 2
                    
            else:
                entry['title'] = "Random Series"
                entry['type'] = {
                    'random_series': {
                        'duration_minutes': [int(request.form['series_duration_min']),int(request.form['series_duration_max'])],
                        'time_mode': "preempt",
                        'episode_mode': request.form['episode_mode'],
                        "ratings": {
                            'allowed': request.form['allow_ratings_cell'].split(', '),
                            'forbidden': request.form['forbid_ratings_cell'].split(', ')
                            },
                        "decades": {
                            'allowed': request.form['allow_decades_cell'].split(', '),
                            'forbidden': request.form['forbid_decades_cell'].split(', ')
                            },
                        "actor": {
                            'allowed': request.form['allow_actor_cell'].split(', '),
                            'forbidden': request.form['forbid_actor_cell'].split(', ')
                            },
                        "director": {
                            'allowed': request.form['allow_director_cell'].split(', '),
                            'forbidden': request.form['forbid_director_cell'].split(', ')
                            },
                        "writer": {
                            'allowed': request.form['allow_writer_cell'].split(', '),
                            'forbidden': request.form['forbid_writer_cell'].split(', ')
                            },
                        "genre": {
                            'allowed': request.form['allow_genre_cell'].split(', '),
                            'forbidden': request.form['forbid_genre_cell'].split(', ')
                            },
                        "studio": {
                            'allowed': request.form['allow_studio_cell'].split(', '),
                            'forbidden': request.form['forbid_studio_cell'].split(', ')
                            },
                        'on_series_end': request.form['on_series_end']
                    }
                }'''        
        elif entry_type == 'music_videos':
            #print(json.dumps(request.form,indent=4))
            print(f"link_mode_select: {request.form['link_mode_select']}")
            if request.form['link_mode'] == 'disabled':
                kevin_bacon_mode = 'false'
            else:
                kevin_bacon_mode = request.form['link_mode_select']
            entry['title'] = "Music Videos"
            entry['type'] = {
                'music_videos': {
                    'duration_minutes': int(request.form['music_videos_duration_max']),
                    "kevin_bacon_mode": kevin_bacon_mode,
                    "decades": {
                        'allowed': request.form['allow_decades_cell'].split(', '),
                        'forbidden': request.form['forbid_decades_cell'].split(', ')
                        },
                    "tag": {
                        'allowed': request.form['allow_tag_cell'].split(', '),
                        'forbidden': request.form['forbid_tag_cell'].split(', ')
                        },
                    }
                }
            print(f"kevin_bacon_mode: {entry['type']['music_videos']['kevin_bacon_mode']}")
        #print(ast.literal_eval(request.form['dow_input']))
        for d in ast.literal_eval(request.form['dow_input']):
            schedule[d][start_time] = entry
            if start_time != time:
                #print(f"{time} -> {request.form['start_time']}:00")
                removed_entry = schedule[d].pop(time, None)
                time = start_time
        
        schedule = sort_times(schedule)
        # Save updated schedule
        print(json.dumps(entry,indent=4))
        save_data(schedule_path, schedule)
        flash(f"Schedule entry updated successfully: {day} {time}", "success")
        return redirect(url_for('edit_get', channel=channel, time=start_time, template_files=get_template_files()))

    filter_data = {
        'ratings': {
            'series': series_ratings,
            'movies': movies_ratings,
        },
        'years': {
            'series': series_years,
            'movies': movies_years,
        },
        'decades': {
            'series': series_decades,
            'movies': movies_decades,
            'music_videos': music_videos_decades,
        },
        'actor': {
            'series': series_actor_names,
            'movies': movie_actor_names,
        },
        'director': {
            'series': series_director_names,
            'movies': movie_director_names,
        },
        'writer': {
            'series': series_writer_names,
            'movies': movie_writer_names,
        },
        'producer': {
            'movies': movie_producer_names,
        },
        'genre': {
            'series': series_genre_names,
            'movies': movie_genre_names,
        },
        'studio': {
            'series': series_studio_names,
            'movies': movie_studio_names,
        },
        'tag': {
            'movies': movie_tags_names,
            'music_videos': music_videos_tags,
        }
    }
    return render_template('edit_entry.html', channel=channel, day=day, time=time, entry=entry, schedule=schedule, dow=dow, shows_details=shows_details, movies_details=movies_details, music_videos_details=music_videos_details, filter_data=filter_data, template_files=get_template_files(),live_onload=live_load())

def sort_times(schedule):
    def time_str_to_datetime(time_str):
        #print(f"Time String: {time_str}")
        time_array = time_str.split(':')
        if len(time_array) == 2:
            time_format = "%H:%M"
        elif len(time_array) == 3:
            time_format = "%H:%M:%S"
        elif len(time_array) > 3:
            time_str = ''
            remaining_loops = 3
            for t in time_array:
                time_str += t
                remaining_loops -= 1
                if remaining_loops > 0:
                    time_str += ':'
                else:
                    break
            print(f"New Time String: {time_str}")
            time_format = "%H:%M:%S"
        try:
            return datetime.datetime.strptime(time_str, time_format).time()
        except ValueError as v:
                print(v)

    for day, times in schedule.items():
        if day != "Template" and isinstance(times, dict):
            # Extract start_time from the Template Morning
            for template_key, template_day in schedule["Template"].items():
                print(template_day)
                template_start_time = template_day["start_time"]
                break
            template_start_time = time_str_to_datetime(template_start_time)
            
            # Create a sorted list of time keys based on the start_time
            time_keys = sorted(
                times.keys(),
                key=lambda k: (time_str_to_datetime(k) < template_start_time, time_str_to_datetime(k))
            )

            # Rebuild the dictionary with sorted keys
            sorted_times = collections.OrderedDict((key, times[key]) for key in time_keys)
            schedule[day] = sorted_times
    return schedule

@app.route('/edit_schedule/<channel>', methods=['GET', 'POST'])
def edit_get(channel):
    schedule_path = os.path.join(CHANNELS_DIR, channel, 'schedule.json')
    if not os.path.exists(schedule_path):
        flash(f"Schedule for channel '{channel}' not found.", "error")
        return redirect(url_for('select_channel'))

    if request.method == 'POST':
        # Load existing schedule
        schedule = load_data(schedule_path)
        
        # Update schedule with the form data
        new_schedule = {}
        for key, value in request.form.items():
            if key.startswith('time-'):
                _, day, index = key.split('-')
                time = value
                new_schedule.setdefault(day, {})[time] = schedule[day].pop(list(schedule[day].keys())[int(index) - 1])
            else:
                _, day, index, attribute = key.split('-')
                time = list(schedule[day].keys())[int(index) - 1]
                new_schedule[day][time][attribute] = value

        save_data(schedule_path, new_schedule)
        flash(f"Schedule for channel '{channel}' updated successfully.", "success")
        return redirect(url_for('edit_get', channel=channel))

    schedule = load_data(schedule_path)

    return render_template('edit_schedule.html', channel=channel, schedule=schedule, shows_details=shows_details, movies_details=movies_details, template_files=get_template_files(), live_onload=live_load())

@app.route('/on_demand', methods=['GET', 'POST'])
def on_demand(content="all"):
    music_videos_details = load_data(os.path.join(LIBRARY_DIR, 'music_videos_details.json'))

    return render_template('on_demand.html', music_videos_details=music_videos_details, shows_details=shows_details, movies_details=movies_details, template_files=get_template_files(), live_onload=live_load())

'''@app.route('/edit_schedule/<channel>', methods=['GET', 'POST'])
def edit_schedule_channel(channel):
    
    file_path = f'channels/{channel}/schedule.json'
    
    try:
        schedule_data = load_data(file_path)
    except FileNotFoundError:
        abort(404)  # Return a 404 error if the file is not found

    if request.method == 'POST':
        # Process form data and update schedule_data
        for day in schedule_data:
            for time_block in schedule_data[day]:
                schedule_data[day][time_block]['title'] = request.form.get(f"{day}-{time_block}-title", "")
                schedule_data[day][time_block]['time_mode'] = request.form.get(f"{day}-{time_block}-time_mode", "")
                schedule_data[day][time_block]['start_time'] = request.form.get(f"{day}-{time_block}-start_time", "")
                schedule_data[day][time_block]['type']['series']['id'] = request.form.get(f"{day}-{time_block}-series-id", "")
                schedule_data[day][time_block]['type']['series']['duration_minutes'] = int(request.form.get(f"{day}-{time_block}-duration_minutes", ""))
                schedule_data[day][time_block]['type']['series']['episode_mode'] = request.form.get(f"{day}-{time_block}-episode_mode", "")
                schedule_data[day][time_block]['type']['series']['on_series_end'] = request.form.get(f"{day}-{time_block}-on_series_end", "")

        # Save the updated data back to the file
        save_data(file_path, schedule_data)
        return redirect(url_for('edit_schedule_channel', channel=channel, template_files=get_template_files(), live_onload = live_load()))
    
    return render_template('edit_schedule.html', channel=channel, schedule_data=schedule_data, template_files=get_template_files(), live_onload = live_load())
'''

@app.route('/select_channel')
def select_channel():
    
    channels = get_available_channels()
    if not channels:
        flash("No channels with schedules found.", "warning")
    return render_template('select_channel.html', channels=channels, template_files = get_template_files(), live_onload = live_load())

def format_minutes(minutes):
    hours = minutes // 60
    remaining_minutes = minutes % 60

    if hours == 0:
        return f"{remaining_minutes} min"
    elif hours == 1 and remaining_minutes == 0:
        return f"{hours} hr"
    elif hours == 1 and remaining_minutes != 0:
        return f"{hours} hr {remaining_minutes} min"
    elif remaining_minutes == 0:
        return f"{hours} hr(s)"
    else:
        return f"{hours} hr(s) {remaining_minutes} min"

@app.template_global()
def to_str(value):
    return str(value)

@app.route('/')
def index():
    section_names = drones.sections()
    print(section_names)
    return render_template('index.html', drones=section_names, live_onload = live_load())

@socketio.on('start_process')
def handle_start_process(data):
    script = data['script']
    print(json.dumps(data,indent=4))
    # Clear the global buffer when starting a new process
    global_output_buffer.seek(0)
    global_output_buffer.truncate()
    args = data.get('arguments', '').split(',')
    process_args = ['python', '-u', script]
    for arg in args:
        process_args.append(arg.strip())
    process = subprocess.Popen(
        process_args,
        cwd=script_directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=False  # Ensure text mode for string output
    )

    with open(pid_file, 'w') as f:
        f.write(str(process.pid))
    
    # Start a background task to process log output
    #threading.Thread(target=process_output, args=(process,)).start()
    thread = threading.Thread(target=process_output, args=(process,))
    thread.daemon = True  # Ensure the thread runs independently
    thread.start()

@socketio.on('stop_process')
def handle_stop_process():
    # Retrieve the PID from the file or directly from the data
    # If PID is not in the data, try reading from a known PID file
    if not os.path.exists(pid_file):
        print("PID file not found, cannot stop process.")
        return
    with open(pid_file, 'r') as f:
        pid = int(f.read().strip())

    # Check if the process is running and terminate it
    try:
        process = psutil.Process(pid)
        if process.is_running():
            # Terminate the process using SIGTERM
            process.terminate()
            process.wait(timeout=5)  # Wait up to 5 seconds for process to terminate
            print(f"Process with PID {pid} has been terminated.")
        else:
            print(f"No process with PID {pid} is currently running.")
    except psutil.NoSuchProcess:
        print(f"No process found with PID {pid}.")
    except Exception as e:
        print(f"Error occurred while trying to terminate process: {e}")

    # Optionally, you can remove the PID file after stopping the process
    if os.path.exists(pid_file):
        os.remove(pid_file)

@socketio.on('start_beehive')
def handle_start_beehive(data):
    start_beehive(data)

@socketio.on('register')
def handle_register(data):
    client_sids[request.sid] = request.sid
    print(f"Registered client SID: {request.sid}")

def run_channel_creation(template_file, sid):
    try:
        # Redirect stdout to capture print statements
        original_stdout = sys.stdout
        sys.stdout = SocketIOOutput(sid)
        
        # Emit initial message
        socketio.emit('process_output', {'data': f"Starting channel creation from template: {template_file}.", 'return': False}, room=sid)
        
        file_path = f'channel_templates/{template_file}'
        channel_str = scheduler.create_new_channel(file_path)
        socketio.emit('process_output', {'data': f"Channel {channel_str} created from template {template_file}.", 'return': False}, room=sid)

        details_path = f'channels/{channel_str}/details.json'
        scheduler.generate_details(details_path, channel_str)
        socketio.emit('process_output', {'data': f"Details generated at {details_path}.", 'return': False}, room=sid)
        
        # Emit completion message
        socketio.emit('process_output', {'data': "Channel creation completed successfully!", 'return': True}, room=sid)


    except Exception as e:
        socketio.emit('process_output', {'data': f"Error: {str(e)}", 'return': True}, room=sid)

@app.route('/new_channel/<template_file>', methods=['GET'])
def new_channel(template_file):
    if os.path.splitext(template_file)[1] != ".json":
        flash("Invalid template file format.", "error")
        return render_template('select_channel.html', template_files=get_template_files(),live_onload=live_load())

    flash(f"Creating New Channel from {template_file}", "info")
    return render_template('loading.html', live_onload=live_load(), template_file=template_file)

'''@app.route('/nfo_generator/<path>', methods=['GET'])
def new_channel(path):
    if os.path.isdir(path) is False:
        flash("Not a valid directory", "error")
        return render_template(url_for('settings'), template_files=get_template_files(),live_onload=live_load())

    flash(f"Generating NFO Files in {path}", "info")
    return render_template('loading.html', live_onload=live_load(), path=path)'''

'''@app.route('/new_channel/<template_file>', methods=['GET'])
def new_channel(template_file):
    
    if os.path.splitext(template_file)[1] == ".json":
        file_path = f'channel_templates/{template_file}'
        channel_str = scheduler.create_new_channel(file_path)
        scheduler.generate_details(f'channels/{channel_str}/details.json',channel_str)
    schedule_data = load_data(f'channels/{channel_str}/schedule.json')
    
    flash(f"Channel '{int(channel_str)}' created successfully from {template_file} template.", "success")
    
    return render_template('edit_schedule.html', channel=channel_str,schedule=schedule_data, template_files=get_template_files(), live_onload = live_load())'''

@app.route('/start_beehive', methods=['POST'])
def http_start_beehive():
    print(request.get_data(as_text=True))
    data = {'script':'beehive.py','arguments':request.get_data(as_text=True)}
    start_beehive(data)
    return f"Starting beehive.py {request.get_data}"

def start_beehive(data):
    script = data['script']
    global_output_buffer.seek(0)
    global_output_buffer.truncate()
    
    # Step 1: Stop any existing process running on the same client before starting a new one
    stop_beehive(client_name=data.get('arguments', '').split(',')[1])
    
    # Step 2: Start a new process
    args = data.get('arguments', '').split(',')
    process_args = ['python', '-u', script]
    for arg in args:
        process_args.append(arg.strip())

    process = subprocess.Popen(
        process_args,
        cwd=script_directory,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=False  # Set to False if using binary mode
    )

    # Step 3: Store the process information in live.json
    
    client_name = args[1]
    live_data = read_live_file()
    if not live_data:
        live_data = {}
    print(live_data)
    if client_name != '' and client_name is not None:
        live_data[client_name] = {
            'pid': process.pid,
            'channel': args[0],
            'title': "",  # Placeholder for title (to be updated by another function)
            'category': ""  # Placeholder for category (to be updated by another function)
        }
        save_data(live_file, live_data)

    # Start a background thread to handle log output processing
    '''thread = threading.Thread(target=process_output, args=(process,))
    thread.daemon = True
    thread.start()'''

    print(f"[INFO] Started new process with PID {process.pid}.")

@socketio.on('stop_beehive')
def handle_stop_beehive(client_name):
    stop_beehive(client_name)

@app.route('/stop_beehive', methods=['POST'])
def http_stop_beehive():
    client_name = request.get_data(as_text=True)
    stop_beehive(client_name)
    return "Stopping beehive.py"

def stop_beehive(client_name):
    #print(f"handle_stop_beehive {client_name}")
    """
    Handles the stop_beehive event to terminate a running script process.
    If a client_name is not specified, attempts to read the PID from the live.json file.
    """
    if not client_name or client_name == 'undefined':
        print("No client_name provided. Cannot stop the process without a reference.")
        return
    
    if not os.path.exists(live_file):
        print("PID file not found, cannot stop process.")
        return

    # Step 1: Load the JSON file and check if the client entry exists
    live_data = read_live_file()
    print(live_data)
    if client_name not in live_data:
        print(f"No process entry found for client: {client_name}.")
        return

    # Step 2: Retrieve the PID and other details for the specified client
    pid = live_data[client_name].get('pid')
    
    # Step 3: Attempt to terminate the process
    try:
        process = psutil.Process(pid)
        if process.is_running():
            # Terminate the process using SIGTERM
            process.terminate()
            process.wait(timeout=5)  # Wait up to 5 seconds for process to terminate
            print(f"Process with PID {pid} has been terminated.")
        else:
            print(f"No process with PID {pid} is currently running.")
    except psutil.NoSuchProcess:
        print(f"No process found with PID {pid}.")
    except Exception as e:
        print(f"Error occurred while trying to terminate process: {e}")

    # Step 4: Remove the client entry from the live.json file
    del live_data[client_name]
    save_data(live_file, live_data)

    print(f"Process entry for client {client_name} removed from live.json.")

@app.route('/current_output')
def current_output():
    global global_output_buffer
    global_output_buffer.seek(0)
    output = global_output_buffer.getvalue()
    if output.endswith('[RETURN]'):
        return jsonify({'data': output, 'return': True, 'newline': False})
    else:
        return jsonify({'data': output, 'return': False, 'newline': True})

def live_load():
    live_data = load_data('live.json')
    live_info = {}
    for client,data in live_data.items():
        #print(data['details'].get('tag'))
        details_text = ''
        channel_str = "{:03}".format(int(data.get('channel')))
        channel_details = load_data(f'channels/{channel_str}/details.json')
        try:
            category = data.get('category')
            
            if category == "series":
                show_key = data['details'].get('show_key')
                print(show_key)
                episode_key = data['details'].get('key')
                print(episode_key)
                show_data = shows_details.get(show_key)
                if show_data:
                    episode_data = show_data['files'].get(episode_key)
                    print(episode_data.get('title'))
                    details_text += f"{episode_data['episode_details'][0].get('title')} "
                    details_text += f"(S{episode_data['episode_details'][0].get('season')}E{episode_data['episode_details'][0].get('episode')}): "
                    certification = f"{show_data.get('certification','')}"
                    try:
                        details_text = episode_data['episode_details'][0].get('plot','')[:300]
                    except TypeError:
                        details_text = ''
                    if len(details_text) >= 300:
                        plot_text = episode_data['episode_details'][0].get('plot','')[:300]+"..."
                    else:
                        plot_text = episode_data['episode_details'][0].get('plot','')
                    details_text += f"{plot_text} {episode_data['episode_details'][0].get('runtime')} mins"
                raw_thumb_path = os.path.splitext(episode_key)[0]+'-thumb.jpg'
                thumbnail_path = url_for('serve_show',filename=raw_thumb_path.replace(config['Settings']['Library Mount Point'],'') if os.path.exists(raw_thumb_path) else '/static/beeprev2.png')
            elif category == "movie":
                key = data['details'].get('key')
                movie_data = movies_details.get(key)
                try:
                    actor_list = movie_data.get('actor', [])
                except:
                    actor_list = []
                actor_names = []
                if len(actor_list) > 0:
                    for actor in actor_list:
                        if len(actor_names) < 2:
                            actor_name = actor.get('name')
                            actor_names.append(actor_name)
                        if len(actor_names) > 1:
                            actors = ", ".join(actor_names)
                        elif len(actor_names) == 1:
                            actors = actor_names[0]
                        else:
                            actors = ''
                else:
                    actors = ''
                plot_text = movie_data.get('plot', '')
                if len(plot_text) > 300:
                    plot_text = plot_text[:300]
                details_text += f"Starring {actors}: {plot_text} {movie_data.get('runtime')}"
                certification = movie_data.get('certification','')
                if certification:
                    if '/' in certification:
                        certification = certification.split('/')[0].strip()
                else:
                    certification = ''
                #certification = "Rated: "+certification
                raw_path = os.path.splitext(movie_data['files'][0].get('filepath'))[0]
                print(raw_path)
                if os.path.isfile(raw_path+'-landscape.jpg'):
                    raw_thumb_path = raw_path+'-landscape.jpg'
                elif os.path.isfile(raw_path+'-clearart.png'):
                    raw_thumb_path = raw_path+'-clearart.png'
                elif os.path.isfile(raw_path+'-banner.jpg'):
                    raw_thumb_path = raw_path+'-banner.jpg'
                elif os.path.isfile(raw_path+'-clearlogo.png'):
                    raw_thumb_path = raw_path+'-clearlogo.png'
                elif os.path.isfile(raw_path+'-discart.jpg'):
                    raw_thumb_path = raw_path+'-discart.jpg'
                elif os.path.isfile(raw_path+'-keyart.jpg'):
                    raw_thumb_path = raw_path+'-keyart.jpg'
                elif os.path.isfile(raw_path+'-poster.jpg'):
                    raw_thumb_path = raw_path+'-poster.jpg'
                elif os.path.isfile(raw_path+'-fanart.jpg'):
                    raw_thumb_path = raw_path+'-fanart.jpg'
                else:
                    raw_thumb_path = None
                    
                thumbnail_path = url_for('serve_movie',filename=raw_thumb_path.replace(config['Settings']['Library Mount Point'],'')) if raw_thumb_path is not None else url_for('static', filename='beeprev2.png').strip()
                print(thumbnail_path)
            elif category == "interstitial":
                key = data['details'].get('key')
                library_key = data['details'].get('library')
                certification = "COMMERCIAL"
                '''tag_raw = data['details'].get('tag',[])
                if isinstance(tag_raw, list):
                    certification = ', '.join(tag_raw)
                else:
                    certification = tag_raw
                if len(certification) > 100:
                    certification = certification[:100]'''
                thumbnail_path = '/static/beeprev2.png'
                interstitials_configs = []
                for interstitial_key, interstitial_json in config['Interstitials'].items():
                    interstitials_configs.append(interstitial_json)
                interstitials_details = load_data(interstitials_configs[data['details'].get('library',0)])
                interstitial_data = interstitials_details.get(key,{})
                details_text = interstitial_data['movie'].get('plot','')
                if len(details_text) > 250:
                    details_text = details_text[:250]+'...'
            else:
                try:
                    if isinstance(tag_raw, list):
                        tags_text = ', '.join(tag_raw)
                    else:
                        tags_text = tag_raw
                except UnboundLocalError:
                    tags_text = ''
                details_text = data.get('plot', tags_text)
                if len(details_text) >= 330:
                    details_text = details_text[:330]+"..."
        except KeyError:
            tag_raw = ''
        try:
            image_path = thumbnail_path
        except UnboundLocalError:
            image_path = '/static/beeprev2.png'
        try:
            cert = certification
        except UnboundLocalError:
            cert = ''
        live_dict = {
            'channel-title': f"{client}",
            'title-text': (data.get('title')),
            'details-text': details_text.replace("'",""),
            'time-date-text': cert,
            'channel-number': f"{html.escape(channel_details.get('channel_call_letters',''))}-{channel_details.get('number_int')}",
            'prevue-image': image_path
                
        }
        live_info[client] = (live_dict)
    try:
        return_dict =  live_info
    except:
        return_dict =  {
            'off': {
                'channel-title': 'NOT PLAYING', 
                'title-text': '',
                'details-text': '', 
                'time-date-text': '', 
                'channel-number': '',
                'prevue-image': '/static/beeprev2.png'
            }
        }
    print(return_dict)
    return return_dict

def process_output(process):
    global global_output_buffer

    # Capture output byte-by-byte
    output_buffer = bytearray()
    print("Capturing process output...")
    
    while True:
        char = process.stdout.read(1)  # Read one byte at a time
        if char == b'':  # EOF
            print("End of process, stopping output capture.")
            break

        output_buffer.extend(char)

        # Detect carriage return
        if b'\r' in output_buffer:
            output_line = output_buffer.decode('utf-8')
            if 'frame=' in output_line:
                ffmpeg_frame_output = output_line
                running_process_output['ffmpeg_frame_output'] = ffmpeg_frame_output
            else:
                carriage_return_line = output_line
                running_process_output['carriage_return_line'] = carriage_return_line
            
            # Emit the processed output
            socketio.emit('process_output', {'data': output_line.strip(), 'return': True, 'newline': False})
            global_output_buffer.write(output_line + '\n')
            global_output_buffer.flush()
            output_buffer.clear()

        # Handle newline
        if b'\n' in output_buffer:
            output_line = output_buffer.decode('utf-8')

            # Emit the processed output
            socketio.emit('process_output', {'data': output_line.strip(), 'return': False, 'newline': True})
            global_output_buffer.write(output_line + '\n')
            global_output_buffer.flush()
            output_buffer.clear()

    
@app.route('/new')
def new():
    return render_template('new.html', template_files=get_template_files(), shows_data=shows_details, movies_data=movies_details,live_onload=live_load())

@app.route('/last/<channel>', methods=['GET','POST'])
def last(channel):
    file_path = f'channels/{channel}/last.json'
    try:
        file_data = load_data(file_path)
        file_data = dict(sorted(file_data.items(), key=lambda item: item[1]["title"]))
    except FileNotFoundError:
        app.logger.error(f"File not found: {file_path}")
        abort(404)  # Return a 404 error if the file is not found

    if request.method == 'POST':
        for entry, path_key in request.form.items():
            file_data[entry] = {
                'title': shows_details[entry]['title'],
                'episode_path': path_key,
                'season_number': shows_details[entry]['files'][path_key]['episode_details'][0]['season'],
                'episode_number': shows_details[entry]['files'][path_key]['episode_details'][0]['episode'],
            }
        print(json.dumps(file_data,indent=4))
        flash(f'Changes to {channel} last episodes file saved successfully!', 'success')
        save_data(file_path, file_data)

    return render_template('last.html',shows_data=shows_details, live_onload=live_load(),channel=channel, file_data=file_data)
    
@app.route('/edit/<template_file>', methods=['GET', 'POST'])
def edit(template_file):
    if os.path.splitext(template_file)[1] == ".json":
        template_files = get_template_files()
        file_path = f'channel_templates/{template_file}'
        try:
            data = load_data(file_path)
        except FileNotFoundError:
            app.logger.error(f"File not found: {file_path}")
            abort(404)  # Return a 404 error if the file is not found
    else:
        file_path = f'channels/{template_file}/schedule.json'
        try:
            file_data = load_data(file_path)
            data = file_data.get('Template')
        except FileNotFoundError:
            app.logger.error(f"File not found: {file_path}")
            abort(404)  # Return a 404 error if the file is not found

    app.logger.debug(f"File path: {file_path}")  # Add this line for logging


    try:
        shows_data = load_data('library/shows_details.json')
    except FileNotFoundError:
        app.logger.error(f"File not found: {'library/shows_details.json'}")
        abort(404)  # Return a 404 error if the file is not found

    try:
        movies_data = load_data('library/movies_details.json')
    except FileNotFoundError:
        app.logger.error(f"File not found: {'library/movies_details.json'}")
        abort(404)  # Return a 404 error if the file is not found

    if request.method == 'POST':
        # Update data with values from the form
        for block_name in data:
            block_data = data[block_name]
            block_data['start_time'] = request.form.get(f"{block_name}-start_time", "")
            block_data['end_time'] = request.form.get(f"{block_name}-end_time", "")
            block_data['allowed_genres'] = request.form.get(f"{block_name}-allowed_genres", "")
            block_data['forbidden_genres'] = request.form.get(f"{block_name}-forbidden_genres", "")
            block_data['allowed_ratings'] = request.form.get(f"{block_name}-allowed_ratings", "")
            block_data['forbidden_ratings'] = request.form.get(f"{block_name}-forbidden_ratings", "")
            block_data['allowed_decades'] = request.form.get(f"{block_name}-allowed_decades", "")
            block_data['forbidden_decades'] = request.form.get(f"{block_name}-forbidden_decades", "")
            block_data['options'] = request.form.get(f"{block_name}-optionsHidden", "")
            block_data['complexity'] = request.form.get(f"{block_name}-complexityHidden", "")
            if f"{block_name}-interstitialsHidden" in request.form:
                interstitials_data = request.form.get(f"{block_name}-interstitialsHidden")
                if interstitials_data:
                    block_data['interstitials'] = interstitials_data



        # Save the modified data back to the file
        if os.path.splitext(template_file)[1] == ".json":
            save_data(file_path, data)
        else:
            file_data['Template'] = data
            save_data(file_path, file_data)
        app.logger.info("JSON Data saved successfully")
        
        #return render_template('edit.html', template_files=get_template_files(), current_file=template_file, data=data, shows_data=shows_data, movies_data=movies_data)
        return redirect(url_for('interstitial_settings', template_file=f'{template_file}'))

    # Render the edit template with existing data
    return render_template('edit.html', template_files=get_template_files(), current_file=template_file, data=data, shows_data=shows_data, movies_data=movies_data, live_onload = live_load())
    
@app.route('/interstitial_settings/<template_file>', methods=['GET', 'POST'])
def interstitial_settings(template_file):
    
    if os.path.splitext(template_file)[1] == ".json":
        template_files = get_template_files()
        file_path = f'channel_templates/{template_file}'
        try:
            data = load_data(file_path)
        except FileNotFoundError:
            app.logger.error(f"File not found: {file_path}")
            abort(404)  # Return a 404 error if the file is not found
    else:
        file_path = f'channels/{template_file}/schedule.json'
        try:
            file_data = load_data(file_path)
            data = file_data.get('Template')
            
        except FileNotFoundError:
            app.logger.error(f"File not found: {file_path}")
            abort(404)  # Return a 404 error if the file is not found

    app.logger.debug(f"File path: {file_path}")  # Add this line for logging

    try:
        shows_data = load_data('library/shows_details.json')
    except FileNotFoundError:
        app.logger.error(f"File not found: {'library/shows_details.json'}")
        abort(404)  # Return a 404 error if the file is not found

    try:
        movies_data = load_data('library/movies_details.json')
    except FileNotFoundError:
        app.logger.error(f"File not found: {'library/movies_details.json'}")
        abort(404)  # Return a 404 error if the file is not found

    if request.method == 'POST':
        # Load existing data from the file
        existing_data = data
        print(json.dumps(request.form,indent=4))
        # Create a new dictionary to hold the merged data
        merged_data = {}

        # Update merged_data with values from the form
        for block_name in existing_data:
            if block_name in data:
                merged_data[block_name] = {**existing_data[block_name], **data[block_name]}
            else:
                merged_data[block_name] = existing_data[block_name]

            # Construct the interstitials dictionary directly
            interstitials = {
                'commercials': request.form.get(f"{block_name}-commercials", 0),
                'tags': request.form.get(f"{block_name}-tag", 0),
                'year': request.form.get(f"{block_name}-year", 0),
                'trailers': request.form.get(f"{block_name}-trailers", 0),
                'genre': request.form.get(f"{block_name}-genre", 0),
                'date': request.form.get(f"{block_name}-date", 0),
                'music_videos': request.form.get(f"{block_name}-music_videos", 0),
                'studio': request.form.get(f"{block_name}-studio", 0),
                'scheduled': request.form.get(f"{block_name}-scheduled", 0),
                'other_videos': request.form.get(f"{block_name}-other_videos", 0),
                'actor': request.form.get(f"{block_name}-actor", 0),
            }
            merged_data[block_name]['interstitials'] = interstitials
            print(json.dumps(interstitials,indent=4))
        # Save the merged data back to the file
        if os.path.splitext(template_file)[1] == ".json":
            save_data(file_path, merged_data)
        else:
            file_data['Template'] = merged_data
            save_data(file_path, file_data)
        flash(f'Changes to {template_file} saved successfully!', 'success')
        app.logger.info(f"Data saved successfully to {file_path}")
        #print(json.dumps(merged_data, indent=4))

        
        return redirect(url_for('select_channel'))
        #return render_template('interstitial_settings.html', template_files=get_template_files(), current_file=template_file, data=merged_data, shows_data=shows_data, movies_data=movies_data, live_onload = live_load())

    # Render the template with existing data
    return render_template('interstitial_settings.html', template_files=get_template_files(), current_file=template_file, data=data, shows_data=shows_data, movies_data=movies_data, live_onload = live_load())

@app.route('/schedule/<channel>', methods=['GET'])
def schedule(channel):
    kiosk_mode = False
    if request.method == 'GET':
        if request.args.get('kiosk'):
            kiosk_mode = request.args.get('kiosk')
    file_path = f'channels/{channel}/daily_schedule.json'
    app.logger.debug(f"File path: {file_path}")  
    try:
        data = load_data(file_path)
    except FileNotFoundError:
        app.logger.error(f"File not found: {file_path}")
        abort(404)  # Return a 404 error if the file is not found

    now = datetime.datetime.now() + datetime.timedelta(minutes=0)
    today = datetime.date.today()

    rows = []
    for day,schedule in data.items():
        day_obj = datetime.datetime.strptime(day, '%Y-%m-%d')
        if day_obj.date() >= today or day_obj.date() >= today - datetime.timedelta(days=1):
            if (day_obj.date() == today - datetime.timedelta(days=1) and now < datetime.datetime.strptime(f"{next(iter(schedule))}", '%H:%M:%S.%f')) or day_obj.date() >= today:
                rows.append(f'</tbody><tr onclick="toggleHide(\'{day}\')"><td class="box firstcolumn yellow">Ch. {int(channel)}</td><td class="box yellow" style="width:100%;text-align:left;">{datetime.datetime.strptime(day, "%Y-%m-%d").strftime("%B %d, %Y")}</td></tr><tbody id="{day}">')
            for time, entry in schedule.items():
                if day_obj.date() == today - datetime.timedelta(days=1) and datetime.datetime.strptime(f"{time}", '%H:%M:%S.%f') < datetime.datetime.strptime(f"{next(iter(schedule))}", '%H:%M:%S.%f') and now < datetime.datetime.strptime(f"{next(iter(schedule))}", '%H:%M:%S.%f'):
                    day_obj += datetime.timedelta(days=1)
                    day = day_obj.strftime('%Y-%m-%d')
                elif day_obj.date() == today and datetime.datetime.strptime(f"{time}", '%H:%M:%S.%f') < datetime.datetime.strptime(f"{next(iter(schedule))}", '%H:%M:%S.%f'):
                    day_obj += datetime.timedelta(days=1)
                    day = day_obj.strftime('%Y-%m-%d')
                if datetime.datetime.strptime(f"{day} {entry.get('end_time')}", '%Y-%m-%d %H:%M:%S.%f') >= now:
                    row = f'<tr title="Double-click to start channel" oncontextmenu="clientSelect({channel}); return false;"><td class="box yellow firstcolumn">{time.split(".")[0]}</td>'
                    cell_color = "blue"
                    title_text = f"<span class='yellow'>{entry.get('title').upper()}"
                    cell_text = ''
                    if next(iter(entry["type"])).upper() == "MOVIE":
                        cell_color = "cyan"
                        if entry.get("kevin_bacon_mode") is not None:
                            if entry["kevin_bacon_mode"].get('setting') is not None:
                                cell_color = "red"
                                if not isinstance(entry['kevin_bacon_mode'], list):
                                    entry['kevin_bacon_mode'] = [entry['kevin_bacon_mode']]
                                for kbm in entry['kevin_bacon_mode']:
                                    print(kbm)
                                    if kbm is not None:
                                        if kbm['degree'][0] is not None:
                                            kbm_degree = ', '.join(kbm['degree'])
                                            if kbm['setting'] == 'certification':
                                                kbm['setting'] = 'rating'
                                                kbm_degree = ''
                                                for kbmd in kbm['degree']:
                                                    kbm_degree += kbmd.split('/')[0].split(':')[-1].strip()+' '
                                        elif kbm['setting'] == 'credits':
                                            kbm['setting'] = 'writer'
                                        try:
                                            kbm_text = f"Linked from {kbm['title']} through the {kbm['setting']} {kbm_degree.strip()}."
                                        except UnboundLocalError:
                                            kbm_text = ''
                                            cell_color = 'cyan'
                                        cell_text += f"{kbm_text} "
                        entry_date = f"({entry['type']['movie'].get('year','')})"
                        title_text += f" {entry_date}</span> "
                        movie_cast = entry['type']['movie'].get('cast')
                        if movie_cast is not None:
                            if isinstance(movie_cast, str):
                                # If it's a string, pass it on
                                result = movie_cast
                            elif isinstance(movie_cast, dict):
                                # If it's a list with at least two elements, convert the first two to a comma-separated string
                                result = movie_cast.get('name')
                            elif isinstance(movie_cast, list) and len(movie_cast) >= 2:
                                # If it's a list with at least two elements, convert the first two to a comma-separated string
                                result = f"{movie_cast[0].get('name')}, {movie_cast[1].get('name')}"
                            elif isinstance(movie_cast, list) and len(movie_cast) < 2:
                                # If it's a list but has fewer than two elements, handle it (e.g., use the only element or default)
                                result = movie_cast[0].get('name') if movie_cast else ""
                            else:
                                # Handle other unexpected cases
                                result = ""
                            cell_text += f"{result}. "
                    elif next(iter(entry["type"])).upper() == "SERIES":
                        try:
                            date_formatted = datetime.datetime.strptime(entry['type']['series'].get('date',''), '%Y-%m-%d').strftime('%B %d, %Y')
                            entry_date = f"Aired: {date_formatted}."
                        except:
                            entry_date = ''
                        episode_mode = entry['type']['series'].get('episode_mode','')
                        if episode_mode == "random":
                            cell_color = "grey"
                        cell_text += f" {entry_date}</span> "
                    row += f'<td style="text-align:left;width:100%;" class="box {cell_color}">{title_text}</td></tr><tr title="Double-click to start channel" oncontextmenu="clientSelect({channel}); return false;"><td style="text-align:left;height:auto;min-width:907px;width:auto;" class="box {cell_color} fullspanx">'
                    
                    if entry.get("summary","") is not None:
                        cell_text += entry.get("summary","")
                    row += f'{cell_text} {entry.get("duration_min")} mins'
                    if next(iter(entry["type"])) == 'movie':
                        if entry["type"]["movie"].get('tag') is not None:
                            tags = ', '.join(map(str, entry["type"]["movie"].get('tag',[])))
                        else:
                            tags = ''
                    else:
                        tags = ''
                    row += f'</td></tr>'
                    rows.append(row)
                    
    return render_template('schedule.html', kiosk_mode=kiosk_mode, channel=channel,config_file=config_file, rows=rows, live_onload = live_load())

@app.route('/edit_template', methods=['GET', 'POST'])
def edit_template(template_file):
    

    file_path = f'channel_templates/{template_file}'
    app.logger.debug(f"File path: {file_path}")  # Add this line for logging
    try:
        data = load_data(file_path)
    except FileNotFoundError:
        app.logger.error(f"File not found: {file_path}")
        abort(404)  # Return a 404 error if the file is not found

    try:
        shows_data = load_data('library/shows_details.json')
    except FileNotFoundError:
        app.logger.error(f"File not found: {'library/shows_details.json'}")
        abort(404)  # Return a 404 error if the file is not found

    try:
        movies_data = load_data('library/movies_details.json')
    except FileNotFoundError:
        app.logger.error(f"File not found: {'library/movies_details.json'}")
        abort(404)  # Return a 404 error if the file is not found

    if request.method == 'POST':
        # Update data with values from the form
        for block_name in data:
            block_data = data[block_name]
            block_data['start_time'] = request.form.get(f"{block_name}-start_time", "")
            block_data['end_time'] = request.form.get(f"{block_name}-end_time", "")
            block_data['allowed_genres'] = request.form.get(f"{block_name}-allowed_genres", "")
            block_data['forbidden_genres'] = request.form.get(f"{block_name}-forbidden_genres", "")
            block_data['allowed_ratings'] = request.form.get(f"{block_name}-allowed_ratings", "")
            block_data['forbidden_ratings'] = request.form.get(f"{block_name}-forbidden_ratings", "")
            block_data['allowed_decades'] = request.form.get(f"{block_name}-allowed_decades", "")
            block_data['forbidden_decades'] = request.form.get(f"{block_name}-forbidden_decades", "")
            block_data['options'] = request.form.get(f"{block_name}-optionsHidden", "")
            block_data['complexity'] = request.form.get(f"{block_name}-complexityHidden", "")
            if f"{block_name}-interstitialsHidden" in request.form:
                interstitials_data = request.form.get(f"{block_name}-interstitialsHidden")
                if interstitials_data:
                    block_data['interstitials'] = interstitials_data



        # Save the modified data back to the file
        save_data(file_path, data)
        app.logger.info("JSON Data saved successfully")
        
        #return render_template('edit.html', template_files=get_template_files(), current_file=template_file, data=data, shows_data=shows_data, movies_data=movies_data)
        return redirect(url_for('interstitial_settings', template_file=f'{template_file}'), template_files=get_template_files(), live_onload = live_load())

    # Render the edit template with existing data
    return render_template('edit.html', template_files=get_template_files(), current_file=template_file, data=data, shows_data=shows_data, movies_data=movies_data, live_onload = live_load())

@app.route('/about', methods=['GET'])
def about():
    return render_template('about.html', config_file=config_file, template_files=get_template_files(), live_onload = live_load())

'''@app.route('/about', methods=['GET'])
def edit_schedule():
    return render_template('edit.html', config_file=config_file, template_files=get_template_files(), live_onload = live_load())'''

@app.route('/movies/<path:filename>')
def serve_movie(filename):
    # Update this to your actual directory where the files are located
    media_dir = config['Settings']['Library Mount Point']
    return send_from_directory(media_dir, filename)
    
@app.route('/shows/<path:filename>')
def serve_show(filename):
    # Update this to your actual directory where the files are located
    media_dir = config['Settings']['Library Mount Point']
    return send_from_directory(media_dir, filename)

@app.route('/show_schedule', methods=['GET'])
def show_schedule():
    channels = []
    schedule_data = {}
    kiosk_mode = False
    now = datetime.datetime.now()
    if request.method == 'GET':
        if request.args.get('kiosk'):
            kiosk_mode = request.args.get('kiosk')
        if request.args.get('offset'):
            now += datetime.timedelta(minutes=int(request.args.get('offset')))
    if kiosk_mode is not False:
        kiosk_get = f'?kiosk={kiosk_mode}'
    else:
        kiosk_get = ''
    
    html_cell = f'<td class="box firstcolumn current-time" style="text-align: end; position: sticky; top: 0; z-index:1;" id="current-time" onclick="window.location.href=window.location.pathname + \'{kiosk_get}\';"></td>'
    time_row = html_cell
    empty_row = f'<tr><td class="box firstcolumn current-time" style="text-align: end;"></td>'
    # Add the next 12 half-hour blocks
    blocks = []
    
    for b in range(12):
        if b == 0:
            offset = -60
        else:
            offset = b*30
        if request.args.get('offset'):
            offset += int(request.args.get('offset'))
        start_block = now - datetime.timedelta(minutes=now.minute % 30, seconds=now.second, microseconds=now.microsecond)
        next_block = start_block + datetime.timedelta(minutes=30 * b)
        next_block_string = next_block.strftime("%H:%M")
        if kiosk_get == '':
            offset_get = f'?offset={offset}'
        else:
            offset_get = f'&offset={offset}'
        html_cell = f'<td class="box yellow" onclick="window.location.href=window.location.pathname + \'{kiosk_get}{offset_get}\';">{next_block_string}</td>'
        time_row += html_cell
        empty_row+=f'<td class="box yellow" onclick="window.location.href=window.location.pathname + \'{kiosk_get}{offset_get}\';">{next_block_string}</td>'
        blocks.append({'start':next_block,'end':next_block+ datetime.timedelta(minutes=30),'html':html_cell})
    print(blocks)
    time_row += '</th>'
    #time_row = html_string
    schedule_data['time'] = blocks
    today = now.strftime('%Y-%m-%d')
    
    # Populate channels list
    for item in os.listdir('channels/'):
        item_path = os.path.join('channels/', item)
        if os.path.isdir(item_path):
            channels.append((item, os.path.join(item_path, 'active_schedule.json'), os.path.join(item_path, 'details.json')))
    
    # Iterate through channels
    padding = 10  # 5px padding on each side
    border = 8    # Assuming 4px border on each side
    default_cell_width = 140  # Default width for a 30-minute block
    max_width = 1920
    cell_width = default_cell_width
    cell_color = "blue"
    channel_data = {}
    for channel_number, file_path, details_path in channels:
        app.logger.debug(f"Channel {channel_number} File Path: {file_path}")

        try:
            details = load_data(details_path)
        except FileNotFoundError:
            app.logger.error(f"File not found: {details_path}")
            details = {}

        ch_num = int(channel_number.split(' ')[0])
        
        channel_data[ch_num] = {'channel':f"<td title='{details.get('channel_name','')}&#10;Click to view channel schedule&#10;Right click to start channel' id='ch_num' data-page='schedule/{channel_number.split(' ')[0]}' oncontextmenu= 'clientSelect({ch_num}); return false;' data-dialog='{ch_num}' class='clickable box blue yellow tall firstcolumn channel'>{details.get('icon','')}</br>{ch_num}</br>{details.get('channel_call_letters','')}</td>"}
        schedule_data[ch_num] = {'html':[f"<td title='{details.get('channel_name','')}&#10;Click to view channel schedule&#10;Right click to start channel' id='ch_num' data-page='schedule/{channel_number.split(' ')[0]}' oncontextmenu= 'clientSelect({ch_num}); return false;' data-dialog='{ch_num}' class='clickable box blue yellow tall firstcolumn channel'>{details.get('icon','')}</br>{ch_num}</br>{details.get('channel_call_letters','')}</td>"]}
        html_string = f"<tr>{channel_data[ch_num]['channel']}"

        try:
            data = load_data(file_path)
        except FileNotFoundError:
            app.logger.error(f"File not found: {file_path}")
            continue
        
        if data:
            daily_schedule = data
            
            total_width_used = 0
            cells_created = 0
            block_filled = False
            prev_start_time = (blocks[0]['start'] - datetime.timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S.%f")
            for i in range(12):
                block_start = blocks[i]['start']
                print(i)
                '''if total_width_used > max_width/12*11:
                    break'''
                '''if not block_filled and total_width_used < max_width and i != 0:
                    if prev_end_time_obj > blocks[i]['start']:
                        time_between = ((blocks[i]['start'] - prev_end_time_obj).seconds // 60)
                    
                    if time_between > 12:
                        # Add an empty block if no content and if there is space left
                        between_width = calculate_cell_width(time_between, cell_width, padding, border)
                        block_html = f"<td class='box blue tall' style='width:{min(between_width,max_width-total_width_used)}px'>{blocks[i]['start']}-{end_time_obj}={time_between}</td>"
                        total_width_used += min(between_width,max_width-total_width_used)

                        html_string += block_html'''
                block_filled = False
                block_end = blocks[i]['end']
                block_html = ""
                block_dict = {}
                if i > 0:
                    after_start_time = False
                else:
                    after_start_time = True
                    
                schedule_items = list(daily_schedule.items())
                #for j, start_time, schedule_entry in enumerate(daily_schedule.items()):
                for j in range(len(schedule_items)-1):
                    start_time, schedule_entry = schedule_items[j]
                    #print(start_time)
                    start_time_obj = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S.%f")
                    end_time_obj = start_time_obj + datetime.timedelta(seconds=schedule_entry['duration_s'])
                    rounded_minutes = round((end_time_obj-start_time_obj).total_seconds()/60)
                    
                    prev_start_time_obj = datetime.datetime.strptime(prev_start_time, "%Y-%m-%d %H:%M:%S.%f")
                    
                    # Add small tolerance to handle close times
                    overlap_start = max(start_time_obj, blocks[i]['start'])
                    overlap_end = min(blocks[i]['end'] + datetime.timedelta(minutes=1), block_end)  # Adding a 1-minute tolerance
                    if (start_time == prev_start_time and i != 1) or (start_time_obj < blocks[i]['start'] and end_time_obj <= blocks[i]['start']):
                        after_start_time = True
                        continue
                    elif after_start_time is True:

                        # Check if the entry overlaps with the current block
                        if prev_start_time_obj < start_time_obj < block_end and (i == 0 and end_time_obj > block_start + datetime.timedelta(minutes=10)) or (i != 0 and end_time_obj >= block_start):
                            
                            
                            '''if total_width_used >= (cell_width-padding-border)*(i+1):
                                continue'''
                            if (cell_width-padding-border)*(i) < total_width_used < (cell_width-padding-border)*(i+1):
                                cell_width = default_cell_width
                            else:
                                cell_width = default_cell_width
                            
                            duration_min_actual = (end_time_obj - start_time_obj).seconds // 60
                            
                            if i == 0:
                                minutes_remaining = (end_time_obj - block_start).seconds //60
                                prev_end_time_obj = blocks[i]['start']
                                if minutes_remaining < duration_min_actual:
                                    duration_min_total = minutes_remaining
                                else:
                                    duration_min_total = duration_min_actual
                                if start_time_obj >= blocks[i]['start']:
                                    time_between = (start_time_obj - blocks[i]['start']).seconds 
                                else:
                                    time_between = 0 
                                minutes_between = time_between // 60
                            else:
                                if start_time_obj < blocks[0]['start']:
                                    duration_min_total = (end_time_obj - blocks[0]['start']).seconds // 60
                                else:
                                    duration_min_total = (end_time_obj - start_time_obj).seconds // 60
                                
                                try:
                                    if prev_end_time_obj <= blocks[i]['start']:
                                        minutes_between = (start_time_obj - prev_end_time_obj).seconds // 60
                                    elif prev_end_time_obj > blocks[i]['start']:
                                        time_between = (start_time_obj - prev_end_time_obj).seconds 
                                        minutes_between = time_between // 60
                                except UnboundLocalError:
                                    pass
                            '''if time_between > 0 and minutes_between >= 10 and start_time != prev_start_time:
                                # Add an empty block if no content and if there is space left
                                empty_block_width = calculate_cell_width(minutes_between, cell_width, padding, border)
                                empty_block = f"<td class='box {cell_color} tall' style='width:{min(empty_block_width,max_width-total_width_used)}px' title='{(start_time_obj - prev_end_time_obj).seconds // 60}/{minutes_between}'>{minutes_between}</td>"
                                total_width_used += min(empty_block_width,max_width-total_width_used)

                                html_string += empty_block
                            else:
                                empty_block = '' 
                            block_html += empty_block'''
                            entry_width = calculate_cell_width(duration_min_total, cell_width, padding, border)
                            kbm_text = None
                            total_width = entry_width #min(entry_width, max_width - total_width_used)  # Ensure row width doesn't exceed max_width
                            cell_color = 'blue'
                            schedule_title = schedule_entry['title']
                            details_text = ''
                            if 'movie' in schedule_entry['type']:
                                movie_info = schedule_entry['type']['movie']
                                if 'kevin_bacon_mode' in schedule_entry:
                                    if schedule_entry['kevin_bacon_mode'] is not None:
                                        if not isinstance(schedule_entry['kevin_bacon_mode'], list):
                                            schedule_entry['kevin_bacon_mode'] = [schedule_entry['kevin_bacon_mode']]
                                        for kbm in schedule_entry['kevin_bacon_mode']:
                                            print(kbm)
                                            if kbm is not None:
                                                if kbm['degree'][0] is not None:
                                                    kbm_degree = ', '.join(kbm['degree'])
                                                    if kbm['setting'] == 'certification':
                                                        kbm['setting'] = 'rating'
                                                        kbm_degree = ''
                                                        for kbmd in kbm['degree']:
                                                            kbm_degree += kbmd.split('/')[0].split(':')[-1].strip()+' '
                                                elif kbm['setting'] == 'credits':
                                                    kbm['setting'] = 'writer'
                                                cell_color = 'red'
                                                try:
                                                    kbm_text = f"Linked from {kbm['title']} through the {kbm['setting']} {kbm_degree.strip()}."
                                                except UnboundLocalError:
                                                    kbm_text = ''
                                                    cell_color = 'cyan'
                                            else:
                                                cell_color = 'cyan'
                                            
                                    else:
                                        cell_color = 'cyan'
                                try:
                                    cell_text_info = remove_accents(f"\"{schedule_title.upper()}\" ({movie_info['year']}) {movie_info['cast'][0]['name']}, {movie_info['cast'][1]['name']}. {duration_min_actual} mins")
                                    cast_text = "Starring " + remove_accents(movie_info['cast'][0]['name']+', '+movie_info['cast'][1]['name']+': ')
                                except IndexError:
                                    cell_text_info = f"\"{schedule_title.upper()}\" ({movie_info['year']}) {duration_min_actual} mins"
                                    cast_text = ''
                                title_text = f"{remove_accents(schedule_title.upper())} ({movie_info['year']})"
                                details_text = cast_text
                                try:
                                    movie_path, movie_filename = os.path.split(movies_details[movie_info['key']]['files'][0]['filepath'])
                                    
                                    raw_path = os.path.splitext(movie_filename)[0]
                                    print(raw_path)
                                    if Path(os.path.join(movie_path,raw_path+'-landscape.jpg')).is_file():
                                        raw_thumb_path = raw_path+'-landscape.jpg'
                                    elif Path(os.path.join(movie_path,raw_path+'-clearart.png')).is_file():
                                        raw_thumb_path = raw_path+'-clearart.png'
                                    elif Path(os.path.join(movie_path,raw_path+'-banner.jpg')).is_file():
                                        raw_thumb_path = raw_path+'-banner.jpg'
                                    elif Path(os.path.join(movie_path,raw_path+'-clearlogo.png')).is_file():
                                        raw_thumb_path = raw_path+'-clearlogo.png'
                                    elif Path(os.path.join(movie_path,raw_path+'-discart.jpg')).is_file():
                                        raw_thumb_path = raw_path+'-discart.jpg'
                                    elif Path(os.path.join(movie_path,raw_path+'-keyart.jpg')).is_file():
                                        raw_thumb_path = raw_path+'-keyart.jpg'
                                    elif Path(os.path.join(movie_path,raw_path+'-poster.jpg')).is_file():
                                        raw_thumb_path = raw_path+'-poster.jpg'
                                    elif Path(os.path.join(movie_path,raw_path+'-fanart.jpg')).is_file():
                                        raw_thumb_path = raw_path+'-fanart.jpg'
                                    else:
                                        raw_thumb_path = None
                                        
                                    if raw_thumb_path is not None:
                                        thumb_filename = raw_thumb_path
                                    else:
                                        thumb_filename = '/static/beeprev2.png'
                                    #shutil.copy(os.path.join(movie_path,thumb_filename),'live/')
                                    thumb_path = url_for('serve_movie',filename=os.path.join(movie_path,thumb_filename).lstrip('/')).replace(config['Settings']['Library Mount Point'],'')

                                    print(thumb_path)
                                    print(thumb_filename)
                                except:
                                    thumb_path = '/static/beeprev2.png'
                            elif 'music_video' in schedule_entry['type']:
                                movie_info = schedule_entry['type']['music_video']
                                if 'kevin_bacon_mode' in schedule_entry:
                                    if schedule_entry['kevin_bacon_mode'] is not None:
                                        if not isinstance(schedule_entry['kevin_bacon_mode'], list):
                                            schedule_entry['kevin_bacon_mode'] = [schedule_entry['kevin_bacon_mode']]
                                        for kbm in schedule_entry['kevin_bacon_mode']:
                                            print(kbm)
                                            if kbm is not None:
                                                if kbm['degree'][0] is not None:
                                                    kbm_degree = ', '.join(kbm['degree'])
                                                    if kbm['setting'] == 'certification':
                                                        kbm['setting'] = 'rating'
                                                        kbm_degree = ''
                                                        for kbmd in kbm['degree']:
                                                            kbm_degree += kbmd.split('/')[0].split(':')[-1].strip()+' '
                                                elif kbm['setting'] == 'credits':
                                                    kbm['setting'] = 'writer'
                                                cell_color = 'red'
                                                try:
                                                    kbm_text = f"Linked from {kbm['title']} through the {kbm['setting']} {kbm_degree.strip()}."
                                                except UnboundLocalError:
                                                    kbm_text = ''
                                                    cell_color = 'blue'
                                            else:
                                                cell_color = 'blue'
                                            
                                    else:
                                        cell_color = 'blue'
                                cell_text_info = remove_accents(f"{schedule_title.upper()}")
                                remove_accents(f"{schedule_title.upper()}")
                                title_text = remove_accents(f"{schedule_title.upper()}")
                                details_text = ''
                                thumb_filename = '/static/beeprev2.png'
                                thumb_path = '/static/beeprev2.png'
                                
                            elif 'series' in schedule_entry['type']:
                                series_info = schedule_entry['type']['series']
                                series_title = series_info['show_title']
                                cell_text_info = series_title
                                title_text = series_title
                                details_text = f" {series_info['episode_title']} (S{series_info['season_number']}E{series_info['episode_number']}): "
                                episode_path, episode_filename = os.path.split(series_info['key'])
                                try:
                                    thumb_filename = os.path.splitext(episode_filename)[0]+'-thumb.jpg'
                                    thumb_path = url_for('serve_show',filename=os.path.join(episode_path, thumb_filename).lstrip('/')).replace(config['Settings']['Library Mount Point'],'')
                                except:
                                    thumb_path = '/static/beeprev2.png'
                                if series_info['episode_mode'] == "random":
                                    cell_color = "grey"
                                elif series_info.get('season_number') == "1" and series_info.get('episode_number') == "1":
                                    cell_color = "cyan"

                            try:
                                if '\n' in schedule_entry['summary']:
                                    summary_text = schedule_entry['summary'].replace('\n', ' ')
                                else:
                                    summary_text = schedule_entry['summary']
                            except AttributeError:
                                summary_text = "ERROR GETTING EPISODE SUMMARY"
                            except TypeError:
                                if schedule_entry['summary'] is None:
                                    summary_text = ''
                                else:
                                    summary_text = schedule_entry['summary']
                            details_text += remove_accents(summary_text)
                            
                            if "interstitial" in schedule_entry['type'].keys():
                                cell_text_info = "Commercial Break"
                                break
                            # Construct the cell content
                            cell_text = f''
                            cell_text += cell_text_info
                            #timeofday = "Today at"
                            if 20 < start_time_obj.hour <= 23 or 0 <= start_time_obj.hour <= 4:
                                timeofday = "Tonight at"
                            elif 4 < start_time_obj.hour <= 10:
                                timeofday = "This Morning at"
                            elif 10 < start_time_obj.hour <= 15:
                                timeofday = "Today at"
                            elif 15 < start_time_obj.hour <= 18:
                                timeofday = "Today at"
                            elif 18 < start_time_obj.hour <= 20:
                                timeofday = "Tonight at"
                            
                            channel_title = details.get('channel_name','Broadcast Emulation Television')
                            
                            details_text = remove_accents(details_text.replace("'","").replace('"', '').replace('\\', '').strip())
                            
                            if len(details_text) >= 300:
                                details_text = details_text[:300]+"..."
                            
                            details_text = f"{details_text} {duration_min_actual} mins"
                            
                            if kbm_text:
                                details_text = remove_accents(kbm_text).replace("'","").replace('"', '').strip() +' '+ details_text
                            
                            timedate_text = f'{timeofday} {start_time_obj.strftime("%I:%M %p").lstrip("0")}'
                            channel_number_text = f'{details.get("channel_call_letters","BTV")}-{int(channel_number.split(" ")[0])}'
                            
                            title_text = title_text.replace("'","\\'").replace('"', '\\"')
                            thumb_path = thumb_path.replace("'","\\'").replace('"', '\\"')
                            prevue_args = f"'{html.escape(channel_title)}', '{html.escape(title_text)}', '{html.escape(details_text)}', '{html.escape(timedate_text)}', '{html.escape(channel_number_text)}', '{html.escape(thumb_path)}'"
                            # Show start time in cell if it isn't on the half-hour
                            if start_time_obj != block_start:
                                cell_text += f" ({start_time_obj.strftime('%H:%M')})"
                            
                            # Add the cell to the row
                            cell_html = f'<td oncontextmenu= "clientSelect({ch_num});return false" class="box tall {cell_color}" style="width:{total_width}px;text-align:left" title="{start_time_obj.strftime("%H:%M")}-{end_time_obj.strftime("%H:%M")}&#10;{html.escape(title_text)}&#10;{html.escape(details_text)}" onclick="prevueText({prevue_args})">{cell_text}</td>'

                            # Check to make sure entry hasn't already been saved
                            skip_continue = False
                            for h, html_data in enumerate(schedule_data[ch_num]['html']):
                                if start_time_obj.strftime("%H:%M") in html_data and end_time_obj.strftime("%H:%M") in html_data and title_text in html_data:
                                    #print(h, html_data)
                                    skip_continue = True
                                    break
                            if skip_continue is True:
                                continue
                            # Check if first start time is more than 30 minutes from the start of the first time block
                            if i == 1 and prev_end_time_obj <= blocks[0]['start']:
                                block_html = f"<td class='box blue dim tall'</td>"
                                schedule_data[ch_num]['html'].append(f"<td class='box blue dim tall'></td>")
     
                            schedule_data[ch_num]['html'].append(cell_html)
                            schedule_data[ch_num].update({
                                'cell_color': cell_color,
                                'total_width': total_width,
                                'start_time': start_time_obj.strftime("%H:%M"),
                                'end_time': end_time_obj.strftime("%H:%M"),
                                'title': html.escape(title_text),
                                'details_text': html.escape(details_text),
                                'prevue_args': prevue_args,
                                'cell_text': cell_text
                            })
                            
                            
                            if blocks[i] != blocks[-1]:
                                next_index = j+1
                                next_type = next(iter(schedule_items[next_index][1]['type']))
                                while next_type == "interstitial":
                                    if schedule_items[-1] == schedule_items[next_index]:
                                        break
                                    next_index += 1
                                    next_type = next(iter(schedule_items[next_index][1]['type']))

                                print(f"{next_index-j} ENTRIES SKIPPED")
                                print(next_type)
                                    
                                next_time_start = datetime.datetime.strptime(schedule_items[next_index][0], "%Y-%m-%d %H:%M:%S.%f")
                                if block_end < next_time_start and end_time_obj < block_end:
                                    next_start = blocks[i+1]['start']
                                else:
                                    next_start = next_time_start
                                time_between = (next_start - end_time_obj).seconds
                                minutes_between = time_between // 60
                                print(f"{time_between} SECONDS UNTIL NEXT ENTRY")

                                if time_between > 0 and minutes_between >= 10:
                                    empty_block_width = calculate_cell_width(minutes_between, cell_width, padding, border)
                                    empty_block = f"<td class='box {cell_color} dim tall' style='width:{min(empty_block_width,max_width-total_width_used)}px'></td>"
                                    total_width_used += min(empty_block_width,max_width-total_width_used)
                                    end_time_obj
                                    cell_html += empty_block
                                    schedule_data[ch_num]['html'].append(empty_block)
                                    schedule_data[ch_num]['empty_block_width'] = min(empty_block_width,max_width-total_width_used)
                                    
                                    end_time_obj = end_time_obj + datetime.timedelta(seconds=time_between)
                            
                            block_html += cell_html        
                            covered_time = overlap_end
                            total_width_used += total_width
                            block_filled = True
                            prev_start_time = start_time
                            prev_end_time_obj = end_time_obj
                            '''cells_created += 1
                            if i == 5 and cells_created < i:
                                total_width_used -= (border+padding)*(i-cells_created)'''
                            break
                        elif start_time_obj > block_end:
                            break
                '''if not block_filled and total_width_used < max_width:
                    # Add an empty block if no content and if there is space left
                    block_html = f"<td class='box blue tall' style='width:{min(cell_width,max_width-total_width_used)}px'></td>"
                    total_width_used += min(cell_width,max_width-total_width_used)'''
                
                html_string += block_html
                channel_data[ch_num][start_time] = block_html
                
                
                block_start = block_end

        html_string += '</tr>'
    
    return render_template('show_schedule.html', kiosk_mode=kiosk_mode, html_string=html_string+time_row, time_row=time_row, empty_row=empty_row, channel_data=channel_data, schedule_data=schedule_data, template_files=get_template_files(), live_onload = live_load())

def calculate_cell_width(duration_min_total, cell_width, padding, border):
    # Separate hours from minutes
    duration_hours = duration_min_total // 60
    duration_min_remaining = duration_min_total % 60
    # Rounding rules for remaining minutes
    if duration_min_remaining < 10:
        duration_min_rounded = 0
    elif 10 <= duration_min_remaining <= 19:
        duration_min_rounded = 15
    elif 20 <= duration_min_remaining <= 35:
        duration_min_rounded = 30
    elif 36 <= duration_min_remaining <= 51:
        duration_min_rounded = 45
    elif 52 <= duration_min_remaining <= 60:
        duration_min_rounded = 60
    duration_min_rounded += duration_hours * 60
    # Calculate the width based on rounded duration
    if duration_min_rounded == 0:
        #entry_width = (cell_width / 2) - (padding + border)  # Half block width
        total_blocks = math.ceil(duration_min_rounded / 15) * 15
        entry_width = total_blocks * cell_width + (total_blocks - 1) * (padding + border)
    elif duration_min_rounded <= 15:
        entry_width = (cell_width / 2) - (border)  # Half block width
    elif 15 < duration_min_rounded <= 30:
        entry_width = cell_width  # Full block width
    else:
        # For multi-block content
        total_blocks = (duration_min_rounded / 30) 
        entry_width = total_blocks * cell_width + (total_blocks - 1) * (padding + border)
    #total_blocks = round(duration_min_rounded / 30)/1
    #entry_width = total_blocks * cell_width + (total_blocks - 1) * (padding + border)
    
    return entry_width

'''@app.route('/show_schedule', methods=['GET'])
def show_schedule():
    channels_directories = []
    channels = []
    data = {}
    now = datetime.datetime.now()
    today = now.strftime('%Y-%m-%d')
    tomorrow = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    for item in os.listdir('channels/'):
        item_path = os.path.join('channels/', item)
        if os.path.isdir(item_path):
            channels.append((item, os.path.join(item_path, 'daily_schedule.json')))
    for i, (channel_number, file_path) in enumerate(channels):
        app.logger.debug(f"Channel {channel_number} File Path: {file_path}")  # Add this line for logging
        try:
            data[channel_number] = load_data(file_path)
        except FileNotFoundError:
            app.logger.error(f"File not found: {file_path}")
            abort(404)  # Return a 404 error if the file is not found

    # Render the template with existing data
    return render_template('show_schedule.html', timedelta=timedelta, datetime=datetime.datetime, len=len, round=round, list=list, now=now, days=(today,tomorrow), schedule_data=data, format_minutes=format_minutes,str=str)'''

@app.route('/delete', methods=['POST'])
def delete_template():
    template_file = request.form.get('template_file')

    try:
        template_path = os.path.join('channel_templates', template_file)
        os.remove(template_path)
        #flash(f'Successfully deleted template: {template_file}', 'success')
    except Exception as e:
        #flash(f'Error deleting template: {str(e)}', 'error')
        pass

    return redirect(url_for('select_channel'))

@app.route('/delete/<template_file>', methods=['GET'])
def confirm_delete_template(template_file):
    return render_template('delete_template.html', template_file=template_file, live_onload = live_load())

@app.route('/delete_channel', methods=['POST'])
def delete_channel():
    channel = request.form.get('channel')
    try:
        dir_path = os.path.join('channels', channel)
        for file in os.listdir(dir_path):
            file_path = os.path.join(dir_path, file)
            os.remove(file_path)  # Remove file
        os.rmdir(dir_path)
        flash(f'Successfully deleted Channel {channel}', 'success')
    except Exception as e:
        #flash(f'Error deleting template: {str(e)}', 'error')
        pass

    return redirect(url_for('select_channel'))

@app.route('/delete_channel/<channel>', methods=['GET'])
def confirm_delete_channel(channel):
    return render_template('delete_channel.html', channel=channel, live_onload = live_load())

@app.route('/create', methods=['POST'])
def create():
    
    try:
        shows_data = shows_details
    except FileNotFoundError:
        abort(404)  # Return a 404 error if the file is not found

    try:
        movies_data = movies_details
    except FileNotFoundError:
        abort(404)  # Return a 404 error if the file is not found

    new_file_name = request.form['new_file_name']
    block_names = ['Morning', 'Midday', 'Afternoon', 'PrimeTime', 'LateNight', 'LateLate']
    complexity = request.form.getlist('complexity[]')
    start_times = request.form.getlist('start_times[]')
    end_times = request.form.getlist('end_times[]')
    allowed_genres = request.form.getlist('allowed_genres[]')
    forbidden_genres = request.form.getlist('forbidden_genres[]')
    allowed_ratings = request.form.getlist('allowed_ratings[]')
    forbidden_ratings = request.form.getlist('forbidden_ratings[]')
    options = request.form.getlist('options[]')

    # Initialize an empty dictionary to store block data
    blocks_data = {}

    # Iterate over block names to collect data for each block
    for block_name in block_names:
        block_data = {
            'complexity': request.form.get(f"{block_name}-complexityHidden", ""),
            'start_time': request.form.get(f"{block_name}-start_time", ""),
            'end_time': request.form.get(f"{block_name}-end_time", ""),
            'allowed_genres': request.form.get(f"{block_name}-allowed_genres", ""),
            'forbidden_genres': request.form.get(f"{block_name}-forbidden_genres", ""),
            'allowed_ratings': request.form.get(f"{block_name}-allowed_ratings", ""),
            'forbidden_ratings': request.form.get(f"{block_name}-forbidden_ratings", ""),
            'allowed_decades': request.form.get(f"{block_name}-allowed_decades", ""),
            'forbidden_decades': request.form.get(f"{block_name}-forbidden_decades", ""),
            'options': request.form.get(f"{block_name}-optionsHidden", ""),
        }
        blocks_data[block_name] = block_data

    # Save the modified data back to the file
    save_data(f"channel_templates/{new_file_name}.json", blocks_data)
    return redirect(url_for('edit', template_file=f'{new_file_name}.json'))

if __name__ == '__main__':
    #app.run(host='0.0.0.0',port=5000,debug=True)
    socketio.run(app, host='0.0.0.0', port=int(config['Settings']['Web UI Port']), debug=True, allow_unsafe_werkzeug=True)
