import base64
import configparser
import datetime
import ffmpeg #install ffmpeg-python with pip
import json
import moviepy.editor as mp
import musicbrainzngs #install with pip
import openai
import cv2 #install with pip
import os
import re
import requests
import time
import traceback
import xml.etree.ElementTree as ET
import yt_dlp as youtube_dl #install yt-dlp with pip
from moviepy.editor import AudioFileClip
from openai import RateLimitError, BadRequestError, InternalServerError, APITimeoutError
from xml.dom import minidom

video_file_extensions = {
    '.mp4', '.mkv', '.avi', '.mov', '.flv',
    '.wmv', '.webm', '.m4v', '.3gp', '.mpeg',
    '.mpg', '.ogv', '.mts', '.m2ts', '.rm', '.rmvb'
}

config = configparser.ConfigParser()
config.read('config.ini')



def save_usage_data(date, data):
    with open('openai_usage.json', 'r+') as file:
        usage_data = json.load(file)
        usage_data[date] = data
        file.seek(0)
        json.dump(usage_data, file, indent=4)

def load_last_saved_date():
    if not os.path.exists('openai_usage.json'):
        with open('openai_usage.json', 'w') as file:
            json.dump({}, file)  # Write an empty dictionary to the file
        return None

    with open('openai_usage.json', 'r') as file:
        usage_data = json.load(file)
        return max(usage_data.keys()) if usage_data else None

def get_openai_usage_data(api_key, date=None):
    """
    Retrieves usage data for an OpenAI API key for a specific date.

    Parameters:
    - api_key (str): The OpenAI API key.
    - date (str, optional): Date in ISO format (YYYY-MM-DD) to retrieve usage data for.

    Returns:
    - dict: Usage data for the specified date.
    """

    # Set default date to today's date if not provided
    if date is None:
        date = datetime.datetime.utcnow().strftime('%Y-%m-%d')

    # API endpoint and headers
    url = 'https://api.openai.com/v1/usage'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    # Parameters for the request
    params = {
        'date': date
    }

    # Make the request to OpenAI API
    response = requests.get(url, headers=headers, params=params)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the JSON response and return the usage data
        usage_data = response.json()
        return usage_data
    else:
        # If the request failed, raise an exception with the error message
        response.raise_for_status()
        
def aggregate_openai_usage_data(data):
    # Initialize variables to hold aggregated data
    aggregated_data = {
        "data": {
            "n_requests": 0,
            "n_context_tokens_total": 0,
            "n_generated_tokens_total": 0
        },
        "whisper_api_data": {
            "num_seconds": 0,
            "num_requests": 0
        }
    }

    # Aggregate data for the "data" key
    if "data" in data:
        for entry in data["data"]:
            aggregated_data["data"]["n_requests"] += entry.get("n_requests", 0)
            aggregated_data["data"]["n_context_tokens_total"] += entry.get("n_context_tokens_total", 0)
            aggregated_data["data"]["n_generated_tokens_total"] += entry.get("n_generated_tokens_total", 0)

    # Aggregate data for the "whisper_api_data" key
    if "whisper_api_data" in data:
        for entry in data["whisper_api_data"]:
            aggregated_data["whisper_api_data"]["num_seconds"] += entry.get("num_seconds", 0)
            aggregated_data["whisper_api_data"]["num_requests"] += entry.get("num_requests", 0)

    # Return the aggregated data
    return aggregated_data

def update_usage_data(api_key, start_date=None, end_date=None, max_days=30):
    # Initialize aggregated data for the whole month
    total_aggregated_data = {
        "data": {
            "n_requests": 0,
            "n_context_tokens_total": 0,
            "n_generated_tokens_total": 0
        },
        "whisper_api_data": {
            "num_seconds": 0,
            "num_requests": 0
        }
    }

    # Load last saved date
    last_saved_date = load_last_saved_date()
    if last_saved_date:
        last_saved_date = datetime.datetime.strptime(last_saved_date, '%Y-%m-%d').date()

    # Calculate the date range for the range
    if not end_date:
        end_date = datetime.datetime.utcnow().date()
    if not start_date:
        start_date = last_saved_date if last_saved_date else end_date - datetime.timedelta(days=max_days-1)

    # Include the last saved date in the range
    if last_saved_date:
        start_date = min(start_date, last_saved_date)

    # Iterate over each day of the past number of days
    for i in range((end_date - start_date).days + 1):
        # Calculate the date for the current iteration
        current_date = (start_date + datetime.timedelta(days=i)).strftime('%Y-%m-%d')

        # Divide the delay into smaller intervals
        for _ in range(15):
            remaining_time = 15 - _
            if remaining_time > 0 and i != 0:
                print(f"{remaining_time}...", end="\r")
                time.sleep(1)

        try:
            # Get the usage data for the current date
            usage_data = get_openai_usage_data(api_key, date=current_date)

            # Aggregate the usage data
            daily_aggregated_data = aggregate_openai_usage_data(usage_data)

            # Add the daily aggregated data to the total aggregated data
            total_aggregated_data["data"]["n_requests"] += daily_aggregated_data["data"]["n_requests"]
            total_aggregated_data["data"]["n_context_tokens_total"] += daily_aggregated_data["data"]["n_context_tokens_total"]
            total_aggregated_data["data"]["n_generated_tokens_total"] += daily_aggregated_data["data"]["n_generated_tokens_total"]
            total_aggregated_data["whisper_api_data"]["num_seconds"] += daily_aggregated_data["whisper_api_data"]["num_seconds"]
            total_aggregated_data["whisper_api_data"]["num_requests"] += daily_aggregated_data["whisper_api_data"]["num_requests"]

            # Save the daily usage data
            save_usage_data(current_date, daily_aggregated_data)

            # Print progress
            print(f"Processed date: {current_date} ({i+1}/{(end_date - start_date).days + 1})")
        except Exception as e:
            print(f"ERROR: {e}")
            continue

    return total_aggregated_data

