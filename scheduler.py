import argparse
import configparser
import copy
import datetime
import json
import math
import os
import random
import re
import statistics
import time
import traceback
from difflib import SequenceMatcher

config = configparser.ConfigParser()
config.read('config.ini')

show_json_path = config['Content']['Show JSON']
movie_json_path = config['Content']['Movie JSON']
commercials_json_path = config['Interstitials']['Commercials JSON']
music_videos_json_path = config['Interstitials']['Music Videos JSON']



channel_templates_dir = "channel_templates"
channels_dir = "channels"
days_of_week = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']

def load_json_file(file_path):
    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
            return data
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON in '{file_path}': {e}")
        return None

# Load Media Libraries
movie_library = load_json_file(movie_json_path)
show_library = load_json_file(show_json_path)
music_videos_library = load_json_file(music_videos_json_path)

def from_filter(data, filter_list, filter_type, include=True):
    
    matching_data = {}
    forbidden_data = {}
    
    #print(filter_list, filter_type, len(filter_list))
    if len(filter_list) > 0 and filter_list[0] != '':
        for filter_item in filter_list:
            if filter_item != '':
                for e in data.keys():
                    try:
                        if include is True:
                            if filter_item in data[e].get(filter_type):
                                #print(f"{data[e].get('title')}: {filter_item} - Allowed")
                                matching_data[e] = data[e]
                        else:
                            if filter_item not in data[e].get(filter_type):
                                matching_data[e] = data[e]
                            else:
                                #print(f"{data[e].get('title')}: {filter_item} - Forbidden")
                                pass
                    except TypeError:
                        pass
        return matching_data
    else:
        return data

def from_ratings(data, ratings_list, include=True, movies=False):
    #data = copy.deepcopy(data)
    matching_data = {}
    #print(ratings_list)
    for e in data.keys():
        try:
            if movies==True:
                show_certification = data[e].get('certification').split('/')[0].split(':')[-1].strip()
            else:
                show_certification = data[e].get('certification').split(':')[-1].strip()
            
            if include == True:
                if show_certification in ratings_list:
                    matching_data[e] = data[e]
            else:
                if show_certification not in ratings_list:
                    matching_data[e] = data[e]
        except:
            pass
    return matching_data

def from_decade(data, decades_list, include=True):
    #data = copy.deepcopy(data)
    matching_data = {}
    for decade in decades_list:
        for e in data.keys():
            try:
                if include is True:
                    if decade[:3] in data[e].get('year'):
                        matching_data[e] = data[e]
                else:
                    if decade[:3] not in data[e].get('year'):
                        matching_data[e] = data[e]
            except TypeError:
                pass
    return matching_data

def get_shows_filter(shows_details, key, minimum_shows=1):
    all_keys = []
    used_keys = []
    for e in shows_details.keys():
        if shows_details[e].get(key) is not None:
            if isinstance(shows_details[e].get(key), str):
                all_keys.append(shows_details[e].get(key))
            elif isinstance(shows_details[e].get(key), list):
                for each_key in shows_details[e].get(key):
                    all_keys.append(each_key)

    all_keys = list(set(all_keys))
    saved_keys = all_keys
    matching_data = {}
    # Randomly select one key from the list
    while len(matching_data) < max(1, round(minimum_shows/10)):
        selected_key = random.choice(all_keys) if all_keys else None
        used_keys.append(selected_key)
        all_keys.remove(selected_key)
        if len(all_keys) < 1:
            all_keys = saved_keys
            all_keys = [value for value in all_keys if value not in used_keys]
        shows_data = {}
        matching_data = {}
        for e in shows_details.keys():
            try:
                if selected_key in shows_details[e].get(key):
                    #print(shows_details[e].get('title'))
                    matching_data[e]= shows_details[e]
            except TypeError:
                pass
    print(f"\n{selected_key}")
    for e in matching_data:
        shows_data[e] = shows_details[e]
        print(shows_details[e].get('title'))

    while len(shows_data) < minimum_shows:
        # Randomly select one key from the list
        new_selected_key = selected_key
        while new_selected_key == selected_key:
            new_selected_key = random.choice(all_keys) if all_keys else None
            
        selected_key = new_selected_key
        used_keys.append(selected_key)
        all_keys.remove(selected_key)
        matching_data = {}
        # Randomly select one key from the list
        while len(matching_data) < max(1, round(minimum_shows/10)):
            selected_key = random.choice(all_keys) if all_keys else None
            used_keys.append(selected_key)
            all_keys.remove(selected_key)
            if len(all_keys) < 1:
                all_keys = saved_keys
                all_keys = [value for value in all_keys if value not in used_keys]
            matching_data = {}
            for e in shows_details.keys():
                try:
                    if selected_key in shows_details[e].get(key):
                        #print(shows_details[e].get('title'))
                        matching_data[e]= shows_details[e]
                except TypeError:
                    pass
        print(f"\n{selected_key}")
        for e in matching_data:
            shows_data[e] = shows_details[e]
            print(shows_details[e].get('title'))

    #print(len(shows_data))
    return shows_data

def get_filtered_show(shows_data, block_data, starting_time, ending_time, selected_shows,  selected_show_key, selected_show, channel_type):
    filtered_shows = shows_data
    keys_to_remove = []

    episode_mode = 'sequential'
    while selected_show_key in selected_shows or selected_show_key is None:
        #print(list(filtered_shows.keys()))
        try:
            selected_show_key = random.choice(list(filtered_shows.keys()))
            selected_show = filtered_shows[selected_show_key]
            del filtered_shows[selected_show_key]
        except IndexError:
            if len(selected_shows) < 1:
                episode_mode = 'random'
                break
            selected_show_key = random.choice(list(selected_shows.keys()))
            episode_mode = 'random'
            selected_show = selected_shows[selected_show_key]
        if len(selected_show['files']) < 1:
            selected_show_key = None
        elif all(x in selected_shows for x in filtered_shows.keys()):
            episode_mode = 'random'
            break
    selected_shows[selected_show_key] = selected_show
    
    print(f"SELECTED SHOW: {selected_show['title']}")
    print(f"Remaining Shows: {len(filtered_shows)}")
    # Calculate ending time based on show runtime
    if selected_show:
        all_durations = []
        for file_key in selected_show['files'].keys():
            for episode_details in selected_show['files'][file_key]['episode_details']:
                all_durations.append(round(int(int(episode_details['fileinfo']['streamdetails']['video']['durationinseconds'])/60)))
        runtime_minutes = int(statistics.median(all_durations))
        ending_time = starting_time + datetime.timedelta(minutes=runtime_minutes)
        #ending_time = ending_time.strftime("%H:%M:%S")
    else:
        ending_time = None
    # Add show entry to the schedule
    print(f"SHOW DURATION: {runtime_minutes}")
    return selected_show['id'], selected_show['title'], runtime_minutes, ending_time, episode_mode

def all_movies_durations(movies_data):
    movies_durations_seconds = []
    for m, movie in movies_data.items():
        durationinseconds = int(movie['fileinfo']['streamdetails']['video']['durationinseconds'])
        movies_durations_seconds.append(durationinseconds)
    rounded_durations_minutes = []
    durations_minutes = []
    for duration_seconds in movies_durations_seconds:
        duration_minutes = int(duration_seconds / 60)
        durations_minutes.append(duration_minutes)
        rounded_minutes = math.ceil(duration_minutes / 15) * 15
        rounded_durations_minutes.append(round(rounded_minutes))
    return sorted(durations_minutes)

def find_ranges(movies_durations_all, max_distance, min_value, max_value, min_override=None):
    # Sort the list of movie durations
    sorted_durations = sorted(movies_durations_all)
    
    # Initialize list to store selected ranges
    selected_ranges = []
    
    # Initialize list to store all ranges and their movie counts
    all_ranges = []
    
    # Initialize remaining time to be filled
    remaining_time = max_value
    
    # Iterate over possible start times within remaining time
    for min_duration in range(min_value, max_value + 1, max_distance):
        max_duration = min(min_duration + max_distance, max_value)
        
        if min_duration >= max_duration:
            break
        
        # Count movies within the current range
        count = sum(min_duration <= d <= max_duration for d in sorted_durations)
        
        if count > 0:
            # Add range and movie count to all_ranges
            all_ranges.append((min_duration, max_duration, count))
    
    # Sort all_ranges by movie count in descending order
    all_ranges.sort(key=lambda x: x[2], reverse=True)
    
    # Drop the lowest 25% of ranges
    '''cutoff_index = len(all_ranges) // 4
    all_ranges = all_ranges[cutoff_index:]'''
    
    # Keep selecting ranges until all time is filled
    while remaining_time > min(t[1] for t in all_ranges):
        # Initialize variables for optimal range within current remaining time
        #print(remaining_time)
        possible_ranges = []
        if len(selected_ranges) < 1:
            for min_duration, max_duration, count in all_ranges:
                if max_duration <= (remaining_time / 2) or (remaining_time - max_distance) <= max_duration <= remaining_time:
                    possible_ranges.append((min_duration,max_duration))
            #print(possible_ranges)
        else:
            for min_duration, max_duration, count in all_ranges:
                if (remaining_time - max_distance) <= max_duration <= remaining_time:
                    if min_override != None:
                        possible_ranges.append((min_override,max_duration))
                    else:
                        possible_ranges.append((min_duration,max_duration))
            #print(possible_ranges)
        if len(possible_ranges) > 0:
            random_range = random.choice(possible_ranges)
            selected_ranges.append(random_range)
            if min_override != None:
                random_range = (min_override,random_range[1])
            # Update remaining time
            print(random_range)
            remaining_time -= random_range[1]
        else:
            remaining_time = 0
    return selected_ranges
    
