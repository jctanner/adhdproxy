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
    logger.debug(f'videoid: {videoid} formatid:{formatid} audio:{audio_only} video:{video_only}')
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
        cmd = f'yt-dlp --dump-json --clean-info-json --dump-single-json "ytsearch5:{q}"'
        logger.debug(cmd)
        pid = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        lines = pid.stdout.decode('utf-8').split('\n')
        for line in lines:
            try:
                ds = json.loads(line)
                videos.append({'id': ds['id'], 'title': ds['title']})

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

        logger.debug(videos)

    else:
        # list what has already been cached
        vfiles = glob.glob(f'{youtubecache}/*/data.json')
        for vfile in vfiles:
            logger.debug(f'read {vfile}')
            try:
                with open(vfile, 'r') as f:
                    ds = json.loads(f.read())
                videos.append({'id': ds['id'], 'title': ds['title']})
            except Exception as e:
                logger.exception(e)

    return render_template('youtube.html', videos=videos)



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
    app.run(host='0.0.0.0', port=5002, debug=True, ssl_context='adhoc')
