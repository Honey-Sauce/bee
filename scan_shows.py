import configparser
import os
import json
import math
import re
import requests
import time
import traceback
import urllib.parse
import uuid
import xmltodict
from datetime import datetime
from difflib import SequenceMatcher
from moviepy.editor import VideoFileClip
from xml.etree import ElementTree as ET

class RateLimiter:
    def __init__(self, requests_per_second):
        self.requests_per_second = requests_per_second
        self.interval = 1.0 / requests_per_second
        self.last_request_time = None

    def wait_before_request(self):
        if self.last_request_time is not None:
            elapsed_time = time.time() - self.last_request_time
            if elapsed_time < self.interval:
                time.sleep(self.interval - elapsed_time)

    def make_request(self, url):
        while True:
            try:
                self.wait_before_request()
                response = requests.get(url)
                self.last_request_time = time.time()
                return response
            except (requests.exceptions.RequestException, requests.exceptions.ConnectionError) as e:
                print(f"Request failed: {e}. Retrying after 2 seconds...")
                time.sleep(2)

config = configparser.ConfigParser()
config.read('config.ini')

api_key = config['Settings']['TMDB Key']
show_folder_path = [s.strip() for s in config['Paths']['Show Folders'].split(',')]
output_json_path = config['Content']['Show JSON']
requests_per_second = int(config['RateLimiter']['Showscan'])
rate_limiter = RateLimiter(requests_per_second=requests_per_second)

#init() #Initialize colorama

# Define valid video file extensions
VALID_VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv'}

def xml_to_dict(element):
    return xmltodict.parse(ET.tostring(element, encoding='utf-8').decode('utf-8'))

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def get_highest_existing_id(existing_data):
    existing_ids = [entry['id'] for entry in existing_data]
    return max(existing_ids) if existing_ids else 0

def clean_title(title):
    title = title.strip()
    # Replace ampersand with the word 'and'
    title = title.replace('&', 'and')
    title = title.replace('.', ' ')
    # Remove special characters, except for parentheses, and extra spaces from the title
    cleaned_title = re.sub(r"[^\w\s!'()]", '', title).strip()
    # Eliminate double or more spaces
    cleaned_title = re.sub(r'\s+', ' ', cleaned_title)
    return cleaned_title

def extract_year_from_filename(filename):
    # Exclude the first word from the filename
    filename_without_first_word = ' '.join(filename.split()[1:])
    
    # Extract a 4-digit number from the modified filename as the year within parentheses
    match = re.search(r'\((\d{4})\)', filename_without_first_word)
    
    return match.group(1) if match else None

def convert_roman_numerals(title):
    # Dictionary to map Roman numerals to their corresponding Arabic numerals
    roman_numerals = {'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5', 'VI': '6', 'VII': '7', 'VIII': '8', 'IX': '9', 'X': '10'}
    
    # Regular expression pattern to match Roman numerals
    pattern = re.compile(r'\b(?:' + '|'.join(re.escape(key) for key in roman_numerals.keys()) + r')\b')
    
    # Replace Roman numerals with corresponding Arabic numerals
    def replace_roman(match):
        roman_numeral = match.group()
        return roman_numerals.get(roman_numeral, roman_numeral)

    converted_title = pattern.sub(replace_roman, title)
    
    return converted_title

def get_show_details(show_id, rate_limiter):
    try:
        details_url = f'https://api.themoviedb.org/3/tv/{show_id}?api_key={api_key}&append_to_response=first_air_dates,alternative_titles,videos,keywords,recommendations,similar,credits'
        # Make request using rate limiter
        response = rate_limiter.make_request(details_url)
        show_details = response.json()

        return show_details
    except Exception as e:
        print(f"Error getting details for movie ID {show_id}: {e}")
    return None

def get_season_details(series_id, season_number):
    # Make a request to the TMDB API to get season details
    url = f"https://api.themoviedb.org/3/tv/{series_id}/season/{season_number}?api_key={api_key}"
    response = rate_limiter.make_request(url)
    return response.json()

def extract_show_details(show_details):
    valid_attributes = {}

    # If show_details is a dictionary, return it directly
    if isinstance(show_details, dict):
        return show_details

    # Collect potential issues during extraction
    problematic_attributes = []

    # Extract movie details and handle potential issues
    for key, value in show_details.__dict__.items():
        # Check if the attribute name is a string
        if isinstance(key, str):
            # Convert attribute name to string
            key_str = str(key)
            valid_attributes[key_str] = value
        else:
            problematic_attributes.append(key)
            print(f"Skipping attribute with non-string name: {key}")

    # Print debug output for problematic attributes
    if problematic_attributes:
        print(f"Problematic attributes: {problematic_attributes}")

    return valid_attributes