def generate_channel_schedule(channel_template_path, shows_details_path, movies_details_path, minimum_shows=50):
    # Load data from JSON files
    channel_template = load_json_file(channel_template_path)
    #print(json.dumps(channel_template, indent=2))
    shows_details = load_json_file(shows_details_path)
    #print(json.dumps(shows_details, indent=2))
    movies_details = load_json_file(movies_details_path)
    #print(json.dumps(movies_details, indent=2))

    if channel_template is None or shows_details is None or movies_details is None:
        # Handle the case when loading fails
        return None

    # Select channel type and randomly
    channel_type = 'default'
    #channel_type = random.choice(['default', 'studio', 'genre', 'decade'])
    
    ## LOOP BELOW FOR EACH DAY OF WEEK, DEPENDING ON COMPLEXITY
    
    # Initialize the schedule dictionary
    channel_schedule = {}
    selected_shows = {}
    
    for day_index, day_of_week in enumerate(days_of_week):
        #Loop over each of the days of the week
        print("-----------------------------------------")
        print(day_of_week.upper())
        channel_schedule[day_of_week] = {}

        ending_time = None
        selected_show_key = None
        selected_show = None
        day = 0
        remaining_time = None
        # Iterate over the blocks in the channel template
        for block_name, block_data in channel_template.items():
            print("-----------------------------------------")
            print(f"{day_of_week.upper()} {block_name.upper()}")

            # Extract block start and end times and complexity
            start_time = block_data.get('start_time')
            end_time = block_data.get('end_time')
            #print(f"{start_time} - {end_time}\n")
            block_complexity = block_data['complexity']
            block_options = block_data['options']

            # Convert start_time and end_time to datetime objects
            try:
                start_time = datetime.datetime.strptime(start_time, "%H:%M")
            except ValueError:
                start_time = datetime.datetime.strptime(start_time, "%H:%M:%S")
            try:
                end_time = datetime.datetime.strptime(end_time, "%H:%M")
            except ValueError:
                end_time = datetime.datetime.strptime(end_time, "%H:%M:%S")
            if day == 1:
                start_time += datetime.timedelta(days=1)
                end_time += datetime.timedelta(days=1)

            time_difference = end_time - start_time
            if time_difference.total_seconds() < 0:
                end_time += datetime.timedelta(days=1)
                time_difference = end_time - start_time
                day=1

            print(f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}\n")
            
            # Convert the time difference to minutes and round it
            time_slot_duration = round(time_difference.total_seconds() / 60)

            # Initialize the list of starting times
            starting_times = []

            # Iterate over half-hour intervals within the block
            current_time = start_time
            interval_minutes = 30
            interval = datetime.timedelta(minutes=interval_minutes)

            '''if current_time > end_time:
                end_time += datetime.timedelta(days=1)'''

            while current_time < end_time:
                starting_times.append(current_time)
                current_time += interval

            # Copy schedules based on complexity settings
            if block_data['complexity'] == 'everyday' and day_of_week != days_of_week[0]:
                # Use the same schedule every day of the week
                print(f"Block set to {block_data['complexity']} type, copying {days_of_week[0]} data")
                for schedule_entry in channel_schedule[days_of_week[0]].keys():
                    entry_start_time = datetime.datetime.strptime(schedule_entry, "%H:%M:%S")
                    #if int(start_time.strftime('%j')) > 1:
                    if entry_start_time < start_time:
                        entry_start_time += datetime.timedelta(days=1)
                    if start_time <= entry_start_time < end_time:
                        channel_schedule[day_of_week][schedule_entry] = copy.deepcopy(channel_schedule[days_of_week[0]][schedule_entry])
                continue
            elif block_data['complexity'] == 'weekday' and day_of_week not in [days_of_week[0], days_of_week[5], days_of_week[6]]:
                # Use the same schedule every weekday, and different schedules for Saturday and Sunday
                print(f"Block set to {block_data['complexity']} type, copying {days_of_week[0]} data")
                for schedule_entry in channel_schedule[days_of_week[0]].keys():
                    entry_start_time = datetime.datetime.strptime(schedule_entry, "%H:%M:%S")
                    #if int(start_time.strftime('%j')) > 1:
                    if entry_start_time < start_time:
                        entry_start_time += datetime.timedelta(days=1)
                    if start_time <= entry_start_time < end_time:
                        channel_schedule[day_of_week][schedule_entry] = copy.deepcopy(channel_schedule[days_of_week[0]][schedule_entry])
                continue
            elif block_data['complexity'] == 'even_odd' and day_of_week in ['Wednesday','Friday','Sunday']:
                # Alternate between two schedules each day
                print(f"Block set to {block_data['complexity']} type, copying {days_of_week[0]} data")
                for schedule_entry in channel_schedule[days_of_week[0]].keys():
                    entry_start_time = datetime.datetime.strptime(schedule_entry, "%H:%M:%S")
                    #if int(start_time.strftime('%j')) > 1:
                    if entry_start_time < start_time:
                        entry_start_time += datetime.timedelta(days=1)
                    if start_time <= entry_start_time < end_time:
                        print('.',end=" ")
                        channel_schedule[day_of_week][schedule_entry] = copy.deepcopy(channel_schedule[days_of_week[0]][schedule_entry])
                print()
                continue
            elif block_data['complexity'] == 'even_odd' and day_of_week in ['Thursday','Saturday']:
                print(f"Block set to {block_data['complexity']} type, copying {days_of_week[1]} data")
                for schedule_entry in channel_schedule[days_of_week[1]].keys():
                    entry_start_time = datetime.datetime.strptime(schedule_entry, "%H:%M:%S")
                    #if int(start_time.strftime('%j')) > 1:
                    if entry_start_time < start_time:
                        entry_start_time += datetime.timedelta(days=1)
                    if start_time <= entry_start_time < end_time:
                        print('.',end=" ")
                        channel_schedule[day_of_week][schedule_entry] = copy.deepcopy(channel_schedule[days_of_week[1]][schedule_entry])
                print()
                continue

            # Initialize data for shows and movies
            shows_data = copy.deepcopy(shows_details)
            movies_data = copy.deepcopy(movies_details)
            
            # genre loop filter here
            if block_data['allowed_genres'] != '':
                if ',' in block_data['allowed_genres']:
                    allowed_genres = [item.strip() for item in block_data['allowed_genres'].split(',')]
                else:
                    allowed_genres = [block_data['allowed_genres']]
                shows_data = from_filter(shows_data, allowed_genres, 'genre')
                movies_data = from_filter(movies_data, allowed_genres, 'genre')    
            if block_data['forbidden_genres'] != '':
                if ',' in block_data['forbidden_genres']:
                    forbidden_genres = [item.strip() for item in block_data['forbidden_genres'].split(',')]
                else:
                    forbidden_genres = [block_data['forbidden_genres']]
                shows_data = from_filter(shows_data, forbidden_genres, 'genre', include=False)
                movies_data = from_filter(movies_data, forbidden_genres, 'genre', include=False)
            
            if block_data['forbidden_ratings'] != '':
                if ',' in block_data['forbidden_ratings']:
                    forbidden_ratings = [item.strip() for item in block_data['forbidden_ratings'].split(',')]
                else:
                    forbidden_ratings = [block_data['forbidden_ratings']]
                shows_data = from_ratings(shows_data, forbidden_ratings, include=False)
                movies_data = from_ratings(movies_data, forbidden_ratings, include=False, movies=True)
            elif block_data['allowed_ratings'] != '':
                if ',' in block_data['allowed_ratings']:
                    allowed_ratings = [item.strip() for item in block_data['allowed_ratings'].split(',')]
                else:
                    allowed_ratings = [block_data['allowed_ratings']]
                shows_data = from_ratings(shows_data, allowed_ratings)      
                movies_data = from_ratings(movies_data, allowed_ratings, movies=True)

            if block_data['allowed_decades'] != '':
                if ',' in block_data['allowed_decades']:
                    allowed_decades = [item.strip() for item in block_data['allowed_decades'].split(',')]
                else:
                    allowed_decades = [block_data['allowed_decades']]
                shows_data = from_decade(shows_data, allowed_decades)
                movies_data = from_decade(movies_data, allowed_decades)

            if block_data['forbidden_decades'] != '':
                if ',' in block_data['forbidden_decades']:
                    forbidden_decades = [item.strip() for item in block_data['forbidden_decades'].split(',')]
                else:
                    forbidden_decades = [block_data['forbidden_decades']]
                shows_data = from_decade(shows_data, forbidden_decades, include=False)
                movies_data = from_decade(movies_data, forbidden_decades, include=False)

            # Apply filtering based on channel type
            if channel_type == 'studio':
                # Combine all studios from all shows into a list, eliminating duplicates
                initial_shows_data = get_shows_filter(shows_data, 'studio')

                initial_movies_data = random.choice([entry for entry in movies_details if movies_details[entry].get('studio') is not None]) if movies_details else None

            elif channel_type == 'genre':
                initial_shows_data = get_shows_filter(shows_data, 'genre')
                
                all_genres = []
                for e in movies_details.keys():
                    entry_genre = movies_details[e].get('genre')
                    if movies_details[e].get('genre') is not None:
                        if isinstance(entry_genre, str):
                            all_genres.append(entry_genre)
                        elif isinstance(entry_genre, list):
                            for each_genre in entry_genre:
                                all_genres.append(each_genre)
                movies_genre = random.choice(list(set(all_genres)))   
                initial_movies_data = movies_details
            elif channel_type == 'decade':
                # Get a list of decades spanned by shows and movies
                all_decades_shows = [shows_data[entry].get('premiered')[:3] + '0s' for entry in shows_data if shows_data[entry].get('premiered')] if shows_data else []
                
                all_decades_movies = [movies_details[entry].get('year')[:3] + '0s' for entry in movies_details if movies_details[entry].get('year')] if movies_details else []
                
                # Combine the lists and remove duplicates
                all_decades = list(set(all_decades_shows + all_decades_movies))
                all_decades.sort()
                #print(all_decades)
                initial_shows_data = {}
                initial_movies_data = {}
                # Select one decade randomly
                selected_decades = []
                loop=0
                adjustment = 1
                while len(initial_shows_data) < minimum_shows or len(initial_movies_data) < minimum_shows and loop <= 10:
                    print(loop)
                    if loop == 0:
                        selected_decade = random.choice(all_decades) if all_decades else None
                        decade_position = all_decades.index(selected_decade)
                        selected_decades.append(selected_decade)
                        
                        if selected_decade == all_decades[-1]:
                            adjustment = -1
                    
                    while selected_decade in selected_decades:
                        print(selected_decade)
                        try:
                            all_decades.remove(selected_decade)
                            selected_decade = all_decades[decade_position]
                            #decade_position = all_decades.index(selected_decade)
                            
                        except IndexError:
                            print("INDEXERROR")
                            print(all_decades)
                            selected_decade = all_decades[-1]
                            decade_position = all_decades.index(selected_decade)
                            
                        if loop >= 1:
                            print(f"Total Shows: {len(initial_shows_data)}")
                            print(f"Total Movies: {len(initial_movies_data)}")
                        loop+=1
             
         
                    print(selected_decade)
                    selected_decades.append(selected_decade)
                    #all_decades.remove(selected_decade)
                    decade_position = all_decades.index(selected_decade)
                    
                    
                    # Filter shows and movies based on the selected decade
                    matching_data = [entry for entry in shows_details if shows_details[entry].get('premiered')[:3] + '0s' == selected_decade] if shows_details else None
                    
                    for e in matching_data:
                        initial_shows_data[e] = shows_details[e]
                        #print(shows_data[e].get('title'))
                    
                    
                    matching_data = [entry for entry in movies_details if movies_details[entry].get('year')[:3]+'0s' == selected_decade] if movies_details else None

                    for e in matching_data:
                        initial_movies_data[e] = movies_details[e]
                    loop+=1
                print(selected_decades)        
            else:
                initial_shows_data = copy.deepcopy(shows_data)
                initial_movies_data = copy.deepcopy(movies_details)
            print(f"Total Shows: {len(initial_shows_data)}")
            print(f"Total Movies: {len(initial_movies_data)}")

            #print(f"SHOWS: {len(shows_data)}")
            movies_data = copy.deepcopy(initial_movies_data)
        
            #iterate over starting times at set interval (default 30 minutes)
            for starting_time in starting_times:
                
                if ending_time is not None:
                    #print(ending_time)
                    if ending_time >= starting_time:
                        continue

                    #continue
                print(f"\nSTARTING TIME IN BLOCK: {starting_time.strftime('%H:%M:%S')}")
                # Determine whether to schedule movies, shows, or both
                options = block_data.get('options')

                # Check if there is at least 45 minutes between the current time and the end time
                enough_time_for_movie = (end_time - starting_time) >= datetime.timedelta(minutes=45)
                enough_time_for_show = (end_time - starting_time) >= datetime.timedelta(minutes=15)
                print(f"TIME REMAINING: {end_time - starting_time}")
                if options == "both" and enough_time_for_movie == False and enough_time_for_show == True:
                    options_action = 'shows'
                    remaining_time = int((end_time - starting_time).total_seconds()/60)
                    print("SETTING options TO shows")
                elif options == 'shows':
                    options_action = 'shows'
                    remaining_time = False
                elif options == 'movies':
                    options_action = 'movies'
                elif options == 'random':
                    options_action = 'random'
                elif options == 'both':
                    options_action = 'both'

                if options_action == 'movies':
                    # Set block for random movie selection
                    movies_durations_all = all_movies_durations(movies_data)
                    movies_durations_minutes = sorted(list(movies_durations_all))
                    #print(movies_durations_minutes)
                    min_duration = 15
                    max_duration = int((end_time-starting_time).total_seconds()/60)
                    selected_ranges = find_ranges(movies_durations_all,int(interval_minutes/2),min_duration,max_duration)
                    print(selected_ranges)
                    for selected_range in selected_ranges:
                        print(f"STARTING TIME: {starting_time.strftime('%H:%M:%S')}")
                        min_minutes, max_minutes = selected_range
                        kevin_bacon_mode_status = 'false' if random.random() < 0.5 else random.choice(['year', 'actor', 'director', 'writer', 'producer', 'studio', 'tag'])
                        duration_span = [min_minutes, max_minutes]
                        print(f"DURATION RANGE: {min_minutes} - {max_minutes}")
                        ending_time = starting_time + datetime.timedelta(minutes=duration_span[1])
                        #ending_time = ending_time.strftime("%H:%M:%S")
                        # Add movie entry to the schedule
                        print(f"MOVIE: {duration_span[0]} - {duration_span[1]} minutes")
                        channel_schedule[day_of_week][starting_time.strftime("%H:%M:%S")] = { 
                            'title': "Random Movie",
                            'time_mode': "preempt", # Strict, Variable, Preempt
                            'start_time': starting_time.strftime("%H:%M:%S"),
                            'type': {
                                'random_movie': {
                                    'duration_minutes': duration_span,
                                    'kevin_bacon_mode': kevin_bacon_mode_status,
                                    'ratings': {
                                        'allowed': block_data.get('allowed_ratings').split(', ') if 'allowed_ratings' in block_data else None,
                                        'forbidden': block_data.get('forbidden_ratings').split(', ') if 'forbidden_ratings' in block_data else None,
                                        },
                                    'decades': {
                                        'allowed': block_data.get('allowed_decades').split(', ') if 'allowed_decades' in block_data else None,
                                        'forbidden': block_data.get('forbidden_decades').split(', ') if 'forbidden_decades' in block_data else None,
                                        },
                                    'actor': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'director': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'writer': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'producer': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'genre': {
                                        'allowed': block_data.get('allowed_genres').split(', ') if 'allowed_genres' in block_data else None,
                                        'forbidden': block_data.get('forbidden_genres').split(', ') if 'forbidden_genres' in block_data else None,
                                        },

                                    'studio': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'tag': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                }
                            }
                        }
                        starting_time = ending_time

                elif options_action == 'shows':
                    print('...')
                    # Select TV Show for programming block
                    show_id, show_title, show_duration, ending_time, episode_mode = get_filtered_show(shows_data, block_data, starting_time, ending_time, selected_shows, selected_show_key, selected_show, channel_type)
                    ending_timestamp = ending_time
                    if starting_times[0] > ending_timestamp:
                        ending_timestamp += datetime.timedelta(days=1)
                    if int(show_duration) != 0:
                        entry_duration = int(show_duration)
                    else:
                        entry_duration = time_slot_duration
                    if remaining_time == False:
                        remaining_time = interval_minutes - entry_duration
                    #print(ending_timestamp)
                    #print(end_time)
                    while ending_timestamp > end_time or (starting_time == starting_times[-1] and remaining_time < 0):
                        # If the show length will bleed into the next block, select a new show
                        show_id, show_title, show_duration, ending_time, episode_mode = get_filtered_show(shows_data, block_data, starting_time, ending_time, selected_shows, selected_show_key, selected_show, channel_type)
                        ending_timestamp = ending_time
                        if starting_times[0] > ending_timestamp:
                            ending_timestamp += datetime.timedelta(days=1)
                        if int(show_duration) != 0:
                            entry_duration = int(show_duration)
                        else:
                            entry_duration = time_slot_duration
                        remaining_time = interval_minutes - entry_duration
                    #print(f"{time_slot_duration} - {entry_duration}")

                    channel_schedule[day_of_week][starting_time.strftime("%H:%M:%S")] = {
                        'title': show_title, # series name or 'random'
                        'time_mode': 'preempt', # Strict, Variable, Preempt
                        'start_time': starting_time.strftime("%H:%M:%S"),
                        'type': { 
                            "series": { # series, movie
                                'id': show_id, # series name or 'random'
                                'duration_minutes': int(show_duration),
                                'episode_mode': episode_mode, # Sequential, Random, Rerun
                                'on_series_end': 'reschedule_similar', # Repeat, Reschedule (Allow All, Similar, Same Rating, From Template)
                            }
                        }
                    }

                    print(f"TIME SLOT REMAINING: {remaining_time}")
                    old_starting_time = starting_time
                    while remaining_time > entry_duration:
                        print(f"ENDING TIME: {ending_time}")
                        ending_timestamp = ending_time
                        minutes_advanced = (5 - ending_timestamp.minute % 5) % 5
                        starting_time = ending_timestamp + datetime.timedelta(minutes=minutes_advanced)
                        ending_time = starting_time + datetime.timedelta(minutes=int(show_duration))

                        print(f"\nSTARTING TIME: {starting_time.strftime('%H:%M:%S')}")

                        channel_schedule[day_of_week][starting_time.strftime("%H:%M:%S")] = copy.deepcopy(channel_schedule[day_of_week][old_starting_time.strftime("%H:%M:%S")])
                        
                        channel_schedule[day_of_week][starting_time.strftime("%H:%M:%S")]['start_time'] = starting_time.strftime("%H:%M:%S")
                        
                        entry_duration = ending_time - old_starting_time
                        
                        if entry_duration.total_seconds() < 0:
                            entry_duration = datetime.timedelta(days=1) + entry_duration
                        #ending_time = ending_time.strftime("%H:%M:%S")
                        entry_duration = entry_duration.total_seconds()/60
                        remaining_time = remaining_time - int(show_duration) - minutes_advanced
                        print(f"TIME SLOT REMAINING: {remaining_time}")
                elif options_action == "both":
                    # Generate block for both movies and shows
                    # Set block for random movie selection
                    movies_durations_all = all_movies_durations(movies_data)
                    movies_durations_minutes = sorted(list(movies_durations_all))
                    #print(movies_durations_minutes)
                    min_duration = 45
                    max_duration = int((end_time-starting_time).total_seconds()/60)
                    try:
                        selected_ranges = find_ranges(movies_durations_all,45,min_duration,max_duration,min_override=min_duration)
                    except:
                        if min_duration < max_duration:
                            selected_ranges = [(min_duration,max_duration)]
                    #print(f"\nSELECTED RANGES: {selected_ranges}")
                    for selected_range in selected_ranges:
                        #print(f"STARTING TIME: {starting_time.strftime('%H:%M:%S')}")
                        max_duration = int((end_time-starting_time).total_seconds()/60)
                        min_minutes, max_minutes = selected_range
                        min_minutes = min_duration
                        max_minutes = min(max_minutes,max_duration)
                        if min_minutes >= max_minutes:
                            break
                        duration_span = [min_minutes, max_minutes]
                        ending_time = starting_time + datetime.timedelta(minutes=duration_span[0])
                        
                        print(f"MOVIE DURATION RANGE: {min_minutes} - {max_minutes} minutes")
                        print(f"MOVIE ENDING TIME: {ending_time.strftime('%H:%M:%S')} - {(ending_time + datetime.timedelta(minutes=duration_span[1]-duration_span[0])).strftime('%H:%M:%S')}")
                        #ending_time = ending_time.strftime("%H:%M:%S")
                        kevin_bacon_mode_status = 'false' if random.random() < 0.5 else random.choice(['year', 'actor', 'director', 'writer', 'producer', 'studio', 'tag'])
                        # Add movie entry to the schedule
                        channel_schedule[day_of_week][starting_time.strftime("%H:%M:%S")] = { 
                            'title': "Random Movie",
                            'time_mode': "preempt", # Strict, Variable, Preempt
                            'start_time': starting_time.strftime("%H:%M:%S"),
                            'type': {
                                'random_movie': {
                                    'duration_minutes': duration_span,
                                    'kevin_bacon_mode': kevin_bacon_mode_status,
                                    'ratings': {
                                        'allowed': block_data.get('allowed_ratings').split(', ') if 'allowed_ratings' in block_data else None,
                                        'forbidden': block_data.get('forbidden_ratings').split(', ') if 'forbidden_ratings' in block_data else None,
                                        },
                                    'decades': {
                                        'allowed': block_data.get('allowed_decades').split(', ') if 'allowed_decades' in block_data else None,
                                        'forbidden': block_data.get('forbidden_decades').split(', ') if 'forbidden_decades' in block_data else None,
                                        },
                                    'actor': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'director': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'writer': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'producer': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'genre': {
                                        'allowed': block_data.get('allowed_genres').split(', ') if 'allowed_genres' in block_data else None,
                                        'forbidden': block_data.get('forbidden_genres').split(', ') if 'forbidden_genres' in block_data else None,
                                        },

                                    'studio': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'tag': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                }
                            }
                        }
                        
                        # Fill in with shows until max minutes
                        minutes_advanced = (30 - ending_time.minute % 30) % 30
                        ending_time_movie = ending_time + datetime.timedelta(minutes=duration_span[1]-duration_span[0])
                        starting_time = ending_time + datetime.timedelta(minutes=minutes_advanced)
                        
                        print(f"SHOW STARTING TIME: {starting_time.strftime('%H:%M:%S')}")
                        
                        ending_timestamp = starting_time + datetime.timedelta(minutes=min_minutes)
                        while starting_time < ending_time_movie:
                        # Select TV Show for programming block
                            show_id, show_title, show_duration, ending_time, episode_mode = get_filtered_show(shows_data, block_data, starting_time, ending_time, selected_shows, selected_show_key, selected_show, channel_type)
                            ending_timestamp = ending_time
                            if starting_times[0] > ending_timestamp:
                                ending_timestamp += datetime.timedelta(days=1)
                            if int(show_duration) != 0:
                                entry_duration = int(show_duration)
                            else:
                                entry_duration = time_slot_duration
                            remaining_time = max_minutes - min_minutes
                            #print(ending_timestamp)
                            #print(end_time)
                            zed = 0
                            while ending_timestamp > starting_time + datetime.timedelta(minutes=max_minutes-min_minutes) or (starting_time == starting_times[-1] and (remaining_time < 0) or ending_timestamp > end_time) and zed <= 50:
                                # If the show length will bleed into the next block, select a new show
                                show_id, show_title, show_duration, ending_time, episode_mode = get_filtered_show(shows_data, block_data, starting_time, ending_time, selected_shows, selected_show_key, selected_show, channel_type)
                                ending_timestamp = ending_time
                                if starting_times[0] > ending_timestamp:
                                    ending_timestamp += datetime.timedelta(days=1)
                                if int(show_duration) != 0:
                                    entry_duration = int(show_duration)
                                else:
                                    entry_duration = time_slot_duration
                                remaining_time = interval_minutes - entry_duration
                                print(f"Remaining Time: {remaining_time} Minutes.")
                                zed += 1
                            #print(f"{time_slot_duration} - {entry_duration}")

                            channel_schedule[day_of_week][starting_time.strftime("%H:%M:%S")] = {
                                'title': show_title, # series name or 'random'
                                'time_mode': 'preempt', # Strict, Variable, Preempt
                                'start_time': starting_time.strftime("%H:%M:%S"),
                                'type': { 
                                    "series": { # series, movie
                                        'id': show_id, # series name or 'random'
                                        'duration_minutes': int(show_duration),
                                        'episode_mode': episode_mode, # Sequential, Random, Rerun
                                        'on_series_end': 'reschedule_similar', # Repeat, Reschedule (Allow All, Similar, Same Rating, From Template)
                                    }
                                }
                            }
                            minutes_advanced = (15 - ending_timestamp.minute % 15) % 15
                            starting_time = ending_timestamp + datetime.timedelta(minutes=minutes_advanced)
                            print(f"SHOW ENDING TIME: {ending_time.strftime('%H:%M:%S')}\n")
                            print(f"NEW STARTING TIME: {starting_time.strftime('%H:%M:%S')}")
                elif options_action == "random":
                    # Generate block for both movies and random shows
                    # Set block for random movie selection
                    movies_durations_all = all_movies_durations(movies_data)
                    movies_durations_minutes = sorted(list(movies_durations_all))
                    #print(movies_durations_minutes)
                    min_duration = 45
                    max_duration = int((end_time-starting_time).total_seconds()/60)
                    try:
                        selected_ranges = find_ranges(movies_durations_all,45,min_duration,max_duration,min_override=min_duration)
                    except:
                        if min_duration < max_duration:
                            selected_ranges = [(min_duration,max_duration)]
                    #print(f"\nSELECTED RANGES: {selected_ranges}")
                    for selected_range in selected_ranges:
                        #print(f"STARTING TIME: {starting_time.strftime('%H:%M:%S')}")
                        max_duration = int((end_time-starting_time).total_seconds()/60)
                        min_minutes, max_minutes = selected_range
                        min_minutes = min_duration
                        max_minutes = min(max_minutes,max_duration)
                        if min_minutes >= max_minutes:
                            break
                        duration_span = [min_minutes, max_minutes]
                        ending_time = starting_time + datetime.timedelta(minutes=duration_span[0])
                        
                        print(f"MOVIE DURATION RANGE: {min_minutes} - {max_minutes} minutes")
                        print(f"MOVIE ENDING TIME: {ending_time.strftime('%H:%M:%S')} - {(ending_time + datetime.timedelta(minutes=duration_span[1]-duration_span[0])).strftime('%H:%M:%S')}")
                        #ending_time = ending_time.strftime("%H:%M:%S")
                        kevin_bacon_mode_status = 'false' if random.random() < 0.5 else random.choice(['year', 'actor', 'director', 'writer', 'producer', 'studio', 'tag'])
                        # Add movie entry to the schedule
                        channel_schedule[day_of_week][starting_time.strftime("%H:%M:%S")] = { 
                            'title': "Random Movie",
                            'time_mode': "preempt", # Strict, Variable, Preempt
                            'start_time': starting_time.strftime("%H:%M:%S"),
                            'type': {
                                'random_movie': {
                                    'duration_minutes': duration_span,
                                    'kevin_bacon_mode': kevin_bacon_mode_status,
                                    'ratings': {
                                        'allowed': block_data.get('allowed_ratings').split(', ') if 'allowed_ratings' in block_data else None,
                                        'forbidden': block_data.get('forbidden_ratings').split(', ') if 'forbidden_ratings' in block_data else None,
                                        },
                                    'decades': {
                                        'allowed': block_data.get('allowed_decades').split(', ') if 'allowed_decades' in block_data else None,
                                        'forbidden': block_data.get('forbidden_decades').split(', ') if 'forbidden_decades' in block_data else None,
                                        },
                                    'actor': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'director': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'writer': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'producer': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'genre': {
                                        'allowed': block_data.get('allowed_genres').split(', ') if 'allowed_genres' in block_data else None,
                                        'forbidden': block_data.get('forbidden_genres').split(', ') if 'forbidden_genres' in block_data else None,
                                        },

                                    'studio': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                    'tag': {
                                        'allowed': "",
                                        'forbidden': "",
                                    },
                                }
                            }
                        }
                        
                        # Fill in with shows until max minutes
                        minutes_advanced = (30 - ending_time.minute % 30) % 30
                        ending_time_movie = ending_time + datetime.timedelta(minutes=duration_span[1]-duration_span[0])
                        starting_time = ending_time + datetime.timedelta(minutes=minutes_advanced)
                        
                        print(f"SHOW STARTING TIME: {starting_time.strftime('%H:%M:%S')}")
                        
                        ending_timestamp = starting_time + datetime.timedelta(minutes=min_minutes)
                        while starting_time <= ending_time_movie-datetime.timedelta(minutes=15):
                        # Select TV Show for programming block
                            '''show_id, show_title, show_duration, ending_time, episode_mode = get_filtered_show(shows_data, block_data, starting_time, ending_time, selected_shows, selected_show_key, selected_show, channel_type)
                            ending_timestamp = ending_time
                            if starting_times[0] > ending_timestamp:
                                ending_timestamp += datetime.timedelta(days=1)
                            if int(show_duration) != 0:
                                entry_duration = int(show_duration)
                            else:
                                entry_duration = time_slot_duration
                            remaining_time = max_minutes - min_minutes
                            #print(ending_timestamp)
                            #print(end_time)
                            
                            while ending_timestamp > starting_time + datetime.timedelta(minutes=max_minutes-min_minutes) or (starting_time == starting_times[-1] and remaining_time < 0) or ending_timestamp > end_time:
                                # If the show length will bleed into the next block, select a new show
                                show_id, show_title, show_duration, ending_time, episode_mode = get_filtered_show(shows_data, block_data, starting_time, ending_time, selected_shows, selected_show_key, selected_show, channel_type)
                                ending_timestamp = ending_time
                                if starting_times[0] > ending_timestamp:
                                    ending_timestamp += datetime.timedelta(days=1)
                                if int(show_duration) != 0:
                                    entry_duration = int(show_duration)
                                else:
                                    entry_duration = time_slot_duration
                                remaining_time = interval_minutes - entry_duration
                            #print(f"{time_slot_duration} - {entry_duration}")'''

                            duration_span = [10, int(min(90, (ending_time_movie-starting_time+datetime.timedelta(minutes=10)).total_seconds()/60))]
                            ending_timestamp = starting_time + datetime.timedelta(minutes=duration_span[0])
                            channel_schedule[day_of_week][starting_time.strftime("%H:%M:%S")] = {
                                'title': 'Random Series', # series name or 'random'
                                'time_mode': 'preempt', # Strict, Variable, Preempt
                                'start_time': starting_time.strftime("%H:%M:%S"),
                                'type': { 
                                    "random_series": {
                                        'duration_minutes': duration_span,
                                        'time_mode': 'preempt',
                                        'episode_mode': 'random',
                                        'ratings': {
                                            'allowed': block_data.get('allowed_ratings').split(', ') if 'allowed_ratings' in block_data else None,
                                            'forbidden': block_data.get('forbidden_ratings').split(', ') if 'forbidden_ratings' in block_data else None,
                                            },
                                        'decades': {
                                            'allowed': block_data.get('allowed_decades').split(', ') if 'allowed_decades' in block_data else None,
                                            'forbidden': block_data.get('forbidden_decades').split(', ') if 'forbidden_decades' in block_data else None,
                                            },
                                        'actor': {
                                            'allowed': "",
                                            'forbidden': "",
                                        },
                                        'director': {
                                            'allowed': "",
                                            'forbidden': "",
                                        },
                                        'writer': {
                                            'allowed': "",
                                            'forbidden': "",
                                        },
                                        'genre': {
                                            'allowed': block_data.get('allowed_genres').split(', ') if 'allowed_genres' in block_data else None,
                                            'forbidden': block_data.get('forbidden_genres').split(', ') if 'forbidden_genres' in block_data else None,
                                            },

                                        'studio': {
                                            'allowed': "",
                                            'forbidden': "",
                                        },
                                        'on_series_end': 'reschedule_similar'
                                    }
                                }
                            }
                            minutes_advanced = (15 - ending_timestamp.minute % 15) % 15
                            starting_time = ending_timestamp + datetime.timedelta(minutes=minutes_advanced)
                            print(f"SHOW ENDING TIME: {ending_time.strftime('%H:%M:%S')}\n")
                            print(f"NEW STARTING TIME: {starting_time.strftime('%H:%M:%S')}")

                #print(f"ENDING TIME: {ending_time.strftime('%H:%M:%S')}\n")
                
                # If the selected show's runtime is shorter than the remaining time, another episode will be scheduled
                if remaining_time is not None and remaining_time < 0:
                    remaining_time += interval_minutes
    channel_schedule['Template'] = channel_template
    return channel_schedule

# Function to get the next available filename in the channels folder
def get_next_filename(folder="channels"):
    # Ensure the folder exists, create if not
    os.makedirs(folder, exist_ok=True)
    
    # Find all existing folders in the channels directory
    existing_folders = [f for f in os.listdir(folder) if os.path.isdir(os.path.join(folder, f))]
    
    # Extract the numbers from existing folder names
    existing_numbers = []
    for folder_name in existing_folders:
        try:
            number = int(folder_name)
            existing_numbers.append(number)
        except ValueError:
            pass

    # Sort the numbers to find the first gap
    existing_numbers.sort()
    
    # Check for gaps in the numbering
    next_number = 1
    if len(existing_numbers) > 0:
        for number in existing_numbers:
            if number != next_number:
                break
            next_number += 1  # Increment to find the next available number

    # Format the next number as a string with leading zeros if necessary
    next_folder = f"{next_number:03}"
    
    # Create the next folder
    next_folder_path = os.path.join(folder, next_folder)
    os.makedirs(next_folder_path, exist_ok=True)
    
    # Return the path to the schedule.json file in the new folder
    return os.path.join(next_folder_path, "schedule.json"), next_folder

