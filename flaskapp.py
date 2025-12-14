#!/usr/bin/env python

import glob
import json
import os
import subprocess

import requests
import requests_cache
from logzero import logger
from urllib.parse import urlparse, quote_plus

from bs4 import BeautifulSoup
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import send_from_directory
from flask import send_file



app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True  # Reload templates on every request
requests_cache.install_cache('/tmp/r.cache', expire_after=86400)  # 1 day = 86400 seconds
session = requests.Session()
#youtubecache = '/tmp/youtubevids'
youtubecache = 'youtube_cache'
youtubecache_index = '/tmp/youtubevids/index.json'
favorites_file = 'favorites.json'


def load_favorites():
    """Load favorites from JSON file"""
    if os.path.exists(favorites_file):
        with open(favorites_file, 'r') as f:
            return json.load(f)
    return {'videos': [], 'channels': []}


def save_favorites(favorites):
    """Save favorites to JSON file"""
    with open(favorites_file, 'w') as f:
        json.dump(favorites, f, indent=2)


def replace_urls(html, domain, protocol=None):
    soup = BeautifulSoup(html,'html.parser')
    arefs = soup.findAll('a')
    arefs = [x.attrs.get('href') for x in arefs]
    arefs = [x for x in arefs if x and x is not None]
    arefs = sorted(set(arefs))

    for idx,x in enumerate(arefs):
        if x.startswith('//'):
            arefs[idx] = '/' + x.lstrip('/')

    for aref in arefs:
        logger.debug(aref)
        naref = None
        if aref.startswith('/'):
            if domain:
                naref = '/' + domain + aref
            else:
                naref = '/' + aref
        elif aref.startswith('https://'):
            naref = aref.replace('https://', 'https.')
        elif aref.startswith('http://'):
            naref = aref.replace('http://', 'http.')
        else:
            # <a href="item?id=19638991">
            naref = '/' + protocol + '.' + domain + '/' + aref

        if naref:

            naref = naref.lstrip('/')
            if naref.startswith('http'):
                naref = '/' + naref

            logger.debug('[%s] %s => %s' % (domain, aref, naref))

            if aref.startswith('/'):
                html = html.replace('href="' + aref, 'href="' + naref)
                html = html.replace('src="' + aref, 'src="' + naref)
            else:
                html = html.replace('href="' + aref, 'href="' + naref)
                html = html.replace('src="' + aref, 'src="' + naref)

            html = html.replace('="' + aref, '="' + naref)

    html = html.replace('="https://', '="/https.')
    html = html.replace('="http://', '="/http.')

    return html


def do_link(path):

    protocol = None
    domain = None
    url = path.lstrip('/')
    if url.startswith('http.'):
        url = url.replace('http.', 'http://')
        o = urlparse(url)
        domain = o.netloc
        protocol = 'http'
    elif url.startswith('https.'):
        url = url.replace('https.', 'https://')
        o = urlparse(url)
        domain = o.netloc
        protocol = 'https'

    elif url.startswith('www') and not domain:
        if '/' in url:
            _domain = url.split('/')[0]
            domain = _domain
        else:
            _domain = url.split('.')
            domain = '.'.join(_domain[1:])


    headers = {
        'User-Agent': 'My User Agent 1.0',
        'From': 'youremail@domain.com'  # This is another valid field
    }

    if not url.startswith('/') and not url.startswith('http'):
        url = 'http://' + url

    logger.info('get %s' % url)
    rr = session.get(url, headers=headers, verify=False)
    thishtml = rr.text
    logger.info('replacing urls (domain=%s)' % domain)
    thishtml = replace_urls(thishtml, domain, protocol=protocol)
    return thishtml


@app.route('/files/youtube/<path:path>')
def files_youtube(path):
    fn = os.path.join(youtubecache, path)
    return send_file(fn)