def calculate_costs_from_file(file_path, config, num_days=30):
    # Load the usage data from the file
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist.")
        return

    with open(file_path, 'r') as file:
        usage_data = json.load(file)

    # Calculate costs
    total_requests = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_whisper_requests = 0
    total_whisper_duration = 0

    for date, daily_data in usage_data.items():
        # Check if the date is within the specified number of days
        date_obj = datetime.datetime.strptime(date, '%Y-%m-%d').date()
        if (datetime.datetime.utcnow().date() - date_obj).days <= num_days:
            total_requests += daily_data["data"]["n_requests"]
            total_input_tokens += daily_data["data"]["n_context_tokens_total"]
            total_output_tokens += daily_data["data"]["n_generated_tokens_total"]
            total_whisper_requests += daily_data["whisper_api_data"]["num_requests"]
            total_whisper_duration += daily_data["whisper_api_data"]["num_seconds"]

    # Calculate costs
    input_cost = total_input_tokens * float(config["OpenAI Settings"]["ChatGPT Input Cost"])
    output_cost = total_output_tokens * float(config["OpenAI Settings"]["ChatGPT Output Cost"])
    whisper_cost = total_whisper_duration * float(config["OpenAI Settings"]["Whisper Cost"])

    # Format whisper duration
    whisper_duration_formatted = str(datetime.timedelta(seconds=total_whisper_duration))

    # Print the results
    print(f"ChatGPT Requests: {total_requests}")
    print(f"ChatGPT Input Tokens: {total_input_tokens}")
    print(f"ChatGPT Output Tokens: {total_output_tokens}")
    print(f"ChatGPT Cost: ${input_cost + output_cost:.2f}")

    print(f"\nWhisper Requests: {total_whisper_requests}")
    print(f"Whisper Requests Duration: {whisper_duration_formatted}")
    print(f"Whisper Cost: ${whisper_cost:.2f}")

    print(f"\nTotal Cost: ${input_cost + output_cost + whisper_cost:.2f}")

def find_files_without_nfo(directory):
    """
    Find video files in the specified directory and its subdirectories
    that do not have matching NFO files.

    Args:
        directory (str): The root directory to start the search.

    Returns:
        list: A list of video files without matching NFO files.
    """
    # List to hold video files without NFO files
    video_files_without_nfo = []

    # Walk through the directory and its subdirectories
    for root, dirs, files in os.walk(directory):
        # Use a set to store file base names (without extensions)
        file_bases = set()

        # Dictionary to store files with their extensions
        files_with_extensions = {}

        # Iterate through each file in the current directory
        for filename in files:
            # Get the file base name and extension
            file_base, file_ext = os.path.splitext(filename)
            
            # Add the base name to the set of file bases
            file_bases.add(file_base)

            # Store the file with its extension in the dictionary
            files_with_extensions[(file_base, file_ext)] = filename

        # Iterate through the video files in the current directory
        string_length = 0
        for (file_base, file_ext) in files_with_extensions.keys():
            # Check if the file is a video file
            if file_ext in video_file_extensions:
                # Check if there is no matching NFO file
                if (file_base, '.nfo') not in files_with_extensions:
                    # Get the full path of the video file
                    video_file_path = os.path.join(root, files_with_extensions[(file_base, file_ext)])
                    # Add the video file path to the list
                    print(video_file_path.ljust(string_length), end='\r')
                    string_length = len(video_file_path)+5
                    video_files_without_nfo.append(video_file_path)
    print()

    return video_files_without_nfo

def get_video_metadata(file_path: str) -> dict:
    """
    Retrieves metadata from a video file using ffmpeg-python.

    Args:
        file_path (str): The file path of the video file.

    Returns:
        dict: A dictionary containing metadata about the video file.
    """
    try:
        # Use ffmpeg-python's probe function to retrieve metadata
        metadata = ffmpeg.probe(file_path)
        
        # Parse and return the desired metadata as a dictionary
        video_metadata = {
            'format': metadata.get('format', {}),
            'streams': metadata.get('streams', [])
        }
        #print(json.dumps(metadata,indent=4))
        '''print(video_metadata['streams'][0]['codec_name'])
        print(f"{video_metadata['streams'][0]['width']}x{video_metadata['streams'][0]['height']}")
        print(f"DURATION: {video_metadata['streams'][0]['duration']} seconds")
        print(f"{video_metadata['format']['format_name']}")'''
        #print(json.dumps(video_metadata,indent=4))
        return video_metadata
    
    except Exception as e:
        print(f"Error retrieving metadata from {file_path}: {e}")
        return {}

def extract_youtube_id_from_filename(file_path: str) -> tuple:
    """
    Extracts a YouTube video ID from the given filename.

    Args:
        filename (str): The filename to check for a YouTube ID.

    Returns:
        str: The extracted YouTube video ID, or None if no ID is found.
    """
    filename, extension = os.path.splitext(file_path)
    filename = os.path.basename(filename)

    # Define the pattern for a valid YouTube ID at the end of the filename
    youtube_id_pattern = re.compile(r'[_-](?:\[([a-zA-Z0-9_-]{11})\]|([a-zA-Z0-9_-]{11}))$')

    # Search the filename for a YouTube video ID
    match = youtube_id_pattern.search(filename)
    
    if match:
        # Get the YouTube ID match
        youtube_id = match.group(1) or match.group(2)
        
        # Check the remaining filename part before the YouTube ID for the excluded patterns
        remaining_filename = filename[:match.start()].strip()
        
        # Check for a hyphen followed by 4 digits in the remaining filename
        year_pattern = re.compile(r'[-_]\d{4}s?[_-]?\d?$')
        
        if not year_pattern.search(youtube_id):
            # Return the matched YouTube video ID and the remaining filename
            #print(youtube_id, remaining_filename)
            return youtube_id, remaining_filename
        
    return None, filename  # If no valid YouTube ID is found, return None and the original filename