def create_new_channel(template_path):
    show_json_path = config['Content']['Show JSON']
    movie_json_path = config['Content']['Movie JSON']
    # Generate the channel schedule
    channel_schedule = generate_channel_schedule(template_path, show_json_path, movie_json_path)

    # Get the next filename
    filename, next_channel_str = get_next_filename()

    # Write the schedule to the file
    with open(filename, "w") as file:
        json.dump(channel_schedule, file, indent=4)

    for day_key, day_schedule in channel_schedule.items():
        if day_key == "Template":
                continue
        print(f"\n{day_key.upper()}")
        for entry_key, entry_value in day_schedule.items():
            entry_title = entry_value.get('title')
            print(f"{entry_key} - {entry_title}", end=" ")
            if 'random_movie' in entry_value['type'].keys():
                duration_span = entry_value['type']['random_movie']['duration_minutes']
                print(f"Between {duration_span[0]} and {duration_span[1]} Minutes")
            elif 'series' in entry_value['type'].keys():
                print(f"- {entry_value['type']['series'].get('duration_minutes')}min - {entry_value['type']['series'].get('episode_mode')}")
            else:
                print()

    print(f"Schedule saved to: {filename}")
    return next_channel_str

def get_kb_degree(movie1, movie2, key, music_video=False):
    if key == "writer":
        key = "credits"
    elif key == "rating":
        key = "certification"
        
    if key in ["decades","year"]:
        #print(json.dumps(movie1,indent=4))
        if music_video is not False:
            movie1_data = movie1['movie'].get('year')
            movie2_data = movie2['movie'].get('year')
        else:
            movie1_data = movie1.get('year')
            movie2_data = movie2.get('year')
    else:
        if music_video is not False:
            movie1_data = movie1['movie'].get(key)
            movie2_data = movie2['movie'].get(key)        
        else:
            movie1_data = movie1.get(key)
            movie2_data = movie2.get(key)
    if movie1_data is None or movie2_data is None:
        return None
    # Handle case where movie1_data or movie2_data is a dictionary instead of a list
    if not isinstance(movie1_data, list):
        movie1_data = [movie1_data]
    if not isinstance(movie2_data, list):
        movie2_data = [movie2_data]

    # Iterate over the entries in movie1 and movie2 and look for a match
    for person1 in movie1_data:
        for person2 in movie2_data:
            if isinstance(person1, dict):
                    if key == "actor":
                        if person1.get("profile") == person2.get("profile"):
                            return person1.get("name")  # Return the first match found
                    elif key == "producer":
                        if person1.get("name") == person2.get("name"):
                            return person1.get("name")  # Return the first match found
                    elif key == "credits" or key == "director":
                        if person1.get("#text") == person2.get("#text"):
                            return person1.get("#text")
            else:
                if person1 == person2:
                    return person1  # Return the first match found
    return None  # Return None if no match is found
    
