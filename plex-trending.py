import requests
import json
import logging
import os
import re
import stat
import yaml
import unidecode
import collections
from plexapi.server import PlexServer
from fuzzywuzzy import fuzz, process
from collections import defaultdict

# Configure logging
log_folder = 'log'
os.makedirs(log_folder, exist_ok=True)

# Create a custom logger
logger = logging.getLogger('plex_trakt_sync')
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler(os.path.join(log_folder, 'app.log'))
console_handler = logging.StreamHandler()

# Create formatters and add them to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Create unwanted.json if it doesn't exist
unwanted_file = 'unwanted.json'
unwanted_template = {
    "movies": ["Add TMDB IDs here, e.g., 12345"],
    "tv_shows": ["Add TVDB IDs here, e.g., 67890"]
}

if not os.path.exists(unwanted_file):
    with open(unwanted_file, 'w') as file:
        json.dump(unwanted_template, file, indent=4)
    logger.info(f"Created {unwanted_file} with instructions.")

def load_unwanted_ids():
    with open(unwanted_file, 'r') as file:
        return json.load(file)

unwanted_ids = load_unwanted_ids()

# Load config from config.yml
with open('config.yml', 'r') as file:
    config = yaml.safe_load(file)

# Extract configuration values
CLIENT_ID = config['trakt']['client_id']
CLIENT_SECRET = config['trakt']['client_secret']
BASE_URL = config['trakt']['base_url']
TRENDING_MOVIES_URL = f"{BASE_URL}{config['trakt']['trending_movies_url']}"
TRENDING_TV_URL = f"{BASE_URL}{config['trakt']['trending_tv_url']}"

MOVIE_SYMLINK_PATH = config['paths']['movie_symlink_path']
TV_SYMLINK_PATH = config['paths']['tv_symlink_path']
MOVIE_FOLDER_PATH = config['paths']['movie_folder_path']
TV_FOLDER_PATH = config['paths']['tv_folder_path']

PLEX_BASE_URL = config['plex']['base_url']
PLEX_TOKEN = config['plex']['token']
PLEX_TRENDING_MOVIES_LIBRARY = config['plex']['trending_movies_library']
PLEX_TRENDING_TV_LIBRARY = config['plex']['trending_tv_library']

DISCORD_WEBHOOK_URL = config['discord']['webhook_url']

plex = PlexServer(PLEX_BASE_URL, PLEX_TOKEN, timeout=900)

json_folder = 'jsons'
os.makedirs(json_folder, exist_ok=True)

def fetch_data(url):
    headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': CLIENT_ID
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        logger.info(f"Fetched data successfully from {url}")
        return response.json()
    else:
        logger.error(f"Failed to fetch data from {url}: {response.text}")
        return []

def simplify_data(data, is_movie=False):
    simplified_data = []
    id_field = 'tmdb' if is_movie else 'tvdb'
    unwanted = unwanted_ids['movies'] if is_movie else unwanted_ids['tv_shows']
    
    for item in data:
        if 'movie' in item:
            movie = item['movie']
            movie_id = movie.get('ids', {}).get(id_field)
            if str(movie_id) in unwanted:
                logger.info(f"Skipping unwanted movie: {movie.get('title')} ({movie_id})")
                continue
            simplified_movie = {
                "title": movie.get('title'),
                "year": movie.get('year'),
                "ids": {
                    id_field: movie_id
                }
            }
            simplified_data.append({'movie': simplified_movie})
        elif 'show' in item:
            show = item['show']
            show_id = show.get('ids', {}).get(id_field)
            if str(show_id) in unwanted:
                logger.info(f"Skipping unwanted show: {show.get('title')} ({show_id})")
                continue
            simplified_show = {
                "title": show.get('title'),
                "ids": {
                    id_field: show_id
                }
            }
            simplified_data.append({'show': simplified_show})
    return simplified_data

def save_to_json(data, filename):
    with open(os.path.join(json_folder, filename), 'w') as json_file:
        json.dump(data, json_file, indent=4)

def get_folder_names(path):
    try:
        return [folder for folder in os.listdir(path) if os.path.isdir(os.path.join(path, folder))]
    except FileNotFoundError:
        logger.error(f"Path '{path}' not found.")
        return []

def extract_id_from_folder_name(folder_name):
    match = re.search(r'\[(\d+)\]', folder_name)
    return match.group(1) if match else None