def fetch_youtube_metadata(youtube_id: str) -> dict:
    """
    Fetches metadata from a YouTube video using yt-dlp.

    Args:
        youtube_id (str): The YouTube video ID.

    Returns:
        dict: A dictionary containing metadata about the YouTube video.
    """
    # Define YouTube video URL
    video_url = f"https://www.youtube.com/watch?v={youtube_id}"
    
    # yt-dlp options to extract metadata only
    ydl_opts = {
        'quiet': True,  # Suppress yt-dlp output
        'no_warnings': True,
        'ignoreerrors': True,
        'dump_single_json': True,
        'no_download': True
    }
    
    try:
        # Use yt-dlp to extract metadata as JSON
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            print()
            if info:
                return_data = {}
                return_data['id'] = info['id']
                return_data['title'] = info['title']
                return_data['webpage_url'] = info['webpage_url']
                return_data['description'] = info['description']
                return_data['tags'] = info['tags']
                return_data['uploader'] = info['uploader']
                return_data['uploader_url'] = info['uploader_url']
                return_data['upload_date'] = info['upload_date']
                return_data['release_year'] = info['release_year']
                #print(json.dumps(return_data,indent=4))
            
        return return_data if info else {}
    
    except Exception as e:
        print(f"Error fetching YouTube metadata for ID {youtube_id}:\n{e}")
        return {}

def extract_artist_title_from_filename(filename: str) -> tuple:
    """Extracts the artist and title from a filename."""
    # Remove the file extension
    base_filename = os.path.splitext(filename)[0]

    # Replace underscores with spaces
    base_filename = base_filename.replace('_', ' ')

    # Split the filename based on the hyphen
    parts = base_filename.split(' - ')
    
    # If a hyphen is present and divides the artist and title
    if len(parts) == 2:
        artist, title = parts
    elif len(parts) > 2:
        artist = parts[0]
        title = parts[1]
    else:
        # If no hyphen is found, assume the entire filename as artist/title
        artist, title = base_filename, base_filename

    # Trim any leading/trailing whitespace from artist and title
    artist = artist.strip()
    title = title.strip()

    return artist, title

def fetch_musicbrainz_metadata(artist: str, title: str, exact_artist=True) -> dict:
    """
    Fetches music metadata from MusicBrainz using the given artist and title.

    Args:
        artist (str): The artist name.
        title (str): The title of the track.

    Returns:
        dict: A dictionary containing metadata about the music, such as artist, title, release date, album, and genres.
    """
    # Define the user agent string to identify your application (use your own application name and version here)
    musicbrainzngs.set_useragent("Broadcast Emulation Automation System Music Video Scanner", "1.0")
    
    title = re.sub(r'\s*[\(\[].*?[\)\]]\s*','',title)
    
    if '(' in title and ')' in title:
        title = title.split('(')[0].strip()
    if artist != title:
        print(f"{artist} - {title}")
        # Perform a search for recordings matching the given artist and title
        results = musicbrainzngs.search_recordings(artist=artist.strip(), recording=f'"{title.strip()}"', artistname=exact_artist)
        #time.sleep(int(config['RateLimiter']['Musicbrainz']))
    else:
        print(f"{title}")
        # Perform a search for recordings matching the given artist and title
        results = musicbrainzngs.search_recordings(recording=f'"{title.strip()}"')
    time.sleep(int(config['RateLimiter']['Musicbrainz']))

    # Create a dictionary to store the metadata
    metadata = {
        "artist": None,
        "title": title,
        "release_date": None,
        "year": None,
        "genres": []
    }
    if artist != title:
        metadata['artist'] = artist
    earliest_recording = None
    earliest_date = None
    release_group_id = None
    genres_list = []
    # Iterate through each recording in the results
    for recording in results.get("recording-list", []):
        recording_title = re.sub(r'[^a-zA-Z0-9 ]', '',recording['title'].lower())
        given_title = re.sub(r'[^a-zA-Z0-9 ]', '',title.lower())
        artist_credit = recording.get('artist-credit')
        artist_list = []
        #print(json.dumps(artist_credit,indent=4))
        for artist_entry in artist_credit:
            #print(json.dumps(artist_entry,indent=4))
            if isinstance(artist_entry, dict):
                artist_list.append(artist_entry.get('name'))
        if artist == title:
            for artist_name in artist_list:
                if artist_name in title:
                    metadata['artist'] = artist_name
                else:
                    metadata['artist'] = artist_list[0]
        else:
            if artist.lower() in artist_list:
                pass
            else:
                for artist_name in artist_list:
                    artist_name = re.sub(r'[^a-zA-Z0-9 ]', '',artist_name.lower())
                    artist_compare = re.sub(r'[^a-zA-Z0-9 ]', '',artist.lower())
                    if artist_name in artist_compare or artist_compare in artist_name:
                        pass
                    else:
                        #print(f"ARTIST MATCH NOT FOUND: {artist_name}")
                        continue
        if recording_title in given_title or given_title in recording_title:
            # Fetch genres/tags if available
            if "tag-list" in recording:
                genres_list = [tag["name"] for tag in recording["tag-list"]]
                for genre in genres_list:
                    if genre not in metadata["genres"]:
                        metadata["genres"].append(genre)
            # Check the release-list under the recording
            for release in recording.get("release-list", []):
                #print(json.dumps(release,indent=4))
                # Parse the date of the release
                release_date = release.get("date")
                
                # Check the Artist of the Release
                release_artist_credit = recording.get('artist-credit')
                release_artist_list = []
                for release_artist_entry in release_artist_credit:
                    try:
                        release_artist_list.append(re.sub(r'[^a-zA-Z0-9 ]', '',release_artist_entry.get('name')).lower())
                    except AttributeError:
                        pass
                artist_metadata_entry = re.sub(r'[^a-zA-Z0-9 ]', '',metadata['artist'].lower())
                
                if release_date:
                    if (artist_metadata_entry in release_artist_list) or (artist_metadata_entry not in release_artist_list and any(release_artist in artist_metadata_entry for release_artist in release_artist_list)):
                        #print(release_date)

                        # Convert the date string to a datetime object for comparison
                         
                        if "-" in release_date:
                            try:
                                release_date_obj = datetime.datetime.strptime(release_date, "%Y-%m-%d")
                            except ValueError:
                                release_date_obj = datetime.datetime.strptime(release_date, "%Y-%m")
                        else:
                            release_date_obj = datetime.datetime.strptime(release_date, "%Y")
                        #print(release_date_obj)
                        # Check if this release date is earlier than the current earliest date

                        if earliest_date is None or release_date_obj < earliest_date:
                            
                            earliest_date = release_date_obj
                            earliest_recording = recording
                            
                            metadata["title"] = earliest_recording["title"].replace("’","'")
                            earliest_year_str = earliest_date.strftime('%Y')
                            if earliest_date.strftime('%m-%d') == "01-01":
                                earliest_date_str = earliest_date.strftime('%Y')
                            else:
                                earliest_date_str = earliest_date.strftime('%Y-%m-%d')
                            metadata['release_date'] = earliest_date_str
                            metadata['year'] = earliest_year_str
                        #print(f"EARLIEST DATE: {earliest_date}")
            
    '''if earliest_recording:
        # Fetch the artist name, title, and release date if available
        #metadata["artist"] = earliest_recording["artist-credit"][0]["name"]
        if "’" in earliest_recording['title']:
            earliest_recording['title'] = earliest_recording['title'].replace("’","'")
        metadata["title"] = earliest_recording["title"]

        # Fetch release information if available
        if "release-list" in earliest_recording:
            for release in earliest_recording["release-list"]:
                if "date" in release:
                    metadata["release_date"] = release["date"]
                    metadata["year"] = release['date'][:4]
                    break'''

    #print(metadata)
    metadata_title = re.sub(r'[^a-zA-Z0-9 ]', '',metadata['title'].lower())
    given_title = re.sub(r'[^a-zA-Z0-9 ]', '',title.lower())
    if metadata_title in given_title or given_title in metadata_title:
        print()
        return metadata
    else:
        print("NOT A MATCH\n")
        return None