def schedule_daily_content(schedule, channel_schedule_file, episode_override, channel_dir, existing_daily_schedule=None, overwrite=False):
    # Initialize daily_schedule dictionary
    daily_schedule = {}
    last_kevin_bacon = None

    # Determine the start date for scheduling
    start_date, day_of_week = determine_start_date(existing_daily_schedule)

   # Get an iterator for the items
    iterator = iter(schedule[day_of_week].items())

    # Initialize variables for next start time and drift
    next_start_time = None
    first_start_time = None
    start_time_keys = []
    for start_time in schedule[day_of_week].keys():
        start_time_keys.append(start_time)
        first_start_time = datetime.datetime.strptime(start_time_keys[0], '%H:%M:%S')
    
    # Iterate through time slots for the matched day
    for start_time, content in schedule[day_of_week].items():
        # Get the start time for the next time slot
        for s, start_time_str in enumerate(start_time_keys):
            if start_time_str == start_time:
                if s < len(start_time_keys):
                    try:
                        next_start_time = datetime.datetime.strptime(start_time_keys[s+1], '%H:%M:%S')
                    except IndexError:
                        next_start_time = datetime.datetime.strptime(start_time_keys[0], '%H:%M:%S') + datetime.timedelta(days=1)
                else:
                    next_start_time = datetime.datetime.strptime(start_time_keys[0], '%H:%M:%S') + datetime.timedelta(days=1)

        #print(json.dumps(content,indent=4))
        preempted = "preempt"
        if first_start_time is None:
            first_start_time = start_time
        else:
            start_time = datetime.datetime.strptime(start_time, '%H:%M:%S')
            if start_time < first_start_time:
                start_time += datetime.timedelta(days=1)
        # Get the next start time and calculate drift

        if next_start_time < datetime.datetime.strptime(start_time_keys[0], '%H:%M:%S'):
            next_start_time += datetime.timedelta(days=1)
        remaining_time = (next_start_time - start_time).total_seconds()*1000
        print("-----------------------------------")
        #time.sleep(60)
        original_start_time = start_time
        print(f"TIME RANGE: {original_start_time.strftime('%H:%M:%S')} - {next_start_time.strftime('%H:%M:%S')}")
        #print(f"{(next_start_time - start_time).total_seconds()*1000}")
        # Schedule content based on its type
        scheduled_content = None
        for key in content['type'].keys():
            content_type = key
            #print(content_type)
        if 'random_movie' == content_type:
            kevin_bacon_mode_setting = content['type']['random_movie']['kevin_bacon_mode']
            if kevin_bacon_mode_setting != "false":
                if kevin_bacon_mode_setting == "writer":
                    kevin_bacon_mode_setting = "credits"
                if kevin_bacon_mode_setting == "rating":
                    kevin_bacon_mode_setting = "certification"
                last_kevin_bacon_tuple = load_last_kevin_bacon(channel_dir)
                
                #print(last_kevin_bacon_dict)
                if last_kevin_bacon_tuple:
                    last_kevin_bacon_dict = {last_kevin_bacon_tuple[0]: last_kevin_bacon_tuple[1]}
                    for kb_key, kb_value in last_kevin_bacon_dict.items():
                        last_kevin_bacon = {'setting':kevin_bacon_mode_setting, 'key':kb_key, 'title':kb_value['title']}
                else:
                    last_kevin_bacon_dict = None
            else:
                last_kevin_bacon = None
            #print("------------------------------------")
            print(f"Scheduling a random movie")
            movie_id, this_kevin_bacon = select_random_movie(channel_dir, start_time, content, schedule, existing_daily_schedule, daily_schedule, copy.deepcopy(movie_library))
            #print(json.dumps(movie_library[movie_id],indent=4))
            selected_movie = movie_library[movie_id]
            print(f"SELECTED MOVIE - {selected_movie['title']}")
            #time.sleep(5)
            if last_kevin_bacon is not None and kevin_bacon_mode_setting != "false":
                print(this_kevin_bacon)
                kb_degree = get_kb_degree(movie_library[last_kevin_bacon['key']],selected_movie,last_kevin_bacon['setting'])
                last_kevin_bacon['degree'] = kb_degree
            movie_duration_seconds = selected_movie['files'][0]['duration']
            if preempted and start_time != first_start_time:

                previous_end_time = datetime.datetime.strptime(daily_schedule[list(daily_schedule.keys())[-1]]['end_time'], '%H:%M:%S.%f')
                
                if previous_end_time < datetime.datetime.strptime(list(daily_schedule.keys())[0], '%H:%M:%S.%f'):
                    previous_end_time += datetime.timedelta(days=1)
                
                if start_time < previous_end_time:
                    # Calculate start time or cancel
                    time_over = (previous_end_time - start_time).total_seconds()
                    time_over_ms = time_over*1000
                    print(f"START DELAY: {time_over} seconds")
                    new_start_time = (start_time + datetime.timedelta(microseconds=time_over_ms*1000+1))

                    max_drift_seconds = (content['type']['random_movie']['duration_minutes'][1]*60) - movie_duration_seconds
                    #print(f"MAX DELAY: {max_drift_seconds} seconds")
                    if time_over_ms > (max_drift_seconds + (movie_duration_seconds/3))*1000:
                        print(f"START DELAY TOO HIGH SKIPPING ENTRY")
                        continue
                    new_end_time = new_start_time + datetime.timedelta(seconds=movie_duration_seconds)
                    if new_end_time > (start_time + datetime.timedelta(minutes=content['type']['random_movie']['duration_minutes'][1])):
                        # Set Preempt times
                        new_end_time = next_start_time - datetime.timedelta(seconds=1)
                        new_start_time = previous_end_time + datetime.timedelta(seconds=1)
                        preempt = movie_duration_seconds - (new_end_time - new_start_time).total_seconds()
                        movie_duration_seconds = (new_end_time - new_start_time).total_seconds()
                        print(f"SETTING PREEMPT OF {preempt} SECONDS")
                    else:
                        # Set Delay times
                        time_to_next = (next_start_time - new_end_time).total_seconds()
                        #print(f"TO NEXT: {time_to_next}")
                        
                        minutes_to_round = (5 - (new_start_time.minute % 5)) % 5
                        seconds_to_round = minutes_to_round*60
                        if time_to_next > seconds_to_round and minutes_to_round != 0:
                            #print(f"Time to next: {time_to_next}\nMinutes to Round: {minutes_to_round}")
                            new_start_time = new_start_time + datetime.timedelta(minutes=minutes_to_round)
                            new_start_time = new_start_time.replace(second=0, microsecond=0)
                        elif time_to_next > 60:
                            #print(f"Time to next: {time_to_next}")
                            new_start_time = new_start_time + datetime.timedelta(minutes=1)
                            new_start_time = new_start_time.replace(second=0, microsecond=0)
                        preempt = 0
                    end_datetime = new_start_time + datetime.timedelta(seconds=movie_duration_seconds)
                    start_time = new_start_time
                    print(f"REVISED START TIME: {start_time.strftime('%H:%M:%S')}")
                else:
                    end_datetime = start_time + datetime.timedelta(seconds=movie_duration_seconds)
                    preempt = False
            else:
                end_datetime = start_time + datetime.timedelta(seconds=movie_duration_seconds)
                preempt = False
            end_time = end_datetime.strftime('%H:%M:%S.%f') # Format end time
            remaining_time = (next_start_time - end_datetime).total_seconds()*1000
            try:
                cast = [{'name':actor.get('name',None), 'role':actor.get('role',None)} for actor in selected_movie.get('actor',{})]
            except AttributeError:
                cast = [selected_movie.get('actor','')]
            scheduled_content = {
                "title": f"{selected_movie['title']}",
                "start_time": start_time.strftime('%H:%M:%S.%f'),
                "end_time": end_time, 
                "type": {
                    "movie": {
                        "key": selected_movie['unique_id'],
                        "title": f"{selected_movie['title']}",
                        "year": selected_movie.get('premiered',"0000")[:4],
                        "date": selected_movie.get('premiered',None),
                        "studio": selected_movie.get('studio',None),
                        "tag": selected_movie.get('tag',None),
                        "genre": selected_movie.get('genre',None),
                        "cast": cast,
                        "source": selected_movie.get('source',None)
                    }
                },
                "duration_ms": movie_duration_seconds*1000,
                "duration_s": movie_duration_seconds, # Duration in seconds
                "duration_min": int(movie_duration_seconds/60), # Duration in minutes
                "is_preempted": preempt,
                "summary": selected_movie['plot'],
                "kevin_bacon_mode": this_kevin_bacon
            }

            # Add the scheduled content to daily_schedule
            daily_schedule[start_time.strftime('%H:%M:%S.%f')] = scheduled_content

        elif content_type == 'series' or content_type == 'random_series':
            # Schedule a TV series
            last_episode_index = None
            last_episode_file = os.path.join(channel_dir, 'last.json')
            try:
                episode_mode = content['type']['series']['episode_mode']
            except KeyError:
                episode_mode = "sequential"
            if content_type == 'series':
                show_id = content['type']['series']['id']
            else:
                random_shows = get_random_shows(show_library, schedule['Template'], start_time, next_start_time, start_date)
                show_id = random.choice(list(random_shows.keys()))
            chosen_show = show_library[show_id]
            all_durations = []
            for file_key in chosen_show['files'].keys():
                for episode_details in chosen_show['files'][file_key]['episode_details']:
                    all_durations.append(round(int(int(episode_details['fileinfo']['streamdetails']['video']['durationinseconds']))))
            if len(all_durations) >= 1:
                show_duration_seconds = int(statistics.median(all_durations))
            else:
                show_duration_seconds = 22*60
            
            #print(remaining_time)
            at_least_one = False
            while True:
                override_episode_mode = False
                #print("----------------------------------")
                if remaining_time < show_duration_seconds * 1000 and at_least_one is True:
                    break
                at_least_one = True
                print(f"{start_time.strftime('%H:%M:%S')}: Scheduling {show_library[show_id]['title']}")
                if episode_mode == 'sequential':
                    last_episode, last_episode_index, episode_keys, files = get_last_episode(show_id, last_episode_file)
                    if last_episode_index is None:
                        last_episode, last_episode_index, episode_keys, files = get_last_episode(show_id, last_episode_file, "random")
                    #print(last_episode_index)
                    if (episode_keys[last_episode_index] == episode_keys[-1] or episode_keys[last_episode_index] == False) and 'series' in content['type']:
                        # Last Episode was the last in the series, get new show and update schedule with new show
                        print(f"{show_library[show_id]['title']} has ended.")
                        old_show_id = show_id
                        if content['type']['series']['on_series_end'] == "repeat":
                            print("Starting show over from the beginning")
                            episode_override = "first"
                            pass
                        if content['type']['series']['on_series_end'] == "reschedule_similar":
                            # Find a show from the similar list that fits the time slot and schedule block parameters

                            # Initialize an empty list to store ids of scheduled shows
                            series_ids = []
                            
                            on_series_end = "reschedule_similar"
                            episode_mode = "sequential"
                            
                            # Iterate over the schedule dictionary
                            for i_day, i_time_slots in schedule.items():
                                if i_day in days_of_week:
                                    for i_start_time, i_content in i_time_slots.items():
                                        # Check if the 'type' key exists and if it contains a 'series' key
                                        if i_content.get('type'):
                                            for content_type, content_data in i_content['type'].items():
                                                if content_type == "series":
                                                    series_id = content_data['id']
                                                    series_ids.append(series_id)
                                        else:
                                            print('type key not found')
                                            #print(json.dumps(i_content, indent=4))

                            print(f"Scheduled Shows Detected: {len(series_ids)}")
                            filtered_similar_shows = get_similar_shows(show_id, show_library, schedule['Template'], start_time, next_start_time, start_date, series_ids)
                            
                            time_slot_duration = (next_start_time - start_time).total_seconds()
                            schedule_new_show = 0
                            # Filter out dictionaries whose keys are present in series_ids
                            #filtered_similar_shows = {}
                            #filtered_similar_shows = {key: value for key, value in similar_shows.items() if key not in series_ids}
                            '''for key, value in similar_shows.items():
                                if key not in series_ids:
                                    filtered_similar_shows[key] = value'''
                                
                            # This loop selects a new random show as long as the selected one doesn't fit within the time slot
                            while schedule_new_show < 20 or time_slot_duration < chosen_show_duration or chosen_show_duration < time_slot_duration/3:
                                if len(filtered_similar_shows) < 1:
                                    # If there are no other similar shows, re-run the existing show
                                    show_id = show_id
                                    override_episode_mode = "random"
                                    chosen_show_duration = content['type']['series']['duration_minutes']
                                    schedule_new_show = 99
                                    break
                                else:
                                    print(f"Similar Shows Count: {len(filtered_similar_shows)}")
                                all_durations = []
                                while len(all_durations) < 1:
                                    all_durations = []
                                    # Randomly select a dictionary from the filtered similar_shows
                                    
                                    chosen_show_files = {}
                                    while chosen_show_files == {}:
                                        chosen_show_id = random.choice(list(filtered_similar_shows.keys()))
                                        chosen_show = filtered_similar_shows[chosen_show_id]
                                        chosen_show_files = chosen_show['files']
                                    print(f"{chosen_show['title']} Selected.")
                                    
                                    for file_key in chosen_show['files'].keys():
                                        for episode_details in chosen_show['files'][file_key]['episode_details']:
                                            all_durations.append(round(int(int(episode_details['fileinfo']['streamdetails']['video']['durationinseconds']))))
                                
                                print("____________________")
                                chosen_show_duration = int(statistics.median(all_durations))
                                if time_slot_duration/3 < chosen_show_duration < time_slot_duration:
                                    series_ids.append(chosen_show_id)
                                    schedule_new_show = 99
                                schedule_new_show += 1
                                try:
                                    show_id = chosen_show_id
                                except UnboundLocalError:
                                    show_id = show_id
                                    override_episode_mode = "random"
                                    chosen_show_duration = content['type']['series']['duration_minutes']
                                if schedule_new_show >= 20:
                                    break
                                del filtered_similar_shows[chosen_show_id]
                            print(f"Finding ended show in schedule.")
                            for day, time_schedule in schedule.items():
                                
                                if day in days_of_week:
                                    #print(f"{day[0]}-,end='')
                                # Loop through all time slots of the current day
                                    for dtime, day_schedule in time_schedule.items():
                                        # Check if 'type', 'series', and 'id' exist in the nested dictionary
                                        type_dict = day_schedule.get('type', {})
                                        series = type_dict.get('series', {})

                                        if series.get('id') == str(old_show_id):
                                            print(f"Series Match: {day}, {dtime}. Replacing...")
                                            episode_mode = series.get('episode_mode', '')

                                            reschedule = False
                                            if episode_mode == "rerun" or episode_mode == "sequential":
                                                reschedule = True
                                            if reschedule is True:
                                                schedule[day][dtime] = {}

                                                schedule[day][dtime]['title'] = show_library[show_id]['title']
                                                
                                                schedule[day][dtime]['type'] = {}
                                                schedule[day][dtime]['type']['series'] = {}

                                                schedule[day][dtime]['type']['series']['id'] = show_id
                                                schedule[day][dtime]['type']['series']['duration_minutes'] = round(int(chosen_show_duration) / 60)
                                                if override_episode_mode is False:
                                                    schedule[day][dtime]['type']['series']['episode_mode'] = episode_mode
                                                else:
                                                    schedule[day][dtime]['type']['series']['episode_mode'] = override_episode_mode
                                                schedule[day][dtime]['type']['series']['on_series_end'] = on_series_end
                            '''dow = [day_of_week]
                            for day in days_of_week:
                                if day == day_of_week:
                                    continue
                                
                                # Get the schedule entry at the specific time for the current day
                                day_schedule = schedule.get(day, {}).get(original_start_time.strftime('%H:%M:%S'), {})
                                
                                if day_schedule == schedule[day_of_week][original_start_time.strftime('%H:%M:%S')]:
                                    dow.append(day)
                            
                            for d in dow:                           
                                schedule[d][original_start_time.strftime('%H:%M:%S')] = {}
                                
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['title'] = show_library[show_id]['title']
                                
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type'] = {}
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series'] = {}
                                
                                
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['id'] = show_id
                                print(chosen_show_duration)
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['duration_minutes'] = round(int(chosen_show_duration)/60)
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['episode_mode'] = episode_mode
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['on_series_end'] = on_series_end'''
                            
                            # Save newly selected show to schedule file
                            print("Saving schedule file")
                            with open(channel_schedule_file, 'w') as file:
                                json.dump(schedule, file, indent=4)
                                
                            print(f"Scheduling: {show_library[show_id]['title']}")
                            episode_override = "first"
                            time.sleep(1)

                        if content['type']['series']['on_series_end'] == "reschedule_template":
                            # Find a show from the similar list that fits the time slot and schedule block parameters

                            # Initialize an empty list to store ids of scheduled shows
                            series_ids = []
                            
                            on_series_end = "reschedule_similar"
                            episode_mode = "sequential"
                            
                            # Iterate over the schedule dictionary
                            for i_day, i_time_slots in schedule.items():
                                for i_start_time, i_content in i_time_slots.items():
                                    # Check if the 'type' key exists and if it contains a 'series' key
                                    if i_content.get('type'):
                                        for content_type, content_data in i_content['type'].items():
                                            if content_type == "series":
                                                series_id = content_data['id']
                                                series_ids.append(series_id)
                                    else:
                                        print('type key not found')
                                        #print(json.dumps(i_content, indent=4))

                            print(f"Scheduled Shows Detected: {len(series_ids)}")
                            filtered_similar_shows = get_random_shows(show_library, schedule['Template'], start_time, next_start_time, start_date, series_ids)
                            
                            
                            time_slot_duration = (next_start_time - start_time).total_seconds()
                            schedule_new_show = 0
                            # Filter out dictionaries whose keys are present in series_ids
                            #filtered_similar_shows = {}
                            #filtered_similar_shows = {key: value for key, value in similar_shows.items() if key not in series_ids}
                            '''for key, value in similar_shows.items():
                                if key not in series_ids:
                                    filtered_similar_shows[key] = value'''
                                
                            # This loop selects a new random show as long as the selected one doesn't fit within the time slot
                            while schedule_new_show < 20 or time_slot_duration < chosen_show_duration or chosen_show_duration < time_slot_duration/3:
                                if len(filtered_similar_shows) < 1:
                                    # If there are no other similar shows, re-run the existing show
                                    show_id = show_id
                                    override_episode_mode = "random"
                                    chosen_show_duration = content['type']['series']['duration_minutes']
                                    schedule_new_show = 99
                                    break
                                else:
                                    print(f"Similar Shows Count: {len(filtered_similar_shows)}")
                                all_durations = []
                                while len(all_durations) < 1:
                                    all_durations = []
                                    # Randomly select a dictionary from the filtered similar_shows
                                    
                                    chosen_show_files = {}
                                    while chosen_show_files == {}:
                                        chosen_show_id = random.choice(list(filtered_similar_shows.keys()))
                                        chosen_show = filtered_similar_shows[chosen_show_id]
                                        chosen_show_files = chosen_show['files']
                                    print(f"{chosen_show['title']} Selected.")
                                    
                                    for file_key in chosen_show['files'].keys():
                                        for episode_details in chosen_show['files'][file_key]['episode_details']:
                                            all_durations.append(round(int(int(episode_details['fileinfo']['streamdetails']['video']['durationinseconds']))))
                                
                                print("____________________")
                                chosen_show_duration = int(statistics.median(all_durations))
                                if time_slot_duration/3 < chosen_show_duration < time_slot_duration:
                                    series_ids.append(chosen_show_id)
                                    schedule_new_show = 99
                                schedule_new_show += 1
                                try:
                                    show_id = chosen_show_id
                                except UnboundLocalError:
                                    show_id = show_id
                                    override_episode_mode = "random"
                                    chosen_show_duration = content['type']['series']['duration_minutes']
                                if schedule_new_show >= 20:
                                    break
                                del filtered_similar_shows[chosen_show_id]
                                
                            for day, time_schedule in schedule.items():
                                print(f"Replacing old show in schedule")
                                if day in days_of_week:
                                # Loop through all time slots of the current day
                                    for dtime, day_schedule in time_schedule.items():
                                        # Check if 'type', 'series', and 'id' exist in the nested dictionary
                                        series = day_schedule.get('type', {}).get('series', {})

                                        if series.get('id') == old_show_id:
                                            episode_mode = series.get('episode_mode', '')
                                            
                                            # If sequential, only replace if it's at the same dtime
                                            if episode_mode == "sequential" or episode_mode == "rerun":
                                                schedule[day][dtime] = {}

                                                schedule[day][dtime]['title'] = show_library[show_id]['title']
                                                
                                                schedule[day][dtime]['type'] = {}
                                                schedule[day][dtime]['type']['series'] = {}

                                                schedule[day][dtime]['type']['series']['id'] = show_id
                                                schedule[day][dtime]['type']['series']['duration_minutes'] = round(int(chosen_show_duration) / 60)
                                                if override_episode_mode is False:
                                                    schedule[day][dtime]['type']['series']['episode_mode'] = episode_mode
                                                else:
                                                    schedule[day][dtime]['type']['series']['episode_mode'] = override_episode_mode
                                                schedule[day][dtime]['type']['series']['on_series_end'] = on_series_end
                                
                            '''dow = [day_of_week]
                            for day in days_of_week:
                                if day == day_of_week:
                                    continue
                                
                                # Get the schedule entry at the specific time for the current day
                                day_schedule = schedule.get(day, {}).get(original_start_time.strftime('%H:%M:%S'), {})
                                
                                if day_schedule == schedule[day_of_week][original_start_time.strftime('%H:%M:%S')]:
                                    dow.append(day)
                            
                            for d in dow:                           
                                schedule[d][original_start_time.strftime('%H:%M:%S')] = {}
                                
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['title'] = show_library[show_id]['title']
                                
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type'] = {}
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series'] = {}
                                
                                
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['id'] = show_id
                                print(chosen_show_duration)
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['duration_minutes'] = round(int(chosen_show_duration)/60)
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['episode_mode'] = episode_mode
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['on_series_end'] = on_series_end'''
                            
                            # Save newly selected show to schedule file
                            with open(channel_schedule_file, 'w') as file:
                                json.dump(schedule, file, indent=4)
                                
                            print(f"Scheduling: {show_library[show_id]['title']}")
                            episode_override = "first"
                            time.sleep(1)

                        if content['type']['series']['on_series_end'] == "reschedule_rating":
                            # Find a show from the similar list that fits the time slot and schedule block parameters

                            # Initialize an empty list to store ids of scheduled shows
                            series_ids = []
                            
                            on_series_end = "reschedule_rating"
                            episode_mode = "sequential"
                            
                            # Iterate over the schedule dictionary
                            for i_day, i_time_slots in schedule.items():
                                for i_start_time, i_content in i_time_slots.items():
                                    # Check if the 'type' key exists and if it contains a 'series' key
                                    if i_content.get('type'):
                                        for content_type, content_data in i_content['type'].items():
                                            if content_type == "series":
                                                series_id = content_data['id']
                                                series_ids.append(series_id)
                                    else:
                                        print('type key not found')
                                        #print(json.dumps(i_content, indent=4))

                            print(f"Scheduled Shows Detected: {len(series_ids)}")
                            filtered_similar_shows = get_same_rating_shows(show_id, show_library, schedule['Template'], start_time, next_start_time, start_date, series_ids)
                            
                            time_slot_duration = (next_start_time - start_time).total_seconds()
                            schedule_new_show = 0
                            # Filter out dictionaries whose keys are present in series_ids
                            #filtered_similar_shows = {}
                            #filtered_similar_shows = {key: value for key, value in similar_shows.items() if key not in series_ids}
                            '''for key, value in similar_shows.items():
                                if key not in series_ids:
                                    filtered_similar_shows[key] = value'''
                                
                            # This loop selects a new random show as long as the selected one doesn't fit within the time slot
                            while schedule_new_show < 20 or time_slot_duration < chosen_show_duration or chosen_show_duration < time_slot_duration/3:
                                if len(filtered_similar_shows) < 1:
                                    # If there are no other similar shows, re-run the existing show
                                    show_id = show_id
                                    override_episode_mode = "random"
                                    chosen_show_duration = content['type']['series']['duration_minutes']
                                    schedule_new_show = 99
                                    break
                                else:
                                    print(f"Same Ratings Shows Count: {len(filtered_similar_shows)}")
                                all_durations = []
                                while len(all_durations) < 1:
                                    all_durations = []
                                    # Randomly select a dictionary from the filtered similar_shows
                                    
                                    chosen_show_files = {}
                                    while chosen_show_files == {}:
                                        chosen_show_id = random.choice(list(filtered_similar_shows.keys()))
                                        chosen_show = filtered_similar_shows[chosen_show_id]
                                        chosen_show_files = chosen_show['files']
                                    print(f"{chosen_show['title']} Selected.")
                                    
                                    for file_key in chosen_show['files'].keys():
                                        for episode_details in chosen_show['files'][file_key]['episode_details']:
                                            all_durations.append(round(int(int(episode_details['fileinfo']['streamdetails']['video']['durationinseconds']))))
                                
                                print("____________________")
                                chosen_show_duration = int(statistics.median(all_durations))
                                if time_slot_duration/3 < chosen_show_duration < time_slot_duration:
                                    series_ids.append(chosen_show_id)
                                    schedule_new_show = 99
                                schedule_new_show += 1
                                try:
                                    show_id = chosen_show_id
                                except UnboundLocalError:
                                    show_id = show_id
                                    override_episode_mode = "random"
                                    chosen_show_duration = content['type']['series']['duration_minutes']
                                if schedule_new_show >= 20:
                                    break
                                del filtered_similar_shows[chosen_show_id]
                                
                            for day, time_schedule in schedule.items():
                                print(f"Replacing old show in schedule")
                                if day in days_of_week:
                                # Loop through all time slots of the current day
                                    for dtime, day_schedule in time_schedule.items():
                                        # Check if 'type', 'series', and 'id' exist in the nested dictionary
                                        series = day_schedule.get('type', {}).get('series', {})

                                        if series.get('id') == old_show_id:
                                            episode_mode = series.get('episode_mode', '')
                                            
                                            # If sequential, only replace if it's at the same time
                                            if episode_mode == "sequential" or episode_mode == "rerun":
                                                schedule[day][dtime] = {}

                                                schedule[day][dtime]['title'] = show_library[show_id]['title']
                                                
                                                schedule[day][dtime]['type'] = {}
                                                schedule[day][dtime]['type']['series'] = {}

                                                schedule[day][dtime]['type']['series']['id'] = show_id
                                                schedule[day][dtime]['type']['series']['duration_minutes'] = round(int(chosen_show_duration) / 60)
                                                if override_episode_mode is False:
                                                    schedule[day][dtime]['type']['series']['episode_mode'] = episode_mode
                                                else:
                                                    schedule[day][dtime]['type']['series']['episode_mode'] = override_episode_mode
                                                schedule[day][dtime]['type']['series']['on_series_end'] = on_series_end
                                
                            '''dow = [day_of_week]
                            for day in days_of_week:
                                if day == day_of_week:
                                    continue
                                
                                # Get the schedule entry at the specific time for the current day
                                day_schedule = schedule.get(day, {}).get(original_start_time.strftime('%H:%M:%S'), {})
                                
                                if day_schedule == schedule[day_of_week][original_start_time.strftime('%H:%M:%S')]:
                                    dow.append(day)
                                
                            for d in dow:                           
                                schedule[d][original_start_time.strftime('%H:%M:%S')] = {}
                                
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['title'] = show_library[show_id]['title']
                                
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type'] = {}
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series'] = {}
                                
                                
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['id'] = show_id
                                print(chosen_show_duration)
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['duration_minutes'] = round(int(chosen_show_duration)/60)
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['episode_mode'] = episode_mode
                                schedule[d][original_start_time.strftime('%H:%M:%S')]['type']['series']['on_series_end'] = on_series_end'''
                            
                            # Save newly selected show to schedule file
                            with open(channel_schedule_file, 'w') as file:
                                json.dump(schedule, file, indent=4)
                                
                            print(f"Scheduling: {show_library[show_id]['title']}")
                            episode_override = "first"
                            time.sleep(1)
                        last_episode, last_episode_index, episode_keys, files = get_last_episode(show_id, last_episode_file, episode_override)
                        
                        episode_id, episode_info = next_episode(show_id, None, episode_keys, files)
                    else:
                        episode_id, episode_info = next_episode(show_id, last_episode, episode_keys, files)
                elif episode_mode == 'random':
                    print("RANDOM EPISODE")

                    files = {}
                    for f, file in chosen_show['files'].items():
                        files[f] = file
                    episode_keys = list(files.keys())
                    episode_id, episode_info = random_episode(files)
                
                episode_duration_seconds = int(show_library[show_id]['files'][episode_id]["episode_details"][0]["fileinfo"]["streamdetails"]["video"]["durationinseconds"])

                start_time, scheduled_content = schedule_series(show_library[show_id], start_time, next_start_time, episode_info, daily_schedule, episode_mode, preempted)
                end_time = start_time + datetime.timedelta(seconds = int(episode_duration_seconds))
                if end_time < datetime.datetime.strptime(start_time_keys[0], '%H:%M:%S'):
                    end_time += datetime.timedelta(days=1)
                #print(scheduled_content)
                if scheduled_content is None:
                    remaining_time = 0
                    continue
                # Add the scheduled content to daily_schedule
                #print(start_time)
                daily_schedule[start_time.strftime('%H:%M:%S.%f')] = scheduled_content

                # Save last episode data necessary at this point here
                if episode_mode == 'sequential':
                    last_episode_dict = {
                        'title': show_library[show_id]['title'],
                        'episode_path': episode_id,
                        'season_number': int(show_library[show_id]['files'][episode_id]['episode_details'][0]['season']),
                        'episode_number': int(show_library[show_id]['files'][episode_id]['episode_details'][0]['episode'])
                    }
                    save_last_episode_details(last_episode_file,last_episode_dict, show_id)
                # Check if there is time for another episode, first check at the nearest 15, then the nearest 5.
                if end_time.minute % 15 == 0 and (next_start_time - (end_time + datetime.timedelta(seconds=1))).total_seconds() > episode_duration_seconds:
                    remaining_time = (next_start_time - (end_time + datetime.timedelta(seconds=1))).total_seconds()*1000
                    last_episode = show_library[show_id]['files'][episode_id]
                    last_episode_index = episode_keys.index(episode_id)
                    start_time = end_time + datetime.timedelta(seconds=1)
                elif end_time.minute % 15 != 0 and (next_start_time - (end_time + datetime.timedelta(minutes=15-(end_time.minute % 15))).replace(second=0, microsecond=0)).total_seconds() > episode_duration_seconds:
                    remaining_time = (next_start_time - (end_time + datetime.timedelta(minutes=15-(end_time.minute % 15))).replace(second=0, microsecond=0)).total_seconds()*1000
                    last_episode = show_library[show_id]['files'][episode_id]
                    last_episode_index = episode_keys.index(episode_id)
                    start_time = (end_time + datetime.timedelta(minutes=15-(end_time.minute % 15))).replace(second=0, microsecond=0)
                elif end_time.minute % 5 == 0 and (next_start_time - (end_time + datetime.timedelta(seconds=1))).total_seconds() > episode_duration_seconds:
                    remaining_time = (next_start_time - (end_time + datetime.timedelta(seconds=1))).total_seconds()*1000
                    last_episode = show_library[show_id]['files'][episode_id]
                    last_episode_index = episode_keys.index(episode_id)
                    start_time = end_time + datetime.timedelta(seconds=1)
                elif end_time.minute % 5 != 0 and (next_start_time - (end_time + datetime.timedelta(minutes=5-(end_time.minute % 5))).replace(second=0, microsecond=0)).total_seconds() > episode_duration_seconds:
                    remaining_time = (next_start_time - (end_time + datetime.timedelta(minutes=5-(end_time.minute % 5))).replace(second=0, microsecond=0)).total_seconds()*1000
                    last_episode = show_library[show_id]['files'][episode_id]
                    last_episode_index = episode_keys.index(episode_id)
                    start_time = (end_time + datetime.timedelta(minutes=5-(end_time.minute % 5))).replace(second=0, microsecond=0)
                else:
                    show_duration_seconds = episode_duration_seconds
                print(remaining_time)
                if remaining_time < show_duration_seconds * 1000:
                    break
        if 'music_videos' == content_type:
            kevin_bacon_mode_setting = content['type']['music_videos']['kevin_bacon_mode']
            last_kevin_bacon = None
            seconds_to_fill = content['type']['music_videos']['duration_minutes']*60
            while seconds_to_fill > 0:
                #print("------------------------------------")
                print(f"Scheduling a random music video")
                music_video_id, this_kevin_bacon = select_music_video(channel_dir, start_time, content, schedule, existing_daily_schedule, daily_schedule, copy.deepcopy(music_videos_library),last_kevin_bacon)
                selected_music_video = music_videos_library[music_video_id]
                print(f"SELECTED MUSIC VIDEO - {selected_music_video['title']}")
                #time.sleep(5)
                if last_kevin_bacon is not None and kevin_bacon_mode_setting != "false":
                    print(this_kevin_bacon)
                    kb_degree = get_kb_degree(music_videos_library[last_kevin_bacon['key']],selected_music_video,last_kevin_bacon['setting'],music_video=True)
                    last_kevin_bacon['degree'] = kb_degree
                music_video_duration_seconds = selected_music_video['files'][0]['duration']
                if preempted and start_time != first_start_time:

                    previous_end_time = datetime.datetime.strptime(daily_schedule[list(daily_schedule.keys())[-1]]['end_time'], '%H:%M:%S.%f')
                    
                    if previous_end_time < datetime.datetime.strptime(list(daily_schedule.keys())[0], '%H:%M:%S.%f'):
                        previous_end_time += datetime.timedelta(days=1)
                    
                    if start_time < previous_end_time:
                        # Calculate start time or cancel
                        time_over = (previous_end_time - start_time).total_seconds()
                        time_over_ms = time_over*1000
                        print(f"START DELAY: {time_over} seconds")
                        new_start_time = (start_time + datetime.timedelta(microseconds=time_over_ms*1000+1))

                        max_drift_seconds = (next_start_time - start_time).total_seconds() - music_video_duration_seconds
                        #print(f"MAX DELAY: {max_drift_seconds} seconds")
                        if time_over_ms > (max_drift_seconds + (music_video_duration_seconds/3))*1000:
                            print(f"START DELAY TOO HIGH SKIPPING ENTRY")
                            seconds_to_fill -= (time_over+1)
                            start_time = previous_end_time + datetime.timedelta(seconds=1)
                            continue
                        new_end_time = new_start_time + datetime.timedelta(seconds=music_video_duration_seconds)
                        if new_end_time > next_start_time:
                            # Set Preempt times
                            new_end_time = next_start_time - datetime.timedelta(seconds=1)
                            new_start_time = previous_end_time + datetime.timedelta(seconds=1)
                            preempt = music_video_duration_seconds - (new_end_time - new_start_time).total_seconds()
                            music_video_duration_seconds = (new_end_time - new_start_time).total_seconds()
                            print(f"SETTING PREEMPT OF {preempt} SECONDS")
                        else:
                            # Set Delay times
                            time_to_next = (next_start_time - new_end_time).total_seconds()
                            #print(f"TO NEXT: {time_to_next}")
                            
                            minutes_to_round = (5 - (new_start_time.minute % 5)) % 5
                            seconds_to_round = minutes_to_round*60
                            if time_to_next > seconds_to_round and minutes_to_round != 0:
                                #print(f"Time to next: {time_to_next}\nMinutes to Round: {minutes_to_round}")
                                new_start_time = new_start_time + datetime.timedelta(minutes=minutes_to_round)
                                new_start_time = new_start_time.replace(second=0, microsecond=0)
                            elif time_to_next > 60:
                                #print(f"Time to next: {time_to_next}")
                                new_start_time = new_start_time + datetime.timedelta(minutes=1)
                                new_start_time = new_start_time.replace(second=0, microsecond=0)
                            preempt = 0
                        end_datetime = new_start_time + datetime.timedelta(seconds=music_video_duration_seconds)
                        start_time = new_start_time
                        print(f"REVISED START TIME: {start_time.strftime('%H:%M:%S')}")
                    else:
                        end_datetime = start_time + datetime.timedelta(seconds=music_video_duration_seconds)
                        preempt = False
                else:
                    end_datetime = start_time + datetime.timedelta(seconds=music_video_duration_seconds)
                    preempt = False
                end_time = end_datetime.strftime('%H:%M:%S.%f') # Format end time
                seconds_to_fill -= music_video_duration_seconds
                remaining_time = (next_start_time - end_datetime).total_seconds()*1000

                scheduled_content = {
                    "title": f"{selected_music_video['title']}",
                    "start_time": start_time.strftime('%H:%M:%S.%f'),
                    "end_time": end_time, 
                    "type": {
                        "music_video": {
                            "key": selected_music_video['files'][0]['filepath'],
                            "title": f"{selected_music_video['title']}",
                            "year": selected_music_video['movie'].get('year',"0000")[:4],
                            "date": selected_music_video['movie'].get('aired',None),
                            "tag": selected_music_video['movie'].get('tag',None),
                            "source": selected_music_video['movie'].get('source',None)
                        }
                    },
                    "duration_ms": music_video_duration_seconds*1000,
                    "duration_s": music_video_duration_seconds, # Duration in seconds
                    "duration_min": int(music_video_duration_seconds/60), # Duration in minutes
                    "is_preempted": preempt,
                    "summary": selected_music_video['movie']['plot'],
                    "kevin_bacon_mode": this_kevin_bacon
                }

                # Add the scheduled content to daily_schedule
                daily_schedule[start_time.strftime('%H:%M:%S.%f')] = scheduled_content
                if remaining_time >= 60:
                    if end_datetime.second != 0:
                        start_time += datetime.timedelta(minutes=1)
                        start_time = start_time.replace(second=0,microsecond=0)
                    else:
                        start_time = end_datetime
                else:
                    seconds_to_fill = 0


        if scheduled_content is None:
            continue

    if existing_daily_schedule:
        existing_daily_schedule[start_date] = daily_schedule
    else:
        existing_daily_schedule = {}
        existing_daily_schedule[start_date] = daily_schedule
    return existing_daily_schedule

def filter_movies_library(movies_library, filter_key, filter_entry):
    filtered_library = {}

    # Function to match based on the key and entry
    def matches(movie, key, entry):
        match_details = []
        
        if key == "certification":
            if movie.get("certification") == entry.get("certification"):
                print(f"Matching certification: {movie.get('certification')} in {movie.get('title')}")
                if movie.get('unique_id') != entry.get("unique_id"):
                    match_details.append({'setting': key, 'key': movie.get('unique_id'), 'title': entry.get('title'), 'degree': movie.get('certification')})
                return match_details

        elif key in ["decade", "year"]:
            if movie.get("year", "")[:4] == entry.get("year", "")[:4]:
                print(f"Matching year: {movie.get('year')} in {movie.get('title')}")
                if movie.get('unique_id') != entry.get("unique_id"):
                    match_details.append({'setting': key, 'key': entry.get('unique_id'), 'title': entry.get('title'), 'degree': movie.get('year')[:4]})
                return match_details

        elif key in ["actor", "producer"]:
            movie_data = movie.get(key, [])
            if not isinstance(movie_data, list):
                movie_data = [movie_data]  # Convert non-list to a list
            entry_data = entry.get(key, [])
            
            for e in entry_data:
                if isinstance(e, dict):
                    for person in movie_data:
                        if person.get("name") == e.get("name"):
                            if movie.get('unique_id') != entry.get('unique_id'):
                                print(f"Matching {key}: {person.get('name').upper()} in {movie.get('title')}")
                                match_details.append({'setting': key, 'key': entry.get('unique_id'), 'title': entry.get('title'), 'degree': person.get('name')})
        
        elif key in ["director", "credits"]:
            movie_data = movie.get(key, [])
            if not isinstance(movie_data, list):
                movie_data = [movie_data]  # Convert non-list to a list
            entry_data = entry.get(key, [])
            if not isinstance(entry_data, list):
                entry_data = [entry_data]
            for e in entry_data:
                for person in movie_data:
                    #print(e.get("#text"),end=' --> ')
                    #print(person.get("#text"))
                    if person.get("#text") == e.get("#text") and person.get("#text") is not None:
                        if movie.get('unique_id') != entry.get('unique_id'):
                            print(f"Matching {key}: {person.get('#text').upper()} in {movie.get('title')}")
                            match_details.append({'setting': key, 'key': entry.get('unique_id'), 'title': entry.get('title'), 'degree': person.get('#text')})

        elif key in ["genre", "studio", "tag"]:
            movie_values = movie.get(key, [])
            entry_values = entry.get(key, [])
            
            # Ensure movie_values is a list of full strings, not characters
            if isinstance(movie_values, str):
                movie_values = [movie_values]  # Convert a single string to a list
                entry_values = entry.get(key, [])
            if isinstance(entry_values, str):
                entry_values = [entry_values]  # Convert a single string to a list
                
            for value in movie_values:
                if value in entry_values:
                    if movie.get('unique_id') != entry.get('unique_id'):
                        print(f"Matching {key}: {value} in {movie.get('title')}")
                        match_details.append({'setting': key, 'key': entry.get('unique_id'), 'title': entry.get('title'), 'degree': value})

        return match_details

    # Iterate over the movies in the library
    link_details = {}
    for movie_id, movie in movies_library.items():
        movie_matches = matches(movie, filter_key, filter_entry[1])
        if movie_matches:
            if isinstance(movie_matches, list):
                movie_match = {
                    'setting': movie_matches[0].get('setting'),
                    'key': movie_matches[0].get('key'),
                    'title': movie_matches[0].get('title'),
                    'degree': []
                    }
                for match in movie_matches:
                    movie_match['degree'].append(match.get('degree'))
                link_details[movie_id] = movie_match
            else:
                link_details[movie_id] = movie_matches
            filtered_library[movie_id] = movie

    return filtered_library, link_details

