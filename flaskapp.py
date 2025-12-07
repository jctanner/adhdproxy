#!/usr/bin/env python

import glob
import json
import os
import subprocess

import requests
import requests_cache
from logzero import logger
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from flask import Flask
from flask import jsonify
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


@app.route('/clear-cache')
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
        return '''
        <html>
        <body>
            <h2>Cache Cleared Successfully</h2>
            <p>Web request cache has been cleared. Your downloaded videos are safe.</p>
            <p><a href="/youtube">Back to YouTube</a> | <a href="/">Home</a></p>
        </body>
        </html>
        '''
    except Exception as e:
        logger.exception(e)
        return f'Error clearing cache: {str(e)}', 500


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
        return render_template('youtube-video.html', video=ds, videofile=videofile)

    videos = []

    # do a search ...
    if q:
        # Lazy pagination: only fetch enough for current page + 1 to check if there's more
        # For page N, we need to fetch N * per_page + 1 results
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

    else:
        # list what has already been cached
        vfiles = glob.glob(f'{youtubecache}/*/data.json')
        all_cached = []
        for vfile in vfiles:
            logger.debug(f'read {vfile}')
            try:
                with open(vfile, 'r') as f:
                    ds = json.loads(f.read())
                all_cached.append({
                    'id': ds['id'],
                    'title': ds['title'],
                    'upload_date': ds.get('upload_date'),
                    'timestamp': ds.get('timestamp', 0)
                })
            except Exception as e:
                logger.exception(e)

        # Sort cached results by timestamp (newest first)
        all_cached.sort(key=lambda x: x['timestamp'], reverse=True)

        # Paginate cached results
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        videos = all_cached[start_idx:end_idx]
        has_next = len(all_cached) > end_idx
        has_prev = page > 1

    return render_template('youtube.html',
                         videos=videos,
                         query=q,
                         page=page,
                         per_page=per_page,
                         has_next=has_next,
                         has_prev=has_prev)



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
