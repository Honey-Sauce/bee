import base64
import configparser
import datetime
import ffmpeg #install ffmpeg-python with pip
import json
import os
import random
import requests
import time
import yt_dlp #install yt-dlp with pip

import nfogen

config = configparser.ConfigParser()
config.read('config.ini')

if config['Fresh Content Settings']['Fresh Content INI'] != '':
    fresh_config = configparser.ConfigParser()
    fresh_config.read(config['Fresh Content Settings']['Fresh Content INI'])
else:
    fresh_config = None

api_key = config['Settings']['TMDB Key']

fresh_content_types = []
for category,condition in config['Fresh Content Types'].items():
    if "true" in condition.lower():
        fresh_content_types.append(category.lower())

def get_movies(api_key, endpoint, max_movies, language_code=None):
    url = f"https://api.themoviedb.org/3/movie/{endpoint}"
    # Parameters for the request
    params = {
        'api_key': api_key,
        'page': 1,  # Start with the first page of results
        'sort_by': 'popularity.desc',  # Sort by popularity in descending order
        'include_adult': 'false'  # Exclude adult content
    }

    # Add language code filter if provided
    if language_code:
        params['language'] = language_code

    movies = []
    while len(movies) < max_movies:

        # Make the request to TMDB API
        response = requests.get(url, params=params)
        time.sleep(0.1)
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            
            # Get the list of movies
            results = data.get('results', [])
            #print(json.dumps(results,indent=4))

            language_key = 'original_language'
            for r, result in enumerate(results):
                if language_code:
                    language,country = language_code.split('-')
                    #print(result['title'].ljust(50),flush=True,end='\r')
                    if result['original_language'] == language.strip():
                        details_url = f"https://api.themoviedb.org/3/movie/{result['id']}"

                        params['append_to_response'] = 'videos,release_dates',
                        movie_dict = result
                        
                        endpoint_url = details_url
                        # Make the request to TMDB API
                        endpoint_response = requests.get(endpoint_url, params=params)
                        time.sleep(0.1)
                        
                        if endpoint_response.status_code == 200:
                            # Parse the JSON response and return movie details
                            details = endpoint_response.json()
                            #print(json.dumps(details,indent=4))
                            for k,v in details.items():
                                movie_dict[k] = v
                            #movie_dict[endpoint_key] = details
                            #time.sleep(5)
                        else:
                            # If the request failed, print the error message
                            print(f"Error: {endpoint_response.status_code}, {endpoint_response.text}")  

                        movies.append(movie_dict)
            if len(movies) < max_movies:
                params['page'] += 1
        else:
            # If the request failed, print the error message
            print(f"Error: {response.status_code}, {response.text}")
            return []
    return movies[:max_movies]