def filter_music_videos_library(music_videos_library, filter_key, filter_entry):
    filtered_library = {}

    # Function to match based on the key and entry
    def matches(music_video, key, entry):
        match_details = []
        if key in ["decade", "year"]:
            if music_video.get("year", "")[:4] == entry.get("year", "")[:4]:
                print(f"Matching year: {music_video.get('year')} in {music_video.get('title')}")
                if music_video.get('unique_id') != entry.get("unique_id"):
                    match_details.append({'setting': key, 'key': entry.get('unique_id'), 'title': entry.get('title'), 'degree': music_video.get('year')[:4]})
                return match_details
        elif key in ["tag"]:
            music_video_values = music_video.get(key, [])
            entry_values = entry.get(key, [])
            
            # Ensure music_video_values is a list of full strings, not characters
            if isinstance(music_video_values, str):
                music_video_values = [music_video_values]  # Convert a single string to a list
                entry_values = entry.get(key, [])
            if isinstance(entry_values, str):
                entry_values = [entry_values]  # Convert a single string to a list
                
            for value in music_video_values:
                if value in entry_values:
                    if music_video.get('unique_id') != entry.get('unique_id'):
                        print(f"Matching {key}: {value} in {music_video.get('title')}")
                        match_details.append({'setting': key, 'key': entry.get('unique_id'), 'title': entry.get('title'), 'degree': value})

        return match_details

    # Iterate over the music_videos in the library
    link_details = {}
    for music_video_id, music_video in music_videos_library.items():
        music_video_matches = matches(music_video, filter_key, filter_entry[1])
        if music_video_matches:
            if isinstance(music_video_matches, list):
                music_video_match = {
                    'setting': music_video_matches[0].get('setting'),
                    'key': music_video_matches[0].get('key'),
                    'title': music_video_matches[0].get('title'),
                    'degree': []
                    }
                for match in music_video_matches:
                    music_video_match['degree'].append(match.get('degree'))
                link_details[music_video_id] = music_video_match
            else:
                link_details[music_video_id] = music_video_matches
            filtered_library[music_video_id] = music_video

    return filtered_library, link_details

def save_last_kevin_bacon(key, value, path):
    # Create a dictionary with the single key-value pair
    filename=os.path.join(path,"last_kevin_bacon.json")
    
    data = {key: value}

    # Open the file in write mode and save the new key-value pair, overwriting any existing content
    with open(filename, 'w') as file:
        json.dump(data, file, indent=4)

def load_last_kevin_bacon(path):
    # Check if the file exists
    filename=os.path.join(path,"last_kevin_bacon.json")
    if os.path.exists(filename):
        # Open the file and load the JSON data
        with open(filename, 'r') as file:
            data = json.load(file)
            # Return the key-value pair (assuming there's only one)
            return list(data.items())[0]  # Returns as (key, value) tuple
    else:
        # Return None if the file doesn't exist
        return None

def select_random_movie(channel_dir, start_time, content, schedule, existing_daily_schedule, daily_schedule, movie_lib):
    link_details = None
    # Implementation to schedule a random movie based on provided parameters
    selection_parameters = content['type']['random_movie']

    save_last = False
    for p, parameter in selection_parameters.items():
        if isinstance(parameter, dict):  # Check if parameter is a dictionary (indicating the new structure)
            if "allowed" in parameter and parameter["allowed"]:
                #print(parameter["allowed"])
                if p == "decades" and parameter["allowed"] != [""]:
                    filtered_movie_library = from_decade(movie_lib, parameter["allowed"])
                else:
                    filtered_movie_library = from_filter(movie_lib, parameter["allowed"], p, include=True)
                if filtered_movie_library and len(filtered_movie_library) > 0:
                    movie_lib = filtered_movie_library
                    #print(f"2: {len(movie_lib)} Movies Remaining",end='\r')
            if "forbidden" in parameter and parameter["forbidden"]:
                #print(parameter["forbidden"])
                if p == "decades" and parameter["forbidden"] != [""]:
                    filtered_movie_library = from_decade(movie_lib, parameter["forbidden"])
                else:
                    filtered_movie_library = from_filter(movie_lib, parameter["forbidden"], p, include=False)
                if filtered_movie_library and len(filtered_movie_library) > 0:
                    movie_lib = filtered_movie_library
                    #print(f"3: {len(movie_lib)} Movies Remaining",end='\r')
        elif p == "duration_minutes":
            if parameter:
                filtered_movie_library = filter_movies_by_duration(movie_lib, parameter)
                if filtered_movie_library and len(filtered_movie_library) > 0:
                    movie_lib = filtered_movie_library
                    #print(f"4: {len(movie_lib)} Movies Remaining",end='\r')
        else:
            if parameter:
                filtered_movie_library = from_filter(movie_lib, parameter, p, include=True)
                #print(p, parameter)
                if filtered_movie_library and len(filtered_movie_library) > 0:
                    movie_lib = filtered_movie_library
                    #print(f"5: {len(movie_lib)} Movies Remaining.",end='\r')
        
        if p == "kevin_bacon_mode":
            if parameter != "false":
                #print(f"Link {parameter.upper()} Library Size:",end=' ')
                if parameter == "writer":
                    parameter = "credits"
                elif parameter == "ratings":
                    parameter = "certification"
                save_last = True
                last_kevin_bacon = load_last_kevin_bacon(channel_dir)
                # Filter movie library by Kevin Bacon rules
                if last_kevin_bacon is not None:
                    print(f"Last Linked Title: {last_kevin_bacon[1]['title']}")
                    filtered_library, link_details = filter_movies_library(movie_lib, parameter, last_kevin_bacon)
                    
                    if len(filtered_library) > 1:
                        movie_lib = filtered_library
                        print(f"{len(filtered_library)} Movies Found")
                    else:
                        print(f"\rLink {parameter.upper()} Match NOT FOUND") 
                        link_details = None
                else:
                    link_details = None
    for time, entry in reversed(list(daily_schedule.items())):
        if entry and 'type' in entry and 'movie' in entry['type'] and entry['type']['movie']['key'] in movie_lib:
            if len(movie_lib) > 1:
                del movie_lib[entry['type']['movie']['key']]                    
    # Check daily schedule history in reverse order to check for matching entries and remove them from movie_lib unless only one is remaining
    if existing_daily_schedule:
        for d, time_slots in reversed(list(existing_daily_schedule.items())):
            for time, entry in reversed(list(time_slots.items())):
                if 'type' in entry and 'movie' in entry['type'] and entry['type']['movie']['key'] in movie_lib:
                    if len(movie_lib) > 1:
                        del movie_lib[entry['type']['movie']['key']]
                    #print(f"1: {len(movie_lib)} Movies Remaining",end='\r')
    print(f"\nSelecting Movie from {len(movie_lib)} options.")
    movie_choice = random.choice(list(movie_lib.keys()))
    if save_last is True:
        save_last_kevin_bacon(movie_choice, movie_lib[movie_choice], channel_dir)
    if link_details:
        #print(link_details)
        return movie_choice, link_details[movie_choice]
    else:
        return movie_choice, None

def select_music_video(channel_dir, start_time, content, schedule, existing_daily_schedule, daily_schedule, music_video_lib, last_kevin_bacon=None):
    link_details = None
    # Implementation to schedule a random movie based on provided parameters
    selection_parameters = content['type']['music_videos']
    '''for d, time_slots in existing_daily_schedule.items():
        for time, entry in list(time_slots.items()):
            if 'type' in entry and 'music_video' in entry['type'] and entry['type']['music_video']['key'] in music_video_lib:
                del music_video_lib[key] #key not defined
                print(f"1: {len(music_video_lib)} Music Videos Remaining",end='\r')'''
    save_last = False
    for p, parameter in selection_parameters.items():
        if isinstance(parameter, dict):  # Check if parameter is a dictionary 
            if "allowed" in parameter and parameter["allowed"]:
                #print(parameter["allowed"])
                filtered_music_video_library = from_filter(music_video_lib, parameter["allowed"], p, include=True)
                if filtered_music_video_library and len(filtered_music_video_library) > 0:
                    music_video_lib = filtered_music_video_library
                    #print(f"2: {len(music_video_lib)} Music Videos Remaining",end='\r')
            if "forbidden" in parameter and parameter["forbidden"]:
                #print(parameter["forbidden"])
                filtered_music_video_library = from_filter(music_video_lib, parameter["forbidden"], p, include=False)
                if filtered_music_video_library and len(filtered_music_video_library) > 0:
                    music_video_lib = filtered_music_video_library
                    #print(f"3: {len(music_video_lib)} Music Videos Remaining",end='\r')
        elif p == "duration_minutes":
            if parameter:
                filtered_music_video_library = filter_movies_by_duration(music_video_lib, [0, parameter])
                if filtered_music_video_library and len(filtered_music_video_library) > 0:
                    music_video_lib = filtered_music_video_library
                    #print(f"4: {len(music_video_lib)} Music Videos Remaining",end='\r')

        if p == "kevin_bacon_mode":
            if parameter != "false":
                #print(f"Link {parameter.upper()} Library Size:",end=' ')
                save_last = True
                # Filter music video library by Kevin Bacon rules
                if last_kevin_bacon is not None:
                    print(f"Last Linked Title: {last_kevin_bacon[1]['title']}")
                    filtered_library, link_details = filter_music_videos_library(music_video_lib, parameter, last_kevin_bacon)
                    
                    if len(filtered_library) > 1:
                        music_video_lib = filtered_library
                        print(f"{len(filtered_library)} Music Videos Found")
                    else:
                        print(f"\rLink {parameter.upper()} Match NOT FOUND") 
                        link_details = None
                else:
                    link_details = None
    print(f"\nSelecting Music Video from {len(music_video_lib)} options.")
    movie_choice = random.choice(list(music_video_lib.keys()))
    if link_details:
        #print(link_details)
        return movie_choice, link_details[movie_choice]
    else:
        return movie_choice, None

def filter_movies_by_duration(movie_library, duration_range):
    filtered_movies = {}
    min_duration = duration_range[0]
    max_duration = duration_range[1]
    
    for movie_id, movie_info in movie_library.items():
        for file_info in movie_info.get('files', []):
            duration_min = file_info.get('duration_min', None)
            if duration_min is not None and min_duration <= duration_min <= max_duration:
                # If duration is within the range, add the movie to the filtered dictionary
                filtered_movies[movie_id] = movie_info
                break  # Move to the next movie since we found a matching duration

    return filtered_movies

def get_similar_shows(show_id, show_library, schedule_template, start_time, next_start_time, start_date, existing_series_ids):
    if show_id:
        # Get a list of shows that are similar and fit within the block restrictions
        base_show = show_library[show_id]
        show_genres = base_show['genre']
        if isinstance(show_genres,str):
            show_genres = [show_genres]
        show_studios = base_show['studio']
        if isinstance(show_studios,str):
            show_studios = [show_studios]
        show_year = base_show['year']
    else:
        show_genres = []
    
    allowed_genres = []
    forbidden_genres = []
    allowed_ratings = []
    forbidden_ratings = []
    allowed_decades = []
    forbidden_decades = []
    first_start = None
    for b, block in schedule_template.items():
        if first_start is None:
            first_start = block['start_time']
        block_complexity = block['complexity']
        #print(json.dumps(block,indent=4))
        try:
            block_start = datetime.datetime.strptime(block['start_time'], '%H:%M')
        except ValueError:
            block_start = datetime.datetime.strptime(block['start_time'], '%H:%M:%S')
        try:
            block_end = datetime.datetime.strptime(block['end_time'], '%H:%M')
        except ValueError:
            block_end = datetime.datetime.strptime(block['end_time'], '%H:%M:%S')
        try:
            first_start_start = datetime.datetime.strptime(first_start, '%H:%M')
        except ValueError:
            first_start_start = datetime.datetime.strptime(first_start, '%H:%M:%S')
        if block_end < first_start_start:
            block_end += datetime.timedelta(days=1)
        if block_start < start_time < next_start_time <= block_end:
            in_block = b
            for a_g in block['allowed_genres'].split(','):
                allowed_genres.append(a_g.strip())
            for f_g in block['forbidden_genres'].split(','):
                forbidden_genres.append(f_g.strip())
            for a_r in block['allowed_ratings'].split(','):
                allowed_ratings.append(a_r.strip().split(':')[-1])
            for f_r in block['forbidden_ratings'].split(','):
                forbidden_ratings.append(f_r.strip().split(':')[-1])
            for a_d in block['allowed_decades'].split(','):
                allowed_decades.append(a_d.strip())
            for f_d in block['forbidden_decades'].split(','):
                forbidden_decades.append(f_d.strip())
            break
    
    filtered_genres_list = list(set(show_genres).intersection(allowed_genres))
    filtered_genres_list = [x for x in filtered_genres_list if x not in forbidden_genres]
    matching_shows = show_library
    if len(filtered_genres_list) > 0:
        matching_shows = from_filter(matching_shows, filtered_genres_list, 'genre')
    if len(forbidden_genres) > 0:
        matching_shows = from_filter(matching_shows, forbidden_genres, 'genre', include=False)

    if len(forbidden_ratings) > 0:
        matching_shows = from_ratings(matching_shows, forbidden_ratings, include=False)
    else:
        matching_shows = from_ratings(matching_shows, allowed_ratings)
        
    preferred_year_range = [int(show_year[:3]+'0'), int(show_year[:3]+'9')]
    
    similar_shows = {}
    for s, show in matching_shows.items():
        if preferred_year_range[0] <= int(show['year']) <= preferred_year_range[1]:
            if s not in existing_series_ids:
                similar_shows[s] = show
    if len(similar_shows) < 1:
        for s, show in matching_shows.items():
            # Check all allowable decade ranges
            for decade in allowed_decades:
                if decade not in forbidden_decades:
                    year_range = [int(decade[:3]+'0'), int(decade[:3]+'9')]
                    if year_range[0] <= int(show['year']) <= year_range[1]:
                        if s not in existing_series_ids:
                            similar_shows[s] = show
    return similar_shows

def get_same_rating_shows(show_id, show_library, schedule_template, start_time, next_start_time, start_date, existing_series_ids):
    allowed_genres = []
    forbidden_genres = []
    allowed_ratings = []
    forbidden_ratings = []
    allowed_decades = []
    forbidden_decades = []
    first_start = None
    if show_id:
        # Get a list of shows that are similar and fit within the block restrictions
        base_show = show_library[show_id]
        show_rating = base_show.get('certification')
        if show_rating is not None:
            allowed_ratings.append(show_rating.split(':')[-1].strip())
            
    for b, block in schedule_template.items():
        if first_start is None:
            first_start = block['start_time']
        block_complexity = block['complexity']
        #print(json.dumps(block,indent=4))
        try:
            block_start = datetime.datetime.strptime(block['start_time'], '%H:%M')
        except ValueError:
            block_start = datetime.datetime.strptime(block['start_time'], '%H:%M:%S')
        try:
            block_end = datetime.datetime.strptime(block['end_time'], '%H:%M')
        except ValueError:
            block_end = datetime.datetime.strptime(block['end_time'], '%H:%M:%S')
        try:
            first_start_start = datetime.datetime.strptime(first_start, '%H:%M')
        except ValueError:
            first_start_start = datetime.datetime.strptime(first_start, '%H:%M:%S')
        if block_end < first_start_start:
            block_end += datetime.timedelta(days=1)
        if block_start < start_time < next_start_time <= block_end:
            in_block = b
            for a_g in block['allowed_genres'].split(','):
                allowed_genres.append(a_g.strip())
            for f_g in block['forbidden_genres'].split(','):
                forbidden_genres.append(f_g.strip())
            for a_d in block['allowed_decades'].split(','):
                allowed_decades.append(a_d.strip())
            for f_d in block['forbidden_decades'].split(','):
                forbidden_decades.append(f_d.strip())
            break
    
    filtered_genres_list = allowed_genres
    filtered_genres_list = [x for x in filtered_genres_list if x not in forbidden_genres]
    matching_shows = show_library
    if len(filtered_genres_list) > 0:
        matching_shows = from_filter(matching_shows, filtered_genres_list, 'genre')
    if len(forbidden_genres) > 0:
        matching_shows = from_filter(matching_shows, forbidden_genres, 'genre', include=False)

    matching_shows = from_ratings(matching_shows, allowed_ratings)
    if len(matching_shows) < 1:
        matching_shows = show_library

    similar_shows = {}
    for s, show in matching_shows.items():
        # Check all allowable decade ranges
        for decade in allowed_decades:
            if decade not in forbidden_decades:
                year_range = [int(decade[:3]+'0'), int(decade[:3]+'9')]
                if year_range[0] <= int(show['year']) <= year_range[1]:
                    if s not in existing_series_ids:
                        similar_shows[s] = show

    return similar_shows
    
def get_random_shows(show_library, schedule_template, start_time, next_start_time, start_date, existing_series_ids=[]):
    
    allowed_genres = []
    forbidden_genres = []
    allowed_ratings = []
    forbidden_ratings = []
    allowed_decades = []
    forbidden_decades = []
    first_start = None
    for b, block in schedule_template.items():
        block_complexity = block['complexity']
        if block['start_time'].count(':') == 2:
            block_start = datetime.datetime.strptime(block['start_time'], '%H:%M:%S')
        else:
            block_start = datetime.datetime.strptime(block['start_time'], '%H:%M')
        if first_start is None:
            first_start = block_start
        if block['end_time'].count(':') == 2:
            block_end = datetime.datetime.strptime(block['end_time'], '%H:%M:%S')
        else:
            block_end = datetime.datetime.strptime(block['end_time'], '%H:%M')
        if block_end < first_start:
            block_end += datetime.timedelta(days=1)
        if block_start < start_time < next_start_time <= block_end:
            in_block = b
            for a_g in block['allowed_genres'].split(','):
                allowed_genres.append(a_g.strip())
            for f_g in block['forbidden_genres'].split(','):
                forbidden_genres.append(f_g.strip())
            for a_r in block['allowed_ratings'].split(','):
                allowed_ratings.append(a_r.strip().split(':')[-1])
            for f_r in block['forbidden_ratings'].split(','):
                forbidden_ratings.append(f_r.strip().split(':')[-1])
            for a_d in block['allowed_decades'].split(','):
                allowed_decades.append(a_d.strip())
            for f_d in block['forbidden_decades'].split(','):
                forbidden_decades.append(f_d.strip())
            break
    
    #filtered_genres_list = [x for x in filtered_genres_list if x not in allowed_genres]
    matching_shows = show_library
    #print(f"SHOW LIBRARY: {len(show_library)}")
    if len(allowed_genres) > 0 and allowed_genres[0] != '':
        matching_shows = from_filter(matching_shows, allowed_genres, 'genre')
    #print(f"MATCHING SHOWS: {len(matching_shows)}")    
    if len(forbidden_genres) > 0 and forbidden_genres[0] != '':
        matching_shows = from_filter(matching_shows, forbidden_genres, 'genre', include=False)
    #print(f"MATCHING SHOWS: {len(matching_shows)}")

    if len(forbidden_ratings) > 0 and forbidden_ratings[0] != '':
        matching_shows = from_ratings(matching_shows, forbidden_ratings, include=False)
    
    random_shows = {}
    #print(f"MATCHING SHOWS: {len(matching_shows)}")
    for s, show in matching_shows.items():
        # Check all allowable decade ranges
        if len(allowed_decades) > 0 and allowed_decades[0] != '':
            for decade in allowed_decades:
                if decade not in forbidden_decades:
                    year_range = [int(decade[:3]+'0'), int(decade[:3]+'9')]
                    if year_range[0] <= int(show['year']) <= year_range[1]:
                        if s not in existing_series_ids:
                            random_shows[s] = show
        else:
            random_shows[s] = show
    return random_shows

def determine_start_date(existing_daily_schedule):
    # If existing daily schedule provided, find the latest scheduled date and set the start date as the next day
    if existing_daily_schedule:
        latest_date = max(existing_daily_schedule.keys())
        start_date = datetime.datetime.strptime(latest_date, "%Y-%m-%d").date() + datetime.timedelta(days=1)
    else:
        # If no existing schedule, start with today
        start_date = datetime.datetime.today().date()
    
    # Get the day of the week for the start date
    day_of_week = start_date.strftime("%A")
    
    return start_date.strftime("%Y-%m-%d"), day_of_week