@app.route('/favorites')
def favorites():
    """Show favorites page"""
    favs = load_favorites()

    # Load details for favorite videos
    video_details = []
    for video_id in favs.get('videos', []):
        vdir = os.path.join(youtubecache, video_id)
        df = os.path.join(vdir, 'data.json')
        if os.path.exists(df):
            try:
                with open(df, 'r') as f:
                    ds = json.loads(f.read())

                    # Skip if data is invalid
                    if not ds or not isinstance(ds, dict) or 'id' not in ds:
                        logger.warning(f'Skipping invalid data file: {df}')
                        continue

                    video_details.append({
                        'id': ds['id'],
                        'title': ds['title'],
                        'uploader': ds.get('uploader'),
                        'channel_id': ds.get('channel_id'),
                        'upload_date': ds.get('upload_date')
                    })
            except Exception as e:
                logger.exception(e)

    # Load details for favorite channels
    channel_details = []
    for channel_info in favs.get('channels', []):
        channel_details.append(channel_info)

    return render_template('favorites.html',
                         videos=video_details,
                         channels=channel_details)


@app.route('/favorite/add', methods=['POST'])
def add_favorite():
    """Add a video or channel to favorites"""
    favs = load_favorites()

    item_type = request.form.get('type')  # 'video' or 'channel'
    item_id = request.form.get('id')

    if item_type == 'video':
        if item_id not in favs['videos']:
            favs['videos'].append(item_id)
    elif item_type == 'channel':
        channel_name = request.form.get('name')
        # Check if channel already exists
        existing = [c for c in favs['channels'] if c['id'] == item_id]
        if not existing:
            favs['channels'].append({'id': item_id, 'name': channel_name})

    save_favorites(favs)

    # Redirect back to referrer or favorites page
    return_url = request.form.get('return_url', '/favorites')
    return redirect(return_url)


@app.route('/favorite/remove', methods=['POST'])
def remove_favorite():
    """Remove a video or channel from favorites"""
    favs = load_favorites()

    item_type = request.form.get('type')  # 'video' or 'channel'
    item_id = request.form.get('id')

    if item_type == 'video' and item_id in favs['videos']:
        favs['videos'].remove(item_id)
    elif item_type == 'channel':
        favs['channels'] = [c for c in favs['channels'] if c['id'] != item_id]

    save_favorites(favs)

    # Redirect back to referrer or favorites page
    return_url = request.form.get('return_url', '/favorites')
    return redirect(return_url)


@app.route('/transcript/fetch', methods=['POST'])
def fetch_transcript():
    """Fetch transcript for a video"""
    video_id = request.form.get('id')
    return_url = request.form.get('return_url', '/youtube')

    if video_id:
        vdir = os.path.join(youtubecache, video_id)
        if not os.path.exists(vdir):
            os.makedirs(vdir)

        try:
            # Try to download auto-generated English subtitles first, then manual
            # Download as .vtt format (easier to parse than .srt)
            cmd = f'yt-dlp --write-auto-sub --sub-lang en --skip-download --sub-format vtt --output "{vdir}/%(id)s" {video_id}'
            logger.info(f'Fetching transcript: {cmd}')
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            # If auto-subs failed, try manual subs
            if result.returncode != 0 or not glob.glob(f'{vdir}/*.vtt'):
                cmd = f'yt-dlp --write-sub --sub-lang en --skip-download --sub-format vtt --output "{vdir}/%(id)s" {video_id}'
                logger.info(f'Trying manual subtitles: {cmd}')
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

            # Check if we got a subtitle file
            vtt_files = glob.glob(f'{vdir}/*.vtt')
            if vtt_files:
                # Convert VTT to plain text
                vtt_file = vtt_files[0]
                transcript_text = convert_vtt_to_text(vtt_file)

                # Save as plain text
                transcript_file = os.path.join(vdir, 'transcript.txt')
                with open(transcript_file, 'w') as f:
                    f.write(transcript_text)

                logger.info(f'Transcript saved: {transcript_file}')
                separator = '&' if '?' in return_url else '?'
                return redirect(return_url + separator + 'transcript=success')
            else:
                logger.warning(f'No transcript available for {video_id}')
                separator = '&' if '?' in return_url else '?'
                return redirect(return_url + separator + 'transcript=unavailable')

        except Exception as e:
            logger.exception(e)
            separator = '&' if '?' in return_url else '?'
            return redirect(return_url + separator + 'transcript=error')

    return redirect(return_url)