def get_youtube_ids(movies, max_duration, max_age_days):
    # Implementation to get YouTube URLs for trailers
    yt_ids = []
    if max_age_days > 0 and max_duration > 0:
        for movie in movies:
            for video in movie['videos']['results']:
                #print(json.dumps(movie,indent=4))
                if 'youtube' in video['site'].lower() and video['type'].lower() in fresh_content_types:
                    published_at = datetime.datetime.strptime(video['published_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    video_age = datetime.datetime.now() - published_at
                    if video_age.days <= max_age_days or not max_age_days:
                        # Extract the duration of the video (assuming it's in seconds)
                        duration_seconds = video.get('duration', 0)
                        
                        # Convert duration to a timedelta object
                        duration_timedelta = datetime.timedelta(seconds=duration_seconds)
                        
                        # Compare the duration with the maximum allowed duration
                        if duration_timedelta.total_seconds() <= max_duration or not max_duration:
                            yt_ids.append((video['key'],movie))
                            #print(video['key'], end='\r')
        print(f"Number of Videos: {len(yt_ids)}".ljust(15), flush=True)
        time.sleep(1)
    return yt_ids
    


def download_youtube_video(youtube_id, existing_fresh_files, directory):
    
    for file in existing_fresh_files:
        if youtube_id in file:
            #print(f"Video with ID {youtube_id} already exists in {directory}",end='\r')
            return None
    print()
    
    # Set options for yt-dlp
    options = {
        'format': 'bestvideo[height<=?1080][vcodec^=avc1]+bestaudio/best[height<=?1080][vcodec^=avc1]+bestaudio/mp4',
        'restrictfilenames': True,
        'writesubtitles': True,
        'allsubtitles': True,
        'merge_output_format': 'mp4',
        'verbose': False,
        'quiet': True,
        'no_warnings': True,
        'progress': True,
        'outtmpl': f"{directory}/%(title)s-[%(id)s].%(ext)s",
    }

    # Initialize yt-dlp downloader
    ydl = yt_dlp.YoutubeDL(options)

    try:
        # Download the video
        yt_url = f'https://www.youtube.com/watch?v={youtube_id}'
        info = ydl.extract_info(yt_url, download=True)
        print(ydl.prepare_filename(info))
        if info:
            ydl_metadata = {}
            ydl_metadata['id'] = info['id']
            ydl_metadata['title'] = info['title']
            ydl_metadata['webpage_url'] = info['webpage_url']
            ydl_metadata['description'] = info['description']
            ydl_metadata['tags'] = info['tags']
            ydl_metadata['uploader'] = info['uploader']
            ydl_metadata['uploader_url'] = info['uploader_url']
            ydl_metadata['upload_date'] = info['upload_date']
            ydl_metadata['release_year'] = info['release_year']
            ydl_metadata['filename'] = ydl.prepare_filename(info)

            print(f"Video '{info['title']}' downloaded successfully!")
            sleep_seconds = random.randint(1000,5000)/1000
            time.sleep(sleep_seconds)
            print(f"Pausing for {sleep_seconds} seconds")
        return ydl_metadata
    except yt_dlp.DownloadError as e:
        print(f"Error downloading video: {e}")
        return None

def get_video_ids_from_playlist(playlist_url, max_age_days=None, max_duration_seconds=None):
    video_ids = []

    ydl = yt_dlp.YoutubeDL({
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'no_warnings': True,
    })

    playlist_info = ydl.extract_info(playlist_url, download=False)

    for entry in playlist_info['entries']:
        try:
            video_id = entry['id']
            if max_age_days or max_duration_seconds:
                criteria_met, reason = meets_criteria(video_id, max_age_days, max_duration_seconds)
                if criteria_met:
                    video_ids.append(video_id)
                    #print(video_id,end='\r')
                else:
                    if reason == "max_age":
                        break
            else:
                video_ids.append(video_id)
                print(video_id,end='\r')
        except:
            pass
    print(f"Videos to Download: {len(video_ids)}")
    return video_ids

def meets_criteria(video_id, max_age_days=None, max_duration_seconds=None):
    ydl = yt_dlp.YoutubeDL({
        'quiet': True,
        'skip_download': True,
        'no_warnings': True,
    })

    # Get video metadata
    video_info = ydl.extract_info(f'https://www.youtube.com/watch?v={video_id}', download=False)

    # Check upload date
    if max_age_days is not None:
        upload_date = datetime.datetime.strptime(video_info.get('upload_date', ''), '%Y%m%d')
        if upload_date:
            days_since_upload = (datetime.datetime.now() - upload_date).days
            if days_since_upload > max_age_days:
                return False, "max_age"

    # Check duration
    if max_duration_seconds is not None:
        duration = video_info.get('duration', 0)
        if duration is not None and duration > max_duration_seconds:
            return False, "max_duration"

    # Check orientation (assume landscape if no orientation data available)
    if 'width' in video_info and 'height' in video_info:
        width = video_info['width']
        height = video_info['height']
        if width < height:
            return False, "orientation"

    return True, None

def delete_old_files(directory_path, max_age_days):
    if max_age_days > 0:
        # Get the current time
        current_time = datetime.datetime.now()

        # List of acceptable video file extensions
        video_extensions = [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".m4v"]

        # Iterate over files in the directory
        dir_files = sorted(os.listdir(directory_path))
        for filename in dir_files:
            filepath = os.path.join(directory_path, filename)
            
            # Check if the path is a file
            if os.path.isfile(filepath):
                # Get the base filename (without extension)
                base_filename, file_extension = os.path.splitext(filename)
                if file_extension in video_extensions:
                    video_filepath = filepath
                    all_associated_files = [video_filepath]
                    for file in dir_files:
                        if base_filename in file:
                            all_associated_files.append(os.path.join(directory_path,file))

                    all_associated_files = list(set(all_associated_files))
                    # Check if the file is older than the maximum age
                    modification_time = datetime.datetime.fromtimestamp(os.path.getmtime(video_filepath))
                    age = (current_time - modification_time).days
                    if age > max_age_days:
                        # Delete the files
                        for to_be_deleted_filepath in all_associated_files:
                            os.remove(to_be_deleted_filepath)
                            print(f"Deleted file: {to_be_deleted_filepath} - {age} days old")

def generate_downloaded_video_data(video,youtube_data,movie_details=None,region='US'):
    # Process each video file
    #print(f"------------------------\n{video}")
    fileinfo = nfogen.initialize_fileinfo(video)
    fileinfo['movie']['tags'] = [] 
    youtube_id, filename = nfogen.extract_youtube_id_from_filename(video)
    
    fileinfo['movie']['source'] = 'YouTube'
    fileinfo['movie']['title'] = youtube_data.get('title')
    fileinfo['movie']['outline'] = youtube_data.get('description')
    fileinfo['movie']['plot'] = youtube_data.get('description')
    if movie_details:
        fileinfo['movie']['plot'] = movie_details['overview']
        for genre in movie_details['genres']:
            fileinfo['movie']['tags'].append(genre['name'].lower().strip())
        for k,v in movie_details.items():
            if k == 'release_dates':
                for release_dict in v['results']:
                    if release_dict['iso_3166_1'].lower() == region.lower():
                        for release_date in release_dict['release_dates']:
                            if release_date['certification'] != '':
                                cert = release_date['certification']
                                fileinfo['movie']['certification'] = f"{region}:{cert} / {region}:Rated {cert}"
                    if release_dict['iso_3166_1'].lower() == 'us':
                        for release_date in release_dict['release_dates']:
                            if release_date['certification'] != '':
                                cert = release_date['certification']
                                fileinfo['movie']['mpaa'] = f"US:{cert} / US:Rated {cert}"
    youtube_upload_date = datetime.datetime.strptime(youtube_data['upload_date'], '%Y%m%d')
    fileinfo['movie']['trailer'] = youtube_data.get('webpage_url')
    fileinfo['movie']['dateadded'] = youtube_upload_date.strftime('%Y-%m-%d %H:%M:%S')
    fileinfo['movie']['aired'] = youtube_upload_date.strftime('%Y-%m-%d')
    fileinfo['movie']['year'] = youtube_upload_date.strftime('%Y')
       
    for youtube_tag in youtube_data.get('tags', []):
        fileinfo['movie']['tags'].append(youtube_tag)

    video_metadata = nfogen.get_video_metadata(video)
    #print(json.dumps(video_metadata,indent=4))
    for streaminfo in video_metadata['streams']:
        codec_type = streaminfo.get('codec_type')
        
        if codec_type == "video":
            fileinfo = nfogen.process_video_stream(fileinfo, streaminfo, youtube_id)
        elif codec_type == "audio":
            fileinfo = nfogen.process_audio_stream(fileinfo, streaminfo)
    

    
    fileinfo['movie']['tags'] = list(set(fileinfo['movie']['tags']))
    
    # Generate and save NFO file
    nfogen.save_nfo_file(video, fileinfo)
    return fileinfo

def fresh_content():
    '''existing_fresh_files = os.listdir(fresh_trailers_directory)
    delete_old_files(fresh_trailers_directory, int(max_age_days))
    endpoints = ['upcoming', 'now_playing']
    for endpoint in endpoints:
        movies = get_movies(api_key, endpoint, round(int(config['Fresh Content Settings']['Fresh Movies'])/2),language_code=f"{language}-{region}")
        youtube_tuples = get_youtube_ids(movies, int(config['Fresh Content Settings']['Max Length'])*60, int(config['Fresh Content Settings']['Max Age Retention']))
        download_ids = []
        existing_fresh_files = os.listdir(fresh_trailers_directory)
        for yt_tuple in youtube_tuples:
            if yt_tuple[0] not in existing_fresh_files:
                metadata = download_youtube_video(yt_tuple[0],existing_fresh_files)
                if metadata:
                    movie_details = yt_tuple[1]
                    video_data = generate_downloaded_video_data(metadata['filename'],metadata,movie_details)
                    time.sleep(1)
            else:
                print(f"Video with ID {yt_tuple[0]} already exists in {fresh_trailers_directory}")
    print(len(movies))'''
    if fresh_config:
        for source_key, source in fresh_config.items():
            if 'Region' in fresh_config[source_key].keys():
                source_region = fresh_config[source_key]['Region']
            else:
                source_region = False
            if 'Language' in fresh_config[source_key]:
                source_language = fresh_config[source_key]['Language']
            else:
                source_language = False
            print('\n',source)
            try:
                # Initialize Options
                download_path = fresh_config[source_key]['Directory']
                if fresh_config.has_option(source_key,'Max Age Retention'):
                    max_age_retention = int(fresh_config.get(source_key,'Max Age Retention'))
                    if max_age_retention != '0' and max_age_retention != '' and max_age_retention != 0:
                        delete_old_files(download_path, max_age_retention)
                else:
                    max_age_retention = None
                if fresh_config.has_option(source_key,'Max Length'):
                    if fresh_config.get(source_key,'Max Length') not in ['','0']:
                        max_length = int(fresh_config.get(source_key,'Max Length'))*60
                    else:
                        max_length = None
                else:
                    max_length = None
                if fresh_config.has_option(source_key,'Max Age Download'):
                    if fresh_config.get(source_key,'Max Age Download') not in ['','0']:
                        max_age_download = int(fresh_config.get(source_key,'Max Age Download'))
                    else:
                        max_age_download = None
                else:
                    max_age_download = None
                if fresh_config[source_key]['Generate NFO'].lower() == "true":
                    generate_nfo = True
                else:
                    generate_nfo = False
                    print("NFO FILE WILL NOT BE GENERATED")
                if fresh_config[source_key]['Is Music Video'].lower() == "true":
                    is_music_video = True
                else:
                    is_music_video = False
                
                # Determine Data Source and initiate download
                if fresh_config[source_key]['Content Type'].lower() == "tmdb":
                    endpoint = fresh_config[source_key]['TMDB Endpoint'].lower()
                    movies = get_movies(api_key, endpoint, int(fresh_config[source_key]['Fresh Movies']),language_code=f"{source_language}-{source_region}")
                    youtube_tuples = get_youtube_ids(movies, max_length, max_age_download)
                    download_ids = []
                    existing_fresh_files = os.listdir(download_path)
                    for yt_tuple in youtube_tuples:
                        if yt_tuple[0] not in existing_fresh_files:
                            metadata = download_youtube_video(yt_tuple[0],existing_fresh_files,directory=download_path)
                            if metadata:
                                movie_details = yt_tuple[1]
                                video_data = generate_downloaded_video_data(metadata['filename'],metadata,movie_details,source_region)
                                time.sleep(1)
                        else:
                            print(f"Video with ID {yt_tuple[0]} already exists in {fresh_trailers_directory}")
                else:
                    try:
                        playlist_url = fresh_config[source_key]['Content Source']
                        existing_playlist_files = os.listdir(download_path)

                        video_id_list = get_video_ids_from_playlist(playlist_url,max_age_download,max_length)
                        existing_fresh_files = os.listdir(download_path)
                        for v, video_id in enumerate(video_id_list):
                            print(f"({v+1}/{len(video_id_list)})",end=": ")
                            metadata = download_youtube_video(video_id,existing_fresh_files,directory=download_path)
                            if generate_nfo is True and metadata:
                                if is_music_video is True:
                                    video_data = nfogen.generate_music_video_data(video=metadata['filename'])
                                elif max_age_retention or not max_length:
                                    video_data = generate_downloaded_video_data(metadata['filename'],metadata,source_region)
                                else:
                                    nfogen.generate_interstitial_video_data(video=metadata['filename'])
                                time.sleep(1)
                    except FileNotFoundError as e:
                        print("ERROR:",e)
            except KeyError as e:
                print(f"ERROR: {e}")
                continue

def playlist_content():                
    if playlist_config:
        for source_key, source in playlist_config.items():
            print('\n',source)
            try:
                download_path = playlist_config[source_key]['Directory']
                playlist_url = playlist_config[source_key]['Content Source']
                existing_playlist_files = os.listdir(download_path)
                if playlist_config[source_key]['Generate NFO'].lower() == "true":
                    generate_nfo = True
                else:
                    generate_nfo = False
                    print("NFO FILE WILL NOT BE GENERATED")
                existing_fresh_files = os.listdir(download_path)
                if playlist_config[source_key]['Is Music Video'].lower() == "true":
                    is_music_video = True
                else:
                    is_music_video = False
                video_id_list = get_video_ids_from_playlist(playlist_url)
                for v, video_id in enumerate(video_id_list):
                    print(f"({v+1}/{len(video_id_list)})",end=": ")
                    metadata = download_youtube_video(video_id,existing_fresh_files,directory=download_path)
                    if generate_nfo is True and metadata:
                        if is_music_video is True:
                            video_data = nfogen.generate_music_video_data(video=metadata['filename'])
                        else:
                            video_data = nfogen.generate_interstitial_video_data(video=metadata['filename'])
                        time.sleep(1)
            except KeyError as e:
                print(f"ERROR: {e}")
                continue                

def main():
    fresh_content()
                
if __name__ == '__main__':
    main()
    #playlist_content()