import atexit
import configparser
import ffmpeg
import json
import os
import requests
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timedelta

config = configparser.ConfigParser()
config.read('config.ini')
drones = configparser.ConfigParser()
drones.read('drones.ini')
movies_library_path = config['Content']['Movie JSON']
series_library_path = config['Content']['Show JSON']
with open(movies_library_path, 'r') as movies_library_file:
    movies_library = json.load(movies_library_file)
with open(series_library_path, 'r') as series_library_file:
    series_library = json.load(series_library_file)    

live_file = 'live.json'

# Define the cleanup function
def cleanup():
    drone = sys.argv[2]
    vlc_url = f"http://{drones[drone]['Address']}:{drones[drone]['Port']}"
    password = drones[drone]['Password']
    vlc_command_url = f"{vlc_url}/requests/status.json"
    status_response = requests.get(f"{vlc_url}/requests/status.json?command=pl_stop",auth=('',password))
    
# Define a signal handler for termination signals
def handle_termination(signum, frame):
    print(f"Received termination signal {signum}. Exiting gracefully...")
    cleanup()
    sys.exit(0)

# Register the signal handlers for SIGINT and SIGTERM
signal.signal(signal.SIGINT, handle_termination)
signal.signal(signal.SIGTERM, handle_termination)

# Register the cleanup function to be called on normal exit
atexit.register(cleanup)

def replace_prefix(text, prefix, replacement):
    if text.startswith(prefix):
        return text.replace(prefix, replacement, 1)
    return text

def get_time(offset=0):
    return datetime.now() + timedelta(seconds=offset)

def load_data(data_file):
    with open(data_file, 'r') as file:
        data = json.load(file)
    return data

def read_live_file():
    """Utility function to safely read and parse the JSON file."""
    if not os.path.exists(live_file):
        return {}
    try:
        return load_data(live_file)
    except json.JSONDecodeError:
        return {}

# Function to save data to JSON file
def save_data(file_path, data):
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)# Function to load data from JSON file

def get_schedule_for_day(schedule, date):
    return schedule.get(date, {})

def get_schedule_item(schedule, current_time_dt):
    return_item = (None,None)
    min_time_diff = None

    for start_time, item in schedule.items():
        start_time_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S.%f")
        start_date = start_time_dt.strftime("%Y-%m-%d")
        end_time = item.get('end_time')
        end_time_dt = datetime.strptime(f"{start_date} {end_time}", "%Y-%m-%d %H:%M:%S.%f")
        
        if end_time_dt < start_time_dt:
            end_time_dt += timedelta(days=1)
        
        if start_time_dt <= current_time_dt < end_time_dt:
            return_item = (start_time, item)
            break
        elif start_time_dt > current_time_dt:
            time_diff = (start_time_dt - current_time_dt).total_seconds()
            if min_time_diff is None or time_diff < min_time_diff:
                min_time_diff = time_diff
                return_item = (start_time, item)
                break

    return return_item

def normalize_path(file_path):
    return file_path.replace('\\', '/')

def run_ffmpeg_copy(rtsp_url, file_info):
    try:
        input_args = {
            'ss': file_info['start_offset'],
            're': None  # Read input at native frame rate
        }
        output_args = {
            'c:v': 'copy',
            'c:a': 'copy',
            'f': 'rtsp',
            'rtsp_transport': 'tcp',
            'timeout': '2000',  # Increase timeout
            'fflags': 'nobuffer',
            'flags': '+global_header',
            'movflags': 'faststart',
            'rtbufsize': '100M',  # Increase buffer size
            't': file_info['duration']
        }

        cmd = [
            'ffmpeg',
            '-re',
            '-ss', str(file_info['start_offset']),
            '-i', f"{file_info['path']}",
            '-c:v', output_args['c:v'],
            '-c:a', output_args['c:a'],
            '-f', output_args['f'],
            '-rtsp_transport', output_args['rtsp_transport'],
            '-timeout', output_args['timeout'],
            '-fflags', output_args['fflags'],
            '-flags', output_args['flags'],
            '-movflags', output_args['movflags'],
            '-rtbufsize', output_args['rtbufsize'],
            '-t', str(file_info['duration']),
            '-map', '0:a:5',
            rtsp_url
        ]

        #print("Running FFmpeg command:", ' '.join(cmd))
        print("FFMPEG RUNNING...")
        process = subprocess.Popen(cmd)
        return process
    except Exception as e:
        print("Error during FFmpeg execution:", e)
        return None