def process_filename(filename: str):
    """Processes a filename to fetch music metadata using MusicBrainz."""
    try:
        # Extract artist and title from the filename
        artist, title = extract_artist_title_from_filename(filename)
        
        # Fetch metadata from MusicBrainz using artist and title
        metadata = fetch_musicbrainz_metadata(artist, title, exact_artist=False)
        
        print()
        if metadata:
            #print(json.dumps(metadata,indent=4))
            return metadata
        
    except ValueError as e:
        print(f"Error processing filename {filename}: {e}")
        return None

def generate_music_video_data_old(videos_directory):
    videos = find_files_without_nfo(videos_directory)
    for video in sorted(videos):
        youtube_data = None
        metadata = None
        print(f"------------------------\n{video}")
        youtube_id, filename = extract_youtube_id_from_filename(video)
        fileinfo = {}
        fileinfo['streamdetails'] = {}    
        fileinfo['movie'] = {}
        fileinfo['movie']['tags'] = []
        fileinfo['movie']['title'] = os.path.splitext(filename)[0].replace('_',' ').replace('.',' ')
        fileinfo['movie']['source'] = "UNKNOWN"
        fileinfo['movie']['edition'] = "NONE" 
        fileinfo['movie']['dateadded'] = None
        if youtube_id:
            youtube_data = fetch_youtube_metadata(youtube_id)
            fileinfo['movie']['source'] = "YouTube"
        if youtube_data:
            artist, title = extract_artist_title_from_filename(youtube_data['title'])
            metadata = fetch_musicbrainz_metadata(artist,title)
            youtube_tags = youtube_data.get('tags')
            for youtube_tag in youtube_tags:
                fileinfo['movie']['tags'].append(youtube_tag)
            youtube_url = youtube_data.get('webpage_url')
            youtube_upload_date = datetime.datetime.strptime(youtube_data.get('upload_date'),'%Y%m%d')
            
            fileinfo['movie']['trailer'] = youtube_url
            fileinfo['movie']['dateadded'] = youtube_upload_date.strftime('%Y-%m-%d %H:%M:%S')
            fileinfo['movie']['title'] = f"{artist} - {title}"
            fileinfo['movie']['plot'] = f"{artist} - {title} - Music Video"
            fileinfo['movie']['outline'] = fileinfo['movie']['plot']
        else:
            metadata = process_filename(os.path.basename(filename))
   
        fileinfo['movie']['original_filename'] = os.path.basename(video)
        
        if metadata:
            fileinfo['movie']['year'] = metadata.get('year')
            fileinfo['movie']['aired'] = metadata.get('release_date')
            fileinfo['movie']['plot'] = f"{metadata.get('artist')} - {metadata.get('title')} - Music Video"
            fileinfo['movie']['outline'] = fileinfo['movie']['plot']
            for tag in metadata['genres']:
                fileinfo['movie']['tags'].append(tag)
        fileinfo['movie']['tags'] = list(set(fileinfo['movie']['tags']))
        video_metadata = get_video_metadata(video)
        for streaminfo in video_metadata['streams']:
            if streaminfo.get('codec_type') == "video":
                fileinfo['streamdetails']['video'] = {}
                fileinfo['streamdetails']['video']['codec'] = streaminfo.get('codec_name')
                fileinfo['streamdetails']['video']['width'] = streaminfo.get('width')
                fileinfo['streamdetails']['video']['height'] = streaminfo.get('height')
                fileinfo['streamdetails']['video']['durationinseconds'] = streaminfo.get('duration')
                if not youtube_id and streaminfo.get('tags'):
                    try:
                        fileinfo['movie']['dateadded'] = datetime.datetime.fromisoformat(streaminfo.get('tags')['creation_time'].replace("Z", "+00:00")).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        pass
            elif streaminfo.get('codec_type') == "audio":
                fileinfo['streamdetails']['audio'] = {}
                fileinfo['streamdetails']['audio']['codec'] = streaminfo.get('codec_name')
                fileinfo['streamdetails']['audio']['channels'] = streaminfo.get('channels')
                fileinfo['streamdetails']['audio']['sample_rate'] = streaminfo.get('sample_rate')
        if fileinfo['movie']['year'] is None:
            try:
                fileinfo['movie']['year'] = fileinfo['movie']['dateadded'][:4]
                fileinfo['movie']['aired'] = fileinfo['movie']['dateadded'].split(' ')[0]
            except:
                pass
        filexml = dict_to_xml(fileinfo)
        # Saving NFO File
        nfo_filename = os.path.splitext(video)[0] + '.nfo'
        nfo_path = nfo_filename
        with open(nfo_path, 'w', encoding='utf-8') as nfo_file:
            nfo_file.write(filexml)
        print(filexml)
        
