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



app = Flask(__name__)
requests_cache.install_cache('/tmp/r.cache')
session = requests.Session()
youtubecache = '/tmp/youtubevids'
youtubecache_index = '/tmp/youtubevids/index.json'


def prefetch_youtube_video(videourl):
    # youtube-dl https://www.youtube.com/channel/UCoHhuummRZaIVX7bD4t2czg -f 249
    if not os.path.exists(youtubecache):
        os.makedirs(youtubecache)

    yindex = {}
    if os.path.exists(youtubecache_index):
        with open(youtubecache_index, 'r') as f:
            yindex = json.loads(f.read())

    if yindex.get(videourl):
        logger.debug('%s already fetched as %s' % (videourl, yindex[videourl]))
        return yindex[videourl]

    cmd = 'cd %s; youtube-dl --skip-download --print-json %s' % (youtubecache, videourl)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    (so, se) = p.communicate()
    jdata = json.loads(so)

    formatids = ['worst']
    for _format in jdata['formats']:
        if 'audio only' in _format['format']:
            continue
        if 'video only' in _format['format']:
            continue
        if _format['ext'] == 'webm':
            formatids.append(_format['format_id'])

    for x in formatids:
        cmd = "cd %s; youtube-dl -v -f %s --no-playlist --write-info-json '%s'" % (youtubecache, x, videourl)
        try:
            p = subprocess.Popen(cmd, shell=True)
            p.communicate()
        except Exception as e:
            continue
        if p.returncode == 0:
            break

    vfile = None
    jfiles = glob.glob('%s/*.info.json' % youtubecache)
    for jfile in jfiles:
        with open(jfile, 'r') as f:
            jfdata = json.loads(f.read())
        if jfdata['id'] == jdata['id']:
            vfile = jfile.replace('.info.json', '.webm')

    #if vfile is None:
    #    import epdb; epdb.st()

    yindex[videourl] = vfile

    with open(youtubecache_index, 'w') as f:
        f.write(json.dumps(yindex, indent=2, sort_keys=True))

    return vfile


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
    app.run(host='0.0.0.0', debug=True)