def convert_vtt_to_text(vtt_file):
    """Convert VTT subtitle file to plain text"""
    import re

    with open(vtt_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove VTT header
    content = re.sub(r'WEBVTT\n.*?\n\n', '', content, flags=re.DOTALL)

    # Remove timestamp lines (e.g., "00:00:00.000 --> 00:00:02.000")
    content = re.sub(r'\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}.*?\n', '', content)

    # Remove cue identifiers (lines that are just numbers)
    content = re.sub(r'^\d+\n', '', content, flags=re.MULTILINE)

    # Remove VTT tags like <c>, <v>, etc.
    content = re.sub(r'<[^>]+>', '', content)

    # Remove alignment tags
    content = re.sub(r'align:start position:\d+%', '', content)

    # Split into lines and filter out empty ones
    lines = [line.strip() for line in content.split('\n')]
    lines = [line for line in lines if line]

    # Join with single newlines, then add paragraph breaks where appropriate
    # (YouTube captions often have sentences split across lines)
    text = ' '.join(lines)

    # Replace common sentence-ending patterns with newline breaks
    text = re.sub(r'\.\s+', '.\n', text)
    text = re.sub(r'\?\s+', '?\n', text)
    text = re.sub(r'!\s+', '!\n', text)

    # Collapse multiple blank lines into single blank line
    text = re.sub(r'\n\n+', '\n\n', text)

    return text.strip()


@app.route('/transcript/download/<video_id>')
def download_transcript(video_id):
    """Download transcript as a text file"""
    vdir = os.path.join(youtubecache, video_id)
    transcript_file = os.path.join(vdir, 'transcript.txt')

    if os.path.exists(transcript_file):
        return send_file(transcript_file,
                        as_attachment=True,
                        download_name=f'{video_id}_transcript.txt',
                        mimetype='text/plain')
    else:
        return "Transcript not found", 404


@app.route('/delete/video', methods=['POST'])
def delete_video():
    """Delete a video from cache"""
    import shutil

    video_id = request.form.get('id')
    return_url = request.form.get('return_url', '/youtube')

    if video_id:
        vdir = os.path.join(youtubecache, video_id)
        if os.path.exists(vdir):
            try:
                shutil.rmtree(vdir)
                logger.info(f'Deleted video cache: {video_id}')

                # Also remove from favorites if present
                favs = load_favorites()
                if video_id in favs.get('videos', []):
                    favs['videos'].remove(video_id)
                    save_favorites(favs)

            except Exception as e:
                logger.exception(e)
                separator = '&' if '?' in return_url else '?'
                return redirect(return_url + separator + 'error=delete_failed')

    return redirect(return_url)


@app.route('/delete/channel', methods=['POST'])
def delete_channel():
    """Delete all videos from a channel from cache"""
    import shutil

    channel_id = request.form.get('id')
    return_url = request.form.get('return_url', '/youtube')

    if channel_id:
        # Find all videos from this channel
        vfiles = glob.glob(f'{youtubecache}/*/data.json')
        deleted_count = 0

        for vfile in vfiles:
            try:
                with open(vfile, 'r') as f:
                    ds = json.loads(f.read())

                if not ds or not isinstance(ds, dict):
                    continue

                if ds.get('channel_id') == channel_id:
                    video_id = ds.get('id')
                    vdir = os.path.dirname(vfile)
                    shutil.rmtree(vdir)
                    deleted_count += 1
                    logger.info(f'Deleted video cache: {video_id}')

                    # Also remove from favorites if present
                    favs = load_favorites()
                    if video_id and video_id in favs.get('videos', []):
                        favs['videos'].remove(video_id)
                        save_favorites(favs)

            except Exception as e:
                logger.exception(e)
                continue

        # Remove channel from favorites
        favs = load_favorites()
        favs['channels'] = [c for c in favs.get('channels', []) if c['id'] != channel_id]
        save_favorites(favs)

        logger.info(f'Deleted {deleted_count} videos from channel {channel_id}')

    return redirect(return_url)


@app.route('/controls')
def controls():
    """Show admin/control page"""
    return render_template('controls.html')


@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    """Clear the web request cache but keep downloaded videos"""
    try:
        # Clear requests cache
        cache_path = '/tmp/r.cache'
        if os.path.exists(cache_path):
            os.remove(cache_path)
        if os.path.exists(cache_path + '.sqlite'):
            os.remove(cache_path + '.sqlite')

        # Reinstall the cache to recreate it
        requests_cache.install_cache('/tmp/r.cache', expire_after=86400)

        logger.info('Cache cleared successfully (videos preserved)')
        return render_template('cache_cleared.html')
    except Exception as e:
        logger.exception(e)
        return f'Error clearing cache: {str(e)}', 500


def fetch_channel_updates(channel_id, playlist_end=50, batch_size=20):
    """Fetch new videos for a channel without removing existing cache.

    Uses batched yt-dlp metadata fetches to cut down on per-video calls.
    """
    channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"
    cmd = f'yt-dlp --dump-json --flat-playlist --playlist-end {playlist_end} "{channel_url}"'
    logger.info(f'Updating channel {channel_id}: {cmd}')

    pid = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lines = pid.stdout.decode('utf-8').strip().split('\n')

    new_count = 0
    missing_ids = []
    for line in lines:
        if not line.strip():
            continue
        try:
            video_data = json.loads(line)
            video_id = video_data.get('id')

            if not video_id:
                continue

            # Check if video is already cached with valid JSON
            vdir = os.path.join(youtubecache, video_id)
            dfile = os.path.join(vdir, 'data.json')

            needs_refresh = False
            if os.path.exists(dfile):
                try:
                    with open(dfile) as df:
                        cached = json.load(df)
                    if not isinstance(cached, dict) or cached.get('id') != video_id:
                        needs_refresh = True
                except Exception:
                    # Corrupt or empty file; refresh it
                    needs_refresh = True
                    try:
                        os.remove(dfile)
                    except OSError:
                        pass
            else:
                needs_refresh = True

            if needs_refresh:
                missing_ids.append(video_id)

        except Exception as e:
            logger.exception(e)
            continue

    # Fetch metadata in batches to reduce per-video process overhead
    for i in range(0, len(missing_ids), batch_size):
        batch = missing_ids[i:i + batch_size]
        meta_cmd = ['yt-dlp', '-J'] + batch
        logger.info(f'Fetching metadata for batch ({len(batch)})')
        meta_pid = subprocess.run(meta_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        meta_output = meta_pid.stdout.decode('utf-8').strip().split('\n')

        for meta_line in meta_output:
            if not meta_line.strip():
                continue
            try:
                meta = json.loads(meta_line)
                if not isinstance(meta, dict):
                    continue
                video_id = meta.get('id')
                if not video_id:
                    continue

                vdir = os.path.join(youtubecache, video_id)
                dfile = os.path.join(vdir, 'data.json')
                if not os.path.exists(vdir):
                    os.makedirs(vdir)
                with open(dfile, 'w') as f:
                    f.write(json.dumps(meta, indent=2))
                new_count += 1
            except Exception as e:
                logger.exception(e)

    logger.info(f'Found {new_count} new videos for channel {channel_id}')
    return new_count


@app.route('/youtube/channel/<channel_id>/update', methods=['POST'])
def youtube_channel_update(channel_id):
    """Fetch the latest (up to 50) videos for a channel."""
    try:
        new_count = fetch_channel_updates(channel_id, playlist_end=50)
        return redirect(f'/youtube/channel/{channel_id}?updated={new_count}')
    except Exception as e:
        logger.exception(e)
        return redirect(f'/youtube/channel/{channel_id}?error=update_failed')


@app.route('/youtube/channel/<channel_id>/refresh-all', methods=['POST'])
def youtube_channel_refresh_all(channel_id):
    """Fetch a deeper slice of the channel playlist while keeping existing cache."""
    try:
        # Grab more entries to catch up on older uploads without deleting downloads
        new_count = fetch_channel_updates(channel_id, playlist_end=200)
        return redirect(f'/youtube/channel/{channel_id}?updated={new_count}')
    except Exception as e:
        logger.exception(e)
        return redirect(f'/youtube/channel/{channel_id}?error=update_failed')


@app.route('/youtube/channel/<channel_id>')
def youtube_channel(channel_id):
    """Show all cached videos from a specific channel"""
    vfiles = glob.glob(f'{youtubecache}/*/data.json')
    channel_videos = []
    channel_name = "Unknown Channel"

    for vfile in vfiles:
        # Skip obviously bad paths (e.g., artifacts with query params)
        if '?' in vfile:
            logger.warning(f'Skipping malformed path: {vfile}')
            continue
        try:
            with open(vfile, 'r') as f:
                ds = json.loads(f.read())

                # Skip if data is invalid
                if not ds or not isinstance(ds, dict):
                    logger.warning(f'Skipping invalid data file: {vfile}')
                    continue

                if ds.get('channel_id') == channel_id:
                    channel_videos.append({
                        'id': ds['id'],
                        'title': ds['title'],
                        'upload_date': ds.get('upload_date'),
                        'timestamp': ds.get('timestamp', 0),
                        'duration_string': ds.get('duration_string')
                    })
                    # Get channel name from first video
                    if channel_name == "Unknown Channel":
                        channel_name = ds.get('uploader') or ds.get('channel', 'Unknown Channel')
        except Exception as e:
            logger.warning(f'Skipping unreadable data file {vfile}: {e}')
            continue

    # Sort by timestamp (newest first)
    channel_videos.sort(key=lambda x: x['timestamp'], reverse=True)

    # Check if channel is favorited
    favs = load_favorites()
    is_favorited = any(c['id'] == channel_id for c in favs.get('channels', []))

    # Check for update notification
    updated_count = request.args.get('updated')
    update_error = request.args.get('error')

    return render_template('channel.html',
                         channel_name=channel_name,
                         channel_id=channel_id,
                         videos=channel_videos,
                         video_count=len(channel_videos),
                         is_favorited=is_favorited,
                         updated_count=updated_count,
                         update_error=update_error)


@app.route('/youtube')
@app.route('/youtube/')
def youtube():

    print('---------------------------')
    logger.debug(request.args)
    q = request.args.get('q')
    videoid = request.args.get('video')
    formatid = request.args.get('format')
    audio_only = request.args.get('audio_only')
    video_only = request.args.get('video_only')
    per_page = int(request.args.get('per_page', 10))  # default 10 results per page
    page = int(request.args.get('page', 1))  # default page 1
    logger.debug(f'videoid: {videoid} formatid:{formatid} audio:{audio_only} video:{video_only}')
    logger.debug(f'per_page: {per_page} page: {page}')
    logger.debug('---------------------------')

    # Redirect searches to dedicated search view
    if q:
        return redirect(f'/youtube/search?q={quote_plus(q)}&per_page={per_page}&page={page}')

    if videoid is not None:

        vdir = os.path.join(youtubecache, videoid)
        if not os.path.exists(vdir):
            os.makedirs(vdir)
        df = os.path.join(vdir, 'data.json')
        if not os.path.exists(df):
            cmd = f'yt-dlp -J {videoid} | tee -a {df}'
            logger.debug(cmd)
            subprocess.run(cmd, shell=True)
        with open(df, 'r') as f:
            ds = json.loads(f.read())

        videofile = None
        if formatid:
            for vformat in ds['formats']:
                print(vformat)
                if vformat['format_id'] == formatid:
                    break

            logger.debug('####################################')
            logger.debug(vformat)
            logger.debug('####################################')

            if vformat['video_ext'] != 'none':
                videofile = videoid + '_' + formatid + '.' + vformat['video_ext']
            elif vformat['audio_ext'] != 'none':
                videofile = videoid + '_' + formatid + '.' + vformat['audio_ext']
            else:
                videofile = videoid + '_' + formatid + '.vid'

            vfilepath = os.path.join(vdir, videofile)
            if not os.path.exists(vfilepath):
                #cmd = f'yt-dlp --keep-video --format {formatid} --extract-audio --output {videofile} {videoid}'
                cmd = f'yt-dlp --keep-video --format {formatid} --output {videofile} {videoid}'
                logger.debug(cmd)
                subprocess.run(cmd, cwd=vdir, shell=True)

        #cmd = 'yt-dlp --keep-video --extract-audio {videoid}'
        favs = load_favorites()
        is_favorited = videoid in favs.get('videos', [])

        # Check for transcript
        transcript_file = os.path.join(vdir, 'transcript.txt')
        transcript = None
        has_transcript = os.path.exists(transcript_file)
        if has_transcript:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript = f.read()

        # Check for transcript status messages
        transcript_status = request.args.get('transcript')

        return render_template('youtube-video.html',
                             video=ds,
                             videofile=videofile,
                             is_favorited=is_favorited,
                             has_transcript=has_transcript,
                             transcript=transcript,
                             transcript_status=transcript_status)

    videos = []

    # list what has already been cached
    vfiles = glob.glob(f'{youtubecache}/*/data.json')
    all_cached = []
    all_tags = set()
    all_categories = set()

    for vfile in vfiles:
        logger.debug(f'read {vfile}')
        try:
            with open(vfile, 'r') as f:
                ds = json.loads(f.read())

            # Skip if data is invalid
            if not ds or not isinstance(ds, dict) or 'id' not in ds:
                logger.warning(f'Skipping invalid data file: {vfile}')
                continue

            video_info = {
                'id': ds['id'],
                'title': ds['title'],
                'upload_date': ds.get('upload_date'),
                'timestamp': ds.get('timestamp', 0),
                'uploader': ds.get('uploader'),
                'channel_id': ds.get('channel_id'),
                'tags': ds.get('tags') or [],
                'categories': ds.get('categories') or []
            }
            all_cached.append(video_info)

            for t in video_info['tags']:
                if isinstance(t, str):
                    all_tags.add(t)
            for c in video_info['categories']:
                if isinstance(c, str):
                    all_categories.add(c)

        except Exception as e:
            logger.exception(e)

    # Filters
    filter_tag = request.args.get('tag')
    filter_category = request.args.get('category')
    filter_text = request.args.get('s')

    if filter_tag:
        all_cached = [v for v in all_cached if filter_tag in v.get('tags', [])]
    if filter_category:
        all_cached = [v for v in all_cached if filter_category in v.get('categories', [])]
    if filter_text:
        needle = filter_text.lower()
        filtered = []
        for v in all_cached:
            # Build a flattened string of all values in the metadata dict
            haystack = []
            for val in v.values():
                if isinstance(val, str):
                    haystack.append(val)
                elif isinstance(val, (list, tuple)):
                    haystack.extend([str(x) for x in val])
                elif val is not None:
                    haystack.append(str(val))
            joined = ' '.join(haystack).lower()
            if needle in joined:
                filtered.append(v)
        all_cached = filtered

    # Sort cached results by timestamp (newest first)
    all_cached.sort(key=lambda x: x['timestamp'], reverse=True)

    # No pagination on main list; show all cached
    videos = all_cached
    has_next = False
    has_prev = False

    return render_template('youtube.html',
                         videos=videos,
                         query=None,
                         page=1,
                         per_page=len(videos),
                         has_next=has_next,
                         has_prev=has_prev,
                         filter_tag=filter_tag,
                         filter_category=filter_category,
                         filter_text=filter_text,
                         tags=sorted(all_tags),
                         categories=sorted(all_categories))



@app.route('/youtube/search')
def youtube_search():
    """Dedicated search view for YouTube queries."""
    q = request.args.get('q')
    per_page = int(request.args.get('per_page', 10))
    page = int(request.args.get('page', 1))

    if not q:
        return redirect('/youtube')

    fetch_count = per_page * page + 1
    cmd = f'yt-dlp --dump-json --clean-info-json --dump-single-json "ytsearch{fetch_count}:{q}"'
    logger.debug(cmd)
    pid = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
    lines = pid.stdout.decode('utf-8').split('\n')
    all_videos = []
    for line in lines:
        try:
            ds = json.loads(line)
            all_videos.append({
                'id': ds['id'],
                'title': ds['title'],
                'upload_date': ds.get('upload_date'),
                'timestamp': ds.get('timestamp', 0)
            })

            vid = ds['id']
            vdir = os.path.join(youtubecache, vid)
            if not os.path.exists(vdir):
                os.makedirs(vdir)
            dfile = os.path.join(vdir, 'data.json')
            if not os.path.exists(dfile):
                with open(dfile, 'w') as f:
                    f.write(json.dumps(ds, indent=2))

        except Exception as e:
            logger.exception(e)
            continue

    # Sort by timestamp (newest first)
    all_videos.sort(key=lambda x: x['timestamp'], reverse=True)

    # Pagination logic: take only the results for current page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    videos = all_videos[start_idx:end_idx]

    # Check if there are more results
    has_next = len(all_videos) > per_page * page
    has_prev = page > 1

    logger.debug(f'fetched {len(all_videos)} results, showing {len(videos)} for page {page}')

    return render_template('youtube_search.html',
                           videos=videos,
                           query=q,
                           page=page,
                           per_page=per_page,
                           has_next=has_next,
                           has_prev=has_prev)


@app.route('/creators')
def creators():
    """List cached creators."""
    vfiles = glob.glob(f'{youtubecache}/*/data.json')
    creators = {}

    for vfile in vfiles:
        # skip malformed path names
        if '?' in vfile:
            continue
        try:
            with open(vfile, 'r') as f:
                ds = json.loads(f.read())

            if not ds or not isinstance(ds, dict) or 'id' not in ds:
                continue

            channel_id = ds.get('channel_id')
            if not channel_id:
                continue

            if channel_id not in creators:
                creators[channel_id] = {
                    'name': ds.get('uploader', 'Unknown'),
                    'channel_id': channel_id,
                    'video_count': 0,
                    'latest_timestamp': 0
                }
            creators[channel_id]['video_count'] += 1
            if ds.get('timestamp', 0) > creators[channel_id]['latest_timestamp']:
                creators[channel_id]['latest_timestamp'] = ds.get('timestamp', 0)

        except Exception as e:
            logger.exception(e)

    creators_list = sorted(creators.values(), key=lambda x: x['video_count'], reverse=True)

    return render_template('creators.html', creators=creators_list)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def abstract_path(path):

    if request.query_string:
        path = path + '?' + request.query_string.decode('utf-8')
    logger.info(path)

    if path == 'favicon.ico':
        return ''

    if not path:
        return render_template('index.html')

    if ('youtube.com/watch?') in path:
        realurl = path.replace('https.', 'https://')
        realurl = path.replace('http.', 'http://')
        if not realurl.startswith('http'):
            realurl = 'https://' + realurl
        #import epdb; epdb.st()
        vpath = prefetch_youtube_video(realurl)
        #return jsonify(vpaths)
        logger.debug('disk path for video: %s' % vpath)
        return send_from_directory(os.path.dirname(vpath), os.path.basename(vpath))

    return do_link(path)


if __name__ == "__main__":
    # Check if running in container (disable debug mode to prevent reload loops)
    debug_mode = os.environ.get('FLASK_ENV') != 'production'

    # Use persistent certificates
    cert_file = '/app/certs/cert.pem'
    key_file = '/app/certs/key.pem'

    # Fallback to adhoc if certs don't exist (for local dev without Docker)
    if os.path.exists(cert_file) and os.path.exists(key_file):
        ssl_context = (cert_file, key_file)
    else:
        ssl_context = 'adhoc'

    app.run(host='0.0.0.0', port=5002, debug=debug_mode, ssl_context=ssl_context)
