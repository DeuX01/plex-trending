# Trending Media Management Script

This script automates the retrieval of the top 50 trending movies and TV shows from Trakt. It then compares this data with your existing media library and creates symbolic links to a specified folder. These symbolic links serve as the foundation for a new library, facilitating easy access and organization.

## Features:
- **Trending Media Integration:** Automatically pulls the top 50 trending movies and TV shows from Trakt.
- **Dynamic Symlink Creation:** Matches trending media with your existing collection and creates symbolic links in a defined folder.
- **Library Organization:** Establishes a structured library based on trending media, enhancing accessibility and usability.

## Organizational Process:
- **Sorting by Trending Order:** Movies and TV shows are sorted based on their trending order, facilitating easy identification and access.
- **Renaming Convention:** Movies are renamed with a prefix '#' followed by a number corresponding to their trending order, enhancing clarity within the library.

## Instructions:

1. **Download and Setup:**
   - Download the repository ZIP file by navigating to `Code > Download Zip` and extract it to your preferred location.

2. **Trakt API Registration:**
   - Create a Trakt API by registering on Trakt and visiting [Trakt API Applications](https://trakt.tv/oauth/applications/new).

3. **Configuration:**
   - Edit the `config.yml` file and provide your Trakt client ID and client secret.
     - Replace `client_id: 'YOUR_TRAKT_CLIENT_ID'` with the client ID obtained from your Trakt API application.
     - Replace `client_secret: 'YOUR_TRAKT_CLIENT_SECRET'` with the client secret obtained from your Trakt API application.
   - Replace `/path/to/trending_movies_symlink` and `/path/to/trending_tv_symlink` with the paths to two folders on your system where the symlinks will be created (e.g., `/mnt/trending_movies` and `/mnt/trending_shows`).
   - Replace `/path/to/movie_storage` and `/path/to/tv_show_storage` with the paths to the parent folders of your existing movies and TV shows (e.g., `/mnt/movies` and `/mnt/shows`).
   - Replace `http://YOUR_PLEX_SERVER_IP:32400` with your Plex server's IP.
   - Replace `YOUR_PLEX_TOKEN` with your Plex token ([Find Your Plex Token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)).
   - Replace `'YOUR_PLEX_MOVIES_LIBRARY_NAME'` with the desired name for a trending movie library (e.g., Trending Movies). Ensure this library is pre-created in Plex.
   - Replace `'YOUR_PLEX_TV_SHOWS_LIBRARY_NAME'` with the desired name for a trending TV library. Ensure this library is pre-created in Plex.

4. **Installation and Execution:**
   - Open a terminal and navigate to the root folder containing `plex-trending.py`.
   - Install the required modules by executing `pip install -r requirements.txt`.
   - Ensure the `config.yml` is correctly configured.
   - Run the script using `python3 plex-trending.py`.

5. **Exclusion of Media:**
   - To ignore specific movies or TV shows from being added to the libraries, edit the `unwanted.json` file and add the TMDB or TVDB ID.

6. **Scheduling Automation:**
   - Schedule the script to run periodically, e.g., every 12 hours, by setting up a cron job:
     1. Open the crontab file by executing `crontab -e`.
     2. Add the following line: `0 */12 * * * /usr/bin/python3 /path/to/your/plex-trending.py`.
     3. Save and exit the editor (e.g., Ctrl+X, Y, Enter).

![Image](./library.jpg)