def dict_to_xml(data: dict) -> str:
    """
    Convert dictionary data to XML format and return a pretty-printed XML string.
    
    Args:
        data (dict): Dictionary containing data to be converted to XML.
    
    Returns:
        str: A formatted XML string.
    """
    # Create the root element
    root = ET.Element("movie")
    
    # Process the data dictionary under "movie"
    for key, value in data.get("movie", {}).items():
        if key != "tags":
            # For other keys, just create a subelement with the key as the tag name
            element = ET.SubElement(root, key)
            element.text = str(value)
        else:
            # If the key is "tags", iterate over each tag and create a <tag> element for each one
            for tag in value:
                tag_element = ET.SubElement(root, "tag")
                tag_element.text = str(tag)
    
    # Add fileinfo and streamdetails
    fileinfo_element = ET.SubElement(root, "fileinfo")
    streamdetails_element = ET.SubElement(fileinfo_element, "streamdetails")
    
    # Add video details
    video = data.get("streamdetails", {}).get("video", {})
    video_element = ET.SubElement(streamdetails_element, "video")
    for key, value in video.items():
        element = ET.SubElement(video_element, key)
        element.text = str(value)
    
    # Add audio details
    audio = data.get("streamdetails", {}).get("audio", {})
    audio_element = ET.SubElement(streamdetails_element, "audio")
    for key, value in audio.items():
        element = ET.SubElement(audio_element, key)
        element.text = str(value)
    
    # Convert the root element to a string
    rough_string = ET.tostring(root, encoding="utf-8")

    # Create the XML declaration and comment with the current date and time
    xml_declaration = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<!--created on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} - Broadcast Emulation Engine -->'
    
    # Pretty print the XML
    dom = minidom.parseString(rough_string)
    pretty_xml_string = dom.toprettyxml(indent="  ")
    pretty_xml_string = pretty_xml_string.replace('<?xml version="1.0" ?>', xml_declaration)
    
    # Return the final formatted XML string with the XML declaration and comment added at the top
    return pretty_xml_string

def update_fileinfo_tags(fileinfo, metadata):
    """
    Update fileinfo's movie tags based on the provided metadata.

    Args:
        fileinfo (dict): Dictionary containing file information.
        metadata (dict): Dictionary containing metadata.

    Returns:
        None
    """
    if metadata:
        # Add genres from metadata to fileinfo tags
        genres = metadata.get('genres', [])
        fileinfo['movie']['tags'].extend(genres)
        
        # Remove duplicate tags and sort them
        fileinfo['movie']['tags'] = list(set(fileinfo['movie']['tags']))
        fileinfo['movie']['tags'].sort()

def generate_music_video_data(videos_directory=False,video=False):
    if videos_directory:
        videos = find_files_without_nfo(videos_directory)
    if video:
        videos = [video]
        
    # Process each video file
    for video in sorted(videos):
        print(f"------------------------\n{video}")
        fileinfo = initialize_fileinfo(video)
        
        youtube_id, filename = extract_youtube_id_from_filename(video)
        youtube_data, metadata = youtube_and_musicbrainz(youtube_id, filename)
        if metadata:
            process_musicbrainz(fileinfo, metadata)
        if youtube_id and youtube_data:
            process_youtube_data(fileinfo, youtube_data)
        
        #update_fileinfo_tags(fileinfo, metadata)
        fileinfo['movie']['tags'] = list(set(fileinfo['movie']['tags']))
        process_stream_details(fileinfo, video, youtube_id)
        
        # Fill in missing year and aired details
        fill_missing_year_and_aired(fileinfo)
        
        # Generate and save NFO file
        save_nfo_file(video, fileinfo)
        
def generate_interstitial_video_data(videos_directory=False,video=False):
    if videos_directory:
        videos = find_files_without_nfo(videos_directory)
    if video:
        videos = [video]
    
    # Process each video file
    for video in sorted(videos):
        print(f"------------------------\n{video}")
        video_data = {}
        fileinfo = initialize_fileinfo(video)
        
        youtube_id, filename = extract_youtube_id_from_filename(video)
        youtube_data = youtube_fetch(youtube_id, filename)

        if youtube_id and youtube_data:
            process_youtube_data(fileinfo, youtube_data)
            video_data['youtube_data'] = youtube_data
        process_stream_details(fileinfo, video, youtube_id)
        video_data['file_info'] = fileinfo
        
        if config['OpenAI Settings']['API Key'] != '':
            clip_dict = analyze_video(video, video_data)
        else:
            clip_dict = None
        if clip_dict:
            process_summary_data(fileinfo, clip_dict)
        
        fileinfo['movie']['tags'] = list(set(fileinfo['movie']['tags']))
        
        # Fill in missing year and aired details
        fill_missing_year_and_aired(fileinfo)
        
        # Generate and save NFO file
        save_nfo_file(video, fileinfo)

def initialize_fileinfo(video):
    filename = os.path.splitext(os.path.basename(video))[0].replace('_', ' ').replace('.', ' ')
    return {
        'streamdetails': {},
        'movie': {
            'title': filename,
            'tags': [],
            'source': 'UNKNOWN',
            'edition': 'NONE',
            'dateadded': None,
            'original_filename': os.path.basename(video),
        }
    }

def youtube_and_musicbrainz(youtube_id, filename):
    youtube_data = None
    metadata = None
    
    if youtube_id:
        youtube_data = fetch_youtube_metadata(youtube_id)
        if youtube_data:
            artist, title = extract_artist_title_from_filename(youtube_data['title'])
            if artist != title:
                metadata = fetch_musicbrainz_metadata(artist, title)
            else:
                metadata = fetch_musicbrainz_metadata(artist, title, exact_artist=False)
    if not metadata:
        metadata = process_filename(os.path.basename(filename))
    return youtube_data, metadata