def get_all_directories(directory_path):
    full_directory_paths = [os.path.join(directory_path, d) for d in os.listdir(directory_path) if os.path.isdir(os.path.join(directory_path, d))]
    return sorted(full_directory_paths)

def get_all_video_files(movie_folders):
    all_video_files = []
    for movie_folder in movie_folders:
        video_files = [file for file in os.listdir(movie_folder) if is_valid_video_file(file)]
        all_video_files.extend(video_files)
    return sorted(all_video_files, reverse=False)

def is_valid_video_file(file_path):
    _, file_extension = os.path.splitext(file_path)
    return file_extension.lower() in VALID_VIDEO_EXTENSIONS

def print_attributes(obj, indent=""):
    for key, value in obj.__dict__.items():
        if hasattr(value, '__dict__'):
            print(f"{indent}{key}:")
            print_attributes(value, indent + "  ")
        else:
            print(f"{indent}{key}: {value}")

def get_attributes(obj, indent=""):
    result = {}
    for key, value in obj.__dict__.items():
        if hasattr(value, '__dict__'):
            result[key] = get_attributes(value, indent + "  ")
        else:
            result[key] = value
    return result

def search_and_store_tv_shows(tv_show_folders, output_json_path):
    tv_shows = {}

    # Load existing data
    '''if os.path.exists(output_json_path):
        with open(output_json_path, 'r') as existing_file:
            existing_data_dict = json.loads(existing_file.read())
    else:
        existing_data_dict = {}'''
    existing_data_dict = {}

    show_directories = []

    for tv_show_folder in tv_show_folders:
        show_directories.extend(get_all_directories(tv_show_folder))

    total_shows = len(show_directories)
    processed_files = 0

    def process_single_episode(episode_element, tv_shows, existing_data_dict, show_folder):
        try:
            file_info = episode_element.find(".//fileinfo")
            stream_details = file_info.find(".//streamdetails")
            video_info = stream_details.find(".//video")
            audio_info = stream_details.find(".//audio")
            duration_in_seconds = int(video_info.find("durationinseconds").text)

            if duration_in_seconds:
                duration_ms = duration_in_seconds * 1000
                duration_min = round(duration_in_seconds / 60)
            else:
                duration_ms = None
                duration_min = None

            episode_filename = episode_element.find(".//original_filename").text if episode_element is not None and episode_element.find(".//original_filename") is not None else None
            episode_directory = os.path.dirname(nfo_file)
            episode_uuid = str(uuid.uuid4())
            episode_id = episode_element.find(".//id").text
            try:
                int(episode_id)
            except:
                unique_id_elements = episode_element.findall(".//uniqueid[@default='true']")
                if unique_id_elements:
                    episode_id = unique_id_elements[0].text
                else:
                    # If no unique_id with default="true" is found, set episode_id to None
                    episode_id = None
                
            if episode_filename:
                episode_path = os.path.join(episode_directory, episode_filename)
            else:
                episode_path = None

            episode_details = xml_to_dict(episode_element)
            episode_data = episode_details.get("episodedetails", {})

            episode_files_dict = {
                'unique_id': episode_uuid,
                'episode_ids': [episode_id],  # List of episode IDs associated with this file
                'episode_path': episode_path,
                'episode_details': [],
            }

            

            # Check if the file already exists in the data
            #existing_file_entry = show_entry['files'].get(episode_path)
            try:
                # Update the list of episode IDs for this file
                show_entry['files'][episode_path]['episode_ids'].append(episode_id)
            except KeyError:
                show_entry['files'][episode_path] = episode_files_dict
            show_entry['files'][episode_path]['episode_details'].append(episode_data)
        except AttributeError as e:
            try:
                print(f'No file for episode: {episode_element.find(".//showtitle").text} S{episode_element.find(".//season").text}E{episode_element.find(".//episode").text} - {episode_element.find(".//title").text}')
            except:
                print(f'No file for episode: {episode_element}')
        except Exception as e:
            print(f"Error processing episode: {e}")
            traceback.print_exc()

    for show_folder in show_directories:
        print(f"\n\nProcessing {show_folder}")
        show_nfo = os.path.join(show_folder, 'tvshow.nfo')
        if os.path.exists(show_nfo):
            
            try:
                tree = ET.parse(show_nfo)
                root = tree.getroot()
                show_id = root.find(".//id").text
                show_title = root.find(".//title").text
                
                with open(show_nfo, 'r', encoding='utf-8') as file:
                    show_content = file.read()
                
                show_tree = ET.ElementTree(ET.fromstring(show_content))
                show_root = show_tree.getroot()
                
                show_data = xml_to_dict(show_root)
                show_data = show_data.get("tvshow", {})
                if show_data == {}:
                    print(show_content)
                existing_entry = existing_data_dict.get(show_id)
                
                if not existing_entry:
                    show_entry = {
                        'id': show_id,
                        'title': show_title,
                        'show_path': show_folder,
                        'files': {},
                    }
                    
                    show_entry.update(show_data)
                    
                    #show_entry['files'] = {}
                    #show_entry['episodes'] = {}

                    # Scrape NFO files in the current folder and subfolders
                    nfo_files = []

                    for root, dirs, files in os.walk(show_folder):
                        for i, file in enumerate(files):
                            if file.lower().endswith(".nfo") and file != 'tvshow.nfo' and not re.match(r'season\d+\.nfo', file, re.I):
                                file_path = os.path.join(root, file)
                                nfo_files.append(file_path)
                            percent_complete = ((i + 1) / len(files)) * 100
                            #print(f"Processed files: {i + 1}/{len(files)} - {percent_complete:.2f}%", end='         \r')
                    print(f"\n{len(nfo_files)} NFO Files found")

                    for i, nfo_file in enumerate(nfo_files):
                        if os.path.basename(nfo_file) != 'season.nfo':
                            try:
                                with open(nfo_file, 'r', errors='ignore') as file:
                                    xml_content = file.read()
                                try:
                                    # Parse the entire XML content using ElementTree
                                    tree = ET.ElementTree(ET.fromstring(xml_content))
                                    root_element = tree.getroot()
                                    process_single_episode(root_element, tv_shows, existing_data_dict,show_folder)
                                except ET.ParseError as pe:
                                    # Multiple episodes in a single NFO file
                                    xml_content = xml_content.replace('</episodedetails>\n<episodedetails>','</episodedetails>[SPLITHERE]<episodedetails>')
                                    xml_content_split = xml_content.split('[SPLITHERE]')
                                    
                                    for episode_element in xml_content_split:
                                        # Parse the entire XML content using ElementTree
                                        #print(episode_element,end='[ENDOFTEXT]\n\n')
                                        tree = ET.ElementTree(ET.fromstring(episode_element.strip()))
                                        root_element = tree.getroot()
                                        process_single_episode(root_element, tv_shows, existing_data_dict,show_folder)

                            except Exception as e:
                                print(f"Error processing '{nfo_file}': {e}")
                                traceback.print_exc()

                            '''print(
                                f"Processed NFO files: {i + 1}/{len(nfo_files)} - {((i + 1) / len(nfo_files)) * 100:.2f}%",
                                end='\r')'''
                    print()
                    
                    show_entry['files'] = reorder_files_dict(show_entry['files'])
                    
                    tv_shows[show_id] = show_entry
                    existing_data_dict[show_id] = show_entry

            except Exception as e:
                print(f"Error processing '{show_folder}': {e}")
                traceback.print_exc()

        processed_files += 1
        percentage_done = (processed_files / total_shows) * 100
        #print(f"Processed shows: {processed_files}/{total_shows} - {percentage_done:.2f}%", end='\r')

    # Validate and clean up entries
    '''for entry_id, entry in existing_data_dict.items():
        # Remove file locations that no longer exist or are not in tv_show_folders
        entry_seasons = entry.get('seasons', [])
        for season in entry_seasons:
            season['episodes'] = {
                episode_key: episode_file_details
                for episode_key, episode_file_details in season.get('episodes', {}).items()
                if os.path.exists(episode_file_details.get('filename', '')) and any(
                    tv_show_folder in episode_file_details.get('filename', '')
                    for tv_show_folder in tv_show_folders
                )
            }

    # Remove entries with empty seasons or episodes arrays
    existing_data_dict = {entry_id: entry for entry_id, entry in existing_data_dict.items() if entry.get('seasons')}'''

    # Combine existing data with new data
    combined_data = existing_data_dict.copy()
    combined_data.update(tv_shows)

    # Save combined results to JSON file
    with open(output_json_path, 'w') as show_file:
        json.dump(combined_data, show_file, indent=2)