def save_last_episode_details(file_path, new_details, show_id):
    # Initialize an empty dictionary
    existing_details = {}

    # Check if the file exists
    if os.path.exists(file_path):
        # Load the existing data
        with open(file_path, 'r', encoding="utf-8") as file:
            existing_details = json.load(file)
    
    # Update the existing details with new details (will only store one key-value pair)
    existing_details[show_id] = new_details

    # Write the updated details back to the file
    with open(file_path, 'w') as file:
        json.dump(existing_details, file, indent=4)

def get_last_episode(show_id, file_path, episode_override=False):
    files = show_library[show_id]['files']
    episode_keys = list(files.keys())
    last_episodes = load_json_file(file_path)
    if last_episodes is None:
        episode_override = "random"
    if episode_override is False:
        if show_id in last_episodes:
            last_episode = last_episodes[show_id]
            try:
                last_episode_index = episode_keys.index(last_episode['episode_path'])
            except ValueError as e:
                print("ValueError:",e)
                last_episode = None
                last_episode_index = None
            
        else:
            last_episode_id, last_episode = random_episode(files)
            if last_episode is not False:
                last_episode_index = episode_keys.index(last_episode_id)
            else:
                last_episode_index = False

    elif episode_override == "random":
        last_episode_id, last_episode = random_episode(files)
        last_episode_index = episode_keys.index(last_episode_id)
    elif episode_override == "first":
        last_episode = None
        last_episode_index = None
    
    return last_episode, last_episode_index, episode_keys, files

def get_last_episode_old(show_id, daily_schedule, episode_override, channel_dir, last_episode_file, existing_daily_schedule=None):
    # Select Values: first, sequential, rerun, random
    # Load show library
    #show_library = load_json_file(show_json_path)
    files = show_library[show_id]['files']
    #print(show_id)
    # If existing_daily_schedule provided, find the last scheduled episode
    last_episode = None
    last_episode_details = {}

    # Check current schedule for the last scheduled episode, if it exists
    for time, content in daily_schedule.items():
        if 'series' in content['type'] and content['type']['series']['show_key'] == show_id and content['type']['series']['episode_mode'] == "sequential":
            last_episode = content['type']['series']['key']

    if existing_daily_schedule:
        for d, existing_schedule in existing_daily_schedule.items():
            for time, content in existing_schedule.items():
                if 'series' in content['type'] and content['type']['series']['show_key'] == show_id and content['type']['series']['episode_mode'] == "sequential":
                    #print(content['type']['series']['show_key'])
                    last_episode = content['type']['series']['key']

    if episode_override == "random":
        last_episode, last_episode_index = random_episode(files)
    elif episode_override == "first":
        last_episode = None
    
    episode_keys = list(files.keys())
    if last_episode:
        last_episode_index = episode_keys.index(last_episode)
        #print(show_library[show_id]['files'][last_episode])
        last_episode_details[show_id] = {
            'title': show_library[show_id]['title'],
            'episode_path': last_episode,
            'season_number': int(show_library[show_id]['files'][last_episode]['episode_details'][0]['season']),
            'episode_number': int(show_library[show_id]['files'][last_episode]['episode_details'][0]['episode'])
        }
        print(f"LAST EPISODE - S{show_library[show_id]['files'][last_episode]['episode_details'][0]['season']}E{show_library[show_id]['files'][last_episode]['episode_details'][0]['episode']} - {show_library[show_id]['files'][last_episode]['episode_details'][0]['title']}")
    else:
        last_episode_index = None
        
    #save_last_episode_details(last_episode_file, last_episode_details)
    
    return last_episode, last_episode_index, episode_keys, files

def next_episode(show_id, last_episode, episode_keys, files):
    #print(json.dumps({'show_id':show_id,'last_episode':last_episode},indent=4))

    # If there is no last episode, select the first episode
    if last_episode is None:
        first_episode_id = min(files.keys())
        return first_episode_id, files[first_episode_id]     

    # If there is a last episode, get the information
    if last_episode.get('episode_details',None) is not None:
        last_episode_season = int(last_episode['episode_details'][0].get('season',0))
        last_episode_number = int(last_episode['episode_details'][0].get('episode',0))
    else:
        last_episode_season = int(last_episode.get('season_number',0))
        last_episode_number = int(last_episode.get('episode_number',0))

    # Use the last episode information to select the next episode
    for episode_id, episode_info in files.items():
        episode_season = int(episode_info['episode_details'][0].get('season'),0)
        episode_number = int(episode_info['episode_details'][0].get('episode',0))
        
        if episode_season == last_episode_season and episode_number == last_episode_number+1:
            return episode_id, episode_info
        if episode_season == last_episode_season+1 and episode_number == 1:
            return episode_id, episode_info

    # If no next episode found, select first        
    for episode_id, episode_info in files.items():
        if episode_season == 1 and episode_number == 1:
            return episode_id, episode_info
        else:
            first_episode_id = min(files.keys())
            return first_episode_id, files[first_episode_id]

def random_episode(files):
    try:
        random_episode_id = random.choice(list(files.keys()))
        return random_episode_id, files[random_episode_id]
    except IndexError:
        return False, False

def schedule_series(series_dict, start_time, next_start_time, episode_info, daily_schedule, episode_mode, preempted=False):
    # Implementation to schedule a TV series based on provided parameters
    # This function will return the scheduled series details
    show_title = episode_info['episode_details'][0]['showtitle']
    print(show_title)
    episode_title = episode_info['episode_details'][0]['title']
    season_number = episode_info['episode_details'][0]['season']
    episode_number = episode_info['episode_details'][0]['episode']
    episode_duration = int(episode_info['episode_details'][0]['fileinfo']['streamdetails']['video']['durationinseconds'])
    try:
        if start_time < datetime.datetime.strptime(list(daily_schedule.keys())[0], '%H:%M:%S.%f'):
            start_time += datetime.timedelta(days=1)
    except IndexError:
        pass
    
    if preempted and len(list(daily_schedule.keys())) > 0:
        
        previous_end_time = datetime.datetime.strptime(daily_schedule[list(daily_schedule.keys())[-1]]['end_time'], '%H:%M:%S.%f')
        
        if previous_end_time < datetime.datetime.strptime(list(daily_schedule.keys())[0], '%H:%M:%S.%f'):
            previous_end_time += datetime.timedelta(days=1)
        
        if start_time < previous_end_time:
            # Calculate start time or cancel
            time_over = (previous_end_time - start_time).total_seconds()
            time_over_ms = time_over*1000
            print(f"TIME OVER: {time_over} seconds")
            new_start_time = (start_time + datetime.timedelta(microseconds=time_over_ms*1000+1))

            max_drift_seconds = (next_start_time - start_time).total_seconds() - episode_duration
            print(f"MAX DRIFT: {max_drift_seconds} seconds")
            if time_over_ms > (max_drift_seconds + (episode_duration/3))*1000:
                print(f"SKIPPING: {start_time}")
                return start_time, None
            new_end_time = new_start_time + datetime.timedelta(seconds=episode_duration)
            if new_end_time > next_start_time:
                # Set Preempt times
                new_end_time = next_start_time - datetime.timedelta(seconds=1)
                new_start_time = previous_end_time + datetime.timedelta(seconds=1)
                new_episode_duration = (new_end_time - new_start_time).total_seconds()
                preempt = episode_duration - new_episode_duration
                episode_duration = new_episode_duration
            else:
                # Set Delay times
                time_to_next = (next_start_time - new_end_time).total_seconds()
                print(f"TO NEXT: {time_to_next}")
                
                minutes_to_round = (5 - (new_start_time.minute % 5)) % 5
                seconds_to_round = minutes_to_round*60
                if time_to_next > seconds_to_round and minutes_to_round != 0:
                    print(f"Time to next: {time_to_next}\nMinutes to Round: {minutes_to_round}")
                    new_start_time = new_start_time + datetime.timedelta(minutes=minutes_to_round)
                    new_start_time = new_start_time.replace(second=0, microsecond=0)
                elif time_to_next > 60:
                    print(f"Time to next: {time_to_next}")
                    new_start_time = new_start_time + datetime.timedelta(minutes=1)
                    new_start_time = new_start_time.replace(second=0, microsecond=0)
                preempt = "delay"
            end_datetime = new_start_time + datetime.timedelta(seconds=episode_duration)
            start_time = new_start_time
        else:
            end_datetime = start_time + datetime.timedelta(seconds=episode_duration)
            preempt = False
    else:
        end_datetime = start_time + datetime.timedelta(seconds=episode_duration)
        preempt = False
    end_time = end_datetime.strftime('%H:%M:%S.%f') # Format end time         
    cast = []
    try:
        for actor in series_dict['actor']:
            
            try:
                actor_name = actor['name']

            except (KeyError,TypeError):
                actor_name = None            
            try:

                role_name = actor['role']
            except (KeyError,TypeError):
                role_name = None
            cast.append({'name':actor_name, 'role':role_name})
    except KeyError:
        pass
    try:
        video_source = episode_info['source']
    except KeyError:
        video_source = None
    premiere_date = episode_info['episode_details'][0].get('aired','')
    if premiere_date != '':
        premiere_year = episode_info['episode_details'][0].get('aired','')
    else:
        premiere_year = ''
    scheduled_content = {
        "title": f"{show_title} S{int(season_number):02d}E{int(episode_number):02d} - {episode_title}",
        "start_time": start_time.strftime('%H:%M:%S.%f'),
        "end_time": end_time,
        "type": {
            "series": {
                "show_key": series_dict['id'],
                "key": episode_info['episode_path'],
                "show_title": show_title,
                "episode_title": episode_title,
                "season_number": season_number,
                "episode_number": episode_number,
                "episode_mode": episode_mode,
                "year": premiere_year,
                "date": premiere_date,
                "studio": episode_info['episode_details'][0].get('studio',None),
                "genre": series_dict['genre'],
                "cast": cast,
                "source": video_source,
            }
        },
        "duration_ms": episode_duration * 1000,
        "duration_s": episode_duration, # Duration in seconds
        "duration_min": episode_duration // 60, # Duration in minutes
        "is_preempted": preempt,
        "summary": episode_info['episode_details'][0]['plot'],
    }
    print(f"{scheduled_content['title']}")
    return start_time, scheduled_content

def save_daily_schedule(schedule, schedule_dir, date=datetime.datetime.now().strftime("%Y-%m-%d")):
    # Construct the path to the daily schedule file
    daily_schedule_path = os.path.join(schedule_dir, "daily_schedule.json")
    
    # Load existing daily schedule if it exists
    if os.path.exists(daily_schedule_path):
        daily_schedule = load_json_file(daily_schedule_path)
    else:
        daily_schedule = {}
    
    # Update or add the current schedule under the current date key
    daily_schedule = schedule
    
    # Save the updated daily schedule to file
    #print(daily_schedule)
    with open(daily_schedule_path, "w") as file:
        json.dump(daily_schedule, file, indent=4)

def generate_daily_schedules(channels_dir, number_of_days=7, single_channel=False):

    # Get list of channel subdirectories sorted numerically then alphabetically
    channel_subdirs = sorted(
        [d for d in os.listdir(channels_dir) if os.path.isdir(os.path.join(channels_dir, d))],
        key=lambda x: (
            int(x.split()[0]),  # Sort by the numeric part before any space
            x.split()[1] if len(x.split()) > 1 else ""  # Sort alphabetically by the part after the space (if present)
        )
    )

    # Get the list of dates using the number_of_days parameter
    dates_list = get_dates(number_of_days)

    # Iterate through each channel directory
    for channel_dir in channel_subdirs:
        if single_channel is not False and single_channel != channel_dir:
            continue
        # Construct the path to the details file
        details_path = os.path.join(channels_dir, channel_dir, "details.json")
        if os.path.exists(details_path):
            validate_details(details_path)
        else:
            generate_details(details_path, channel_dir)

        channel_schedule_file = os.path.join(channels_dir, channel_dir, "schedule.json")
        existing_schedule_file = os.path.join(channels_dir, channel_dir, "daily_schedule.json")
        channel_path = os.path.join(channels_dir, channel_dir)
        if os.path.exists(channel_schedule_file):
            print(f"Processing schedule for channel: {channel_dir}")
            schedule = load_json_file(channel_schedule_file)
            #print(channel_schedule_file)
            if os.path.exists(existing_schedule_file):
                loaded_daily_schedule = load_json_file(existing_schedule_file)
                episode_override = False
                print(f"Daily Schedule Length is {len(loaded_daily_schedule)} days. Maximum retained length is 90.")
                existing_daily_schedule = dict(list(loaded_daily_schedule.items())[-90:])

            else:
                existing_daily_schedule = None
                episode_override = "random"
            
            # Check if any existing daily schedule dates are equal to or later than the generated dates
            if existing_daily_schedule:
                last_existing_date = max(existing_daily_schedule.keys())
                last_existing_date = datetime.datetime.strptime(last_existing_date, "%Y-%m-%d")
            else:
                last_existing_date = datetime.datetime.now() - datetime.timedelta(days=1)
            for date in dates_list:
                date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
                if date_obj <= last_existing_date.date():
                    continue  # Skip this iteration
                else:
                    daily_schedule = schedule_daily_content(schedule, channel_schedule_file, episode_override, channel_path, existing_daily_schedule)
                    # Optionally, save or print the generated daily schedule for this channel
                    #print(json.dumps(daily_schedule, indent=4))
                    save_daily_schedule(daily_schedule, os.path.join(channels_dir,channel_dir))
    #print(schedule['Template'])
    return schedule['Template']

def get_dates(num_days,start_date=None):
    # Use today's date if start_date is not provided
    if start_date is None:
        start_date = datetime.datetime.now().date()

    # Create a list to store the dates
    dates_list = []

    # Iterate through the range of days
    for i in range(num_days):
        # Calculate the date for the current iteration
        current_date = start_date + datetime.timedelta(days=i)
        # Append the date to the list in YYYY-MM-DD format
        dates_list.append(current_date.strftime("%Y-%m-%d"))

    return sorted(dates_list)

def get_interstitials(date, time_range, daily_schedule, movie_library, show_library, interstitial_libraries, schedule_template, active_schedule, channel_number):
    selected_interstitials = {}
    block_settings = {}
    # Initialize a list to store interstitial videos that fit within the remaining time
    fitting_interstitials = []
    all_interstitials = []
    weights_defaults = {
        "commercials": "1",
        "tags": "0",
        "year": "0",
        "trailers": "1",
        "genre": "0",
        "date": "0",
        "music_videos": "1",
        "studio": "0",
        "scheduled": "0",
        "other_videos": "1",
        "actor": "0"
        }
    previous_end_time, next_start_time = time_range
    if next_start_time > previous_end_time:
        #print(f"{previous_end_time} - {next_start_time}")
        for block_key in schedule_template.keys():
            try:
                block_start_time = datetime.datetime.strptime(schedule_template[block_key]['start_time'],'%H:%M').replace(year=previous_end_time.year,month=previous_end_time.month, day=previous_end_time.day)
            except ValueError:
                block_start_time = datetime.datetime.strptime(schedule_template[block_key]['start_time'],'%H:%M:%S').replace(year=previous_end_time.year,month=previous_end_time.month, day=previous_end_time.day)
            try:
                block_end_time = datetime.datetime.strptime(schedule_template[block_key]['end_time'],'%H:%M').replace(year=previous_end_time.year,month=previous_end_time.month, day=previous_end_time.day)
            except ValueError:
                block_end_time = datetime.datetime.strptime(schedule_template[block_key]['end_time'],'%H:%M:%S').replace(year=previous_end_time.year,month=previous_end_time.month, day=previous_end_time.day)

            if block_end_time < block_start_time:
                if block_end_time < block_start_time < previous_end_time:
                    block_end_time += datetime.timedelta(days=1)
                    next_start_time += datetime.timedelta(days=1)
                elif previous_end_time < block_end_time < block_start_time:
                    block_start_time -= datetime.timedelta(days=1)

            #print(f"{block_start_time} - {block_end_time}")
            if (block_end_time > block_start_time and previous_end_time >= block_start_time and previous_end_time <= block_end_time) or (block_end_time < block_start_time and previous_end_time >= block_start_time  and previous_end_time <= block_end_time):
                try:
                    weights = schedule_template[block_key]['interstitials']
                except KeyError:
                    print("USING DEFAULT WEIGHT VALUES")
                    weights = weights_defaults
                try:
                    block_settings = schedule_template[block_key]
                except UnboundLocalError:
                    block_settings = {}
                break

        #print(json.dumps(block_settings,indent=4))
        remaining_time = (next_start_time - previous_end_time).total_seconds()*1000
        total_duration = sum(
            subdict.get('files', [{}])[0].get('duration_ms', 0) 
            for interstitial_library in interstitial_libraries 
            if isinstance(interstitial_library[1], dict) 
            for subdict in interstitial_library[1].values() 
            if isinstance(subdict.get('files', []), list) and len(subdict.get('files', [])) > 0 and isinstance(subdict.get('files', [])[0], dict)
        )


        print(f"Total duration: {datetime.timedelta(seconds=total_duration/1000)}")
        print(f"TIME TO FILL: {datetime.timedelta(seconds=remaining_time/1000)}")

        # Iterate through each interstitial library
        number_of_interstitials = 0
        for library_name, library in interstitial_libraries:
            number_of_interstitials += len(library)
        if remaining_time > 1000:
            for i, interstitial_lib in enumerate(interstitial_libraries):
                interstitial_library_name, interstitial_library = interstitial_lib
                # Iterate through each interstitial video in the library
                for loop, video_entry in enumerate(interstitial_library.items()):
                    video_id, video_info = video_entry
                    # Filter out existing entries if the total duration exceeds the time to fill
                    active_schedule_key_match = []
                    for time_, data in active_schedule.items():
                        key = None
                        if 'type' in data:
                            interstitial_data = data['type'].get('interstitial', {})
                            if interstitial_data:
                                key = interstitial_data.get('key')
                        if key != "None" and key != None and key == video_id:
                            active_schedule_key_match.append(key)

                    if len(active_schedule_key_match) > 0:
                        if total_duration > remaining_time:
                            total_duration -= remaining_time
                            continue
                    
                    all_interstitials.append((video_id, video_info, i, interstitial_library_name.replace(' json','')))

            print(f"\nAll Interstitials: {len(all_interstitials)}")
            random.shuffle(all_interstitials)
            start_loop = datetime.datetime.now()
            for loop, interstitial in enumerate(all_interstitials):
                video_id, video_info, i, i_library_name = interstitial
                filter_settings = {
                    'allowed_genres': block_settings.get('allowed_genres','').split(','),
                    'forbidden_genres': block_settings.get('forbidden_genres','').split(','),
                    'allowed_ratings': block_settings.get('allowed_ratings','').split(','),
                    'forbidden_ratings': block_settings.get('forbidden_ratings','').split(','),
                    'allowed_decades': block_settings.get('allowed_decades','').split(','),
                    'forbidden_decades': block_settings.get('forbidden_decades','').split(','),
                }
                
                # Filter based on block settings
                video_tags = video_info['movie'].get('tag',[])
                video_year = video_info['movie'].get('year',None)
                trailer_rating = video_info['movie'].get('certification',None)
                if trailer_rating:
                    trailer_rating = trailer_rating.split(' / ')[0].split(':')[1].strip()
                if filter_settings['forbidden_genres'] != []:
                    if set(map(str.lower,filter_settings['forbidden_genres'])).intersection(video_tags):
                        continue
                if filter_settings['allowed_decades'] != None:
                    skip = True
                    for decade in filter_settings['allowed_decades']:
                        if video_year[:3] == decade[:3] or decade == "":
                            skip = False
                    if skip is True:
                        continue
                if filter_settings['forbidden_decades'] != None:
                    skip = False
                    for decade in filter_settings['forbidden_decades']:
                        if video_year[:3] == decade[:3]:
                            skip = True
                    if skip is True:
                        continue                                        
                if filter_settings['allowed_ratings'] != None:
                    if trailer_rating and trailer_rating not in filter_settings['allowed_ratings'] and filter_settings['allowed_ratings'] != "":
                        continue
                if filter_settings['forbidden_ratings'] != None:
                    if trailer_rating and trailer_rating in filter_settings['forbidden_ratings'] and filter_settings['forbidden_ratings'] != "":
                        continue                                        
                    
                # Check for similarities with scheduled content
                similarity_score = calculate_similarity(date, video_info, time_range, daily_schedule, show_library, movie_library, weights, i_library_name.lower().strip())
                # Add the video to fitting_interstitials along with its similarity score
                fitting_interstitials.append((video_id, similarity_score, i))
                
                now_loop = datetime.datetime.now()
                time_passed = (now_loop - start_loop).total_seconds()
                '''try:
                    print(f"Ch. {channel_number} | {datetime.timedelta(seconds=time_passed)} | {round((loop+1)/time_passed,1)}/s | Processing {loop+1} of {len(all_interstitials)} | {round(((loop+1)/len(all_interstitials))*100,1)}% | Score: {similarity_score}", end='\r')
                except ZeroDivisionError:
                    pass'''
    else:
        return {}
    # Sort fitting_interstitials based on similarity score in descending order
    fitting_interstitials.sort(key=lambda x: x[1], reverse=True)

    # Select a subset of fitting_interstitials 
    selected_ids = []
    remaining_time_ms = remaining_time
    ljust_len = 1
    for video_id, similarity_score, i in fitting_interstitials:
        try:
            #print(interstitial_libraries[i][1].keys())
            
            video_data = interstitial_libraries[i][1][video_id]
            #print(video_id)
            video_duration = video_data['files'][0]['duration_ms']
            video_string = f"{similarity_score} | {video_data['title']} - Duration: {video_duration/1000} seconds"
            #print(video_string.ljust(ljust_len),flush=True,end='\n')
            ljust_len = len(video_string)
        except TypeError:
            #print("\nTYPE ERROR")
            #traceback.print_exc()
            continue
        except IndexError:
            print(f"Index error in {video_id}")
            continue
        
        if video_duration <= remaining_time:
            selected_ids.append((video_id, i, similarity_score))
            #remaining_time_ms -= video_duration
        '''if remaining_time_ms < 500:
            break'''
    print(f"\nSorted Interstitials: {len(selected_ids)}")
    # Populate selected_interstitials with the selected interstitial videos
    min_score = 999999
    max_score = -999999
    for v,i,s in selected_ids:
        if s < min_score:
            min_score = s
        if s > max_score:
            max_score = s
    print(f"SCORE RANGE: {min_score} - {max_score}")
    
    for video_id, i, score in selected_ids:
        selected_interstitials[video_id] = (i, interstitial_libraries[i][1][video_id],score)
    return selected_interstitials