def youtube_fetch(youtube_id, filename):
    youtube_data = None
    
    if youtube_id:
        youtube_data = fetch_youtube_metadata(youtube_id)
        if youtube_data:
            artist, title = extract_artist_title_from_filename(youtube_data['title'])

    return youtube_data

def process_musicbrainz(fileinfo, metadata):
    fileinfo['movie']['year'] = metadata.get('year')
    fileinfo['movie']['aired'] = metadata.get('release_date')
    fileinfo['movie']['title'] = f"{metadata.get('artist')} - {metadata.get('title')}"
    fileinfo['movie']['outline'] = fileinfo['movie']['plot'] = f"{metadata.get('artist')} - {metadata.get('title')} (Music Video)"
    for metadata_tag in metadata['genres']:
        fileinfo['movie']['tags'].append(metadata_tag)
    #fileinfo['movie']['tags'].extend(metadata['genres'])
    fileinfo['movie']['dateadded'] = metadata.get('release_date')

def process_youtube_data(fileinfo, youtube_data):
    
    artist, title = extract_artist_title_from_filename(youtube_data['title'])
    fileinfo['movie']['source'] = 'YouTube'
    fileinfo['movie']['title'] = f"{artist} - {title}"
    fileinfo['movie']['plot'] = youtube_data.get('description')
    
    youtube_upload_date = datetime.datetime.strptime(youtube_data['upload_date'], '%Y%m%d')
    fileinfo['movie']['trailer'] = youtube_data.get('webpage_url')
    fileinfo['movie']['dateadded'] = youtube_upload_date.strftime('%Y-%m-%d %H:%M:%S')
    
    for youtube_tag in youtube_data.get('tags', []):
        fileinfo['movie']['tags'].append(youtube_tag)

def process_summary_data(fileinfo, summary_dict):
    fileinfo['movie']['title'] = summary_dict['Title']
    fileinfo['movie']['aired'] = summary_dict['Air Date']
    fileinfo['movie']['year'] = summary_dict['Air Date'][:4]
    fileinfo['movie']['plot'] = summary_dict['Description'] + "\n\nGenerated by ChatGPT"
    fileinfo['movie']['outline'] = summary_dict['Description'] + "\n\nGenerated by ChatGPT"
    tags = summary_dict['Tags'].split(',')
    fileinfo['movie']['tags'] = []
    for tag in tags:
        fileinfo['movie']['tags'].append(tag.strip())
    return fileinfo
    
def process_stream_details(fileinfo, video, youtube_id):
    video_metadata = get_video_metadata(video)
    for streaminfo in video_metadata['streams']:
        codec_type = streaminfo.get('codec_type')
        
        if codec_type == "video":
            process_video_stream(fileinfo, streaminfo, youtube_id)
        elif codec_type == "audio":
            process_audio_stream(fileinfo, streaminfo)
    return fileinfo

def process_video_stream(fileinfo, streaminfo, youtube_id):
    video_details = {
        'codec': streaminfo.get('codec_name'),
        'width': streaminfo.get('width'),
        'height': streaminfo.get('height'),
        'durationinseconds': streaminfo.get('duration')
    }
    
    fileinfo['streamdetails']['video'] = video_details
    
    if not youtube_id and streaminfo.get('tags'):
        creation_time = streaminfo['tags'].get('creation_time')
        if creation_time:
            try:
                creation_time_formatted = datetime.datetime.fromisoformat(creation_time.replace("Z", "+00:00")).strftime('%Y-%m-%d %H:%M:%S')
                fileinfo['movie']['dateadded'] = creation_time_formatted
            except ValueError:
                pass
    return fileinfo

def process_audio_stream(fileinfo, streaminfo):
    audio_details = {
        'codec': streaminfo.get('codec_name'),
        'channels': streaminfo.get('channels'),
        'sample_rate': streaminfo.get('sample_rate')
    }
    
    fileinfo['streamdetails']['audio'] = audio_details
    return fileinfo

def fill_missing_year_and_aired(fileinfo):
    if 'year' not in fileinfo['movie']:
        print(fileinfo['movie'])
        fileinfo['movie']['year'] = None
        
    if fileinfo['movie']['year'] is None:
        try:
            dateadded = fileinfo['movie']['dateadded']
            if dateadded:
                fileinfo['movie']['year'] = dateadded[:4]
                fileinfo['movie']['aired'] = dateadded.split(' ')[0]
        except:
            pass

def save_nfo_file(video, fileinfo):
    filexml = dict_to_xml(fileinfo)
    nfo_filename = os.path.splitext(video)[0] + '.nfo'
    with open(nfo_filename, 'w', encoding='utf-8') as nfo_file:
        nfo_file.write(filexml)
    #print(filexml)