def set_read_permissions(path):
    for root, dirs, files in os.walk(path):
        for name in dirs:
            try:
                os.chmod(os.path.join(root, name), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            except PermissionError as e:
                logger.error(f"PermissionError: {e} - {os.path.join(root, name)}")
        for name in files:
            try:
                os.chmod(os.path.join(root, name), stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            except PermissionError as e:
                logger.error(f"PermissionError: {e} - {os.path.join(root, name)}")

def create_symlink(source, dest):
    try:
        if not os.path.exists(dest):
            os.symlink(source, dest)
            logger.info(f"Created symlink: {dest} -> {source}")
        else:
            logger.info(f"Symlink already exists: {dest}")
    except Exception as e:
        logger.error(f"Failed to create symlink: {e}")

def remove_symlink(path):
    try:
        if os.path.islink(path):
            os.unlink(path)
            logger.info(f"Removed symlink: {path}")
    except Exception as e:
        logger.error(f"Failed to remove symlink: {e}")

def send_discord_message(webhook_url, title, description, color, image_url=None):
    data = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "thumbnail": {"url": image_url} if image_url else None
            }
        ]
    }
    response = requests.post(webhook_url, json=data)
    if response.status_code == 204:
        logger.info("Discord message sent successfully")
    else:
        logger.error(f"Failed to send Discord message: {response.status_code} - {response.text}")

def notify_discord_new_items(new_items, is_movie=True):
    if new_items:
        title = "New Trending Movies" if is_movie else "New Trending TV Shows"
        description = "\n".join([f"{index + 1} - **{item['title']}**" for index, item in enumerate(new_items)])
        image_url = "https://cdn.iconscout.com/icon/free/png-256/free-trakt-3521769-2945267.png"
        send_discord_message(DISCORD_WEBHOOK_URL, title, description, color=3066993, image_url=image_url)  # Green color

def notify_discord_removed_items(removed_items, is_movie=True):
    if removed_items:
        title = "Removed Trending Movies" if is_movie else "Removed Trending TV Shows"
        description_lines = []
        for index, item in enumerate(removed_items):
            clean_title = re.sub(r'\s*\[\d+\]', '', item['title'])
            description_lines.append(f"{index + 1} - **{clean_title}**")
        description = "\n".join(description_lines)
        image_url = "https://cdn.iconscout.com/icon/free/png-256/free-trakt-3521769-2945267.png"
        send_discord_message(DISCORD_WEBHOOK_URL, title, description, color=15158332, image_url=image_url)  # Red color

def clean_old_symlinks(matched_data_file, symlink_path, is_movie=True):
    try:
        with open(os.path.join(json_folder, matched_data_file), 'r') as file:
            current_matches = json.load(file)
    except FileNotFoundError:
        current_matches = []

    current_folders = {item['folder_name'] for item in current_matches}
    removed_items = []
    for symlink in os.listdir(symlink_path):
        symlink_path_full = os.path.join(symlink_path, symlink)
        if symlink not in current_folders:
            remove_symlink(symlink_path_full)
            removed_items.append({"title": symlink})
    notify_discord_removed_items(removed_items, is_movie)

def compare_with_folders(json_data, folder_names, symlink_path, is_movie=False):
    matches = []
    id_field = 'tmdb' if is_movie else 'tvdb'
    new_items = []

    count = 0
    for item in json_data:
        if count >= 20:
            break

        title = item.get('movie', {}).get('title') if is_movie else item.get('show', {}).get('title')
        ids = item.get('movie', {}).get('ids', {}).get(id_field) if is_movie else item.get('show', {}).get('ids', {}).get(id_field)
        if ids:
            for folder in folder_names:
                folder_id = extract_id_from_folder_name(folder)
                if folder_id and str(ids) == folder_id:
                    matches.append({"title": title, "folder_name": folder})
                    source_path = os.path.join(MOVIE_FOLDER_PATH if is_movie else TV_FOLDER_PATH, folder)
                    symlink_dest = os.path.join(symlink_path, folder)
                    set_read_permissions(source_path)
                    create_symlink(source_path, symlink_dest)
                    new_items.append({"title": title, "folder_name": folder})
                    count += 1
                    break
                else:
                    logger.debug(f"IDs do not match: {ids} (json) != {folder_id} (folder)")
        else:
            logger.error(f"No valid ID found for {title}")

    notify_discord_new_items(new_items, is_movie)
    return matches

def trigger_plex_scan(library_name):
    plex.library.section(library_name).update()
    logger.info(f"Triggered scan for Plex library: {library_name}")

def normalize_title(title):
    # Remove accents and make lowercase
    normalized = unidecode.unidecode(title).lower()
    # Replace 'and' with '&'
    normalized = normalized.replace('and', '&')
    # Remove any leading/trailing whitespace
    normalized = normalized.strip()
    return normalized