def preprocess_daily_schedule(daily_schedule):
    for date, time_schedule in daily_schedule.items():
        for time, schedule in time_schedule.items():
            schedule['end_time_dt'] = datetime.datetime.strptime(schedule['end_time'], '%H:%M:%S.%f')
            schedule['start_time_dt'] = datetime.datetime.strptime(schedule['start_time'], '%H:%M:%S.%f')

def calculate_similarity_slow(video_info, time_range, daily_schedule, show_library, movie_library, weights, i_library_name):
    preprocess_daily_schedule(daily_schedule)
    previous_end_time, next_start_time = time_range
    scheduled_before = None
    scheduled_after = None
    scheduled_dates = []  # Define scheduled_dates list here

    video_date_str = video_info['movie'].get('aired', None) or video_info['movie'].get('year', None)
    try:
        video_date = datetime.datetime.strptime(video_date_str, "%Y-%m-%d").date() if video_date_str else datetime.datetime.now().date()
    except ValueError:
        try:
            video_date = datetime.datetime.strptime(video_date_str[:4], "%Y").date() if video_date_str else datetime.datetime.now().date()
        except ValueError:
            video_date_str = video_info['movie'].get('dateadded')
            if video_date_str and video_date_str != "None":
                video_date = datetime.datetime.strptime(video_date_str, "%Y-%m-%d %H:%M:%S").date()
            else:
                video_date = datetime.datetime.now().date()

    for date, time_schedule in daily_schedule.items():
        daily_schedule_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()  # Move this line inside the loop
        for time, schedule in time_schedule.items():
            if schedule['end_time_dt'] == previous_end_time:
                scheduled_before = schedule
                if scheduled_after:
                    break
            elif schedule['start_time_dt'] == next_start_time:
                scheduled_after = schedule
                if scheduled_before:
                    break
        if scheduled_before and scheduled_after:
            break

    if scheduled_before:
        genre_list, studio_list, actor_list, tag_list, premiered_dates = extract_info(scheduled_before, show_library)
        scheduled_dates.extend(premiered_dates)

    if scheduled_after:
        genre_list, studio_list, actor_list, tag_list, premiered_dates = extract_info(scheduled_after, show_library)
        scheduled_dates.extend(premiered_dates)

    # Optimized similarity calculations
    tag_similarity = SequenceMatcher(None, ','.join(tag_list), ','.join(video_info.get('tag', []))).ratio()
    video_year = str(video_date.year)
    year_similarity = max(SequenceMatcher(None, video_year, str(year.year)).ratio() for year in scheduled_dates) if scheduled_dates else 0
    month_day_similarity = max(SequenceMatcher(None, str(video_date.month) + str(video_date.day), str(scheduled_date.month) + str(scheduled_date.day)).ratio() for scheduled_date in scheduled_dates) if scheduled_dates else 0
    genre_similarity = SequenceMatcher(None, ','.join(genre_list), ','.join(video_info.get('genre', []))).ratio()
    studio_similarity = max(SequenceMatcher(None, video_info.get('studio', ''), studio).ratio() for studio in studio_list) if studio_list else 0
    actor_similarity = SequenceMatcher(None, ','.join(actor_list), ','.join(video_info.get('actor', []))).ratio()
    scheduled_day_similarity = SequenceMatcher(None, str(video_date.month) + str(video_date.day), str(daily_schedule_date.month) + str(daily_schedule_date.day)).ratio()
    library_name = i_library_name.replace(" json", "").lower()
    library_score = {"commercials": weights.get('commercials', 0), "trailers": weights.get('trailers', 0), "music videos": weights.get('music_videos', 0), "other videos": weights.get('other_videos', 0)}.get(library_name, 0)
    weights = {key: int(value) for key, value in weights.items()}
    library_score = float(library_score)

    similarity_score = (
        (weights['scheduled'] / 100) * scheduled_day_similarity +
        (weights['tags'] / 100) * tag_similarity +
        (weights['year'] / 100) * year_similarity +
        (weights['date'] / 100) * month_day_similarity +
        (weights['genre'] / 100) * genre_similarity +
        (weights['studio'] / 100) * studio_similarity +
        (weights['actor'] / 100) * actor_similarity +
        library_score / 100
    )

    return similarity_score
    
def extract_info(schedule_item, show_library, movie_library, music_videos_library):
    genre_list = []
    studio_list = []
    actor_list = []
    tag_list = []
    premiered_dates = []

    type_info = schedule_item.get('type', {})
    if 'series' in type_info:
        show_key = type_info['series'].get('show_key')
        show_info = show_library.get(show_key, {})
        genre_list.extend(show_info.get('genre', []))
        studio_data = show_info.get('studio')
        if studio_data is not None:
            studio_list.extend(studio_data)
        #actor_list.extend(actor['name'] for actor in show_info.get('actor', []))
        actor_value = show_info.get('actor', [])
        try:
            if isinstance(actor_value, dict):
                actor_list.append(actor_value.get('name', ''))
            elif isinstance(actor_value, list):
                actor_list.extend(actor['name'] for actor in actor_value)
        except TypeError:
            print("TYPERROR!")
            print(actor_value)
            return
        premiered_date = show_info.get('premiered')
        #print(library[show_key])
    elif 'movie' in type_info:
        movie_key = type_info['movie'].get('key')
        movie_info = movie_library.get(movie_key, {})
        genre_list.extend(movie_info.get('genre', []))
        studio_list.extend(movie_info.get('studio', []))
        actor_value = movie_info.get('actor', [])
        if isinstance(actor_value, dict):
            actor_list.append(actor_value.get('name', ''))
        elif isinstance(actor_value, list):
            actor_list.extend(actor['name'] for actor in actor_value)
        tag_list.extend(movie_info.get('tag', []))
        premiered_date = movie_info.get('premiered')
        
    elif 'interstitial' in type_info:
        interstitial_key = type_info['interstitial'].get('key')
        interstitial_library = type_info['interstitial'].get('library')
        interstitial_info = interstitial_libraries.get(interstitial_library, {}).get(interstitial_key, {}).get('movie', {})
        tag_list.extend(interstitial_info.get('tag', []))
        premiered_date = interstitial_info.get('aired')
    elif 'music_video' in type_info:
        music_video_key = type_info['music_video'].get('key')
        music_video_info = music_videos_library.get(music_video_key, {}).get('movie', {})
        tag_list.extend(music_video_info.get('tag', []))
        premiered_date = music_video_info.get('aired')
    if premiered_date is not None and premiered_date != "None":
        try:
            premiered_dates.append(datetime.datetime.strptime(premiered_date, "%Y-%m-%d").date())
        except ValueError:
            try:
                premiered_dates.append(datetime.datetime.strptime(premiered_date, "%Y").date())
            except ValueError:
                print(premiered_date)

    return genre_list, studio_list, actor_list, tag_list, premiered_dates