def generate_summary(audio_text,video_data,frames,openai_client):
    video_context = ''
    response = None
    if video_data:
        video_context += f"The filename of this video file is {video_data['file_info']['movie']['title']} and it is {video_data['file_info']['streamdetails']['video']['durationinseconds']} seconds long."

    if audio_text:
        video_context += '\nThe following text is a transcript of the audio from the video clip\n'+audio_text

    content = [{"type": "text","text": video_context}]
    for frame in frames:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{frame}", "detail": config['OpenAI Settings']['Vision Detail Level']}}
)
    loops = 0
    while True:
        loops += 1
        try:
            req=openai_client.chat.completions.create(
              model=config['OpenAI Settings']['GPT Model'],
              messages=[
                    {"role": "system", "content": config['OpenAI Settings']['ChatGPT Role']},
                    {"role": "user", "content": content},
                    {"role": "user", "content": config['OpenAI Settings']['ChatGPT Prompt']}
                ],
                max_tokens=4096,
            )
            response = req

            break
        except RateLimitError as e:
            error_message = e.message
            try:
                match = re.search(r"'message': '(.*?)'", error_message)
                if match:
                    error_text = match.group(1)
                    print("ERROR: "+ error_text)

                
                # Implement your retry logic based on the error information
                time_pattern = re.compile(r'in (\d+m\d+s)')
                match = time_pattern.search(error_text)

                if match:
                    time_to_wait = match.group(1)
                    seconds_to_wait = int(time_to_wait.split('m')[0]) * 60 + int(time_to_wait.split('m')[1].rstrip('s'))
                else:
                    seconds_to_wait = 15 * 60

                retry_at = datetime.datetime.now() + datetime.timedelta(seconds=seconds_to_wait)
                retry_at_str = retry_at.strftime('%H:%M:%S')
                print(e.message,"Retrying at " + retry_at_str)
                time.sleep(seconds_to_wait)

            except Exception as e:
                print(e)
                #print(error_message)
                retry_at = datetime.datetime.now()+datetime.timedelta(minutes=15)
                retry_at_str = retry_at.strftime('%H:%M:%S')
                print(e, "Retrying at "+retry_at_str)
                time.sleep(900)
        except BadRequestError as e:
            error_message = e.message
            match = re.search(r"'message': '(.*?)'", error_message)
            if match:
                error_text = match.group(1)
                print("ERROR: "+ error_text)
            if loops < 3:
                code_match = re.search(r"'code': '(.*?)'", error_message)
                if code_match:
                    code = code_match.group(1)
                    
                    if code == "content_policy_violation":
                        content = []
                        content.append({"type": "text","text": video_context})
                        content.append({"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{frames[0]}","detail":config['OpenAI Settings']['Vision Detail Level']}})
                        print(f"CONTENT POLICY VIOLATION")
                    if "invalid_type" in code:
                        print(error_message)
                        #print(json.dumps(content,indent=4))
                        print(f"INVALID TYPE")
                        '''for k,v in content:
                            print(k[:30])
                            time.sleep(10)'''
                        break
                retry_at = datetime.datetime.now()+datetime.timedelta(seconds=loops*loops+loops)
                retry_at_str = retry_at.strftime('%H:%M:%S')
                print(e, "Retrying at "+retry_at_str)
                time.sleep(loops*loops+loops)
            else:
                if loops <= 5:
                    retries = loops - 2
                    retry_at = datetime.datetime.now()+datetime.timedelta(seconds=retries*retries)
                    retry_at_str = retry_at.strftime('%H:%M:%S')
                    print(e, "Retrying at "+retry_at_str)
                    time.sleep(retries*retries)
                else:
                    break
        except (APITimeoutError, InternalServerError) as e:
            error_message = e.message
            match = re.search(r"'message': '(.*?)'", error_message)
            if match:
                error_text = match.group(1)
                print("ERROR: "+ error_text)
            if loops <= 6:
                retry_at = datetime.datetime.now()+datetime.timedelta(seconds=loops*loops)
                retry_at_str = retry_at.strftime('%H:%M:%S')
                print(f"{e}: Retrying at {retry_at.strftime('%H:%M:%S')}")
                time.sleep(loops*loops)
            else:
                break
    try:
        finish_details = response.choices[0].finish_reason
        summary = response.choices[0].message.content
    except AttributeError as e:
        print(e)
        finish_details = response.finish_reason
        summary = response.message.content
    tokens_used = response.usage.total_tokens
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens
    #print(response)
    return summary, tokens_used, input_tokens, output_tokens, finish_details