def get_stream_indexes(file_path, language_tag):
    try:
        # Run ffprobe to get detailed stream information with language tags
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'stream=index,codec_type:stream_tags=language', '-of', 'json', file_path],
            capture_output=True, text=True, check=True
        )
        
        streams_info = result.stdout
        video_index = '0'  # Default to 0
        audio_index = '0'  # Default to 0
        
        import json
        data = json.loads(streams_info)
        
        for stream in data['streams']:
            index = stream['index']
            codec_type = stream['codec_type']
            language = stream.get('tags', {}).get('language', None)
            
            if language == language_tag:
                if codec_type == 'video':
                    video_index = language
                elif codec_type == 'audio':
                    audio_index = language
        
        return video_index, audio_index

    except subprocess.CalledProcessError as e:
        print(f"Error running ffprobe: {e}")
        return '0', '0'  # Default to 0 if there's an error

def run_ffmpeg_rtsp(rtsp_url, file_info):
    # Retrieve language tag from config
    language_tag = config['Settings']['Language']
    
    # Get stream indexes
    video_index, audio_index = get_stream_indexes(file_info['path'], language_tag)
    
    try:
        # Update encoding and streaming parameters
        output_args = {
            #'vf': 'scale=w=1920:h=1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
            'c:v': 'libx264',
            'preset': 'ultrafast',  # Faster preset to improve speed
            'profile:v': 'main',   # Standard high profile
            'level:v': '4.2',
            'b:v': '3M',
            'maxrate': '2M',
            'bufsize': '250M',       # Reduce buffer size for speed
            'c:a': 'aac',
            'strict': 'experimental',
            'ar': '48000',
            'b:a': '192k',
            'ac': '2',
            'f': 'rtsp',
            'rtsp_transport': 'tcp',
            'movflags': 'faststart',
            'rtbufsize': '250M',   # buffer size
            't': file_info['duration']
        }
        
        if audio_index != '0':
            audio_map = f'0:a:m:language:{audio_index}'
        else:
            audio_map = "0:a:0"
            
        if video_index != '0':
            video_map = f'0:v:m:language:{video_index}'
        else:
            video_map = "0:v:0"
            
        cmd = [
            'ffmpeg',
            '-re',
            '-ss', str(file_info['start_offset']),
            '-i', f"{file_info['path']}",
            #'-vf', output_args['vf'],
            #'-vsync', 'vfr',
            '-async', '1500',
            '-c:v', output_args['c:v'],
            '-preset', output_args['preset'],
            '-profile:v', output_args['profile:v'],
            '-level:v', output_args['level:v'],
            '-b:v', output_args['b:v'],
            '-maxrate', output_args['maxrate'],
            '-bufsize', output_args['bufsize'],
            '-g', '50',
            '-keyint_min', '50',
            '-c:a', output_args['c:a'],
            '-strict', output_args['strict'],
            '-ar', output_args['ar'],
            '-b:a', output_args['b:a'],
            '-ac', output_args['ac'],
            '-f', output_args['f'],
            '-rtsp_transport', output_args['rtsp_transport'],
            '-movflags', output_args['movflags'],
            #'-rtbufsize', output_args['rtbufsize'],
            '-loglevel', 'info',
            #'-progress', '-',
            '-t', str(file_info['duration']),
            '-map', audio_map,
            '-map', video_map,
            rtsp_url
        ]

        print("Now Streaming", file_info['current_item']['title'],end='\r')
        global process
        process = subprocess.Popen(cmd)
        
        return process
    except Exception as e:
        print("Error during FFmpeg execution:", e)
        return None