def reorder_files_dict(files_dict):
    # Sorting the dictionary by 'season' and 'episode'
    sorted_files = dict(
        sorted(
            files_dict.items(),
            key=lambda item: (
                int(item[1]['episode_details'][0]['season']),  # First sort by season
                int(item[1]['episode_details'][0]['episode'])  # Then sort by episode
            )
        )
    )
    return sorted_files

def get_file_details(root, file):
    try:
        # Create a VideoFileClip object to extract video information
        video_clip = VideoFileClip(os.path.join(root, file))

        # Extract video duration and filesize
        video_duration = video_clip.duration * 1000
        video_filesize = os.path.getsize(os.path.join(root, file))

        # Create a dictionary with file details
        file_id = uuid.uuid4()
        file_details = {
            'file_id': str(file_id),
            'filename': os.path.abspath(os.path.join(root, file)),
            'filesize': video_filesize,
            'duration_ms': round(video_duration),
            'duration_min': round(video_duration / 60000),
            'episode_id': None
        }

        # Extract metadata from the video (if available)
        if video_clip.reader.infos:
            file_details.update(video_clip.reader.infos)

        return file_details
    except UnicodeDecodeError:
        print(f"Error decoding file: {os.path.join(root, file)}")
        return None

def find_matching_video_file(show_folder, show_title, season_number, episode_number, all_video_files):
    # Clean the show_title
    cleaned_show_title = clean_title(show_title)

    # Iterate over files in show_folder and its subdirectories
    for file_info_key, file_info in all_video_files.items():
        filepath = file_info['filename']
        
        root, file = os.path.split(filepath)
        file, extension = os.path.splitext(file)
        # Clean the filename
        cleaned_filename = clean_title(file)
        
        # Check if cleaned_show_title is present in the cleaned_filename
        if cleaned_show_title in cleaned_filename:
            # Remove cleaned_show_title from cleaned_filename
            cleaned_filename = cleaned_filename.replace(cleaned_show_title, '')
        # Remove content within parentheses and the parentheses themselves
        cleaned_filename = re.sub(r'\([^)]*\)', '', cleaned_filename)
        
        # Print cleaned filename for debugging
        #print(f"Cleaned Filename: {cleaned_filename}")

        # Use regex to extract season and episode numbers
        match = re.search(r'(?i)(?:S|s)(\d+)[^\d]*(\d+)|(\d+)x(\d+)', cleaned_filename)

        # Print regex match for debugging
        #print(f"Regex Match: {match}")

        if match:
            # Check if the group values are digits before conversion
            file_season = int(match.group(1) or match.group(3)) if match.group(1) or match.group(3) else None
            file_episode = int(match.group(2) or match.group(4)) if match.group(2) or match.group(4) else None

            # Check if season and episode numbers match
            if file_season == season_number and file_episode == episode_number:
                return file_info['file_id']

    # Print statement for files with no matches
    print(f"No match found for {show_title} S{season_number:02d}E{episode_number:02d}")

    # Return None if no matching file is found
    return None