def alternative_titles(title):
    # Create a list of title variations
    titles = [title, unidecode.unidecode(title)]
    
    # Remove all non-alphanumeric characters
    title_no_special = re.sub(r'[^\w\s]', '', title)
    if title_no_special not in titles:
        titles.append(title_no_special)
    
    title_no_special_unidecode = re.sub(r'[^\w\s]', '', unidecode.unidecode(title))
    if title_no_special_unidecode not in titles:
        titles.append(title_no_special_unidecode)
    
    # Normalize whitespace (collapse multiple spaces into one)
    title_normalized_whitespace = re.sub(r'\s+', ' ', title).strip()
    if title_normalized_whitespace not in titles:
        titles.append(title_normalized_whitespace)
    
    title_normalized_whitespace_unidecode = re.sub(r'\s+', ' ', unidecode.unidecode(title)).strip()
    if title_normalized_whitespace_unidecode not in titles:
        titles.append(title_normalized_whitespace_unidecode)
    
    # Add punctuation variations
    punct_variations = [
        title.replace(':', ' -'),
        title.replace('-', ':'),
        title.replace('!', ''),
        title.replace('&', 'and')
    ]
    titles.extend(punct_variations)
    
    return list(set(titles))  # Remove duplicates

def update_plex_sort_titles(library_name, matches):
    library = plex.library.section(library_name)
    all_titles = {normalize_title(item.title): item for item in library.all()}

    existing_sort_titles = defaultdict(list)
    for item in library.all():
        existing_sort_titles[normalize_title(item.title)].append(item.titleSort)

    for index, item in enumerate(matches, start=1):
        title = item['title']
        normalized_title = normalize_title(title)
        ids = item['folder_name']

        plex_items = library.search(title=title)
        logger.info(f"Searching for exact title: {title}")
        if not plex_items:
            if 'movie' in item:
                plex_items = library.search(**{'tmdb': ids})
                logger.info(f"Searching by TMDB ID: {ids}")
            elif 'show' in item:
                plex_items = library.search(**{'tvdb': ids})
                logger.info(f"Searching by TVDB ID: {ids}")

        if not plex_items:
            matches = process.extract(normalized_title, all_titles.keys(), scorer=fuzz.ratio)
            best_match = next((match for match in matches if match[1] > 80), None)
            if best_match:
                plex_items = [all_titles[best_match[0]]]
                logger.info(f"Fuzzy matched title: {best_match[0]} with score: {best_match[1]}")

        if plex_items:
            plex_item = plex_items[0]
            sort_title = f"{index:02d}"
            new_name = f"#{index} {title}"

            if new_name not in existing_sort_titles[normalized_title]:
                plex_item.edit(**{'titleSort.value': sort_title, 'titleSort.locked': 1, 'title.value': new_name, 'title.locked': 1})
                plex_item.reload()
                logger.info(f"Updated sort title for {title} to {sort_title} and name to {new_name}")
            else:
                logger.warning(f"Skipping update for {title} as it might conflict with an existing sort title")

        else:
            for alt_title in alternative_titles(title):
                plex_items = library.search(title=alt_title)
                logger.info(f"Searching for alternative title: {alt_title}")
                if plex_items:
                    plex_item = plex_items[0]
                    sort_title = f"{index:02d}"
                    new_name = f"#{index} {title}"
                    
                    if new_name not in existing_sort_titles[normalize_title(alt_title)]:
                        plex_item.edit(**{'titleSort.value': sort_title, 'titleSort.locked': 1, 'title.value': new_name, 'title.locked': 1})
                        plex_item.reload()
                        logger.info(f"Updated sort title for {title} (using alternative search) to {sort_title} and name to {new_name}")
                        break
            else:
                logger.error(f"Failed to match and update title for: {title}")

def process_media_trending(is_movie=True):
    url = TRENDING_MOVIES_URL if is_movie else TRENDING_TV_URL
    symlink_path = MOVIE_SYMLINK_PATH if is_movie else TV_SYMLINK_PATH
    folder_path = MOVIE_FOLDER_PATH if is_movie else TV_FOLDER_PATH
    matched_data_file = 'matched_movies.json' if is_movie else 'matched_tv.json'

    data = fetch_data(url)
    simplified_data = simplify_data(data, is_movie)
    save_to_json(simplified_data, 'movies.json' if is_movie else 'tv_shows.json')

    folder_names = get_folder_names(folder_path)
    folder_names_normalized = [normalize_title(folder) for folder in folder_names]

    matches = compare_with_folders(simplified_data, folder_names, symlink_path, is_movie)

    save_to_json(matches, matched_data_file)

    clean_old_symlinks(matched_data_file, symlink_path, is_movie)

    trigger_plex_scan(PLEX_TRENDING_MOVIES_LIBRARY if is_movie else PLEX_TRENDING_TV_LIBRARY)
    update_plex_sort_titles(PLEX_TRENDING_MOVIES_LIBRARY if is_movie else PLEX_TRENDING_TV_LIBRARY, matches)

if __name__ == "__main__":
    process_media_trending(is_movie=True)
    process_media_trending(is_movie=False)