def calculate_similarity(date_string, video_info, time_range, daily_schedule, show_library, movie_library, weights, i_library_name):
    previous_end_time, next_start_time = time_range

    # Initialize lists to store information from scheduled items
    genre_list = []
    studios_list = []
    actor_list = []
    tag_list = []

    # Initialize scheduled_before and scheduled_after
    scheduled_before = None
    scheduled_after = None

    # Iterate over daily_schedule items

    for time_schedule in daily_schedule[date_string].items():
        # Iterate over time_schedule items
        t, schedule = time_schedule
        # Extract the end_time and start_time from the schedule
        #print(json.dumps(time_schedule[1],indent=4))
        end_time = schedule['end_time']
        start_time = schedule['start_time']
        
        end_time_dt = datetime.datetime.strptime(f"{date_string} {end_time}", '%Y-%m-%d %H:%M:%S.%f')
        start_time_dt = datetime.datetime.strptime(f"{date_string} {start_time}", '%Y-%m-%d %H:%M:%S.%f')

        # Check if the current schedule matches previous_end_time
        #print(end_time_dt, previous_end_time)
        if end_time_dt == previous_end_time:
            scheduled_before = schedule

            # If both scheduled_before and scheduled_after are found, exit the loop
            if scheduled_after:
                break

        # Check if the current schedule matches next_start_time
        elif start_time_dt == next_start_time:
            scheduled_after = schedule

            # If both scheduled_before and scheduled_after are found, exit the loop
            if scheduled_before:
                break

        # Check if both scheduled_before and scheduled_after are found
        if scheduled_before and scheduled_after:
            break

    # Extract information from scheduled items before and after
    scheduled_dates = []  # Initialize list to store premiered dates
    daily_schedule_date = datetime.datetime.strptime(date_string, "%Y-%m-%d").date()

    if scheduled_before:
        genre_b, studio_b, actor_b, tag_b, premiered_dates_b = extract_info(scheduled_before, show_library, movie_library, music_videos_library)
        genre_list.extend(genre_b)
        studios_list.extend(studio_b)
        actor_list.extend(actor_b)
        tag_list.extend(tag_b)
        scheduled_dates.extend(premiered_dates_b)

    if scheduled_after:
        genre_a, studio_a, actor_a, tag_a, premiered_dates_a = extract_info(scheduled_after, show_library, movie_library, music_videos_library)
        genre_list.extend(genre_a)
        studios_list.extend(studio_a)
        actor_list.extend(actor_a)
        tag_list.extend(tag_a)
        scheduled_dates.extend(premiered_dates_a)

    # Convert video date to datetime object
    video_date_str = video_info['movie'].get('aired', None) or video_info['movie'].get('year', None)
    if video_date_str:
        try:
            video_date = datetime.datetime.strptime(video_date_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                video_date = datetime.datetime.strptime(video_date_str[:4], "%Y").date()
            except ValueError:
                try:
                    video_date = datetime.datetime.strptime(video_date_str, "%Y-%m-%d %H:%M:%S").date()
                except ValueError:
                    video_date = datetime.datetime.strptime("1970-01-01", "%Y-%m-%d").date()
    else:
        video_date = datetime.datetime.strptime("1970-01-01", "%Y-%m-%d").date()

    metadata_types = ['tag', 'genre', 'studio', 'actor', 'network']
    video_tags = []
    for md_type in metadata_types:
        video_tags.extend(video_info['movie'].get(md_type, []))

    # Convert lists to lowercase strings
    tag_list = [tag.lower() for tag in tag_list]
    genre_list = [genre.lower() for genre in genre_list]
    studios_list = [studio.lower() for studio in studios_list]
    actor_list = [actor.lower() for actor in actor_list]

    exclude_from_tags = set(genre_list) | set(studios_list) | set(actor_list)
    tag_list = [tag for tag in tag_list if tag not in exclude_from_tags]

    # Calculate similarity for tags
    tag_similarity = sum(1 for tag in tag_list if tag in video_tags)
    genre_similarity = sum(1 for genre in genre_list if genre in video_tags)
    studio_similarity = sum(1 for studio in studios_list if studio in video_tags)
    actor_similarity = sum(1 for actor in actor_list if actor in video_tags)
    
    # Calculate scheduled day similarity with sliding scale
    
    if video_date.month == daily_schedule_date.month and video_date.day == daily_schedule_date.day:
        scheduled_day_similarity = 1.1
    elif video_date.month == 1 and video_date.day == 1:
        scheduled_day_similarity = 0
    else:
        # Calculate the days remaining in the year from the video_date
        days_remaining_in_year = (datetime.date(video_date.year, 12, 31) - datetime.date(video_date.year, video_date.month, video_date.day)).days
        
        # Calculate the days remaining in the year from the daily_schedule_date
        days_remaining_in_year_schedule = (datetime.date(daily_schedule_date.year, 12, 31) - datetime.date(daily_schedule_date.year, daily_schedule_date.month, daily_schedule_date.day)).days
        
        # Get the maximum number of days in the year of the daily_schedule_date
        max_days_in_year = 366 if daily_schedule_date.year % 4 == 0 and (daily_schedule_date.year % 100 != 0 or daily_schedule_date.year % 400 == 0) else 365
        
        # Calculate the similarity based on the remaining days in the year
        scheduled_day_similarity = max(0.00, 1.0 - abs(days_remaining_in_year - days_remaining_in_year_schedule) / max_days_in_year)

    # Calculate year similarity
    year_similarity = 0
    video_year = video_date.year

    for year in scheduled_dates:
        #print(year.year)
        if video_year == year.year:
            year_similarity += 1.1
        else:
            year_difference = abs((video_year - year.year))
            year_similarity += max(0.0, 1.0 - (year_difference/5))

    # Calculate month and day similarity
    # Initialize the maximum similarity
    max_similarity = 0
    #print("\n",scheduled_dates,"\n")
    if scheduled_dates:
        for scheduled_date in scheduled_dates:
            #print(f"\n Video Date: {video_date.month}-{video_date.day}, Scheduled Date: {scheduled_date.month}-{scheduled_date.day}")
            # Compute the month-day difference
            month_difference = video_date.month - scheduled_date.month
            day_difference = video_date.day - scheduled_date.day
            total_difference = abs(month_difference * 30 + day_difference)
            
            # Calculate the similarity
            similarity = 1.0 - total_difference / 365
            
            # Update the maximum similarity
            if similarity > max_similarity:
                max_similarity = similarity
    else:
        max_similarity = 0
    month_day_similarity = max_similarity
    #print(f"\nM/D Score: {month_day_similarity}")
    # Calculate library score
    library_name = i_library_name.replace(" json", "").lower()
    library_score = {"commercials": weights.get('commercials', 0), "trailers": weights.get('trailers', 0), "music videos": weights.get('music_videos', 0), "other videos": weights.get('other_videos', 0)}.get(library_name, 0)

    # Convert weights dictionary values to integers
    weights = {key: int(value) for key, value in weights.items()}

    library_score = float(library_score)
    # Combine and weight the similarity scores
    similarity_score = (
        weights['scheduled'] / 10 * scheduled_day_similarity +
        weights['tags'] / 10 * tag_similarity +
        weights['year'] / 10 * year_similarity +
        weights['date'] / 10 * month_day_similarity +
        weights['genre'] / 10 * genre_similarity +
        weights['studio'] / 10 * studio_similarity +
        weights['actor'] / 10 * actor_similarity +
        library_score / 10 + random.randint(1,10) / 10
    )

    #print("{:.5f}".format(tag_similarity*weights['tags'] / 10),'|',"{:.5f}".format(genre_similarity*weights['genre']),'|',"{:.5f}".format(studio_similarity*weights['studio']/10),'|',"{:.5f}".format(actor_similarity*weights['actor']/10),'|',"{:.5f}".format(library_score),'|',"{:.5f}".format(scheduled_day_similarity*weights['scheduled'] / 10),'|',"{:.5f}".format(year_similarity*weights['year']/10),'|',"{:.5f}".format(month_day_similarity*weights['date']/10),'  |  ',"{:.5f}".format(similarity_score))
    '''if any(score > 0 for score in [tag_similarity, genre_similarity, studio_similarity, actor_similarity,scheduled_day_similarity,year_similarity,month_day_similarity]):
        print("\n")
        time.sleep(1)'''

    return (similarity_score * 10 // 1) / 10

def create_active_schedule(date_string, daily_schedule_path, movie_library, show_library, interstitial_libraries, schedule_template):
    active_schedule = {}
    # Define column widths for each piece of information
    time_width = 30
    duration_width = 6
    aired_width = 14
    library_width = 15
    title_width = 60
    network_width = 15
    score_width = 20
    daily_schedule = load_json_file(daily_schedule_path)
    previous_end_time = None
    first_start_time = None
    
    for start, schedule_entry in daily_schedule[date_string].items():
        if first_start_time == None:
            first_start_time = schedule_entry['start_time']
            print("\n-------------------------------------\n")
            print(f"START: {schedule_entry['start_time']}\n{schedule_entry['title']}")
        if previous_end_time == None:
            previous_end_time = schedule_entry['end_time']
            active_schedule[f"{date_string} {start}"] = schedule_entry
            continue
        else:
            end_time = schedule_entry['end_time']
        
        print(f"END: {previous_end_time}")
        
        print("\n-------------------------------------\n")
        previous_end_time = datetime.datetime.strptime(f"{date_string} {previous_end_time}", '%Y-%m-%d %H:%M:%S.%f')
        next_start_time = datetime.datetime.strptime(f"{date_string} {schedule_entry['start_time']}", '%Y-%m-%d %H:%M:%S.%f')
        
        if next_start_time < datetime.datetime.strptime(f"{date_string} {first_start_time}", '%Y-%m-%d %H:%M:%S.%f'):
            next_start_time += datetime.timedelta(days=1)
        if previous_end_time < datetime.datetime.strptime(f"{date_string} {first_start_time}", '%Y-%m-%d %H:%M:%S.%f'):
            previous_end_time += datetime.timedelta(days=1)
        
        interstitials = get_interstitials(date_string, (previous_end_time, next_start_time), daily_schedule, movie_library, show_library, interstitial_libraries, schedule_template, active_schedule, os.path.basename(os.path.dirname(daily_schedule_path)).lstrip('0'))
        remaining_time = (next_start_time - previous_end_time).total_seconds()*1000
        
        total_duration = sum(subdict['duration_ms'] for key, (i, interstitial, score) in interstitials.items() if isinstance(interstitial, dict) for subdict in interstitial['files'])
        print(f"ALL DURATION: {datetime.timedelta(seconds=total_duration/1000)}")
        selected_interstitials = {}

        highest_score_items = {}
        max_score = float('-inf')  # Start with the lowest possible value
        for key, value in interstitials.items():
            score = value[2]
            if score not in highest_score_items.keys():
                highest_score_items[score] = []
            highest_score_items[score].append(key)
        sorted_scores = sorted(highest_score_items.keys(), reverse=True)
        while remaining_time > 1000 and interstitials:
            
            for score in sorted_scores:
                if len(highest_score_items[score]) > 0:
                    break
            key = random.choice(highest_score_items[score])
            highest_score_items[score].remove(key)
            if len(highest_score_items[score]) < 1:
                del highest_score_items[score]
                sorted_scores.remove(score)
            if len(highest_score_items) < 1:
                break
            i, interstitial, score = interstitials[key]
            # Access the duration_ms value
            duration_ms = interstitial['files'][0]['duration_ms']+1000
            if duration_ms > remaining_time:
                continue
                        
            # Add the interstitial to selected_interstitials
            selected_interstitials[key] = (i, interstitial, score)
            #print(interstitial['title'],score)
            # Subtract duration_ms from remaining_time
            remaining_time -= duration_ms
            interstitials.pop(key)
            #print(f"Time Remaining: {remaining_time}", end='\r')
            #print(f"Interstitials length: {len(interstitials)}")
        
        '''for key, (i, interstitial, score) in interstitials.items():
            if isinstance(interstitial, dict):
                # Access the duration_ms value
                duration_ms = interstitial['files'][0]['duration_ms']+1000
                
                # Check if duration_ms is less than remaining_time
                if duration_ms <= remaining_time:
                    # Add the interstitial to selected_interstitials
                    selected_interstitials[key] = (i, interstitial, score)
                    
                    # Subtract duration_ms from remaining_time
                    remaining_time -= duration_ms
                    
                    # Check if remaining_time is less than 1000 milliseconds
                    if remaining_time < 1000:
                        break'''
        
        print(f"INTERSTITIALS SELECTED: {len(selected_interstitials)}",end='\n\n')
        i_keys = list(selected_interstitials.keys())
        random.shuffle(i_keys)
        interstitials_duration = 0

        if len(i_keys) > 0:
            print(f"{'Start Time':{time_width}} | "
                  f"{'Title':{title_width}} | "
                  f"{'Network':{network_width}} | "
                  f"{'Length':{duration_width}} | "
                  f"{'Aired Date':{aired_width}} | "
                  f"{'Library':{library_width}} | "
                  f"{'Score':{score_width}}"
                  )
        for i in i_keys:
            interstitial_tuple = selected_interstitials[i]
            interstitial_library, interstitial, interstitial_score = interstitial_tuple
            interstitial_start = previous_end_time + datetime.timedelta(seconds=1)
            
            interstitial_end = interstitial_start + datetime.timedelta(microseconds=interstitial['files'][0]['duration_ms']*1000)
            interstitial_dict = {
                "title": interstitial['title'],
                "start_time": interstitial_start.strftime('%H:%M:%S.%f'),
                "end_time": interstitial_end.strftime('%H:%M:%S.%f'),
                "type": {
                    "interstitial": {
                        "key": i,
                        "library": interstitial_library,
                        "title": interstitial['title'],
                        "year": interstitial['movie'].get("year",""),
                        "date": interstitial['movie'].get("date",""),
                        "network": interstitial['movie'].get("network",""),
                        "tag": interstitial['movie'].get("tag",""),
                        "source": interstitial['movie'].get("source",""),
                    }
                },
                "score": interstitial_score,
                "duration_s": interstitial['files'][0]['duration'], # Duration in seconds
                "duration_ms": interstitial['files'][0]['duration_ms'],
                "duration_min": interstitial['files'][0]['duration_min'], # Duration in minutes
                "summary": interstitial['movie'].get('plot',''),
            }
            previous_end_time = interstitial_start + datetime.timedelta(microseconds=interstitial['files'][0]['duration_ms']*1000)
            active_schedule[interstitial_start.strftime('%Y-%m-%d %H:%M:%S.%f')] = interstitial_dict
            interstitial_start = interstitial_start.strftime('%Y-%m-%d %H:%M:%S.%f')
            duration_seconds = round(interstitial['files'][0]['duration'], 1)
            duration_str = f"{duration_seconds}s"
            aired_date = interstitial['movie'].get('aired', f"{interstitial['movie'].get('year', 'XXXX')}-XX-XX")
            library_name = interstitial_libraries[interstitial_library][0].replace(' json', '')
            title = interstitial['title']
            network = interstitial['movie'].get('network', '')
            
            # Print information with evenly spaced columns
            print(f"{interstitial_start:{time_width}} | "
                  f"{title[:60]:{title_width}} | "
                  f"{network:{network_width}} | "
                  f"{duration_str:{duration_width}} | "
                  f"{aired_date:{aired_width}} | "
                  f"{library_name:{library_width}} | "
                  f"{interstitial_score:{score_width}}")
                  
            interstitials_duration += interstitial['files'][0]['duration']
        active_schedule[f"{next_start_time.strftime('%Y-%m-%d')} {start}"] = schedule_entry
        previous_end_time = end_time
        print(f"FILLED TIME: {datetime.timedelta(seconds=interstitials_duration)}")
        print("\n-------------------------------------\n")
        print(f"START: {schedule_entry['start_time']}\n{schedule_entry['title']}")
        end_time = schedule_entry['end_time']
    
    print(f"END: {previous_end_time}")
    print("\n-------------------------------------\n")
    
    next_day = datetime.datetime.strptime(date_string, '%Y-%m-%d') + datetime.timedelta(days=1)
    next_day_string = next_day.strftime('%Y-%m-%d')
    
    previous_end_time = datetime.datetime.strptime(f"{next_day_string} {end_time}", '%Y-%m-%d %H:%M:%S.%f')
    
    next_start_time = datetime.datetime.strptime(f"{next_day_string} {first_start_time}", '%Y-%m-%d %H:%M:%S.%f')
    
    '''if next_start_time <= datetime.datetime.strptime(first_start_time, '%H:%M:%S.%f'):
        next_start_time += datetime.timedelta(days=1)'''
    
    if previous_end_time < next_start_time:
        interstitials = get_interstitials(date_string, (previous_end_time, next_start_time), daily_schedule, movie_library, show_library, interstitial_libraries, schedule_template, active_schedule, os.path.basename(os.path.dirname(daily_schedule_path)).lstrip('0'))
    remaining_time = (next_start_time - previous_end_time).total_seconds()*1000
    
    total_duration = sum(subdict['duration_ms'] for key, (i, interstitial, score) in interstitials.items() if isinstance(interstitial, dict) for subdict in interstitial['files'])
    print(f"ALL DURATION: {datetime.timedelta(seconds=total_duration/1000)}")
    selected_interstitials = {}
    for key, (i, interstitial, score) in interstitials.items():
        if isinstance(interstitial, dict):
            # Access the duration_ms value
            duration_ms = interstitial['files'][0]['duration_ms']
            
            # Check if duration_ms is less than remaining_time
            if duration_ms <= remaining_time:
                # Add the interstitial to selected_interstitials
                selected_interstitials[key] = (i, interstitial, score)
                
                # Subtract duration_ms from remaining_time
                remaining_time -= duration_ms
                
                # Check if remaining_time is less than 500 milliseconds
                if remaining_time < 500:
                    break
    
    print(f"INTERSTITIALS SELECTED: {len(selected_interstitials)}",end='\n\n')
    i_keys = list(selected_interstitials.keys())
    random.shuffle(i_keys)
    interstitials_duration = 0

    if len(i_keys) > 0:
        print(f"{'Start Time':{time_width}} | "
              f"{'Title':{title_width}} | "
              f"{'Network':{network_width}} | "
              f"{'Length':{duration_width}} | "
              f"{'Aired Date':{aired_width}} | "
              f"{'Library':{library_width}} | "
              f"{'Score':{score_width}}"
              )
    for i in i_keys:
        interstitial_tuple = selected_interstitials[i]
        interstitial_library, interstitial, interstitial_score = interstitial_tuple
        interstitial_start = previous_end_time + datetime.timedelta(seconds=1)
        
        interstitial_end = interstitial_start + datetime.timedelta(microseconds=interstitial['files'][0]['duration_ms']*1000)
        interstitial_dict = {
            "title": interstitial['title'],
            "start_time": interstitial_start.strftime('%H:%M:%S.%f'),
            "end_time": interstitial_end.strftime('%H:%M:%S.%f'),
            "type": {
                "interstitial": {
                    "key": i,
                    "library": interstitial_library,
                    "title": interstitial['title'],
                    "year": interstitial['movie'].get("year",""),
                    "date": interstitial['movie'].get("date",""),
                    "network": interstitial['movie'].get("network",""),
                    "tag": interstitial['movie'].get("tag",""),
                    "source": interstitial['movie'].get("source",""),
                }
            },
            "score": interstitial_score,
            "duration_s": interstitial['files'][0]['duration'], # Duration in seconds
            "duration_ms": interstitial['files'][0]['duration_ms'],
            "duration_min": interstitial['files'][0]['duration_min'], # Duration in minutes
            "summary": interstitial['movie'].get('plot',''),
        }
        previous_end_time = interstitial_start + datetime.timedelta(microseconds=interstitial['files'][0]['duration_ms']*1000)
        active_schedule[interstitial_start.strftime('%Y-%m-%d %H:%M:%S.%f')] = interstitial_dict
        interstitial_start = interstitial_start.strftime('%H:%M:%S.%f')
        duration_seconds = round(interstitial['files'][0]['duration'], 1)
        duration_str = f"{duration_seconds}s"
        aired_date = interstitial['movie'].get('aired', f"{interstitial['movie'].get('year', 'XXXX')}-XX-XX")
        library_name = interstitial_libraries[interstitial_library][0].replace(' json', '')
        title = interstitial['title']
        network = interstitial['movie'].get('network', '')
        
        # Print information with evenly spaced columns
        print(f"{interstitial_start:{time_width}} | "
              f"{title[:60]:{title_width}} | "
              f"{network:{network_width}} | "
              f"{duration_str:{duration_width}} | "
              f"{aired_date:{aired_width}} | "
              f"{library_name:{library_width}} | "
              f"{interstitial_score:{score_width}}")
              
        interstitials_duration += interstitial['files'][0]['duration']+1
    active_schedule[f"{next_start_time.strftime('%Y-%m-%d')} {start}"] = schedule_entry
    previous_end_time = end_time
    print(f"FILLED TIME: {datetime.timedelta(seconds=interstitials_duration)}")
    print("\n-------------------------------------\n")
    return active_schedule

def update_schedule(existing_active_schedule, active_schedule):
    if not active_schedule:
        return existing_active_schedule
    
    # Convert keys to datetime objects for easy comparison
    existing_keys = {datetime.datetime.strptime(k, "%Y-%m-%d %H:%M:%S.%f"): v for k, v in existing_active_schedule.items()}
    active_keys = {datetime.datetime.strptime(k, "%Y-%m-%d %H:%M:%S.%f"): v for k, v in active_schedule.items()}
    
    # Identify the earliest entry in active_schedule
    earliest_active_entry = min(active_keys.keys())
    time_threshold = earliest_active_entry - datetime.timedelta(hours=24)
    
    # Remove entries more than 24 hours older than the earliest active entry and remove entries that overlap with active_schedule
    for key in list(existing_keys.keys()):
        if key < time_threshold:
            del existing_active_schedule[key.strftime("%Y-%m-%d %H:%M:%S.%f")]
        elif key >= earliest_active_entry:
            del existing_active_schedule[key.strftime("%Y-%m-%d %H:%M:%S.%f")]
    
    '''for active_key, active_value in active_keys.items():
        active_start = active_key
        active_end = datetime.datetime.strptime(active_value['end_time'], "%H:%M:%S.%f")
        for existing_key, existing_value in list(existing_keys.items()):
            existing_start = existing_key
            existing_end = datetime.datetime.strptime(existing_value['end_time'], "%H:%M:%S.%f")
            # Check if the time ranges overlap
            if (existing_start <= active_end and active_start <= existing_end):
                del existing_keys[existing_key]'''
    
    # Convert keys back to string format
    active_keys = {k.strftime("%Y-%m-%d %H:%M:%S.%f"): v for k, v in active_keys.items()}
    
    # Add entries from active_schedule to existing_active_schedule
    existing_active_schedule.update(active_keys)
    
    # Convert keys back to string format
    #updated_schedule = {k.strftime("%Y-%m-%d %H:%M:%S.%f"): v for k, v in existing_keys.items()}
    
    return existing_active_schedule

def select_template(channel_number, template_dir, json_files):
    # Attempt to match a file name with the channel number
    channel_template = None
    for file in json_files:
        # Remove trailing zeroes and check if it starts with the channel number
        file_match = re.match(r'^0*(\d+)', file)
        if file_match:
            stripped_file = file_match.group(1)
        else:
            stripped_file = ''
        if stripped_file.startswith(str(channel_number)):
            channel_template = file
            break
    
    # If no match found, select a non-numbered template at random
    if not channel_template:
        non_numbered_templates = [f for f in json_files if not re.match(r'^\d+', f)]
        if non_numbered_templates:
            channel_template = random.choice(non_numbered_templates)
            json_files.remove(channel_template)  # Remove selected template to avoid reuse
        else:
            # If all templates have been used, allow reuse
            channel_template = random.choice(json_files)
    
    return channel_template

def get_unicode_character():
    characters = [
        "📺",  # Television
        "📷",  # Camera
        "📹",  # Video Camera
        "📽️", # Film Projector
        "🎥",  # Movie Camera
        "🖥️", # Desktop Computer
        "📀",  # DVD
        "💾",  # Floppy Disk
        "🎬",  # Clapper Board
        "🎞️", # Film Frames
        "📼",  # VHS Tape
        "🎤",  # Microphone
        "🎧",  # Headphones
        "🎙️", # Studio Microphone
        "📡",  # Satellite Dish
        "🎭",  # Performing Arts 
        "🎟️", # Admission Tickets
        "🎫",  # Ticket
        "🌠",  # Shooting Star 
        "⭐",  # Star 
        ]
    try:
        return random.choice(characters)
    except KeyError:
        return "📺"

def validate_details(file_path):
    """
    Validate the structure of the details dictionary in a JSON file,
    ensuring 'icon_text' maps to the Unicode character in 'icon'.
    """
    required_structure = {
        "number_raw": str,
        "number_int": int,
        "channel_name": str,
        "channel_call_letters": str,
        "icon": str,       # Unicode character
    }

    try:
        with open(file_path, 'r') as file:
            data = json.load(file)
        
        # Check if all required keys exist and their types match
        for key, value_type in required_structure.items():
            if key not in data or not isinstance(data[key], value_type):
                return False
        return True
    except (json.JSONDecodeError, FileNotFoundError):
        return False

def generate_channel_name():
    adjectives = ["National", "Regional", "Global", "International", "Local", "Universal", "City", "State", "Galactic", "Intergalactic", "Pangalactic", "Worldwide", "Community", "Public", "Independent", "Continental", "Federal", "Transnational", "Provincial", "Metropolitan", "Subnational", "Territorial", "Universal", "Intercontinental", "Nationwide", "Interregional", "Suburban", "Urban", "Exurban", "Rural", "Neighborhood", "Federation", "Zone", "Borough", "Municipal", "Interstate", "Pan-national", "Extraterritorial", "Borderless", "Oceanic", "Continental", "Transcontinental", "Worldly", "Satellite", "Federalist", "Area", "Sector", "Subregional", "Enclave", "Sphere",  "Archipelagic", "Coastal", "Island-wide", "Transoceanic", "Planetary", "Celestial", "Solar", "Lunar",     "Independent", "Free", "Dynamic", "Innovative", "Progressive", "Modern", "Creative", "Visionary", "Pioneering", "Epic",     "Bold", "Brilliant", "Golden", "Radiant", "Vivid", "Majestic", "Prime", "Grand", "Noble", "Iconic", "Stellar", "Superior", "Classic", "Timeless", "Legendary"]
    modifier_words = ["Prime", "Classic", "Vintage", "Timeless", "Eternal", "Golden", "Legacy", "Prestige", "Refined", "Superior",
    "Master", "Royal", "Platinum", "Grand", "Exquisite", "Modern", "Next", "Future", "Neo", "Ultra", "Advanced",
    "Quantum", "Dynamic", "Innovative", "Progressive", "High-Tech", "Turbo", "Supercharged", "Interactive",
    "Digital", "Ultimate", "Super", "Mega", "Hyper", "Colossal", "Giga", "Ultra", "Extreme", "Monster", "Epic",
    "Titan", "Mighty", "Power", "Infinity", "Omni", "Alpha", "Beta", "Delta", "Omega", "Zeta", "Nova", "Cosmic",
    "Solar", "Lunar", "Astral", "Stellar", "Galactic", "Universal", "Infinity", "Orbit", "Elite", "Star", "Vision",
    "Regal", "Majestic", "Crown", "Sovereign", "Imperial", "Lavish", "Luxe", "Opulent", "Prestigious", "Noble",
    "Iconic", "Illustrious", "Central", "Premier", "Express", "Essential", "Core", "Hub", "Main", "True", "Key",
    "Prime", "Anchor", "Trusted", "Pinnacle", "Beacon", "Base", "Honey", "Jewel", "Crystal", "Amber",
    "Velvet", "Dream", "Pulse", "Flare", "Bliss", "Bloom", "Arc", "Zenith", "Fusion", "Horizon"]
    thematic_words = ["Entertainment", "Adventure", "Arts", "Culture", "Discovery", "Journey", "Odyssey", "Horizon", "Galaxy", "World", "Realm", "Universe", "Exploration", "Expedition", "Innovation", "Dreams", "Vision", "Imagination", "Fantasy", "Future", "Legacy", "Wonder", "Infinity", "Spectrum", "Perspective", "Epoch", "Era", "Passion", "Connection", "Dialogue", "Unity", "Fusion", "Pulse", "Rhythm", "Emotion", "Life", "Expression", "Essence", "Momentum", "Energy", "Journey", "Renaissance", "Sauce"]    
    medium_words = ["Network", "Channel", "Television", "TV", "Station", "Media", "Broadcasting", "Communications",  "Collective", ""]
    medium_word = random.choice(medium_words)
    if medium_word in ["Channel", "Station", "Corporation", "Company", "Group", "Partnership", "Association", "Alliance"]:
        article = "The "
    else:
        article = ""
    channel_name = f"{article}{random.choice(adjectives)} {random.choice(thematic_words)} {medium_word}".strip()
    return channel_name

def generate_call_letters(channel_name):
    call_letters = random.choice(['K','W',''])
    name_array = channel_name.split()
    for word in name_array:
        if word in ["TV", "Television"]:
            call_letters += "TV"
            if call_letters[0] in ['K','W']:
                call_letters = call_letters[1:]
        elif word != "The":
            call_letters += word[0]
    return call_letters

def generate_details(file_path, number_raw):
    """
    Generate a new details JSON file with procedurally generated values.
    """
    channel_name = generate_channel_name()
    call_letters = generate_call_letters(channel_name)
    icon = get_unicode_character()

    details = {
        "number_raw": number_raw,
        "number_int": int(number_raw),
        "channel_name": channel_name,
        "channel_call_letters": call_letters,
        "icon": icon
    }

    # Save the details to a new file
    with open(file_path, 'w') as file:
        json.dump(details, file, indent=4)

    print(f"Generated new Channel {int(number_raw)} details file at {file_path}")

def create_one_channel(template_file):
    file_path = f'channel_templates/{template_file}'
    channel_str = create_new_channel(file_path)
    generate_details(f'channels/{channel_str}/details.json',channel_str)
    schedule_template = generate_daily_schedules('channels/', number_of_days=int(config['Settings']['Advance Days']),single_channel=channel_str)
    # Get today's date
    today_date = datetime.datetime.now().date()

    # Format the date as YYYY-MM-DD
    formatted_date = today_date.strftime("%Y-%m-%d")
    
    interstitial_libraries = []
    for l, library in config['Interstitials'].items():
        interstitial_library = load_json_file(library)
        interstitial_libraries.append((l.replace(" JSON",""),interstitial_library))

    
    channel=channel_str
    # Construct the path to the details file
    details_path = os.path.join(channels_dir, channel, "details.json")
    
    if os.path.exists(details_path):
        validate_details(details_path)
        
    else:
        generate_details(details_path, channel)

    active_schedule = create_active_schedule(formatted_date, os.path.join(channels_dir, channel, "daily_schedule.json"), movie_library, show_library, interstitial_libraries, load_json_file(os.path.join(channels_dir,channel,'schedule.json'))['Template'])

    # Construct the path to the active schedule file
    active_schedule_path = os.path.join(channels_dir, channel, "active_schedule.json")
    
    # Load existing daily schedule if it exists
    if os.path.exists(active_schedule_path):
        existing_active_schedule = load_json_file(active_schedule_path)
    else:
        existing_active_schedule = {}
    
    # Update or add the current schedule under the current date key
    #print(existing_active_schedule)
    updated_active_schedule = update_schedule(existing_active_schedule, active_schedule)
    #existing_active_schedule[formatted_date] = active_schedule
    
    # Save the updated daily schedule to file
    with open(active_schedule_path, "w") as file:
        json.dump(updated_active_schedule, file, indent=4)
    ending = datetime.datetime.now()
    
def main():
    starting = datetime.datetime.now()
    # Count the number of subdirectories containing 'schedule.json'
    count = sum(
        1 for subdir in os.listdir(channels_dir)
        if os.path.isdir(os.path.join(channels_dir, subdir)) and os.path.isfile(os.path.join(channels_dir, subdir, 'schedule.json'))
    )

    # Calculate the number of channels to be created
    channels_to_create = int(config['Settings']['Minimum Channels']) - count

    json_files = [f for f in os.listdir(channel_templates_dir) if f.endswith('.json')]
    

    # Run the function if the number of channels to be created is greater than zero
    if channels_to_create > 0:
        print(f"Creating {channels_to_create} channels.")
        for _ in range(channels_to_create):
            print("------------------------------------------------")
            channel_number = count + _ + 1
            template_file = select_template(channel_number, channel_templates_dir, json_files)
            create_start = datetime.datetime.now()
            create_new_channel(os.path.join(channel_templates_dir, template_file))
            create_end = datetime.datetime.now()
            create_time = datetime.timedelta(seconds=(create_end - create_start).total_seconds())
            print(f"CHANNEL {channel_number} CREATION COMPLETE IN {create_time}.")
        print("------------------------------------------------")
    schedule_template = generate_daily_schedules(channels_dir, number_of_days=int(config['Settings']['Advance Days']))
    # Get today's date
    today_date = datetime.datetime.now().date()

    # Format the date as YYYY-MM-DD
    formatted_date = today_date.strftime("%Y-%m-%d")
    
    channel_subdirs = sorted(
        [d for d in os.listdir(channels_dir) if os.path.isdir(os.path.join(channels_dir, d))],
        key=lambda x: (
            int(x.split()[0]),  # Sort by the numeric part before any space
            x.split()[1] if len(x.split()) > 1 else ""  # Sort alphabetically by the part after the space (if present)
        )
    )
    
    #movie_library = load_json_file(movie_json_path)
    #show_library = load_json_file(show_json_path)
    interstitial_libraries = []
    for l, library in config['Interstitials'].items():
        interstitial_library = load_json_file(library)
        interstitial_libraries.append((l.replace(" JSON",""),interstitial_library))

    
    for channel in channel_subdirs:
        # Construct the path to the details file
        details_path = os.path.join(channels_dir, channel, "details.json")
        
        if os.path.exists(details_path):
            validate_details(details_path)
            
        else:
            generate_details(details_path, channel)

        active_schedule = create_active_schedule(formatted_date, os.path.join(channels_dir, channel, "daily_schedule.json"), movie_library, show_library, interstitial_libraries, load_json_file(os.path.join(channels_dir,channel,'schedule.json'))['Template'])

        # Construct the path to the active schedule file
        active_schedule_path = os.path.join(channels_dir, channel, "active_schedule.json")
        
        # Load existing daily schedule if it exists
        if os.path.exists(active_schedule_path):
            existing_active_schedule = load_json_file(active_schedule_path)
        else:
            existing_active_schedule = {}
        
        # Update or add the current schedule under the current date key
        #print(existing_active_schedule)
        updated_active_schedule = update_schedule(existing_active_schedule, active_schedule)
        #existing_active_schedule[formatted_date] = active_schedule
        
        # Save the updated daily schedule to file
        with open(active_schedule_path, "w") as file:
            json.dump(updated_active_schedule, file, indent=4)
    ending = datetime.datetime.now()
    print(datetime.timedelta(seconds=(ending-starting).total_seconds()))
    
if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description="BEE Scheduler")
    argparser.add_argument('--mode', choices=['main','create'],help="Select run mode")
    argparser.add_argument('--file',help="Indicate template file name")
    argparser.add_argument('--on_start',help="Run scripts on start")

    args = argparser.parse_args()
    
    if args.mode == 'create':
        if args.file:
            if os.path.splitext(args.file)[1] != ".json":
                template_file = f"{args.file}.json"
            else:
                template_file = args.file
        else:
            print("No template specified, please include template file with argument '--file'")
            sys.exit()
        template_path = os.path.join('channel_templates',template_file)
        if os.path.exists(template_path):
            create_one_channel(template_file)
        else:
            print("Template file not found")
            sys.exit()
    else:
        main()
    
    
