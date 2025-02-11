import configparser
import copy
import os
import json
import math
import re
import requests
import shutil
import stat
import tempfile
import time
import traceback
import urllib.parse
import uuid
import xmltodict
from datetime import datetime
from moviepy.editor import VideoFileClip
from xml.etree import ElementTree as ET

import nfogen

config = configparser.ConfigParser()
config.read(os.path.abspath('./config.ini'))
api_key = config['Settings']['TMDB Key']

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

def atomic_write(file_path, data):
    temp_file = None
    try:
        # Create a temporary file in the same directory as the target file
        temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w', dir=os.path.dirname(file_path))
        
        # Write the JSON data to the temporary file
        json.dump(data, temp_file, indent=2)
        
        # Close the temporary file to flush its content to disk
        temp_file.close()
        
        # Set file permissions (read and write for everyone)
        os.chmod(temp_file.name, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH)
        
        # Move the temporary file to the target location atomically
        shutil.move(temp_file.name, file_path)
    
    except Exception as e:
        # Ensure the temporary file is removed if an error occurs
        if temp_file is not None:
            try:
                os.remove(temp_file.name)
            except OSError:
                pass
        raise e
    
    finally:
        # Additional safeguard to remove the temp file if it wasn't already removed
        if temp_file is not None and os.path.exists(temp_file.name):
            try:
                os.remove(temp_file.name)
            except OSError:
                pass

def xml_to_dict(element):
    return xmltodict.parse(ET.tostring(element, encoding='utf-8').decode('utf-8'))