def find_unmatched_video_files(show_output_json, show_folders):
    # Load the show output JSON
    with open(show_output_json, 'r') as json_file:
        shows_data = json.load(json_file)

    # Get a list of all video files in the show folders and subfolders
    all_video_files = []
    for show_folder in sorted(show_folders):
        print('\n------------------------')
        print(f"\nScanning video files in {show_folder}...")
        for root, dirs, files in os.walk(show_folder):
            for file in sorted(files):
                if file.lower().endswith(('.mp4', '.mkv', '.avi', '.m4v', '.webm', '.flv')):
                    #print(file.ljust(os.get_terminal_size().columns - 1),end='\r',flush=True)
                    all_video_files.append(os.path.join(root, file))

    # Extract unique filenames from the show output JSON
    json_video_files = set()
    total_shows = len(shows_data)
    show_counter = 0
    for show_id, show_data in shows_data.items():
        show_counter += 1
        #print(f"Processing show data ({show_counter}/{total_shows})...",end='\r',flush=True)

        try:
            for season_data in show_data['details']:
                for episode_data in season_data['episodes']:
                    if 'files' in episode_data:
                        try:
                            json_video_files.update(file_details['filename'] for file_details in episode_data['files'])
                        except:
                            pass
        except:
            pass

    # Find unmatched video files
    unmatched_files = sorted(set(all_video_files) - json_video_files)

    return unmatched_files

def main():
    search_and_store_tv_shows(show_folder_path, output_json_path)

if __name__ == '__main__':
    main()
'''unmatched_files = find_unmatched_video_files(output_json_path, show_folder_path)
print("\nUnmatched Video Files:")
for file in unmatched_files:
    print("-----------------------------------")
    print(file)
    print(file)
    print(clean_title(os.path.basename(file)))'''