def run_ffmpeg(rtmp_url, file_info):
    # Retrieve language tag from config
    language_tag = config['Settings']['Language']
    
    # Get stream indexes (FIX WHAT HAPPENS IF TWO ARE GIVEN)
    video_index, audio_index = get_stream_indexes(file_info['path'], language_tag)
    
    try:
        # Update encoding and streaming parameters
        output_args = {
            'c:v': 'libx264',
            'preset': 'ultrafast',  # Faster preset to improve speed
            'profile:v': 'main',   # Standard high profile
            'level:v': '4.2',
            'b:v': '3M',
            'maxrate': '2M',
            'bufsize': '62500k',       # Reduce buffer size for speed
            'c:a': 'aac',
            'strict': 'experimental',
            'ar': '48000',
            'b:a': '192k',
            'ac': '2',
            'f': 'flv',             # FLV is required for RTMP streaming
            'movflags': 'faststart',
            'rtbufsize': '250M',   # Buffer size
            't': file_info['duration']
        }
        
        if audio_index != '0':
            audio_map = f'0:a:m:language:{audio_index}'
        else:
            audio_map = "0:a:0"
            
        if video_index != '0':
            video_map = f'0:v:m:language:{video_index}'
        else:
            video_map = "0:v:0"
        print(f"Video Map: {video_map}, Audio Map: {audio_map}")

        cmd = [
            'ffmpeg',
            '-re',
            '-ss', str(file_info['start_offset']),
            '-i', f"{file_info['path']}",
            '-c:v', output_args['c:v'],
            '-preset', output_args['preset'],
            '-profile:v', output_args['profile:v'],
            '-level:v', output_args['level:v'],
            '-maxrate', output_args['maxrate'],
            '-bufsize', output_args['bufsize'],
            '-g', '50',
            '-keyint_min', '50',
            '-c:a', output_args['c:a'],
            '-strict', output_args['strict'],
            '-ar', output_args['ar'],
            '-b:a', output_args['b:a'],
            '-ac', output_args['ac'],
            '-f', output_args['f'],
            '-movflags', output_args['movflags'],
            '-loglevel', 'warning',
            '-t', str(file_info['duration']),
            '-map', audio_map,
            '-map', video_map,
            rtmp_url
        ]

        print("Now Streaming", file_info['current_item']['title'], end='\r')
        global process
        process = subprocess.Popen(cmd)
        
        return process
    except Exception as e:
        print("Error during FFmpeg execution:", e)
        return None


def cleanup_ffmpeg():
    global process
    if process:
        print("Terminating FFmpeg process...")
        process.kill()
        process.wait()

#atexit.register(cleanup_ffmpeg)     