def search_and_store_video_details(videos_folders, output_json_path):
    videos = {}
    videos_details = {}

    # Check if the output JSON file exists
    if os.path.exists(output_json_path) and 1 > 2:
        # Load existing data as a dictionary with unique_id as the key
        with open(output_json_path, 'r') as existing_file:
            existing_data_str = existing_file.read()
            existing_data_dict = json.loads(existing_data_str) if existing_data_str else {}

        # Extract existing movie IDs for comparison
        existing_videos_ids = list(existing_data_dict.keys())
    else:
        existing_data_dict = {}
        existing_videos_ids = []

    total_files = 0
    processed_files = 0

    # Define videos_folders before using it in the generator expression
    total_files = sum(
        1 for videos_folder in videos_folders
        for root, _, files in os.walk(videos_folder) 
        for file in files if file.endswith(".nfo")
    )

    print(f"{total_files} nfo files detected.")
                    
    for videos_folder in videos_folders:
        # Scrape all NFO files in the current folder and its subfolders
        for folder_path, _, files in os.walk(videos_folder):
            for pf, file in enumerate(files):
                if file.endswith(".nfo"):
                    nfo_file_path = os.path.join(folder_path, file)
                    processed_files += 1
                    # Initialize file_details here
                    file_details = None

                    """
                    Parse the information from the NFO file and return relevant details.
                    """
                    try:
                        tree = ET.parse(nfo_file_path)
                        root = tree.getroot()

                        # Extracting file information from <fileinfo>
                        file_info = root.find(".//fileinfo")
                        video_info = file_info.find(".//video")
                        audio_info = file_info.find(".//audio")
                        try:
                            duration_in_seconds = float(video_info.find("durationinseconds").text)
                        except ValueError:
                            video_file_name = root.find(".//original_filename").text
                            video_file_path = os.path.join(folder_path, video_file_name)
                            video_file_clip = VideoFileClip(video_file_path)
                            duration_in_seconds = video_file_clip.duration
                        file_path = os.path.join(os.path.dirname(nfo_file_path), root.find("original_filename").text)
                        # Create a dictionary with file details from the NFO file
                        file_details = {
                            'filepath': file_path,
                            'codec': video_info.find("codec").text,
                            'width': int(video_info.find("width").text),
                            'height': int(video_info.find("height").text),
                            'duration': duration_in_seconds,
                            'duration_ms': duration_in_seconds * 1000,
                            'duration_min': round(duration_in_seconds / 60),
                            'audio_codec': audio_info.find("codec").text,
                            'channels': int(audio_info.find("channels").text),
                        }
                        print(file_path)
                    except Exception as e:
                        print(f"Error parsing NFO file '{nfo_file_path}': {e}")
                        traceback.print_exc()

                    if file_details:
                        # Extract original filename from NFO
                        original_filename = root.find(".//original_filename").text

                        video_title = root.find(".//title").text

                        # Check if the movie is already in the existing data
                        existing_entry_key = next(
                            (entry_id for entry_id, entry in existing_data_dict.items() if entry['title'] == video_title),
                            None)

                        if existing_entry_key:
                            # Update file locations array
                            #existing_data_dict[existing_entry_key]['files'].append(file_details)
                            percentage_done = ((processed_files) / total_files) * 100
                            #print(f"Processed files: {processed_files}/{total_files} - {percentage_done:.2f}% - {folder_path}",end='\r')
                            continue

                        # Create a dictionary with all movie details
                        unique_id = str(uuid.uuid4())
                        video_entry = {
                            'unique_id': unique_id,
                            'title': video_title,
                            'files': [file_details],
                        }
                        
                        video_entry.update(xml_to_dict(root))

                        videos[file_path] = video_entry
                        existing_videos_ids.append(file_path)
                percentage_done = ((processed_files) / total_files) * 100
                #print(f"Processed files: {processed_files}/{total_files} - {percentage_done:.2f}% - {folder_path}", end='\r')

    # Validate and clean up entries
    for entry_id, entry in existing_data_dict.items():
        # Remove file locations that no longer exist or are not in videos_folders
        entry['files'] = [
            file_detail for file_detail in entry.get('files')
            if file_detail is not None and os.path.exists(file_detail.get('filepath')) and any(
                videos_folder in file_detail.get('filepath')
                for videos_folder in videos_folders
            )
        ]


    # Remove entries with empty files arrays
    #existing_data_dict = {entry_id: entry for entry_id, entry in existing_data_dict.items() if entry.get('files')}

    # Combine existing data with new data
    combined_data = copy.deepcopy(existing_data_dict)
    combined_data.update(videos)
    
    # Validate and clean up entries in the combined data
    '''combined_data = {
        entry_id: entry
        for entry_id, entry in combined_data.items()
        if 'files' in entry and isinstance(entry['files'], list) and len(entry['files']) > 0
    }'''

    # Save combined results to JSON file
    atomic_write(output_json_path, combined_data)
        
def main(): 
    commercials_folders = [s.strip() for s in config['Paths']['Commercials Folders'].split(',')]
    commercials_json = config['Interstitials']['Commercials JSON']
    for commercials_folder in commercials_folders:
        nfogen.generate_interstitial_video_data(commercials_folder)
    search_and_store_video_details(commercials_folders, commercials_json)

    trailers_folders = [s.strip() for s in config['Paths']['Trailers Folders'].split(',')]
    trailers_json = config['Interstitials']['Trailers JSON']
    for trailers_folder in trailers_folders:
        nfogen.generate_interstitial_video_data(trailers_folder)
    search_and_store_video_details(trailers_folders, trailers_json)

    music_videos_folders = [s.strip() for s in config['Paths']['Music Videos Folders'].split(',')]
    music_videos_json = config['Interstitials']['Music Videos JSON']
    for music_videos_folder in music_videos_folders:
        nfogen.generate_music_video_data(videos_directory=music_videos_folder)
    search_and_store_video_details(music_videos_folders, music_videos_json)

    other_videos_folders = [s.strip() for s in config['Paths']['Other Videos Folders'].split(',')]
    other_videos_json = config['Interstitials']['Other Videos JSON']
    for other_videos_folder in other_videos_folders:
        nfogen.generate_interstitial_video_data(other_videos_folder)
    search_and_store_video_details(other_videos_folders, other_videos_json)
    
if __name__ == '__main__': 
    main()