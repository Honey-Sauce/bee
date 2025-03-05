import configparser
import os
import json
import math
import re
import requests
import time
import urllib.parse
import uuid
import xmltodict
from datetime import datetime
from moviepy.editor import VideoFileClip
from xml.etree import ElementTree as ET

config = configparser.ConfigParser()
config.read('config.ini')

api_key = config['Settings']['TMDB Key']
movie_folder_path = [s.strip() for s in config['Paths']['Movie Folders'].split(',')]
output_json_path = config['Content']['Movie JSON']

# Define valid video file extensions
VALID_VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', ".webm", ".m4v"}

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

def xml_to_dict(element):
    return xmltodict.parse(ET.tostring(element, encoding='utf-8').decode('utf-8'))


def search_and_store_movie_details(movie_folders, output_json_path):
    movies = {}
    movie_details = {}

    # Check if the output JSON file exists
    '''if os.path.exists(output_json_path):
        # Load existing data as a dictionary with unique_id as the key
        with open(output_json_path, 'r') as existing_file:
            existing_data_str = existing_file.read()
            existing_data_dict = json.loads(existing_data_str) if existing_data_str else {}

        # Extract existing movie IDs for comparison
        existing_movie_ids = list(existing_data_dict.keys())
    else:
        existing_data_dict = {}
        existing_movie_ids = []'''
    existing_data_dict = {}
    existing_movie_ids = []
    all_movie_folders = list(movie_folders)
    for folder in movie_folders:
        subfolders = [os.path.join(folder,d) for d in os.listdir(folder) if os.path.isdir(os.path.join(folder,d))]
        all_movie_folders.extend(subfolders)
    total_files = 0
    processed_files = 0
    percentage_done = 0
    for movie_folder in all_movie_folders:
        # Scrape all NFO files in the current folder
        all_files = os.listdir(movie_folder)
        for processed_files, file in enumerate(all_files):
            total_files = len(all_files)
            if file.endswith(".nfo"):
                nfo_file_path = os.path.join(movie_folder, file)
                
                """
                Parse the information from the NFO file and return relevant details.
                """
                try:
                    tree = ET.parse(nfo_file_path)
                    root = tree.getroot()

                    # Extracting file information from <fileinfo>
                    file_info = root.find(".//fileinfo")
                    video_info = file_info.find(".//video")
                    try:
                        audio_info = file_info.find(".//audio")
                        audio_codec = audio_info.find("codec").text
                        audio_channels = int(audio_info.find("channels").text)
                    except AttributeError:
                        audio_info = None
                        audio_codec = ''
                        audio_channels = ''
                    duration_in_seconds = int(video_info.find("durationinseconds").text)
                    
                    # Create a dictionary with file details from the NFO file
                    file_details = {
                        'filepath': os.path.join(os.path.dirname(nfo_file_path),root.find("original_filename").text),
                        'codec': video_info.find("codec").text,
                        'aspect': float(video_info.find("aspect").text),
                        'width': int(video_info.find("width").text),
                        'height': int(video_info.find("height").text),
                        'duration': duration_in_seconds,
                        'duration_ms': duration_in_seconds*1000,
                        'duration_min': round(duration_in_seconds/60),
                        'audio_codec': audio_codec,
                        'channels': audio_channels,
                    }

                except Exception as e:
                    print(f"Error parsing NFO file '{nfo_file_path}': {e}")

                if root:
                    # Extract original filename from NFO
                    original_filename = root.find(".//original_filename").text

                    movie_title = root.find(".//title").text

                    print('------------------------')
                    print(f"File Location: {movie_folder}")
                    print(f"Original Filename: {original_filename}")

                    # Check if the movie is already in the existing data
                    existing_entry = next((entry for entry in existing_data_dict.values() if entry['title'] == movie_title), None)

                    if existing_entry:
                        # Update file locations array
                        existing_entry['files'].append(file_details)
                        percentage_done = ((processed_files+1) / total_files) * 100
                        #print(f"Processed files: {processed_files+1}/{total_files} - {percentage_done:.2f}%", end='\r')
                        continue

                    # Create a dictionary with all movie details
                    unique_id =  root.find(".//id").text
                    movie_entry = {
                        'unique_id': unique_id,
                        'title': movie_title,
                        'files': [file_details],
                    }
                    
                    movie_entry.update(xml_to_dict(root).get("movie", {}))

                    movies[movie_entry['unique_id']] = movie_entry
                    existing_movie_ids.append(unique_id)
                    percentage_done = ((processed_files+1) / total_files) * 100
            #print(f"Processed files: {processed_files+1}/{total_files} - {percentage_done:.2f}%", end='\r')

    # Validate and clean up entries
    for entry_id, entry in existing_data_dict.items():
        # Remove file locations that no longer exist or are not in movie_folders
        entry['files'] = [
            file_detail for file_detail in entry.get('files', [])
            if os.path.exists(file_detail.get('filename', '')) and any(
                movie_folder in file_detail.get('filename', '')
                for movie_folder in movie_folders
            )
        ]

    # Remove entries with empty files arrays
    existing_data_dict = {entry_id: entry for entry_id, entry in existing_data_dict.items() if entry.get('files')}

    # Combine existing data with new data
    combined_data = existing_data_dict.copy()
    combined_data.update(movies)

    # Save combined results to JSON file
    with open(output_json_path, 'w') as movie_file:
        json.dump(combined_data, movie_file, indent=2)

def main():
    search_and_store_movie_details(movie_folder_path, output_json_path)

if __name__ == '__main__':         
    main()