def run_vlc_playback(file_info,drone):
    """
    Function to control remote VLC instance for media playback.
    Args:
    - file_info: Dictionary containing file path and playback information.
    """
    
    vlc_url = f"http://{drones[drone]['Address']}:{drones[drone]['Port']}"
    password = drones[drone]['Password']
    vlc_command_url = f"{vlc_url}/requests/status.json"
    status_response = requests.get(f"{vlc_url}/requests/status.json?",auth=('',password))
    #status_dict = json.loads(status_response)
    # Prepare the media URL (file path or stream URL)
    media_url = urllib.parse.quote(file_info['path'])
    start_offset = int(file_info['start_offset'])
    try:
        # Load the media file in VLC
        #status_response = requests.get(vlc_stop_url, auth=('', password))
        state = status_response.json().get("state","")
        print(f"VLC State: {state}")
        if "playing" in state:
            # enqueue file to playlist
            #current_plid = status_dict.get('currentplid')

            load_command = f"{vlc_url}/requests/status.json?command=in_enqueue&input={media_url}"
            response = requests.get(load_command, auth=('', password))
            print("File Loading ",end='',flush=True)
            while os.path.basename(file_info['path']) not in response.text and '"state":"playing"' in response.text:
                response = requests.get(f"{vlc_url}/requests/status.json?",auth=('',password))
                print('-',end='',flush=True)
                
                time.sleep(1)
            print('',end='\n',flush=True)
            print(f"VLC State: {response.json().get('state','')}")
            #next_command = f"{vlc_url}/requests/status.json?command=pl_next"
            print(f"Playing {file_info['current_item']['title']} on {drone} player")
            load_command = f"{vlc_url}/requests/status.json?command=in_play&input={media_url}"
            response = requests.get(load_command, auth=('', password))
        elif "paused" in state:
            # enqueue file to playlist
            #current_plid = status_dict.get('currentplid')
            load_command = f"{vlc_url}/requests/status.json?command=in_enqueue&input={media_url}"
            time.sleep(0.05)
            next_command = f"{vlc_url}/requests/status.json?command=pl_next"
            print(f"Playing {file_info['current_item']['title']} on {drone} player")
            play_command = f"{vlc_url}/requests/status.json?command=in_play&input={media_url}"
            response = requests.get(play_command, auth=('', password))
        elif "stopped" in state:
            print("Playing File...")
            clear_response = requests.get(f"{vlc_command_url}?command=pl_empty",auth=('',password))
            time.sleep(0.01)
            load_command = f"{vlc_url}/requests/status.json?command=in_play&input={media_url}"
            response = requests.get(load_command, auth=('', password))
            
            if response.status_code == 200:
                print(f"Playing {file_info['current_item']['title']} on {drone} player")
            else:
                print(f"Error: Unable to play media on {Den}. Status code: {response.status_code}")
                return
        else:
            print(f"Unknown VLC state: [{state}], trying to play anyway.")
            load_command = f"{vlc_url}/requests/status.json?command=in_play&input={media_url}"
            response = requests.get(load_command, auth=('', password))

        # Wait until media is fully loaded before seeking
        media_loaded = False
        while media_loaded is False:  # Retry checking for media load status
            status_response = requests.get(vlc_command_url, auth=('', password))
            if os.path.basename(file_info['path']) in status_response.text and '"state":"playing"' in status_response.text:
                media_loaded = True
                break
            
            time.sleep(0.5)  # Wait a moment before checking again
            #start_offset += 1

        if media_loaded is True:
            # Send fullscreen command (once, not repeatedly)
            #fullscreen_command = f"{vlc_url}/requests/status.json?command=fullscreen"
            #requests.get(fullscreen_command, auth=('', password))

            # Send seek command to offset the video playback
            if start_offset > 2:
                seek_command = f"{vlc_url}/requests/status.json?command=seek&val={start_offset}"
                requests.get(seek_command, auth=('', password))
                print(f"Video set to start at {start_offset} seconds.")
        else:
            print("Error: Media did not start playing within the expected time.")

    except Exception as e:
        print(f"Error controlling VLC playback: {e}")

def stream_video(url, file_info, start_time, process_ref):
    try:
        # Calculate the delay until the scheduled start time
        delay = (start_time - get_time()).total_seconds()
        
        if delay > 0:
            print(f"Delay: {delay} seconds")
            time.sleep(delay)
        '''if process_ref[0]:
            process_ref[0].terminate()'''  # Terminate the previous FFmpeg process
        #process = run_ffmpeg(url, file_info)
        process = run_vlc_playback(file_info,sys.argv[2])
        if process:
            process_ref[0] = process  # Update the reference to the process object
            #process.wait()  # Wait for the process to terminate
            return process
    except Exception as e:
        print(f"Error during streaming: {e}")
        return None