def analyze_video(video_path, video_data):
    openai_client = openai.OpenAI(api_key=config['OpenAI Settings']['API Key'])
    starting_time = datetime.datetime.now()
    scriptPath = "./"
    try:
        # Open the video file
        directory, video_file_name = os.path.split(video_path)

        video = cv2.VideoCapture(video_path)
        assert video.isOpened()

        # Obtain video properties
        x_shape = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
        y_shape = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = video.get(cv2.CAP_PROP_FPS)

        # Create a JSON object to store the results
        output = {"frames": []}
        frames = []
        gray_frames = []
        blurred_frames = []
        threshold_frames = []
        morphed_frames = []
        sharpened_frames = []
        processed_frames = []
        base64_frames = []
        video_name = os.path.basename(video_path)
        video_name = os.path.splitext(video_name)[0]
        print("Extracting audio from video using MoviePy")
        audio_file = os.path.join(scriptPath, f"{video_name}.wav")
        video_mp = mp.VideoFileClip(video_path)
        video_mp.audio.write_audiofile(audio_file, verbose=False, logger=None)
        video_duration = video_mp.duration
        video_mp.close()
        wav_size = os.path.getsize(audio_file)
        target_size = 26214400
        
        if wav_size > target_size:
            audio = AudioFileClip(audio_file)
            mp3_file = os.path.join(scriptPath, f"{video_name}.mp3")
            audio.write_audiofile(mp3_file, codec='mp3', bitrate='192k', logger="bar")
            print(f"File compressed to MP3: {mp3_file}")
            print("Extracting audio transcript")
            audio_mp3 = open(os.path.join(scriptPath, f"{video_name}.mp3"), 'rb')
            audio_text = openai_client.audio.transcriptions.create(model="whisper-1", file=audio_mp3)
            audio_mp3.close()            
            os.remove(os.path.join(scriptPath, f"{video_name}.mp3"))
        else:
            print("Extracting audio transcript")
            audio_wav = open(os.path.join(scriptPath, f"{video_name}.wav"), 'rb')
            audio_text = openai_client.audio.transcriptions.create(model="whisper-1", file=audio_wav)
            audio_wav.close()
        print("[TRANSCRIPTION] "+audio_text.text)
        os.remove(os.path.join(scriptPath, f"{video_name}.wav"))
        if os.path.exists(os.path.join(scriptPath, f"{video_name}.mp3")):
            os.remove(os.path.join(scriptPath, f"{video_name}.mp3"))
        print("Processing Frames")
        cap = cv2.VideoCapture(video_path)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        f = 0
        
        while True:
            ret, frame = video.read()
            if not ret:
                frame_diff = frame_count - len(frames)
                while frame_diff > 0:
                    #bar()
                    frame_diff -= 1
                break

            _, frame_buffer = cv2.imencode('.jpg', frame)
            frame_base64 = base64.b64encode(frame_buffer).decode('utf-8')
            
            base64_frames.append(frame_base64)
            #bar()
            f += 1
        video.release()
        cap.release()
        count = 0

        chosen_frames = []
        labels = []
        frame_interval = int(fps*float(config['OpenAI Settings']['Seconds Per Image']))
        
        for i in range(int(fps), len(base64_frames), frame_interval):
            chosen_frames.append(base64_frames[i])
        
        video.release()
        #cv2.destroyAllWindows()
        attempt = 0
        while True:
            try:
                attempt += 1
                print("Generating a summary using OpenAI")
                summary, tokens_used, input_tokens, output_tokens, finish_details = generate_summary(audio_text.text, video_data, chosen_frames, openai_client)
                print("Summary generated with complete code: "+str(finish_details))
                print("Input Tokens Used: "+str(input_tokens),end='\n')
                print("Output Tokens Used: "+str(output_tokens),end='\n')
                try:
                    print("Saving API Usage Data...")
                    api_usage_json = "api_usage.json"
                    if os.path.exists(api_usage_json):
                        with open(api_usage_json, "r") as jsonfile:
                            existing_api_usage = json.load(jsonfile)
                    else:
                        existing_api_usage = {}
                    current_month_year = datetime.datetime.now().strftime("%Y-%m")
                    chatgpt_usage = int(tokens_used)
                    chatgpt_input = int(input_tokens)
                    chatgpt_output = int(output_tokens)
                    if attempt == 1:
                        whisper_usage = round(video_duration)
                        #vision_usage = count
                    else:
                        whisper_usage = 0
                        #vision_usage = 0
                    
                    if current_month_year in existing_api_usage:
                        month_data = existing_api_usage[current_month_year]
                    else:
                        month_data = {
                            'chatgpt': {
                                'usage': 0,
                                'input': 0,
                                'output': 0,
                                'cost': 0
                            },
                            'whisper': {
                                'usage': 0,
                                'cost': 0
                            }
                        }
                        existing_api_usage[current_month_year] = month_data
                        
                except Exception as e:
                    print("ERROR: "+str(e))
                    traceback.print_exc()
                
                month_data['chatgpt']['usage'] += chatgpt_usage
                
                try:
                    month_data['chatgpt']['input'] += chatgpt_input
                except:
                    month_data['chatgpt']['input'] = chatgpt_input
                try:
                    month_data['chatgpt']['output'] += chatgpt_output
                except:
                    month_data['chatgpt']['output'] = chatgpt_output
                    
                month_data['whisper']['usage'] += whisper_usage
                #month_data['vision']['usage'] += vision_usage
                
                chatgpt_input_cost = float(config['OpenAI Settings']['ChatGPT Input Cost'])
                chatgpt_output_cost = float(config['OpenAI Settings']['ChatGPT Output Cost'])
                
                whisper_cost = float(config['OpenAI Settings']['Whisper Cost'])
                
                clip_processing_cost = (chatgpt_input_cost * chatgpt_input) + (chatgpt_output_cost * chatgpt_output) + (whisper_cost * whisper_usage)
                
                print("\nAPI Usage Cost $"+str(clip_processing_cost))                
                try:
                    month_data['chatgpt']['cost'] = (month_data['chatgpt']['input'] * chatgpt_input_cost) + (month_data['chatgpt']['output'] * chatgpt_output_cost)
                except:
                    month_data['chatgpt']['cost'] = month_data['chatgpt']['usage'] * (chatgpt_input_cost + chatgpt_output_cost)/2
                
                month_data['whisper']['cost'] = month_data['whisper']['usage'] * whisper_cost

                existing_api_usage[current_month_year] = month_data

                with open(api_usage_json, 'w') as file:
                    json.dump(existing_api_usage, file, indent=4)
                start_pos = summary.find("{")
                end_pos = summary.rfind("}")
                
                if start_pos != -1 and end_pos != -1:
                    json_str = summary[start_pos:end_pos + 1]
                    clip_dict = json.loads(json_str)
                else:
                    clip_dict = json.loads(summary)
                break
            except json.decoder.JSONDecodeError as e:
                print("ERROR: "+str(e))
                print(summary)
                traceback.print_exc()
                if finish_details != "stop":
                    break
                print(e, "Retrying...")
        try:
            if " " not in clip_dict['Title']:
                clip_dict['Title'] = clip_dict['Title'].replace('-',' ').replace('_',' ')
            #print(json.dumps(clip_dict,indent=4))
        except Exception as e:
            print("ERROR: "+str(e))
            traceback.print_exc()
            clip_dict = None
        
        #get time to complete
        end_time = datetime.datetime.now()
        elapsed_time = end_time - starting_time
        time_minutes = elapsed_time.total_seconds() // 60
        time_seconds = elapsed_time.total_seconds() % 60
        #print(f"\nElapsed time: {int(time_minutes):02d}:{int(time_seconds):02d}")
        print("\n------------------------------------------------")
        if elapsed_time.total_seconds() >= 15:    
            print("Total API Usage and Costs for the past 30 days")
            update_usage_data(config['OpenAI Settings']['API Key'])
            calculate_costs_from_file("openai_usage.json", config=config, num_days=30)
            print("------------------------------------------------")
        print(f"File Analyisis Complete in {int(time_minutes):d} minutes, {int(time_seconds):d} seconds")
        try:
            for k, v in clip_dict.items():
                print(str(k)+': '+str(v))
            
        except:
            pass
        print("------------------------------------------------\n")
        time.sleep(0.5)
        return clip_dict
    except Exception as e:
        print("ERROR:  "+str(e))
        traceback.print_exc()
        return None


if __name__ == '__main__':  
    #generate_music_video_data('Z:/music videos/')
    generate_interstitial_video_data(videos_directory='Z:\commercials\Fake Commercials')