def main():
    print("Starting beehive.py...", flush=True)
    print(f"Channel {sys.argv[1]}", flush=True)
    print(f"Drone: {sys.argv[2]}", flush=True)
    if len(sys.argv) < 3:
        print("Usage: python script.py <channel> <client>", flush=True)
        sys.exit(1)
    channel_dir = os.path.join('channels',f"{int(sys.argv[1]):03}")
    schedule_file = os.path.join(channel_dir, 'active_schedule.json')
    current_item = None
    schedule = load_data(schedule_file)
    url = ''
    
    preload_seconds = 2  # Preload the next video stream early
    process_ref = [None]
    
    vlc_url = f"http://{drones[sys.argv[2]]['Address']}:{drones[sys.argv[2]]['Port']}"
    password = drones[sys.argv[2]]['Password']
    vlc_command_url = f"{vlc_url}/requests/status.json"
    stop_response = requests.get(f"{vlc_url}/requests/status.json?command=pl_stop",auth=('',password))
    server_prefix = config['Settings']['Library Mount Point']
    client_prefix = drones[sys.argv[2]]['Library Mount Point']
    
    while True:
        datetime_now = get_time()
        current_time = datetime_now.strftime("%H:%M:%S.%f")
        current_date = datetime_now.strftime("%Y-%m-%d")
        print(f"[{current_time}] -------------------", flush=True)

        start_time, current_item = get_schedule_item(schedule, datetime_now)

        if current_item is not None:
            print(f"Next: {current_item.get('title')}", flush=True)
            end_time = current_item.get('end_time')
            
            start_time_dt = datetime.strptime(f"{start_time}", "%Y-%m-%d %H:%M:%S.%f")
            end_time_dt = start_time_dt + timedelta(seconds=current_item.get('duration_s'))
            
            content_type = list(current_item['type'].keys())[0]
            if content_type != 'movie':
                content_path = os.path.normpath(current_item['type'][content_type]['key'])
            else:
                content_path = os.path.normpath(movies_library[current_item['type'][content_type]['key']]['files'][0]['filepath'])

            content_path = replace_prefix(content_path, server_prefix, client_prefix)

            time_diff = (get_time() - start_time_dt).total_seconds()
            offset = max(0, time_diff)
            preempt_seconds = current_item.get('is_preempted',0)
            try:
                offset += float(preempt_seconds)
            except:
                pass
            '''if isinstance(preempt_seconds, (int,float)):
                offset += preempt_seconds'''
            duration = (end_time_dt - get_time()).total_seconds()  # Adjust duration based on the current time
            file_info = {
                'path': normalize_path(content_path),
                'start_offset': offset,
                'duration': duration,  # Use the corrected duration
                'current_item': current_item
            }

            print(f"Start time: {start_time_dt}, End time: {end_time_dt}, \nOffset: {offset}s, Duration: {duration}s", flush=True)

            # Calculate the actual start time, considering the preload time
            actual_start_time = start_time_dt - timedelta(seconds=preload_seconds)
            #print(f"Actual start time: {actual_start_time}")

            process = stream_video(url, file_info, actual_start_time, process_ref)

            # SAVE NOW PLAYING DATA TO FILE
            live_json = read_live_file()
            if not live_json or live_json == {}:
                live_json = {sys.argv[2]:{}}
            else:
                live_json[sys.argv[2]] = {}
            live_json[sys.argv[2]]['pid'] = os.getpid()
            live_json[sys.argv[2]]['channel'] = sys.argv[1]
            content_key = current_item['type'][content_type].get('key')
            if content_type == "movie":
                content_details = movies_library[content_key]
                live_json[sys.argv[2]]['title'] = f"{current_item['type'][content_type].get('title')} ({current_item['type'][content_type].get('year')})"
                live_json[sys.argv[2]]['plot'] = content_details.get('plot')
                live_json[sys.argv[2]]['tagline'] = content_details.get('tagline')
                live_json[sys.argv[2]]['rated'] = content_details.get('certification')
            elif content_type == "series":
                show_key = current_item['type'][content_type].get('show_key')
                content_details = series_library[show_key]
                episode_details = content_details['files'].get(content_key)
                live_json[sys.argv[2]]['title'] = current_item['type'][content_type].get('show_title')
                live_json[sys.argv[2]]['rated'] = content_details.get('certification')
                live_json[sys.argv[2]]['plot'] = episode_details['episode_details'][0].get('plot')
            else:
                live_json[sys.argv[2]]['title'] = current_item.get('title')
            
            live_json[sys.argv[2]]['category'] = content_type
            live_json[sys.argv[2]]['details'] = current_item['type'].get(content_type)
            save_data(live_file,live_json)
            # FINISH SAVING DATA TO FILE
            


            time.sleep(0.25)
            
            # Wait until the next video should start before proceeding to the next item
            time_to_next_start = (end_time_dt - get_time()).total_seconds()
            if time_to_next_start > 0:
                time.sleep(time_to_next_start)  # Add a small buffer to ensure smooth transitions

            # Update datetime_now to the end of the current item
            #datetime_now = end_time_dt + timedelta(microseconds=1)
            #process_ref[0].terminate() 
            '''try:
                process.terminate()
                process.wait()
            except:
                pass'''
            
        else:
            print("No more scheduled items found. Checking again shortly...", flush=True)
            time.sleep(1)  # Wait for 1 seconds before checking the schedule again

if __name__ == "__main__":
    main()
